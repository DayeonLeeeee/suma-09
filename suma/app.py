"""
suma server — Railway 배포용 (고1 순열·조합 특화)
OCR: Gemini 2.5 Flash
채점: Claude Opus (증거 기반 감점형, Batanero 15유형 오류분류)
"""

import os, json, base64, re, datetime, traceback, uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
import anthropic
import google.generativeai as genai

# ─── 환경변수 ──────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)


# ═══════════════════════════════════════════════════
# 프롬프트 모듈
# ═══════════════════════════════════════════════════

PROMPT_VERSION = "v3.2-demo30-2026-11-03"

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


def build_grading_prompt(problem_text, clean_steps, correct_answer, reference_solution=""):
    answer_info = f"\n[이 문제의 정답]\n{correct_answer}\n" if correct_answer else ""
    reference_info = (
        f"\n[참고 풀이 — 채점 기준으로만 사용, 학생에게 그대로 노출 금지]\n{reference_solution}\n"
        "학생이 다른 방법으로 풀었더라도 논리가 타당하면 맞게 채점하세요.\n"
    ) if reference_solution else ""

    return f"""[문제]
{problem_text}
{answer_info}{reference_info}
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
6. "wrong"은 반드시 하나만: 최초 오류 단계 딱 하나만 "wrong". 그 이후 단계는 모두 "depends". 절대로 "wrong"을 2개 이상 주지 마세요.
7. 경우 누락도 오류입니다: 학생이 나열해야 할 경우(분할, 케이스)를 하나라도 빠뜨렸으면 그 단계는 "wrong"이고 오류유형은 B01입니다. "나열한 것은 맞지만 빠뜨린 게 있다"도 wrong입니다. 빠뜨린 경우가 있다는 사실만 지적하고, 빠뜨린 경우가 구체적으로 무엇인지(어떤 분할인지, 어떤 숫자인지)는 알려주지 마세요.

[정답 노출 절대 금지 — 최우선 규칙]
- ai_explanation, explanation, hint_direction, hint_concept 어디에서든 올바른 값·정답·정답에 가까운 수치를 절대로 말하지 마세요.
- "올바른 값은 20이다", "C(6,3) = 20이므로", "정답은 310이다" 같은 표현은 절대 금지.
- 올바른 공식을 직접 보여주는 것도 금지: "C(6,3) = 6!/(3!×3!)" 처럼 올바른 전개를 쓰면 학생이 답을 알게 됩니다.
- 올바른 분모·분자·계산식을 구체적으로 쓰지 마세요. "나누어야 하는 값은 3이 아닙니다"까지만 하고, 실제로 무엇으로 나눠야 하는지는 쓰지 마세요.
- 틀린 부분이 어디인지, 어떤 종류의 실수인지만 지적하세요.
- 예시 OK: "이 단계에서 나눗셈이 빠져 있습니다", "조합 공식의 분모를 다시 확인하세요", "나열한 경우 중 빠진 것이 있습니다"
- 예시 NG: "C(6,3) = 6!/(3!×3!)", "분모는 3!이어야 합니다", "올바른 계산은 20 × 5 = 100", "(6,0,0,0) 경우가 빠져 있습니다"
- hint_near_answer(3단계)만 예외: 거의 답까지 보여주되, 최종 답 숫자 자체는 여전히 말하지 마세요.

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
            "text": "읽기 쉬운 수학 표현 (학생이 쓴 내용 그대로 옮기기)",
            "status": "ok|wrong|depends",
            "explanation": "이 단계 설명 — 무엇이 잘못되었는지만 지적. 올바른 값·정답·정답에 가까운 수치를 절대 포함하지 마세요.",
            "evidence": "학생 풀이에서 직접 인용한 원문 (ok인 경우 생략 가능)"
        }}
    ],
    "error_category": null 또는 "B01"~"B15" 중 하나,
    "error_detail": "간단한 오류 설명",
    "ai_explanation": "학생에게 보여줄 격려/안내 한 줄 — 어디를 다시 살펴보라는 방향만. 올바른 값·공식 결과·정답을 절대 포함하지 마세요.",
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
# 시연 문제 전용 모듈 (30번 · 7자리 문자열 · aaa)
#   화면(static/js/demo.js)의 해설과 같은 흐름을 채점 기준으로 쓴다
# ═══════════════════════════════════════════════════

DEMO_KEY = "DEMO-30"
DEMO_ANSWER = "188"   # 3^7개 문자열 전수 계산으로 검증

# 학생에게 노출 금지 수치 (학생이 직접 쓴 숫자는 예외)
DEMO_FORBIDDEN_VALUES = ["188"]                                          # 모든 필드 금지
DEMO_CASE_VALUES = ["44", "88", "100", "12", "22", "10", "32", "36"]     # hint_near_answer에서만 허용


def _norm(t: str) -> str:
    """OCR·LaTeX 표기 차이 정리: 공백·$·LaTeX 명령/괄호 제거, 소문자화."""
    t = t or ""
    t = re.sub(r"\\(?:text|mathrm|mathit|textit|operatorname)\s*", "", t)
    t = re.sub(r"[\s$\\{}()（）'\"“”‘’]", "", t)
    return t.lower()


# 문제 문장이 조금씩 달라도 잡히도록 '단서 일부만 맞아도' 판별
DEMO_CLUES = [
    "7자리", "문자열", "연달아", "뿐이다", "4개이상", "5개이하", "중복을허락",
    "baaacca", "ccbbaaa", "aabbcca", "aaabccc", "ccbaaaa",
]
DEMO_CLUE_THRESHOLD = 4


def is_demo_problem(problem_text: str, problem_key: str = "") -> bool:
    """시연 문제 판별: problem_key가 오거나, 문제 문장 단서가 4개 이상 맞으면."""
    if problem_key == DEMO_KEY:
        return True
    t = _norm(problem_text)
    return sum(1 for c in DEMO_CLUES if c in t) >= DEMO_CLUE_THRESHOLD


# 받은 고정 풀이 (화면 해설과 같은 내용) — 채점·힌트·'내 풀이와 비교'의 기준
DEMO_REFERENCE_SOLUTION = """aaa 블록의 위치로 경우를 나눈다. aaa 바로 옆에는 b 또는 c가 와야 한다.
1. aaa가 양 끝 (aaa____ 또는 ____aaa, 대칭)
  a가 5개: 2 × 3C2 × 2 = 12
  a가 4개: 2 × (3C1 × 2 × 2 − 1) = 22  (aaabbba처럼 bbb가 생기는 경우 제외)
  a가 3개: 2^4 − 2 × 3 = 10  (bbb, ccc가 생기는 경우 제외)
  44 × 2 = 88
2. aaa가 가운데
  _aaa___: 2 × 2 × (3^2 − 1) = 32
  __aaa__: 2 × 2 × 3 × 3 = 36
  ___aaa_: 32 (대칭)
  합 100
답: 88 + 100 = 188"""

DEMO_GRADING_BLOCK = """[이 문제 전용 채점 지침 — 시연 문제]

[조건 해석 — 채점 기준]
- 문자는 a, b, c. 같은 문자를 여러 번 써도 되지만 각 문자는 5개 이하. 모두 7개로 7자리 문자열.
- (가) 정확히 3개가 연달아 이어진 묶음이 있어야 하고, 그런 묶음을 이루는 문자는 a뿐이다.
  → b나 c가 3개 연속되는 문자열은 제외.
- (나) 어떤 문자도 4개 이상 연속되면 안 된다. → aaa 바로 옆 칸에는 a가 올 수 없다(b 또는 c).
- a가 5개 이하이므로 aaa 묶음은 정확히 하나만 생긴다 (aaa?aaa는 a가 6개).

[기준 풀이 — 받은 고정 풀이. 채점 전용, 학생에게 그대로 노출 금지. 학생이 나중에 보는 해설과 같은 내용]
판정·오답유형·힌트·solution_note는 모두 이 풀이를 기준으로 작성하세요.
(양 끝의 a 개수 경우는 나머지 세 자리에 들어가는 a의 개수로 나눈 것이며, a가 6개가 되는 aaa?aaa는 처음부터 제외된다.)
@@REFERENCE@@

[다른 풀이 허용]
- 위치를 다섯 가지(1~3, 2~4, 3~5, 4~6, 5~7번째)로 바로 나누고, 양 끝에서 나머지 세 자리 27가지 중
  조건에 맞지 않는 5가지를 빼는 풀이(2 × 22 = 44)도 맞는 풀이다.
- 위치 순서·이름·묶는 방식이 달라도, 경우를 빠짐없이 겹치지 않게 나누고 각 경우를 바르게 세면 "ok".
- "전체에서 조건에 맞지 않는 것을 뺀다"(경우의 수 빼기)는 허용. 단, 합집합 공식 형태의 포함배제 원리를 명시적으로 쓰면 B15.
- 3×3×3, 2^4를 곱의 법칙으로 세는 것은 허용. 중복순열 기호(₃Π₃ 등)를 쓰면 B15.
- 양 끝/가운데 경우를 "대칭이므로 같다"고 쓰는 것은 허용.

[이 문제에서 자주 나오는 오답 → 오답유형 판별표]
학생 풀이에서 처음 틀린 줄의 오류가 아래 중 무엇인지 고르세요. 표에 없으면 15유형 정의로 판단.
| 학생 풀이의 모습 | 유형 |
| aaa의 위치 경우를 일부만 나눔 (예: 양 끝만, 가운데 일부 빠짐) | B01 |
| 양 끝 경우에서 a 개수(5·4·3개) 경우 중 일부를 빠뜨림 | B01 |
| 경우를 나눴지만 범위가 서로 겹치거나 경계가 빠짐 | B09 |
| aaa 바로 옆 칸에 a를 허용함 (4연속이 생김) | B04 |
| b·c가 3개 연속되는 문자열을 빼지 않음 ((가)의 'a뿐' 무시) | B08 |
| a가 6개가 되는 문자열(aaa?aaa)을 빼지 않음 (5개 이하 조건 무시) | B08 |
| aaa를 한 덩어리로 놓고 나머지 4자리를 자유롭게 채워, 같은 문자열을 여러 번 셈 | B05 |
| 경우별 결과를 곱해서 합침, 또는 한 경우 안에서 곱할 것을 더함 | B03 |
| 3C2, 3C1 같은 조합 계산 자체를 잘못 씀 | B06 |
| 개념·경우 나누기는 맞는데 사칙연산에서 실수 | B13 |
| 경우의 수가 근거 없이 갑자기 나옴 | B12 |
| aaa를 문자열 전체에서 a를 3개 고르는 조합으로 세는 등, 연속 조건을 다른 구조로 바꿈 | B14 |

[처음 틀린 줄 판정 규칙 — 이 문제]
- 경우를 일부만 나눈 경우(B01): 경우 나누기를 선언한 줄이 "wrong". 선언 없이 바로 계산했다면 합하는 줄이 "wrong".
- 한 경우 안에서의 오류(B04, B08, B13 등): 그 경우를 계산한 줄 중 오류가 처음 나타난 줄이 "wrong".
- 앞 경우가 틀리고 뒤 경우는 맞게 계산했더라도, 뒤 줄은 모두 "depends".

[이 문제 전용 힌트 사다리 — 유형별]
아래 사다리의 구조와 정보량을 따르세요. 문장은 학생 풀이에 맞게 다듬되 정보량을 늘리지 마세요.
3단계 힌트는 위 기준 풀이(학생이 나중에 볼 해설)의 흐름과 용어(양 끝 / 가운데, a의 개수)를 따르세요.
B01 (경우 누락)
  1단계: "aaa가 놓일 수 있는 자리를 다시 세어 보세요." (양 끝 안에서 빠뜨렸다면 "a의 개수로 나눈 경우를 다시 세어 보세요.")
  2단계: 빠짐없이 경우를 나눠야 한다는 점(aaa 위치를 한 칸씩 옮기기, 또는 a의 개수를 하나씩 바꾸기).
  3단계: aaa가 양 끝인 경우와 가운데인 경우(세 가지)로 나누고, 양 끝은 a가 5·4·3개인 경우로 나눈다는 점까지.
B04 (옆 칸 a 허용)
  1단계: "aaa 바로 옆 칸에 올 수 있는 문자를 확인하세요."
  2단계: 옆 칸에 a가 오면 a가 4개 연속되어 (나)에 어긋나므로, 옆 칸을 고정 조건으로 먼저 처리해야 한다는 점.
  3단계: 옆 칸은 b, c 두 가지뿐이고, 해당 경우의 칸별 가짓수를 구체적으로 제시.
B08 ('a뿐' 무시)
  1단계: "(가)의 'a뿐이다'를 다시 읽어 보세요."
  2단계: b나 c가 3개 연속되는 문자열도 조건에 맞지 않으므로 빼야 한다는 점.
  3단계: 학생이 계산한 경우에서 빼야 할 문자열의 모양(예: aaabbba의 bbb, 끝 네 자리가 bbb나 ccc를 포함)을 제시.
B08 (5개 이하 무시)
  1단계: "문제 첫 문장의 개수 조건을 다시 보세요."
  2단계: 각 문자는 5개 이하이므로 a가 6개가 되는 문자열은 빼야 한다는 점.
  3단계: aaa가 양 끝에 있을 때 반대편 세 자리가 다시 aaa이면 a가 6개가 된다는 점.
B05 (덩어리 중복)
  1단계: "같은 문자열을 두 번 센 곳이 없는지 확인하세요."
  2단계: aaa를 한 덩어리로 두고 나머지를 자유롭게 채우면 덩어리 옆에 a가 붙은 문자열이 다른 경우와 겹친다는 점, 위치로 나누고 옆 칸을 제한해야 한다는 점.
  3단계: 양 끝·가운데로 위치를 나누고, 각 위치에서 옆 칸이 b, c뿐이라는 점.
B03 (합·곱 혼동)
  1단계: "경우별 결과를 합칠 때 쓴 연산을 확인하세요."
  2단계: aaa의 위치(또는 a의 개수)가 다른 경우는 동시에 일어나지 않으므로 합의 법칙을 쓴다는 점.
  3단계: 경우별로 구한 값을 모두 더하면 된다는 점 (합 결과는 쓰지 않음).
B06·B13 (공식·계산 실수)
  1단계: "이 줄의 계산을 다시 해 보세요."
  2단계: 어느 계산(조합 값, 뺄셈, 곱셈)을 검산해야 하는지.
  3단계: 그 줄의 올바른 중간 계산식을 제시하되 최종 답은 쓰지 않음.

[이 문제 전용 노출 금지]
- 최종 답 188은 어떤 필드에도 절대 쓰지 마세요. hint_near_answer도 마찬가지입니다.
- 기준 풀이의 경우별 수치(12, 22, 10, 44, 88, 32, 36, 100)는 hint_near_answer에서만 쓸 수 있고,
  explanation·ai_explanation·hint_direction·hint_concept·error_detail에는 쓰지 마세요.
  단, 학생이 풀이에 직접 쓴 숫자를 인용하는 것은 괜찮습니다.
- 학생이 빠뜨린 경우가 구체적으로 무엇인지는 hint_near_answer 전까지 말하지 마세요.

[추가 출력 — 해설 화면 연결]
학생은 채점 뒤 '해설 보기'를 누르면 위 기준 풀이와 같은 해설을 봅니다. 해설 화면을 학생 풀이에 맞추기 위해
JSON에 아래 두 키를 함께 넣으세요.
- "solution_focus": 학생의 처음 틀린 줄(또는 빠뜨린 경우)과 이어지는 해설 구간 id 목록 (1~3개).
  구간 id: "split"(경우 나누기·aaa 옆 칸 조건), "end5", "end4", "end3"(양 끝, a가 5·4·3개),
  "end_sum"(양 끝 합), "mid1"(_aaa___), "mid2"(__aaa__), "mid3"(___aaa_), "mid_sum"(가운데 합), "total"(최종 합).
  학생이 다른 방법(위치 다섯 가지 등)으로 풀었으면 같은 내용을 다루는 구간으로 연결하세요.
  정답이면 빈 목록 [].
- "solution_note": 해설 화면 맨 위에 보일 1~2문장. 학생 풀이의 처음 틀린 줄과 해설의 해당 구간을 비교해
  무엇이 달랐는지 말하세요(예: "내 풀이는 양 끝 경우에서 a가 6개 되는 문자열을 빼지 않았어요. 해설 ③을 보세요.").
  이 문장은 해설과 함께 보이므로 해설의 수치를 써도 됩니다. 정답이면 학생 풀이 방식과 해설 방식을 한 문장으로 비교하세요.
""".replace("@@REFERENCE@@", DEMO_REFERENCE_SOLUTION)

DEMO_SOLUTION_SECTIONS = {"split", "end5", "end4", "end3", "end_sum", "mid1", "mid2", "mid3", "mid_sum", "total"}


def clean_solution_focus(result):
    """해설 강조 구간 id를 정리 (알 수 없는 id 제거, 정답이면 비움)."""
    focus = result.get("solution_focus") or []
    if isinstance(focus, str):
        focus = [focus]
    focus = [f for f in focus if isinstance(f, str) and f in DEMO_SOLUTION_SECTIONS]
    result["solution_focus"] = [] if result.get("is_correct") else list(dict.fromkeys(focus))[:3]
    if not isinstance(result.get("solution_note"), str):
        result["solution_note"] = ""
    return result


def build_demo_grading_prompt(problem_text, clean_steps):
    """시연 문제 전용 채점 프롬프트: 공통 프롬프트 + 전용 지침 (참고 풀이는 지침 안에 포함)."""
    base = build_grading_prompt(problem_text, clean_steps, DEMO_ANSWER)
    marker = "\n[채점 원칙 — 매우 중요]"
    return base.replace(marker, "\n" + DEMO_GRADING_BLOCK + marker, 1)


def _has_num(text, v):
    return isinstance(text, str) and re.search(rf"(?<!\d){v}(?!\d)", text) is not None


def _demo_leak_targets(result, student_text):
    """(필드 위치, 금지값 목록). 학생이 직접 쓴 숫자는 노출이 아니므로 제외."""
    def not_written(values):
        return [v for v in values if not _has_num(student_text, v)]
    strict = not_written(DEMO_FORBIDDEN_VALUES + DEMO_CASE_VALUES)
    final_only = not_written(DEMO_FORBIDDEN_VALUES)
    targets = [(("top", k), strict) for k in ("ai_explanation", "hint_direction", "hint_concept", "error_detail")]
    targets.append((("top", "hint_near_answer"), final_only))
    for i, _ in enumerate(result.get("steps", []) or []):
        targets.append((("step", i), strict))
    return targets


def _leak_get(result, where):
    kind, k = where
    return result.get(k) if kind == "top" else result["steps"][k].get("explanation")


def _leak_set(result, where, value):
    kind, k = where
    if kind == "top":
        result[k] = value
    else:
        result["steps"][k]["explanation"] = value


def find_demo_leaks(result, student_text):
    leaks = []
    for where, values in _demo_leak_targets(result, student_text):
        text = _leak_get(result, where)
        for v in values:
            if _has_num(text, v):
                leaks.append(f"{where[1]}:{v}")
    return leaks


def scrub_demo_leaks(result, student_text):
    """재작성 후에도 남은 노출만 '그 값'으로 바꾼다 (마지막 안전장치)."""
    for where, values in _demo_leak_targets(result, student_text):
        text = _leak_get(result, where)
        if not isinstance(text, str):
            continue
        for v in values:
            text = re.sub(rf"(?<!\d){v}(?!\d)", "그 값", text)
        _leak_set(result, where, text)
    return result


DEMO_LEAK_RETRY = """

[재작성 지시] 직전 응답에서 학생에게 보여 주면 안 되는 수치가 노출되었습니다: {leaks}
- 최종 답은 어떤 필드에도 쓰지 마세요.
- 경우별 수치는 hint_near_answer에서만 쓸 수 있습니다.
- 학생이 직접 쓴 숫자를 인용하는 것은 괜찮습니다.
판정(is_correct, status, error_category, error_step_index)은 바꾸지 말고 문장만 고쳐 같은 JSON 형식으로 다시 출력하세요."""


# 시연 문제 해설 — 화면(demo.js) 해설과 같은 흐름, 전수 계산과 일치 확인 (LLM 호출 없음)
DEMO_SOLUTION = {
    "method_type": "aaa의 위치로 경우 나누기",
    "concept_tags": ["합의 법칙", "곱의 법칙", "경우 나누기"],
    "answer": DEMO_ANSWER,
    "steps": [
        {"step": 1, "title": "경우 나누기",
         "content": "$aaa$ 묶음의 위치로 경우를 나눕니다. $aaa$ 바로 옆에는 $b$ 또는 $c$가 와야 합니다.",
         "formula": "양 끝 / 가운데"},
        {"step": 2, "title": "양 끝",
         "content": "나머지 세 자리의 $a$ 개수로 나눕니다. $a$ 5개 $2\\times{}_3C_2\\times2=12$, 4개 $2\\times({}_3C_1\\times2\\times2-1)=22$, 3개 $2^4-2\\times3=10$.",
         "formula": "$44\\times2=88$"},
        {"step": 3, "title": "가운데",
         "content": "$\\_aaa\\_\\_\\_$는 $2\\times2\\times(3^2-1)=32$, $\\_\\_aaa\\_\\_$는 $2\\times2\\times3\\times3=36$, $\\_\\_\\_aaa\\_$는 대칭으로 $32$.",
         "formula": "$32+36+32=100$"},
        {"step": 4, "title": "합하기",
         "content": "경우들은 동시에 일어나지 않으므로 합의 법칙으로 더합니다.",
         "formula": "$88+100=188$"},
    ],
}


GRADE_FINAL_INSTRUCTION = "\n\n[최종 지시] 사고 과정을 출력하지 마세요. 오직 JSON 객체 하나만 출력하세요. 첫 글자가 반드시 '{'이어야 합니다."


def run_grader(prompt, assistant_prev=None, followup=None):
    """채점 호출 (JSON 파싱 실패 시 1회 재시도). assistant_prev/followup이 있으면 재작성 요청."""
    messages = [{"role": "user", "content": prompt + GRADE_FINAL_INSTRUCTION}]
    if assistant_prev and followup:
        messages += [{"role": "assistant", "content": assistant_prev},
                     {"role": "user", "content": followup + GRADE_FINAL_INSTRUCTION}]
    last_raw = ""
    for attempt in range(2):
        msg = claude_client.messages.create(
            model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
            system=GRADING_SYSTEM, messages=messages,
        )
        last_raw = msg.content[0].text if msg.content else ""
        print(f"[Grade] attempt={attempt+1}, stop={msg.stop_reason}, len={len(last_raw)}, first100={last_raw[:100]!r}")
        try:
            return parse_json_loose(last_raw)
        except (json.JSONDecodeError, Exception) as parse_err:
            print(f"[Grade] JSON parse fail attempt {attempt+1}: {parse_err}")
    raise ValueError(f"채점 AI 응답을 파싱할 수 없습니다. 다시 시도해주세요. (raw[:200]={last_raw[:200]!r})")


def demo_rewrite_leaks(result, prompt, clean_steps):
    """시연 문제: 노출이 있으면 판정은 그대로 두고 문장만 한 번 다시 쓰게 한 뒤, 남은 것은 가린다."""
    leaks = find_demo_leaks(result, clean_steps)
    if leaks:
        print(f"[Grade] demo leak → rewrite: {leaks}")
        try:
            retry = run_grader(prompt, assistant_prev=json.dumps(result, ensure_ascii=False),
                               followup=DEMO_LEAK_RETRY.format(leaks=", ".join(leaks)))
            for k in ("is_correct", "error_step_index", "error_category"):
                retry[k] = result.get(k)
            for k in ("solution_focus", "solution_note"):
                if not retry.get(k):
                    retry[k] = result.get(k)
            if len(retry.get("steps") or []) == len(result.get("steps") or []):
                for a, b in zip(retry["steps"], result["steps"]):
                    a["status"] = b.get("status")
                if len(find_demo_leaks(retry, clean_steps)) < len(leaks):
                    result = retry
        except Exception as e:
            print(f"[Grade] demo rewrite failed: {e}")
    result["_answer_leak"] = find_demo_leaks(result, clean_steps)
    result = scrub_demo_leaks(result, clean_steps)
    result = clean_solution_focus(result)
    result["problem_key"] = DEMO_KEY
    return result


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

def call_gemini_ocr(image_b64, mime_type, mode="problem"):
    """Gemini Flash로 OCR 수행 (단일 엔진)"""
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

    model = genai.GenerativeModel("gemini-2.5-flash")
    image_part = {"mime_type": mime_type, "data": base64.b64decode(image_b64)}
    response = model.generate_content(
        [instruction, "이 수학 문제/풀이를 정확히 읽어줘.", image_part],
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
    )
    return response.text


# ═══════════════════════════════════════════════════
# API 엔드포인트
# ═══════════════════════════════════════════════════

def _bank_by_key():
    return {f"{p['set']}-{p['num']}": p for p in TEMP_PROBLEMS}


def bank_answer(problem_key):
    """문제 은행 문항이면 저장된 정답 (없으면 빈 문자열 → 채점 AI가 직접 풀어 확인)."""
    p = _bank_by_key().get(problem_key or "")
    return (p or {}).get("answer", "") or ""


@app.route("/api/problems", methods=["GET"])
def problems_endpoint():
    """홈 화면 문제 목록. 정답은 내려보내지 않는다 (채점 때 서버가 problem_key로 찾음)."""
    level_names = {1: "기본", 2: "중간", 3: "심화"}
    items = []
    for p in sorted(TEMP_PROBLEMS, key=lambda p: (p["set"].rstrip("2"), len(p["set"]), p["num"])):
        text = p["text"]
        m = re.match(r"\[([^\]]+)\]\s*", text)
        source = m.group(1) if m else ""
        items.append({
            "key": f"{p['set']}-{p['num']}",
            "source": source,
            "text": text[m.end():] if m else text,
            "level": level_names.get(_rec_level_from_text(text), "중간"),
        })
    return jsonify({"success": True, "problems": items})


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

        gemini_raw = call_gemini_ocr(image_b64, mime_type, mode)
        gemini_json = parse_json_loose(gemini_raw)

        final_text = gemini_json.get("ocr_text", "")

        result = {
            "success": True, "mode": mode,
            "ocr_result": gemini_json,
            "final_text": final_text,
        }
        if mode == "solution" and "steps" in gemini_json:
            result["steps"] = gemini_json["steps"]

        # 문제 사진이 시연 문제(30번)로 읽히면 표시 → 화면이 정돈된 문제·전용 채점·고정 해설을 씀
        if mode == "problem":
            ocr_all = " ".join(str(gemini_json.get(k, "")) for k in ("ocr_text", "latex"))
            if is_demo_problem(ocr_all):
                result["problem_key"] = DEMO_KEY
                print("[OCR] demo problem detected")

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
        problem_key = data.get("problem_key", "")
        correct_answer = data.get("correct_answer", "") or bank_answer(problem_key)
        reference_solution = data.get("reference_solution", "")

        clean_problem = problem_latex or problem_text
        clean_steps = "\n".join([f"Step {s['index']}: {s['text']}" for s in solution_steps])

        demo = is_demo_problem(clean_problem, problem_key)
        if demo:
            # 시연 문제: 전용 지침(화면 해설과 같은 기준 풀이 포함) 사용
            prompt = build_demo_grading_prompt(clean_problem, clean_steps)
        else:
            prompt = build_grading_prompt(clean_problem, clean_steps, correct_answer, reference_solution)
        print(f"[Grade] demo={demo}")

        result = run_grader(prompt)
        if demo:
            result = demo_rewrite_leaks(result, prompt, clean_steps)

        # 증거 검증 + 모순 점검
        result = validate_evidence(result, clean_steps)
        result = check_contradictions(result)

        # difficulty 키가 혹시 있으면 제거
        result.pop("difficulty", None)

        # (선택) 오답이면 유사 문제 추천 첨부 — 요청에 "recommend": true 일 때만
        if data.get("recommend") and not result.get("is_correct") and result.get("error_category"):
            try:
                result["recommendation"] = recommend_problem(
                    error_category=result["error_category"],
                    original_key=data.get("problem_key"),
                    original_text=problem_text,
                    error_step_index=result.get("error_step_index"),
                    total_steps=len(result.get("steps") or solution_steps),
                    history=data.get("history", []),
                )
            except Exception as rec_err:
                print(f"[Grade] recommend fail: {rec_err}")

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

        # 0) 시연 문제: 검증된 고정 풀이 반환 (LLM 호출 없음)
        if is_demo_problem(the_problem, data.get("problem_key", "")):
            result = json.loads(json.dumps(DEMO_SOLUTION, ensure_ascii=False))
            result["success"] = True
            result["full_solution"] = ""
            result["problem_key"] = DEMO_KEY
            return jsonify(result)

        # 1) 정답: 클라이언트에서 받거나, 문제 은행에 있으면 그 값, 없으면 Claude로 계산
        correct_answer = data.get("correct_answer", "") or bank_answer(data.get("problem_key", ""))
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

        # 2) 풀이 작성: GPT-4o (OpenAI 키가 없거나 실패하면 Claude가 작성)
        gen_system = "고1 순열·조합 단원의 정확한 풀이 생성기. 6종 교과서 교집합 범위의 개념만 사용하여, 주어진 정답으로 정확히 수렴하는 풀이를 만듭니다."
        gpt_result = None
        if openai_client:
            try:
                gpt_resp = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": gen_system},
                        {"role": "user", "content": build_solution_prompt(the_problem, correct_answer)},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=4096, temperature=0.1,
                )
                gpt_result = json.loads(gpt_resp.choices[0].message.content)
            except Exception as gen_err:
                print(f"[Solution] GPT-4o fail → Claude: {gen_err}")
        if gpt_result is None:
            gen_msg = claude_client.messages.create(
                model="claude-opus-4-6", max_tokens=4096, temperature=0.0, system=gen_system,
                messages=[{"role": "user", "content": build_solution_prompt(the_problem, correct_answer)}],
            )
            gpt_result = parse_json_loose(gen_msg.content[0].text)
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
    # ═══ P세트 (소민·지원) ═══
    {"set": "P", "num": 1, "order": 1,
     "text": "남학생 6명과 여학생 5명이 봉사활동에 지원하였고, 지원자 11명 중에서 4명을 선발할 때, 남학생과 여학생이 적어도 한 명씩은 포함되도록 하는 경우의 수는?\n\n① 300  ② 305  ③ 310  ④ 315  ⑤ 316",
     "answer": "310"},
    {"set": "P", "num": 2, "order": 2,
     "text": "6명이 타고 있는 낚싯배가 4군데의 낚시터에 차례로 들른다. 4군데의 낚시터에 들르는 동안 6명의 낚시꾼이 모두 내리는 경우의 수는? (단, 각 낚시터에서 한 명도 내리지 않거나 두 명 이상이 내려야 한다.)\n\n① 660  ② 662  ③ 664  ④ 666  ⑤ 668",
     "answer": "664"},
    {"set": "P", "num": 3, "order": 3,
     "text": "방정식 $8^x \\times 4^y \\times 2^z = 2^{17}$을 만족시키는 세 자연수 $x, y, z$의 순서쌍 $(x, y, z)$의 개수는?\n\n① 14  ② 15  ③ 16  ④ 17  ⑤ 18",
     "answer": "16"},
    {"set": "P", "num": 4, "order": 4,
     "text": "A 반 학생 3명, B 반 학생 3명, C 반 학생 4명을 일렬로 세울 때, 양 끝에 선 두 학생의 반이 서로 다른 경우의 수는 $a \\times 8!$이다. 이때 $a$의 값을 구하시오.",
     "answer": "66"},
    {"set": "P", "num": 5, "order": 5,
     "text": "1부터 6까지의 숫자가 각각 하나씩 적힌 6개의 공이 들어 있는 주머니에서 한 개씩 두 번 공을 꺼낼 때, 꺼낸 공에 적힌 수를 차례대로 $a, b$라 하자. $a + b$와 $ab$의 값이 모두 4의 배수인 경우의 수를 구하시오. (단, 꺼낸 공은 다시 넣는다.)",
     "answer": "5"},
    # ═══ Q세트 (세인·혁민) ═══
    {"set": "Q", "num": 1, "order": 1,
     "text": "서로 다른 흰 공 4개, 서로 다른 빨간 공과 파란 공이 각각 3개씩 총 10개의 공이 들어 있는 주머니가 있다. 이 주머니에서 4개의 공을 꺼낼 때, 꺼낸 공의 색이 3종류인 경우의 수를 구하시오.",
     "answer": "126"},
    {"set": "Q", "num": 2, "order": 2,
     "text": "서로 다른 세 주머니 A, B, C가 있고, 각 주머니에 숫자 1, 2, 3, 4, 5, 6, 7이 각각 하나씩 적힌 7개의 공이 들어 있다. 세 주머니 A, B, C에서 꺼낸 공에 적힌 수를 각각 $a, b, c$라 할 때, $ab + bc + ca$의 값이 짝수가 되는 경우의 수를 구하시오.",
     "answer": "135"},
    {"set": "Q", "num": 3, "order": 3,
     "text": "서로 다른 4개 나라의 대사관에 파견되었던 4명의 대사들의 임기가 다 되어 이번엔 서로 근무지를 바꾸어 파견하고자 한다. 이전에 파견되었던 나라에 연속으로 파견되지 않도록 4명의 대사들을 각 나라에 파견하는 방법의 수는?\n\n① 9  ② 12  ③ 18  ④ 21  ⑤ 27",
     "answer": "9"},
    {"set": "Q", "num": 4, "order": 4,
     "text": "1부터 9까지의 자연수를 일렬로 나열할 때, 맨 앞에 있는 수부터 차례대로 $a_1, a_2, a_3, \\ldots, a_9$라 하자. 이때 다음 조건을 모두 만족시키도록 9개의 수를 나열하는 경우의 수를 구하시오.\n\n(가) $a_1 < a_2 < a_3 < a_4 < a_5$\n(나) $a_5 > a_6 > a_7 > a_8 > a_9$",
     "answer": "70"},
    {"set": "Q", "num": 5, "order": 5,
     "text": "A, B, C, D, E, F, G, H의 8명 중에서 4명의 대표를 선출할 때, 다음 조건을 모두 만족시키는 경우의 수를 구하시오.\n\n(가) A를 선출하면 B 또는 C를 선출해야 한다.\n(나) C를 선출하면 D와 E는 선출하지 않아야 한다.",
     "answer": "35"},
    # ═══ P2세트 — P 유사문제 ═══
    {"set": "P2", "num": 1, "order": 6,
     "text": "[블랙라벨 S2-26] 남학생 4명과 여학생 3명이 있다. 남학생을 적어도 2명 이상 포함하여 4명의 학생을 뽑은 다음 서로 다른 4개의 초콜릿을 1개씩 나누어주는 경우의 수는?\n\n① 720  ② 744  ③ 768  ④ 792  ⑤ 816",
     "answer": ""},
    {"set": "P2", "num": 2, "order": 7,
     "text": "[블랙라벨 S2-32] 남학생 6명과 여학생 2명이 있다. 8명을 2개조로 나누어 두 구역 A, B에 청소를 배정하려고 한다. 각 조에는 적어도 3명을 배정하고, 2명의 여학생은 같은 조에 포함되도록 하는 방법의 수를 구하시오.",
     "answer": ""},
    {"set": "P2", "num": 3, "order": 8,
     "text": "[블랙라벨 S1-03] 세 자연수 x, y, z에 대하여 부등식 x + 3y < 10 − 2z를 만족시키는 순서쌍 (x, y, z)의 개수는?\n\n① 3  ② 5  ③ 7  ④ 9  ⑤ 11",
     "answer": ""},
    {"set": "P2", "num": 4, "order": 9,
     "text": "[일품 17] 1부터 9까지의 9개의 숫자 중에서 서로 다른 5개를 사용하여 다섯 자리 자연수를 만들 때, 각 자리의 숫자가 홀수와 짝수가 번갈아 나오는 자연수의 개수를 구하시오.",
     "answer": ""},
    {"set": "P2", "num": 5, "order": 10,
     "text": "[일품 07] 2n 이하의 두 자연수 a, b에 대하여 a+b의 값이 짝수가 되도록 하는 a, b의 순서쌍 (a, b)의 개수가 50일 때, 자연수 n의 값은?\n\n① 4  ② 5  ③ 6  ④ 7  ⑤ 8",
     "answer": ""},
    # ═══ Q2세트 — Q 유사문제 ═══
    {"set": "Q2", "num": 1, "order": 6,
     "text": "[블랙라벨 S1-18] 두 학생이 서로 다른 7개의 동아리 중에서 각각 2개의 동아리를 선택하여 신청하려고 한다. 두 학생이 공통으로 신청하는 동아리가 1개 이하가 되도록 하는 경우의 수를 구하시오. (단, 신청 순서는 고려하지 않는다.)",
     "answer": ""},
    {"set": "Q2", "num": 2, "order": 7,
     "text": "[블랙라벨 S2-08] 1부터 10까지의 자연수가 각각 하나씩 적힌 10장의 카드가 들어 있는 주머니에서 한 장씩 카드를 두 번 꺼낼 때, 처음과 두 번째에 나온 카드에 적힌 수를 각각 a, b라 하자. 이때 a+b의 값이 3의 배수가 되는 경우의 수는? (단, 한 번 꺼낸 카드는 다시 넣지 않는다.)\n\n① 21  ② 24  ③ 27  ④ 30  ⑤ 33",
     "answer": ""},
    {"set": "Q2", "num": 3, "order": 8,
     "text": "[블랙라벨 S2-03] 다섯 개의 숫자 2, 2, 3, 4, 4가 각각 하나씩 적힌 다섯 장의 카드를 일렬로 나열할 때, k번째 자리에는 숫자 k가 적힌 카드가 나오지 않도록 나열하는 방법의 수를 구하시오. (단, k = 2, 3, 4이고, 카드의 모양과 크기는 같다.)",
     "answer": ""},
    {"set": "Q2", "num": 4, "order": 9,
     "text": "[일품 04] 4개의 숫자 1, 2, 3, 4를 모두 한 번씩 사용하여 만든 네 자리 자연수의 천의 자리의 숫자를 a, 백의 자리의 숫자를 b, 십의 자리의 숫자를 c, 일의 자리의 숫자를 d라 할 때, a<b, c<b, c<d 또는 b<a, b<c, d<c인 자연수의 개수는?\n\n① 6  ② 8  ③ 10  ④ 12  ⑤ 14",
     "answer": ""},
    {"set": "Q2", "num": 5, "order": 10,
     "text": "[일품 23] 주머니 안에 1, 2, 3, 4, 5, 6, 7의 숫자가 각각 하나씩 적힌 7개의 공이 들어 있다. 이 주머니에서 3개의 공을 동시에 꺼낼 때, 꺼낸 공에 적힌 세 수의 합이 10 이상 17 이하인 경우의 수는?\n\n① 25  ② 26  ③ 27  ④ 28  ⑤ 29",
     "answer": ""},
]

# 기존 문제의 원본 UUID 매핑 (복구용)
ORIGINAL_PROBLEM_IDS = {
    "P-1": "67e859a5-fbaf-40d1-a4e4-03b81b7d7b03",
    "P-2": "156a7d06-8b36-43ab-845d-bfbb95da5f7d",
    "P-3": "05951551-1db7-4247-afc2-fb6d649e1496",
    "P-4": "a387f861-bcd0-4350-a35c-5ca89adecbd4",
    "P-5": "56b51931-50ff-4e49-b9e2-c64961e02922",
    "Q-1": "6f4f567a-a924-4899-a4a2-131748901eb5",
    "Q-2": "0c5b02d7-ee99-422b-9eb8-9b499250d747",
    "Q-3": "ea79e7b6-7de7-4360-b350-bb38b8a7286c",
    "Q-4": "ad56dedb-5ab2-4293-b12c-461c8a4cad03",
    "Q-5": "ceb9f00d-91e3-42b5-851b-470b3b789d50",
}

@app.route("/api/seed", methods=["POST"])
def seed_problems():
    """문제 시드 — 원본 UUID 유지하여 upsert"""
    try:
        from supabase import create_client
        sb_url = os.environ.get("SUPABASE_URL", "")
        sb_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if not sb_url or not sb_key:
            return jsonify({"success": False, "error": "SUPABASE_URL / SUPABASE_KEY 환경변수 필요"}), 400

        sb = create_client(sb_url, sb_key)

        # 기존 문제 전부 삭제 후 원본 UUID로 재삽입
        sb.table("field_problem").delete().neq("problem_id", "00000000-0000-0000-0000-000000000000").execute()

        rows = []
        for p in TEMP_PROBLEMS:
            key = f"{p['set']}-{p['num']}"
            pid = ORIGINAL_PROBLEM_IDS.get(key)
            row = {
                "problem_set": p["set"],
                "problem_number": p["num"],
                "problem_order": p["order"],
                "problem_text": p["text"],
                "answer": p["answer"],
                "source": "임시",
            }
            row["problem_id"] = pid if pid else str(uuid.uuid4())
            rows.append(row)

        sb.table("field_problem").insert(rows).execute()
        inserted = len(rows)

        return jsonify({"success": True, "count": inserted})
    except Exception as e:
        print(f"[Seed error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/restore", methods=["POST"])
def restore_data():
    """백업 데이터 복구 — attempt, hint_log 재삽입"""
    try:
        from supabase import create_client
        sb_url = os.environ.get("SUPABASE_URL", "")
        sb_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if not sb_url or not sb_key:
            return jsonify({"success": False, "error": "SUPABASE_URL / SUPABASE_KEY 환경변수 필요"}), 400

        sb = create_client(sb_url, sb_key)
        data = request.get_json()
        table = data.get("table")
        rows = data.get("rows", [])

        if table not in ("field_attempt", "field_hint_log"):
            return jsonify({"success": False, "error": f"허용되지 않는 테이블: {table}"}), 400

        if not rows:
            return jsonify({"success": False, "error": "rows가 비어있습니다"}), 400

        # upsert로 중복 방지
        pk = "attempt_id" if table == "field_attempt" else "hint_log_id"
        sb.table(table).upsert(rows, on_conflict=pk).execute()

        return jsonify({"success": True, "table": table, "count": len(rows)})
    except Exception as e:
        print(f"[Restore error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════
# 유사 문제 추천 — "같은 함정, 다른 겉모습" (설계 단계, 효과 미검증)
#   ① 필터: 학생의 오답유형을 '발생 가능 유형'으로 가진 문항만, 푼 문항·사실상 같은 문항 제외
#   ② 점수: 0.4·함정위치 일치 + 0.3·난이도 적합도 + 0.3·새로움
#   ③ 선택: 최고점 1문항
# 가중치는 설계값(미튜닝). 문항 태그는 교사 검수 전 임시값.
# ═══════════════════════════════════════════════════
# >>> RECOMMENDER START

REC_WEIGHTS = {"trap": 0.4, "difficulty": 0.3, "novelty": 0.3}
REC_DUP_THRESHOLD = 0.9      # 원문제와 이 이상 유사하면 사실상 같은 문제로 보고 제외
REC_RECENT_WINDOW = 3        # 새로움 계산 시 비교할 최근 문항 수

# 문항 태그 — key는 TEMP_PROBLEMS의 "{set}-{num}"
#   error_types: 이 문항에서 발생 가능한 오답유형 (Q-matrix, Tatsuoka 1983)
#   trap: 주요 함정 위치 early(상황 모델링) / mid(경우 나누기) / late(계산)
#   ※ 아래 값은 교사 검수 전 임시 태그입니다. 실제 서비스 전 교사 라벨로 교체하세요.
PROBLEM_TAGS = {
    "P-1":  {"error_types": ["B07", "B05"],        "trap": "early"},
    "P-2":  {"error_types": ["B09", "B01"],        "trap": "mid"},
    "P-3":  {"error_types": ["B01", "B14"],        "trap": "early"},
    "P-4":  {"error_types": ["B07", "B04"],        "trap": "early"},
    "P-5":  {"error_types": ["B01", "B08"],        "trap": "mid"},
    "Q-1":  {"error_types": ["B09", "B05"],        "trap": "mid"},
    "Q-2":  {"error_types": ["B09", "B07"],        "trap": "mid"},
    "Q-3":  {"error_types": ["B01"],               "trap": "mid"},
    "Q-4":  {"error_types": ["B14", "B02"],        "trap": "early"},
    "Q-5":  {"error_types": ["B08", "B09"],        "trap": "mid"},
    "P2-1": {"error_types": ["B07", "B02", "B05"], "trap": "early"},
    "P2-2": {"error_types": ["B09", "B11", "B10"], "trap": "mid"},
    "P2-3": {"error_types": ["B01", "B08"],        "trap": "mid"},
    "P2-4": {"error_types": ["B04", "B10"],        "trap": "early"},
    "P2-5": {"error_types": ["B09", "B13"],        "trap": "late"},
    "Q2-1": {"error_types": ["B07", "B05"],        "trap": "early"},
    "Q2-2": {"error_types": ["B09", "B01"],        "trap": "mid"},
    "Q2-3": {"error_types": ["B01", "B11"],        "trap": "mid"},
    "Q2-4": {"error_types": ["B01", "B14"],        "trap": "mid"},
    "Q2-5": {"error_types": ["B07", "B01"],        "trap": "mid"},
}
TRAP_STAGES = ("early", "mid", "late")


def _rec_level_from_text(text: str) -> int:
    """출처 표기로 난이도 등급 추정: 일품=1, 블랙라벨 S1=2, S2=3, 표기 없음=2"""
    if "[일품" in text:
        return 1
    if "[블랙라벨 S1" in text:
        return 2
    if "[블랙라벨 S2" in text:
        return 3
    return 2


def _rec_clean_text(text: str) -> str:
    """유사도 계산용 정리: 출처 태그·보기(①~⑤)·LaTeX 기호 제거 → 문제 본문만 비교"""
    text = re.sub(r"\[[^\]]*\]", " ", text or "")
    text = re.split(r"[①②③④⑤]", text)[0]
    text = re.sub(r"[\$\\{}]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _rec_similarity_matrix(texts):
    """문제 본문 간 코사인 유사도. scikit-learn TF-IDF(문자 2~3-gram), 없으면 순수 파이썬으로 대체."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
        return cosine_similarity(vec.fit_transform(texts)).tolist()
    except ImportError:
        from collections import Counter
        import math
        def grams(t):
            return Counter(t[i:i + n] for n in (2, 3) for i in range(len(t) - n + 1))
        g = [grams(t) for t in texts]
        norms = [math.sqrt(sum(v * v for v in c.values())) or 1.0 for c in g]
        return [[sum(a[k] * b.get(k, 0) for k in a) / (norms[i] * norms[j])
                 for j, b in enumerate(g)] for i, a in enumerate(g)]


def build_problem_bank():
    """TEMP_PROBLEMS + PROBLEM_TAGS → 추천용 문항 은행"""
    bank = []
    for p in TEMP_PROBLEMS:
        key = f"{p['set']}-{p['num']}"
        tags = PROBLEM_TAGS.get(key)
        if not tags:
            continue
        bank.append({
            "key": key,
            "text": p["text"],
            "level": _rec_level_from_text(p["text"]),
            "error_types": tags["error_types"],
            "trap": tags["trap"],
        })
    return bank


def _rec_student_stage(error_step_index, total_steps):
    """처음 틀린 줄의 상대 위치 → early / mid / late (정보 없으면 None)"""
    try:
        idx, total = int(error_step_index), int(total_steps)
    except (TypeError, ValueError):
        return None
    if total <= 0 or idx <= 0:
        return None
    ratio = min(idx / total, 1.0)
    return "early" if ratio <= 1 / 3 else ("mid" if ratio <= 2 / 3 else "late")


def _rec_target_level(base_level, error_category, history):
    """목표 난이도: 같은 유형 2회 이상 오답 → 한 단계 아래, 직전 추천 문항 정답 → 한 단계 위"""
    repeats = 1 + sum(1 for h in history
                      if h.get("error_category") == error_category and not h.get("is_correct"))
    target = base_level - 1 if repeats >= 2 else base_level
    last_rec = next((h for h in reversed(history) if h.get("recommended")), None)
    if last_rec and last_rec.get("is_correct"):
        target += 1
    return max(1, min(3, target)), repeats


def recommend_problem(error_category, original_key=None, original_text="",
                      error_step_index=None, total_steps=None, history=None, bank=None, top_k=3):
    """
    history: [{"problem_key": "P-1", "error_category": "B07", "is_correct": false, "recommended": false}, ...]
             (오래된 것 → 최근 순)
    반환: {"recommended": {...} | None, "candidates": [...], "fallback": bool, ...}
    """
    history = history or []
    bank = bank if bank is not None else build_problem_bank()
    by_key = {b["key"]: b for b in bank}

    if original_key in by_key and not original_text:
        original_text = by_key[original_key]["text"]
    base_level = by_key[original_key]["level"] if original_key in by_key else _rec_level_from_text(original_text)

    seen = {h.get("problem_key") for h in history if h.get("problem_key")}
    if original_key:
        seen.add(original_key)

    # 유사도: [원문제, 은행 문항들]
    texts = [_rec_clean_text(original_text)] + [_rec_clean_text(b["text"]) for b in bank]
    sim = _rec_similarity_matrix(texts)
    idx_of = {b["key"]: i + 1 for i, b in enumerate(bank)}
    recent_idx = [idx_of[h["problem_key"]] for h in history[-REC_RECENT_WINDOW:]
                  if h.get("problem_key") in idx_of]

    stage = _rec_student_stage(error_step_index, total_steps)
    target, repeats = _rec_target_level(base_level, error_category, history)

    def score(b):
        i = idx_of[b["key"]]
        sim_orig = sim[0][i] if original_text else 0.0
        max_sim = max([sim_orig] + [sim[r][i] for r in recent_idx])
        trap = 1.0 if (stage and b["trap"] == stage) else 0.0
        diff = 1.0 - abs(b["level"] - target) / 2.0
        novelty = 1.0 - max_sim
        total = (REC_WEIGHTS["trap"] * trap + REC_WEIGHTS["difficulty"] * diff
                 + REC_WEIGHTS["novelty"] * novelty)
        return {"key": b["key"], "level": b["level"], "trap": b["trap"],
                "error_types": b["error_types"], "text": b["text"],
                "score": round(total, 4),
                "breakdown": {"trap_match": trap, "difficulty_fit": round(diff, 3),
                              "novelty": round(novelty, 3), "sim_to_original": round(sim_orig, 3)}}

    # ① 필터
    pool = [b for b in bank if b["key"] not in seen]
    pool = [b for b in pool
            if not (original_text and sim[0][idx_of[b["key"]]] >= REC_DUP_THRESHOLD)]
    candidates = [b for b in pool if error_category in b["error_types"]]
    fallback = not candidates
    if fallback:            # 같은 유형 문항이 소진되면 남은 문항 전체에서 고름
        candidates = pool

    # ② 점수 → ③ 선택 (동점이면 원문제와 덜 비슷한 문항, 그다음 key 순)
    scored = sorted((score(b) for b in candidates),
                    key=lambda s: (-s["score"], s["breakdown"]["sim_to_original"], s["key"]))
    return {
        "recommended": scored[0] if scored else None,
        "candidates": scored[:top_k],
        "fallback": fallback,
        "student_stage": stage,
        "target_level": target,
        "same_type_error_count": repeats,
        "weights": REC_WEIGHTS,
    }

# <<< RECOMMENDER END


@app.route("/api/recommend", methods=["POST"])
def recommend_endpoint():
    """
    요청 JSON:
      error_category (필수, "B01"~"B15"), problem_key 또는 problem_text,
      error_step_index, total_steps, history(선택)
    """
    try:
        data = request.get_json() or {}
        error_category = data.get("error_category")
        if not error_category:
            return jsonify({"success": False, "error": "error_category가 필요합니다"}), 400
        result = recommend_problem(
            error_category=error_category,
            original_key=data.get("problem_key"),
            original_text=data.get("problem_text", ""),
            error_step_index=data.get("error_step_index"),
            total_steps=data.get("total_steps"),
            history=data.get("history", []),
        )
        result["success"] = True
        return jsonify(result)
    except Exception as e:
        print(f"[Recommend error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Static 서빙 ─────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# 현장연구 때 쓰던 학생 화면 (시연 페이지와 분리)
@app.route("/field/")
def field_study():
    return send_from_directory("static/field", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
