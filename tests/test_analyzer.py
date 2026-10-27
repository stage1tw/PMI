"""PRD §5 F3 압력지수 산식 단위 테스트 (시나리오 8)."""
import pytest

from pmi import analyzer, collectors, report
from pmi.config import CATEGORIES, level_of


def test_ndt_matches_hand_calculation():
    # 손계산 (PRD 산식, 샘플 거시지표 CPI 2.1 / PPI 1.4):
    #   비파괴시험공 281,000 / 265,600 - 1 = +5.80%,  최저임금 10,320 / 10,030 - 1 = +2.89%
    #   노무비 = 0.6×5.80 + 0.4×2.89 = 4.64
    #   예상 = 0.72×4.64 + 0.08×1.4 + 0.20×2.1 = 3.34 + 0.11 + 0.42 = 3.87%
    #   법규리스크 = min(15, 4 + 2×3) = 10, 공급집중도 = 11
    #   지수 = 3.87 / 8 × 70 + 10 + 11 = 54.86 → 54.9 (보통)
    q = analyzer.compute_pressure("ndt")
    assert q["macro"]["is_sample"]
    assert q["rates"] == {"labor": 4.64, "material": 1.4, "expense": 2.1}
    assert q["contrib"] == {"labor": 3.34, "material": 0.11, "expense": 0.42}
    assert q["expected"] == pytest.approx(3.87)
    assert q["regulation_risk"] == 10
    assert q["index"] == pytest.approx(54.9)
    assert q["level"] == "보통"


@pytest.mark.parametrize("key", list(CATEGORIES))
def test_formula_holds_for_every_category(key):
    q = analyzer.compute_pressure(key)
    cat = CATEGORIES[key]
    expected = sum(cat.cost_mix[k] * q["rates"][k] for k in cat.cost_mix)
    assert q["base_expected"] == pytest.approx(expected, abs=0.02)
    idx = q["expected"] / 8 * 70 + q["regulation_risk"] + cat.supply_concentration
    assert q["index"] == pytest.approx(min(100, max(0, idx)), abs=0.06)
    assert q["level"] == level_of(q["index"])[0]


@pytest.mark.parametrize("value,label", [
    (0, "낮음"), (29.9, "낮음"), (30, "보통"), (54.9, "보통"), (55, "높음"),
    (74.9, "높음"), (75, "매우 높음"), (100, "매우 높음"),
])
def test_level_boundaries(value, label):
    assert level_of(value)[0] == label


def test_ai_adjustment_and_regulation_risk_are_clipped():
    base = analyzer.compute_pressure("ndt")
    q = analyzer.compute_pressure("ndt", regulation_risk=99, ai_adjustment_pp=9.0)
    assert q["ai_adjustment_pp"] == 2.0
    assert q["expected"] == pytest.approx(base["base_expected"] + 2.0)
    assert q["regulation_risk"] == 15
    q = analyzer.compute_pressure("ndt", regulation_risk=-5, ai_adjustment_pp=-9.0)
    assert q["ai_adjustment_pp"] == -2.0 and q["regulation_risk"] == 0


@pytest.mark.parametrize("macro_yoy,bound", [(80.0, 100), (-80.0, 0)])
def test_index_clipped_to_0_100(monkeypatch, macro_yoy, bound):
    fake = {"cpi_yoy": macro_yoy, "ppi_yoy": macro_yoy, "base_rate": 2.5, "is_sample": True}
    monkeypatch.setattr(collectors, "macro_snapshot", lambda: fake)
    monkeypatch.setitem(collectors.WAGE_SAMPLE, "보통인부", {2025: 100, 2026: 100 * (1 + macro_yoy / 100)})
    q = analyzer.compute_pressure("construction", regulation_risk=0 if bound == 0 else 15)
    assert q["index"] == bound


def test_rule_based_report_follows_template():
    r, q = analyzer.rule_based_report("ndt", [], [])
    assert r.expected_increase_low < q["expected"] < r.expected_increase_high
    md = report.to_markdown(r.model_dump(), q, [], False)
    for section in ["종합 판단", "핵심 지표", "관련 법규", "공급시장", "구매전략 제안", "원가 분해", "참고자료"]:
        assert section in md
    html = report.to_html(md, "t")
    assert 'class="cover"' in html and "<table>" in html
