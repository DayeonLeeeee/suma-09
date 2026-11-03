/* ═══════════════════════════════════════════════════
   suma 시연 페이지
   홈(문제 촬영 · 문제 골라 풀기)
   → 문제 촬영(사이트 안 카메라) → Gemini Flash OCR → 문제 확인·글자 고치기
   → 풀이 촬영 → Gemini Flash OCR → 풀이 줄별 확인·수정
   → 채점 → 결과·힌트 3단계 → 해설(내 풀이와 비교)
   찍은 문제가 30번으로 인식되면 정돈된 문제 · 받은 고정 풀이 기준 채점 · 고정 해설을 쓴다.
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
// 서버 is_demo_problem 과 같은 단서 (글자를 고친 뒤에도 30번인지 판별)
const DEMO_CLUES = ["7자리", "문자열", "연달아", "뿐이다", "4개이상", "5개이하", "중복을허락",
  "baaacca", "ccbbaaa", "aabbcca", "aaabccc", "ccbaaaa"];
const MAX_SIDE = 1600;   // 업로드 전 사진 긴 변 (px)

const S = {
  screen: "home",
  stack: ["home"],     // 브라우저 기록과 같은 순서의 화면 목록
  busy: false,
  problem: null,       // {text, isDemo, key, photo, source, ocrSeconds, edited}
  solutionPhoto: null,
  lines: [],           // 읽은 풀이 줄 (수정 가능)
  attempts: 0,
  history: [],         // 이 문제에서 제출한 결과 [{error_category, is_correct}]
  grade: null,
  hints: [],
  hintOpen: 0,
  solutionCache: null,
  bank: [],
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
const NEEDS_PROBLEM = new Set(["confirm", "solve", "draw", "check", "result", "solution"]);

function show(screen) {
  if (S.screen === "camera" && screen !== "camera") stopCamera();
  document.querySelectorAll(".screen").forEach(el => el.classList.remove("active"));
  $("screen-" + screen).classList.add("active");
  S.screen = screen;
  window.scrollTo(0, 0);
}

function go(screen, { replace = false } = {}) {
  show(screen);
  if (replace) {
    S.stack[S.stack.length - 1] = screen;
    history.replaceState({ screen }, "");
  } else {
    S.stack.push(screen);
    history.pushState({ screen }, "");
  }
}

// 기록에서 가장 가까운 screen 까지 되돌아간다 (없으면 그 화면으로 이동)
function backTo(screen) {
  const i = S.stack.lastIndexOf(screen);
  const n = i >= 0 ? S.stack.length - 1 - i : 0;
  if (n > 0) history.go(-n);
  else if (i < 0) go(screen);
}

window.addEventListener("popstate", e => {
  if (S.busy) {                       // 읽는 중·채점 중에는 뒤로가기를 막는다
    history.pushState({ screen: S.screen }, "");
    return;
  }
  let target = (e.state && e.state.screen) || "home";
  const i = S.stack.lastIndexOf(target);
  S.stack = i >= 0 ? S.stack.slice(0, i + 1) : [...S.stack, target];
  if (TRANSIENT.has(target)) target = "home";
  if (NEEDS_PROBLEM.has(target) && !S.problem) target = "home";
  if ((target === "result" || target === "solution") && !S.grade) target = "check";
  if (target === "check" && !S.lines.length) target = "solve";
  show(target);
  if (target === "camera") startCamera();
  if (target === "check") growAllLines();
  if (target === "draw") requestAnimationFrame(() => pad.layout());
});
history.replaceState({ screen: "home" }, "");

document.querySelectorAll("[data-back]").forEach(b => b.addEventListener("click", () => history.back()));
document.querySelectorAll("[data-home]").forEach(b => b.addEventListener("click", newProblem));

function newProblem() {
  S.problem = null;
  S.grade = null;
  S.lines = [];
  resetSolutionPhoto();
  setText("home-error", "");
  backTo("home");
}

// ─── 홈: 문제 골라 풀기 ──────────────────────────────
async function loadBank() {
  try {
    const resp = await fetch(API + "/problems");
    const data = await resp.json();
    if (!data.success) throw new Error();
    S.bank = data.problems || [];
  } catch (e) {
    S.bank = [];
  }
  renderBank("");
}

function renderBank(level) {
  const list = $("bank-list");
  const items = [{ key: DEMO_KEY, source: "시연 문제 30번", level: "심화", text: DEMO_TEXT }, ...S.bank]
    .filter(p => !level || p.level === level);
  $("bank-count").textContent = `${S.bank.length + 1}문제`;
  if (!items.length) {
    list.innerHTML = `<div class="muted center bank-empty">이 난이도의 문제가 없습니다</div>`;
    return;
  }
  list.innerHTML = items.map(p => `
    <button class="bank-item" data-key="${esc(p.key)}">
      <span class="bank-top">
        <span class="bank-source">${esc(p.source || "문제 은행")}</span>
        <span class="level-pill lv-${esc(p.level)}">${esc(p.level)}</span>
      </span>
      <span class="bank-text">${esc(plainMath(p.text).split(/[①\n]/)[0])}</span>
    </button>`).join("");
  list.querySelectorAll(".bank-item").forEach(btn =>
    btn.addEventListener("click", () => startFromBank(btn.dataset.key)));
}

$("bank-filters").addEventListener("click", e => {
  const btn = e.target.closest(".filter");
  if (!btn) return;
  document.querySelectorAll("#bank-filters .filter").forEach(f => f.classList.toggle("on", f === btn));
  renderBank(btn.dataset.level);
});

function startFromBank(key) {
  const p = key === DEMO_KEY ? { key, text: DEMO_TEXT, source: "시연 문제 30번" } : S.bank.find(b => b.key === key);
  if (!p) return;
  setProblem({ text: key === DEMO_KEY ? DEMO_TEXT : plainMath(p.text), isDemo: key === DEMO_KEY,
               key: key === DEMO_KEY ? null : key, source: p.source });
  openSolve();
}

function setProblem(p) {
  S.problem = { photo: null, ocrSeconds: null, edited: false, ...p };
  S.attempts = 0;
  S.history = [];
  S.grade = null;
  S.lines = [];
  S.solutionCache = null;
  resetSolutionPhoto();
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

// ─── 공통: 읽는 중 화면 ──────────────────────────────
function startReading(dataUrl, kind) {
  $("reading-img").src = dataUrl;
  $("reading-title").textContent = kind === "problem" ? "문제를 읽고 있어요" : "풀이를 읽고 있어요";
  $("reading-sub").textContent = kind === "problem"
    ? "사진 속 글자와 수식을 텍스트로 바꾸는 중입니다"
    : "손글씨 풀이를 한 줄씩 텍스트로 바꾸는 중입니다";
  $("read-tidy-label").textContent = kind === "problem" ? "문제 정리" : "줄 나누기";
  readStep("upload", "active"); readStep("ocr", ""); readStep("tidy", "");
}

function readStep(step, state) {
  const dot = document.querySelector(`#read-${step} .proc-dot`);
  dot.className = "proc-dot" + (state ? " " + state : "");
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
  startReading(dataUrl, "problem");
  go("reading", { replace: S.screen === "camera" });
  const t0 = performance.now();

  try {
    const pending = postJson("/ocr", { image: dataUrl.split(",")[1], mime_type: "image/jpeg", mode: "problem" });
    readStep("upload", "done"); readStep("ocr", "active");
    const ocr = await pending;
    readStep("ocr", "done"); readStep("tidy", "active");

    const raw = ocr.final_text || (ocr.ocr_result && ocr.ocr_result.ocr_text) || "";
    const isDemo = ocr.problem_key === DEMO_KEY;
    if (!isDemo && !raw.trim()) throw new Error("사진에서 문제를 찾지 못했어요.");

    setProblem({ photo: dataUrl, isDemo, key: null, text: isDemo ? DEMO_TEXT : plainMath(raw),
                 ocrSeconds: (performance.now() - t0) / 1000 });
    readStep("tidy", "done");
    S.busy = false;
    renderConfirm();
    go("confirm", { replace: true });
  } catch (e) {
    S.busy = false;
    S.stack[S.stack.length - 1] = "home";
    show("home");
    history.replaceState({ screen: "home" }, "");
    setText("home-error", `문제를 읽지 못했어요. ${e.message} 밝은 곳에서 문제가 잘 보이게 다시 찍어주세요.`);
  }
}

function looksDemo(text) {
  const t = String(text || "").replace(/[\s$\\{}()'"]/g, "").toLowerCase();
  return DEMO_CLUES.filter(c => t.includes(c)).length >= 4;
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
  const p = S.problem;
  if (p.isDemo && !p.edited) return $("tpl-demo-problem").innerHTML;
  const tag = p.source ? esc(p.source) : (p.photo ? "찍은 문제" : "문제");
  return `<div class="problem-head"><span class="chip">${tag}</span></div>
    <p class="problem-text pre">${esc(p.text)}</p>`;
}

function renderConfirm() {
  const p = S.problem;
  $("confirm-img").src = p.photo || "";
  $("confirm-problem").innerHTML = problemHtml();
  $("confirm-time").textContent = p.ocrSeconds != null ? `${p.ocrSeconds.toFixed(1)}초` : "";
  $("confirm-unit").hidden = !p.isDemo;
  closeProblemEdit();
}

// 문제 글자 고치기
$("confirm-edit-btn").addEventListener("click", () => {
  $("confirm-textarea").value = S.problem.text;
  $("confirm-edit").hidden = false;
  $("confirm-problem").hidden = true;
  $("confirm-edit-hint").hidden = true;
  autoGrow($("confirm-textarea"));
  $("confirm-textarea").focus();
});
$("confirm-edit-cancel").addEventListener("click", closeProblemEdit);
$("confirm-edit-save").addEventListener("click", () => {
  const text = $("confirm-textarea").value.trim();
  if (!text) return;
  if (text !== S.problem.text) {
    S.problem.text = text;
    S.problem.edited = true;
    S.problem.isDemo = S.problem.isDemo && looksDemo(text);
  }
  $("confirm-problem").innerHTML = problemHtml();
  $("confirm-unit").hidden = !S.problem.isDemo;
  closeProblemEdit();
});
$("confirm-textarea").addEventListener("input", e => autoGrow(e.target));

function closeProblemEdit() {
  $("confirm-edit").hidden = true;
  $("confirm-problem").hidden = false;
  $("confirm-edit-hint").hidden = false;
}

$("confirm-retake-btn").addEventListener("click", () => {
  S.stack[S.stack.length - 1] = "home";
  history.replaceState({ screen: "home" }, "");
  openCamera("problem");
});
$("confirm-ok-btn").addEventListener("click", openSolve);

function openSolve() {
  $("solve-problem").innerHTML = problemHtml();
  document.querySelector("#screen-solve [data-back]").textContent = S.problem.photo ? "‹ 문제" : "‹ 목록";
  setText("submit-error", "");
  go("solve");
}

// ─── 풀이 사진 ───────────────────────────────────────
$("solution-upload-area").addEventListener("click", () => openCamera("solution"));
$("retake-btn").addEventListener("click", () => openCamera("solution"));
$("submit-btn").addEventListener("click", readSolution);

function setSolutionPhoto(dataUrl) {
  S.solutionPhoto = dataUrl;
  S.solutionSource = "photo";
  S.lines = [];
  $("solution-preview-img").src = dataUrl;
  $("solution-preview").hidden = false;
  $("solve-choices").hidden = true;
  $("solve-problem-wrap").open = false;
  setText("submit-error", "");
}

function resetSolutionPhoto() {
  S.solutionPhoto = null;
  S.solutionSource = null;
  S.lines = [];
  $("solution-preview").hidden = true;
  $("solve-choices").hidden = false;
  $("solve-problem-wrap").open = true;
  pad.reset();
}

// ─── 풀이 쓰기 (화면에 직접) ─────────────────────────
// 획(stroke)을 좌표 목록으로 저장해 두고 다시 그린다 → 되돌리기·지우개·공간 늘리기가 쉬움
const pad = {
  canvas: $("draw-canvas"),
  strokes: [],         // [{points: [[x, y], ...], width}]  (CSS px 좌표)
  undo: [],            // strokes 스냅샷
  tool: "pen",
  current: null,
  height: 0,
  ready: false,

  reset() {
    this.strokes = [];
    this.undo = [];
    this.current = null;
    this.height = 0;
    this.ready = false;
    this.setTool("pen");
    this.updateEmpty();
  },

  layout() {
    const scroll = $("draw-scroll");
    const w = $("draw-paper").clientWidth;
    if (!w) return;
    if (!this.height) this.height = Math.max(scroll.clientHeight - 70, 560);
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    this.canvas.style.width = w + "px";
    this.canvas.style.height = this.height + "px";
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(this.height * dpr);
    const ctx = this.canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ready = true;
    this.redraw();
  },

  redraw() {
    const ctx = this.canvas.getContext("2d");
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    for (const s of this.strokes) this.drawStroke(ctx, s);
    this.updateEmpty();
  },

  drawStroke(ctx, s) {
    const p = s.points;
    ctx.strokeStyle = "#1A1814";
    ctx.fillStyle = "#1A1814";
    ctx.lineWidth = s.width;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (p.length === 1) {
      ctx.beginPath(); ctx.arc(p[0][0], p[0][1], s.width / 2, 0, Math.PI * 2); ctx.fill();
      return;
    }
    ctx.beginPath();
    ctx.moveTo(p[0][0], p[0][1]);
    for (let i = 1; i < p.length - 1; i++) {      // 중간점을 이어 부드럽게
      const mx = (p[i][0] + p[i + 1][0]) / 2, my = (p[i][1] + p[i + 1][1]) / 2;
      ctx.quadraticCurveTo(p[i][0], p[i][1], mx, my);
    }
    const last = p[p.length - 1];
    ctx.lineTo(last[0], last[1]);
    ctx.stroke();
  },

  snapshot() {
    this.undo.push(this.strokes.map(s => ({ ...s, points: s.points.slice() })));
    if (this.undo.length > 60) this.undo.shift();
  },

  pos(e) {
    const r = this.canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  },

  eraseAt(x, y) {
    const r = 14;
    const before = this.strokes.length;
    this.strokes = this.strokes.filter(s => !s.points.some(([px, py]) => (px - x) ** 2 + (py - y) ** 2 < r * r));
    if (this.strokes.length !== before) this.redraw();
  },

  setTool(tool) {
    this.tool = tool;
    document.querySelectorAll(".draw-tools [data-tool]").forEach(b => b.classList.toggle("on", b.dataset.tool === tool));
    this.canvas.classList.toggle("move", tool === "move");
  },

  updateEmpty() {
    $("draw-empty").hidden = this.strokes.length > 0;
  },

  // 쓴 부분만 잘라 흰 바탕 그림으로 (OCR용)
  exportImage() {
    if (!this.strokes.length) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const s of this.strokes) for (const [x, y] of s.points) {
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    }
    const margin = 28;
    x0 = Math.max(0, x0 - margin); y0 = Math.max(0, y0 - margin); x1 += margin; y1 += margin;
    const k = Math.min(2, MAX_SIDE / Math.max(x1 - x0, y1 - y0));
    const out = document.createElement("canvas");
    out.width = Math.round((x1 - x0) * k);
    out.height = Math.round((y1 - y0) * k);
    const ctx = out.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.setTransform(k, 0, 0, k, -x0 * k, -y0 * k);
    for (const s of this.strokes) this.drawStroke(ctx, { ...s, width: Math.max(s.width, 3) });
    return out.toDataURL("image/jpeg", 0.92);
  },
};

pad.canvas.addEventListener("pointerdown", e => {
  if (pad.tool === "move") return;
  e.preventDefault();
  pad.canvas.setPointerCapture(e.pointerId);
  pad.snapshot();
  const [x, y] = pad.pos(e);
  if (pad.tool === "eraser") {
    pad.current = { erasing: true };
    pad.eraseAt(x, y);
  } else {
    const width = e.pointerType === "pen" ? 2.2 + 2 * (e.pressure || 0.5) : 3;
    pad.current = { points: [[x, y]], width };
    pad.strokes.push(pad.current);
    pad.redraw();
  }
  setText("draw-error", "");
});
pad.canvas.addEventListener("pointermove", e => {
  if (!pad.current) return;
  e.preventDefault();
  const events = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
  for (const ev of events.length ? events : [e]) {
    const [x, y] = pad.pos(ev);
    if (pad.current.erasing) pad.eraseAt(x, y);
    else pad.current.points.push([x, y]);
  }
  if (!pad.current.erasing) {
    const ctx = pad.canvas.getContext("2d");
    const p = pad.current.points;
    ctx.strokeStyle = "#1A1814"; ctx.lineWidth = pad.current.width; ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(...p[Math.max(0, p.length - events.length - 1)]);
    for (let i = Math.max(1, p.length - events.length); i < p.length; i++) ctx.lineTo(...p[i]);
    ctx.stroke();
  }
});
for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
  pad.canvas.addEventListener(type, () => {
    if (!pad.current) return;
    const wasErasing = pad.current.erasing;
    pad.current = null;
    if (!wasErasing) pad.redraw();       // 부드러운 곡선으로 다시 그림
  });
}

document.querySelectorAll(".draw-tools [data-tool]").forEach(b =>
  b.addEventListener("click", () => pad.setTool(b.dataset.tool)));
$("draw-undo").addEventListener("click", () => {
  if (!pad.undo.length) return;
  pad.strokes = pad.undo.pop();
  pad.redraw();
});
$("draw-clear").addEventListener("click", () => {
  if (!pad.strokes.length) return;
  pad.snapshot();
  pad.strokes = [];
  pad.redraw();
});
$("draw-more").addEventListener("click", () => {
  pad.height += 360;
  pad.layout();
  $("draw-scroll").scrollBy({ top: 320, behavior: "smooth" });
});
$("draw-problem-btn").addEventListener("click", () => {
  $("draw-problem-body").innerHTML = `<div class="card problem-card">${problemHtml()}</div>`;
  $("draw-problem").hidden = false;
});
$("draw-problem-close").addEventListener("click", () => { $("draw-problem").hidden = true; });
window.addEventListener("resize", () => { if (S.screen === "draw") pad.layout(); });

$("draw-btn").addEventListener("click", openDraw);

function openDraw() {
  setText("draw-error", "");
  $("draw-problem").hidden = true;
  go("draw");
  requestAnimationFrame(() => pad.layout());
}

$("draw-done").addEventListener("click", () => {
  const img = pad.exportImage();
  if (!img) { setText("draw-error", "아직 쓴 풀이가 없어요. 풀이를 쓴 다음 눌러주세요."); return; }
  S.solutionPhoto = img;
  S.solutionSource = "draw";
  S.lines = [];
  readSolution();
});

// ─── 풀이 읽기 (OCR) → 줄별 확인·수정 ────────────────
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

async function readSolution() {
  if (!S.solutionPhoto || S.busy) return;
  const origin = S.screen;               // 실패하면 돌아갈 화면 (풀이 제출 또는 풀이 쓰기)
  const errorBox = origin === "draw" ? "draw-error" : "submit-error";
  S.busy = true;
  setText(errorBox, "");
  startReading(S.solutionPhoto, "solution");
  go("reading");
  const t0 = performance.now();

  try {
    const pending = postJson("/ocr", { image: S.solutionPhoto.split(",")[1], mime_type: "image/jpeg", mode: "solution" });
    readStep("upload", "done"); readStep("ocr", "active");
    const ocr = await pending;
    readStep("ocr", "done"); readStep("tidy", "active");
    const lines = (ocr.steps && ocr.steps.length)
      ? ocr.steps.map(s => String(s.text || ""))
      : String(ocr.final_text || "").split("\n");
    S.lines = lines.map(t => t.trim()).filter(Boolean);
    if (!S.lines.length) throw new Error("사진에서 풀이 글씨를 찾지 못했어요.");
    readStep("tidy", "done");
    S.busy = false;
    renderCheck((performance.now() - t0) / 1000);
    go("check", { replace: true });
    growAllLines();
  } catch (e) {
    S.busy = false;
    S.stack[S.stack.length - 1] = origin;
    show(origin);
    history.replaceState({ screen: origin }, "");
    if (origin === "draw") requestAnimationFrame(() => pad.layout());
    setText(errorBox, origin === "draw"
      ? `풀이를 읽지 못했습니다. ${e.message} 글씨를 조금 크게 써서 다시 눌러주세요.`
      : `풀이를 읽지 못했습니다. ${e.message} 사진이 흐리면 다시 찍어서, 아니면 잠시 뒤에 다시 시도해주세요.`);
  }
}

function renderCheck(seconds) {
  const drawn = S.solutionSource === "draw";
  $("check-img").src = S.solutionPhoto;
  $("check-time").textContent = `${seconds.toFixed(1)}초`;
  $("check-photo-wrap").open = false;
  document.querySelector("#check-photo-wrap summary").textContent = drawn ? "내가 쓴 풀이" : "찍은 풀이 사진";
  $("check-back").textContent = drawn ? "‹ 쓰기" : "‹ 사진";
  $("check-retake-btn").textContent = drawn ? "다시 쓰기" : "다시 찍기";
  setText("check-error", "");
  renderLines();
}

function renderLines() {
  $("check-count").textContent = `${S.lines.length}줄`;
  $("line-list").innerHTML = S.lines.map((t, i) => `
    <div class="line-row">
      <span class="line-no">${i + 1}</span>
      <textarea class="line-input" data-i="${i}" rows="1" aria-label="${i + 1}번째 줄">${esc(t)}</textarea>
      <button class="line-del" data-i="${i}" aria-label="${i + 1}번째 줄 지우기">×</button>
    </div>`).join("");
  $("line-list").querySelectorAll(".line-input").forEach(ta => {
    autoGrow(ta);
    ta.addEventListener("input", () => { S.lines[Number(ta.dataset.i)] = ta.value; autoGrow(ta); });
  });
  $("line-list").querySelectorAll(".line-del").forEach(btn =>
    btn.addEventListener("click", () => { S.lines.splice(Number(btn.dataset.i), 1); renderLines(); }));
}

$("add-line-btn").addEventListener("click", () => {
  S.lines.push("");
  renderLines();
  const inputs = $("line-list").querySelectorAll(".line-input");
  inputs[inputs.length - 1].focus();
});
$("check-retake-btn").addEventListener("click", () => {
  if (S.solutionSource === "draw") {   // 확인 → 쓰던 화면 그대로 (이어서 고치기)
    S.lines = [];
    history.back();
    return;
  }
  resetSolutionPhoto();
  history.back();                      // 확인 → 풀이 제출 화면
});
$("grade-btn").addEventListener("click", gradeSolution);

function autoGrow(el) {
  if (!el.offsetParent) return;          // 화면에 보일 때만 높이를 잴 수 있다
  el.style.height = "auto";
  el.style.height = el.scrollHeight + 2 + "px";
}

function growAllLines() {
  requestAnimationFrame(() => $("line-list").querySelectorAll(".line-input").forEach(autoGrow));
}

// ─── 채점 ────────────────────────────────────────────
async function gradeSolution() {
  if (S.busy) return;
  const steps = S.lines.map(t => t.trim()).filter(Boolean).map((text, i) => ({ index: i + 1, text }));
  if (!steps.length) { setText("check-error", "채점할 풀이 줄이 없어요. 줄을 추가하거나 다시 찍어주세요."); return; }
  S.busy = true;
  setText("check-error", "");
  go("processing");
  procStep("grade", "active"); procStep("type", ""); procStep("hint", "");

  try {
    const body = { problem_text: S.problem.text, solution_steps: steps };
    if (S.problem.isDemo) {
      body.problem_key = DEMO_KEY;
      body.correct_answer = DEMO_ANSWER;
    } else if (S.problem.key) {
      body.problem_key = S.problem.key;    // 문제 은행 문항: 정답은 서버가 찾음
    }
    const result = await postJson("/grade", body);
    procStep("grade", "done"); procStep("type", "done"); procStep("hint", "done");

    S.attempts += 1;
    S.grade = result;
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
    S.stack[S.stack.length - 1] = "check";
    show("check");
    history.replaceState({ screen: "check" }, "");
    setText("check-error", `채점하지 못했습니다. ${e.message} 잠시 뒤에 다시 눌러주세요.`);
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
  backTo("solve");
}
$("solution-retry-btn").addEventListener("click", retry);

// ─── 유사 문제 추천 (설계 단계) ──────────────────────
// 실패해도 결과 화면에는 아무것도 띄우지 않는다
async function loadRecommendation(result, totalSteps, history) {
  let data;
  try {
    const body = {
      error_category: result.error_category,
      problem_text: S.problem.text,
      error_step_index: result.error_step_index,
      total_steps: totalSteps,
      history,
    };
    if (S.problem.key) body.problem_key = S.problem.key;
    data = await postJson("/recommend", body);
  } catch (e) {
    return;
  }
  const slot = $("rec-slot");
  if (!slot || !data.recommended) return;
  slot.innerHTML = recommendationCard(data, result.error_category);
  const btn = $("rec-solve-btn");
  if (btn) btn.addEventListener("click", () => startFromBank(data.recommended.key));
}

function recommendationCard(data, category) {
  const rec = data.recommended;
  const b = rec.breakdown || {};
  const source = (rec.text.match(/^\[([^\]]+)\]/) || [])[1] || "";
  const body = rec.text.replace(/^\[[^\]]+\]\s*/, "");
  const stage = STAGE_NAMES[data.student_stage];
  const typeName = ERROR_TYPE_NAMES[category] || category;
  const inBank = S.bank.some(p => p.key === rec.key);

  const rows = [
    ["함정 위치", b.trap_match, b.trap_match ? `${STAGE_NAMES[rec.trap]}에 함정이 있는 문제` : "함정 위치가 다름"],
    ["난이도", b.difficulty_fit, `${LEVEL_NAMES[rec.level] || rec.level} 문제 · 목표 ${LEVEL_NAMES[data.target_level] || data.target_level}`],
    ["새로움", b.novelty, "이 문제와 소재·문장이 다른 정도"],
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
      <div class="rec-text">${esc(plainMath(body))}</div>
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
    ${inBank ? `<button class="btn-secondary rec-solve" id="rec-solve-btn">이 문제 풀어보기</button>` : ""}
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
    const body = { problem_text: S.problem.text };
    if (S.problem.key) body.problem_key = S.problem.key;
    const sol = await postJson("/solution", body);
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

loadBank();
