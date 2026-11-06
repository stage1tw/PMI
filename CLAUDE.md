# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PMI (Procurement Market Intelligence) — a Streamlit app for Hyundai Steel's procurement team that collects market data for outsourced services/subcontracted construction (NDT, maintenance, cleaning, security, etc.), computes a per-category **price pressure index**, and generates purchasing reports with Claude. `PRD.md` is the source of truth for requirements (Korean); `PROMPTS.md` holds the staged development prompts (skeleton → features → navy-tone UI → Playwright QA). UI text, reports, and docs are in Korean. The end-user manual (사용 매뉴얼) is a Claude Docs document, not a file in this repo: https://claude.ai/artifact/8Y81HwU6dvPcXtw1jbzcY1 — update it when screens or keys change.

## Commands

Windows dev environment; a venv lives in `.venv` (Python 3.15 locally — Streamlit Cloud / GitHub Actions use 3.12, so avoid 3.13+-only syntax). If `.venv` fails with `did not find executable at 'C:\Python315\python.exe'`, the base interpreter is gone: recreate it (`python -m venv .venv` with 3.12) or use any 3.12 venv with `requirements.txt` installed. Port 8501 is often taken by other local apps — pass `--server.port <free port>` and check with `netstat -ano` before assuming the page you see is PMI.

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
- `go()` waits for `.pmi-hero[data-page="<menu>"]` (set by `theme.hero(page=...)`), not for hero text — hero titles are free to change. Dashboard E2E pins the current layout: 4 `.pmi-kpi`, 3 Plotly charts keyless (bar + donut + minimum-wage line; CPI/PPI tabs only draw with ECOS data), TOP 5 as an HTML `.pmi-table` (no `stDataFrame`), and the bar chart's category names compared with whitespace stripped (labels wrap onto two lines). Update these deliberately when the dashboard changes.
- Streamlit caches imported `pmi.*` modules: after editing `pmi/theme.py` (CSS) or other `pmi/` files, restart the server — a browser reload alone keeps serving the old module.
- Responsive screenshots land in `tests/e2e/screenshots/` (gitignored).

Set `PYTHONIOENCODING=utf-8` when printing Korean from the Windows shell. `data/pmi.db` is created on first run; delete it to reset state (first app load re-runs `collect_all()` when `collect_log` is empty, ~15s for news RSS).

## Deployment & Git

- **Streamlit Cloud** deploys `stage1tw/PMI`, branch `main`, main file `app.py`, Python 3.12 (https://65spxsvbzljnzjadn38q8s.streamlit.app/). Secrets use the same key names as `.env`; as of 2026-11-06 only `OPENAI_API_KEY` and `DATA_GO_KR_KEY` are set there.
- Cloud wraps the app in an iframe, so for browser automation open `<app url>/~/+/` (the sidebar and `.pmi-*` elements are not in the top document otherwise).
- **After pushing changes under `pmi/`, Reboot the app** (Manage app → ⋮ → Reboot app). Cloud keeps the previously imported `pmi.*` modules while re-running the new `app.py`, which fails with `AttributeError` on any new helper (seen with `theme.sidebar_tagline`).
- **Never upload through the GitHub web UI**: it flattens folders. It already happened twice (`ModuleNotFoundError` for `pmi`, then for `anthropic` because `requirements.txt` was missing). `stage1tw/Procurement-Market-Intelligence` is such a flat 6-file copy and is not the deploy target. Use `git push`.
- `main` also receives the weekly `chore: weekly PMI report <date>` commit that changes the tracked `data/pmi.db`. Run `git pull --rebase origin main` before pushing, and never commit a locally generated `data/pmi.db` (move it out of the way first — an untracked local copy blocks the pull).
- Line endings: `.gitattributes` is `text=auto eol=lf`, but `app.py` and `CLAUDE.md` are stored with CRLF (every other file is LF). Check with `git ls-files --eol`.
- A push failing with `403 Permission to stage1tw/PMI.git denied to <other user>` means the cached Windows Git credential belongs to another account — sign in again as `stage1tw` rather than working around it.

## Architecture

Data flow: `collectors` → SQLite (`storage`) → `analyzer` → `report` → `app.py` (UI). The same pipeline runs in `scripts/weekly_job.py`, triggered weekly by `.github/workflows/weekly.yml`, which commits the updated `data/pmi.db` back to the repo (that commit is how the deployed Streamlit Cloud app receives new reports — the DB file is intentionally versioned).

- **`pmi/config.py`** — all domain knobs: `CATEGORIES` (cost mix labor/material/expense summing to 1.0, occupations, keywords, regulation keywords, `supply_concentration` 0–15), `MINIMUM_WAGE`, `WAGE_SAMPLE`, `MACRO_SAMPLE`, `SOURCES`, pressure `LEVELS` with status colors, and `MODEL`. `WAGE_SAMPLE` values are **demo placeholders**, not published figures — keep them labeled as samples anywhere they surface.
- **`pmi/analyzer.py`** — two layers that must stay consistent:
  1. `compute_pressure()` — deterministic, explainable index (the formula in PRD §5 F3): labor = 0.6×occupation wage growth + 0.4×minimum-wage growth, material = PPI, expense = CPI; weighted by cost mix; plus AI adjustment clipped to ±2pp; index = expected/8×70 + regulation risk + supply concentration, clipped 0–100.
  2. Claude: `research()` uses the `web_search_20260209` server tool (handles `pause_turn`) to gather unstructured info with source URLs; `analyze()` uses `client.beta.messages.parse(output_format=MarketReport)` for structured output, then re-runs `compute_pressure()` with the model's `regulation_risk` / `ai_adjustment_pp`. Both calls use `claude-opus-5-5`, adaptive thinking, and server-side refusal fallback (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`).
  - `rule_based_report()` produces the same `MarketReport` shape without an API key — the app must always work keyless. `build_report()` picks the path.
- **`pmi/collectors.py`** — ECOS (BOK), 나라장터 (data.go.kr), Google News RSS. Every source runs through `_run()` so one failure is logged to `collect_log` instead of aborting; missing keys log `skipped` and the app falls back to sample values (`macro_snapshot()["is_sample"]`). `fetch_g2b()` raises on data.go.kr error payloads (`OpenAPI_ServiceResponse` / `resultCode != "00"`) — they arrive as HTTP 403/400 JSON that used to be swallowed as "success, 0 rows"; keep errors visible in `collect_log` when touching it.
- **`pmi/storage.py`** — SQLite helpers; DB location is `PMI_DB_PATH` if set, else `data/pmi.db` (resolved at import time). Reports are stored as `payload` JSON `{"report": MarketReport.model_dump(), "quant": compute_pressure(...), "sources": [...]}` plus rendered markdown; the dashboard prefers the latest stored report's `quant` over a fresh rule-based computation.
- **`pmi/report.py`** — Markdown in the PRD §5 F5 template, and HTML via markdown-it for print/PDF.
- **`pmi/chatbot.py`** — Q&A chatbot on **OpenAI** (chat.completions streaming, model `OPENAI_MODEL`, default `gpt-5.5`), deliberately separate from the Claude-based analyzer. `build_context()` injects every category's pressure index plus, for the selected focus category, its latest stored report and news into the system prompt — answers are grounded in PMI data, so changes to the report payload shape must be mirrored here.
- **`app.py`** — single-file UI; sidebar radio (`key="menu"`) dispatches to `page_*` functions at the bottom; buttons navigate by setting `st.session_state["menu"]` in an `on_click` callback. The dashboard follows the design mock `Designer (3).png`: top bar, hero, 4 KPI cards, per-category risk bar with a 전체/도급공사/외주용역 segmented control (`GROUPS` in app.py is our own grouping, not in `config.py`), TOP 5 issue table, news-by-category donut, right-hand news column + indicator tabs, bottom shortcut buttons. All figures come from stored data — the mock's placeholder content (user name, notification badge, search box, week-over-week deltas) is deliberately not reproduced. Keys come from `secret()` (st.secrets → env var); `load_dotenv()` at the top loads a local `.env` (gitignored) before `pmi` imports. The Anthropic key can also be entered in the sidebar for the session. Chat history lives in `st.session_state.chat`. API failures go through `show_error()` → `friendly_error()`, which maps Anthropic/OpenAI auth, rate-limit and connection errors to actionable Korean messages and tucks the raw exception into an expander — route new API calls' errors through it. The archive page's "품목별 주차 비교" is computed from `storage.list_reports()` rows (pressure index per report + diff vs previous), not from a separate table.

## Conventions

- UI styling lives in `pmi/theme.py`: color constants (navy palette — placeholders until official CI colors are supplied; the logo is a text wordmark and the hero/news thumbnails are an inline SVG skyline / icon tiles standing in for photos), the single `inject_css()` stylesheet, HTML helpers (`topbar`, `hero`, `kpi_cards`, `panel_title`, `news_cards`, `issue_table`, `legend`, `summary_card`, `card`, `box`, `news_list`, `badge`, `level_pill`, `sidebar_*`) and the default Plotly template `"pmi"`. Pages call these helpers; don't add inline `<style>` elsewhere. Any AI/news text placed into HTML must go through `theme.esc()` / `theme.md_inline()`. `pmi/report.py` imports the same constants for the HTML report.
- Streamlit 1.67 DOM quirks the CSS depends on (re-check after upgrading): bordered containers have no testid, so use `panel()` in app.py (`st.container(border=True, key="panel_N")`) and style `[class*="st-key-panel_"]`; radio options are `stRadioGroup > div > label[stRadioOption]` (sidebar icons are `::before` Material Symbols ligatures by `nth-child`); tabs are `[data-testid="stTab"][data-selected]`; segmented control buttons use `data-variant`/`data-selected`; `st.button(key="qa_*")` cards are styled via `.st-key-qa_*`.
- Charts: Plotly via `chart()` in app.py, which passes `theme=None` so the `"pmi"` template (transparent background, `automargin`) applies instead of Streamlit's own chart theme; single-series color `theme.ACCENT`; status colors from `LEVELS` are reserved for pressure levels and always paired with `LEVEL_ICON`/label text.
- `app.py` (and `CLAUDE.md`) keep CRLF line endings. `sed -i` or a read/write script without `newline=""` silently converts them to LF and turns the whole file into one giant diff — restore CRLF before finishing (`git diff --numstat -- app.py` should show only real changes; the Edit tool preserves CRLF).
- Use `width="stretch"` rather than the deprecated `use_container_width`.
- Never let the AI invent numbers: prompts require sources, unsourced items get `source="추정"`, `confidence="low"`. Preserve this when editing prompts.
- Secrets: `ANTHROPIC_API_KEY`, `ECOS_API_KEY`, `DATA_GO_KR_KEY`, `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`) (template in `.streamlit/secrets.toml.example`; same names in GitHub Actions secrets).

## Known gaps vs PRD

Verified in the stage-4 review; don't assume these exist:
- §10 acceptance: real Claude web-search report path is untested end-to-end (no `ANTHROPIC_API_KEY` in the dev env or on Cloud). Streamlit Cloud is deployed and all six pages load without exceptions (checked 2026-11-06), but it runs largely keyless: Anthropic and ECOS keys are unset (CPI/PPI stay sample, "샘플 데이터 포함" badge). Only the OpenAI key is verified working (`GET /v1/models` → 200, default model `gpt-5.5` listed); no chat completion was sent.
- KOSIS (통계청) API is not integrated — covered only by Claude web search (`SOURCES` says "확장 예정").
- F4-4 week comparison is minimal (index trend + delta only, no report-body diff); F1-4 custom categories (P2) not implemented; `Category.examples` is an unused field.
- 나라장터 collection never succeeded: as of 2026-11-06 (still failing ~5 h after the key was issued, locally and on Cloud) the `DATA_GO_KR_KEY` is rejected with `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` (HTTP 403) on every operation of `/1230000/ad/BidPublicInfoService` over http and https (the endpoint exists; `BidPublicInfoService04/05` do not). The key format is fine (64 hex chars, no `%`/quotes), so it is not registered for that service on data.go.kr — activation lag is getting less likely than a key/service mismatch; copy the key from the service's own detail page or ask data.go.kr (1566-0025). Not fixable in code. Until it works, bids stay empty, `collect_log` shows the error, and reports say "나라장터 데이터 미수집".
- `.streamlit/config.toml` theme colors are still the old palette (only the custom CSS uses the new one); the dashboard bars all read "보통" yellow while every category sits in the 30–55 band.
- Category news keywords are noisy (e.g. "NDT 검사" pulls unrelated stock news) — a data-quality issue in `config.CATEGORIES[*].keywords`, not code.
