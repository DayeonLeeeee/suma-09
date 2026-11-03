"""
E2E 테스트 공통 설정
- static/ 폴더를 로컬 http 서버로 띄우고 /api/* 는 가짜 응답으로 가로챈다
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
}

GRADE_CORRECT = {
    "success": True,
    "is_correct": True,
    "error_step_index": None,
    "error_category": None,
    "steps": [{"index": 1, "text": "88 + 100 = 188", "status": "ok"}],
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


class FakeApi:
    def __init__(self):
        self.calls = {}        # endpoint -> [body, ...]
        self.responses = {
            "ocr": {"success": True, "steps": [{"index": 1, "text": "aaa가 양 끝: 44 × 2 = 88"}, {"index": 2, "text": "답 88"}]},
            "grade": copy.deepcopy(GRADE_WRONG),
            "recommend": copy.deepcopy(RECOMMEND_OK),
        }
        self.status = {}
        self.supabase_requests = []

    def handle_api(self, route):
        req = route.request
        name = urlparse(req.url).path.rsplit("/", 1)[-1]
        body = json.loads(req.post_data or "{}") if req.method == "POST" else {}
        self.calls.setdefault(name, []).append(body)
        payload = self.responses.get(name, {"success": False, "error": "unexpected call"})
        return route.fulfill(status=self.status.get(name, 200), content_type="application/json", body=json.dumps(payload))

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
        b = p.chromium.launch(headless=True, channel="chrome")
        yield b
        b.close()


@pytest.fixture
def api():
    return FakeApi()


@pytest.fixture
def page(browser, base_url, api):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
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


def upload(page, name="solution.png", mime="image/png", data=TINY_PNG):
    page.set_input_files("#solution-file-input", files=[{"name": name, "mimeType": mime, "buffer": data}])
    page.wait_for_selector("#solution-preview", state="visible")


def submit(page):
    page.click("#submit-btn")
    page.wait_for_selector("#screen-result.active", timeout=15000)
