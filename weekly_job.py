"""주간 배치: 데이터 수집 → 전 품목 리포트 생성 → data/pmi.db 저장.

GitHub Actions(.github/workflows/weekly.yml) 또는 서버 cron 에서 실행:
    python scripts/weekly_job.py [--no-web]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pmi import analyzer, collectors, report, storage  # noqa: E402
from pmi.config import CATEGORIES  # noqa: E402


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    collectors.collect_all(os.environ.get("ECOS_API_KEY"), os.environ.get("DATA_GO_KR_KEY"))
    for key, cat in CATEGORIES.items():
        try:
            r, q, sources, ai_used = analyzer.build_report(key, api_key, "--no-web" not in sys.argv, progress=print)
            payload = {"report": r.model_dump(), "quant": q, "sources": sources}
            storage.save_report(key, q["index"], ai_used, payload, report.to_markdown(payload["report"], q, sources, ai_used))
            print(f"[OK] {cat.name}: 압력지수 {q['index']} ({q['level']})")
        except Exception as e:
            print(f"[FAIL] {cat.name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
