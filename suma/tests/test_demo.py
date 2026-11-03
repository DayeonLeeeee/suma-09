"""시연 화면: 홈 → 문제 촬영(사이트 안 카메라) → Gemini Flash OCR → 확인 → 풀이 촬영 → 채점 → 힌트 → 해설"""
from conftest import (GRADE_CORRECT, OCR_PROBLEM_OTHER, album, shoot_problem, submit, to_solve,
                      upload, wait_camera_ready)


# ─── 홈 · 카메라 ─────────────────────────────────────
def test_opens_on_home_without_problem(page):
    assert page.locator("#screen-home.active").count() == 1
    home = page.inner_text("#screen-home")
    assert "문제 촬영하기" in home
    assert "baaacca" not in home            # 문제가 미리 박혀 있지 않다
    assert not page.errors


def test_shoot_button_opens_in_page_camera_with_controls(page):
    page.click("#shoot-problem-btn")
    wait_camera_ready(page)
    for sel in ["#cam-back", "#cam-shutter", "#cam-album", "#cam-flip"]:
        assert page.is_visible(sel), sel
    assert "문제를 찍어주세요" in page.inner_text("#cam-title")


def test_camera_back_button_returns_home_and_stops_camera(page):
    page.click("#shoot-problem-btn")
    wait_camera_ready(page)
    page.click("#cam-back")
    page.wait_for_selector("#screen-home.active")
    assert page.evaluate("document.getElementById('cam-video').srcObject") is None


def test_phone_back_key_closes_camera(page):
    page.click("#shoot-problem-btn")
    wait_camera_ready(page)
    page.go_back()
    page.wait_for_selector("#screen-home.active")


def test_camera_failure_offers_photo_picker(browser, base_url, api):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    pg.add_init_script("navigator.mediaDevices.getUserMedia = () => Promise.reject(Object.assign(new Error('x'), {name: 'NotAllowedError'}))")
    pg.route(f"{base_url}/api/**", api.handle_api)
    pg.goto(base_url + "/")
    pg.click("#shoot-problem-btn")
    pg.wait_for_selector("#cam-error", state="visible")
    assert "권한" in pg.inner_text("#cam-error")
    assert pg.is_visible("#cam-native-btn")
    ctx.close()


# ─── 문제 읽기 (OCR) ─────────────────────────────────
def test_shutter_sends_problem_photo_to_ocr(page, api):
    shoot_problem(page)
    body = api.calls["ocr"][0]
    assert body["mode"] == "problem"
    assert body["mime_type"] == "image/jpeg"
    assert len(body["image"]) > 100


def test_demo_problem_is_shown_tidy_with_gemini_badge(page):
    shoot_problem(page)
    text = page.inner_text("#confirm-problem")
    assert "30" in text and "(가)" in text and "(나)" in text and "baaacca" in text
    meta = page.inner_text(".ocr-meta")
    assert "Gemini Flash" in meta and "초" in meta and "순열과 조합" in meta


def test_album_on_home_also_reads_problem(page, api):
    page.click("#album-problem-btn")
    album(page)
    page.wait_for_selector("#screen-confirm.active")
    assert api.calls["ocr"][0]["mode"] == "problem"


def test_other_problem_shows_ocr_text(page, api):
    api.responses["ocr_problem"] = OCR_PROBLEM_OTHER
    shoot_problem(page)
    text = page.inner_text("#confirm-problem")
    assert "남학생 6명과 여학생 5명" in text and "$" not in text
    assert page.is_hidden("#confirm-unit")


def test_problem_ocr_failure_returns_home_with_message(page, api):
    api.responses["ocr_problem"] = {"success": False, "error": "사진에서 글씨를 찾지 못했습니다"}
    page.click("#shoot-problem-btn")
    wait_camera_ready(page)
    page.click("#cam-shutter")
    page.wait_for_selector("#screen-home.active")
    assert "사진에서 글씨를 찾지 못했습니다" in page.inner_text("#home-error")


def test_retake_from_confirm_opens_camera(page):
    shoot_problem(page)
    page.click("#confirm-retake-btn")
    wait_camera_ready(page)


# ─── 풀이 제출 · 채점 ────────────────────────────────
def test_grade_request_for_demo_problem(page, api):
    upload(page)
    submit(page)
    body = api.calls["grade"][0]
    assert body["problem_key"] == "DEMO-30"
    assert body["correct_answer"] == "188"
    assert "(가)" in body["problem_text"]
    assert body["solution_steps"] == [{"index": 1, "text": "aaa가 양 끝: 44 × 2 = 88"}, {"index": 2, "text": "답 88"}]
    assert api.calls["ocr"][1]["mode"] == "solution"


def test_grade_request_for_other_problem_has_no_demo_answer(page, api):
    api.responses["ocr_problem"] = OCR_PROBLEM_OTHER
    upload(page)
    submit(page)
    body = api.calls["grade"][0]
    assert "problem_key" not in body and "correct_answer" not in body
    assert "남학생" in body["problem_text"]


def test_solution_camera_title_and_back_to_solve(page):
    to_solve(page)
    page.click("#solution-upload-area")
    wait_camera_ready(page)
    assert "풀이를 찍어주세요" in page.inner_text("#cam-title")
    page.click("#cam-back")
    page.wait_for_selector("#screen-solve.active")


def test_solution_shutter_shows_preview(page):
    to_solve(page)
    page.click("#solution-upload-area")
    wait_camera_ready(page)
    page.click("#cam-shutter")
    page.wait_for_selector("#screen-solve.active")
    assert page.is_visible("#solution-preview")


def test_wrong_answer_stops_steps_at_first_wrong_line(page):
    upload(page)
    submit(page)
    rows = page.locator(".step-row")
    assert rows.count() == 2
    assert "틀린 줄" in rows.nth(1).inner_text()
    assert "체계적 나열 실패" in page.inner_text("#result-content")


def test_first_hint_is_open_and_later_hints_are_locked(page):
    upload(page)
    submit(page)
    assert page.inner_text("#hint-body") == "HINT-1 방향"
    assert "locked" in page.get_attribute("#hint-tab-1", "class")
    assert "locked" in page.get_attribute("#hint-tab-2", "class")


def test_hints_open_in_order(page):
    upload(page)
    submit(page)
    page.click("#hint-tab-2")
    assert "HINT-3" not in page.inner_text("#hint-body")
    page.click("#hint-tab-1")
    assert page.inner_text("#hint-body") == "HINT-2 개념"
    page.click("#hint-tab-2")
    assert page.inner_text("#hint-body") == "HINT-3 근접"
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
    page.wait_for_selector("#screen-solve.active")
    assert page.is_hidden("#solution-preview")
    upload(page)
    submit(page)
    assert "2번째" in page.inner_text(".attempt-info")


def test_back_from_result_goes_to_solve_not_processing(page):
    upload(page)
    submit(page)
    page.go_back()
    page.wait_for_selector("#screen-solve.active")


def test_ocr_failure_returns_to_solve_with_message(page, api):
    api.responses["ocr"] = {"success": False, "error": "사진에서 글씨를 찾지 못했습니다"}
    upload(page)
    page.click("#submit-btn")
    page.wait_for_selector("#screen-solve.active")
    assert "사진에서 글씨를 찾지 못했습니다" in page.inner_text("#submit-error")


def test_new_problem_button_goes_home(page):
    upload(page)
    submit(page)
    page.click("#screen-result [data-home]")
    page.wait_for_selector("#screen-home.active")


# ─── 해설 ────────────────────────────────────────────
def test_demo_solution_is_fixed_and_needs_no_api(page, api):
    upload(page)
    submit(page)
    page.click("#solution-btn")
    sol = page.inner_text("#solution-body")
    for piece in ["양 끝", "가운데", "12", "22", "10", "88", "32", "36", "100", "188"]:
        assert piece in sol, piece
    assert "solution" not in api.calls


def test_demo_solution_follows_my_solution(page):
    upload(page)
    submit(page)
    page.click("#solution-btn")
    compare = page.inner_text("#compare-card")
    assert "2번째 줄" in compare and "답 88" in compare
    assert "NOTE-가운데 경우가 빠졌어요" in compare
    focused = page.eval_on_selector_all("#solution-body .focus", "els => els.map(e => e.dataset.sec)")
    assert focused == ["mid1", "mid_sum"]


def test_correct_answer_solution_has_no_focus(page, api):
    api.responses["grade"] = GRADE_CORRECT
    upload(page)
    submit(page)
    page.click("#solution-btn")
    assert "정답이에요" in page.inner_text("#compare-card")
    assert page.locator("#solution-body .focus").count() == 0


def test_other_problem_solution_is_generated(page, api):
    api.responses["ocr_problem"] = OCR_PROBLEM_OTHER
    upload(page)
    submit(page)
    page.click("#solution-btn")
    page.wait_for_selector("#solution-body .sol-step")
    assert "310" in page.inner_text("#solution-body")
    assert "남학생" in api.calls["solution"][0]["problem_text"]


def test_solution_retry_goes_to_solve(page):
    upload(page)
    submit(page)
    page.click("#solution-btn")
    page.click("#solution-retry-btn")
    page.wait_for_selector("#screen-solve.active")
    assert page.is_hidden("#solution-preview")


# ─── 공통 ────────────────────────────────────────────
def test_never_talks_to_supabase(page, api):
    upload(page)
    submit(page)
    page.click("#hint-tab-1")
    assert api.supabase_requests == []


def test_page_allows_pinch_zoom(page):
    assert "user-scalable=no" not in page.get_attribute('meta[name="viewport"]', "content")


def test_no_script_errors_through_full_flow(page):
    upload(page)
    submit(page)
    page.click("#solution-btn")
    assert not page.errors
