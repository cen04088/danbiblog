# -*- coding: utf-8 -*-
"""
단비 포스팅 스튜디오 (Streamlit)
로컬:  streamlit run app.py
배포:  GitHub push → share.streamlit.io → Secrets에 GEMINI_API_KEY 등록
"""
import json
import re
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types, errors

# ───────────────────────────────────────────────
# 상수 — 절대 바뀌면 안 되는 문구
# ───────────────────────────────────────────────
OPENING = "안녕하세요 :) 단비 언니입니다(!)"
CLOSING = (
    "오늘도 제 포스팅을 봐주셔서 너무 감사합니다♡\n"
    "오늘 하루도 즐겁고 행복한 하루 보내세요(!)"
)

STYLE = """너는 네이버 블로그 '단비 언니'의 문체를 그대로 재현하는 초안 작가다.
반려견 단비(중형견, 관절이 약함, 털갈이 심함)와의 일상을 곁들인 협찬 제품 리뷰를 쓴다.

[문체 규칙 — 반드시]
- 종결어미 기본값은 '~더라고요'. '~답니다' '~좋았어요' '~같아요'를 섞는다.
- 거의 모든 문단을 ♥ 또는 (!) 또는 ㅎㅎ 로 닫는다. 맨 마침표로 끝내지 마라.
- '너무/진짜/엄청/제일' 을 자연스럽게 자주 쓴다.
- 독자에게 말을 건다: "귀엽지 않나요?!" "사이즈 괜찮죠?!" "기억하시나요?! ㅎㅎ"
- 쉼표로 근거 두세 개를 이어 붙인 중장문을 쓴다.
- 나는 '저는', 강아지는 '단비'.
- ♡ 는 클로징에서만. ㅠㅠ 는 불편했던 이야기에서만.

[분량과 디테일 — 반드시]
- 각 문단은 최소 3문장 이상. 짧게 끝내지 말고 구체적인 장면으로 채워라.
- 시간·장소·단비의 표정이나 행동 같은 구체적 디테일을 문단마다 하나 이상 넣어라.
- 가능하면 이전에 쓰던 제품이나 방법과 비교하는 문장을 한 번 이상 넣어라.
- 오감(냄새, 촉감, 소리, 온도) 중 하나를 살려 묘사하는 문장을 섞어라.

[금지]
- 맞춤법을 과하게 다듬지 마라. 느슨한 구어체가 이 블로그의 목소리다.
- 효능을 단정하지 마라. "~에 도움을 줄 수 있어요" 식 완충 어법.
- AI 티 표현 금지: '뿐만 아니라', '결론적으로', '다양한 측면에서', 불릿 나열.
- 지정된 기호 외의 이모지 금지.

[인포박스 포맷 — 시그니처]
잠깐, [용어]?!

: [용어]는 [정의]로, [효용]에 도움을 줄 수 있어요!"""

BANNED = ["치료", "완치", "부작용 없음", "부작용이 없", "100%", "효과가 보장", "의학적으로 입증"]
CLOSERS = ("♥", "(!)", "ㅎㅎ", "?!", "♡", "🫡")

CUSTOM = "직접 입력"
HOOK_OPTIONS = [
    "요즘 비가 자주 와요", "날씨가 부쩍 더워졌어요", "날씨가 쌀쌀해졌어요",
    "환절기라 털갈이가 심해요", "미세먼지가 심한 날이 많아요",
    "산책하기 좋은 날씨예요", "이사한 지 얼마 안 됐어요",
]
PROBLEM_OPTIONS = [
    "산책할 때 옷을 입히면 더워해요", "관절이 약해서 오래 걷는 걸 힘들어해요",
    "털갈이가 심해서 집안이 지저분해요", "피부가 예민해서 트러블이 잦아요",
    "발바닥이 미끄러워해요", "산책 후 발 닦이는 걸 싫어해요",
    "낯을 많이 가려서 외출을 꺼려해요",
]
POINT_OPTIONS = [
    "사이즈가 잘 맞아요", "소재가 부드러워요", "입히기 편해요(벨크로·지퍼 등)",
    "냉감 소재라 시원해요", "보온이 잘 돼요", "세탁이 편해요",
    "디자인이 예뻐요", "가성비가 좋아요", "냄새가 안 나요", "튼튼해요",
]

LAST_INPUT_FILE = Path(".last_input.json")


# ───────────────────────────────────────────────
# 최근 입력값 — 반복되는 값(브랜드/스펙/고지문구) 재입력 방지
# ───────────────────────────────────────────────
def load_last():
    if LAST_INPUT_FILE.exists():
        try:
            return json.loads(LAST_INPUT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_last(b):
    data = {
        "brand": b["brand"],
        "specs": b["specs"],
        "disc": b["disc"],
        "sponsored": b["sponsored"],
    }
    try:
        LAST_INPUT_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ───────────────────────────────────────────────
# 룰베이스 — 골격 + 사진 슬롯 가이드
# 각 항목은 (kind, value, slot) — slot은 재생성 버튼을 붙일 수 있는 원고 슬롯 이름
# ───────────────────────────────────────────────
def build(b, filled):
    S = [("text", OPENING, None), ("text", filled.get("hook", ""), "hook")]
    S.append(("photo", "단비 근황 컷 · 눕방이나 산책 사진", None))

    card = [b["pname"]] + [f"{k} : {v}" for k, v in b["specs"]]
    S.append(("text", "\n".join(card), None))
    S.append(("photo", "제품 패키지 또는 착용 전신샷", None))

    for i, p in enumerate(b["points"]):
        S.append(("photo", f"'{p}' 이 보이는 컷", None))
        S.append(("text", filled.get(f"point{i}", ""), f"point{i}"))
        if filled.get(f"info{i}"):
            S.append(("text", filled[f"info{i}"], f"info{i}"))

    S.append(("text", f"접기/펴기\n{b['pfull']} 실사용 후기", None))
    for _ in range(3):
        S.append(("photo", "접기/펴기 안에 넣을 사진", None))

    S.append(("photo", "단비가 편안하게 쉬는 마무리 컷", None))
    S.append(("text", filled.get("wrap", ""), "wrap"))
    if b["sponsored"]:
        S.append(("text", b["disc"], None))
    S.append(("text", CLOSING, None))
    return [(t, v, s) for t, v, s in S if v]


# ───────────────────────────────────────────────
# 체커
# ───────────────────────────────────────────────
def check(blocks, b):
    text = "\n\n".join(v for t, v, _ in blocks if t == "text")
    out = []

    if b["sponsored"] and not re.search(r"제공받아|대가|지원받아|협찬", text):
        out.append(("error", "협찬 고지 문구가 없습니다. 반드시 넣어주세요."))
    for w in BANNED:
        if w in text:
            out.append(("error", f"단정적인 효능 표현: '{w}' — 빼주세요."))
    if OPENING not in text:
        out.append(("error", "오프닝 인사가 바뀌었습니다."))
    if CLOSING not in text:
        out.append(("error", "클로징 인사가 바뀌었습니다."))

    n = text.count(b["pfull"]) if b["pfull"] else 0
    if n < 3:
        out.append(("warning", f"검색용 이름이 {n}번만 나옵니다 (3~5번 권장)"))
    elif n > 5:
        out.append(("warning", f"검색용 이름이 {n}번 — 너무 많으면 광고로 보입니다"))

    paras = [p for p in text.split("\n\n") if p.strip()]
    closed = sum(1 for p in paras if p.strip().endswith(CLOSERS))
    ratio = closed / max(len(paras), 1)
    if ratio < 0.5:
        out.append(("warning", f"♥ (!) ㅎㅎ 로 끝나는 문단이 {ratio:.0%} — 톤이 조금 딱딱해요"))

    n_photo = sum(1 for t, _, _ in blocks if t == "photo")
    if n_photo < 8:
        out.append(("warning", f"사진 자리가 {n_photo}개 — 평소보다 적어요"))

    if not out:
        out.append(("success", "이상 없어요. 그대로 올리셔도 됩니다 ♥"))
    return out


# ───────────────────────────────────────────────
# LLM
# ───────────────────────────────────────────────
def slot_briefs(b):
    slots = [{
        "slot": "hook",
        "brief": f"오프닝 인사 다음에 올 도입부 3~5문장. 근황: {b['hook']}. "
                 f"단비의 문제 상황: {b['problem']}. 그래서 \"{b['pfull']}\"를 소개하겠다는 "
                 f"흐름으로 자연스럽게 이어라. 제품명은 큰따옴표로 감싸라. "
                 f"구체적인 장면(언제, 어디서, 단비가 뭘 하고 있었는지)으로 시작해라."
    }]
    for i, p in enumerate(b["points"]):
        extra = f' 문단 안에 "{b["pfull"]}" 를 한 번 넣어라.' if i % 2 == 0 else ""
        slots.append({"slot": f"point{i}",
                      "brief": f"좋았던 점 '{p}' 를 4~6문장 문단으로 풀어라. "
                               f"실제 있었던 장면처럼 구체적으로 쓰고, 이전 제품이나 방법과 "
                               f"비교하는 문장을 하나 넣어라.{extra}"})
        if i < len(b["terms"]):
            slots.append({"slot": f"info{i}",
                          "brief": f"'{b['terms'][i]}' 를 시그니처 인포박스 포맷으로 작성하라."})
    slots.append({"slot": "wrap",
                  "brief": f"단비가 제품을 편하게 쓰는 모습으로 마무리하는 감정 문단 3~4문장, "
                           f"여운이 남게 써라. \"{b['pfull']}\" 를 한 번 포함하라."})
    return slots


@st.cache_resource
def get_client(key):
    return genai.Client(api_key=key)


def generate_slot(b, key, brief):
    prompt = f"""아래 협찬 리뷰의 슬롯 하나만 써라.

브랜드: {b['brand']}
제품명: {b['pname']}
검색용 이름: {b['pfull']}
스펙: {' / '.join(f'{k} {v}' for k, v in b['specs'])}

슬롯 지시사항: {brief}

원고 텍스트만 출력해라. 설명이나 따옴표로 감싸지 마라."""

    r = get_client(key).models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=STYLE, max_output_tokens=1500),
    )
    return r.text.strip()


def write(b, key):
    return {s["slot"]: generate_slot(b, key, s["brief"]) for s in slot_briefs(b)}


def rewrite_one(b, key, slot):
    brief = next(s["brief"] for s in slot_briefs(b) if s["slot"] == slot)
    return generate_slot(b, key, brief)


def friendly_error(e):
    if isinstance(e, errors.APIError):
        if e.code in (401, 403):
            return "API 키가 유효하지 않아요. Secrets에 등록한 GEMINI_API_KEY를 확인해주세요."
        if e.code == 429:
            return "API 사용량 한도를 초과했어요. 잠시 후 다시 시도하거나 사용량 한도를 확인해주세요."
        return "네트워크나 서버 문제로 요청이 실패했어요. 다시 눌러주세요."
    return f"초안을 못 만들었어요. 다시 눌러주세요.\n\n{e}"


# ───────────────────────────────────────────────
# 화면
# ───────────────────────────────────────────────
st.set_page_config(page_title="단비 포스팅 스튜디오", page_icon="♥", layout="wide")
st.title("단비 포스팅 스튜디오 ♥")
st.caption("제품 정보만 넣으면, 붙여넣기 순서 그대로 초안이 나옵니다")

try:
    KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    KEY = ""
LAST = load_last()

with st.sidebar:
    st.header("제품 정보")
    brand = st.text_input("브랜드", value=LAST.get("brand", ""), placeholder="바잇미")
    pname = st.text_input("제품명", placeholder="바잇미 산리오캐릭터즈 버그쉴드 쿨베스트",
                          help="제품 카드에 그대로 들어갑니다")
    pfull = st.text_input("검색용 이름", placeholder="바잇미 산리오 해충방지 강아지 쿨티",
                          help="본문에 3~5번 자연스럽게 반복됩니다")

    default_spec_lines = "\n".join(f"{k} : {v}" for k, v in LAST.get("specs", [])) or \
        "색상 : 블루, 옐로우, 레드\n사이즈 : S ~ 3XL"
    spec_raw = st.text_area("스펙", default_spec_lines, help="한 줄에 하나씩,  항목 : 내용")

    st.header("이번 글 이야기")
    hook_choice = st.selectbox("요즘 근황 · 계절 한 줄", HOOK_OPTIONS + [CUSTOM])
    hook = st.text_input("근황 직접 입력", placeholder="예: 비 자주 오는 시기, 이사 후 벌레가 많음") \
        if hook_choice == CUSTOM else hook_choice

    problem_choice = st.selectbox("단비가 겪던 문제", PROBLEM_OPTIONS + [CUSTOM])
    problem = st.text_input("문제 직접 입력", placeholder="예: 산책 때 옷 입히면 단비가 더워함") \
        if problem_choice == CUSTOM else problem_choice

    point_choices = st.multiselect("좋았던 점 (여러 개 선택 가능)", POINT_OPTIONS)
    extra_points_raw = st.text_area("그 외 좋았던 점 (목록에 없으면 직접 입력)",
                                    placeholder="한 줄에 하나씩", height=80)
    terms_raw = st.text_area("「잠깐, ○○?!」로 설명할 용어", placeholder="에코쉴드 방충가공\n강아지 쿨티",
                             help="한 줄에 하나씩")

    sponsored = st.checkbox("협찬 받은 제품입니다", value=LAST.get("sponsored", True))
    disc = st.text_input("고지 문구", LAST.get("disc", "본 포스팅은 업체로부터 제품을 제공받아 솔직하게 작성하였습니다.")) \
        if sponsored else ""

    go = st.button("초안 만들기", type="primary", width="stretch")

if go:
    if not KEY:
        st.error("API 키가 설정되지 않았습니다. (배포 설정 → Secrets → GEMINI_API_KEY)")
        st.stop()
    points = point_choices + [x.strip() for x in extra_points_raw.splitlines() if x.strip()]
    if not pname or not points:
        st.error("제품명과 '좋았던 점'은 최소 한 개 필요합니다.")
        st.stop()

    specs = [tuple(x.split(":", 1)) for x in spec_raw.splitlines() if ":" in x]
    specs = [(k.strip(), v.strip()) for k, v in specs]

    b = {
        "brand": brand, "pname": pname, "pfull": pfull or pname,
        "specs": specs,
        "hook": hook, "problem": problem,
        "points": points,
        "terms": [x.strip() for x in terms_raw.splitlines() if x.strip()],
        "sponsored": sponsored, "disc": disc,
    }

    with st.spinner("단비 언니 말투로 쓰는 중…"):
        try:
            st.session_state.filled = write(b, KEY)
            st.session_state.brief = b
            st.session_state.draft_id = st.session_state.get("draft_id", 0) + 1
            save_last(b)
        except Exception as e:
            st.error(friendly_error(e))

if "filled" in st.session_state:
    b = st.session_state.brief
    filled = st.session_state.filled
    blocks = build(b, filled)
    draft_id = st.session_state.get("draft_id", 0)

    for lvl, msg in check(blocks, b):
        getattr(st, lvl)(msg)

    n_photo = sum(1 for t, _, _ in blocks if t == "photo")
    files = st.file_uploader(
        f"사진을 한 번에 올려주세요 (필요한 사진: {n_photo}장)",
        type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
        key=f"uploader_{draft_id}",
    )

    order = list(range(n_photo))
    if files:
        st.caption("자리마다 들어갈 사진을 바꾸고 싶으면 아래에서 골라주세요. 기본값은 업로드한 순서입니다.")
        options = ["(비워두기)"] + [f"{i + 1}. {f.name}" for i, f in enumerate(files)]
        cols = st.columns(4)
        order = []
        for pi in range(n_photo):
            default_idx = pi + 1 if pi < len(files) else 0
            with cols[pi % 4]:
                choice = st.selectbox(f"사진 {pi + 1} 자리", options, index=default_idx,
                                      key=f"slot_{draft_id}_{pi}")
            order.append(options.index(choice) - 1 if choice != "(비워두기)" else None)

    st.divider()
    st.subheader("발행 순서")
    st.caption("위에서부터 복사해서 붙여넣고, 초록 칸이 나오면 그 자리에 사진을 넣으세요")

    pi = 0
    for kind, val, slot in blocks:
        if kind == "text":
            st.code(val, language=None)          # ← 우측 상단에 복사 버튼
            if slot:
                if st.button("🔄 이 문단 다시 쓰기", key=f"rewrite_{draft_id}_{slot}"):
                    with st.spinner("다시 쓰는 중…"):
                        try:
                            st.session_state.filled[slot] = rewrite_one(b, KEY, slot)
                            st.rerun()
                        except Exception as e:
                            st.error(friendly_error(e))
        else:
            fi = order[pi] if pi < len(order) else None
            c1, c2 = st.columns([1, 4])
            with c1:
                if fi is not None and files and fi < len(files):
                    st.image(files[fi], width="stretch")
                else:
                    st.markdown(
                        "<div style='height:90px;border:2px dashed #5FCBAA;border-radius:10px;"
                        "display:flex;align-items:center;justify-content:center;color:#5FCBAA;"
                        "font-size:24px'>＋</div>", unsafe_allow_html=True)
            with c2:
                st.success(f"**사진 {pi + 1}** · {val}")
            pi += 1

    st.divider()
    with st.expander("체크리스트 다시 보기"):
        for lvl, msg in check(blocks, b):
            getattr(st, lvl)(msg)
