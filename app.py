"""Procurement Market Intelligence (PMI) — 도급공사/외주용역 시장동향 AI 리포터."""
import os
from datetime import date

import anthropic
import openai
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # 로컬 .env (OPENAI_API_KEY 등) → 환경변수

from pmi import analyzer, chatbot, collectors, report, storage, theme  # noqa: E402
from pmi.config import CATEGORIES, LEVEL_ICON, MINIMUM_WAGE, SOURCES, WAGE_SAMPLE  # noqa: E402

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


def chart(fig, height=360, title=None):
    fig.update_layout(height=height, title=title)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


# ---------- 사이드바 ----------
with st.sidebar:
    theme.sidebar_brand()
    page = st.radio("메뉴", ["대시보드", "품목 리포트", "AI 챗봇", "시장 지표", "리포트 아카이브", "수집 현황·설정"],
                    label_visibility="collapsed")
    st.divider()
    api_key = secret("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = st.text_input("Anthropic API Key (세션 한정)", type="password",
                                help="입력하지 않으면 규칙 기반 리포트로 동작합니다.") or None
    theme.sidebar_status([("Claude 분석", bool(api_key)), ("AI 챗봇", bool(secret("OPENAI_API_KEY")))])
    ecos_key, g2b_key = secret("ECOS_API_KEY"), secret("DATA_GO_KR_KEY")

if not storage.collect_status():
    with st.spinner("최초 실행 — 시장 데이터 수집 중..."):
        collectors.collect_all(ecos_key, g2b_key)

MACRO = collectors.macro_snapshot()


def hero(title, *extra):
    data = theme.badge("샘플 데이터 포함", "warn", "⚠ ") if MACRO["is_sample"] else theme.badge("실데이터", "on", "● ")
    theme.hero(title, [f"기준일 {date.today():%Y-%m-%d}", data, *extra])


def current_pressure(key):
    """저장된 최신 리포트(AI 반영)가 있으면 그 지수, 없으면 규칙 기반."""
    latest = storage.latest_report(key)
    if latest:
        p = latest["payload"]
        return p["quant"], p["report"], latest
    return analyzer.compute_pressure(key), None, None


# ---------- 대시보드 ----------
def page_dashboard():
    hero("전사 외주용역 원가상승 압력 대시보드", "압력지수 0~100 · 높을수록 다음 입찰 시 단가 인상 압박이 큼")

    rows = []
    for key, cat in CATEGORIES.items():
        q, r, latest = current_pressure(key)
        rows.append({
            "key": key, "품목": cat.name, "압력지수": q["index"], "수준": q["level"], "color": q["color"],
            "예상 인상률(%)": q["expected"],
            "분석": ("AI " if latest and latest["ai_used"] else "규칙 ") + (latest["created_at"][:10] if latest else "실시간"),
        })
    df = pd.DataFrame(rows).sort_values("압력지수")
    mw = collectors.yoy(MINIMUM_WAGE, max(MINIMUM_WAGE))
    occ = [v for v in (collectors.wage_growth(o) for o in WAGE_SAMPLE) if v is not None]
    sample = " (샘플)" if MACRO["is_sample"] else ""
    theme.kpi_cards([
        ("최저임금 인상률", f"{mw:+.1f}%", f"{max(MINIMUM_WAGE)}년 {MINIMUM_WAGE[max(MINIMUM_WAGE)]:,}원/시간"),
        ("직종 노임 상승률", f"{sum(occ) / len(occ):+.1f}%", "노임단가 평균 (예시 기준표)"),
        ("소비자물가 CPI", f"{MACRO['cpi_yoy']:+.1f}%", "전년동월 대비" + sample),
        ("생산자물가 PPI", f"{MACRO['ppi_yoy']:+.1f}%", "전년동월 대비" + sample),
        ("고위험 품목", f"{(df['압력지수'] >= 55).sum()} / {len(df)}", "압력지수 55 이상"),
    ])

    left, right = st.columns([1.35, 1], gap="medium")
    with left, st.container(border=True):
        fig = go.Figure(go.Bar(
            x=df["압력지수"], y=df["품목"], orientation="h",
            marker=dict(color=df["color"], cornerradius=4),
            text=[f"{LEVEL_ICON[l]} {v:.1f} {l}" for v, l in zip(df["압력지수"], df["수준"])],
            textposition="outside", cliponaxis=False,
            customdata=df[["예상 인상률(%)", "분석"]],
            hovertemplate="<b>%{y}</b><br>압력지수 %{x:.1f}<br>예상 인상률 %{customdata[0]:+.2f}%<br>%{customdata[1]}<extra></extra>",
        ))
        for x, lbl in ((30, "보통"), (55, "높음"), (75, "매우 높음")):
            fig.add_vline(x=x, line=dict(color="#C3C2B7", dash="dot", width=1),
                          annotation=dict(text=lbl, font=dict(size=11, color=theme.MUTED)), annotation_position="top")
        fig.update_xaxes(range=[0, 115], title="압력지수")
        chart(fig, 420, "품목별 단가 인상 압력지수")
    with right, st.container(border=True):
        st.markdown("#### 품목 요약")
        show = df.sort_values("압력지수", ascending=False)[["품목", "압력지수", "수준", "예상 인상률(%)"]]
        show["수준"] = show["수준"].map(lambda l: f"{LEVEL_ICON[l]} {l}")
        st.dataframe(show, hide_index=True, width="stretch",
                     column_config={"품목": st.column_config.TextColumn(width=125),
                                    "압력지수": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f", width=95),
                                    "수준": st.column_config.TextColumn(width=72),
                                    "예상 인상률(%)": st.column_config.NumberColumn("인상률", format="%+.2f%%", width=68)})

    st.markdown("#### 이번 주 주요 이슈")
    news = [(CATEGORIES[k].name, n) for k in CATEGORIES for n in storage.get_news(k, 2)]
    if news:
        theme.news_list(news[:10])
    else:
        st.caption("수집된 뉴스가 없습니다. '수집 현황·설정'에서 수집을 실행하세요.")


# ---------- 품목 리포트 ----------
def render_report(payload, md_text, cat_name):
    q, r = payload["quant"], payload["report"]
    a, b = st.columns([1.2, 1], gap="medium")
    with a:
        theme.summary_card(q, r, LEVEL_ICON[q["level"]])
        st.markdown(f'<div class="pmi-headline">{theme.esc(r["headline"])}</div>', unsafe_allow_html=True)
        st.caption(r["adjustment_reason"])
    with b, st.container(border=True):
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
    with a, st.container(border=True):
        fig = go.Figure(go.Bar(x=mw["year"].astype(str), y=mw["wage"], marker=dict(color=theme.ACCENT, cornerradius=4),
                               customdata=mw["yoy"], hovertemplate="%{x}년 %{y:,}원<br>전년 대비 %{customdata:+.1f}%<extra></extra>"))
        fig.update_yaxes(tickformat=",")
        chart(fig, 360, "최저임금 (원/시간) — 고용노동부 고시")
    with b, st.container(border=True):
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
            with st.container(border=True):
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
    with c2, st.container(border=True):
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
    with st.container(border=True):
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
