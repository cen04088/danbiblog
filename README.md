# 단비 포스팅 스튜디오 ♥

제품 정보를 넣으면 단비 언니 문체로 협찬 리뷰 초안을 만들고,
스마트에디터에 붙여넣을 순서대로 텍스트 블록과 사진 자리를 배치해줍니다.

---

## 배포 (한 번만, 민준님이)

### 1. 키 발급
aistudio.google.com/apikey → **이 앱 전용 키를 새로 발급**하세요.
개인 키를 재사용하지 말고, 프로젝트에 **사용량 상한**을 걸어두는 걸 권합니다.

### 2. GitHub
이 폴더를 GitHub 리포지토리에 올립니다.
`.gitignore`에 `secrets.toml`이 이미 들어있으니 **키가 커밋될 일은 없습니다.**

### 3. Streamlit Community Cloud
1. share.streamlit.io → **New app** → 리포지토리 선택 → Main file: `app.py`
2. **Advanced settings → Secrets** 에 아래 한 줄 붙여넣기:
   ```
   GEMINI_API_KEY = "AIza..."
   ```
3. Deploy → 나온 URL을 여자친구분께 전달

### 4. (선택) 비공개로
Settings → Sharing → 여자친구분 이메일만 허용.
공개로 두면 링크 아는 사람이 API를 쓰게 되니 **막아두는 걸 권합니다.**

---

## 로컬에서 테스트

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # 키 채우기
streamlit run app.py
```

---

## 여자친구분 사용법

1. 왼쪽에 제품 정보 채우기 → **초안 만들기**
2. 사진 여러 장을 한 번에 올리면 순서대로 자리에 들어감
3. 위에서부터: 회색 박스 **복사 버튼** → 스마트에디터에 붙여넣기
   → 초록 칸 나오면 그 사진 넣기 → 다음 블록 복사 → 반복
4. 맨 위 **빨간 경고는 반드시 해결**하고 발행

발행 버튼은 직접 누릅니다. 네이버는 자동 발행을 약관으로 금지하고,
계정 제재로 이어질 수 있어서 마지막 한 단계는 사람이 합니다.

---

## 문체를 더 정확하게

`app.py` 상단의 `STYLE` 문자열이 문체 규칙 전부입니다.
초안이 어색하면 여기에 규칙을 한 줄씩 추가하세요.
기존 글을 10편쯤 더 넣고 프로파일을 다시 뽑으면 눈에 띄게 정확해집니다.
