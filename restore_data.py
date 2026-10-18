"""
DB 복구 스크립트 — 로컬에서 실행
사용법:
  python restore_data.py field_attempt_rows.json field_hint_log_rows.json

1) 먼저 /api/seed 호출하여 문제 테이블 복구 (원본 UUID 유지)
2) attempt 데이터 복구 (배치로 나눠서 전송, 이미지 포함)
3) hint_log 데이터 복구
"""
import json, sys, requests

BASE = "https://suma-09-production.up.railway.app"
BATCH_SIZE = 3  # attempt는 이미지 포함이라 작게

def main():
    if len(sys.argv) < 3:
        print("Usage: python restore_data.py <attempt_json> <hint_log_json>")
        sys.exit(1)

    attempt_file = sys.argv[1]
    hint_file = sys.argv[2]

    # Step 1: Seed problems (원본 UUID 복구)
    print("[1/3] Seeding problems with original UUIDs...")
    r = requests.post(f"{BASE}/api/seed")
    print(f"  → {r.json()}")

    # Step 2: Restore attempts (배치)
    print(f"\n[2/3] Restoring field_attempt...")
    with open(attempt_file, encoding="utf-8") as f:
        attempts = json.load(f)

    for i in range(0, len(attempts), BATCH_SIZE):
        batch = attempts[i:i+BATCH_SIZE]
        r = requests.post(f"{BASE}/api/restore",
                          json={"table": "field_attempt", "rows": batch},
                          timeout=120)
        result = r.json()
        print(f"  batch {i//BATCH_SIZE + 1}: {len(batch)} rows → {result.get('success')}")
        if not result.get("success"):
            print(f"  ERROR: {result}")
            return

    # Step 3: Restore hint_log
    print(f"\n[3/3] Restoring field_hint_log...")
    with open(hint_file, encoding="utf-8") as f:
        hints = json.load(f)

    r = requests.post(f"{BASE}/api/restore",
                      json={"table": "field_hint_log", "rows": hints},
                      timeout=60)
    result = r.json()
    print(f"  → {len(hints)} rows → {result}")

    print("\nDone!")

if __name__ == "__main__":
    main()
