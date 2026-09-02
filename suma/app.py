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
            "표기 규칙: "
            "- 분수는 a/b 형식 (예: 3/5, (a+b)/c) "
            "- 제곱근은 √ (예: √6, √(a+b)) "
            "- 로그 밑은 log_2 형식 (예: log_2 72, log_5 (x+1)) "
            "- 지수는 ^로 (예: x^2, 2^n) "
            "- 첨자는 _로 (예: a_n, x_1) "
            "- 곱셈은 × 또는 ·, 나눗셈은 ÷ "
            "- 부등호는 ≤ ≥ ≠ "
            "예시: 'a_2 = a_1 - 2', 'log_2 72 - log_2 (36/16) = log_2 (72 × 16/36)' "
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

[채점 원칙 — 매우 중요]
0. 먼저 당신이 직접 이 문제를 끝까지 풀어 정답을 구하세요. 나머지정리·인수정리·근의공식·삼각함수·부등식 등 모든 표준 정리를 정확히 적용하세요.
   (예: "나눈 나머지가 R이다" = 나누는 수를 대입한 값이 R. R=0이 아님)
1. 그 정답을 기준으로 학생 풀이를 채점하되, 글자 그대로 비교하지 마세요.
2. 학생이 다른 방법·다른 순서·다른 표기를 써도, 논리적으로 타당하고 같은 결론에 도달하면 "ok"입니다.
3. 중간 계산을 일부 생략했어도 수학적으로 맞으면 "ok"로 인정하세요.
4. 학생이 "참/거짓"을 명시한 경우, 그 판단의 근거가 수학적으로 타당한지 확인하세요.
5. OCR로 부호(-)·분수가 깨졌을 수 있으니, 표기 실수는 학생 의도를 고려해 관대하게 보고 실제 수학적 오류만 "wrong"으로 잡으세요.
6. 학생의 최종 답이 정답과 일치하고 논리에 큰 결함이 없으면 is_correct=true.
7. 진짜 수학적으로 틀린 최초 단계만 "wrong", 그 이후는 "depends".

[판단 기준] "이 줄이 모범풀이와 똑같은가?"가 아니라 "이 단계가 수학적으로 옳고, 결론으로 가는 데 타당한가?"로 채점하세요.

[오류 분류]
error_category: "calculation_error"(계산실수) | "wrong_concept"(개념오류) | "concept_missing"(개념부재) | "approach_failure"(접근실패)

[힌트 3단계 - 정보량을 점진적으로 늘리기]

hint_direction (방향 힌트, 1단계):
- 학생이 어느 부분을 다시 봐야 할지만 알려주세요.
- 정답이나 정답 근처 값은 절대 노출 금지.
- 공식 이름도 알려주지 마세요.
- 1줄 (20자 이내)로 짧게.
- 예: "마지막 계산을 다시 확인해보세요." / "분배법칙을 적용한 부분을 살펴보세요."

hint_concept (개념 힌트, 2단계):
- 필요한 공식·정리·개념의 이름을 알려주세요.
- 그 개념이 왜 이 단계에 필요한지 한 문장 설명.
- 정답이나 정답 근처 값은 여전히 노출 금지.
- 2~3줄.
- 예: "로그의 성질 log(ab) = log a + log b를 떠올려보세요. 두 항을 합치는 단계에서 이 공식이 필요합니다."

hint_near_answer (근접 힌트, 3단계):
- 거의 답까지 보여주는 단계. 마지막 한 두 계산만 학생이 하도록.
- 구체적인 식과 중간 값을 모두 노출.
- 단, 최종 답 자체는 직접 말하지 않고 학생이 구하게 둠.
- 예: "72 × 16/36 = 32 까지 정리하셨습니다. 이제 log₂ 32 = ? 만 계산하면 답입니다."

[힌트 작성 원칙]
- 세 힌트는 같은 오류를 다른 깊이로 다룹니다. 서로 다른 주제를 다루지 마세요.
- 방향 → 개념 → 근접 순으로 정보량이 증가해야 합니다.
- 1단계는 절대 답 근처 값을 노출하지 마세요. 3단계는 학생이 마지막 한 발만 떼면 되도록 거의 다 풀어주세요.

[중요] steps의 text는 LaTeX 없이 읽기 쉬운 수학 표현으로 작성하세요 (예: sin θ, (√3/3), (π/6)).

반드시 아래 JSON 형식으로만 응답:
{{
    "is_correct": true/false,
    "difficulty": "하 또는 중 또는 상",
    "error_step_index": null 또는 숫자,
    "steps": [
        {{"index": 1, "text": "읽기 쉬운 수학 표현", "status": "ok|wrong|depends", "explanation": "이 단계 설명"}}
    ],
    "error_category": null 또는 문자열,
    "error_detail": "간단한 오류 설명",
    "ai_explanation": "학생에게 보여줄 설명 (한국어, 친절하게)",
    "hint_direction": "방향 힌트",
    "hint_concept": "개념 힌트",
    "hint_near_answer": "근접 힌트",
    "confidence": 0.0~1.0
}}"""

        msg = claude_client.messages.create(
            model="claude-opus-4-6", max_tokens=4096, temperature=0.0,
            system="당신은 수학 채점 전문가입니다. 먼저 문제를 스스로 정확히 풀어 정답을 구한 뒤, 학생 풀이를 맥락과 논리 중심으로 채점합니다. 응답은 반드시 JSON 객체로만 시작하고 끝납니다. 풀이 과정이나 설명을 JSON 밖에 절대 작성하지 마세요.",
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
                system="당신은 정확한 수학 문제 해결자입니다. 답을 반드시 검산하는 습관이 있고, 절대 추측하지 않습니다.",
                messages=[{"role": "user", "content": f"""다음 수학 문제를 풀어 최종 정답만 정확히 구하세요.

[문제]
{the_problem}

[지시 - 매우 중요]
1. 문제를 차근차근 단계별로 풀이하세요.
2. 각 계산을 검증하며 진행하세요.
3. 최종 답을 다른 접근법으로 한 번 더 검산하세요.
4. 답의 형태(자연수/분수/소수/기호 등)를 명확히 하세요.
5. 어떤 경우에도 답을 추측하지 말고, 수학적으로 정확히 도출하세요.

JSON으로만 응답:
{{
    "answer": "최종 답 (간단한 텍스트, $ 없이. 예: 5, 65, 3/5)",
    "verification": "답이 맞다는 검증 한 줄 (예: 'log_2 32 = 5 확인')",
    "difficulty": "하 또는 중 또는 상"
}}"""}],
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
                {"role": "system", "content": "정확한 수학 풀이 생성기. 주어진 정답으로 정확히 수렴하는 풀이를 만듭니다."},
                {"role": "user", "content": f"""당신은 고등학교 수학 모범 풀이 전문가입니다.

[문제]
{the_problem}
{answer_constraint}
[작성 규칙]
1. 가장 정석적이고 교과서적인 풀이를 작성하세요. 다른 풀이법은 절대 포함하지 마세요.
2. 위 "필수 정답"으로 정확히 수렴하는 풀이를 작성하세요. 정답을 임의로 바꾸지 마세요.
3. 단계 수는 난이도에 따라 결정하세요:
   - 난이도 "하": 2~3단계 (간단한 계산 문제는 풀이를 길게 늘리지 마세요)
   - 난이도 "중": 3~4단계
   - 난이도 "상": 4~5단계
4. 각 단계는 제목, 설명, 핵심 수식으로 구성하세요.
5. 설명(content)과 수식(formula) 안의 수학 표현은 모두 $...$ 로 감싸세요. 한글은 $ 밖에.

[분량 제약 — 매우 중요]
- title: 10자 이내. 간결한 제목.
- content: 1~2문장만. 군더더기·반복·형식적 표현 최소화.
- formula: 그 단계의 핵심 식 한 줄만.
- concept_tags: 2~3개로 제한.

반드시 아래 JSON 형식으로만 응답:
{{
    "method_type": "풀이 방법 이름",
    "difficulty": "하 또는 중 또는 상",
    "concept_tags": ["개념1", "개념2"],
    "answer": "최종 답 ($ 없이 간단히)",
    "steps": [
        {{"step": 1, "title": "단계 제목", "content": "설명 (수식은 $...$)", "formula": "$핵심 수식$"}}
    ]
}}"""},
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
                system="수학 교육 콘텐츠 검수 전문가. 수학적 정확성을 최우선으로 검증하고 정리합니다. JSON 외 어떤 텍스트도 출력하지 않습니다.",
                messages=[{"role": "user", "content": f"""아래는 수학 문제와 풀이입니다. 정확성과 표현을 다듬어 정리하세요.

[문제]
{the_problem}

[필수 정답 - 반드시 이 답으로 끝나야 함]
{correct_answer or gpt_result.get("answer", "")}

[검토할 풀이 (JSON)]
{json.dumps(gpt_result, ensure_ascii=False)}

[정리 규칙]
1. 풀이의 최종 답이 "필수 정답"과 다르면, 풀이 자체를 수정해서 정답에 맞추세요.
2. 각 단계가 논리적으로 이어지는지 검증하세요. 비약·오류가 있으면 고치세요.
3. 수식은 $...$ 로 감싸고, 한글 설명은 $ 밖에 두세요.
4. answer는 $ 없이 간단한 텍스트로.
5. 원본과 동일한 JSON 구조로만 응답 (method_type, difficulty, concept_tags, answer, steps).
6. 분량 제약: title 10자 이내, content 1~2문장, formula 한 줄.
7. 단계 수 - 난이도 "하": 2~3단계, "중": 3~4단계, "상": 4~5단계. 잘게 쪼개진 단계는 합치세요.
8. 한 가지 풀이만 보여주세요. 여러 풀이법을 나열하지 마세요.

JSON 외 다른 텍스트는 절대 포함하지 마세요. JSON으로만 응답하세요."""}],
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
