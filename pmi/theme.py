"""PMI 디자인 시스템 — 남색(Navy) 톤 컬러·CSS·HTML 컴포넌트·Plotly 템플릿.

색상값은 공식 CI 값을 받으면 아래 상수만 교체하면 된다.
CSS 는 inject_css() 한 곳에서만 주입하고, 페이지 코드는 아래 헬퍼만 사용한다.
레이아웃은 디자인 시안(Designer (3).png)을 따른다: 좌측 남색 사이드바 · 상단바 · 히어로 배너 ·
KPI 카드 · 차트/표 패널 · 우측 뉴스 컬럼 · 하단 바로가기.
"""
import html
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import markdown_it
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY = "#0A2A63"  # 사이드바·히어로 배경
NAVY_600 = "#0B3D91"  # 강조 텍스트·버튼·합계 막대
ACCENT = "#1F66D1"  # 차트 기본 시리즈·링크·활성 메뉴
SURFACE = "#EEF3FA"
CARD = "#FFFFFF"
BORDER = "#E1E8F2"
TEXT = "#0B0B0B"
TEXT_2 = "#44536B"
MUTED = "#7F8DA3"
ICON_BG = "#E4EEFC"  # KPI 아이콘 타일
DONUT = ["#0B3D91", "#1F66D1", "#7FB0F0", "#9AA6B8", "#D3DAE5"]  # 도넛 분포 (진한 남색 → 회색)
FONT = "'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
# 상태색은 압력 수준 전용 (config.LEVELS 와 동일). 노랑 배경에는 어두운 글자.
ON_STATUS = {"#fab219": TEXT}

_md = markdown_it.MarkdownIt("commonmark").enable("table")

# 히어로 배너 배경: 제철소 실루엣 (사진 대체용 인라인 SVG — 실제 사진을 받으면 이 상수만 교체)
_SKYLINE = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 140' preserveAspectRatio='xMaxYMax slice'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#3a74c4'/>"
    "<stop offset='1' stop-color='#0d2f6e'/></linearGradient></defs>"
    "<rect width='1200' height='140' fill='url(#g)'/>"
    "<g fill='#0a2150' opacity='.92'>"
    "<rect x='560' y='64' width='60' height='76'/><rect x='630' y='34' width='34' height='106'/>"
    "<rect x='690' y='74' width='120' height='66'/><rect x='722' y='24' width='22' height='56'/>"
    "<rect x='782' y='44' width='26' height='40'/><polygon points='830,140 830,54 860,34 890,54 890,140'/>"
    "<rect x='900' y='58' width='70' height='82'/><rect x='930' y='18' width='18' height='50'/>"
    "<rect x='990' y='78' width='90' height='62'/><rect x='1040' y='38' width='20' height='46'/>"
    "<rect x='1100' y='62' width='100' height='78'/></g>"
    "<g fill='#fff' opacity='.14'><ellipse cx='733' cy='16' rx='34' ry='10'/><ellipse cx='939' cy='10' rx='30' ry='9'/>"
    "<ellipse cx='1050' cy='30' rx='26' ry='8'/></g></svg>"
)
_HERO_BG = (
    "linear-gradient(90deg, rgba(10,42,99,.97) 0%, rgba(10,42,99,.86) 44%, rgba(10,42,99,.12) 100%), "
    f"url(\"data:image/svg+xml,{quote(_SKYLINE)}\") right bottom / cover no-repeat"
)
_NAV_ICONS = ["home", "description", "smart_toy", "monitoring", "inventory_2", "settings"]
_NAV_ICON_CSS = "\n".join(
    f'[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div:nth-child({i}) p::before {{ content: "{ic}"; }}'
    for i, ic in enumerate(_NAV_ICONS, 1)
)

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap');
html, body, .stApp, .stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp label,
.stApp input, .stApp textarea, .stApp button {{ font-family: {FONT}; }}
[data-testid="stIconMaterial"] {{ font-family: "Material Symbols Rounded" !important; }}
.mi {{ font-family: "Material Symbols Rounded" !important; font-weight: 400; font-style: normal; line-height: 1;
  letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; font-size: 24px;
  font-feature-settings: 'liga'; -webkit-font-feature-settings: 'liga'; }}
.stApp {{ background: {SURFACE}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ padding: 1rem 1.4rem 2rem; max-width: 1680px; }}
h1, h2, h3, h4 {{ color: {NAVY}; letter-spacing: -0.01em; }}
a {{ color: {ACCENT}; }}

/* 사이드바 */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {NAVY} 0%, #0E3A86 100%); }}
@media (min-width: 992px) {{ [data-testid="stSidebar"] {{ width: 212px !important; min-width: 212px !important; }} }}
[data-testid="stSidebarUserContent"] {{ padding: 1rem 1rem 1rem !important; }}
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{ min-height: calc(100vh - 7rem); }}
[data-testid="stSidebar"] * {{ color: #E8EEF6; }}
[data-testid="stSidebar"] input {{ color: {TEXT} !important; background: #fff; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.15); }}
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"]),
[data-testid="stSidebar"] [data-testid="stRadio"], [data-testid="stSidebar"] [data-testid="stRadio"] > div {{ width: 100% !important; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ width: 100%; gap: 4px; align-items: stretch; }}
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div {{ margin: 0 -1rem; width: auto; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
  display: flex; align-items: center; width: 100%; margin: 0; padding: .85rem .6rem .85rem 1.2rem;
  border-radius: 0; cursor: pointer; transition: background .15s;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{ background: rgba(255,255,255,.08); }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{ background: {ACCENT}; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stIconMaterial"] {{ color: #E8EEF6 !important; }}
[data-testid="stSidebar"] [role="radiogroup"] p {{ font-size: .92rem; font-weight: 500; display: flex; align-items: center; gap: .65rem; white-space: nowrap; }}
[data-testid="stSidebar"] [role="radiogroup"] p::before {{ font-family: "Material Symbols Rounded"; font-size: 24px; line-height: 1;
  font-weight: 400; font-feature-settings: 'liga'; -webkit-font-feature-settings: 'liga'; }}
{_NAV_ICON_CSS}
.pmi-brand {{ display: flex; align-items: center; gap: .55rem; padding: .35rem 0 1.1rem; }}
.pmi-brand .h {{ font-size: 2.3rem; font-weight: 800; font-style: italic; line-height: 1; color: #fff; letter-spacing: -.05em; }}
.pmi-brand .w {{ font-size: 1.02rem; font-weight: 800; line-height: 1.05; color: #fff; letter-spacing: .02em; }}
.pmi-status {{ display: flex; flex-direction: column; gap: .4rem; margin-top: .5rem; }}
.pmi-tagline {{ font-size: .98rem; line-height: 1.5; font-weight: 500; color: #E8EEF6; padding: 1rem 0 0; }}
.pmi-tagline small {{ display: block; font-size: .72rem; line-height: 1.4; color: #AFC0DA; font-weight: 400; margin-top: 1.6rem; }}
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.pmi-tagline) {{ margin-top: auto; }}

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

/* 상단바 */
.pmi-topbar {{ display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: .4rem 1.2rem; margin-bottom: .7rem; }}
.pmi-topbar .t {{ font-size: 1.28rem; font-weight: 700; color: {NAVY}; line-height: 1.25; letter-spacing: -.01em; }}
.pmi-topbar .s {{ font-size: .86rem; color: {TEXT_2}; margin-top: .1rem; }}
.pmi-topbar .r {{ display: flex; gap: 1rem; align-items: center; font-size: .78rem; color: {TEXT_2}; flex-wrap: wrap; }}
.pmi-topbar .upd {{ color: {ACCENT}; font-weight: 500; }}

/* 페이지 헤더 배너 */
.pmi-hero {{ background: {_HERO_BG}; color: #fff; border-radius: 8px; padding: 1.35rem 1.8rem; margin-bottom: 1rem;
  min-height: 118px; display: flex; justify-content: space-between; align-items: center; gap: 1rem; overflow: hidden; }}
.pmi-hero h1 {{ color: #fff; font-size: 1.85rem; margin: 0; padding: 0; font-weight: 800; letter-spacing: -.02em; line-height: 1.25; }}
.pmi-hero .sub {{ font-size: 1.02rem; margin-top: .55rem; color: #E3ECFA; }}
.pmi-hero .meta {{ display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; margin-top: .6rem; font-size: .82rem; opacity: .95; }}
.pmi-hero .slogan {{ font-family: 'Brush Script MT', 'Segoe Script', cursive; font-style: italic; font-size: 1.7rem; line-height: 1.15;
  color: rgba(255,255,255,.82); text-align: right; white-space: nowrap; transform: rotate(-4deg); text-shadow: 0 2px 8px rgba(0,0,0,.3); }}

/* KPI 카드 */
.pmi-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .8rem; margin-bottom: 1rem; }}
.pmi-kpis.four {{ grid-template-columns: repeat(4, 1fr); }}
.pmi-kpi {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: .95rem 1.1rem;
  box-shadow: 0 1px 3px rgba(16,42,90,.05); display: flex; align-items: center; gap: .9rem; }}
.pmi-kpi .bd {{ min-width: 0; flex: 1; }}
.pmi-kpi .ic {{ flex: none; width: 52px; height: 52px; border-radius: 12px; background: {ICON_BG}; color: {ACCENT};
  display: flex; align-items: center; justify-content: center; }}
.pmi-kpi .ic .mi {{ font-size: 28px; font-variation-settings: 'FILL' 1; }}
.pmi-kpi .label {{ font-size: .86rem; color: {TEXT_2}; font-weight: 500; }}
.pmi-kpi .value {{ font-size: 1.85rem; font-weight: 700; color: {NAVY}; margin-top: .1rem; white-space: nowrap; line-height: 1.2; }}
.pmi-kpi .value small {{ font-size: 1rem; font-weight: 500; margin-left: .2rem; color: {NAVY}; }}
.pmi-kpi .sub {{ font-size: .76rem; color: {MUTED}; margin-top: .1rem; }}
@media (max-width: 1180px) {{ .pmi-kpis.four {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 640px) {{ .pmi-kpis.four {{ grid-template-columns: 1fr; }} }}

/* 카드·패널 */
[class*="st-key-panel_"] {{ background: {CARD}; border-color: {BORDER}; border-radius: 10px; box-shadow: 0 1px 3px rgba(16,42,90,.05); }}
.pmi-ptitle {{ font-size: 1.08rem; font-weight: 700; color: {NAVY}; margin: 0 0 .5rem; line-height: 1.5; }}
.pmi-card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 1.1rem 1.2rem; margin-bottom: .9rem;
  box-shadow: 0 1px 3px rgba(16,42,90,.05); }}
.pmi-card h4 {{ margin: 0 0 .5rem; font-size: 1rem; }}
.pmi-card ul {{ margin: 0; padding-left: 1.1rem; }} .pmi-card li {{ margin: .2rem 0; font-size: .92rem; }}
.pmi-box {{ background: {CARD}; border: 1.5px solid {NAVY_600}; border-radius: 10px; padding: 1.1rem 1.2rem; margin: .6rem 0; }}
.pmi-box h4 {{ margin: 0 0 .5rem; font-size: 1.02rem; color: {NAVY_600}; }}
.pmi-box.fill {{ background: #EEF3FA; }}
.pmi-box ul {{ margin: 0; padding-left: 1.1rem; }} .pmi-box li {{ margin: .25rem 0; }}

/* 종합판단 카드 */
.pmi-summary {{ background: {CARD}; border: 1px solid {BORDER}; border-top: 5px solid var(--lv); border-radius: 10px; padding: 1.2rem 1.3rem; }}
.pmi-summary .row {{ display: flex; flex-wrap: wrap; gap: 1.6rem; align-items: flex-end; }}
.pmi-summary .k {{ font-size: .8rem; color: {TEXT_2}; }}
.pmi-summary .big {{ font-size: 2.6rem; font-weight: 700; color: {NAVY}; line-height: 1.1; }}
.pmi-summary .big small {{ font-size: 1rem; color: {MUTED}; font-weight: 500; }}
.pmi-summary .range {{ font-size: 1.6rem; font-weight: 700; color: {NAVY_600}; white-space: nowrap; }}
.pmi-summary .bar {{ height: 8px; background: #E9EEF5; border-radius: 4px; margin: .9rem 0 .4rem; position: relative; }}
.pmi-summary .bar > div {{ height: 100%; border-radius: 4px; background: var(--lv); }}
.pmi-summary .foot {{ font-size: .85rem; color: {TEXT_2}; }}
.pmi-headline {{ font-size: 1.05rem; font-weight: 600; color: {NAVY}; margin: 1rem 0 .4rem; }}

/* 버튼·탭·세그먼트 */
.stButton > button[kind="primary"], .stDownloadButton > button {{ border-radius: 8px; font-weight: 500; }}
.stButton > button[kind="primary"] {{ background: {ACCENT}; border-color: {ACCENT}; }}
.stButton > button[kind="primary"]:hover {{ background: {NAVY_600}; border-color: {NAVY_600}; }}
.stDownloadButton > button {{ border-color: {NAVY_600}; color: {NAVY_600}; }}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {{
  border: none; border-radius: 6px; font-size: .86rem; padding: .3rem 1.1rem; background: #EEF3FA; color: {TEXT_2}; box-shadow: none; }}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] {{ background: {ACCENT}; color: #fff; }}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] * {{ color: #fff !important; }}
[data-testid="stTabs"] [role="tablist"] {{ gap: 0; background: #EEF3FA; border-radius: 6px; padding: 0; border-bottom: none; box-shadow: none; }}
[data-testid="stTab"] {{ flex: 1; justify-content: center; border-radius: 6px; padding: .35rem .6rem; height: auto; border-bottom: none !important;
  box-shadow: none !important; }}
[data-testid="stTab"] p {{ font-size: .82rem; }}
[data-testid="stTab"][data-selected="true"] {{ background: {ACCENT}; }}
[data-testid="stTab"][data-selected="true"] * {{ color: #fff !important; }}

/* 하단 바로가기 */
[class*="st-key-qa_"] button {{ height: 76px; justify-content: flex-start; text-align: left; gap: .8rem; padding: .6rem 1rem;
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; box-shadow: 0 1px 3px rgba(16,42,90,.05); }}
[class*="st-key-qa_"] button:hover {{ border-color: {ACCENT}; background: #F7FAFF; }}
[class*="st-key-qa_"] button > div {{ width: 100%; justify-content: flex-start; }}
[class*="st-key-qa_"] button > div > span {{ display: flex; flex-direction: row; align-items: center; gap: .9rem; width: 100%; }}
[class*="st-key-qa_"] button p {{ text-align: left; font-size: .82rem; color: {TEXT_2}; line-height: 1.4; }}
[class*="st-key-qa_"] button p strong {{ display: block; font-size: 1.02rem; color: {NAVY}; }}
[class*="st-key-qa_"] button > div > span::after {{ content: "chevron_right"; font-family: "Material Symbols Rounded"; font-size: 1.6rem;
  color: {TEXT_2}; margin-left: auto; font-feature-settings: 'liga'; -webkit-font-feature-settings: 'liga'; }}
[class*="st-key-qa_"] [data-testid="stMarkdownContainer"] {{ flex: 1; text-align: left; }}
[class*="st-key-qa_"] button [data-testid="stIconMaterial"] {{ color: {ACCENT}; background: {ICON_BG}; border-radius: 10px;
  display: inline-flex; align-items: center; justify-content: center; width: 46px; height: 46px; font-size: 1.6rem; }}

/* 뉴스 리스트 (품목 외 페이지·단순 목록) */
.pmi-news {{ list-style: none; padding: 0; margin: 0; }}
.pmi-news li {{ padding: .55rem 0; border-bottom: 1px solid {BORDER}; font-size: .92rem; }}
.pmi-news li:last-child {{ border-bottom: none; }}
.pmi-news .tag {{ display: inline-block; font-size: .72rem; color: {NAVY_600}; background: #E6EEF8; border-radius: 4px; padding: .05rem .4rem; margin-right: .4rem; }}
.pmi-news .date {{ color: {MUTED}; font-size: .78rem; margin-left: .3rem; }}

/* 오늘의 주요 뉴스 (우측 컬럼) */
.pmi-newsbox {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 1rem 1.1rem .4rem;
  box-shadow: 0 1px 3px rgba(16,42,90,.05); margin-bottom: 1rem; }}
.pmi-ni {{ display: flex; gap: .8rem; padding: .75rem 0; border-top: 1px solid {BORDER}; text-decoration: none !important; align-items: flex-start; }}
.pmi-ni:first-of-type {{ border-top: none; padding-top: .4rem; }}
.pmi-ni .th {{ flex: none; width: 76px; height: 68px; border-radius: 6px; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--c), #0A2A63); color: #fff; }}
.pmi-ni .th .mi {{ font-size: 30px; opacity: .92; }}
.pmi-ni .nb {{ min-width: 0; flex: 1; }}
.pmi-ni .tg {{ display: inline-block; font-size: .7rem; font-weight: 700; color: #fff; padding: .05rem .5rem; border-radius: 4px; }}
.pmi-ni .nt {{ font-size: .92rem; font-weight: 700; color: {NAVY}; margin-top: .2rem; line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.pmi-ni .ns {{ font-size: .76rem; color: {TEXT_2}; margin-top: .15rem; }}
.pmi-ni .nd {{ font-size: .74rem; color: {MUTED}; margin-top: .05rem; }}
@media (max-width: 1180px) {{ .pmi-ni .th {{ display: none; }} }}

/* TOP 5 표 */
.pmi-table {{ width: 100%; border-collapse: collapse; font-size: .86rem; }}
.pmi-table th {{ text-align: left; font-weight: 500; color: {TEXT_2}; background: #F1F5FB; padding: .45rem .6rem; border-bottom: 1px solid {BORDER}; white-space: nowrap; }}
.pmi-table td {{ padding: .62rem .6rem; border-bottom: 1px solid {BORDER}; color: {TEXT}; vertical-align: middle; }}
.pmi-table tr:last-child td {{ border-bottom: none; }}
.pmi-table td.c, .pmi-table th.c {{ text-align: center; }}
.pmi-table td.ttl a {{ color: {TEXT}; text-decoration: none; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }}
.pmi-table td.ttl a:hover {{ color: {ACCENT}; }}
.pmi-table td.d {{ color: {TEXT_2}; white-space: nowrap; }}
.pmi-pill {{ display: inline-block; min-width: 3.1rem; text-align: center; font-size: .78rem; font-weight: 700; padding: .12rem .6rem; border-radius: 999px; }}
.pmi-tablewrap {{ overflow-x: auto; }}

/* 범례 */
.pmi-legend {{ display: flex; flex-direction: column; gap: .5rem; font-size: .84rem; color: {TEXT_2}; justify-content: center; height: 100%; }}
.pmi-legend .it {{ display: flex; align-items: center; gap: .55rem; }}
.pmi-legend .sw {{ flex: none; width: 12px; height: 12px; border-radius: 3px; }}
.pmi-legend .dot {{ border-radius: 50%; }}
.pmi-legend .pc {{ margin-left: auto; color: {TEXT}; font-weight: 500; padding-left: .8rem; }}

@media (max-width: 640px) {{
  .pmi-hero {{ padding: 1rem 1.1rem; }} .pmi-hero h1 {{ font-size: 1.3rem; }} .pmi-hero .slogan {{ display: none; }}
  .pmi-kpi .value {{ font-size: 1.45rem; }}
  .pmi-summary .big {{ font-size: 2rem; }} .pmi-summary .range {{ font-size: 1.3rem; }}
  .pmi-topbar .t {{ font-size: 1.05rem; }}
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


def fmt_date(s: str) -> str:
    """RSS 'published'(RFC 822) → 2026.11.02. 파싱 실패 시 앞 16자."""
    try:
        return parsedate_to_datetime(s).strftime("%Y.%m.%d")
    except Exception:
        return str(s)[:16]


def badge(text, kind="off", icon=""):
    return f'<span class="pmi-badge {kind}">{icon}{esc(text)}</span>'


def level_badge(level, color, icon):
    fg = ON_STATUS.get(color.lower(), "#fff")
    return f'<span class="pmi-badge" style="background:{color};color:{fg}">{icon} {esc(level)}</span>'


def level_pill(level, color):
    """표·뉴스용 압력 수준 알약. 상태색은 압력 수준 전용이며 항상 라벨과 함께 쓴다."""
    fg = ON_STATUS.get(color.lower(), "#fff")
    return f'<span class="pmi-pill" style="background:{color};color:{fg}">{esc(level)}</span>'


def sidebar_brand():
    # 공식 로고 이미지를 받기 전까지의 텍스트 워드마크 (placeholder)
    st.markdown(
        '<div class="pmi-brand"><span class="h">H</span><span class="w">HYUNDAI<br>STEEL</span></div>',
        unsafe_allow_html=True,
    )


def sidebar_status(items):
    """items: [(라벨, 활성여부)]"""
    rows = "".join(badge(f"{label} {'활성' if on else '비활성'}", "on" if on else "off", "● " if on else "○ ") for label, on in items)
    st.markdown(f'<div class="pmi-status">{rows}</div>', unsafe_allow_html=True)


def sidebar_tagline():
    st.markdown(
        '<div class="pmi-tagline">더 나은<br>내일의 철강,<br>사람과 기술로<br>만듭니다.'
        '<small>Beyond Steel<br>for a Sustainable Tomorrow</small></div>',
        unsafe_allow_html=True,
    )


_WEEKDAY = "월화수목금토일"


def topbar(updated: str):
    """상단바: 서비스명 · 현재 시각 · 마지막 데이터 수집 시각."""
    now = datetime.now()
    st.markdown(
        '<div class="pmi-topbar"><div><div class="t">Procurement Market Intelligence (PMI)</div>'
        '<div class="s">도급공사 · 외주용역 시장동향 AI 리포터</div></div>'
        f'<div class="r"><span>{now:%Y년 %m월 %d일} ({_WEEKDAY[now.weekday()]}) {now:%H:%M}</span>'
        f'<span class="upd">⟳ 데이터 업데이트: {esc(updated)}</span></div></div>',
        unsafe_allow_html=True,
    )


def hero(title, meta_items, sub="", page=""):
    """meta_items: 배지 HTML 또는 일반 문자열 목록. page: 메뉴명(테스트·스타일 훅)."""
    meta = "".join(m if m.startswith("<span") else f"<span>{esc(m)}</span>" for m in meta_items)
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="pmi-hero" data-page="{esc(page)}"><div class="txt"><h1>{esc(title)}</h1>{sub_html}'
        f'<div class="meta">{meta}</div></div><div class="slogan">Better Steel<br>for a Brighter Tomorrow</div></div>',
        unsafe_allow_html=True,
    )


def kpi_cards(items, cls=""):
    """items: [(라벨, 값, 보조설명[, 아이콘[, 단위]])]. 아이콘은 Material Symbols 이름."""
    out = []
    for label, value, sub, *rest in items:
        icon = rest[0] if rest else ""
        unit = rest[1] if len(rest) > 1 else ""
        ic = f'<div class="ic"><span class="mi">{esc(icon)}</span></div>' if icon else ""
        out.append(
            f'<div class="pmi-kpi">{ic}<div class="bd"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}<small>{esc(unit)}</small></div><div class="sub">{esc(sub)}</div></div></div>'
        )
    st.markdown(f'<div class="pmi-kpis {cls}">{"".join(out)}</div>', unsafe_allow_html=True)


def panel_title(text):
    st.markdown(f'<div class="pmi-ptitle">{esc(text)}</div>', unsafe_allow_html=True)


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


def news_cards(title, items):
    """items: [{tag, color, title, link, src, date, icon}] — 우측 '오늘의 주요 뉴스' 컬럼.
    썸네일 사진 대신 품목 아이콘 타일(수준 색 그라데이션)을 쓴다."""
    rows = "".join(
        f'<a class="pmi-ni" href="{esc(n["link"])}" target="_blank" rel="noopener">'
        f'<div class="th" style="--c:{n["color"]}"><span class="mi">{esc(n["icon"])}</span></div>'
        f'<div class="nb"><span class="tg" style="background:{n["color"]};'
        f'color:{ON_STATUS.get(n["color"].lower(), "#fff")}">{esc(n["tag"])}</span>'
        f'<div class="nt">{esc(n["title"])}</div><div class="ns">{esc(n["src"])}</div>'
        f'<div class="nd">{esc(n["date"])}</div></div></a>' for n in items
    )
    body = rows or '<div class="ns" style="padding:.6rem 0 1rem">수집된 뉴스가 없습니다.</div>'
    st.markdown(f'<div class="pmi-newsbox"><div class="pmi-ptitle">{esc(title)}</div>{body}</div>', unsafe_allow_html=True)


def issue_table(rows):
    """rows: [{title, link, cat, tag, color, date}] — 순위·이슈명·카테고리·영향도·등록일."""
    trs = "".join(
        f'<tr><td class="c">{i}</td><td class="ttl"><a href="{esc(r["link"])}" target="_blank" rel="noopener">{esc(r["title"])}</a></td>'
        f'<td>{esc(r["cat"])}</td><td class="c">{level_pill(r["tag"], r["color"])}</td><td class="d">{esc(r["date"])}</td></tr>'
        for i, r in enumerate(rows, 1)
    )
    st.markdown(
        '<div class="pmi-tablewrap"><table class="pmi-table"><thead><tr><th class="c">순위</th><th>이슈명</th><th>카테고리</th>'
        f'<th class="c">영향도</th><th>등록일</th></tr></thead><tbody>{trs}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def legend(items, round_=False, pct=False):
    """items: [(색, 라벨[, 값])]"""
    its = "".join(
        f'<div class="it"><span class="sw{" dot" if round_ else ""}" style="background:{c}"></span>{esc(lbl)}'
        + (f'<span class="pc">{esc(rest[0])}</span>' if rest else "") + "</div>"
        for c, lbl, *rest in items
    )
    st.markdown(f'<div class="pmi-legend">{its}</div>', unsafe_allow_html=True)


# ---------- Plotly ----------
pio.templates["pmi"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, color=TEXT_2, size=13),
        title=dict(font=dict(color=NAVY, size=15), x=0, xanchor="left"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=[ACCENT],
        xaxis=dict(gridcolor="#E9EEF5", linecolor="#C3CCDA", zeroline=False, tickfont=dict(color=TEXT_2), automargin=True),
        yaxis=dict(gridcolor="#E9EEF5", linecolor="#C3CCDA", zeroline=False, tickfont=dict(color=TEXT_2), automargin=True),
        hoverlabel=dict(bgcolor="#fff", bordercolor=BORDER, font=dict(family=FONT, color=TEXT, size=13)),
        margin=dict(l=8, r=16, t=44, b=8),
    )
)
pio.templates.default = "pmi"
