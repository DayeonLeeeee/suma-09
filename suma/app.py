"""
suma server — Railway 배포용 (고1 순열·조합 특화)
OCR: Mathpix + Gemini 2.5 Pro + Claude 판정
채점: Claude Opus (증거 기반 감점형, Batanero 15유형 오류분류)
해설: Claude 정답 → GPT-4o 풀이 → Claude 검증
"""

import os, json, base64, re, datetime, traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
import requests as http_requests
import anthropic
import google.generativeai as genai

# ─── 환경변수 ──────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY    = os.environ["OPENAI_API_KEY"]
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
MATHPIX_APP_ID    = os.environ["MATHPIX_APP_ID"]
MATHPIX_APP_KEY   = os.environ["MATHPIX_APP_KEY"]

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)


# ═══════════════════════════════════════════════════
# 프롬프트 모듈
# ═══════════════════════════════════════════════════

PROMPT_VERSION = "v3.0-2026-10-12"

# ─── Batanero 15유형 오류 분류 체계 ──────────────────
BATANERO_ERROR_TYPES = """[Batanero 오류 분류 체계 — 15유형]
각 유형은 조합론 학습에서 나타나는 특정 오류 패턴을 분류합니다.
학생 풀이에서 오류를 발견하면, 아래 중 가장 부합하는 유형 하나를 선택하세요.

B01. 체계적 나열 실패 (Listing errors)
  - 경우를 빠뜨리거나 중복 나열
  - 예: 3개 중 2개 택하는 조합에서 (A,B), (B,C)만 나열하고 (A,C) 누락

B02. 순열-조합 혼동 (Permutation-combination confusion)
  - 순서가 없는 문제에 순열 적용, 또는 순서가 있는 문제에 조합 적용
  - 예: "위원 3명을 뽑는" 문제에 P(n,r) 사용

B03. 합의 법칙-곱의 법칙 혼동 (Addition-multiplication principle confusion)
  - 동시에 일어나는 사건에 합의 법칙, 또는 배타적 사건에 곱의 법칙 적용
  - 예: 셔츠 3벌과 바지 2벌의 조합 수를 3+2=5로 계산

B04. 고정 조건 처리 오류 (Fixed-position/constraint errors)
  - 특정 위치/조건 고정 후 나머지 처리에서 오류
  - 예: "A가 반드시 포함"인데 전체에서 선택 후 A 포함 여부 미확인

B05. 중복 계산 (Overcounting)
  - 같은 경우를 여러 번 세거나, 제거해야 할 중복을 놓침
  - 예: 원순열에서 회전 동치를 고려하지 않음

B06. 공식 오적용 (Formula misapplication)
  - nPr, nCr, n! 등의 공식을 잘못 적용 (n, r 값 대입 오류 포함)
  - 예: C(5,3)을 5!/(3!×3!)로 계산

B07. 여사건 접근 실패 (Complement approach failure)
  - 여사건으로 풀어야 효율적인 문제에서 직접 세기 시도 후 오류, 또는 여사건 설정 자체가 잘못됨
  - 예: "적어도 1개" 문제에서 전체에서 0개인 경우를 빼야 하는데 직접 나열

B08. 조건 누락/오독 (Condition oversight/misreading)
  - 문제의 제약조건을 빠뜨리거나 잘못 해석
  - 예: "서로 다른"이라는 조건을 무시하고 중복 허용으로 풀이

B09. 분류 기준 오류 (Partitioning errors)
  - 경우를 나눌 때 MECE(상호배타·전체포괄) 위반
  - 예: 짝수/홀수로 나누면서 0을 빠뜨림

B10. 자리 배분 오류 (Seat/slot allocation errors)
  - 자리·슬롯에 배치하는 문제에서 단계별 가용 수 계산 오류
  - 예: 5명을 3자리에 앉힐 때 첫째 자리 5, 둘째 자리 5(4가 아닌)로 계산

B11. 대칭성·동치 무시 (Symmetry/equivalence oversight)
  - nCr = nC(n-r) 등 대칭성을 활용하지 못하거나 동치 관계 무시
  - 예: C(10,8)을 직접 계산하면서 C(10,2)로 변환하지 못함 (오답 자체는 아니나, 그 과정에서 계산 오류 발생 시)

B12. 단계 간 논리 비약 (Logical gap between steps)
  - 풀이 단계 사이에 근거 없는 도약이 있음
  - 예: "경우의 수는 10이다"라고 쓰고 어떻게 구했는지 과정 없음

B13. 산술·대입 계산 오류 (Arithmetic/substitution errors)
  - 개념은 맞지만 사칙연산·대입 과정에서 실수
  - 예: 7×6×5 = 200 (정답 210)

B14. 문제 상황 모델링 실패 (Problem modeling failure)
  - 문제의 실생활/수학적 상황을 경우의 수 구조로 변환하는 데 실패
  - 예: "동아리에서 회장, 부회장을 뽑는" 문제를 조합으로 모델링

B15. 교육과정 범위 밖 개념 사용 (Out-of-curriculum concept)
  - 고1 순열·조합 단원에서 다루지 않는 개념 사용
  - 예: 이항정리, 포함배제 원리, 중복조합, 생성함수 사용
"""

# ─── 교육과정 범위 제약 (공통) ─────────────────────
CURRICULUM_CONSTRAINT = """[교육과정 범위 제약 — 반드시 준수]
고1 순열·조합 단원 평가입니다. 아래 허용 개념만 사용하세요.

[허용 개념 목록 — 6종 교과서 교집합]
• 합의 법칙: 두 사건이 동시에 일어나지 않을 때 경우의 수 m+n
• 곱의 법칙: 두 사건이 잇달아 일어날 때 경우의 수 m×n
• 순열의 정의·기호 nPr: 서로 다른 n개에서 r개를 택해 일렬로 나열
• 순열의 수 공식: nPr = n!/(n-r)!
• 계승: n! = n(n-1)…1, 0!=1, nP0=1
• 조합의 정의·기호 nCr: 순서 없이 r개를 택함
• 조합의 수 공식: nCr = n!/{r!(n-r)!}
• nC0=1, nCn=1
• nCr = nC(n-r) (조합의 대칭성)
• 파스칼 관계: nCr = (n-1)C(r-1) + (n-1)Cr
• 사건의 정의, 경우의 수의 정의
• 기본적인 사칙연산, 대입, 경우 나누기"""

# ─── 채점 프롬프트 (증거 기반 감점형) ────────────────
GRADING_SYSTEM = (
    "당신은 고등학교 1학년 순열·조합 단원 전문 채점 교사입니다. "
    "먼저 문제를 스스로 정확히 풀어 정답을 구한 뒤, 학생 풀이를 맥락과 논리 중심으로 채점합니다. "
    "모든 판단에는 학생 풀이 원문에서 직접 인용한 증거(evidence)가 반드시 필요합니다. "
    "증거 없이 감점하거나 오류를 지적하지 마세요. "
    "판단 근거로 고1 순열·조합 교과서 교집합 범위의 개념만 사용하세요. "
    "응답은 반드시 JSON 객체로만 시작하고 끝납니다."
)


def build_grading_prompt(problem_text, clean_steps, correct_answer):
    answer_info = f"\n[이 문제의 정답]\n{correct_answer}\n" if correct_answer else ""

    return f"""[문제]
{problem_text}
{answer_info}
[학생의 풀이]
{clean_steps}

{CURRICULUM_CONSTRAINT}

[허용 밖 개념을 학생이 사용한 경우]
답이 수학적으로 맞더라도, 이항정리·포함배제·중복조합·중복순열·확률·생성함수·수학적 귀납법 등 허용 밖 개념을 사용했다면:
- is_correct를 false로 판정
- error_category를 "B15"로 분류
- error_detail에 "허용 범위 밖 개념 사용: [개념명]"

{BATANERO_ERROR_TYPES}

[채점 원칙 — 매우 중요]
0. 먼저 당신이 직접 이 문제를 끝까지 풀어 정답을 구하세요.
1. 그 정답을 기준으로 학생 풀이를 채점하되, 글자 그대로 비교하지 마세요.
2. 학생이 다른 방법·다른 순서·다른 표기를 써도, 논리적으로 타당하고 같은 결론에 도달하면 "ok".
3. 중간 계산을 일부 생략했어도 수학적으로 맞으면 "ok".
4. OCR로 부호(-)·분수가 깨졌을 수 있으니, 표기 실수는 학생 의도를 고려해 관대하게 보고 실제 수학적 오류만 "wrong".
5. 학생의 최종 답이 정답과 일치하고 논리에 큰 결함이 없으면 is_correct=true.
6. 진짜 수학적으로 틀린 최초 단계만 "wrong", 그 이후는 "depends".

[증거 기반 채점 — 핵심 원칙]
- 모든 감점·오류 지적에는 학생 풀이 원문에서 직접 인용한 evidence가 필수.
- evidence는 학생이 실제로 쓴 문자열을 그대로 인용. 존재하지 않는 내용을 인용하지 마세요.
- evidence가 학생 풀이 어디에도 없으면, 해당 감점은 취소해야 합니다.
- "이 줄이 모범풀이와 똑같은가?"가 아니라 "이 단계가 수학적으로 옳고, 결론으로 가는 데 타당한가?"

[모순 검증 — 반드시 수행]
응답 전에 아래를 스스로 점검하세요:
1. is_correct=true인데 status="wrong"인 단계가 있으면 → 모순. 재검토.
2. is_correct=false인데 모든 단계가 "ok"이면 → 모순. 재검토.
3. error_step_index가 가리키는 단계의 status가 "wrong"이 아니면 → 모순. 수정.

[힌트 3단계 — 정보량을 점진적으로 늘리기]

hint_direction (방향 힌트, 1단계):
- 학생이 어느 부분을 다시 봐야 할지만 알려주세요.
- 정답이나 정답 근처 값은 절대 노출 금지. 공식 이름도 알려주지 마세요.
- 1줄 (20자 이내)로 짧게.
- 예: "두 번째 단계의 계산을 다시 확인해보세요."

hint_concept (개념 힌트, 2단계):
- 필요한 공식·정리·개념의 이름을 알려주세요.
- 그 개념이 왜 이 단계에 필요한지 한 문장 설명.
- 정답이나 정답 근처 값은 여전히 노출 금지.
- 2~3줄.
- 예: "이 문제는 순서가 없는 선택이므로 조합(C)을 사용해야 합니다."

hint_near_answer (근접 힌트, 3단계):
- 거의 답까지 보여주는 단계. 마지막 한두 계산만 학생이 하도록.
- 구체적인 식과 중간 값을 모두 노출.
- 단, 최종 답 자체는 직접 말하지 않고 학생이 구하게 둠.
- 예: "C(7,3) = 7×6×5 / (3×2×1) = 210/6 까지 계산하면, 나눗셈 한 번만 하면 답입니다."

[힌트 작성 원칙]
- 세 힌트는 같은 오류를 다른 깊이로 다룹니다. 서로 다른 주제를 다루지 마세요.
- 방향 → 개념 → 근접 순으로 정보량이 증가해야 합니다.
- 1단계는 절대 답 근처 값을 노출하지 마세요.
- 3단계는 학생이 마지막 한 발만 떼면 되도록 거의 다 풀어주세요.
- 당신의 설명·힌트에서도 허용 목록 밖 개념의 이름을 언급하거나 암시적으로 사용하지 마세요.

[중요] steps의 text는 LaTeX 없이 읽기 쉬운 수학 표현으로 작성하세요 (예: P(5,3), C(7,3), 5!).

반드시 아래 JSON 형식으로만 응답:
{{
    "is_correct": true/false,
    "error_step_index": null 또는 숫자,
    "steps": [
        {{
            "index": 1,
            "text": "읽기 쉬운 수학 표현",
            "status": "ok|wrong|depends",
            "explanation": "이 단계 설명",
            "evidence": "학생 풀이에서 직접 인용한 원문 (ok인 경우 생략 가능)"
        }}
    ],
    "error_category": null 또는 "B01"~"B15" 중 하나,
    "error_detail": "간단한 오류 설명",
    "ai_explanation": "학생에게 보여줄 설명 (한국어, 친절하게)",
    "hint_direction": "방향 힌트",
    "hint_concept": "개념 힌트",
    "hint_near_answer": "근접 힌트",
    "confidence": 0.0~1.0
}}"""


# ─── 해설 프롬프트 ───────────────────────────────────
def build_solution_prompt(problem_text, correct_answer):
    answer_constraint = f"\n[필수 정답]\n{correct_answer}\n" if correct_answer else ""

    return f"""당신은 고등학교 1학년 순열·조합 단원의 모범 풀이 전문가입니다.

[문제]
{problem_text}
{answer_constraint}
[작성 규칙]
1. 가장 정석적이고 교과서적인 풀이를 작성하세요. 다른 풀이법은 절대 포함하지 마세요.
2. 위 "필수 정답"으로 정확히 수렴하는 풀이를 작성하세요. 정답을 임의로 바꾸지 마세요.
3. 고1 순열·조합 교과서 교집합 범위의 개념만 사용하세요 (합의 법칙, 곱의 법칙, 순열 nPr, 조합 nCr, 계승 n!, 대칭성, 파스칼 관계).
   이항정리·포함배제 등 고2 이상 개념은 사용하지 마세요.
4. 단계 수는 문제에 맞게 2~5단계로 자연스럽게 구성하세요.
5. 각 단계는 제목, 설명, 핵심 수식으로 구성하세요.
6. 설명(content)과 수식(formula) 안의 수학 표현은 모두 $...$ 로 감싸세요. 한글은 $ 밖에.

[분량 제약 — 매우 중요]
- title: 10자 이내. 간결한 제목.
- content: 1~2문장만. 군더더기·반복·형식적 표현 최소화.
- formula: 그 단계의 핵심 식 한 줄만.
- concept_tags: 2~3개로 제한.

반드시 아래 JSON 형식으로만 응답:
{{
    "method_type": "풀이 방법 이름",
    "concept_tags": ["개념1", "개념2"],
    "answer": "최종 답 ($ 없이 간단히)",
    "steps": [
        {{"step": 1, "title": "단계 제목", "content": "설명 (수식은 $...$)", "formula": "$핵심 수식$"}}
    ]
}}"""


# ═══════════════════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════════════════

def parse_json_loose(s: str) -> dict:
    s = s.strip()
    s = re.sub(r'^```(?:json)?\s*\n?', '', s)
    s = re.sub(r'\n?```\s*$', '', s).strip()

    start = -1
    for i, c in enumerate(s):
        if c == '{':
            tail = s[i:i+200]
            if '"' in tail and ':' in tail:
                start = i
                break
    if start < 0:
        raise json.JSONDecodeError("no JSON object", s, 0)
    end = s.rfind('}')
    if end <= start:
        raise json.JSONDecodeError("no closing }", s, len(s))
    s = s[start:end+1]

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    def fix_backslashes(text):
        result, i = [], 0
        while i < len(text):
            c = text[i]
            if c == '\\' and i + 1 < len(text):
                nxt = text[i + 1]
                if nxt in '"\\/bfnrtu':
                    result.append(c); result.append(nxt); i += 2
                else:
                    result.append('\\\\'); i += 1
            else:
                result.append(c); i += 1
        return ''.join(result)

    return json.loads(fix_backslashes(s))


def validate_evidence(grading_result, student_text):
    """증거(evidence)가 학생 풀이 원문에 실제로 존재하는지 검증."""
    if not grading_result.get("steps"):
        return grading_result

    normalized_student = student_text.replace(" ", "").lower()
    needs_review = False

    for step in grading_result["steps"]:
        evidence = step.get("evidence", "")
        if not evidence or step.get("status") == "ok":
            continue

        normalized_evidence = evidence.replace(" ", "").lower()
        if normalized_evidence and normalized_evidence not in normalized_student:
            step["evidence_valid"] = False
            needs_review = True
        else:
            step["evidence_valid"] = True

    grading_result["_evidence_validated"] = True
    grading_result["_needs_review"] = needs_review
    return grading_result


def check_contradictions(result):
    """채점 결과 내부 모순 점검."""
    flags = []

    steps = result.get("steps", [])
    is_correct = result.get("is_correct", False)
    has_wrong = any(s.get("status") == "wrong" for s in steps)
    all_ok = all(s.get("status") == "ok" for s in steps)

    if is_correct and has_wrong:
        flags.append("correct_with_wrong_step")
    if not is_correct and all_ok and not result.get("error_category"):
        flags.append("incorrect_but_all_ok")

    error_idx = result.get("error_step_index")
    if error_idx is not None:
        matching = [s for s in steps if s.get("index") == error_idx]
        if matching and matching[0].get("status") != "wrong":
            flags.append("error_index_not_wrong")

    result["_contradiction_flags"] = flags
    return result


# ═══════════════════════════════════════════════════
# OCR
# ═══════════════════════════════════════════════════

def call_mathpix(image_b64, mime_type):
    resp = http_requests.post(
        "https://api.mathpix.com/v3/text",
        headers={"app_id": MATHPIX_APP_ID, "app_key": MATHPIX_APP_KEY, "Content-Type": "application/json"},
        data=json.dumps({
            "src": f"data:{mime_type};base64,{image_b64}",
            "formats": ["text", "latex_styled"],
            "data_options": {"include_latex": True},
        }),
    )
    if resp.status_code == 200:
        d = resp.json()
        return (d.get("latex_styled") or d.get("text", "")).strip()
    return ""


def call_gemini_ocr(image_b64, mime_type, mode="problem"):
    if mode == "solution":
        instruction = (
            "당신은 손글씨 수학 풀이 OCR 시스템입니다. "
            "학생이 쓴 풀이를 적힌 그대로 정확히 읽으세요. 오류를 고치지 마세요. "
            "단계별로 번호를 나누세요. "
            "중요: LaTeX 명령어(\\frac, \\sqrt, \\log 등)는 절대 사용하지 마세요. "
            "수식을 사람이 읽기 쉬운 평문으로 작성하세요. "
            "표기 규칙: "
            "- 분수는 a/b 형식 (예: 3/5, (a+b)/c) "
            "- 제곱근은 √ (예: √6, √(a+b)) "
            "- 로그 밑은 log_2 형식 (예: log_2 72, log_5 (x+1)) "
            "- 지수는 ^로 (예: x^2, 2^n) "
            "- 첨자는 _로 (예: a_n, x_1) "
            "- 곱셈은 × 또는 ·, 나눗셈은 ÷ "
            "- 부등호는 ≤ ≥ ≠ "
            "예시: 'a_2 = a_1 - 2', 'log_2 72 - log_2 (36/16) = log_2 (72 × 16/36)' "
            '반드시 JSON으로만 응답: {"steps": [{"index": 1, "text": "평문 수식"}]}'
        )
    else:
        instruction = (
            "당신은 수학 문제 OCR 시스템입니다. 인쇄된 문제를 적힌 그대로 정확히 읽으세요. "
            "중요: 모든 수식은 $...$ 로 감싸고, 한글은 $ 밖에 두세요. "
            '반드시 JSON으로만 응답: {"ocr_text": "...", "latex": "...", "problem_number": "...", "source": "..."}'
        )

    model = genai.GenerativeModel("gemini-2.5-pro")
    image_part = {"mime_type": mime_type, "data": base64.b64decode(image_b64)}
    response = model.generate_content(
        [instruction, "이 수학 문제/풀이를 정확히 읽어줘.", image_part],
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
    )
    return response.text


def call_judge_claude(image_b64, mime_type, res_a, res_b):
    prompt = f"""두 OCR 결과가 다릅니다. 첨부 이미지를 직접 보고 올바르게 다시 읽어주세요.
수식은 반드시 $...$ 로 감싸고, 한글은 $ 밖에 두세요.

[엔진 A - Mathpix]: {res_a}
[엔진 B - Gemini]: {res_b}

JSON으로만 응답: {{"final_text": "...", "winner": "a 또는 b 또는 rewrite"}}"""

    msg = claude_client.messages.create(
        model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
        ]}],
    )
    return msg.content[0].text


# ═══════════════════════════════════════════════════
# API 엔드포인트
# ═══════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": PROMPT_VERSION, "time": str(datetime.datetime.now())})


@app.route("/api/ocr", methods=["POST"])
def ocr_endpoint():
    try:
        data = request.get_json()
        image_b64 = data["image"]
        mime_type = data.get("mime_type", "image/jpeg")
        mode = data.get("mode", "problem")

        print(f"\n[OCR] mode={mode}, size={len(image_b64)//1024}KB")

        mathpix_result = call_mathpix(image_b64, mime_type)
        gemini_raw = call_gemini_ocr(image_b64, mime_type, mode)
        gemini_json = parse_json_loose(gemini_raw)

        gemini_text = gemini_json.get("ocr_text", "")
        is_match = mathpix_result.replace(" ", "") == gemini_text.replace(" ", "")
        judge_result = None

        if not is_match and mathpix_result and gemini_text and mode == "problem":
            try:
                judge_result = parse_json_loose(
                    call_judge_claude(image_b64, mime_type, mathpix_result, gemini_text)
                )
                judged = judge_result.get("final_text", "")
                final_text = judged if '$' in judged else (gemini_text or mathpix_result)
            except Exception:
                final_text = gemini_text or mathpix_result
        else:
            final_text = gemini_text or mathpix_result

        result = {
            "success": True, "mode": mode,
            "mathpix_result": mathpix_result,
            "gpt4o_result": gemini_json,
            "is_match": is_match,
            "judge_result": judge_result,
            "final_text": final_text,
        }
        if mode == "solution" and "steps" in gemini_json:
            result["steps"] = gemini_json["steps"]

        return jsonify(result)

    except Exception as e:
        print(f"[OCR error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/grade", methods=["POST"])
def grade_endpoint():
    try:
        data = request.get_json()
        problem_text = data.get("problem_text", "")
        solution_steps = data.get("solution_steps", [])
        problem_latex = data.get("problem_latex", "")
        correct_answer = data.get("correct_answer", "")

        clean_problem = problem_latex or problem_text
        clean_steps = "\n".join([f"Step {s['index']}: {s['text']}" for s in solution_steps])

        prompt = build_grading_prompt(clean_problem, clean_steps, correct_answer)

        msg = claude_client.messages.create(
            model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
            system=GRADING_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result = parse_json_loose(msg.content[0].text)

        # 증거 검증 + 모순 점검
        result = validate_evidence(result, clean_steps)
        result = check_contradictions(result)

        # difficulty 키가 혹시 있으면 제거
        result.pop("difficulty", None)

        result["success"] = True
        result["prompt_version"] = PROMPT_VERSION
        return jsonify(result)

    except Exception as e:
        print(f"[Grade error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/solution", methods=["POST"])
def solution_endpoint():
    try:
        data = request.get_json()
        problem_text = data.get("problem_text", "")
        problem_latex = data.get("problem_latex", "")
        the_problem = problem_latex or problem_text

        # 1) 정답: 클라이언트에서 받거나 Claude로 계산
        correct_answer = data.get("correct_answer", "")
        if not correct_answer:
            try:
                ans_msg = claude_client.messages.create(
                    model="claude-opus-4-6", max_tokens=2048, temperature=0.0,
                    system="당신은 고1 순열·조합 문제를 정확히 풀어내는 수학 교사입니다. 합의 법칙·곱의 법칙·순열·조합·계승 등 교과서 교집합 범위의 개념만 사용합니다. 답을 반드시 검산하며, 절대 추측하지 않습니다.",
                    messages=[{"role": "user", "content": f"""다음 수학 문제를 풀어 최종 정답만 정확히 구하세요.

[문제]
{the_problem}

[지시 - 매우 중요]
1. 문제를 차근차근 단계별로 풀이하세요.
2. 각 계산을 검증하며 진행하세요.
3. 최종 답을 다른 접근법으로 한 번 더 검산하세요.
4. 답의 형태(자연수/분수/소수/기호 등)를 명확히 하세요.
5. 어떤 경우에도 답을 추측하지 말고, 수학적으로 정확히 도출하세요.

JSON으로만 응답:
{{
    "answer": "최종 답 (간단한 텍스트, $ 없이. 예: 5, 65, 3/5)",
    "verification": "답이 맞다는 검증 한 줄"
}}"""}],
                )
                ans_data = parse_json_loose(ans_msg.content[0].text)
                correct_answer = str(ans_data.get("answer", "")).strip()
            except Exception:
                pass

        # 2) GPT-4o 풀이 작성
        gpt_resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "고1 순열·조합 단원의 정확한 풀이 생성기. 6종 교과서 교집합 범위의 개념만 사용하여, 주어진 정답으로 정확히 수렴하는 풀이를 만듭니다."},
                {"role": "user", "content": build_solution_prompt(the_problem, correct_answer)},
            ],
            response_format={"type": "json_object"},
            max_tokens=4096, temperature=0.1,
        )
        gpt_result = json.loads(gpt_resp.choices[0].message.content)
        if correct_answer and str(gpt_result.get("answer", "")).strip() != correct_answer:
            gpt_result["answer"] = correct_answer

        # 3) Claude 검증
        result = gpt_result
        try:
            verify_msg = claude_client.messages.create(
                model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
                system="고1 순열·조합 단원 교육 콘텐츠 검수 전문가. 수학적 정확성과 교육과정 범위 준수를 최우선으로 검증합니다. 이항정리·포함배제 등 고2 이상 개념이 포함되어 있으면 교집합 범위 내 표현으로 수정합니다. JSON 외 어떤 텍스트도 출력하지 않습니다.",
                messages=[{"role": "user", "content": f"""아래는 수학 문제와 풀이입니다. 정확성과 표현을 다듬어 정리하세요.

[문제]
{the_problem}

[필수 정답 - 반드시 이 답으로 끝나야 함]
{correct_answer or gpt_result.get("answer", "")}

[검토할 풀이 (JSON)]
{json.dumps(gpt_result, ensure_ascii=False)}

[정리 규칙]
1. 풀이의 최종 답이 "필수 정답"과 다르면, 풀이 자체를 수정해서 정답에 맞추세요.
2. 각 단계가 논리적으로 이어지는지 검증하세요. 비약·오류가 있으면 고치세요.
3. 수식은 $...$ 로 감싸고, 한글 설명은 $ 밖에 두세요.
4. answer는 $ 없이 간단한 텍스트로.
5. 원본과 동일한 JSON 구조로만 응답 (method_type, concept_tags, answer, steps).
6. 분량 제약: title 10자 이내, content 1~2문장, formula 한 줄.
7. 단계 수는 2~5단계. 잘게 쪼개진 단계는 합치세요.
8. 한 가지 풀이만 보여주세요. 여러 풀이법을 나열하지 마세요.

JSON 외 다른 텍스트는 절대 포함하지 마세요. JSON으로만 응답하세요."""}],
            )
            polished = parse_json_loose(verify_msg.content[0].text)
            if correct_answer and str(polished.get("answer", "")).strip() != correct_answer:
                polished["answer"] = correct_answer
            result = polished
        except Exception:
            pass

        # difficulty 키가 혹시 있으면 제거
        result.pop("difficulty", None)

        result["success"] = True
        result["full_solution"] = ""
        return jsonify(result)

    except Exception as e:
        print(f"[Solution error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 임시 문제 시드 ─────────────────────────────
TEMP_PROBLEMS = [
    # P세트
    {"set": "P", "num": 1, "order": 1, "text": "서로 다른 5개의 공에서 3개를 택하는 조합의 수를 구하시오.", "answer": "10"},
    {"set": "P", "num": 2, "order": 2, "text": "1, 2, 3, 4, 5의 숫자가 하나씩 적힌 5장의 카드 중에서 3장을 택하여 일렬로 나열하여 세 자리 자연수를 만들 때, 만들 수 있는 자연수의 개수를 구하시오.", "answer": "60"},
    {"set": "P", "num": 3, "order": 3, "text": "남학생 3명과 여학생 2명이 일렬로 서는 경우의 수를 구하시오.", "answer": "120"},
    {"set": "P", "num": 4, "order": 4, "text": "어느 동아리에서 회장 1명과 부회장 1명을 뽑으려고 한다. 후보가 6명일 때, 회장과 부회장을 뽑는 경우의 수를 구하시오.", "answer": "30"},
    # Q세트
    {"set": "Q", "num": 1, "order": 1, "text": "서로 다른 6개의 구슬 중 2개를 택하는 조합의 수를 구하시오.", "answer": "15"},
    {"set": "Q", "num": 2, "order": 2, "text": "0, 1, 2, 3, 4의 숫자가 하나씩 적힌 5장의 카드 중에서 3장을 택하여 일렬로 나열하여 세 자리 자연수를 만들 때, 만들 수 있는 자연수의 개수를 구하시오.", "answer": "48"},
    {"set": "Q", "num": 3, "order": 3, "text": "남학생 4명과 여학생 3명 중에서 대표 3명을 뽑는 경우의 수를 구하시오.", "answer": "35"},
    {"set": "Q", "num": 4, "order": 4, "text": "8명의 학생 중에서 반장 1명, 부반장 1명, 서기 1명을 뽑는 경우의 수를 구하시오.", "answer": "336"},
]

@app.route("/api/seed", methods=["POST"])
def seed_problems():
    """임시 문제 시드 — Supabase에 테스트용 문제를 삽입"""
    try:
        from supabase import create_client
        sb_url = os.environ.get("SUPABASE_URL", "")
        sb_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if not sb_url or not sb_key:
            return jsonify({"success": False, "error": "SUPABASE_URL / SUPABASE_KEY 환경변수 필요"}), 400

        sb = create_client(sb_url, sb_key)

        # 기존 임시 데이터 삭제
        sb.table("field_problem").delete().eq("source", "임시").execute()

        # 삽입
        rows = [{
            "problem_set": p["set"],
            "problem_number": p["num"],
            "problem_order": p["order"],
            "problem_text": p["text"],
            "answer": p["answer"],
            "source": "임시",
        } for p in TEMP_PROBLEMS]

        sb.table("field_problem").insert(rows).execute()

        return jsonify({"success": True, "count": len(rows)})
    except Exception as e:
        print(f"[Seed error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Static 서빙 ─────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
