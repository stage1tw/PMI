"""PMI 디자인 시스템 — 남색(Navy) 톤 컬러·CSS·HTML 컴포넌트·Plotly 템플릿.

색상값은 공식 CI 값을 받으면 아래 상수만 교체하면 된다.
CSS 는 inject_css() 한 곳에서만 주입하고, 페이지 코드는 아래 헬퍼만 사용한다.
"""
import html

import markdown_it
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY = "#0B2A4A"  # 사이드바·헤더 배경
NAVY_600 = "#003876"  # 강조 텍스트·버튼·합계 막대
ACCENT = "#2A78D6"  # 차트 기본 시리즈·링크
SURFACE = "#F5F7FA"
CARD = "#FFFFFF"
BORDER = "#DDE3EC"
TEXT = "#0B0B0B"
TEXT_2 = "#52514E"
MUTED = "#8A8984"
FONT = "'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
# 상태색은 압력 수준 전용 (config.LEVELS 와 동일). 노랑 배경에는 어두운 글자.
ON_STATUS = {"#fab219": TEXT}

_md = markdown_it.MarkdownIt("commonmark").enable("table")

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, .stApp, .stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp label,
.stApp input, .stApp textarea, .stApp button {{ font-family: {FONT}; }}
[data-testid="stIconMaterial"] {{ font-family: "Material Symbols Rounded" !important; }}
.stApp {{ background: {SURFACE}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.2rem; max-width: 1400px; }}
h1, h2, h3, h4 {{ color: {NAVY}; letter-spacing: -0.01em; }}
a {{ color: {ACCENT}; }}

/* 사이드바 */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {NAVY} 0%, #0E3560 100%); }}
[data-testid="stSidebar"] * {{ color: #E8EEF6; }}
[data-testid="stSidebar"] input {{ color: {TEXT} !important; background: #fff; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.15); }}
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"]),
[data-testid="stSidebar"] [data-testid="stRadio"], [data-testid="stSidebar"] [data-testid="stRadio"] > div {{ width: 100% !important; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ width: 100%; gap: 2px; align-items: stretch; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
  display: flex; width: 100%; padding: .55rem .8rem; border-radius: 8px; margin: 0; cursor: pointer; transition: background .15s;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{ background: rgba(255,255,255,.08); }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{
  background: rgba(255,255,255,.14); box-shadow: inset 3px 0 0 {ACCENT};
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stIconMaterial"] {{ color: #E8EEF6 !important; }}
[data-testid="stSidebar"] [role="radiogroup"] p {{ font-size: .95rem; font-weight: 500; }}
.pmi-brand {{ padding: .25rem 0 1rem; border-bottom: 1px solid rgba(255,255,255,.15); margin-bottom: .75rem; }}
.pmi-brand .mark {{ font-size: 1.9rem; font-weight: 700; letter-spacing: .04em; color: #fff; line-height: 1; }}
.pmi-brand .mark span {{ color: {ACCENT}; }}
.pmi-brand .sub {{ font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; opacity: .7; margin-top: .35rem; }}
.pmi-brand .desc {{ font-size: .82rem; opacity: .85; margin-top: .5rem; }}
.pmi-status {{ display: flex; flex-direction: column; gap: .4rem; margin-top: .5rem; }}

/* 배지 */
.pmi-badge {{ display: inline-flex; align-items: center; gap: .3rem; padding: .18rem .6rem; border-radius: 999px;
  font-size: .78rem; font-weight: 500; line-height: 1.5; white-space: nowrap; }}
.pmi-badge.on {{ background: rgba(12,163,12,.16); color: #0a7d0a; }}
.pmi-badge.off {{ background: rgba(138,137,132,.18); color: {TEXT_2}; }}
.pmi-badge.warn {{ background: rgba(250,178,25,.2); color: #7a5300; }}
.pmi-badge.navy {{ background: rgba(255,255,255,.16); color: #fff; }}
.pmi-hero .pmi-badge.warn {{ background: #FAB219; color: {TEXT}; }}
.pmi-hero .pmi-badge.on {{ background: rgba(255,255,255,.18); color: #fff; }}
[data-testid="stSidebar"] .pmi-badge.on {{ background: rgba(12,163,12,.25); color: #b9f0b9; }}
[data-testid="stSidebar"] .pmi-badge.off {{ background: rgba(255,255,255,.1); color: #c9d3e0; }}

/* 페이지 헤더 배너 */
.pmi-hero {{ background: linear-gradient(120deg, {NAVY} 0%, {NAVY_600} 60%, #1F5FA8 100%); color: #fff;
  border-radius: 14px; padding: 1.4rem 1.6rem; margin-bottom: 1.2rem; }}
.pmi-hero h1 {{ color: #fff; font-size: 1.6rem; margin: 0; padding: 0; font-weight: 700; }}
.pmi-hero .meta {{ display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; margin-top: .6rem; font-size: .88rem; opacity: .95; }}

/* KPI 카드 */
.pmi-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .8rem; margin-bottom: 1rem; }}
.pmi-kpi {{ background: {CARD}; border: 1px solid {BORDER}; border-left: 4px solid {NAVY_600}; border-radius: 10px; padding: .85rem 1rem; }}
.pmi-kpi .label {{ font-size: .82rem; color: {TEXT_2}; }}
.pmi-kpi .value {{ font-size: 1.65rem; font-weight: 700; color: {NAVY}; margin-top: .15rem; white-space: nowrap; }}
.pmi-kpi .sub {{ font-size: .76rem; color: {MUTED}; margin-top: .1rem; }}

/* 카드·박스 */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ background: {CARD}; border-color: {BORDER}; border-radius: 12px; }}
.pmi-card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 1.1rem 1.2rem; margin-bottom: .9rem; }}
.pmi-card h4 {{ margin: 0 0 .5rem; font-size: 1rem; }}
.pmi-card ul {{ margin: 0; padding-left: 1.1rem; }} .pmi-card li {{ margin: .2rem 0; font-size: .92rem; }}
.pmi-box {{ background: {CARD}; border: 1.5px solid {NAVY_600}; border-radius: 12px; padding: 1.1rem 1.2rem; margin: .6rem 0; }}
.pmi-box h4 {{ margin: 0 0 .5rem; font-size: 1.02rem; color: {NAVY_600}; }}
.pmi-box.fill {{ background: #EEF3FA; }}
.pmi-box ul {{ margin: 0; padding-left: 1.1rem; }} .pmi-box li {{ margin: .25rem 0; }}

/* 종합판단 카드 */
.pmi-summary {{ background: {CARD}; border: 1px solid {BORDER}; border-top: 5px solid var(--lv); border-radius: 12px; padding: 1.2rem 1.3rem; }}
.pmi-summary .row {{ display: flex; flex-wrap: wrap; gap: 1.6rem; align-items: flex-end; }}
.pmi-summary .k {{ font-size: .8rem; color: {TEXT_2}; }}
.pmi-summary .big {{ font-size: 2.6rem; font-weight: 700; color: {NAVY}; line-height: 1.1; }}
.pmi-summary .big small {{ font-size: 1rem; color: {MUTED}; font-weight: 500; }}
.pmi-summary .range {{ font-size: 1.6rem; font-weight: 700; color: {NAVY_600}; white-space: nowrap; }}
.pmi-summary .bar {{ height: 8px; background: #E9EEF5; border-radius: 4px; margin: .9rem 0 .4rem; position: relative; }}
.pmi-summary .bar > div {{ height: 100%; border-radius: 4px; background: var(--lv); }}
.pmi-summary .foot {{ font-size: .85rem; color: {TEXT_2}; }}
.pmi-headline {{ font-size: 1.05rem; font-weight: 600; color: {NAVY}; margin: 1rem 0 .4rem; }}

/* 버튼 */
.stButton > button[kind="primary"], .stDownloadButton > button {{ border-radius: 8px; font-weight: 500; }}
.stButton > button[kind="primary"] {{ background: {NAVY_600}; border-color: {NAVY_600}; }}
.stButton > button[kind="primary"]:hover {{ background: {NAVY}; border-color: {NAVY}; }}
.stDownloadButton > button {{ border-color: {NAVY_600}; color: {NAVY_600}; }}

/* 뉴스 리스트 */
.pmi-news {{ list-style: none; padding: 0; margin: 0; }}
.pmi-news li {{ padding: .55rem 0; border-bottom: 1px solid {BORDER}; font-size: .92rem; }}
.pmi-news li:last-child {{ border-bottom: none; }}
.pmi-news .tag {{ display: inline-block; font-size: .72rem; color: {NAVY_600}; background: #E6EEF8; border-radius: 4px; padding: .05rem .4rem; margin-right: .4rem; }}
.pmi-news .date {{ color: {MUTED}; font-size: .78rem; margin-left: .3rem; }}

@media (max-width: 640px) {{
  .pmi-hero {{ padding: 1rem 1.1rem; }} .pmi-hero h1 {{ font-size: 1.25rem; }}
  .pmi-kpi .value {{ font-size: 1.35rem; }}
  .pmi-summary .big {{ font-size: 2rem; }} .pmi-summary .range {{ font-size: 1.3rem; }}
}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(s) -> str:
    return html.escape(str(s))


def md_inline(text: str) -> str:
    """AI·뉴스 문장의 마크다운(링크·강조)을 HTML 로. 원시 HTML 은 commonmark 기본값대로 이스케이프되지 않으므로 사전 이스케이프."""
    return _md.renderInline(esc(text))


def badge(text, kind="off", icon=""):
    return f'<span class="pmi-badge {kind}">{icon}{esc(text)}</span>'


def level_badge(level, color, icon):
    fg = ON_STATUS.get(color.lower(), "#fff")
    return f'<span class="pmi-badge" style="background:{color};color:{fg}">{icon} {esc(level)}</span>'


def sidebar_brand():
    st.markdown(
        '<div class="pmi-brand"><div class="mark">PMI<span>.</span></div>'
        '<div class="sub">Procurement Market Intelligence</div>'
        '<div class="desc">현대제철 구매 · 도급공사·외주용역<br>시장동향 AI 리포터</div></div>',
        unsafe_allow_html=True,
    )


def sidebar_status(items):
    """items: [(라벨, 활성여부)]"""
    rows = "".join(badge(f"{label} {'활성' if on else '비활성'}", "on" if on else "off", "● " if on else "○ ") for label, on in items)
    st.markdown(f'<div class="pmi-status">{rows}</div>', unsafe_allow_html=True)


def hero(title, meta_items):
    """meta_items: 배지 HTML 또는 일반 문자열 목록."""
    meta = "".join(m if m.startswith("<span") else f"<span>{esc(m)}</span>" for m in meta_items)
    st.markdown(f'<div class="pmi-hero"><h1>{esc(title)}</h1><div class="meta">{meta}</div></div>', unsafe_allow_html=True)


def kpi_cards(items):
    """items: [(라벨, 값, 보조설명)]"""
    cards = "".join(
        f'<div class="pmi-kpi"><div class="label">{esc(l)}</div><div class="value">{esc(v)}</div>'
        f'<div class="sub">{esc(s)}</div></div>' for l, v, s in items
    )
    st.markdown(f'<div class="pmi-kpis">{cards}</div>', unsafe_allow_html=True)


def _ul(items):
    return "<ul>" + "".join(f"<li>{md_inline(i)}</li>" for i in items) + "</ul>" if items else "<p>-</p>"


def card(title, items):
    st.markdown(f'<div class="pmi-card"><h4>{esc(title)}</h4>{_ul(items)}</div>', unsafe_allow_html=True)


def box(title, items, fill=False):
    st.markdown(f'<div class="pmi-box{" fill" if fill else ""}"><h4>{esc(title)}</h4>{_ul(items)}</div>', unsafe_allow_html=True)


def summary_card(q, r, icon):
    st.markdown(
        f'''<div class="pmi-summary" style="--lv:{q["color"]}">
  <div class="row">
    <div><div class="k">원가상승 압력지수</div><div class="big">{q["index"]:.1f}<small> / 100</small></div></div>
    <div>{level_badge("인상 압박 " + q["level"], q["color"], icon)}</div>
    <div><div class="k">다음 입찰 예상 인상률</div>
      <div class="range">{r["expected_increase_low"]:+.1f}% ~ {r["expected_increase_high"]:+.1f}%</div></div>
  </div>
  <div class="bar"><div style="width:{min(q["index"], 100):.1f}%"></div></div>
  <div class="foot">정량 기준 {q["base_expected"]:+.2f}% · AI 조정 {q["ai_adjustment_pp"]:+.1f}%p · {esc(q["note"])}</div>
</div>''',
        unsafe_allow_html=True,
    )


def news_list(items):
    """items: [(태그, news dict)]"""
    lis = "".join(
        f'<li><span class="tag">{esc(t)}</span><a href="{esc(n["link"])}" target="_blank">{esc(n["title"])}</a>'
        f'<span class="date">{esc(n["published"][:16])}</span></li>' for t, n in items
    )
    st.markdown(f'<div class="pmi-card"><ul class="pmi-news">{lis}</ul></div>', unsafe_allow_html=True)


# ---------- Plotly ----------
pio.templates["pmi"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, color=TEXT_2, size=13),
        title=dict(font=dict(color=NAVY, size=15), x=0, xanchor="left"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=[ACCENT],
        xaxis=dict(gridcolor="#E9EEF5", linecolor="#C3C2B7", zeroline=False, tickfont=dict(color=TEXT_2)),
        yaxis=dict(gridcolor="#E9EEF5", linecolor="#C3C2B7", zeroline=False, tickfont=dict(color=TEXT_2)),
        hoverlabel=dict(bgcolor="#fff", bordercolor=BORDER, font=dict(family=FONT, color=TEXT, size=13)),
        margin=dict(l=8, r=16, t=44, b=8),
    )
)
pio.templates.default = "pmi"
