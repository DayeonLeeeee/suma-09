"""풀이 쓰기: 화면에 직접 쓴 풀이 → 그림으로 바꿔 OCR → 줄별 확인 → 채점"""
from conftest import to_solve


def open_draw(page):
    to_solve(page)
    page.click("#draw-btn")
    page.wait_for_selector("#screen-draw.active")
    page.wait_for_function("document.getElementById('draw-canvas').width > 0")


def scribble(page, y=150, x0=40, x1=260):
    box = page.locator("#draw-canvas").bounding_box()
    page.mouse.move(box["x"] + x0, box["y"] + y)
    page.mouse.down()
    for k in range(1, 11):
        page.mouse.move(box["x"] + x0 + (x1 - x0) * k / 10, box["y"] + y + (8 if k % 2 else -8))
    page.mouse.up()


def stroke_count(page):
    return page.evaluate("pad.strokes.length")


def test_solve_screen_offers_write_and_photo(page):
    to_solve(page)
    text = page.inner_text("#solve-choices")
    assert "풀이 쓰기" in text and "사진 찍기" in text


def test_draw_screen_has_tools(page):
    open_draw(page)
    for sel in ["#tool-pen", "#tool-eraser", "#tool-move", "#draw-undo", "#draw-clear", "#draw-done", "#draw-more"]:
        assert page.is_visible(sel), sel
    assert page.is_visible("#draw-empty")


def test_pen_draws_strokes_and_hides_placeholder(page):
    open_draw(page)
    scribble(page, 120)
    scribble(page, 190)
    assert stroke_count(page) == 2
    assert page.is_hidden("#draw-empty")


def test_undo_and_clear(page):
    open_draw(page)
    scribble(page, 120)
    scribble(page, 190)
    page.click("#draw-undo")
    assert stroke_count(page) == 1
    page.click("#draw-clear")
    assert stroke_count(page) == 0
    page.click("#draw-undo")
    assert stroke_count(page) == 1


def test_eraser_removes_touched_stroke(page):
    open_draw(page)
    scribble(page, 120)
    scribble(page, 260)
    page.click("#tool-eraser")
    scribble(page, 120, 100, 140)
    assert stroke_count(page) == 1


def test_move_tool_does_not_draw(page):
    open_draw(page)
    page.click("#tool-move")
    scribble(page, 120)
    assert stroke_count(page) == 0


def test_more_space_grows_canvas(page):
    open_draw(page)
    h0 = page.evaluate("pad.height")
    page.click("#draw-more")
    assert page.evaluate("pad.height") == h0 + 360


def test_problem_can_be_viewed_while_writing(page):
    open_draw(page)
    page.click("#draw-problem-btn")
    assert "(가)" in page.inner_text("#draw-problem")
    page.click("#draw-problem-close")
    assert page.is_hidden("#draw-problem")


def test_done_without_writing_shows_message(page, api):
    open_draw(page)
    page.click("#draw-done")
    assert "쓴 풀이가 없어요" in page.inner_text("#draw-error")
    assert len(api.calls.get("ocr", [])) == 1          # 문제 OCR 한 번만


def test_done_sends_drawing_to_ocr_and_shows_lines(page, api):
    open_draw(page)
    scribble(page, 120)
    page.click("#draw-done")
    page.wait_for_selector("#screen-check.active")
    body = api.calls["ocr"][-1]
    assert body["mode"] == "solution" and body["mime_type"] == "image/jpeg" and len(body["image"]) > 100
    assert page.locator(".line-input").count() == 2
    assert page.inner_text("#check-retake-btn") == "다시 쓰기"


def test_drawn_solution_is_graded(page, api):
    open_draw(page)
    scribble(page, 120)
    page.click("#draw-done")
    page.wait_for_selector("#screen-check.active")
    page.click("#grade-btn")
    page.wait_for_selector("#screen-result.active")
    assert api.calls["grade"][0]["solution_steps"][0]["text"] == "aaa가 양 끝: 44 × 2 = 88"


def test_rewrite_keeps_drawing(page):
    open_draw(page)
    scribble(page, 120)
    page.click("#draw-done")
    page.wait_for_selector("#screen-check.active")
    page.click("#check-retake-btn")
    page.wait_for_selector("#screen-draw.active")
    assert stroke_count(page) == 1


def test_ocr_failure_stays_on_draw(page, api):
    api.responses["ocr"] = {"success": False, "error": "글씨를 찾지 못했습니다"}
    open_draw(page)
    scribble(page, 120)
    page.click("#draw-done")
    page.wait_for_selector("#screen-draw.active")
    assert "글씨를 찾지 못했습니다" in page.inner_text("#draw-error")
    assert stroke_count(page) == 1


def test_retry_clears_drawing(page):
    open_draw(page)
    scribble(page, 120)
    page.click("#draw-done")
    page.wait_for_selector("#screen-check.active")
    page.click("#grade-btn")
    page.wait_for_selector("#screen-result.active")
    page.click("#retry-btn")
    page.wait_for_selector("#screen-solve.active")
    assert stroke_count(page) == 0
