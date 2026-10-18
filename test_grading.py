"""
SUMA 채점 자동 테스트 스크립트
— 배포된 서버에 정답/오답 풀이를 보내서 채점 결과를 확인합니다.
— 사용법: python test_grading.py [BASE_URL]
— 예: python test_grading.py https://suma-09-production.up.railway.app
"""

import sys, json, requests, time

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:5000"

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
