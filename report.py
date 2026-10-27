"""리포트 렌더링 (Markdown / HTML)."""
import html
from datetime import date

import markdown_it

from .theme import ACCENT, BORDER, FONT, NAVY, NAVY_600


def _week_label(d: date):
    y, w, _ = d.isocalendar()
    return f"{y}년 {w}주차"


def to_markdown(report: dict, quant: dict, sources: list, ai_used: bool, today: date | None = None) -> str:
    today = today or date.today()
    r = report
    lines = [
        f"# 외주용역 시장동향 Report — {quant['category']}",
        f"{_week_label(today)} (기준일 {today:%Y-%m-%d}) · 분석: {'Claude AI + 정량지표' if ai_used else '정량지표(규칙 기반)'}",
        "",
        f"## ■ 종합 판단: 단가 인상 압박 **{quant['level']}** (압력지수 {quant['index']}/100)",
        f"- 다음 입찰 예상 인상률: **{r['expected_increase_low']:+.1f}% ~ {r['expected_increase_high']:+.1f}%**",
        f"- {r['headline']}",
        f"- 정량 기준 {quant['base_expected']:+.2f}% / AI 조정 {quant['ai_adjustment_pp']:+.1f}%p — {r['adjustment_reason']}",
        "",
        "## ○ 핵심 지표",
        "| 지표 | 값 | 설명 | 출처 | 신뢰도 |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {k['label']} | {k['value']} | {k['detail']} | {k['source']} | {k['confidence']} |" for k in r["key_items"]]

    def section(title, items):
        lines.extend(["", f"## ○ {title}"] + [f"- {i}" for i in items] if items else [])

    section("시장 동향", r["market_trends"])
    section("관련 법규", r["regulations"])
    section("공급시장", r["supply_market"])
    section("구매전략 제안", r["strategies"])
    section("협상 포인트", r["negotiation_points"])
    section("리스크", r["risks"])

    lines += ["", "## ○ 원가 분해", "| 항목 | 구성비 | 상승률 | 기여도 |", "|---|---|---|---|"]
    names = {"labor": "노무비", "material": "자재비", "expense": "경비"}
    for k, n in names.items():
        lines.append(f"| {n} | {quant['cost_mix'][k]:.0%} | {quant['rates'][k]:+.2f}% | {quant['contrib'][k]:+.2f}%p |")

    if sources:
        lines += ["", "## ■ 출처"] + [f"{i}. [{s['title'] or s['url']}]({s['url']})" for i, s in enumerate(sources, 1)]
    if quant["macro"]["is_sample"]:
        lines += ["", "> ⚠ 일부 지표(노임단가·물가)는 데모용 샘플값입니다. 운영 전 실제 공표값/API 키를 설정하세요."]
    lines += ["", "> ※ 본 리포트는 AI가 공개 데이터를 기반으로 생성한 참고자료이며, 최종 의사결정은 담당자 검토를 거쳐야 합니다."]
    return "\n".join(lines)


def to_html(md_text: str, title: str) -> str:
    lines = md_text.split("\n")
    # 첫 두 줄(제목·주차)은 남색 표지 헤더로
    title_line, meta_line = lines[0].lstrip("# ").strip(), lines[1] if len(lines) > 1 else ""
    body = markdown_it.MarkdownIt("commonmark").enable("table").render("\n".join(lines[2:]))
    body = (f'<div class="cover"><div class="brand">Procurement Market Intelligence · 현대제철 구매</div>'
            f'<h1>{html.escape(title_line)}</h1><p>{html.escape(meta_line)}</p></div>' + body)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--navy:{NAVY};--navy6:{NAVY_600};--accent:{ACCENT};--border:{BORDER}}}
body{{font-family:{FONT};max-width:900px;margin:0 auto;padding:0 20px 40px;color:#1a1a1a;line-height:1.65;background:#fff}}
.cover{{background:linear-gradient(120deg,var(--navy),var(--navy6));color:#fff;padding:22px 26px;margin:0 -20px 24px;border-radius:0 0 12px 12px}}
.cover .brand{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;opacity:.75}}
h1{{font-size:1.5em;margin:6px 0 0;color:#fff}}
.cover p{{margin:6px 0 0;opacity:.9;font-size:.92em}}
h2{{margin-top:28px;color:var(--navy6);font-size:1.12em;border-bottom:2px solid var(--border);padding-bottom:6px}}
table{{border-collapse:collapse;width:100%;font-size:.9em;margin:8px 0}}
th,td{{border:1px solid var(--border);padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:var(--navy6);color:#fff;font-weight:500}}
tr:nth-child(even) td{{background:#F5F7FA}}
a{{color:var(--accent)}}
blockquote{{color:#52514E;border-left:4px solid var(--navy6);background:#EEF3FA;margin:12px 0;padding:6px 14px}}
@page{{size:A4;margin:16mm 14mm}}
@media print{{body{{max-width:none;padding:0}} .cover{{margin:0 0 18px;border-radius:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
 th,tr:nth-child(even) td{{-webkit-print-color-adjust:exact;print-color-adjust:exact}} h2{{break-after:avoid}} tr{{break-inside:avoid}}}}
</style></head><body>{body}</body></html>"""
