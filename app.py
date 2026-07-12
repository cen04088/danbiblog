# -*- coding: utf-8 -*-
"""
단비 포스팅 스튜디오 (Streamlit)
로컬:  streamlit run app.py
배포:  GitHub push → share.streamlit.io → Secrets에 GEMINI_API_KEY 등록
"""
import json
import re
import streamlit as st
import google.generativeai as genai

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


# ───────────────────────────────────────────────
# 룰베이스 — 골격 + 사진 슬롯 가이드
# ───────────────────────────────────────────────
def build(b, filled):
    S = [("text", OPENING), ("text", filled.get("hook", ""))]
    S.append(("photo", "단비 근황 컷 · 눕방이나 산책 사진"))

    card = [b["pname"]] + [f"{k} : {v}" for k, v in b["specs"]]
    if b["link"]:
        card.append(b["link"])
    S.append(("text", "\n".join(card)))
    S.append(("photo", "제품 패키지 또는 착용 전신샷"))

    for i, p in enumerate(b["points"]):
        S.append(("photo", f"‘{p}’ 이 보이는 컷"))
        S.append(("text", filled.get(f"point{i}", "")))
        if filled.get(f"info{i}"):
            S.append(("text", filled[f"info{i}"]))

    S.append(("text", f"접기/펴기\n{b['pfull']} 실사용 후기"))
    for _ in range(3):
        S.append(("photo", "접기/펴기 안에 넣을 사진"))

    S.append(("photo", "단비가 편안하게 쉬는 마무리 컷"))
    S.append(("text", filled.get("wrap", "")))
    if b["sponsored"]:
        S.append(("text", b["disc"]))
    S.append(("text", CLOSING))
    return [(t, v) for t, v in S if v]


# ───────────────────────────────────────────────
# 체커
# ───────────────────────────────────────────────
def check(blocks, b):
    text = "\n\n".join(v for t, v in blocks if t == "text")
    out = []

    if b["sponsored"] and not re.search(r"제공받아|대가|지원받아|협찬", text):
        out.append(("error", "협찬 고지 문구가 없습니다. 반드시 넣어주세요."))
    for w in BANNED:
        if w in text:
            out.append(("error", f"단정적인 효능 표현: ‘{w}’ — 빼주세요."))
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

    slots = sum(1 for t, _ in blocks if t == "photo")
    if slots < 8:
        out.append(("warning", f"사진 자리가 {slots}개 — 평소보다 적어요"))

    if not out:
        out.append(("success", "이상 없어요. 그대로 올리셔도 됩니다 ♥"))
    return out


# ───────────────────────────────────────────────
# LLM
# ───────────────────────────────────────────────
def write(b, key):
    slots = [{
        "slot": "hook",
        "brief": f"오프닝 인사 다음에 올 도입부 2~3문장. 근황: {b['hook']}. "
                 f"단비의 문제 상황: {b['problem']}. 그래서 \"{b['pfull']}\"를 소개하겠다는 "
                 f"흐름으로 자연스럽게 이어라. 제품명은 큰따옴표로 감싸라."
    }]
    for i, p in enumerate(b["points"]):
        extra = f' 문단 안에 "{b["pfull"]}" 를 한 번 넣어라.' if i % 2 == 0 else ""
        slots.append({"slot": f"point{i}",
                      "brief": f"좋았던 점 '{p}' 를 2~4문장 문단으로 풀어라.{extra}"})
        if i < len(b["terms"]):
            slots.append({"slot": f"info{i}",
                          "brief": f"'{b['terms'][i]}' 를 시그니처 인포박스 포맷으로 작성하라."})
    slots.append({"slot": "wrap",
                  "brief": f"단비가 제품을 편하게 쓰는 모습으로 마무리하는 감정 문단 2~3문장. "
                           f"\"{b['pfull']}\" 를 한 번 포함하라."})

    prompt = f"""아래 협찬 리뷰의 각 슬롯 원고를 써라.

브랜드: {b['brand']}
제품명: {b['pname']}
검색용 이름: {b['pfull']}
스펙: {' / '.join(f'{k} {v}' for k, v in b['specs'])}
체험 메모: {b['notes'] or '(없음)'}

슬롯:
{json.dumps(slots, ensure_ascii=False, indent=2)}

JSON 객체 하나만 출력하라. 키는 slot 이름, 값은 원고 문자열.
코드펜스도 다른 설명도 붙이지 마라."""

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-flash-latest", system_instruction=STYLE)
    r = model.generate_content(
        prompt,
        generation_config={"max_output_tokens": 4000, "response_mime_type": "application/json"},
    )
    raw = r.text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw)


# ───────────────────────────────────────────────
# 화면
# ───────────────────────────────────────────────
st.set_page_config(page_title="단비 포스팅 스튜디오", page_icon="♥", layout="wide")
st.title("단비 포스팅 스튜디오 ♥")
st.caption("제품 정보만 넣으면, 붙여넣기 순서 그대로 초안이 나옵니다")

KEY = st.secrets.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("제품 정보")
    brand = st.text_input("브랜드", placeholder="바잇미")
    pname = st.text_input("제품명", placeholder="바잇미 산리오캐릭터즈 버그쉴드 쿨베스트",
                          help="제품 카드에 그대로 들어갑니다")
    pfull = st.text_input("검색용 이름", placeholder="바잇미 산리오 해충방지 강아지 쿨티",
                          help="본문에 3~5번 자연스럽게 반복됩니다")
    spec_raw = st.text_area("스펙", "색상 : 블루, 옐로우, 레드\n사이즈 : S ~ 3XL",
                            help="한 줄에 하나씩,  항목 : 내용")
    link = st.text_input("상품 링크", placeholder="https://naver.me/...")

    st.header("이번 글 이야기")
    hook = st.text_input("요즘 근황 · 계절 한 줄", placeholder="비 자주 오는 시기, 이사 후 벌레가 많음")
    problem = st.text_input("단비가 겪던 문제", placeholder="산책 때 옷 입히면 단비가 더워함")
    points_raw = st.text_area("좋았던 점", placeholder="양쪽 벨크로라 다리 안 들고 입힘\n냉감 소재라 산책 때 덜 더워함",
                              help="한 줄에 하나씩", height=110)
    terms_raw = st.text_area("「잠깐, ○○?!」로 설명할 용어", placeholder="에코쉴드 방충가공\n강아지 쿨티",
                             help="한 줄에 하나씩")
    notes = st.text_area("메모", placeholder="아무렇게나 적어도 됩니다")

    sponsored = st.checkbox("협찬 받은 제품입니다", value=True)
    disc = st.text_input("고지 문구", "본 포스팅은 업체로부터 제품을 제공받아 솔직하게 작성하였습니다.") \
        if sponsored else ""

    go = st.button("초안 만들기", type="primary", use_container_width=True)

if go:
    if not KEY:
        st.error("API 키가 설정되지 않았습니다. (배포 설정 → Secrets → GEMINI_API_KEY)")
        st.stop()
    if not pname or not points_raw.strip():
        st.error("제품명과 ‘좋았던 점’은 최소 한 줄 필요합니다.")
        st.stop()

    b = {
        "brand": brand, "pname": pname, "pfull": pfull or pname, "link": link,
        "specs": [tuple(x.split(":", 1)) for x in spec_raw.splitlines() if ":" in x],
        "hook": hook, "problem": problem,
        "points": [x.strip() for x in points_raw.splitlines() if x.strip()],
        "terms": [x.strip() for x in terms_raw.splitlines() if x.strip()],
        "notes": notes, "sponsored": sponsored, "disc": disc,
    }
    b["specs"] = [(k.strip(), v.strip()) for k, v in b["specs"]]

    with st.spinner("단비 언니 말투로 쓰는 중…"):
        try:
            st.session_state.blocks = build(b, write(b, KEY))
            st.session_state.brief = b
        except Exception as e:
            st.error(f"초안을 못 만들었어요. 다시 눌러주세요.\n\n{e}")

if "blocks" in st.session_state:
    blocks = st.session_state.blocks
    b = st.session_state.brief

    for lvl, msg in check(blocks, b):
        getattr(st, lvl)(msg)

    n_photo = sum(1 for t, _ in blocks if t == "photo")
    files = st.file_uploader(
        f"사진 {n_photo}장을 한 번에 올려주세요 — 순서대로 자리에 들어갑니다",
        type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
    )

    st.divider()
    st.subheader("발행 순서")
    st.caption("위에서부터 복사해서 붙여넣고, 초록 칸이 나오면 그 자리에 사진을 넣으세요")

    pi = 0
    for kind, val in blocks:
        if kind == "text":
            st.code(val, language=None)          # ← 우측 상단에 복사 버튼
        else:
            c1, c2 = st.columns([1, 4])
            with c1:
                if files and pi < len(files):
                    st.image(files[pi], use_container_width=True)
                else:
                    st.markdown(
                        "<div style='height:90px;border:2px dashed #5FCBAA;border-radius:10px;"
                        "display:flex;align-items:center;justify-content:center;color:#5FCBAA;"
                        "font-size:24px'>＋</div>", unsafe_allow_html=True)
            with c2:
                st.success(f"**사진 {pi + 1}** · {val}")
            pi += 1
