-- ═══════════════════════════════════════════════════
-- suma Supabase Schema
-- ═══════════════════════════════════════════════════

-- 1. 학생
CREATE TABLE IF NOT EXISTS student (
  student_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  grade        TEXT NOT NULL DEFAULT '고등',
  srl_level    INT  NOT NULL DEFAULT 5,
  srl_settings JSONB NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. 업로드 문제
CREATE TABLE IF NOT EXISTS student_upload_problem (
  upload_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id          UUID NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
  upload_problem_code TEXT NOT NULL UNIQUE,
  matched_main_id     UUID,
  ocr_text            TEXT NOT NULL DEFAULT '',
  match_status        TEXT NOT NULL DEFAULT 'new'
                      CHECK (match_status IN ('matched_main','matched_upload','new')),
  uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_upload_student ON student_upload_problem(student_id);

-- 3. 손글씨 풀이
CREATE TABLE IF NOT EXISTS handwriting_solution (
  hw_solution_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id          UUID NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
  main_problem_id     UUID,
  upload_problem_code TEXT,
  gen_problem_id      UUID,
  problem_source_type TEXT NOT NULL DEFAULT 'upload'
                      CHECK (problem_source_type IN ('main','upload','generated')),
  ocr_steps           JSONB NOT NULL DEFAULT '[]',
  is_correct          BOOLEAN NOT NULL DEFAULT FALSE,
  error_step_index    INT,
  submitted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hw_student ON handwriting_solution(student_id);
CREATE INDEX IF NOT EXISTS idx_hw_upload  ON handwriting_solution(upload_problem_code);

-- 4. 오류 진단
CREATE TABLE IF NOT EXISTS error_diagnosis (
  diagnosis_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hw_solution_id UUID NOT NULL REFERENCES handwriting_solution(hw_solution_id) ON DELETE CASCADE,
  error_step     INT  NOT NULL,
  error_category TEXT NOT NULL DEFAULT 'calculation_error'
                 CHECK (error_category IN ('calculation_error','wrong_concept','concept_missing','approach_failure')),
  error_detail   TEXT NOT NULL DEFAULT '',
  ai_explanation TEXT NOT NULL DEFAULT '',
  confidence     REAL NOT NULL DEFAULT 0.0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_diag_hw ON error_diagnosis(hw_solution_id);

-- ─── RLS (Row Level Security) ───
-- 기본 anon 접근 허용 (프로토타입용, 프로덕션에서는 auth 추가 필요)
ALTER TABLE student                ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_upload_problem ENABLE ROW LEVEL SECURITY;
ALTER TABLE handwriting_solution   ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_diagnosis        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_all_student"   ON student                FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_upload"    ON student_upload_problem  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_hw"        ON handwriting_solution    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_diagnosis" ON error_diagnosis         FOR ALL USING (true) WITH CHECK (true);
