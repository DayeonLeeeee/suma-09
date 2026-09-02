/* ═══════════════════════════════════════════════════
   suma SPA — vanilla JS
   ═══════════════════════════════════════════════════ */

// ─── Config ──────────────────────────────────────────
const API = location.origin + "/api";

const SUPABASE_URL  = "https://ptlqoigzcomhdspmcgkb.supabase.co";
const SUPABASE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0bHFvaWd6Y29taGRzcG1jZ2tiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MTQ4ODksImV4cCI6MjA5NjA5MDg4OX0.bq7zxOzmPeU6Q6-Od98zctze5-K-O0go9eellN3st-8";

let sb = null;
try { sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY); } catch(e) { console.warn("Supabase init skipped", e); }

// ─── State ───────────────────────────────────────────
const S = {
  mode: "problem",           // "problem" | "solution"
  imageDataUrl: null,        // base64 data URL
  imageBase64: null,          // raw base64 (no prefix)
  problemText: "",
  problemLatex: "",
  solutionSteps: [],          // [{index,text}]
  studentId: null,
  uploadProblemCode: null,
};

// ─── Routing ─────────────────────────────────────────
function go(screen) {
  document.querySelectorAll(".screen").forEach(el => el.classList.remove("active"));
  const el = document.getElementById("screen-" + screen);
  if (el) el.classList.add("active");

  const showChrome = (screen === "home");
  document.getElementById("fab-wrap").style.display  = showChrome ? "" : "none";
  document.getElementById("tab-bar").style.display   = showChrome ? "" : "none";
}

// ─── Home ────────────────────────────────────────────
function initHome() {
  const d = new Date();
  document.getElementById("home-date").textContent =
    d.toLocaleDateString("ko-KR", { year:"numeric", month:"2-digit", day:"2-digit", weekday:"short" });
}

// ─── Camera / Upload ─────────────────────────────────
function openCamera(mode) {
  S.mode = mode || "problem";
  S.imageDataUrl = null;
  S.imageBase64 = null;
  document.getElementById("camera-title").textContent = S.mode === "solution" ? "풀이 촬영" : "문제 촬영";
  document.getElementById("upload-badge").textContent  = S.mode === "solution" ? "풀이" : "문제";
  document.getElementById("upload-badge").className    = S.mode === "solution" ? "badge solution" : "badge";
  document.getElementById("upload-preview").style.display = "none";
  document.getElementById("file-input").value = "";
  go("camera");
}

document.getElementById("upload-area").addEventListener("click", () => {
  document.getElementById("file-input").click();
});

document.getElementById("file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    S.imageDataUrl = ev.target.result;
    S.imageBase64 = ev.target.result.split(",")[1];
    document.getElementById("preview-img-upload").src = S.imageDataUrl;
    document.getElementById("upload-preview").style.display = "";
    document.getElementById("upload-area").style.display = "none";
  };
  reader.readAsDataURL(file);
});

// ─── Crop (Canvas) ───────────────────────────────────
let cropImg = null;
let cropBox = { x: 0.04, y: 0.04, w: 0.92, h: 0.92 };
let cropDrag = null;
const cropCanvas = document.getElementById("crop-canvas");
const cropCtx = cropCanvas.getContext("2d");

function openCrop() {
  if (!S.imageDataUrl) return;
  cropBox = { x: 0.04, y: 0.04, w: 0.92, h: 0.92 };
  cropImg = new Image();
  cropImg.onload = () => {
    const maxW = Math.min(window.innerWidth - 40, 600);
    const scale = maxW / cropImg.width;
    cropCanvas.width = Math.round(cropImg.width * scale);
    cropCanvas.height = Math.round(cropImg.height * scale);
    drawCrop();
    go("crop");
  };
  cropImg.src = S.imageDataUrl;
}

function drawCrop() {
  if (!cropImg) return;
  const cw = cropCanvas.width, ch = cropCanvas.height;
  cropCtx.clearRect(0, 0, cw, ch);
  cropCtx.drawImage(cropImg, 0, 0, cw, ch);
  // dim outside
  cropCtx.fillStyle = "rgba(0,0,0,0.5)";
  const bx = cropBox.x * cw, by = cropBox.y * ch, bw = cropBox.w * cw, bh = cropBox.h * ch;
  cropCtx.fillRect(0, 0, cw, by);
  cropCtx.fillRect(0, by + bh, cw, ch - by - bh);
  cropCtx.fillRect(0, by, bx, bh);
  cropCtx.fillRect(bx + bw, by, cw - bx - bw, bh);
  // frame
  cropCtx.strokeStyle = "#fff";
  cropCtx.lineWidth = 2;
  cropCtx.strokeRect(bx, by, bw, bh);
  // grid
  cropCtx.strokeStyle = "rgba(255,255,255,0.25)";
  cropCtx.lineWidth = 0.5;
  for (let i = 1; i < 3; i++) {
    cropCtx.beginPath(); cropCtx.moveTo(bx, by + bh * i / 3); cropCtx.lineTo(bx + bw, by + bh * i / 3); cropCtx.stroke();
    cropCtx.beginPath(); cropCtx.moveTo(bx + bw * i / 3, by); cropCtx.lineTo(bx + bw * i / 3, by + bh); cropCtx.stroke();
  }
}

function cropPreset(type) {
  if (type === "top")    cropBox = { x: 0.02, y: 0.02, w: 0.96, h: 0.48 };
  if (type === "bottom") cropBox = { x: 0.02, y: 0.50, w: 0.96, h: 0.48 };
  if (type === "center") cropBox = { x: 0.12, y: 0.15, w: 0.76, h: 0.70 };
  drawCrop();
}
function resetCrop() { cropBox = { x: 0.04, y: 0.04, w: 0.92, h: 0.92 }; drawCrop(); }

// crop touch/mouse drag
function getCropPos(e) {
  const rect = cropCanvas.getBoundingClientRect();
  const t = e.touches ? e.touches[0] : e;
  return { x: t.clientX - rect.left, y: t.clientY - rect.top };
}
cropCanvas.addEventListener("pointerdown", (e) => {
  const p = getCropPos(e);
  const cw = cropCanvas.width, ch = cropCanvas.height;
  const bx = cropBox.x*cw, by = cropBox.y*ch, bw = cropBox.w*cw, bh = cropBox.h*ch;
  const H = 20;
  let type = "";
  const nearL = Math.abs(p.x-bx)<H, nearR = Math.abs(p.x-bx-bw)<H;
  const nearT = Math.abs(p.y-by)<H, nearB = Math.abs(p.y-by-bh)<H;
  if (nearT&&nearL) type="tl"; else if(nearT&&nearR) type="tr";
  else if(nearB&&nearL) type="bl"; else if(nearB&&nearR) type="br";
  else if(nearT) type="t"; else if(nearB) type="b";
  else if(nearL) type="l"; else if(nearR) type="r";
  else if(p.x>bx&&p.x<bx+bw&&p.y>by&&p.y<by+bh) type="move";
  if (!type) return;
  cropDrag = { type, startX: p.x, startY: p.y, startBox: {...cropBox} };
  cropCanvas.setPointerCapture(e.pointerId);
});
cropCanvas.addEventListener("pointermove", (e) => {
  if (!cropDrag) return;
  const p = getCropPos(e);
  const cw = cropCanvas.width, ch = cropCanvas.height;
  const dx = (p.x - cropDrag.startX)/cw, dy = (p.y - cropDrag.startY)/ch;
  let {x,y,w,h} = cropDrag.startBox;
  const MIN = 0.08;
  const t = cropDrag.type;
  if (t==="move") { x = clamp(x+dx,0,1-w); y = clamp(y+dy,0,1-h); }
  else {
    if (t.includes("t")) { const ny = clamp(y+dy,0,y+h-MIN); h -= ny-y; y = ny; }
    if (t.includes("b")) h = clamp(h+dy,MIN,1-y);
    if (t.includes("l")) { const nx = clamp(x+dx,0,x+w-MIN); w -= nx-x; x = nx; }
    if (t.includes("r")) w = clamp(w+dx,MIN,1-x);
  }
  cropBox = {x,y,w,h};
  drawCrop();
});
cropCanvas.addEventListener("pointerup", () => { cropDrag = null; });

function applyCrop() {
  if (!cropImg) { go("camera"); return; }
  const offscreen = document.createElement("canvas");
  const sx = Math.round(cropBox.x * cropImg.width);
  const sy = Math.round(cropBox.y * cropImg.height);
  const sw = Math.round(cropBox.w * cropImg.width);
  const sh = Math.round(cropBox.h * cropImg.height);
  offscreen.width = sw; offscreen.height = sh;
  offscreen.getContext("2d").drawImage(cropImg, sx, sy, sw, sh, 0, 0, sw, sh);
  S.imageDataUrl = offscreen.toDataURL("image/jpeg", 0.85);
  S.imageBase64 = S.imageDataUrl.split(",")[1];
  document.getElementById("preview-img-upload").src = S.imageDataUrl;
  go("camera");
}

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

// ─── OCR ─────────────────────────────────────────────
async function runOCR() {
  if (!S.imageBase64) return;
  go("preview");
  document.getElementById("preview-title").textContent = S.mode === "solution" ? "풀이 확인" : "문제 확인";
  show("preview-processing"); hide("preview-failed"); hide("preview-result");

  try {
    const resp = await fetch(API + "/ocr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: S.imageBase64, mime_type: "image/jpeg", mode: S.mode }),
    });
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "OCR 실패");

    hide("preview-processing");
    show("preview-result");

    if (S.mode === "solution") {
      const steps = data.steps || (data.gpt4o_result || {}).steps || [{ index: 1, text: data.final_text }];
      S.solutionSteps = steps;
      hide("problem-result"); show("solution-result");
      renderStepEditor(steps);
      saveSolutionToDB(steps);
    } else {
      const text = data.final_text || (data.gpt4o_result || {}).ocr_text || "";
      const latex = (data.gpt4o_result || {}).latex || "";
      S.problemText = text;
      S.problemLatex = latex;
      show("problem-result"); hide("solution-result");
      document.getElementById("problem-text-input").value = text;
      renderMath("problem-math-preview", text);
      saveProblemToDB(text, latex);
    }
  } catch (e) {
    hide("preview-processing");
    show("preview-failed");
    document.getElementById("preview-error").textContent = e.message;
  }
}

// problem text live preview
document.getElementById("problem-text-input").addEventListener("input", (e) => {
  S.problemText = e.target.value;
  renderMath("problem-math-preview", e.target.value);
});

// ─── Step Editor ─────────────────────────────────────
function renderStepEditor(steps) {
  const wrap = document.getElementById("solution-steps-editor");
  wrap.innerHTML = "";
  steps.forEach((step, i) => {
    const div = document.createElement("div");
    div.className = "step-editor-row";
    div.innerHTML = `<div class="step-label">Step ${i+1}</div><input class="step-input" value="${esc(step.text)}" data-idx="${i}">`;
    div.querySelector("input").addEventListener("input", (e) => { S.solutionSteps[i].text = e.target.value; });
    wrap.appendChild(div);
  });
}
function addStepInput() {
  S.solutionSteps.push({ index: S.solutionSteps.length + 1, text: "" });
  renderStepEditor(S.solutionSteps);
}

function startSolutionCapture() {
  openCamera("solution");
}

// ─── Grading ─────────────────────────────────────────
async function runGrading() {
  go("grading");
  show("grading-loading"); hide("grading-result");

  const steps = S.solutionSteps.filter(s => s.text.trim());
  if (!steps.length) {
    hide("grading-loading"); show("grading-result");
    document.getElementById("grading-result").innerHTML = '<div class="center-msg"><h2>채점 실패</h2><div class="muted">풀이 단계가 없습니다.</div></div>';
    return;
  }

  try {
    const resp = await fetch(API + "/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_text: S.problemText,
        problem_latex: S.problemLatex || S.problemText,
        solution_steps: steps.map(s => ({ index: s.index, text: s.text })),
      }),
    });
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "채점 실패");

    hide("grading-loading"); show("grading-result");
    renderGrading(data);
  } catch (e) {
    hide("grading-loading"); show("grading-result");
    document.getElementById("grading-result").innerHTML =
      `<div class="center-msg"><h2>채점 실패</h2><div class="error-text">${esc(e.message)}</div><button class="btn-primary" onclick="runGrading()">다시 시도</button></div>`;
  }
}

const ERROR_LABELS = {
  calculation_error: "계산 실수", wrong_concept: "개념 적용 오류",
  concept_missing: "개념 누락", approach_failure: "접근 방식 오류",
};
const STATUS_LABELS = { ok: "맞음", wrong: "오답", depends: "이전 오류 영향" };
const STATUS_COLORS = { ok: "var(--ok)", wrong: "var(--accent)", depends: "var(--ink3)" };

function renderGrading(r) {
  const isCorrect = !!r.is_correct;
  let html = `<div class="banner ${isCorrect ? 'correct' : 'wrong'}">
    <div class="banner-title">${isCorrect ? '정답입니다' : `Step ${r.error_step_index ?? '-'}에서 확인이 필요합니다`}</div>
    <div class="banner-text">${isCorrect ? '모든 풀이 단계가 문제 조건과 잘 맞습니다.' : (ERROR_LABELS[r.error_category] || r.error_category || '')}</div>
    ${r.ai_explanation ? `<div class="banner-text" style="margin-top:6px">${esc(r.ai_explanation)}</div>` : ''}
    <div class="confidence">신뢰도 ${Math.round((r.confidence||0)*100)}%</div>
  </div>`;

  if (!isCorrect) {
    const hints = [r.hint_direction || "", r.hint_concept || "", r.hint_near_answer || ""];
    html += `<div class="card">
      <div class="card-title">힌트 단계</div>
      <div class="hint-tabs">
        <button class="hint-tab active" onclick="switchHint(0,this)">방향</button>
        <button class="hint-tab" onclick="switchHint(1,this)">개념</button>
        <button class="hint-tab" onclick="switchHint(2,this)">근접</button>
      </div>
      <div class="hint-body" id="hint-body">${esc(hints[0])}</div>
    </div>`;
    window._hints = hints;
  }

  html += `<div class="card"><div class="card-title">단계별 판정</div>`;
  (r.steps || []).forEach(step => {
    const color = STATUS_COLORS[step.status] || "var(--ink3)";
    html += `<div class="step-row">
      <div class="status-dot" style="background:${color}"></div>
      <div style="flex:1">
        <div class="step-status" style="color:${color}">Step ${step.index} · ${STATUS_LABELS[step.status]||step.status}</div>
        <div class="math-render">${esc(step.text)}</div>
        ${step.explanation ? `<div class="step-explanation">${esc(step.explanation)}</div>` : ''}
      </div>
    </div>`;
  });
  html += `</div>`;

  html += `<div class="btn-row"><button class="btn-primary" onclick="goHome()">홈으로</button></div>`;

  document.getElementById("grading-result").innerHTML = html;
  renderAllMath(document.getElementById("grading-result"));
}

function switchHint(idx, btn) {
  document.querySelectorAll(".hint-tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById("hint-body").textContent = window._hints[idx] || "힌트가 없습니다.";
}

// ─── Solution ────────────────────────────────────────
async function viewSolution() {
  go("solution");
  show("solution-loading"); hide("solution-content");

  try {
    const resp = await fetch(API + "/solution", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_text: S.problemText,
        problem_latex: S.problemLatex || S.problemText,
      }),
    });
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "해설 생성 실패");

    hide("solution-loading"); show("solution-content");
    renderSolution(data);
  } catch (e) {
    hide("solution-loading"); show("solution-content");
    document.getElementById("solution-content").innerHTML =
      `<div class="center-msg"><h2>해설 생성 실패</h2><div class="error-text">${esc(e.message)}</div><button class="btn-primary" onclick="viewSolution()">다시 시도</button></div>`;
  }
}

function renderSolution(data) {
  let html = `<div class="problem-card"><div class="label">PROBLEM</div><div class="math-render">${esc(S.problemText)}</div></div>`;
  html += `<div class="meta-row">`;
  if (data.method_type) html += `<div class="chip">${esc(data.method_type)}</div>`;
  if (data.difficulty)  html += `<div class="chip">난이도 ${esc(data.difficulty)}</div>`;
  if (data.answer)      html += `<div class="chip accent">정답 ${esc(data.answer)}</div>`;
  html += `</div>`;

  html += `<div class="card"><div class="card-title">단계별 해설</div>`;
  (data.steps || []).forEach(step => {
    html += `<div class="sol-step">
      <div class="sol-step-title">Step ${step.step}. ${esc(step.title)}</div>
      <div class="math-render">${esc(step.content)}</div>
      ${step.formula ? `<div class="formula-box math-render">${esc(step.formula)}</div>` : ''}
    </div>`;
  });
  html += `</div>`;

  document.getElementById("solution-content").innerHTML = html;
  renderAllMath(document.getElementById("solution-content"));
}

// ─── KaTeX rendering ─────────────────────────────────
function renderMath(elementId, text) {
  const el = document.getElementById(elementId);
  el.textContent = text;
  try {
    renderMathInElement(el, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
      throwOnError: false, strict: false,
    });
  } catch (e) { /* fallback: plain text */ }
}

function renderAllMath(container) {
  try {
    renderMathInElement(container, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
      throwOnError: false, strict: false,
    });
  } catch (e) { /* ignore */ }
}

// ─── Supabase DB ─────────────────────────────────────
async function ensureStudent() {
  if (S.studentId) return S.studentId;
  if (!sb) return null;
  try {
    const { data: existing } = await sb.from("student").select("student_id").eq("name", "테스트").limit(1).maybeSingle();
    if (existing?.student_id) { S.studentId = existing.student_id; return S.studentId; }
    const { data } = await sb.from("student").insert({ name: "테스트", grade: "고등", srl_level: 5, srl_settings: {} }).select("student_id").single();
    S.studentId = data.student_id;
    return S.studentId;
  } catch (e) { console.warn("DB student error", e); return null; }
}

async function saveProblemToDB(text, latex) {
  const sid = await ensureStudent();
  if (!sid || !sb) return;
  try {
    const code = "UP_" + Date.now().toString(36);
    await sb.from("student_upload_problem").insert({ student_id: sid, upload_problem_code: code, ocr_text: text, match_status: "new" });
    S.uploadProblemCode = code;
  } catch (e) { console.warn("DB problem save error", e); }
}

async function saveSolutionToDB(steps) {
  const sid = await ensureStudent();
  if (!sid || !sb) return;
  try {
    await sb.from("handwriting_solution").insert({
      student_id: sid,
      upload_problem_code: S.uploadProblemCode || `UP_${Date.now().toString(36)}`,
      problem_source_type: "upload",
      ocr_steps: steps.map(s => ({ step: s.index, raw: s.text, latex: s.text })),
      is_correct: false,
    });
  } catch (e) { console.warn("DB solution save error", e); }
}

// ─── Utilities ───────────────────────────────────────
function show(id) { document.getElementById(id).style.display = ""; }
function hide(id) { document.getElementById(id).style.display = "none"; }
function esc(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }
function goHome() { S.mode = "problem"; go("home"); }

// ─── Init ────────────────────────────────────────────
initHome();
