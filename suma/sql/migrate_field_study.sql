-- ═══════════════════════════════════════════════════
-- 현장연구용 마이그레이션 (기존 테이블 유지, 신규 추가)
-- Supabase SQL Editor에서 실행
-- ═══════════════════════════════════════════════════

-- 1. student 테이블에 student_code 컬럼 추가
ALTER TABLE student ADD COLUMN IF NOT EXISTS student_code INT UNIQUE;

-- 2. 현장연구 문제
CREATE TABLE IF NOT EXISTS field_problem (
  problem_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  problem_set    TEXT NOT NULL CHECK (problem_set IN ('P', 'Q')),
  problem_number INT  NOT NULL,
  problem_order  INT  NOT NULL DEFAULT 0,
  problem_text   TEXT NOT NULL,
  answer         TEXT NOT NULL DEFAULT '',
  solution_text  TEXT,
  source         TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(problem_set, problem_number)
);

-- 3. 현장연구 시도 기록
CREATE TABLE IF NOT EXISTS field_attempt (
  attempt_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id     UUID NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
  problem_id     UUID NOT NULL REFERENCES field_problem(problem_id) ON DELETE CASCADE,
  attempt_no     INT  NOT NULL DEFAULT 1,
  ocr_steps      JSONB NOT NULL DEFAULT '[]',
  is_correct     BOOLEAN NOT NULL DEFAULT FALSE,
  error_step_index INT,
  error_category TEXT,
  error_detail   TEXT NOT NULL DEFAULT '',
  grading_json   JSONB NOT NULL DEFAULT '{}',
  image_base64   TEXT,
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
  hint_level   INT  NOT NULL CHECK (hint_level IN (1, 2, 3)),
  revealed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hint_student ON field_hint_log(student_id);

-- 5. RLS
ALTER TABLE field_problem  ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_attempt  ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_hint_log ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'anon_all_problem') THEN
    CREATE POLICY "anon_all_problem" ON field_problem FOR ALL USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'anon_all_attempt') THEN
    CREATE POLICY "anon_all_attempt" ON field_attempt FOR ALL USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'anon_all_hint') THEN
    CREATE POLICY "anon_all_hint" ON field_hint_log FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

-- 6. 샘플 문제 삽입 (P세트, Q세트 각 5문제씩 — 실제 문제로 교체 필요)
-- INSERT INTO field_problem (problem_set, problem_number, problem_order, problem_text, answer, source) VALUES
-- ('P', 1, 1, '서로 다른 5개의 공에서 3개를 택하는 조합의 수를 구하시오.', '10', '예시'),
-- ('P', 2, 2, '...', '...', '예시'),
-- ('Q', 1, 1, '...', '...', '예시');
