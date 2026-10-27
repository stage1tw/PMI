"""E2E 공통 픽스처: 격리된 DB·키 없는 환경으로 Streamlit 서버를 띄운다."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(__file__).parent / "screenshots"
KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_MODEL", "ECOS_API_KEY", "DATA_GO_KR_KEY"]
# .env 로드 전에 테스트 프로세스의 실제 키를 보관 (시나리오 11 에서만 사용)
REAL_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def app_url():
    port = _free_port()
    db = Path(tempfile.mkdtemp(prefix="pmi-e2e-")) / "e2e.db"
    # 빈 문자열로 덮어 load_dotenv() 가 .env 값을 주입하지 못하게 한다 (키 없는 상태 재현).
    env = {**os.environ, "PMI_DB_PATH": str(db), **{k: "" for k in KEYS}}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port),
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if urllib.request.urlopen(f"{url}/_stcore/health", timeout=1).read() == b"ok":
                break
        except OSError:
            time.sleep(1)
    else:
        proc.kill()
        pytest.fail("Streamlit 서버가 60초 내에 기동되지 않음")
    yield url
    proc.terminate()
    proc.wait(10)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1440, "height": 900}, "accept_downloads": True}


def wait_idle(page, timeout=90_000):
    """Streamlit 재실행이 끝날 때까지 대기 (실행 중 표시 위젯이 사라질 때까지)."""
    page.wait_for_timeout(600)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=timeout)
    page.wait_for_timeout(400)


@pytest.fixture
def app(page, app_url):
    page.set_default_timeout(30_000)
    page.goto(app_url)
    # 첫 실행에는 시장 데이터 수집(RSS)이 돌아 시간이 걸린다
    page.wait_for_selector(".pmi-hero", timeout=120_000)
    wait_idle(page)
    return page


def go(page, menu):
    page.locator('[data-testid="stSidebar"] [data-testid="stRadioOption"]').filter(has_text=menu).first.click()
    wait_idle(page)
    page.wait_for_selector(f'.pmi-hero h1:has-text("{menu.split()[0]}")')


def select(page, label, option):
    box = page.locator('[data-testid="stSelectbox"]').filter(has_text=label).first
    box.click()
    page.get_by_role("option", name=option, exact=True).click()
    wait_idle(page)


def generate_report(page, category):
    select(page, "품목", category)
    page.get_by_role("button", name="리포트 생성").click()
    page.wait_for_selector('[data-testid="stExpander"]:has-text("완료"), [data-testid="stExpander"]:has-text("생성 실패")',
                           timeout=180_000)
    wait_idle(page)
