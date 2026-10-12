-- ═══════════════════════════════════════════════════
-- suma Supabase Schema — 현장연구용 (2026-10)
-- ═══════════════════════════════════════════════════

-- 1. 학생
CREATE TABLE IF NOT EXISTS student (
  student_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_code INT  NOT NULL UNIQUE,             -- 1~4
  name         TEXT NOT NULL,
  grade        TEXT NOT NULL DEFAULT '고등',
  srl_level    INT  NOT NULL DEFAULT 5,
  srl_settings JSONB NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. 현장연구 문제 (사전 등록)
CREATE TABLE IF NOT EXISTS field_problem (
  problem_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  problem_set    TEXT NOT NULL CHECK (problem_set IN ('P', 'Q')),
  problem_number INT  NOT NULL,                   -- 세트 내 문제번호
  problem_order  INT  NOT NULL DEFAULT 0,         -- 정렬 순서
  problem_text   TEXT NOT NULL,                   -- 문제 텍스트 (KaTeX 포함 가능)
  answer         TEXT NOT NULL DEFAULT '',        -- 정답
  solution_text  TEXT,                            -- 모범 풀이 (선택)
  source         TEXT,                            -- 출처 (교육청/평가원 등)
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(problem_set, problem_number)
);

-- 3. 현장연구 시도 기록
CREATE TABLE IF NOT EXISTS field_attempt (
  attempt_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id     UUID NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
  problem_id     UUID NOT NULL REFERENCES field_problem(problem_id) ON DELETE CASCADE,
  attempt_no     INT  NOT NULL DEFAULT 1,
  ocr_steps      JSONB NOT NULL DEFAULT '[]',     -- [{index, text}]
  is_correct     BOOLEAN NOT NULL DEFAULT FALSE,
  error_step_index INT,
  error_category TEXT,
  error_detail   TEXT NOT NULL DEFAULT '',
  grading_json   JSONB NOT NULL DEFAULT '{}',     -- 전체 채점 결과
  image_base64   TEXT,                            -- 풀이 사진 (base64)
  submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attempt_student ON field_attempt(student_id);
CREATE INDEX IF NOT EXISTS idx_attempt_problem ON field_attempt(problem_id);

-- 4. 힌트 사용 로그
CREATE TABLE IF NOT EXISTS field_hint_log (
  hint_log_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id   UUID NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
  problem_id   UUID NOT NULL REFERENCES field_problem(problem_id) ON DELETE CASCADE,
  attempt_no   INT  NOT NULL DEFAULT 1,
  hint_level   INT  NOT NULL CHECK (hint_level IN (1, 2, 3)),  -- 1=방향, 2=개념, 3=근접
  revealed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hint_student ON field_hint_log(student_id);

-- ─── RLS ───
ALTER TABLE student          ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_problem    ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_attempt    ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_hint_log   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_all_student"   ON student         FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_problem"   ON field_problem    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_attempt"   ON field_attempt    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_hint"      ON field_hint_log   FOR ALL USING (true) WITH CHECK (true);
