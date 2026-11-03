"""
E2E 테스트 공통 설정
- static/ 폴더를 로컬 http 서버로 띄우고 /api/* 는 가짜 응답으로 가로챈다
- 크롬 가짜 카메라(--use-fake-device-for-media-stream)로 사이트 안 카메라·셔터까지 확인한다
- Supabase로 가는 요청은 모두 막고 기록만 남긴다 (시연 화면은 DB를 쓰지 않아야 함)
"""
import copy
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import sync_playwright

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

OCR_PROBLEM_DEMO = {"success": True, "mode": "problem", "problem_key": "DEMO-30",
                    "final_text": "30. 세 문자 $a, b, c$ 중에서 ... 7자리의 문자열 ... $a$뿐이다 ..."}
OCR_PROBLEM_OTHER = {"success": True, "mode": "problem",
                     "final_text": "남학생 $6$명과 여학생 $5$명 중에서 $4$명을 선발하는 경우의 수는?"}

GRADE_WRONG = {
    "success": True,
    "is_correct": False,
    "error_step_index": 2,
    "error_category": "B01",
    "error_detail": "aaa가 가운데 오는 경우를 빠뜨림",
    "ai_explanation": "경우를 나눈 부분을 다시 살펴보세요.",
    "steps": [
        {"index": 1, "text": "aaa가 양 끝: 44 × 2 = 88", "status": "ok"},
        {"index": 2, "text": "답 88", "status": "wrong", "explanation": "나열한 경우 중 빠진 것이 있습니다."},
        {"index": 3, "text": "끝", "status": "depends"},
    ],
    "hint_direction": "HINT-1 방향",
    "hint_concept": "HINT-2 개념",
    "hint_near_answer": "HINT-3 근접",
    "solution_focus": ["mid1", "mid_sum"],
    "solution_note": "NOTE-가운데 경우가 빠졌어요",
}

GRADE_CORRECT = {
    "success": True,
    "is_correct": True,
    "error_step_index": None,
    "error_category": None,
    "steps": [{"index": 1, "text": "88 + 100 = 188", "status": "ok"}],
    "solution_focus": [],
    "solution_note": "NOTE-해설과 같은 흐름",
}

RECOMMEND_OK = {
    "success": True,
    "recommended": {
        "key": "Q2-5",
        "score": 0.8123,
        "level": 1,
        "trap": "mid",
        "error_types": ["B07", "B01"],
        "text": "[일품 23] 주머니 안에 1, 2, 3, 4, 5, 6, 7의 숫자가 각각 하나씩 적힌 7개의 공이 들어 있다.\n\n① 25  ② 26",
        "breakdown": {"trap_match": 1.0, "difficulty_fit": 0.5, "novelty": 0.874, "sim_to_original": 0.126},
    },
    "candidates": [],
    "fallback": False,
    "student_stage": "mid",
    "target_level": 2,
    "same_type_error_count": 1,
}

SOLUTION_GENERATED = {
    "success": True, "answer": "310", "concept_tags": ["여사건"],
    "steps": [{"step": 1, "title": "전체", "content": "$_{11}C_4$", "formula": "$330$"}],
}


class FakeApi:
    def __init__(self):
        self.calls = {}        # endpoint -> [body, ...]
        self.responses = {
            "ocr_problem": copy.deepcopy(OCR_PROBLEM_DEMO),
            "ocr": {"success": True, "steps": [{"index": 1, "text": "aaa가 양 끝: 44 × 2 = 88"}, {"index": 2, "text": "답 88"}]},
            "grade": copy.deepcopy(GRADE_WRONG),
            "recommend": copy.deepcopy(RECOMMEND_OK),
            "solution": copy.deepcopy(SOLUTION_GENERATED),
        }
        self.status = {}
        self.supabase_requests = []

    def handle_api(self, route):
        req = route.request
        name = urlparse(req.url).path.rsplit("/", 1)[-1]
        body = json.loads(req.post_data or "{}") if req.method == "POST" else {}
        self.calls.setdefault(name, []).append(body)
        key = "ocr_problem" if name == "ocr" and body.get("mode") == "problem" else name
        payload = self.responses.get(key, {"success": False, "error": "unexpected call"})
        return route.fulfill(status=self.status.get(key, 200), content_type="application/json", body=json.dumps(payload))

    def block_supabase(self, route):
        self.supabase_requests.append(f"{route.request.method} {route.request.url}")
        return route.abort()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(_QuietHandler, directory=str(STATIC_DIR))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, channel="chrome", args=[
            "--use-fake-ui-for-media-stream",        # 카메라 권한 자동 허용
            "--use-fake-device-for-media-stream",    # 가짜 카메라 영상
        ])
        yield b
        b.close()


@pytest.fixture
def api():
    return FakeApi()


@pytest.fixture
def page(browser, base_url, api):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, permissions=["camera"])
    pg = ctx.new_page()
    pg.route("https://*.supabase.co/**", api.block_supabase)
    pg.route(f"{base_url}/api/**", api.handle_api)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(base_url + "/")
    pg.wait_for_load_state("networkidle")
    yield pg
    ctx.close()


TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def album(page, name="photo.png", mime="image/png", data=TINY_PNG):
    page.set_input_files("#album-input", files=[{"name": name, "mimeType": mime, "buffer": data}])


def wait_camera_ready(page):
    page.wait_for_selector("#screen-camera.active")
    page.wait_for_function("document.getElementById('cam-video').videoWidth > 0", timeout=10000)


def shoot_problem(page, use_album=False):
    """홈 → 카메라 → 촬영 → 문제 확인 화면"""
    page.click("#shoot-problem-btn")
    if use_album:
        page.wait_for_selector("#screen-camera.active")
        album(page)
    else:
        wait_camera_ready(page)
        page.click("#cam-shutter")
    page.wait_for_selector("#screen-confirm.active", timeout=10000)


def to_solve(page):
    shoot_problem(page)
    page.click("#confirm-ok-btn")
    page.wait_for_selector("#screen-solve.active")


def upload(page):
    """풀이 제출 화면에서 카메라를 열고 앨범으로 풀이 사진을 고른다"""
    if not page.locator("#screen-solve.active").count():
        to_solve(page)
    page.click("#solution-upload-area" if page.is_visible("#solution-upload-area") else "#retake-btn")
    page.wait_for_selector("#screen-camera.active")
    album(page)
    page.wait_for_selector("#screen-solve.active")
    page.wait_for_selector("#solution-preview", state="visible")


def submit(page):
    page.click("#submit-btn")
    page.wait_for_selector("#screen-result.active", timeout=15000)
