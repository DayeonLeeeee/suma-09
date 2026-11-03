"""
SUMA 채점 자동 테스트 스크립트
— 배포된 서버에 정답/오답 풀이를 보내서 채점 결과를 확인합니다.
— 사용법: python test_grading.py [BASE_URL]
— 예: python test_grading.py https://suma-09-production.up.railway.app
— 시연 문제만: python test_grading.py https://... --demo
"""

import sys, json, requests, time

_args = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = _args[0].rstrip("/") if _args else "http://localhost:5000"
DEMO_ONLY = "--demo" in sys.argv

# ═══ 테스트 케이스: (문제 텍스트, 정답, 정답풀이 steps, 오답풀이 steps) ═══
TESTS = [
    # ──── P1 ────
    {
        "label": "P1",
        "text": "남학생 6명과 여학생 5명이 봉사활동에 지원하였고, 지원자 11명 중에서 4명을 선발할 때, 남학생과 여학생이 적어도 한 명씩은 포함되도록 하는 경우의 수는?",
        "answer": "310",
        "correct_steps": [
            {"index": 1, "text": "전체 경우의 수: C(11,4) = 330"},
            {"index": 2, "text": "남학생만: C(6,4)=15, 여학생만: C(5,4)=5, 합=20"},
            {"index": 3, "text": "330 - 20 = 310"},
        ],
        "wrong_steps": [
            {"index": 1, "text": "전체 경우의 수: C(11,4) = 330"},
            {"index": 2, "text": "남학생만: P(6,4) = 360"},
            {"index": 3, "text": "330 - 360 = -30"},
        ],
    },
    # ──── P3 ────
    {
        "label": "P3",
        "text": "방정식 8^x × 4^y × 2^z = 2^17을 만족시키는 세 자연수 x, y, z의 순서쌍 (x,y,z)의 개수는?",
        "answer": "16",
        "correct_steps": [
            {"index": 1, "text": "2^(3x) × 2^(2y) × 2^z = 2^17 이므로 3x+2y+z=17"},
            {"index": 2, "text": "x=1일 때 2y+z=14, y는 1~6 → 6가지"},
            {"index": 3, "text": "x=2일 때 2y+z=11, y는 1~5 → 5가지"},
            {"index": 4, "text": "x=3일 때 2y+z=8, y는 1~3 → 3가지"},
            {"index": 5, "text": "x=4일 때 2y+z=5, y는 1~2 → 2가지"},
            {"index": 6, "text": "총합: 6+5+3+2 = 16"},
        ],
        "wrong_steps": [
            {"index": 1, "text": "3x+2y+z=17"},
            {"index": 2, "text": "x, y, z는 자연수이므로 x는 1~5"},
            {"index": 3, "text": "각 x에 대해 2y+z=17-3x, 해의 수는 (17-3x-1)/2"},
            {"index": 4, "text": "합: 6+5+4+2+1 = 18"},
        ],
    },
    # ──── Q1 ────
    {
        "label": "Q1",
        "text": "서로 다른 흰 공 4개, 서로 다른 빨간 공과 파란 공이 각각 3개씩 총 10개의 공이 들어 있는 주머니가 있다. 이 주머니에서 4개의 공을 꺼낼 때, 꺼낸 공의 색이 3종류인 경우의 수를 구하시오.",
        "answer": "126",
        "correct_steps": [
            {"index": 1, "text": "(흰2,빨1,파1): C(4,2)×C(3,1)×C(3,1) = 6×3×3 = 54"},
            {"index": 2, "text": "(흰1,빨2,파1): C(4,1)×C(3,2)×C(3,1) = 4×3×3 = 36"},
            {"index": 3, "text": "(흰1,빨1,파2): C(4,1)×C(3,1)×C(3,2) = 4×3×3 = 36"},
            {"index": 4, "text": "총합: 54 + 36 + 36 = 126"},
        ],
        "wrong_steps": [
            {"index": 1, "text": "3색 모두 포함 → 최소 1개씩 선택: C(4,1)×C(3,1)×C(3,1) = 36"},
            {"index": 2, "text": "나머지 1개를 10-3=7개에서: C(7,1) = 7"},
            {"index": 3, "text": "36 × 7 = 252"},
        ],
    },
    # ──── Q3 ────
    {
        "label": "Q3",
        "text": "서로 다른 4개 나라의 대사관에 파견되었던 4명의 대사들의 임기가 다 되어 이번엔 서로 근무지를 바꾸어 파견하고자 한다. 이전에 파견되었던 나라에 연속으로 파견되지 않도록 4명의 대사들을 각 나라에 파견하는 방법의 수는?",
        "answer": "9",
        "correct_steps": [
            {"index": 1, "text": "완전순열(교란수) D(4) = 4!(1 - 1/1! + 1/2! - 1/3! + 1/4!)"},
            {"index": 2, "text": "= 24(1 - 1 + 1/2 - 1/6 + 1/24)"},
            {"index": 3, "text": "= 24 × 3/8 = 9"},
        ],
        "wrong_steps": [
            {"index": 1, "text": "4명을 4곳에 배치: 4! = 24"},
            {"index": 2, "text": "같은 나라에 가는 경우를 빼야 함"},
            {"index": 3, "text": "24 - 4 = 20"},
        ],
    },
]


# ═══ 시연 문제 (7자리 문자열 · aaa) ═══
DEMO_TEXT = (
    "세 문자 a, b, c 중에서 중복을 허락하여 각각 5개 이하씩 모두 7개를 택해 다음 조건을 만족시키는 "
    "7자리의 문자열을 만들려고 한다. (가) 한 문자가 연달아 3개 이어지고 그 문자는 a뿐이다. "
    "(나) 어느 한 문자도 연달아 4개 이상 이어지지 않는다. 예를 들어, baaacca, ccbbaaa는 조건을 "
    "만족시키는 문자열이고 aabbcca, aaabccc, ccbaaaa는 조건을 만족시키지 않는 문자열이다. "
    "만들 수 있는 모든 문자열의 개수를 구하시오."
)
DEMO_ANSWER = "188"

def S(*lines):
    return [{"index": i + 1, "text": t} for i, t in enumerate(lines)]

DEMO_CORRECT = S(
    "aaa가 놓이는 위치로 나눈다: 1~3, 2~4, 3~5, 4~6, 5~7번째",
    "1~3번째: 4번째는 b 또는 c → 2가지. 5~7번째 27가지 중 bba, bbb, bbc, ccc, aaa 5가지 제외 → 22. 2×22=44",
    "5~7번째: 같은 방법으로 44",
    "2~4번째: 1번째 2가지, 5번째 2가지, 6·7번째 9가지 중 5번째와 같은 문자 2개 제외 → 2×2×8=32",
    "4~6번째: 같은 방법으로 32",
    "3~5번째: 2번째 2가지, 6번째 2가지, 1·7번째 각 3가지 → 2×3×2×3=36",
    "44+44+32+32+36=188",
)

# 화면 해설과 같은 흐름의 정답 풀이 (양 끝은 a 개수로 나누기)
DEMO_CORRECT_SCREEN = S(
    "aaa 위치로 나눈다. aaa 옆은 b 또는 c",
    "aaa가 양 끝: a 5개 2×3C2×2=12, a 4개 2×(3C1×2×2-1)=22, a 3개 2^4-2×3=10 → 44, 44×2=88",
    "aaa가 가운데: _aaa___ 2×2×(3^2-1)=32, __aaa__ 2×2×3×3=36, ___aaa_ 32 → 100",
    "88+100=188",
)

# (라벨, 풀이, 허용 오답유형, 처음 틀린 줄)
DEMO_WRONG = [
    ("5개 이하 무시", S(
        "aaa가 놓이는 위치로 나눈다: 1~3, 2~4, 3~5, 4~6, 5~7번째",
        "1~3번째: 4번째는 b 또는 c → 2가지. 5~7번째 27가지 중 bba, bbb, bbc, ccc 4가지 제외 → 23. 2×23=46",
        "5~7번째: 같은 방법으로 46",
        "2~4번째: 2×2×8=32",
        "4~6번째: 32",
        "3~5번째: 2×3×2×3=36",
        "46+46+32+32+36=192",
    ), {"B08"}, 2),
    ("'a뿐' 무시", S(
        "aaa가 놓이는 위치로 나눈다: 1~3, 2~4, 3~5, 4~6, 5~7번째",
        "1~3번째: 4번째는 b 또는 c → 2가지. 5~7번째 27가지 중 a가 6개 되는 aaa와 4연속 bbb만 제외 → 25. 2×25=50",
        "5~7번째: 같은 방법으로 50",
        "2~4번째: 1번째 2가지, 5번째 2가지, 6·7번째 9가지 → 36",
        "4~6번째: 36",
        "3~5번째: 2×3×2×3=36",
        "50+50+36+36+36=208",
    ), {"B08"}, 2),
    ("옆 칸 a 허용", S(
        "aaa가 놓이는 위치로 나눈다: 1~3, 2~4, 3~5, 4~6, 5~7번째",
        "1~3번째: 2×22=44",
        "5~7번째: 44",
        "2~4번째: 2×2×8=32",
        "4~6번째: 32",
        "3~5번째: 나머지 1, 2, 6, 7번째에 a, b, c 아무거나 → 3×3×3×3=81",
        "44+44+32+32+81=233",
    ), {"B04"}, 6),
    ("위치 누락", S(
        "aaa가 놓이는 위치로 나눈다: 1~3, 3~5, 5~7번째",
        "1~3번째: 4번째는 b 또는 c → 2가지. 5~7번째 27가지 중 5가지 제외 → 22. 2×22=44",
        "5~7번째: 44",
        "3~5번째: 2×3×2×3=36",
        "44+44+36=124",
    ), {"B01", "B09"}, 1),
    ("계산 실수", S(
        "aaa가 놓이는 위치로 나눈다: 1~3, 2~4, 3~5, 4~6, 5~7번째",
        "1~3번째: 4번째는 b 또는 c → 2가지. 5~7번째 27가지 중 5가지 제외 → 27-5=21. 2×21=42",
        "5~7번째: 42",
        "2~4번째: 2×2×8=32",
        "4~6번째: 32",
        "3~5번째: 2×3×2×3=36",
        "42+42+32+32+36=184",
    ), {"B13"}, 2),
    ("덩어리 중복", S(
        "aaa를 한 묶음으로 보면 묶음의 위치는 5가지",
        "나머지 4자리는 각각 a, b, c 중 하나 → 3×3×3×3=81",
        "5×81=405",
    ), {"B05", "B04"}, 2),
]

LEAK_STRICT = ["188", "44", "88", "100", "12", "22", "10", "32", "36"]
LEAK_FIELDS = ["ai_explanation", "hint_direction", "hint_concept"]


def check_leak(data, steps):
    """정답·경우별 수치 노출 검사 (학생이 직접 쓴 숫자는 노출이 아님)"""
    import re
    found = []
    def has(text, v):
        return isinstance(text, str) and re.search(rf"(?<!\d){v}(?!\d)", text)
    student = " ".join(s["text"] for s in steps)
    strict = [v for v in LEAK_STRICT if not has(student, v)]
    for f in LEAK_FIELDS:
        for v in strict:
            if has(data.get(f), v):
                found.append(f"{f}:{v}")
    if "188" in strict and has(data.get("hint_near_answer"), "188"):
        found.append("hint_near_answer:188")
    for s in data.get("steps", []):
        for v in strict:
            if has(s.get("explanation"), v):
                found.append(f"step{s.get('index')}:{v}")
    return found


def post_grade(steps):
    payload = {"problem_text": DEMO_TEXT, "correct_answer": DEMO_ANSWER,
               "solution_steps": steps, "problem_key": "DEMO-30"}
    r = requests.post(f"{BASE}/api/grade", json=payload, timeout=180)
    return r.json()


def test_demo():
    print(f"\n{'═'*50}\n  시연 문제 테스트 (정답 2 + 오답 {len(DEMO_WRONG)} + 해설)\n{'═'*50}")
    total = passed = 0

    # 정답 풀이 (위치 다섯 가지 풀이 / 화면 해설 흐름 풀이)
    for name, sol in (("정답 풀이·위치 5가지", DEMO_CORRECT), ("정답 풀이·화면 해설 흐름", DEMO_CORRECT_SCREEN)):
        total += 1
        d = post_grade(sol)
        ok = d.get("success") and d.get("is_correct") is True
        print(f"\n  [{name}] is_correct={d.get('is_correct')}  {'✅' if ok else '❌'}")
        passed += ok
        time.sleep(2)

    # 오답 풀이
    for label, steps, cats, first in DEMO_WRONG:
        total += 1
        d = post_grade(steps)
        if not d.get("success"):
            print(f"\n  [{label}] ❌ 서버 에러: {d.get('error')}")
            continue
        wrongs = [s["index"] for s in d.get("steps", []) if s.get("status") == "wrong"]
        cat = d.get("error_category")
        leak_srv = d.get("_answer_leak", [])
        leak_now = check_leak(d, steps)
        checks = {
            "is_correct=false": d.get("is_correct") is False,
            f"유형∈{sorted(cats)}": cat in cats,
            f"처음 틀린 줄={first}": wrongs == [first],
            "노출 없음": not leak_now,
        }
        ok = all(checks.values())
        passed += ok
        print(f"\n  [{label}] {'✅' if ok else '❌'}  유형={cat}  wrong줄={wrongs}")
        for k, v in checks.items():
            if not v:
                print(f"     ✗ {k}")
        if leak_srv:
            print(f"     (재작성 후에도 남아 서버가 바꾼 노출: {leak_srv})")
        print(f"     힌트1: {d.get('hint_direction')}")
        print(f"     힌트2: {d.get('hint_concept')}")
        print(f"     힌트3: {d.get('hint_near_answer')}")
        time.sleep(2)

    # 해설
    total += 1
    s = requests.post(f"{BASE}/api/solution",
                      json={"problem_text": DEMO_TEXT, "problem_key": "DEMO-30"}, timeout=60).json()
    ok = s.get("success") and str(s.get("answer")) == DEMO_ANSWER and s.get("problem_key") == "DEMO-30"
    passed += ok
    print(f"\n  [해설] answer={s.get('answer')}  고정풀이={s.get('problem_key') == 'DEMO-30'}  {'✅' if ok else '❌'}")

    return passed, total


def test_grade(label, text, answer, steps, expect_correct):
    """채점 API를 호출하고 결과를 출력"""
    tag = "정답풀이" if expect_correct else "오답풀이"
    print(f"\n{'─'*50}")
    print(f"  {label} / {tag}")
    print(f"{'─'*50}")

    payload = {
        "problem_text": text,
        "correct_answer": answer,
        "solution_steps": steps,
    }

    try:
        r = requests.post(f"{BASE}/api/grade", json=payload, timeout=120)
        data = r.json()
    except Exception as e:
        print(f"  ❌ 요청 실패: {e}")
        return False

    if not data.get("success"):
        print(f"  ❌ 서버 에러: {data.get('error')}")
        return False

    is_correct = data.get("is_correct", False)
    score = data.get("score", "?")
    print(f"  is_correct: {is_correct}  (기대: {expect_correct})")
    print(f"  score: {score}")

    # 단계별 결과
    for step in data.get("steps", []):
        status_emoji = "✅" if step["status"] == "ok" else "❌" if step["status"] == "wrong" else "⚠️"
        print(f"    {status_emoji} Step {step['index']}: {step['status']}")
        if step.get("explanation"):
            print(f"       → {step['explanation'][:80]}")

    # 오류 유형
    errors = data.get("error_types", [])
    if errors:
        print(f"  오류유형: {errors}")

    # 힌트
    if data.get("hint_direction"):
        print(f"  힌트1(방향): {data['hint_direction'][:60]}...")

    # 판정 일치 확인
    match = is_correct == expect_correct
    if not match:
        print(f"  ⚠️  판정 불일치! 기대={expect_correct}, 실제={is_correct}")
    else:
        print(f"  ✅ 판정 일치")

    return match


def main():
    print(f"SUMA 채점 자동 테스트")
    print(f"서버: {BASE}")
    print(f"테스트 수: {len(TESTS)} 문제 × 2 (정답/오답) = {len(TESTS)*2}건")

    # 서버 확인
    try:
        r = requests.get(f"{BASE}/api/health", timeout=10)
        print(f"서버 상태: {r.json()}")
    except:
        print("⚠️  서버 연결 안됨 — 그래도 시도합니다")

    total = 0
    passed = 0

    p, t_ = test_demo()
    passed += p
    total += t_
    if DEMO_ONLY:
        print(f"\n{'═'*50}\n  결과: {passed}/{total} 통과\n{'═'*50}")
        return

    for t in TESTS:
        # 정답 풀이 테스트
        total += 1
        if test_grade(t["label"], t["text"], t["answer"], t["correct_steps"], True):
            passed += 1
        time.sleep(2)

        # 오답 풀이 테스트
        total += 1
        if test_grade(t["label"], t["text"], t["answer"], t["wrong_steps"], False):
            passed += 1
        time.sleep(2)

    print(f"\n{'═'*50}")
    print(f"  결과: {passed}/{total} 통과")
    print(f"{'═'*50}")


if __name__ == "__main__":
    main()
