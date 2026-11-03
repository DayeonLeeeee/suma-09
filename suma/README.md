# 수마 (suma) — AI 수학 진단 시스템

고등학교 수학 문제 촬영 → OCR → 채점 → 해설 생성

## 구조

```
app.py              Flask 서버 (API + 프론트엔드 서빙)
static/index.html   시연 페이지 → /  (문제 촬영 → OCR → 풀이 촬영 → 채점 → 해설, 30번은 전용 처리, DB 저장 없음)
static/js/demo.js
static/field/       현장연구 때 쓰던 학생 화면 (번호 로그인, Supabase 기록) → /field/
sql/schema.sql      Supabase 테이블 스키마
tests/              E2E·API 테스트 (외부 API와 DB는 가짜 응답으로 대체)
```

## 테스트

```bash
pip install -r tests/requirements-dev.txt
pytest tests          # 브라우저는 로컬 Google Chrome 사용
```

## 배포 (Railway)

1. GitHub 레포 연결
2. 환경변수 설정:

| 변수 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `OPENAI_API_KEY` | GPT-4o API 키 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `MATHPIX_APP_ID` | Mathpix 앱 ID |
| `MATHPIX_APP_KEY` | Mathpix 앱 키 |

3. Railway가 `Procfile`로 자동 빌드/배포

## Supabase

`sql/schema.sql`을 Supabase SQL Editor에서 실행.

테이블: `student`, `student_upload_problem`, `handwriting_solution`, `error_diagnosis`

## 로컬 실행

```bash
pip install -r requirements.txt
# .env.example → .env 복사 후 키 입력
export $(cat .env | xargs)
python app.py
```

## API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/health` | GET | 서버 상태 |
| `/api/ocr` | POST | 이미지 OCR (Mathpix + Gemini + Claude) |
| `/api/grade` | POST | 풀이 채점 (Claude). `reference_solution`을 넣으면 채점 기준으로 참고 |
| `/api/recommend` | POST | 오답유형 기반 유사 문제 추천 (설계 단계) |
| `/api/solution` | POST | 해설 생성 (Claude + GPT-4o) |
