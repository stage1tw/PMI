# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PMI (Procurement Market Intelligence) — a Streamlit app for Hyundai Steel's procurement team that collects market data for outsourced services/subcontracted construction (NDT, maintenance, cleaning, security, etc.), computes a per-category **price pressure index**, and generates purchasing reports with Claude. `PRD.md` is the source of truth for requirements (Korean); `PROMPTS.md` holds the staged development prompts (skeleton → features → navy-tone UI → Playwright QA). UI text, reports, and docs are in Korean.

## Commands

Windows dev environment; a venv lives in `.venv` (Python 3.15 locally — Streamlit Cloud / GitHub Actions use 3.12, so avoid 3.13+-only syntax).

```bash
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/streamlit run app.py                      # http://localhost:8501
.venv/Scripts/python scripts/weekly_job.py [--no-web]   # batch: collect + build reports for all categories
```

Tests (pytest; no linter configured):

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt && .venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m pytest                                   # all (~3 min, E2E dominates)
.venv/Scripts/python -m pytest tests/test_analyzer.py            # formula unit tests only (seconds)
.venv/Scripts/python -m pytest "tests/e2e/test_app.py::test_report_generation_per_category[chromium-ndt]"  # single case
```

- `tests/conftest.py` points `PMI_DB_PATH` at a temp file before `pmi.storage` is imported; never let tests touch `data/pmi.db`.
- `tests/e2e/conftest.py` launches its own Streamlit server on a free port with all API keys set to `""` (empty strings stop `load_dotenv()` from injecting `.env`), so E2E runs are keyless by design. `test_ai_report_has_sources` runs only if `ANTHROPIC_API_KEY` is in the test process env.
- Streamlit renders asynchronously: use the `wait_idle`/`go`/`select`/`generate_report` helpers and Playwright `expect(...)` (auto-retrying), not immediate `is_visible()`/`count()` checks — those caused the only flaky failures so far.
- `tests/test_analyzer.py` pins hand-calculated NDT values (index 54.9, expected +3.87%) derived from `WAGE_SAMPLE`/`MACRO_SAMPLE`; update them deliberately when those tables change.
- Responsive screenshots land in `tests/e2e/screenshots/` (gitignored).

Set `PYTHONIOENCODING=utf-8` when printing Korean from the Windows shell. `data/pmi.db` is created on first run; delete it to reset state (first app load re-runs `collect_all()` when `collect_log` is empty, ~15s for news RSS).

## Architecture

Data flow: `collectors` → SQLite (`storage`) → `analyzer` → `report` → `app.py` (UI). The same pipeline runs in `scripts/weekly_job.py`, triggered weekly by `.github/workflows/weekly.yml`, which commits the updated `data/pmi.db` back to the repo (that commit is how the deployed Streamlit Cloud app receives new reports — the DB file is intentionally versioned).

- **`pmi/config.py`** — all domain knobs: `CATEGORIES` (cost mix labor/material/expense summing to 1.0, occupations, keywords, regulation keywords, `supply_concentration` 0–15), `MINIMUM_WAGE`, `WAGE_SAMPLE`, `MACRO_SAMPLE`, `SOURCES`, pressure `LEVELS` with status colors, and `MODEL`. `WAGE_SAMPLE` values are **demo placeholders**, not published figures — keep them labeled as samples anywhere they surface.
- **`pmi/analyzer.py`** — two layers that must stay consistent:
  1. `compute_pressure()` — deterministic, explainable index (the formula in PRD §5 F3): labor = 0.6×occupation wage growth + 0.4×minimum-wage growth, material = PPI, expense = CPI; weighted by cost mix; plus AI adjustment clipped to ±2pp; index = expected/8×70 + regulation risk + supply concentration, clipped 0–100.
  2. Claude: `research()` uses the `web_search_20260209` server tool (handles `pause_turn`) to gather unstructured info with source URLs; `analyze()` uses `client.beta.messages.parse(output_format=MarketReport)` for structured output, then re-runs `compute_pressure()` with the model's `regulation_risk` / `ai_adjustment_pp`. Both calls use `claude-opus-5-5`, adaptive thinking, and server-side refusal fallback (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`).
  - `rule_based_report()` produces the same `MarketReport` shape without an API key — the app must always work keyless. `build_report()` picks the path.
- **`pmi/collectors.py`** — ECOS (BOK), 나라장터 (data.go.kr), Google News RSS. Every source runs through `_run()` so one failure is logged to `collect_log` instead of aborting; missing keys log `skipped` and the app falls back to sample values (`macro_snapshot()["is_sample"]`).
- **`pmi/storage.py`** — SQLite helpers; DB location is `PMI_DB_PATH` if set, else `data/pmi.db` (resolved at import time). Reports are stored as `payload` JSON `{"report": MarketReport.model_dump(), "quant": compute_pressure(...), "sources": [...]}` plus rendered markdown; the dashboard prefers the latest stored report's `quant` over a fresh rule-based computation.
- **`pmi/report.py`** — Markdown in the PRD §5 F5 template, and HTML via markdown-it for print/PDF.
- **`pmi/chatbot.py`** — Q&A chatbot on **OpenAI** (chat.completions streaming, model `OPENAI_MODEL`, default `gpt-5.5`), deliberately separate from the Claude-based analyzer. `build_context()` injects every category's pressure index plus, for the selected focus category, its latest stored report and news into the system prompt — answers are grounded in PMI data, so changes to the report payload shape must be mirrored here.
- **`app.py`** — single-file UI; sidebar radio dispatches to `page_*` functions at the bottom. Keys come from `secret()` (st.secrets → env var); `load_dotenv()` at the top loads a local `.env` (gitignored) before `pmi` imports. The Anthropic key can also be entered in the sidebar for the session. Chat history lives in `st.session_state.chat`. API failures go through `show_error()` → `friendly_error()`, which maps Anthropic/OpenAI auth, rate-limit and connection errors to actionable Korean messages and tucks the raw exception into an expander — route new API calls' errors through it. The archive page's "품목별 주차 비교" is computed from `storage.list_reports()` rows (pressure index per report + diff vs previous), not from a separate table.

## Conventions

- UI styling lives in `pmi/theme.py`: color constants (navy palette — placeholders until official CI colors are supplied), the single `inject_css()` stylesheet, HTML helpers (`hero`, `kpi_cards`, `summary_card`, `card`, `box`, `news_list`, `badge`) and the default Plotly template `"pmi"`. Pages call these helpers; don't add inline `<style>` elsewhere. Any AI/news text placed into HTML must go through `theme.esc()` / `theme.md_inline()`. The CSS targets Streamlit `data-testid` selectors (`stSidebar`, `stRadioOption`, `stIconMaterial`…), which can change between Streamlit versions — re-check the sidebar after upgrading. `pmi/report.py` imports the same constants for the HTML report.
- Charts: Plotly via `chart()` in app.py (uses the `"pmi"` template), single-series color `theme.ACCENT`; status colors from `LEVELS` are reserved for pressure levels and always paired with `LEVEL_ICON` + label.
- Use `width="stretch"` rather than the deprecated `use_container_width`.
- Never let the AI invent numbers: prompts require sources, unsourced items get `source="추정"`, `confidence="low"`. Preserve this when editing prompts.
- Secrets: `ANTHROPIC_API_KEY`, `ECOS_API_KEY`, `DATA_GO_KR_KEY`, `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`) (template in `.streamlit/secrets.toml.example`; same names in GitHub Actions secrets).

## Known gaps vs PRD

Verified in the stage-4 review; don't assume these exist:
- §10 acceptance: real Claude web-search report path is untested end-to-end (no `ANTHROPIC_API_KEY` in the dev env); Streamlit Cloud deployment not done.
- KOSIS (통계청) API is not integrated — covered only by Claude web search (`SOURCES` says "확장 예정").
- F4-4 week comparison is minimal (index trend + delta only, no report-body diff); F1-4 custom categories (P2) not implemented; `Category.examples` is an unused field.
- Category news keywords are noisy (e.g. "NDT 검사" pulls unrelated stock news) — a data-quality issue in `config.CATEGORIES[*].keywords`, not code.
