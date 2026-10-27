"""원가상승 압력지수(규칙 기반) + Claude 시장분석.

1) compute_pressure(): 수집 지표만으로 계산하는 설명 가능한 정량 지수 (AI 없이도 동작)
2) research(): Claude web_search 로 시장동향·법규·공급사 뉴스 수집 (출처 포함)
3) analyze(): 정량 지표 + 리서치 + 뉴스를 종합해 구조화된 리포트(MarketReport) 생성
"""
from datetime import date
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from . import collectors, storage
from .config import CATEGORIES, MINIMUM_WAGE, MODEL, SOURCES, level_of

FALLBACK_BETA = "server-side-fallback-2026-07-01"


# ---------- 구조화 출력 스키마 ----------

class KeyItem(BaseModel):
    label: str = Field(description="지표명. 예: 'NDT 검사원 인건비'")
    value: str = Field(description="값. 예: '전년 대비 +5.8%'")
    detail: str = Field(description="한두 문장 설명")
    source: str = Field(description="출처 기관명 또는 URL. 없으면 '추정'")
    confidence: Literal["high", "medium", "low"]


class MarketReport(BaseModel):
    headline: str = Field(description="한 줄 종합 판단")
    expected_increase_low: float = Field(description="다음 입찰 예상 단가 인상률 하단(%)")
    expected_increase_high: float = Field(description="다음 입찰 예상 단가 인상률 상단(%)")
    ai_adjustment_pp: float = Field(description="정량 예상치 대비 정성 조정폭(%p), -2~+2")
    adjustment_reason: str
    regulation_risk: int = Field(description="법규 리스크 점수 0~15")
    key_items: list[KeyItem] = Field(description="인건비, 최저임금, 물가 등 핵심 지표")
    market_trends: list[str] = Field(description="최근 시장동향")
    regulations: list[str] = Field(description="관련 법규 개정·검토 사항 (출처 포함)")
    supply_market: list[str] = Field(description="공급시장 변화: 신규/이탈 업체, 인력 수급, M&A 등")
    strategies: list[str] = Field(description="구매전략 제안 (실행 가능한 문장)")
    negotiation_points: list[str] = Field(description="공급사 인상 요구 시 협상 논리")
    risks: list[str]


# ---------- 정량 지수 ----------

def compute_pressure(category_key: str, regulation_risk: int | None = None, ai_adjustment_pp: float = 0.0):
    cat = CATEGORIES[category_key]
    macro = collectors.macro_snapshot()
    min_wage_yoy = collectors.yoy(MINIMUM_WAGE, max(MINIMUM_WAGE))

    occ = {o: collectors.wage_growth(o) for o in cat.occupations}
    occ_vals = [v for v in occ.values() if v is not None]
    occ_avg = sum(occ_vals) / len(occ_vals) if occ_vals else min_wage_yoy

    rates = {
        "labor": round(0.6 * occ_avg + 0.4 * min_wage_yoy, 2),
        "material": macro["ppi_yoy"],
        "expense": macro["cpi_yoy"],
    }
    contrib = {k: round(cat.cost_mix[k] * rates[k], 2) for k in rates}
    base = round(sum(contrib.values()), 2)
    adj = max(-2.0, min(2.0, ai_adjustment_pp))
    expected = round(base + adj, 2)

    reg = regulation_risk if regulation_risk is not None else min(15, 4 + 2 * len(cat.regulation_keywords))
    reg = max(0, min(15, reg))
    index = round(max(0, min(100, expected / 8 * 70 + reg + cat.supply_concentration)), 1)
    label, color, note = level_of(index)

    return {
        "category": cat.name,
        "min_wage_yoy": min_wage_yoy,
        "min_wage_year": max(MINIMUM_WAGE),
        "occupation_growth": occ,
        "occupation_avg": round(occ_avg, 2),
        "rates": rates,
        "cost_mix": cat.cost_mix,
        "contrib": contrib,
        "base_expected": base,
        "ai_adjustment_pp": adj,
        "expected": expected,
        "regulation_risk": reg,
        "supply_concentration": cat.supply_concentration,
        "index": index,
        "level": label,
        "color": color,
        "note": note,
        "macro": macro,
    }


# ---------- Claude ----------

def _client(api_key: str):
    return anthropic.Anthropic(api_key=api_key, max_retries=3)


def _check(resp):
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude가 요청을 처리하지 못했습니다(refusal). 질의 내용을 조정해 다시 시도하세요.")


def research(api_key: str, category_key: str, max_searches: int = 8):
    """Claude web_search 로 비정형 시장정보 수집. (text, sources) 반환."""
    cat = CATEGORIES[category_key]
    source_list = "\n".join(f"- {s['name']} ({s['url']}): {s['data']}" for s in SOURCES)
    prompt = f"""오늘은 {date.today():%Y-%m-%d}입니다. 현대제철 구매부서가 '{cat.name}' ({cat.description}) 외주용역/도급 계약의
다음 입찰을 준비하고 있습니다. 아래 기관과 뉴스를 중심으로 웹 검색해 최근 6개월 정보를 조사하세요.

{source_list}

조사 항목:
1. {cat.name} 시장 동향 (수요, 단가 흐름, 인력 수급)
2. 관련 직종({', '.join(cat.occupations)}) 노임단가·인건비 최신 공표값과 상승률
3. 최저임금 결정 현황 (내년도 포함)
4. 관련 법규 개정·검토 ({', '.join(cat.regulation_keywords)})
5. 주요 공급사 뉴스, 신규 진입·이탈 업체, M&A
6. 관련 원자재·물가 변동 (자재비 비중 {cat.cost_mix['material']:.0%})

각 항목마다 확인된 사실만 수치·날짜와 함께 bullet로 정리하고, 문장마다 출처(기관명과 URL)를 붙이세요.
찾지 못한 항목은 '확인되지 않음'이라고 쓰세요."""

    client = _client(api_key)
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches,
              "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]
    texts, sources = [], {}
    for _ in range(4):
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=tools,
            messages=messages,
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        _check(resp)
        for b in resp.content:
            if b.type == "text":
                texts.append(b.text)
            elif b.type == "web_search_tool_result" and isinstance(b.content, list):
                for r in b.content:
                    sources[r.url] = r.title
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    return "".join(texts).strip(), [{"url": u, "title": t} for u, t in sources.items()]


def analyze(api_key: str, category_key: str, research_text: str, news: list, bids: list):
    cat = CATEGORIES[category_key]
    quant = compute_pressure(category_key)
    news_txt = "\n".join(f"- {n['title']} ({n['source']}, {n['published']})" for n in news[:15]) or "(없음)"
    bid_txt = "\n".join(f"- {b['notice_date']} {b['agency']} / {b['title']}" for b in bids[:15]) or "(없음)"
    sample_note = "※ 노임단가·거시지표 일부는 데모용 샘플값임" if quant["macro"]["is_sample"] else ""

    prompt = f"""당신은 제철소 외주용역·도급공사 구매 전문 애널리스트입니다.
품목: {cat.name} — {cat.description}
원가 구성비: 노무비 {cat.cost_mix['labor']:.0%}, 자재비 {cat.cost_mix['material']:.0%}, 경비 {cat.cost_mix['expense']:.0%}

[정량 지표 — 시스템 산출] {sample_note}
- 최저임금 {quant['min_wage_year']}년 인상률: {quant['min_wage_yoy']}%
- 직종별 노임 상승률: {quant['occupation_growth']}
- 노무비 상승률(가중): {quant['rates']['labor']}%, 자재비(PPI): {quant['rates']['material']}%, 경비(CPI): {quant['rates']['expense']}%
- 원가 구성비 가중 예상 상승률: {quant['base_expected']}%
- 공급 집중도 점수: {quant['supply_concentration']}/15

[웹 리서치 결과]
{research_text or '(리서치 없음)'}

[최근 뉴스 헤드라인]
{news_txt}

[나라장터 최근 공고]
{bid_txt}

위 자료만 근거로 다음 입찰 시 단가 인상 압박을 분석하세요.
- 예상 인상률 범위는 정량 예상치 {quant['base_expected']}%를 기준으로, 리서치에서 확인된 정성 요인만큼만 조정하세요(조정폭 ±2%p 이내).
- 자료에 없는 수치를 만들지 마세요. 출처가 없는 항목은 source='추정', confidence='low'로 표시하세요.
- 리서치 결과에서 확인된 최신 공표값이 시스템 지표와 다르면 key_items에 리서치 값을 출처와 함께 적고 차이를 detail에 설명하세요.
- strategies 와 negotiation_points 는 구매 담당자가 바로 실행할 수 있게 구체적으로 쓰세요."""

    resp = _client(api_key).beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
        output_format=MarketReport,
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    _check(resp)
    report: MarketReport = resp.parsed_output
    final = compute_pressure(category_key, report.regulation_risk, report.ai_adjustment_pp)
    return report, final


def rule_based_report(category_key: str, news: list, bids: list) -> tuple[MarketReport, dict]:
    """API 키가 없을 때 정량 지표만으로 만드는 리포트."""
    cat = CATEGORIES[category_key]
    q = compute_pressure(category_key)
    sample = " (샘플)" if q["macro"]["is_sample"] else ""
    items = [
        KeyItem(label=f"{o} 인건비", value=f"전년 대비 {v:+.1f}%", detail="직종 노임단가 기준표 기준",
                source="대한건설협회/엔지니어링협회 (예시값)", confidence="low")
        for o, v in q["occupation_growth"].items() if v is not None
    ]
    items += [
        KeyItem(label="최저임금", value=f"{q['min_wage_yoy']:+.1f}% ({q['min_wage_year']}년 {MINIMUM_WAGE[q['min_wage_year']]:,}원)",
                detail="고용노동부 고시", source="고용노동부", confidence="high"),
        KeyItem(label="소비자물가(CPI)", value=f"{q['rates']['expense']:+.1f}%", detail="경비 상승 기준",
                source="한국은행 ECOS" + sample, confidence="medium"),
        KeyItem(label="생산자물가(PPI)", value=f"{q['rates']['material']:+.1f}%", detail="자재비 상승 기준",
                source="한국은행 ECOS" + sample, confidence="medium"),
    ]
    labor_heavy = cat.cost_mix["labor"] >= 0.7
    strategies = [
        f"단가 인상 요구 예상 — 정량 기준 인상 여력은 약 {q['expected']:.1f}% 수준, 이를 상회하는 요구에는 원가 근거 제출 요청",
        "노임단가 연동형 물가조정 조항 도입 검토 (반기 공표 노임단가 기준)" if labor_heavy
        else "자재비 연동 조항(PPI/원자재 지수) 도입 검토",
    ]
    if cat.supply_concentration >= 8:
        strategies.append("공급 집중도가 높음 — 경쟁사 Pool 확대 및 신규 업체 PQ(사전심사) 추진 필요")
    report = MarketReport(
        headline=f"{cat.name} 단가 인상 압박 '{q['level']}' (압력지수 {q['index']}/100)",
        expected_increase_low=round(q["expected"] - 0.7, 1),
        expected_increase_high=round(q["expected"] + 0.7, 1),
        ai_adjustment_pp=0.0,
        adjustment_reason="AI 분석 미실행 — 정량 지표만 반영",
        regulation_risk=q["regulation_risk"],
        key_items=items,
        market_trends=[f"[뉴스] {n['title']}" for n in news[:5]] or ["ANTHROPIC_API_KEY 설정 시 AI가 시장동향을 수집합니다."],
        regulations=[f"모니터링 대상: {k}" for k in cat.regulation_keywords],
        supply_market=[f"나라장터 최근 60일 관련 공고 {len(bids)}건"] if bids else ["나라장터 데이터 미수집 (DATA_GO_KR_KEY 필요)"],
        strategies=strategies,
        negotiation_points=[
            f"노무비 비중 {cat.cost_mix['labor']:.0%} × 노무비 상승률 {q['rates']['labor']:.1f}% = {q['contrib']['labor']:.2f}%p가 인건비 요인 상한",
            f"최저임금 인상률 {q['min_wage_yoy']:.1f}%는 전 직종 공통 요인 — 최저임금 적용 인력 비중을 확인할 것",
        ],
        risks=["노임단가는 데모용 예시값 — 실제 공표값으로 교체 전에는 참고용으로만 사용"],
    )
    return report, q


def build_report(category_key: str, api_key: str | None, use_web_search: bool = True, progress=None):
    """리포트 생성 전체 파이프라인. (report, quant, sources, ai_used) 반환."""
    news = storage.get_news(category_key, 15)
    bids = storage.get_bids(category_key, 20)
    if not api_key:
        r, q = rule_based_report(category_key, news, bids)
        return r, q, [], False
    research_text, sources = "", []
    if use_web_search:
        progress and progress("Claude가 웹에서 시장동향·법규·공급사 정보를 검색 중...")
        research_text, sources = research(api_key, category_key)
    progress and progress("Claude가 수집 데이터를 종합 분석 중...")
    r, q = analyze(api_key, category_key, research_text, news, bids)
    return r, q, sources, True
