/* ═══════════════════════════════════════════════════
   suma 시연 페이지 — 30번 한 문제
   풀이 촬영 → OCR → 채점 → 힌트 3단계 → 해설
   DB에는 아무것도 저장하지 않는다
   ═══════════════════════════════════════════════════ */

const API = location.origin + "/api";

const PROBLEM_TEXT = [
  "세 문자 a, b, c 중에서 중복을 허락하여 각각 5개 이하씩 모두 7개를 택해 다음 조건을 만족시키는 7자리의 문자열을 만들려고 한다.",
  "(가) 한 문자가 연달아 3개 이어지고 그 문자는 a뿐이다.",
  "(나) 어느 한 문자도 연달아 4개 이상 이어지지 않는다.",
  "예를 들어, baaacca, ccbbaaa는 조건을 만족시키는 문자열이고 aabbcca, aaabccc, ccbaaaa는 조건을 만족시키지 않는 문자열이다. 만들 수 있는 모든 문자열의 개수를 구하시오.",
].join("\n");

const CORRECT_ANSWER = "188";

// 채점 기준용 모범 풀이 (해설 화면과 같은 흐름)
const REFERENCE_SOLUTION = [
  "aaa 블록의 위치로 경우를 나눈다. aaa 바로 옆에는 b 또는 c가 와야 한다.",
  "1. aaa가 양 끝 (aaa____ 또는 ____aaa, 대칭)",
  "  a가 5개: 2 × 3C2 × 2 = 12",
  "  a가 4개: 2 × (3C1 × 2 × 2 − 1) = 22  (aaabbba처럼 bbb가 생기는 경우 제외)",
  "  a가 3개: 2^4 − 2 × 3 = 10  (bbb, ccc가 생기는 경우 제외)",
  "  44 × 2 = 88",
  "2. aaa가 가운데",
  "  _aaa___: 2 × 2 × (3^2 − 1) = 32",
  "  __aaa__: 2 × 2 × 3 × 3 = 36",
  "  ___aaa_: 32 (대칭)",
  "  합 100",
  "답: 88 + 100 = 188",
].join("\n");

const S = {
  file: null,
  imageDataUrl: null,
  imageBase64: null,
  attempts: 0,
  hints: [],
  hintOpen: 0,   // 열린 힌트 개수 (0~3)
  history: [],   // 이번 접속에서 제출한 결과 [{error_category, is_correct}]
};

// app.py 오답유형 코드 → 이름
const ERROR_TYPE_NAMES = {
  B01: "체계적 나열 실패", B02: "순열-조합 혼동", B03: "합의 법칙-곱의 법칙 혼동",
  B04: "고정 조건 처리 오류", B05: "중복 계산", B06: "공식 오적용",
  B07: "여사건 접근 실패", B08: "조건 누락·오독", B09: "분류 기준 오류",
  B10: "자리 배분 오류", B11: "대칭성·동치 무시", B12: "단계 간 논리 비약",
  B13: "산술·대입 계산 오류", B14: "문제 상황 모델링 실패", B15: "교육과정 범위 밖 개념 사용",
};
const STAGE_NAMES = { early: "초반", mid: "중반", late: "후반" };
const LEVEL_NAMES = { 1: "기본", 2: "중간", 3: "심화" };

// ─── 화면 전환 ───────────────────────────────────────
function go(screen) {
  document.querySelectorAll(".screen").forEach(el => el.classList.remove("active"));
  document.getElementById("screen-" + screen).classList.add("active");
  window.scrollTo(0, 0);
}

// ─── 사진 고르기 ─────────────────────────────────────
const fileInput = document.getElementById("solution-file-input");
const uploadArea = document.getElementById("solution-upload-area");

uploadArea.addEventListener("click", () => fileInput.click());
uploadArea.addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});

fileInput.addEventListener("change", e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    S.file = file;
    S.imageDataUrl = ev.target.result;
    S.imageBase64 = ev.target.result.split(",")[1];
    document.getElementById("solution-preview-img").src = S.imageDataUrl;
    show("solution-preview");
    hide("solution-upload-area");
    setError("");
  };
  reader.readAsDataURL(file);
});

function resetPhoto() {
  S.file = null;
  S.imageDataUrl = null;
  S.imageBase64 = null;
  fileInput.value = "";
  hide("solution-preview");
  show("solution-upload-area");
}

function setError(msg) {
  document.getElementById("submit-error").textContent = msg;
}

document.getElementById("retake-btn").addEventListener("click", resetPhoto);
document.getElementById("submit-btn").addEventListener("click", submitSolution);

// ─── 제출 ────────────────────────────────────────────
async function postJson(path, body) {
  const resp = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await resp.json(); } catch (e) { /* 본문이 JSON이 아님 */ }
  if (!resp.ok || !data || !data.success) {
    throw new Error((data && data.error) || `서버 응답 오류 (${resp.status})`);
  }
  return data;
}

async function submitSolution() {
  if (!S.imageBase64) return;
  setError("");
  go("processing");
  procStep("ocr", "active");
  procStep("grade", "");
  procStep("hint", "");

  try {
    const ocr = await postJson("/ocr", {
      image: S.imageBase64,
      mime_type: S.file?.type || "image/jpeg",
      mode: "solution",
    });
    const steps = (ocr.steps && ocr.steps.length)
      ? ocr.steps.map(s => ({ index: s.index, text: s.text }))
      : [{ index: 1, text: ocr.final_text || "" }];

    procStep("ocr", "done");
    procStep("grade", "active");

    const result = await postJson("/grade", {
      problem_text: PROBLEM_TEXT,
      solution_steps: steps,
      correct_answer: CORRECT_ANSWER,
      reference_solution: REFERENCE_SOLUTION,
    });

    procStep("grade", "done");
    procStep("hint", "done");

    S.attempts += 1;
    const previous = S.history.slice();
    S.history.push({ error_category: result.error_category || null, is_correct: !!result.is_correct });
    renderResult(result);
    go("result");
    if (!result.is_correct && result.error_category) {
      // error_step_index는 채점 결과의 줄 번호 기준이므로 전체 줄 수도 채점 결과에서 센다
      loadRecommendation(result, (result.steps || steps).length, previous);
    }
  } catch (e) {
    go("problem");
    setError(`제출하지 못했습니다. ${e.message} 사진이 흐리면 다시 찍어서, 아니면 잠시 뒤에 다시 제출해주세요.`);
  }
}

function procStep(step, state) {
  const dot = document.querySelector(`#proc-${step} .proc-dot`);
  dot.className = "proc-dot" + (state ? " " + state : "");
}

// ─── 결과 ────────────────────────────────────────────
function renderResult(r) {
  const correct = !!r.is_correct;
  let html = `<div class="banner ${correct ? "correct" : "wrong"}">
    <div class="banner-title">${correct ? "정답입니다" : "다시 확인해볼 곳이 있어요"}</div>
    <div class="banner-text">${correct
      ? "풀이 단계가 모두 맞습니다."
      : esc(r.ai_explanation || "처음 틀린 줄부터 다시 살펴보세요.")}</div>
    <div class="attempt-info">${S.attempts}번째 제출</div>
  </div>`;

  // 처음 틀린 줄까지만 보여 준다
  if (r.steps && r.steps.length) {
    html += `<div class="card"><div class="card-title">줄별 판정</div>`;
    for (const step of r.steps) {
      const wrong = step.status === "wrong";
      html += `<div class="step-row ${wrong ? "is-wrong" : "is-ok"}">
        <div class="status-dot"></div>
        <div class="step-body">
          <div class="step-status">${step.index}번째 줄 · ${wrong ? "처음 틀린 줄" : "맞음"}</div>
          <div class="step-text">${esc(step.text)}</div>
          ${wrong && step.explanation ? `<div class="step-explanation">${esc(step.explanation)}</div>` : ""}
        </div>
      </div>`;
      if (wrong) break;
    }
    html += `</div>`;
  }

  if (!correct) {
    S.hints = [r.hint_direction, r.hint_concept, r.hint_near_answer].map(h => h || "이 단계의 힌트가 없습니다.");
    S.hintOpen = 1;
    html += `<div class="card" id="hint-card">
      <div class="card-title">힌트</div>
      <div class="hint-tabs">
        ${["방향", "개념", "거의 답"].map((name, i) => `
          <button class="hint-tab ${i === 0 ? "active" : "locked"}" id="hint-tab-${i}" data-level="${i}">
            ${i + 1}단계<small>${name}</small>
          </button>`).join("")}
      </div>
      <div class="hint-body" id="hint-body">${esc(S.hints[0])}</div>
      <div class="hint-note muted" id="hint-note">막히면 다음 단계를 눌러보세요. 한 단계씩 열립니다.</div>
    </div>`;
  }

  if (!correct) html += `<div id="rec-slot"></div>`;

  html += `<div class="btn-row">
    <button class="btn-secondary" id="solution-btn">해설 보기</button>
    <button class="btn-primary" id="retry-btn">다시 풀기</button>
  </div>`;

  const box = document.getElementById("result-content");
  box.innerHTML = html;
  box.querySelectorAll(".hint-tab").forEach(tab =>
    tab.addEventListener("click", () => openHint(Number(tab.dataset.level))));
  document.getElementById("solution-btn").addEventListener("click", () => go("solution"));
  document.getElementById("retry-btn").addEventListener("click", retry);
}

// ─── 힌트: 앞 단계를 본 다음에만 다음 단계가 열린다 ───
function openHint(level) {
  if (level > S.hintOpen) {
    document.getElementById("hint-note").textContent = `${S.hintOpen + 1}단계 힌트를 먼저 확인해주세요.`;
    return;
  }
  if (level === S.hintOpen) {
    S.hintOpen += 1;
    document.getElementById(`hint-tab-${level}`).classList.remove("locked");
  }
  document.querySelectorAll(".hint-tab").forEach(t => t.classList.remove("active"));
  document.getElementById(`hint-tab-${level}`).classList.add("active");
  document.getElementById("hint-body").textContent = S.hints[level];
  document.getElementById("hint-note").textContent =
    S.hintOpen < 3 ? "막히면 다음 단계를 눌러보세요. 한 단계씩 열립니다." : "마지막 힌트입니다. 답은 직접 구해보세요.";
}

// ─── 유사 문제 추천 (설계 단계) ──────────────────────
// 실패해도 결과 화면에는 아무것도 띄우지 않는다
async function loadRecommendation(result, totalSteps, history) {
  let data;
  try {
    data = await postJson("/recommend", {
      error_category: result.error_category,
      problem_text: PROBLEM_TEXT,
      error_step_index: result.error_step_index,
      total_steps: totalSteps,
      history,
    });
  } catch (e) {
    return;
  }
  const slot = document.getElementById("rec-slot");
  if (!slot || !data.recommended) return;
  slot.innerHTML = recommendationCard(data, result.error_category);
}

function recommendationCard(data, category) {
  const rec = data.recommended;
  const b = rec.breakdown || {};
  const source = (rec.text.match(/^\[([^\]]+)\]/) || [])[1] || "";
  const body = rec.text.replace(/^\[[^\]]+\]\s*/, "");
  const stage = STAGE_NAMES[data.student_stage];
  const typeName = ERROR_TYPE_NAMES[category] || category;

  const rows = [
    ["함정 위치", b.trap_match, b.trap_match ? `${STAGE_NAMES[rec.trap]}에 함정이 있는 문제` : "함정 위치가 다름"],
    ["난이도", b.difficulty_fit, `${LEVEL_NAMES[rec.level] || rec.level} 문제 · 목표 ${LEVEL_NAMES[data.target_level] || data.target_level}`],
    ["새로움", b.novelty, "30번 문제와 소재·문장이 다른 정도"],
  ];

  return `<div class="card rec-card" id="rec-card">
    <div class="rec-head">
      <div class="card-title">비슷한 실수를 연습할 문제</div>
      <span class="chip small">설계 단계</span>
    </div>
    <p class="rec-why">${stage ? `풀이 ${stage}에서 ` : ""}<b>${esc(typeName)}</b> 유형으로 틀렸습니다.
      같은 실수가 나올 수 있는 문제 중 겉모습이 다른 문제를 골랐습니다.</p>
    <div class="rec-problem">
      ${source ? `<div class="rec-source">${esc(source)}</div>` : ""}
      <div class="rec-text">${esc(body)}</div>
    </div>
    <div class="rec-scores">
      ${rows.map(([label, v, note]) => `
        <div class="rec-score">
          <div class="rec-score-top"><span>${label}</span><span>${fmt(v)}</span></div>
          <div class="rec-bar"><div style="width:${Math.round((v || 0) * 100)}%"></div></div>
          <div class="rec-note">${esc(note)}</div>
        </div>`).join("")}
    </div>
    <div class="rec-formula muted">점수 = 0.4 × 함정 위치 + 0.3 × 난이도 + 0.3 × 새로움 = <b>${fmt(rec.score)}</b></div>
  </div>`;
}

function fmt(v) { return (typeof v === "number" ? v : 0).toFixed(2); }

function retry() {
  resetPhoto();
  setError("");
  go("problem");
}

document.getElementById("result-back-btn").addEventListener("click", () => go("problem"));
document.getElementById("solution-back-btn").addEventListener("click", () => go("result"));
document.getElementById("solution-retry-btn").addEventListener("click", retry);

// ─── 유틸 ────────────────────────────────────────────
function show(id) { document.getElementById(id).style.display = ""; }
function hide(id) { document.getElementById(id).style.display = "none"; }
function esc(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }
