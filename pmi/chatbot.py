"""외주용역/도급공사 Q&A 챗봇 (OpenAI).

PMI 가 보유한 최신 지표·리포트를 시스템 프롬프트에 넣어 답변 근거로 삼는다.
OPENAI_API_KEY, OPENAI_MODEL(선택) 은 .env 또는 st.secrets 에서 읽는다.
"""
from datetime import date

from openai import OpenAI

from . import analyzer, collectors, storage
from .config import CATEGORIES, MINIMUM_WAGE

DEFAULT_MODEL = "gpt-5.5"

SUGGESTIONS = [
    "비파괴검사 연간계약 갱신 시 예상 단가 인상률과 근거는?",
    "공급사가 8% 인상을 요구하면 어떻게 협상해야 하나요?",
    "청소·경비 용역에서 최저임금 인상 영향은 얼마나 되나요?",
    "중대재해처벌법이 도급공사 계약에 미치는 영향은?",
]


def build_context(focus_key: str | None = None) -> str:
    """PMI 데이터 요약. focus_key 품목은 최신 리포트 상세까지 포함."""
    macro = collectors.macro_snapshot()
    y = max(MINIMUM_WAGE)
    lines = [
        f"기준일: {date.today():%Y-%m-%d}",
        f"최저임금 {y}년 {MINIMUM_WAGE[y]:,}원 (전년 대비 {collectors.yoy(MINIMUM_WAGE, y):+.1f}%)",
        f"CPI {macro['cpi_yoy']:+.1f}%, PPI {macro['ppi_yoy']:+.1f}%, 기준금리 {macro['base_rate']}%"
        + (" (일부 샘플값)" if macro["is_sample"] else ""),
        "",
        "[품목별 원가상승 압력지수]",
    ]
    for key, cat in CATEGORIES.items():
        latest = storage.latest_report(key)
        q = latest["payload"]["quant"] if latest else analyzer.compute_pressure(key)
        mix = cat.cost_mix
        lines.append(
            f"- {cat.name}: 압력지수 {q['index']} ({q['level']}), 예상 상승률 {q['expected']:+.2f}%, "
            f"원가구성 노무 {mix['labor']:.0%}/자재 {mix['material']:.0%}/경비 {mix['expense']:.0%}, "
            f"관련 법규: {', '.join(cat.regulation_keywords)}"
        )

    if focus_key:
        latest = storage.latest_report(focus_key)
        if latest:
            r = latest["payload"]["report"]
            lines += [
                "",
                f"[{CATEGORIES[focus_key].name} 최신 리포트 ({latest['created_at'][:10]}, "
                f"{'AI 분석' if latest['ai_used'] else '규칙 기반'})]",
                f"종합: {r['headline']} / 예상 인상률 {r['expected_increase_low']:+.1f}% ~ {r['expected_increase_high']:+.1f}%",
                *[f"- {k['label']}: {k['value']} (출처 {k['source']})" for k in r["key_items"]],
                "법규: " + " / ".join(r["regulations"]),
                "공급시장: " + " / ".join(r["supply_market"]),
                "구매전략: " + " / ".join(r["strategies"]),
            ]
        news = storage.get_news(focus_key, 8)
        if news:
            lines += ["", "[최근 뉴스]"] + [f"- {n['title']} ({n['published'][:16]})" for n in news]
    return "\n".join(lines)


def system_prompt(context: str) -> str:
    return f"""당신은 현대제철 구매부서의 도급공사·외주용역 구매 전문 어시스턴트입니다.
답변 대상은 구매 담당자이며, 단가 협상·입찰 전략·계약 조건·관련 법규·시장 동향 질문에 답합니다.

원칙:
- 아래 PMI 데이터에 있는 수치를 우선 근거로 사용하고, 사용한 수치는 출처(예: 'PMI 압력지수', '고용노동부 고시')를 밝히세요.
- PMI 데이터에 없는 최신 수치·법령 조문은 단정하지 말고 "확인 필요"라고 표시하세요. 수치를 지어내지 마세요.
- 노임단가 등 '샘플/예시'로 표시된 값은 참고용임을 함께 알리세요.
- 법률 해석은 일반적 설명에 그치고, 계약 확정 전 법무 검토를 권고하세요.
- 한국어로, 결론 먼저 → 근거 → 실행 제안 순으로 간결하게 답하세요.

[PMI 데이터]
{context}"""


def stream_answer(api_key: str, model: str, history: list[dict], context: str):
    """history: [{'role': 'user'|'assistant', 'content': str}, ...] → 텍스트 조각 generator."""
    client = OpenAI(api_key=api_key)
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt(context)}, *history[-20:]],
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
