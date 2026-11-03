"""/api/grade: 참고 풀이(reference_solution)가 채점 프롬프트에 들어가는지 확인 (외부 API 호출 없음)"""
import importlib
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    for name in ("anthropic", "openai", "google", "google.generativeai"):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    cors = types.ModuleType("flask_cors")
    cors.CORS = lambda app: None
    monkeypatch.setitem(sys.modules, "flask_cors", cors)
    monkeypatch.syspath_prepend(str(ROOT))
    sys.modules.pop("app", None)
    mod = importlib.import_module("app")

    sent = []
    reply = {"is_correct": True, "error_step_index": None, "steps": [{"index": 1, "text": "188", "status": "ok"}],
             "error_category": None}

    def fake_create(**kwargs):
        sent.append(kwargs["messages"][0]["content"])
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps(reply))]
        msg.stop_reason = "end_turn"
        return msg

    mod.claude_client = MagicMock()
    mod.claude_client.messages.create.side_effect = fake_create
    yield mod.app.test_client(), sent
    sys.modules.pop("app", None)


def _grade(client, **extra):
    body = {"problem_text": "문제", "solution_steps": [{"index": 1, "text": "188"}], "correct_answer": "188"}
    body.update(extra)
    return client.post("/api/grade", json=body)


def test_reference_solution_goes_into_prompt(server):
    client, sent = server
    resp = _grade(client, reference_solution="REF-양끝 88 + 가운데 100 = 188")
    assert resp.status_code == 200
    assert "REF-양끝 88 + 가운데 100 = 188" in sent[0]


def test_prompt_unchanged_without_reference_solution(server):
    client, sent = server
    _grade(client)
    assert "참고 풀이" not in sent[0]


def test_field_study_page_still_served(server):
    client, _ = server
    resp = client.get("/field/")
    assert resp.status_code == 200
    assert b"/field/app.js" in resp.data


def test_root_serves_demo_page(server):
    client, _ = server
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"/js/demo.js" in resp.data
