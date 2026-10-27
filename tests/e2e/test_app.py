"""PRD §10 수용기준 + §5 기능 요구사항 E2E 검증.

실행: pytest tests/e2e  (스크린샷: tests/e2e/screenshots/)
"""
import pytest
from playwright.sync_api import expect
from conftest import REAL_ANTHROPIC_KEY, SHOTS, generate_report, go, select, wait_idle

from pmi.config import CATEGORIES

MENUS = ["대시보드", "품목 리포트", "AI 챗봇", "시장 지표", "리포트 아카이브", "수집 현황·설정"]


# 1. 기동 · 수용기준 2 (키 없이 실행, 샘플 명시)
def test_starts_without_keys_and_flags_sample_data(app):
    nav = app.locator('[data-testid="stSidebar"] [data-testid="stRadioOption"]')
    assert nav.all_inner_texts() == MENUS
    expect(app.locator(".pmi-hero .pmi-badge", has_text="샘플 데이터 포함")).to_be_visible()
    expect(app.locator('[data-testid="stSidebar"] .pmi-badge', has_text="Claude 분석 비활성")).to_be_visible()
    assert app.locator('[data-testid="stException"]').count() == 0


# 2. 대시보드 · F4-1, 수용기준 1
def test_dashboard_kpis_and_all_categories(app):
    kpis = app.locator(".pmi-kpi")
    assert kpis.count() == 5
    for i in range(5):  # 값 잘림(…) 없음
        assert kpis.nth(i).locator(".value").evaluate("e => e.scrollWidth <= e.clientWidth")
    expect(app.locator(".js-plotly-plot")).to_have_count(1)
    chart = app.locator(".js-plotly-plot").first.inner_text()
    for cat in CATEGORIES.values():
        assert cat.name in chart, f"{cat.name} 압력지수 막대 누락"
    assert app.locator('[data-testid="stDataFrame"]').count() == 1


# 3. 품목 리포트 · F3, F4-2, 수용기준 1 (8개 품목 각각)
@pytest.mark.parametrize("key", list(CATEGORIES))
def test_report_generation_per_category(app, key):
    name = CATEGORIES[key].name
    go(app, "품목 리포트")
    generate_report(app, name)
    assert app.get_by_text("완료").first.is_visible()
    summary = app.locator(".pmi-summary")
    text = summary.inner_text()
    assert "/ 100" in text and "~" in text and "%" in text
    assert app.locator(".pmi-headline").inner_text().startswith(name)
    assert app.locator('[data-testid="stDataFrame"]').count() >= 1  # 핵심 지표 표
    assert app.locator(".pmi-box", has_text="구매전략 제안").locator("li").count() >= 1
    assert app.locator('[data-testid="stException"]').count() == 0


# 4. 다운로드 · F5, 수용기준 4
def test_report_downloads_follow_template(app, tmp_path):
    go(app, "품목 리포트")
    select(app, "품목", CATEGORIES["ndt"].name)
    with app.expect_download() as d:
        app.get_by_role("button", name="Markdown").click()
    md = (tmp_path / "r.md")
    d.value.save_as(md)
    text = md.read_text(encoding="utf-8")
    for section in ["종합 판단", "핵심 지표", "구매전략 제안", "참고자료"]:
        assert section in text, f"Markdown 리포트에 '{section}' 없음"
    with app.expect_download() as d:
        app.get_by_role("button", name="HTML").click()
    html = (tmp_path / "r.html")
    d.value.save_as(html)
    body = html.read_text(encoding="utf-8")
    assert body.startswith("<!doctype html>") and 'class="cover"' in body and "구매전략 제안" in body


# 5. 시장 지표 · F4-3
def test_indicators_charts_and_csv(app, tmp_path):
    go(app, "시장 지표")
    expect(app.locator(".js-plotly-plot")).to_have_count(2)
    app.get_by_text("원본 데이터").click()
    with app.expect_download() as d:
        app.get_by_role("button", name="최저임금 CSV").click()
    f = tmp_path / "mw.csv"
    d.value.save_as(f)
    lines = f.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "year,wage,yoy" and len(lines) >= 8


# 6. 리포트 아카이브 · F4-4 (이력 + 주차별 비교)
def test_archive_lists_generated_reports(app):
    go(app, "품목 리포트")
    generate_report(app, CATEGORIES["cleaning"].name)
    generate_report(app, CATEGORIES["cleaning"].name)
    go(app, "리포트 아카이브")
    select(app, "품목", CATEGORIES["cleaning"].name)
    expect(app.locator(".js-plotly-plot")).to_contain_text("압력지수 추이")
    prev = app.locator(".pmi-kpi", has_text="직전 대비")
    expect(prev.locator(".value")).to_have_text("+0.0p")  # 같은 입력 → 변화 없음
    expect(app.locator('[data-testid="stSelectbox"]', has_text="리포트 열기")).to_be_visible()
    expect(app.get_by_text("외주용역 시장동향 Report").first).to_be_visible()
    expect(app.get_by_role("button", name="HTML")).to_be_visible()


# 7. 수집 현황 · F2-7, F4-5, 수용기준 5
def test_collection_status_and_manual_run(app):
    go(app, "수집 현황·설정")
    app.get_by_role("button", name="지금 수집 실행").click()
    app.get_by_text("수집 완료").wait_for(timeout=120_000)
    cards = app.locator(".pmi-kpi")
    assert cards.count() == 4
    assert all(v == "미설정" for v in cards.locator(".value").all_inner_texts())
    assert app.locator('[data-testid="stDataFrame"]').count() == 2


# 9. 실패 경로 — 잘못된 Anthropic 키
def test_invalid_anthropic_key_shows_error_without_crash(app):
    key_input = app.locator('[data-testid="stSidebar"] input[type="password"]')
    key_input.fill("sk-ant-invalid-key-for-test")
    key_input.press("Enter")
    wait_idle(app)
    expect(app.locator('[data-testid="stSidebar"] .pmi-badge', has_text="Claude 분석 활성")).to_be_visible()
    go(app, "품목 리포트")
    generate_report(app, CATEGORIES["ndt"].name)
    expect(app.get_by_text("생성 실패").first).to_be_visible()
    expect(app.locator('[data-testid="stAlertContentError"]').first).to_contain_text("API 키가 유효하지 않습니다")
    assert app.locator('[data-testid="stAlertContentError"]').count() >= 1
    assert app.locator('[data-testid="stException"]').count() == 0
    go(app, "대시보드")  # 이후에도 앱이 정상 동작
    assert app.locator(".pmi-kpi").count() == 5


# 10. 반응형 — 가로 스크롤·텍스트 잘림 없음
@pytest.mark.parametrize("width", [1440, 1024, 390])
def test_responsive_layout(app, width):
    app.set_viewport_size({"width": width, "height": 900})
    SHOTS.mkdir(exist_ok=True)
    for i, menu in enumerate(MENUS):
        if width < 700:
            app.locator('[data-testid="stExpandSidebarButton"]').click()
        go(app, menu)
        if width < 700:
            app.keyboard.press("Escape")
            app.mouse.click(width - 10, 500)
            app.wait_for_timeout(500)
        assert not app.evaluate("document.documentElement.scrollWidth > window.innerWidth"), f"{menu} @{width}px 가로 스크롤"
        clipped = app.evaluate("""[...document.querySelectorAll('.pmi-kpi .value, .pmi-summary .range, .pmi-hero h1')]
            .filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent)""")
        assert not clipped, f"{menu} @{width}px 텍스트 잘림: {clipped}"
        app.screenshot(path=str(SHOTS / f"{width}_{i}_{menu.replace('·', '_')}.png"), full_page=True)


# 11. 실제 Claude 리포트 (ANTHROPIC_API_KEY 가 있을 때만)
@pytest.mark.skipif(not REAL_ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY 미설정 — 실제 AI 리포트 검증 생략")
def test_ai_report_has_sources(app):
    key_input = app.locator('[data-testid="stSidebar"] input[type="password"]')
    key_input.fill(REAL_ANTHROPIC_KEY)
    key_input.press("Enter")
    wait_idle(app)
    go(app, "품목 리포트")
    generate_report(app, CATEGORIES["ndt"].name)
    expect(app.get_by_text("Claude AI 분석").first).to_be_visible()
    sources = app.locator('[data-testid="stExpander"]', has_text="출처")
    assert sources.count() >= 1 and int(sources.inner_text().split("출처")[1].split("건")[0]) >= 1
