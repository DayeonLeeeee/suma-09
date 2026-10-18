/* ═══════════════════════════════════════════════════
   suma SPA — 현장연구용 (2026-10)
   학생 선택 → 배정 문제 → 풀이 촬영 → 채점 → 힌트
   ═══════════════════════════════════════════════════ */

// ─── Config ──────────────────────────────────────────
const API = location.origin + "/api";

const SUPABASE_URL = "https://tfggqqutghkmnlmrrvfo.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRmZ2dxcXV0Z2hrbW5sbXJydmZvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE3ODY1NTcsImV4cCI6MjEwNzM2MjU1N30.oLtSBEmRKWpGVIE4VOe6WqbNp99dF4HAi2UIHE64dm0";

let sb = null;
try { sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY); } catch (e) { console.warn("Supabase init skipped", e); }

// ─── State ───────────────────────────────────────────
const S = {
  studentCode: null,       // 1~4
  studentId: null,          // UUID from DB
  problemSet: null,         // "P" or "Q"
  problems: [],             // [{problem_id, problem_number, problem_text, answer, problem_set}]
  attempts: {},             // {problem_id: [{attempt_no, is_correct, ...}]}
  currentProblem: null,     // 현재 선택한 문제 객체
  currentAttempt: 0,        // 현재 시도 횟수
  imageDataUrl: null,
  imageBase64: null,
  lastGradingResult: null,  // 마지막 채점 결과
  hintRevealed: 0,          // 0=없음, 1=방향, 2=개념, 3=근접
};

// 학생번호 → 문제세트 매핑
const STUDENT_SET_MAP = { 1: "P", 2: "P", 3: "Q", 4: "Q" };

// ─── Routing ─────────────────────────────────────────
function go(screen) {
  document.querySelectorAll(".screen").forEach(el => el.classList.remove("active"));
  const el = document.getElementById("screen-" + screen);
  if (el) el.classList.add("active");

  if (screen === "home") loadProblems();
}

// ─── Login ───────────────────────────────────────────
function loginWithId() {
  const input = document.getElementById("login-id-input");
  const errorEl = document.getElementById("login-error");
  const code = parseInt(input.value, 10);

  if (!code || code < 1 || code > 4) {
    errorEl.textContent = "1~4 사이의 번호를 입력해주세요.";
    input.focus();
    return;
  }
  errorEl.textContent = "";
  selectStudent(code);
}

async function selectStudent(code) {
  S.studentCode = code;
  S.problemSet = STUDENT_SET_MAP[code];

  // DB에서 학생 찾거나 생성
  if (sb) {
    try {
      const studentName = `학생${code}`;
      const { data: existing } = await sb
        .from("student")
        .select("student_id")
        .eq("student_code", code)
        .limit(1)
        .maybeSingle();

      if (existing?.student_id) {
        S.studentId = existing.student_id;
      } else {
        const { data } = await sb
          .from("student")
          .insert({ name: studentName, student_code: code, grade: "고등", srl_level: 5, srl_settings: {} })
          .select("student_id")
          .single();
        S.studentId = data.student_id;
      }
    } catch (e) {
      console.warn("DB student error", e);
    }
  }

  document.getElementById("home-title").textContent = `${S.problemSet}세트 문제`;
  document.getElementById("home-badge").textContent = `학생 ${code}`;

  go("home");
}

function logout() {
  S.studentCode = null;
  S.studentId = null;
  S.problems = [];
  S.attempts = {};
  go("login");
}

// ─── Problem List ────────────────────────────────────
async function loadProblems() {
  const list = document.getElementById("problem-list");
  list.innerHTML = '<div class="center-msg"><div class="spinner"></div></div>';

  try {
    // Supabase에서 문제 세트 로드
    const { data: problems, error } = await sb
      .from("field_problem")
      .select("*")
      .eq("problem_set", S.problemSet)
      .order("problem_order", { ascending: true });

    if (error) throw error;
    S.problems = problems || [];

    // 이 학생의 시도 기록 로드
    if (S.studentId) {
      const { data: attempts } = await sb
        .from("field_attempt")
        .select("*")
        .eq("student_id", S.studentId)
        .order("attempt_no", { ascending: true });

      S.attempts = {};
      (attempts || []).forEach(a => {
        if (!S.attempts[a.problem_id]) S.attempts[a.problem_id] = [];
        S.attempts[a.problem_id].push(a);
      });
    }

    renderProblemList();
  } catch (e) {
    console.error("문제 로드 실패:", e);
    list.innerHTML = `<div class="center-msg"><div class="error-text">문제를 불러올 수 없습니다.<br>${e.message}</div></div>`;
  }
}

function renderProblemList() {
  const list = document.getElementById("problem-list");
  if (!S.problems.length) {
    list.innerHTML = '<div class="center-msg"><div class="muted">배정된 문제가 없습니다.</div></div>';
    return;
  }

  let solved = 0;
  let html = "";

  S.problems.forEach((p, i) => {
    const attempts = S.attempts[p.problem_id] || [];
    const lastAttempt = attempts[attempts.length - 1];
    const isCorrect = lastAttempt?.is_correct === true;
    const attemptCount = attempts.length;

    if (isCorrect) solved++;

    let statusClass = "pending";
    let statusText = "미풀이";
    let statusIcon = "";

    if (isCorrect) {
      statusClass = "correct";
      statusText = "정답";
      statusIcon = "✓";
    } else if (attemptCount > 0) {
      statusClass = "retry";
      statusText = `${attemptCount}회 시도`;
      statusIcon = "↻";
    }

    html += `
      <div class="problem-card-item ${statusClass}" onclick="openProblem(${i})">
        <div class="problem-card-left">
          <div class="problem-card-num">${i + 1}</div>
          <div class="problem-card-info">
            <div class="problem-card-title">문제 ${p.problem_number || (i + 1)}</div>
            <div class="problem-card-sub">${statusText}${attemptCount > 0 ? ` · ${attemptCount}회` : ""}</div>
          </div>
        </div>
        <div class="problem-card-status ${statusClass}">
          ${statusIcon ? `<span>${statusIcon}</span>` : '<span class="arrow">›</span>'}
        </div>
      </div>`;
  });

  list.innerHTML = html;

  // 진행률 업데이트
  const total = S.problems.length;
  document.getElementById("progress-text").textContent = `${solved}/${total}`;
  document.getElementById("progress-fill").style.width = total > 0 ? `${(solved / total) * 100}%` : "0%";
}

// ─── Problem Detail ──────────────────────────────────
function openProblem(idx) {
  const p = S.problems[idx];
  if (!p) return;

  S.currentProblem = p;
  const attempts = S.attempts[p.problem_id] || [];
  S.currentAttempt = attempts.length;
  S.imageDataUrl = null;
  S.imageBase64 = null;
  S.hintRevealed = 0;
  S.lastGradingResult = null;

  document.getElementById("problem-nav-title").textContent = `문제 ${p.problem_number || (idx + 1)}`;
  document.getElementById("problem-number").textContent = `문제 ${p.problem_number || (idx + 1)}`;
  document.getElementById("problem-text").innerHTML = esc(p.problem_text);

  // 업로드 영역 초기화
  document.getElementById("solution-preview").style.display = "none";
  document.getElementById("solution-upload-area").style.display = "";
  document.getElementById("solution-file-input").value = "";

  go("problem");

  // KaTeX 렌더링
  renderAllMath(document.getElementById("problem-display"));
}

// ─── Solution Photo Upload ───────────────────────────
document.getElementById("solution-upload-area").addEventListener("click", () => {
  document.getElementById("solution-file-input").click();
});

document.getElementById("solution-file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (ev) => {
    S.imageDataUrl = ev.target.result;
    S.imageBase64 = ev.target.result.split(",")[1];
    document.getElementById("solution-preview-img").src = S.imageDataUrl;
    document.getElementById("solution-preview").style.display = "";
    document.getElementById("solution-upload-area").style.display = "none";
  };
  reader.readAsDataURL(file);
});

function retakePhoto() {
  S.imageDataUrl = null;
  S.imageBase64 = null;
  document.getElementById("solution-preview").style.display = "none";
  document.getElementById("solution-upload-area").style.display = "";
  document.getElementById("solution-file-input").value = "";
}

// ─── Submit Solution ─────────────────────────────────
async function submitSolution() {
  if (!S.imageBase64 || !S.currentProblem) return;

  go("processing");
  updateProcStep("ocr", "active");
  updateProcStep("grade", "");
  updateProcStep("hint", "");

  try {
    // 1) OCR
    const ocrResp = await fetch(API + "/ocr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: S.imageBase64, mime_type: "image/jpeg", mode: "solution" }),
    });
    const ocrData = await ocrResp.json();
    if (!ocrData.success) throw new Error(ocrData.error || "OCR 실패");

    const steps = ocrData.steps || (ocrData.gpt4o_result || {}).steps || [{ index: 1, text: ocrData.final_text }];

    updateProcStep("ocr", "done");
    updateProcStep("grade", "active");

    // 2) 채점
    const gradeResp = await fetch(API + "/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_text: S.currentProblem.problem_text,
        problem_latex: S.currentProblem.problem_text,
        solution_steps: steps.map(s => ({ index: s.index, text: s.text })),
        correct_answer: S.currentProblem.answer,
      }),
    });
    const gradeData = await gradeResp.json();
    if (!gradeData.success) throw new Error(gradeData.error || "채점 실패");

    updateProcStep("grade", "done");
    updateProcStep("hint", "done");

    S.lastGradingResult = gradeData;
    S.lastGradingResult._ocrSteps = steps;
    S.currentAttempt++;

    // 3) DB 저장
    await saveAttempt(gradeData, steps);

    // 4) 결과 화면
    renderResult(gradeData);
    go("result");

  } catch (e) {
    console.error("제출 실패:", e);
    go("problem");
    alert("제출 중 오류가 발생했습니다: " + e.message);
  }
}

function updateProcStep(step, state) {
  const el = document.getElementById("proc-" + step);
  if (!el) return;
  const dot = el.querySelector(".proc-dot");
  dot.className = "proc-dot";
  if (state === "active") dot.classList.add("active");
  if (state === "done") dot.classList.add("done");
}

// ─── Save Attempt to DB ─────────────────────────────
async function saveAttempt(gradeData, ocrSteps) {
  if (!sb || !S.studentId || !S.currentProblem) return;

  try {
    await sb.from("field_attempt").insert({
      student_id: S.studentId,
      problem_id: S.currentProblem.problem_id,
      attempt_no: S.currentAttempt,
      ocr_steps: ocrSteps,
      is_correct: !!gradeData.is_correct,
      error_step_index: gradeData.error_step_index || null,
      error_category: gradeData.error_category || null,
      error_detail: gradeData.error_detail || "",
      grading_json: gradeData,
      image_base64: S.imageBase64,
    });

    // attempts 캐시 업데이트
    const pid = S.currentProblem.problem_id;
    if (!S.attempts[pid]) S.attempts[pid] = [];
    S.attempts[pid].push({
      attempt_no: S.currentAttempt,
      is_correct: !!gradeData.is_correct,
    });
  } catch (e) {
    console.warn("DB attempt save error:", e);
  }
}

// ─── Render Result ───────────────────────────────────
function renderResult(r) {
  const isCorrect = !!r.is_correct;
  let html = "";

  // 배너
  html += `<div class="banner ${isCorrect ? "correct" : "wrong"}">
    <div class="banner-icon">${isCorrect ? "🎉" : "🔍"}</div>
    <div class="banner-title">${isCorrect ? "정답입니다!" : "다시 확인해보세요"}</div>
    <div class="banner-text">${isCorrect
      ? "잘 풀었습니다! 모든 풀이 단계가 올바릅니다."
      : (r.ai_explanation || "풀이에서 확인이 필요한 부분이 있습니다.")}</div>
    <div class="attempt-info">시도 ${S.currentAttempt}회</div>
  </div>`;

  // 단계별 판정
  if (r.steps && r.steps.length > 0) {
    html += `<div class="card"><div class="card-title">단계별 판정</div>`;
    r.steps.forEach(step => {
      const color = step.status === "ok" ? "var(--ok)" : step.status === "wrong" ? "var(--accent)" : "var(--ink3)";
      const label = step.status === "ok" ? "맞음" : step.status === "wrong" ? "오답" : "영향받음";
      html += `<div class="step-row">
        <div class="status-dot" style="background:${color}"></div>
        <div style="flex:1">
          <div class="step-status" style="color:${color}">Step ${step.index} · ${label}</div>
          <div class="math-render">${esc(step.text)}</div>
          ${step.explanation ? `<div class="step-explanation">${esc(step.explanation)}</div>` : ""}
        </div>
      </div>`;
    });
    html += `</div>`;
  }

  // 힌트 (오답일 때만)
  if (!isCorrect) {
    const hints = [
      r.hint_direction || "힌트가 없습니다.",
      r.hint_concept || "힌트가 없습니다.",
      r.hint_near_answer || "힌트가 없습니다.",
    ];
    window._hints = hints;

    html += `<div class="card" id="hint-card">
      <div class="card-title">힌트</div>
      <div class="hint-tabs">
        <button class="hint-tab active" id="hint-tab-0" onclick="revealHint(0)">1단계<br><small>방향</small></button>
        <button class="hint-tab locked" id="hint-tab-1" onclick="revealHint(1)">2단계<br><small>개념</small></button>
        <button class="hint-tab locked" id="hint-tab-2" onclick="revealHint(2)">3단계<br><small>근접</small></button>
      </div>
      <div class="hint-body" id="hint-body">${esc(hints[0])}</div>
    </div>`;

    // 재시도 + 해설보기 버튼
    html += `<div class="btn-row">
      <button class="btn-secondary" onclick="viewSolutionFromResult()">해설 보기</button>
      <button class="btn-primary" onclick="retryProblem()">다시 풀기</button>
    </div>`;
  } else {
    // 정답이면 다음 문제 또는 목록
    html += `<div class="btn-row">
      <button class="btn-secondary" onclick="viewSolutionFromResult()">해설 보기</button>
      <button class="btn-primary" onclick="go('home')">문제 목록</button>
    </div>`;
  }

  document.getElementById("result-content").innerHTML = html;
  renderAllMath(document.getElementById("result-content"));

  // 힌트 첫 단계 자동 공개 + 로깅
  S.hintRevealed = 1;
  logHintEvent(1);
}

// ─── Hint System ─────────────────────────────────────
function revealHint(idx) {
  if (idx > S.hintRevealed) {
    // 순서대로만 열 수 있음
    if (idx !== S.hintRevealed) return;
    S.hintRevealed = idx + 1;

    // 탭 잠금 해제
    const tab = document.getElementById(`hint-tab-${idx}`);
    if (tab) tab.classList.remove("locked");

    // 로깅
    logHintEvent(idx + 1);
  }

  // 모든 탭 비활성화 후 현재 활성화
  document.querySelectorAll(".hint-tab").forEach(t => t.classList.remove("active"));
  const activeTab = document.getElementById(`hint-tab-${idx}`);
  if (activeTab && !activeTab.classList.contains("locked")) {
    activeTab.classList.add("active");
  }

  // 힌트 내용 표시
  const body = document.getElementById("hint-body");
  if (body && window._hints) {
    if (idx < S.hintRevealed) {
      body.textContent = window._hints[idx];
    } else {
      body.innerHTML = '<span class="muted">이전 단계의 힌트를 먼저 확인하세요</span>';
    }
  }
}

async function logHintEvent(level) {
  if (!sb || !S.studentId || !S.currentProblem) return;
  try {
    await sb.from("field_hint_log").insert({
      student_id: S.studentId,
      problem_id: S.currentProblem.problem_id,
      attempt_no: S.currentAttempt,
      hint_level: level,
    });
  } catch (e) {
    console.warn("Hint log error:", e);
  }
}

// ─── Retry ───────────────────────────────────────────
function retryProblem() {
  if (!S.currentProblem) { go("home"); return; }
  // 문제 상세로 돌아가기 (사진 초기화)
  const idx = S.problems.findIndex(p => p.problem_id === S.currentProblem.problem_id);
  if (idx >= 0) openProblem(idx);
  else go("home");
}

// ─── Solution View ───────────────────────────────────
async function viewSolutionFromResult() {
  go("solution");
  show("solution-loading");
  hide("solution-content");

  try {
    const resp = await fetch(API + "/solution", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_text: S.currentProblem.problem_text,
        problem_latex: S.currentProblem.problem_text,
        correct_answer: S.currentProblem.answer,
      }),
    });
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "해설 생성 실패");

    hide("solution-loading");
    show("solution-content");
    renderSolution(data);
  } catch (e) {
    hide("solution-loading");
    show("solution-content");
    document.getElementById("solution-content").innerHTML =
      `<div class="center-msg"><h2>해설 생성 실패</h2><div class="error-text">${esc(e.message)}</div></div>`;
  }
}

function renderSolution(data) {
  let html = `<div class="problem-card-display"><div class="label">문제</div><div class="math-render">${esc(S.currentProblem.problem_text)}</div></div>`;

  html += `<div class="meta-row">`;
  if (data.method_type) html += `<div class="chip">${esc(data.method_type)}</div>`;
  if (data.answer) html += `<div class="chip accent">정답 ${esc(String(data.answer))}</div>`;
  html += `</div>`;

  html += `<div class="card"><div class="card-title">단계별 해설</div>`;
  (data.steps || []).forEach(step => {
    html += `<div class="sol-step">
      <div class="sol-step-title">Step ${step.step}. ${esc(step.title)}</div>
      <div class="math-render">${esc(step.content)}</div>
      ${step.formula ? `<div class="formula-box math-render">${esc(step.formula)}</div>` : ""}
    </div>`;
  });
  html += `</div>`;

  html += `<div class="btn-row"><button class="btn-primary" onclick="go('home')">문제 목록</button></div>`;

  document.getElementById("solution-content").innerHTML = html;
  renderAllMath(document.getElementById("solution-content"));
}

// ─── KaTeX rendering ─────────────────────────────────
function renderAllMath(container) {
  if (!container) return;
  try {
    renderMathInElement(container, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
      throwOnError: false,
      strict: false,
    });
  } catch (e) { /* ignore */ }
}

// ─── Utilities ───────────────────────────────────────
function show(id) { const el = document.getElementById(id); if (el) el.style.display = ""; }
function hide(id) { const el = document.getElementById(id); if (el) el.style.display = "none"; }
function esc(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }
