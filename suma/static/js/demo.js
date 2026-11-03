/* ═══════════════════════════════════════════════════
   suma 시연 페이지
   홈 → 문제 촬영(사이트 안 카메라) → Gemini Flash OCR → 문제 확인
      → 풀이 촬영 → 채점 → 결과·힌트 3단계 → 해설(내 풀이와 비교)
   찍은 문제가 30번으로 인식되면 정돈된 문제·전용 채점·검증된 해설을 쓴다.
   DB에는 아무것도 저장하지 않는다.
   ═══════════════════════════════════════════════════ */

const API = location.origin + "/api";
const DEMO_KEY = "DEMO-30";
const DEMO_ANSWER = "188";
const DEMO_TEXT = [
  "세 문자 a, b, c 중에서 중복을 허락하여 각각 5개 이하씩 모두 7개를 택해 다음 조건을 만족시키는 7자리의 문자열을 만들려고 한다.",
  "(가) 한 문자가 연달아 3개 이어지고 그 문자는 a뿐이다.",
  "(나) 어느 한 문자도 연달아 4개 이상 이어지지 않는다.",
  "예를 들어, baaacca, ccbbaaa는 조건을 만족시키는 문자열이고 aabbcca, aaabccc, ccbaaaa는 조건을 만족시키지 않는 문자열이다. 만들 수 있는 모든 문자열의 개수를 구하시오.",
].join("\n");
const MAX_SIDE = 1600;   // 업로드 전 사진 긴 변 (px)

const S = {
  screen: "home",
  busy: false,
  problem: null,      // {photo, text, isDemo, ocrSeconds}
  solutionPhoto: null,
  attempts: 0,
  history: [],        // 이 문제에서 제출한 결과 [{error_category, is_correct}]
  grade: null,        // 마지막 채점 결과
  gradedSteps: [],
  hints: [],
  hintOpen: 0,
  solutionCache: null,
};

const ERROR_TYPE_NAMES = {
  B01: "체계적 나열 실패", B02: "순열-조합 혼동", B03: "합의 법칙-곱의 법칙 혼동",
  B04: "고정 조건 처리 오류", B05: "중복 계산", B06: "공식 오적용",
  B07: "여사건 접근 실패", B08: "조건 누락·오독", B09: "분류 기준 오류",
  B10: "자리 배분 오류", B11: "대칭성·동치 무시", B12: "단계 간 논리 비약",
  B13: "산술·대입 계산 오류", B14: "문제 상황 모델링 실패", B15: "교육과정 범위 밖 개념 사용",
};
const STAGE_NAMES = { early: "초반", mid: "중반", late: "후반" };
const LEVEL_NAMES = { 1: "기본", 2: "중간", 3: "심화" };
const $ = id => document.getElementById(id);

// ─── 화면 전환 + 휴대폰 뒤로가기 ─────────────────────
const TRANSIENT = new Set(["reading", "processing"]);   // 뒤로가기로 돌아오지 않는 화면
const NEEDS_PROBLEM = new Set(["confirm", "solve", "result", "solution"]);

function show(screen) {
  if (S.screen === "camera" && screen !== "camera") stopCamera();
  document.querySelectorAll(".screen").forEach(el => el.classList.remove("active"));
  $("screen-" + screen).classList.add("active");
  S.screen = screen;
  window.scrollTo(0, 0);
}

function go(screen, { replace = false } = {}) {
  show(screen);
  const state = { screen };
  if (replace) history.replaceState(state, "");
  else history.pushState(state, "");
}

window.addEventListener("popstate", e => {
  if (S.busy) {                       // 읽는 중·채점 중에는 뒤로가기를 막는다
    history.pushState({ screen: S.screen }, "");
    return;
  }
  let target = (e.state && e.state.screen) || "home";
  if (TRANSIENT.has(target)) target = "home";
  if (NEEDS_PROBLEM.has(target) && !S.problem) target = "home";
  if (target === "result" && !S.grade) target = "solve";
  show(target);
  if (target === "camera") startCamera();
});
history.replaceState({ screen: "home" }, "");

document.querySelectorAll("[data-back]").forEach(b => b.addEventListener("click", () => history.back()));
document.querySelectorAll("[data-home]").forEach(b => b.addEventListener("click", newProblem));

function newProblem() {
  S.problem = null;
  S.grade = null;
  resetSolutionPhoto();
  setText("home-error", "");
  go("home");
}

// ─── 카메라 ──────────────────────────────────────────
const cam = { stream: null, track: null, mode: "problem", facing: "environment", torch: false };
const video = $("cam-video");

function openCamera(mode) {
  cam.mode = mode;
  $("cam-title").textContent = mode === "problem" ? "문제를 찍어주세요" : "풀이를 찍어주세요";
  $("cam-guide").textContent = mode === "problem"
    ? "문제가 틀 안에 들어오게 맞춰주세요"
    : "풀이 전체가 틀 안에 들어오게 맞춰주세요";
  go("camera");
  startCamera();
}

async function startCamera() {
  $("cam-error").hidden = true;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    camError("이 브라우저에서는 카메라를 바로 열 수 없어요. 아래 버튼으로 사진을 찍어주세요.");
    return;
  }
  stopCamera();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: cam.facing }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false,
    });
    if (S.screen !== "camera") { stream.getTracks().forEach(t => t.stop()); return; }
    cam.stream = stream;
    cam.track = stream.getVideoTracks()[0];
    video.srcObject = stream;
    await video.play().catch(() => {});
    const caps = (cam.track.getCapabilities && cam.track.getCapabilities()) || {};
    $("cam-torch").hidden = !caps.torch;
    $("cam-torch-spacer").hidden = !!caps.torch;
  } catch (err) {
    camError(err && err.name === "NotAllowedError"
      ? "카메라 권한이 꺼져 있어요. 브라우저 설정에서 허용하거나, 아래 버튼으로 사진을 찍어주세요."
      : "카메라를 열지 못했어요. 아래 버튼으로 사진을 찍어주세요.");
  }
}

function stopCamera() {
  if (cam.stream) cam.stream.getTracks().forEach(t => t.stop());
  cam.stream = null;
  cam.track = null;
  cam.torch = false;
  $("cam-torch").classList.remove("on");
  video.srcObject = null;
}

function camError(msg) {
  $("cam-error-text").textContent = msg;
  $("cam-error").hidden = false;
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopCamera();
  else if (S.screen === "camera") startCamera();
});

$("cam-back").addEventListener("click", () => history.back());
$("cam-album").addEventListener("click", () => $("album-input").click());
$("cam-native-btn").addEventListener("click", () => $("native-camera-input").click());
$("cam-flip").addEventListener("click", () => {
  cam.facing = cam.facing === "environment" ? "user" : "environment";
  startCamera();
});
$("cam-torch").addEventListener("click", async () => {
  if (!cam.track) return;
  try {
    cam.torch = !cam.torch;
    await cam.track.applyConstraints({ advanced: [{ torch: cam.torch }] });
    $("cam-torch").classList.toggle("on", cam.torch);
  } catch (e) { cam.torch = false; }
});

$("cam-shutter").addEventListener("click", () => {
  if (!cam.stream || !video.videoWidth) return;
  const { w, h } = fit(video.videoWidth, video.videoHeight);
  const canvas = $("cam-canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d").drawImage(video, 0, 0, w, h);
  const flash = $("cam-flash");
  flash.classList.remove("go"); void flash.offsetWidth; flash.classList.add("go");
  captured(canvas.toDataURL("image/jpeg", 0.9));
});

for (const id of ["album-input", "native-camera-input"]) {
  $(id).addEventListener("change", async e => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try {
      captured(await shrinkFile(file));
    } catch (err) {
      camError("사진을 열지 못했어요. 다른 사진을 골라주세요.");
    }
  });
}

function fit(w, h) {
  const k = Math.min(1, MAX_SIDE / Math.max(w, h));
  return { w: Math.round(w * k), h: Math.round(h * k) };
}

function shrinkFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => resolve(reader.result);          // 그리지 못하면 원본 그대로
      img.onload = () => {
        const { w, h } = fit(img.naturalWidth || 1, img.naturalHeight || 1);
        const canvas = $("cam-canvas");
        canvas.width = w;
        canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.9));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

function captured(dataUrl) {
  if (cam.mode === "problem") {
    readProblem(dataUrl);
  } else {
    setSolutionPhoto(dataUrl);
    stopCamera();
    history.back();                    // 카메라 → 풀이 제출 화면
  }
}

// ─── 문제 읽기 (Gemini Flash OCR) ────────────────────
$("shoot-problem-btn").addEventListener("click", () => openCamera("problem"));
$("album-problem-btn").addEventListener("click", () => {
  cam.mode = "problem";
  $("album-input").click();
});

async function readProblem(dataUrl) {
  S.busy = true;
  setText("home-error", "");
  $("reading-img").src = dataUrl;
  readStep("upload", "active"); readStep("ocr", ""); readStep("tidy", "");
  if (S.screen === "camera") go("reading", { replace: true });
  else go("reading");
  const t0 = performance.now();

  try {
    const pending = postJson("/ocr", { image: dataUrl.split(",")[1], mime_type: "image/jpeg", mode: "problem" });
    readStep("upload", "done"); readStep("ocr", "active");
    const ocr = await pending;
    readStep("ocr", "done"); readStep("tidy", "active");

    const raw = ocr.final_text || (ocr.ocr_result && ocr.ocr_result.ocr_text) || "";
    const isDemo = ocr.problem_key === DEMO_KEY;
    if (!isDemo && !raw.trim()) throw new Error("사진에서 문제를 찾지 못했어요.");

    S.problem = {
      photo: dataUrl,
      isDemo,
      text: isDemo ? DEMO_TEXT : plainMath(raw),
      ocrSeconds: (performance.now() - t0) / 1000,
    };
    S.attempts = 0;
    S.history = [];
    S.grade = null;
    S.solutionCache = null;
    resetSolutionPhoto();
    readStep("tidy", "done");
    S.busy = false;
    renderConfirm();
    go("confirm", { replace: true });
  } catch (e) {
    S.busy = false;
    show("home");
    history.replaceState({ screen: "home" }, "");
    setText("home-error", `문제를 읽지 못했어요. ${e.message} 밝은 곳에서 문제가 잘 보이게 다시 찍어주세요.`);
  }
}

function readStep(step, state) {
  const dot = document.querySelector(`#read-${step} .proc-dot`);
  dot.className = "proc-dot" + (state ? " " + state : "");
}

function plainMath(s) {
  return String(s || "")
    .replace(/\$\$?/g, "")
    .replace(/\\(?:text|mathrm|mathit|operatorname)\{([^}]*)\}/g, "$1")
    .replace(/\\times/g, "×").replace(/\\cdot/g, "·").replace(/\\le(q)?/g, "≤").replace(/\\ge(q)?/g, "≥")
    .replace(/\\ldots|\\cdots/g, "…").replace(/\\neq/g, "≠")
    .replace(/\\([a-zA-Z]+)/g, "$1")
    .replace(/[{}]/g, "")
    .trim();
}

function problemHtml() {
  if (S.problem.isDemo) return $("tpl-demo-problem").innerHTML;
  return `<div class="problem-head"><span class="chip">찍은 문제</span></div>
    <p class="problem-text pre">${esc(S.problem.text)}</p>`;
}

function renderConfirm() {
  $("confirm-img").src = S.problem.photo;
  $("confirm-problem").innerHTML = problemHtml();
  $("confirm-time").textContent = `${S.problem.ocrSeconds.toFixed(1)}초`;
  $("confirm-unit").hidden = !S.problem.isDemo;
}

$("confirm-retake-btn").addEventListener("click", () => {
  history.replaceState({ screen: "home" }, "");
  openCamera("problem");
});
$("confirm-ok-btn").addEventListener("click", () => {
  $("solve-problem").innerHTML = problemHtml();
  setText("submit-error", "");
  go("solve");
});

// ─── 풀이 사진 ───────────────────────────────────────
$("solution-upload-area").addEventListener("click", () => openCamera("solution"));
$("retake-btn").addEventListener("click", () => openCamera("solution"));
$("submit-btn").addEventListener("click", submitSolution);

function setSolutionPhoto(dataUrl) {
  S.solutionPhoto = dataUrl;
  $("solution-preview-img").src = dataUrl;
  $("solution-preview").hidden = false;
  $("solution-upload-area").hidden = true;
  $("solve-problem-wrap").open = false;
  setText("submit-error", "");
}

function resetSolutionPhoto() {
  S.solutionPhoto = null;
  $("solution-preview").hidden = true;
  $("solution-upload-area").hidden = false;
  $("solve-problem-wrap").open = true;
}

// ─── 제출 → 채점 ─────────────────────────────────────
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
  if (!S.solutionPhoto || S.busy) return;
  S.busy = true;
  setText("submit-error", "");
  go("processing");
  procStep("ocr", "active"); procStep("grade", ""); procStep("hint", "");

  try {
    const ocr = await postJson("/ocr", {
      image: S.solutionPhoto.split(",")[1],
      mime_type: "image/jpeg",
      mode: "solution",
    });
    const steps = (ocr.steps && ocr.steps.length)
      ? ocr.steps.map(s => ({ index: s.index, text: s.text }))
      : [{ index: 1, text: ocr.final_text || "" }];
    procStep("ocr", "done"); procStep("grade", "active");

    const body = { problem_text: S.problem.text, solution_steps: steps };
    if (S.problem.isDemo) {
      body.problem_key = DEMO_KEY;
      body.correct_answer = DEMO_ANSWER;
    }
    const result = await postJson("/grade", body);
    procStep("grade", "done"); procStep("hint", "done");

    S.attempts += 1;
    S.grade = result;
    S.gradedSteps = steps;
    const previous = S.history.slice();
    S.history.push({ error_category: result.error_category || null, is_correct: !!result.is_correct });
    S.busy = false;
    renderResult(result);
    go("result", { replace: true });
    if (!result.is_correct && result.error_category) {
      loadRecommendation(result, (result.steps || steps).length, previous);
    }
  } catch (e) {
    S.busy = false;
    show("solve");
    history.replaceState({ screen: "solve" }, "");
    setText("submit-error", `제출하지 못했습니다. ${e.message} 사진이 흐리면 다시 찍어서, 아니면 잠시 뒤에 다시 제출해주세요.`);
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

  if (!correct && r.error_category) {
    html += `<div class="type-row"><span class="chip accent">오답 유형 · ${esc(ERROR_TYPE_NAMES[r.error_category] || r.error_category)}</span></div>`;
  }

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
    html += `<div id="rec-slot"></div>`;
  }

  html += `<div class="btn-row">
    <button class="btn-secondary" id="solution-btn">해설 보기</button>
    <button class="btn-primary" id="retry-btn">다시 풀기</button>
  </div>`;

  const box = $("result-content");
  box.innerHTML = html;
  box.querySelectorAll(".hint-tab").forEach(tab =>
    tab.addEventListener("click", () => openHint(Number(tab.dataset.level))));
  $("solution-btn").addEventListener("click", openSolution);
  $("retry-btn").addEventListener("click", retry);
}

// ─── 힌트: 앞 단계를 본 다음에만 다음 단계가 열린다 ───
function openHint(level) {
  if (level > S.hintOpen) {
    $("hint-note").textContent = `${S.hintOpen + 1}단계 힌트를 먼저 확인해주세요.`;
    return;
  }
  if (level === S.hintOpen) {
    S.hintOpen += 1;
    $(`hint-tab-${level}`).classList.remove("locked");
  }
  document.querySelectorAll(".hint-tab").forEach(t => t.classList.remove("active"));
  $(`hint-tab-${level}`).classList.add("active");
  $("hint-body").textContent = S.hints[level];
  $("hint-note").textContent =
    S.hintOpen < 3 ? "막히면 다음 단계를 눌러보세요. 한 단계씩 열립니다." : "마지막 힌트입니다. 답은 직접 구해보세요.";
}

function retry() {
  resetSolutionPhoto();
  setText("submit-error", "");
  history.back();                      // 결과 → 풀이 제출 화면
}
$("solution-retry-btn").addEventListener("click", () => {
  resetSolutionPhoto();
  setText("submit-error", "");
  history.go(-2);                      // 해설 → 결과 → 풀이 제출 화면
});

// ─── 유사 문제 추천 (설계 단계) ──────────────────────
// 실패해도 결과 화면에는 아무것도 띄우지 않는다
async function loadRecommendation(result, totalSteps, history) {
  let data;
  try {
    data = await postJson("/recommend", {
      error_category: result.error_category,
      problem_text: S.problem.text,
      error_step_index: result.error_step_index,
      total_steps: totalSteps,
      history,
    });
  } catch (e) {
    return;
  }
  const slot = $("rec-slot");
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
    ["새로움", b.novelty, "찍은 문제와 소재·문장이 다른 정도"],
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

// ─── 해설: 내 풀이와 비교 + 해설 본문 ────────────────
function openSolution() {
  renderCompare();
  go("solution");
  if (S.problem.isDemo) {
    $("solution-body").innerHTML = $("tpl-demo-solution").innerHTML;
    const focus = (S.grade && S.grade.solution_focus) || [];
    let first = null;
    for (const sec of focus) {
      const el = $("solution-body").querySelector(`[data-sec="${sec}"]`);
      if (!el) continue;
      el.classList.add("focus");
      if (!first) first = el;
    }
    if (first) setTimeout(() => first.scrollIntoView({ behavior: "smooth", block: "center" }), 350);
  } else {
    loadGeneratedSolution();
  }
}

function renderCompare() {
  const r = S.grade || {};
  const note = r.solution_note ? `<p class="compare-note">${esc(r.solution_note)}</p>` : "";
  let html;
  if (r.is_correct) {
    html = `<div class="card compare ok">
      <div class="card-title">내 풀이와 비교</div>
      <p class="compare-lead">정답이에요. 내 풀이와 해설의 흐름을 비교해 보세요.</p>${note}
    </div>`;
  } else {
    const wrong = (r.steps || []).find(s => s.status === "wrong");
    const typeName = ERROR_TYPE_NAMES[r.error_category] || "";
    const hasFocus = S.problem.isDemo && (r.solution_focus || []).length;
    html = `<div class="card compare">
      <div class="card-title">내 풀이와 비교</div>
      ${wrong ? `<div class="compare-line"><span>${wrong.index}번째 줄 · 처음 틀린 줄</span><div>${esc(wrong.text)}</div></div>` : ""}
      ${typeName ? `<div class="type-row"><span class="chip accent">오답 유형 · ${esc(typeName)}</span></div>` : ""}
      ${note}
      ${hasFocus ? `<p class="muted">아래 해설에서 <span class="focus-mark">표시된 부분</span>이 내가 틀린 곳과 이어지는 부분이에요.</p>` : ""}
    </div>`;
  }
  $("compare-card").innerHTML = html;
}

async function loadGeneratedSolution() {
  const box = $("solution-body");
  if (S.solutionCache) { box.innerHTML = S.solutionCache; return; }
  box.innerHTML = `<div class="card center-msg small"><div class="spinner"></div><div class="muted">해설을 만드는 중입니다</div></div>`;
  try {
    const sol = await postJson("/solution", { problem_text: S.problem.text });
    const html = `<div class="meta-row">
        ${(sol.concept_tags || []).map(t => `<div class="chip">${esc(t)}</div>`).join("")}
        ${sol.answer ? `<div class="chip accent">정답 ${esc(plainMath(sol.answer))}</div>` : ""}
      </div>
      <div class="card sol-case">
        ${(sol.steps || []).map(st => `<div class="sol-step">
            <div class="sol-step-title">${esc(st.step)}. ${esc(plainMath(st.title))}</div>
            <div>${esc(plainMath(st.content))}</div>
            ${st.formula ? `<div class="formula-box">${esc(plainMath(st.formula))}</div>` : ""}
          </div>`).join("")}
      </div>`;
    S.solutionCache = html;
    if (S.screen === "solution") box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<div class="card"><p class="error-text">해설을 불러오지 못했어요. 잠시 뒤에 다시 열어주세요.</p></div>`;
  }
}

// ─── 유틸 ────────────────────────────────────────────
function fmt(v) { return (typeof v === "number" ? v : 0).toFixed(2); }
function setText(id, msg) { $(id).textContent = msg; }
function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
