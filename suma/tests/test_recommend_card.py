"""오답 결과 아래 유사 문제 추천 카드"""
from conftest import GRADE_CORRECT, submit, upload


def wait_card(page):
    page.wait_for_selector("#rec-card", timeout=5000)
    return page.inner_text("#rec-card")


def test_wrong_answer_shows_recommended_problem(page):
    upload(page)
    submit(page)
    card = wait_card(page)
    assert "주머니 안에 1, 2, 3, 4, 5, 6, 7의 숫자가" in card
    assert "일품 23" in card


def test_card_explains_why_this_problem(page):
    upload(page)
    submit(page)
    card = wait_card(page)
    for label in ["함정 위치", "난이도", "새로움"]:
        assert label in card, label
    assert "중반" in card              # student_stage
    assert "설계 단계" in card


def test_recommend_request_uses_grading_result(page, api):
    upload(page)
    submit(page)
    wait_card(page)
    body = api.calls["recommend"][0]
    assert body["error_category"] == "B01"
    assert body["error_step_index"] == 2
    assert body["total_steps"] == 3
    assert "(가)" in body["problem_text"]
    assert body["history"] == []


def test_second_wrong_submission_sends_history(page, api):
    upload(page)
    submit(page)
    wait_card(page)
    page.click("#retry-btn")
    upload(page)
    submit(page)
    wait_card(page)
    assert api.calls["recommend"][1]["history"] == [{"error_category": "B01", "is_correct": False}]


def test_correct_answer_skips_recommendation(page, api):
    api.responses["grade"] = GRADE_CORRECT
    upload(page)
    submit(page)
    page.wait_for_timeout(300)
    assert "recommend" not in api.calls
    assert page.locator("#rec-card").count() == 0


def test_recommend_failure_keeps_result_clean(page, api):
    api.status["recommend"] = 405
    api.responses["recommend"] = {"success": False, "error": "Method Not Allowed"}
    upload(page)
    submit(page)
    page.wait_for_timeout(500)
    assert page.locator("#rec-card").count() == 0
    assert "Method" not in page.inner_text("#screen-result")
    assert page.locator("#hint-card").count() == 1
