"""시연 화면: 30번 문제 하나로 촬영 → 채점 → 힌트 → 해설"""
from conftest import GRADE_CORRECT, submit, upload


def test_opens_on_problem_30_without_login(page):
    assert page.locator("#screen-problem.active").count() == 1
    text = page.inner_text("#problem-display")
    assert "30" in text
    assert "(가)" in text and "(나)" in text
    assert "baaacca" in text
    assert not page.errors


def test_grade_request_carries_answer_and_reference_solution(page, api):
    upload(page)
    submit(page)
    body = api.calls["grade"][0]
    assert body["correct_answer"] == "188"
    assert "(가)" in body["problem_text"]
    assert "aaa" in body["reference_solution"] and "188" in body["reference_solution"]
    assert body["solution_steps"] == [{"index": 1, "text": "aaa가 양 끝: 44 × 2 = 88"}, {"index": 2, "text": "답 88"}]


def test_ocr_request_uses_uploaded_file_type(page, api):
    upload(page, name="note.png", mime="image/png")
    submit(page)
    assert api.calls["ocr"][0]["mime_type"] == "image/png"
    assert api.calls["ocr"][0]["mode"] == "solution"


def test_wrong_answer_stops_steps_at_first_wrong_line(page):
    upload(page)
    submit(page)
    rows = page.locator(".step-row")
    assert rows.count() == 2
    assert "틀린 줄" in rows.nth(1).inner_text()


def test_first_hint_is_open_and_later_hints_are_locked(page):
    upload(page)
    submit(page)
    assert page.inner_text("#hint-body") == "HINT-1 방향"
    assert "locked" in page.get_attribute("#hint-tab-1", "class")
    assert "locked" in page.get_attribute("#hint-tab-2", "class")


def test_second_hint_opens_after_first(page):
    upload(page)
    submit(page)
    page.click("#hint-tab-1")
    assert page.inner_text("#hint-body") == "HINT-2 개념"
    assert "locked" not in page.get_attribute("#hint-tab-1", "class")


def test_third_hint_opens_after_second(page):
    upload(page)
    submit(page)
    page.click("#hint-tab-1")
    page.click("#hint-tab-2")
    assert page.inner_text("#hint-body") == "HINT-3 근접"


def test_third_hint_cannot_skip_second(page):
    upload(page)
    submit(page)
    page.click("#hint-tab-2")
    assert "HINT-3" not in page.inner_text("#hint-body")
    assert "locked" in page.get_attribute("#hint-tab-2", "class")


def test_earlier_hint_can_be_reopened(page):
    upload(page)
    submit(page)
    page.click("#hint-tab-1")
    page.click("#hint-tab-0")
    assert page.inner_text("#hint-body") == "HINT-1 방향"


def test_correct_answer_shows_no_hints(page, api):
    api.responses["grade"] = GRADE_CORRECT
    upload(page)
    submit(page)
    assert "정답" in page.inner_text(".banner")
    assert page.locator("#hint-card").count() == 0


def test_retry_counts_attempts_and_resets_photo(page):
    upload(page)
    submit(page)
    page.click("#retry-btn")
    assert page.locator("#screen-problem.active").count() == 1
    assert page.is_hidden("#solution-preview")
    upload(page)
    submit(page)
    assert "2번째" in page.inner_text(".attempt-info")


def test_solution_follows_case_split_and_needs_no_api(page, api):
    upload(page)
    submit(page)
    page.click("#solution-btn")
    sol = page.inner_text("#screen-solution")
    for piece in ["양 끝", "가운데", "12", "22", "10", "88", "32", "36", "100", "188"]:
        assert piece in sol, piece
    assert "solution" not in api.calls


def test_ocr_failure_returns_to_problem_with_message(page, api):
    api.responses["ocr"] = {"success": False, "error": "사진에서 글씨를 찾지 못했습니다"}
    upload(page)
    page.click("#submit-btn")
    page.wait_for_selector("#screen-problem.active")
    assert "사진에서 글씨를 찾지 못했습니다" in page.inner_text("#submit-error")


def test_never_talks_to_supabase(page, api):
    upload(page)
    submit(page)
    page.click("#hint-tab-1")
    assert api.supabase_requests == []


def test_page_allows_pinch_zoom(page):
    assert "user-scalable=no" not in page.get_attribute('meta[name="viewport"]', "content")
