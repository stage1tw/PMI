import os
import tempfile
from pathlib import Path

# pmi.storage 가 import 되기 전에 테스트 전용 DB 로 분리 (실제 data/pmi.db 오염 방지).
# ECOS 캐시가 비어 있어야 샘플 거시지표(CPI 2.1 / PPI 1.4)가 쓰이므로 매 세션 새 파일.
_tmp = Path(tempfile.mkdtemp(prefix="pmi-test-"))
os.environ["PMI_DB_PATH"] = str(_tmp / "unit.db")
