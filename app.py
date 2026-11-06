"""Procurement Market Intelligence (PMI) — 도급공사/외주용역 시장동향 AI 리포터."""
import os
from datetime import date, datetime
from email.utils import parsedate_to_datetime

import anthropic
import openai
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # 로컬 .env (OPENAI_API_KEY 등) → 환경변수

from pmi import analyzer, chatbot, collectors, report, storage, theme  # noqa: E402
from pmi.config import CATEGORIES, LEVEL_ICON, LEVELS, SOURCES, WAGE_SAMPLE  # noqa: E402

st.set_page_config(page_title="PMI · 외주용역 시장동향", page_icon="📊", layout="wide")
theme.inject_css()


def secret(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:  # secrets.toml 이 없는 로컬 실행
        pass
    return os.environ.get(name)


def friendly_error(e: Exception) -> str:
    """API 오류를 담당자가 조치할 수 있는 문장으로 (원문은 접어서 제공)."""
    if isinstance(e, (anthropic.AuthenticationError, openai.AuthenticationError)):
        return "API 키가 유효하지 않습니다. 키 값을 확인하거나 새로 발급받아 다시 입력하세요."
    if isinstance(e, (anthropic.RateLimitError, openai.RateLimitError)):
        return "API 호출 한도를 초과했습니다. 잠시 후 다시 시도하세요."
    if isinstance(e, (anthropic.APIConnectionError, openai.APIConnectionError)):
        return "AI 서비스에 연결할 수 없습니다. 네트워크(사내 프록시·방화벽)를 확인하세요."
    return f"{type(e).__name__}: {e}"


def show_error(prefix: str, e: Exception):
    st.error(f"{prefix} — {friendly_error(e)}")
    with st.expander("오류 상세"):
        st.code(f"{type(e).__name__}: {e}")


_PANEL_N = [0]  # 스크립트가 재실행될 때마다 0 으로 초기화됨


def panel():
    """흰 카드 패널. Streamlit 1.67 은 테두리 컨테이너에 고유 testid 가 없어 key 클래스(st-key-panel_*)로 스타일링한다."""
    _PANEL_N[0] += 1
    return st.container(border=True, key=f"panel_{_PANEL_N[0]}")


def chart(fig, height=360, title=None):
    fig.update_layout(height=height, title=title)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})  # theme=None: pmi 템플릿(투명 배경) 사용


# ---------- 사이드바 ----------
with st.sidebar:
    theme.sidebar_brand()
    page = st.radio("메뉴", ["대시보드", "품목 리포트", "AI 챗봇", "시장 지표", "리포트 아카이브", "수집 현황·설정"],
                    key="menu", label_visibility="collapsed")
    st.divider()
    api_key = secret("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = st.text_input("Anthropic API Key (세션 한정)", type="password",
                                help="입력하지 않으면 규칙 기반 리포트로 동작합니다.") or None
    theme.sidebar_status([("Claude 분석", bool(api_key)), ("AI 챗봇", bool(secret("OPENAI_API_KEY")))])
    ecos_key, g2b_key = secret("ECOS_API_KEY"), secret("DATA_GO_KR_KEY")
    theme.sidebar_tagline()

if not storage.collect_status():
    with st.spinner("최초 실행 — 시장 데이터 수집 중..."):
        collectors.collect_all(ecos_key, g2b_key)

MACRO = collectors.macro_snapshot()


def last_update_label():
    """마지막 수집 시각 — 오늘이면 '오늘 09:00', 아니면 날짜."""
    ats = [r["at"] for r in storage.collect_status() if r.get("at")]
    if not ats:
        return "-"
    at = datetime.fromisoformat(max(ats))
    return f"오늘 {at:%H:%M}" if at.date() == date.today() else f"{at:%Y.%m.%d %H:%M}"


def hero(title, *extra, sub=""):
    data = theme.badge("샘플 데이터 포함", "warn", "⚠ ") if MACRO["is_sample"] else theme.badge("실데이터", "on", "● ")
    theme.hero(title, [f"기준일 {date.today():%Y-%m-%d}", data, *extra], sub=sub, page=page)


theme.topbar(last_update_label())


def current_pressure(key):
    """저장된 최신 리포트(AI 반영)가 있으면 그 지수, 없으면 규칙 기반."""
    latest = storage.latest_report(key)
    if latest:
        p = latest["payload"]
        return p["quant"], p["report"], latest
    return analyzer.compute_pressure(key), None, None


# ---------- 대시보드 ----------
# 도급공사 / 외주용역 구분 (디자인 시안의 탭). 품목 성격에 따른 분류이며 config 에는 없다.
GROUPS = {"도급공사": ["plant", "construction", "maintenance"],
          "외주용역": ["ndt", "cleaning", "security", "safety", "engineering"]}
CAT_ICON = {"ndt": "troubleshoot", "maintenance": "build", "plant": "factory", "construction": "apartment",
            "cleaning": "cleaning_services", "security": "security", "safety": "health_and_safety", "engineering": "engineering"}


def _news_ts(n):
    try:
        return parsedate_to_datetime(n["published"]).replace(tzinfo=None)
    except Exception:
        return datetime.min


def _issue(key, n, q):
    return {"title": n["title"], "link": n["link"], "cat": CATEGORIES[key].name, "tag": q["level"], "color": q["color"],
            "date": theme.fmt_date(n["published"]), "src": n.get("source") or CATEGORIES[key].name,
            "icon": CAT_ICON.get(key, "article"), "ts": _news_ts(n)}


def _go(target):
    st.session_state["menu"] = target


def page_dashboard():
    hero("시장 인사이트로 더 스마트한 구매를", sub="AI가 분석한 도급공사 · 외주용역 시장 동향으로, 더 나은 의사결정을 지원합니다.")

    rows, quants = [], {}
    for key, cat in CATEGORIES.items():
        q, r, latest = current_pressure(key)
        quants[key] = q
        rows.append({
            "key": key, "품목": cat.name, "압력지수": q["index"], "수준": q["level"], "color": q["color"],
            "예상 인상률(%)": q["expected"],
            "분석": ("AI " if latest and latest["ai_used"] else "규칙 ") + (latest["created_at"][:10] if latest else "실시간"),
        })
    df = pd.DataFrame(rows)
    news_by_cat = {k: storage.get_news(k, 500) for k in CATEGORIES}
    n_news = sum(len(v) for v in news_by_cat.values())

    main, side = st.columns([3.1, 1.05], gap="medium")
    with main:
        theme.kpi_cards([
            ("시장 위험도", f"{df['압력지수'].mean():.0f}", f"{len(df)}개 품목 평균 압력지수", "shield", "점"),
            ("예상 원가상승률", f"{df['예상 인상률(%)'].mean():+.1f}", "다음 입찰 기준 품목 평균", "bar_chart", "%"),
            ("주요 시장이슈", f"{n_news}", "수집된 최근 뉴스", "article", "건"),
            ("관리 필요 품목", f"{(df['압력지수'] >= 55).sum()}", "압력지수 55 이상", "groups", "개"),
        ], cls="four")

        with panel():
            c1, c2 = st.columns([1, 1.5], vertical_alignment="center")
            with c1:
                theme.panel_title("품목별 시장 위험도")
            grp = c2.segmented_control("구분", ["전체", *GROUPS], default="전체", key="dash_grp",
                                       label_visibility="collapsed") or "전체"
            sub = (df if grp == "전체" else df[df["key"].isin(GROUPS[grp])]).sort_values("압력지수", ascending=False)
            st.caption("압력지수 0~100 · 높을수록 다음 입찰 시 단가 인상 압박이 큼")
            cl, cr = st.columns([3.4, 1], vertical_alignment="center")
            with cl:
                fig = go.Figure(go.Bar(
                    x=[n.replace(" ", "<br>", 1) for n in sub["품목"]], y=sub["압력지수"],
                    marker=dict(color=sub["color"], cornerradius=3),
                    text=[f"{v:.1f}" for v in sub["압력지수"]], textposition="outside", cliponaxis=False,
                    customdata=sub[["수준", "예상 인상률(%)", "분석"]],
                    hovertemplate="<b>%{x}</b><br>압력지수 %{y:.1f} · %{customdata[0]}<br>예상 인상률 %{customdata[1]:+.2f}%"
                                  "<br>%{customdata[2]}<extra></extra>",
                ))
                fig.update_yaxes(range=[0, 100], dtick=20)
                fig.update_xaxes(tickfont=dict(size=11))
                fig.update_layout(bargap=0.38, margin=dict(t=24, b=8, l=8, r=8))
                chart(fig, 330)
            with cr:
                prev, items = 0, []
                for upper, label, color, _msg in LEVELS:
                    items.append((color, f"{prev}~{min(upper, 100)} {label}"))
                    prev = upper
                theme.legend(items)

        a, b = st.columns([1.3, 1], gap="medium")
        with a, panel():
            theme.panel_title("최근 시장 이슈 TOP 5")
            top = []
            for key in df.sort_values("압력지수", ascending=False)["key"]:
                if news_by_cat[key]:
                    top.append(_issue(key, news_by_cat[key][0], quants[key]))
                if len(top) == 5:
                    break
            if top:
                theme.issue_table(top)
            else:
                st.caption("수집된 뉴스가 없습니다. '수집 현황·설정'에서 수집을 실행하세요.")
        with b, panel():
            theme.panel_title("이슈 카테고리 분포")
            counts = sorted(((CATEGORIES[k].name, len(v)) for k, v in news_by_cat.items()), key=lambda x: -x[1])
            total = sum(c for _, c in counts)
            if total:
                head, rest = counts[:4], sum(c for _, c in counts[4:])
                dist = head + ([("기타", rest)] if rest else [])
                pc1, pc2 = st.columns([1, 1], vertical_alignment="center")
                with pc1:
                    pie = go.Figure(go.Pie(labels=[d[0] for d in dist], values=[d[1] for d in dist], hole=0.64, sort=False,
                                           marker=dict(colors=theme.DONUT[:len(dist)], line=dict(color="#fff", width=2)),
                                           textinfo="none", hovertemplate="%{label} %{value}건 (%{percent})<extra></extra>"))
                    pie.update_layout(showlegend=False, margin=dict(t=4, b=4, l=4, r=4), annotations=[
                        dict(text=f"<b>{total}건</b>", x=0.5, y=0.54, showarrow=False, font=dict(size=22, color=theme.NAVY)),
                        dict(text="총 이슈", x=0.5, y=0.4, showarrow=False, font=dict(size=12, color=theme.MUTED))])
                    chart(pie, 250)
                with pc2:
                    theme.legend([(theme.DONUT[i], d[0], f"{d[1] / total:.0%}") for i, d in enumerate(dist)], round_=True)
            else:
                st.caption("수집된 뉴스가 없습니다.")

    with side:
        latest_news = sorted((_issue(k, n, quants[k]) for k in CATEGORIES for n in news_by_cat[k][:3]),
                             key=lambda i: i["ts"], reverse=True)
        picked, seen = [], set()
        for i in latest_news:  # 품목이 한쪽으로 쏠리지 않게 품목당 1건
            if i["cat"] not in seen:
                seen.add(i["cat"])
                picked.append(i)
            if len(picked) == 5:
                break
        theme.news_cards("오늘의 주요 뉴스", picked)

        with panel():
            theme.panel_title("주요 지표 동향 (최근 6년)")
            t1, t2, t3 = st.tabs(["최저임금", "CPI", "PPI"])
            with t1:
                mw = [r for r in collectors.minimum_wage_table() if r["yoy"] is not None][-6:]
                fig = go.Figure(go.Scatter(
                    x=[str(r["year"]) for r in mw], y=[r["yoy"] for r in mw], mode="lines+markers+text",
                    text=[f"{r['yoy']:.1f}" for r in mw], textposition="top center",
                    line=dict(color=theme.ACCENT, width=2), marker=dict(size=7, color=theme.ACCENT),
                    hovertemplate="%{x}년 전년 대비 %{y:+.1f}%<extra></extra>"))
                fig.update_yaxes(title="(단위: %)", range=[0, max(r["yoy"] for r in mw) * 1.3])
                fig.update_layout(margin=dict(t=12, b=8, l=8, r=8))
                chart(fig, 230)
            for tab, k, label in ((t2, "cpi", "소비자물가지수"), (t3, "ppi", "생산자물가지수")):
                with tab:
                    s = storage.get_indicator_series(k)
                    if len(s) >= 2:
                        d = pd.DataFrame(s).tail(24)
                        fig = go.Figure(go.Scatter(x=d["period"], y=d["value"], mode="lines+markers",
                                                   line=dict(color=theme.ACCENT, width=2), marker=dict(size=5),
                                                   hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
                        fig.update_layout(margin=dict(t=12, b=8, l=8, r=8), hovermode="x")
                        chart(fig, 230)
                    else:
                        st.caption(f"{label}: ECOS_API_KEY를 설정하면 시계열이 표시됩니다. "
                                   f"현재는 샘플 {MACRO[k + '_yoy']:+.1f}% (전년동월 대비)를 사용합니다.")

    q1, q2, q3 = st.columns(3, gap="small")
    q1.button("**AI 리포트 생성**  \n품목별 시장 분석 리포트를 자동으로 생성합니다.", key="qa_report", icon=":material/description:",
              on_click=_go, args=("품목 리포트",), width="stretch")
    q2.button("**시장동향 분석**  \n최저임금·노임·물가 지표와 추이를 확인하세요.", key="qa_market", icon=":material/monitoring:",
              on_click=_go, args=("시장 지표",), width="stretch")
    q3.button("**구매 영향 분석**  \nAI에게 구매 전략과 리스크를 질문하세요.", key="qa_chat", icon=":material/smart_toy:",
              on_click=_go, args=("AI 챗봇",), width="stretch")


# ---------- 품목 리포트 ----------
def render_report(payload, md_text, cat_name):
    q, r = payload["quant"], payload["report"]
    a, b = st.columns([1.2, 1], gap="medium")
    with a:
        theme.summary_card(q, r, LEVEL_ICON[q["level"]])
        st.markdown(f'<div class="pmi-headline">{theme.esc(r["headline"])}</div>', unsafe_allow_html=True)
        st.caption(r["adjustment_reason"])
    with b, panel():
        names = {"labor": "노무비", "material": "자재비", "expense": "경비"}
        wf = go.Figure(go.Waterfall(
            x=[names[k] for k in names] + ["AI 조정", "예상"],
            measure=["relative"] * 4 + ["total"],
            y=[q["contrib"][k] for k in names] + [q["ai_adjustment_pp"], 0],
            text=[f"{q['contrib'][k]:+.2f}" for k in names] + [f"{q['ai_adjustment_pp']:+.1f}", f"{q['expected']:+.2f}%"],
            textposition="outside", cliponaxis=False,
            increasing=dict(marker=dict(color=theme.ACCENT)), decreasing=dict(marker=dict(color=theme.MUTED)),
            totals=dict(marker=dict(color=theme.NAVY_600)), connector=dict(line=dict(color="#C3C2B7", width=1)),
            hovertemplate="%{x}: %{y:+.2f}%p<extra></extra>",
        ))
        wf.update_yaxes(title="%p", range=[min(0, q["expected"]) - 0.5, max(q["expected"], max(q["contrib"].values())) * 1.25 + 0.3])
        chart(wf, 270, "원가 구성비 가중 상승 기여도")

    st.markdown("#### 핵심 지표")
    st.dataframe(pd.DataFrame(r["key_items"]).rename(columns={
        "label": "지표", "value": "값", "detail": "설명", "source": "출처", "confidence": "신뢰도"}),
        hide_index=True, width="stretch")

    t1, t2 = st.columns(2, gap="medium")
    with t1:
        theme.card("📈 시장 동향", r["market_trends"])
    with t2:
        theme.card("⚖️ 관련 법규", r["regulations"])
    t1, t2 = st.columns(2, gap="medium")
    with t1:
        theme.card("🏭 공급시장", r["supply_market"])
    with t2:
        theme.card("⚠️ 리스크", r["risks"])
    theme.box("🎯 구매전략 제안", r["strategies"], fill=True)
    theme.box("🤝 협상 포인트", r["negotiation_points"])
    if payload.get("sources"):
        with st.expander(f"출처 {len(payload['sources'])}건"):
            for i, s in enumerate(payload["sources"], 1):
                st.markdown(f"{i}. [{s['title'] or s['url']}]({s['url']})")

    fname = f"PMI_{cat_name}_{date.today():%Y%m%d}"
    d1, d2, _ = st.columns([1, 1.3, 3])
    d1.download_button("⬇ Markdown", md_text, f"{fname}.md", "text/markdown", width="stretch")
    d2.download_button("⬇ HTML (인쇄→PDF)", report.to_html(md_text, fname), f"{fname}.html", "text/html", width="stretch")
    st.caption("※ AI가 공개 데이터를 기반으로 생성한 참고자료입니다. 최종 의사결정은 담당자 검토를 거쳐야 합니다.")


def page_report():
    hero("품목별 시장동향 리포트")
    key = st.selectbox("품목", list(CATEGORIES), format_func=lambda k: CATEGORIES[k].name)
    cat = CATEGORIES[key]
    st.caption(f"{cat.description} · 원가구성 노무비 {cat.cost_mix['labor']:.0%} / 자재비 {cat.cost_mix['material']:.0%} / 경비 {cat.cost_mix['expense']:.0%}")

    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    web = c2.toggle("Claude 웹검색으로 최신 시장정보 수집", value=True, disabled=not api_key,
                    help="협회·법규·공급사 뉴스를 웹에서 찾아 출처와 함께 반영합니다 (검색 비용 발생).")
    if c1.button("🤖 리포트 생성", type="primary", width="stretch"):
        with st.status("리포트 생성 중...", expanded=True) as status:
            try:
                r, q, sources, ai_used = analyzer.build_report(key, api_key, web, progress=status.write)
                payload = {"report": r.model_dump(), "quant": q, "sources": sources}
                md_text = report.to_markdown(payload["report"], q, sources, ai_used)
                storage.save_report(key, q["index"], ai_used, payload, md_text)
                status.update(label="완료", state="complete", expanded=False)
            except Exception as e:
                status.update(label="생성 실패", state="error")
                show_error("리포트 생성 실패", e)
                return

    latest = storage.latest_report(key)
    if latest:
        st.caption(f"최근 생성: {latest['created_at']} · {'Claude AI 분석' if latest['ai_used'] else '규칙 기반'}")
        render_report(latest["payload"], latest["markdown"], cat.name)
    else:
        st.info("아직 생성된 리포트가 없습니다. 아래는 정량 지표 기반 미리보기입니다.")
        r, q = analyzer.rule_based_report(key, storage.get_news(key, 15), storage.get_bids(key, 20))
        payload = {"report": r.model_dump(), "quant": q, "sources": []}
        render_report(payload, report.to_markdown(payload["report"], q, [], False), cat.name)


# ---------- AI 챗봇 ----------
def page_chat():
    openai_key = secret("OPENAI_API_KEY")
    model = secret("OPENAI_MODEL") or chatbot.DEFAULT_MODEL
    hero("외주용역·도급공사 AI 챗봇", theme.badge(f"모델 {model}", "navy"))
    if not openai_key:
        st.warning("OPENAI_API_KEY가 설정되지 않았습니다. 프로젝트 폴더의 .env 또는 Streamlit Secrets에 추가하세요.")
        return

    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    focus = c1.selectbox("관심 품목 (해당 품목의 최신 리포트·뉴스를 답변 근거로 추가)", [None, *CATEGORIES],
                         format_func=lambda k: "전체" if k is None else CATEGORIES[k].name)
    if c2.button("대화 초기화", width="stretch"):
        st.session_state.chat = []
    st.caption("PMI 압력지수·지표·리포트를 근거로 답변합니다. 답변은 참고용이며 계약·법률 판단은 담당 부서 검토가 필요합니다.")

    history = st.session_state.setdefault("chat", [])
    for m in history:
        st.chat_message(m["role"]).markdown(m["content"])

    question = st.chat_input("예: 비파괴검사 다음 입찰 시 단가 인상 요구에 어떻게 대응할까요?")
    if not history and not question:
        st.markdown("#### 추천 질문")
        cols = st.columns(2)
        for i, q in enumerate(chatbot.SUGGESTIONS):
            if cols[i % 2].button(q, key=f"sugg{i}", width="stretch"):
                question = q
    if not question:
        return

    history.append({"role": "user", "content": question})
    st.chat_message("user").markdown(question)
    with st.chat_message("assistant"):
        try:
            answer = st.write_stream(chatbot.stream_answer(openai_key, model, history, chatbot.build_context(focus)))
        except Exception as e:
            history.pop()
            show_error("답변 생성 실패", e)
            return
    history.append({"role": "assistant", "content": answer})


# ---------- 시장 지표 ----------
def page_indicators():
    hero("시장 지표")
    mw = pd.DataFrame(collectors.minimum_wage_table())
    a, b = st.columns(2, gap="medium")
    with a, panel():
        fig = go.Figure(go.Bar(x=mw["year"].astype(str), y=mw["wage"], marker=dict(color=theme.ACCENT, cornerradius=4),
                               customdata=mw["yoy"], hovertemplate="%{x}년 %{y:,}원<br>전년 대비 %{customdata:+.1f}%<extra></extra>"))
        fig.update_yaxes(tickformat=",")
        chart(fig, 360, "최저임금 (원/시간) — 고용노동부 고시")
    with b, panel():
        g = pd.DataFrame([{"직종": o, "상승률": collectors.wage_growth(o)} for o in WAGE_SAMPLE]).sort_values("상승률")
        fig = go.Figure(go.Bar(x=g["상승률"], y=g["직종"], orientation="h", marker=dict(color=theme.ACCENT, cornerradius=4),
                               text=g["상승률"].map(lambda v: f"{v:+.1f}%"), textposition="outside", cliponaxis=False,
                               hovertemplate="%{y}: %{x:+.2f}%<extra></extra>"))
        fig.add_vline(x=mw["yoy"].iloc[-1], line=dict(dash="dot", color=theme.NAVY_600, width=1),
                      annotation=dict(text=f"최저임금 {mw['yoy'].iloc[-1]:+.1f}%", font=dict(size=11, color=theme.NAVY_600)),
                      annotation_position="top")
        fig.update_xaxes(range=[0, g["상승률"].max() * 1.25])
        fig.update_layout(margin=dict(t=70))
        chart(fig, 360, "직종별 노임단가 상승률 (예시 기준표)")

    for key, label in [("cpi", "소비자물가지수 (ECOS)"), ("ppi", "생산자물가지수 (ECOS)")]:
        s = storage.get_indicator_series(key)
        if s:
            d = pd.DataFrame(s)
            with panel():
                fig = go.Figure(go.Scatter(x=d["period"], y=d["value"], mode="lines", line=dict(color=theme.ACCENT, width=2),
                                           hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
                fig.update_layout(hovermode="x")
                chart(fig, 280, label)
    if not storage.get_indicator_series("cpi"):
        st.info("ECOS_API_KEY를 설정하면 한국은행 CPI·PPI·기준금리 시계열이 표시됩니다.")

    with st.expander("원본 데이터"):
        st.dataframe(mw, hide_index=True)
        st.download_button("최저임금 CSV", mw.to_csv(index=False).encode("utf-8-sig"), "minimum_wage.csv")
        wages = pd.DataFrame(WAGE_SAMPLE).T
        st.dataframe(wages)
        st.download_button("노임단가 CSV", wages.to_csv().encode("utf-8-sig"), "wage_table.csv")


# ---------- 아카이브 ----------
def page_archive():
    hero("리포트 아카이브")
    rows = storage.list_reports()
    if not rows:
        st.info("생성된 리포트가 없습니다.")
        return
    df = pd.DataFrame(rows)
    df["품목"] = df["category"].map(lambda k: CATEGORIES[k].name)
    df["분석"] = df["ai_used"].map({1: "Claude AI", 0: "규칙 기반"})
    st.dataframe(df[["id", "created_at", "품목", "pressure_index", "분석"]].rename(
        columns={"created_at": "생성일시", "pressure_index": "압력지수"}), hide_index=True, width="stretch")
    st.markdown("#### 품목별 주차 비교")
    cat_key = st.selectbox("품목", sorted(df["category"].unique()), format_func=lambda k: CATEGORIES[k].name, key="cmp_cat")
    hist = df[df["category"] == cat_key].sort_values("id")
    hist = hist.assign(주차=pd.to_datetime(hist["created_at"]).dt.strftime("%G-W%V"), 변화=hist["pressure_index"].diff())
    last = hist.iloc[-1]
    c1, c2 = st.columns([1, 2.5], gap="medium")
    with c1:
        theme.kpi_cards([
            ("최신 압력지수", f"{last['pressure_index']:.1f}", f"{last['주차']} · {last['created_at'][:10]}"),
            ("직전 대비", "-" if pd.isna(last["변화"]) else f"{last['변화']:+.1f}p",
             "비교할 이전 리포트 없음" if pd.isna(last["변화"]) else f"이전 {hist.iloc[-2]['created_at'][:10]}"),
        ])
    with c2, panel():
        fig = go.Figure(go.Scatter(x=hist["created_at"], y=hist["pressure_index"], mode="lines+markers",
                                   line=dict(color=theme.ACCENT, width=2), marker=dict(size=8),
                                   customdata=hist["주차"], hovertemplate="%{customdata}<br>압력지수 %{y:.1f}<extra></extra>"))
        for y, lbl in ((30, "보통"), (55, "높음"), (75, "매우 높음")):
            fig.add_hline(y=y, line=dict(color="#C3C2B7", dash="dot", width=1),
                          annotation=dict(text=lbl, font=dict(size=11, color=theme.MUTED)), annotation_position="right")
        fig.update_yaxes(range=[0, 100], title="압력지수")
        fig.update_layout(hovermode="x")
        chart(fig, 260, f"{CATEGORIES[cat_key].name} 압력지수 추이")

    st.markdown("#### 리포트 보기")
    rid = st.selectbox("리포트 열기", df["id"], format_func=lambda i: f"#{i} {df.set_index('id').loc[i, '품목']} ({df.set_index('id').loc[i, 'created_at']})")
    rep = storage.get_report(int(rid))
    with panel():
        st.markdown(rep["markdown"])
    st.download_button("⬇ HTML", report.to_html(rep["markdown"], f"PMI_report_{rid}"), f"PMI_report_{rid}.html", "text/html")


# ---------- 수집 현황 ----------
def page_settings():
    hero("수집 현황·설정")
    if st.button("🔄 지금 수집 실행", type="primary"):
        with st.spinner("수집 중..."):
            collectors.collect_all(ecos_key, g2b_key)
        st.success("수집 완료")
    icon = {"success": "✅ 성공", "error": "❌ 오류", "skipped": "⏭ 건너뜀", "sample": "🧪 예시값"}
    st.markdown("#### 소스별 최근 수집")
    st.dataframe(pd.DataFrame(storage.collect_status()).assign(status=lambda d: d["status"].map(icon)).rename(
        columns={"source": "소스", "status": "상태", "count": "건수", "message": "메시지", "at": "시각"}),
        hide_index=True, width="stretch")

    st.markdown("#### API 키 상태")
    keys = [("ANTHROPIC_API_KEY", "Claude AI 분석·웹검색"), ("OPENAI_API_KEY", "AI 챗봇 (OpenAI)"),
            ("ECOS_API_KEY", "한국은행 물가·금리"), ("DATA_GO_KR_KEY", "나라장터 입찰공고 (공공데이터포털)")]
    theme.kpi_cards([(name, "설정됨" if secret(name) else "미설정", desc) for name, desc in keys])

    st.markdown("#### 수집 대상")
    st.dataframe(pd.DataFrame(SOURCES).drop(columns="key").rename(
        columns={"name": "기관", "url": "URL", "data": "수집 데이터", "method": "방식"}),
        hide_index=True, width="stretch", column_config={"URL": st.column_config.LinkColumn()})


{"대시보드": page_dashboard, "품목 리포트": page_report, "AI 챗봇": page_chat, "시장 지표": page_indicators,
 "리포트 아카이브": page_archive, "수집 현황·설정": page_settings}[page]()
