"""
suma server — Railway 배포용
OCR: Mathpix + Gemini 2.5 Pro + Claude 판정
채점: Claude Opus
해설: Claude 정답 → GPT-4o 풀이 → Claude 검증
"""

import os, json, base64, re, datetime, traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
import requests as http_requests
import anthropic
import google.generativeai as genai

# ─── 환경변수 ──────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY    = os.environ["OPENAI_API_KEY"]
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
MATHPIX_APP_ID    = os.environ["MATHPIX_APP_ID"]
MATHPIX_APP_KEY   = os.environ["MATHPIX_APP_KEY"]

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)


# ─── 유틸: JSON 파싱 ────────────────────────────────
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


# ─── Mathpix OCR ─────────────────────────────────────
def call_mathpix(image_b64, mime_type):
    resp = http_requests.post(
        "https://api.mathpix.com/v3/text",
        headers={"app_id": MATHPIX_APP_ID, "app_key": MATHPIX_APP_KEY, "Content-Type": "application/json"},
        data=json.dumps({
            "src": f"data:{mime_type};base64,{image_b64}",
            "formats": ["text", "latex_styled"],
            "data_options": {"include_latex": True},
        }),
    )
    if resp.status_code == 200:
        d = resp.json()
        return (d.get("latex_styled") or d.get("text", "")).strip()
    return ""


# ─── Gemini OCR ──────────────────────────────────────
def call_gemini_ocr(image_b64, mime_type, mode="problem"):
    if mode == "solution":
        instruction = (
            "당신은 손글씨 수학 풀이 OCR 시스템입니다. "
            "학생이 쓴 풀이를 적힌 그대로 정확히 읽으세요. 오류를 고치지 마세요. "
            "단계별로 번호를 나누세요. "
            "중요: LaTeX 명령어(\\frac, \\sqrt, \\log 등)는 절대 사용하지 마세요. "
            "수식을 사람이 읽기 쉬운 평문으로 작성하세요. "
            "표기 규칙: 분수는 a/b, 제곱근은 √, 로그 밑은 log_2, 지수는 ^, 첨자는 _ "
            '반드시 JSON으로만 응답: {"steps": [{"index": 1, "text": "평문 수식"}]}'
        )
    else:
        instruction = (
            "당신은 수학 문제 OCR 시스템입니다. 인쇄된 문제를 적힌 그대로 정확히 읽으세요. "
            "중요: 모든 수식은 $...$ 로 감싸고, 한글은 $ 밖에 두세요. "
            '반드시 JSON으로만 응답: {"ocr_text": "...", "latex": "...", "problem_number": "...", "source": "..."}'
        )

    model = genai.GenerativeModel("gemini-2.5-pro")
    image_part = {"mime_type": mime_type, "data": base64.b64decode(image_b64)}
    response = model.generate_content(
        [instruction, "이 수학 문제/풀이를 정확히 읽어줘.", image_part],
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
    )
    return response.text


# ─── Claude 판정 (불일치 시) ─────────────────────────
def call_judge_claude(image_b64, mime_type, res_a, res_b):
    prompt = f"""두 OCR 결과가 다릅니다. 첨부 이미지를 직접 보고 올바르게 다시 읽어주세요.
수식은 반드시 $...$ 로 감싸고, 한글은 $ 밖에 두세요.

[엔진 A - Mathpix]: {res_a}
[엔진 B - Gemini]: {res_b}

JSON으로만 응답: {{"final_text": "...", "winner": "a 또는 b 또는 rewrite"}}"""

    msg = claude_client.messages.create(
        model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
        ]}],
    )
    return msg.content[0].text


# ─── API: Health ─────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": str(datetime.datetime.now())})


# ─── API: OCR ────────────────────────────────────────
@app.route("/api/ocr", methods=["POST"])
def ocr_endpoint():
    try:
        data = request.get_json()
        image_b64 = data["image"]
        mime_type = data.get("mime_type", "image/jpeg")
        mode = data.get("mode", "problem")

        print(f"\n[OCR] mode={mode}, size={len(image_b64)//1024}KB")

        mathpix_result = call_mathpix(image_b64, mime_type)
        gemini_raw = call_gemini_ocr(image_b64, mime_type, mode)
        gemini_json = parse_json_loose(gemini_raw)

        gemini_text = gemini_json.get("ocr_text", "")
        is_match = mathpix_result.replace(" ", "") == gemini_text.replace(" ", "")
        judge_result = None

        if not is_match and mathpix_result and gemini_text and mode == "problem":
            try:
                judge_result = parse_json_loose(
                    call_judge_claude(image_b64, mime_type, mathpix_result, gemini_text)
                )
                judged = judge_result.get("final_text", "")
                final_text = judged if '$' in judged else (gemini_text or mathpix_result)
            except Exception:
                final_text = gemini_text or mathpix_result
        else:
            final_text = gemini_text or mathpix_result

        result = {
            "success": True, "mode": mode,
            "mathpix_result": mathpix_result,
            "gpt4o_result": gemini_json,
            "is_match": is_match,
            "judge_result": judge_result,
            "final_text": final_text,
        }
        if mode == "solution" and "steps" in gemini_json:
            result["steps"] = gemini_json["steps"]

        return jsonify(result)

    except Exception as e:
        print(f"[OCR error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 채점 ───────────────────────────────────────
@app.route("/api/grade", methods=["POST"])
def grade_endpoint():
    try:
        data = request.get_json()
        problem_text = data.get("problem_text", "")
        solution_steps = data.get("solution_steps", [])
        problem_latex = data.get("problem_latex", "")

        clean_problem = problem_latex or problem_text
        clean_steps = "\n".join([f"Step {s['index']}: {s['text']}" for s in solution_steps])

        prompt = f"""당신은 고등학교 수학 채점 전문가입니다.

[문제]
{clean_problem}

[학생의 풀이]
{clean_steps}

[채점 원칙]
0. 먼저 직접 문제를 풀어 정답을 구하세요.
1. 학생이 다른 방법·순서·표기를 써도 논리적으로 타당하면 "ok".
2. 중간 계산 생략도 수학적으로 맞으면 "ok".
3. OCR 표기 실수는 관대하게, 실제 수학적 오류만 "wrong".
4. 최종 답이 정답과 일치하고 논리 결함이 없으면 is_correct=true.
5. 진짜 틀린 최초 단계만 "wrong", 그 이후는 "depends".

[오류 분류]
error_category: "calculation_error" | "wrong_concept" | "concept_missing" | "approach_failure"

[힌트 3단계]
hint_direction: 방향만 (20자 이내, 정답 노출 금지)
hint_concept: 필요한 공식/정리 이름 + 왜 필요한지 (2~3줄)
hint_near_answer: 거의 답까지 (마지막 한두 계산만 학생이 하도록)

반드시 JSON:
{{
    "is_correct": true/false,
    "difficulty": "하/중/상",
    "error_step_index": null 또는 숫자,
    "steps": [{{"index": 1, "text": "...", "status": "ok|wrong|depends", "explanation": "..."}}],
    "error_category": null 또는 문자열,
    "error_detail": "...",
    "ai_explanation": "학생에게 보여줄 설명 (한국어)",
    "hint_direction": "...",
    "hint_concept": "...",
    "hint_near_answer": "...",
    "confidence": 0.0~1.0
}}"""

        msg = claude_client.messages.create(
            model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
            system="수학 채점 전문가. JSON 객체로만 응답.",
            messages=[{"role": "user", "content": prompt}],
        )
        result = parse_json_loose(msg.content[0].text)
        result["success"] = True
        return jsonify(result)

    except Exception as e:
        print(f"[Grade error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 해설 ───────────────────────────────────────
@app.route("/api/solution", methods=["POST"])
def solution_endpoint():
    try:
        data = request.get_json()
        problem_text = data.get("problem_text", "")
        problem_latex = data.get("problem_latex", "")
        the_problem = problem_latex or problem_text

        # 1) Claude로 정답 계산
        correct_answer = ""
        try:
            ans_msg = claude_client.messages.create(
                model="claude-opus-4-6", max_tokens=2048, temperature=0.0,
                system="정확한 수학 문제 해결자. 반드시 검산.",
                messages=[{"role": "user", "content": f"""다음 문제를 풀어 정답만 구하세요.

[문제]
{the_problem}

JSON: {{"answer": "최종 답", "verification": "검증 한 줄", "difficulty": "하/중/상"}}"""}],
            )
            ans_data = parse_json_loose(ans_msg.content[0].text)
            correct_answer = str(ans_data.get("answer", "")).strip()
        except Exception:
            pass

        # 2) GPT-4o 풀이 작성
        answer_constraint = f"\n[필수 정답]\n{correct_answer}\n" if correct_answer else ""
        gpt_resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "정확한 수학 풀이 생성기."},
                {"role": "user", "content": f"""고등학교 수학 모범 풀이를 작성하세요.

[문제]
{the_problem}
{answer_constraint}
[규칙]
1. 정석적 교과서 풀이 1개만.
2. 수식은 $...$ 로 감싸고 한글은 밖에.
3. title 10자 이내, content 1~2문장, formula 한 줄.

JSON: {{"method_type": "...", "difficulty": "하/중/상", "concept_tags": [...], "answer": "...", "steps": [{{"step": 1, "title": "...", "content": "...", "formula": "..."}}]}}"""},
            ],
            response_format={"type": "json_object"},
            max_tokens=4096, temperature=0.1,
        )
        gpt_result = json.loads(gpt_resp.choices[0].message.content)
        if correct_answer and str(gpt_result.get("answer", "")).strip() != correct_answer:
            gpt_result["answer"] = correct_answer

        # 3) Claude 검증
        result = gpt_result
        try:
            verify_msg = claude_client.messages.create(
                model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
                system="수학 콘텐츠 검수. JSON만 출력.",
                messages=[{"role": "user", "content": f"""풀이를 검증/정리하세요.

[문제] {the_problem}
[필수 정답] {correct_answer or gpt_result.get("answer", "")}
[풀이] {json.dumps(gpt_result, ensure_ascii=False)}

원본과 동일 JSON 구조로 응답. title 10자, content 1~2문장."""}],
            )
            polished = parse_json_loose(verify_msg.content[0].text)
            if correct_answer and str(polished.get("answer", "")).strip() != correct_answer:
                polished["answer"] = correct_answer
            result = polished
        except Exception:
            pass

        result["success"] = True
        result["full_solution"] = ""
        return jsonify(result)

    except Exception as e:
        print(f"[Solution error] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Static 서빙 ─────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
