# PMI — 도급공사·외주용역 시장동향 AI 리포터

현대제철 구매부서용 Procurement Market Intelligence 플랫폼 (설계 문서: [PRD.md](PRD.md)).

## 로컬 실행
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # 키 입력 (선택)
streamlit run app.py
```
키가 하나도 없어도 실행됩니다 (규칙 기반 리포트 + 샘플 지표).

| 키 | 용도 | 발급 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude AI 분석 + 웹검색 | https://console.anthropic.com |
| `ECOS_API_KEY` | 한국은행 CPI·PPI·기준금리 | https://ecos.bok.or.kr/api/ |
| `DATA_GO_KR_KEY` | 나라장터 입찰공고 | https://www.data.go.kr (조달청_나라장터 입찰공고정보서비스) |
| `OPENAI_API_KEY` | AI 챗봇 (선택: `OPENAI_MODEL`, 기본 `gpt-5.5`) | https://platform.openai.com |

로컬에서는 키를 프로젝트 폴더의 `.env` 파일에 `OPENAI_API_KEY=...` 형식으로 넣어도 됩니다 (`.gitignore` 로 제외됨).

## 테스트
```bash
pip install -r requirements-dev.txt && playwright install chromium
pytest                       # 단위(산식) + Playwright E2E, 실제 data/pmi.db 는 건드리지 않음
```

## Streamlit Community Cloud 배포
1. GitHub에 **Private** 저장소를 만들고 이 폴더를 push (`.streamlit/secrets.toml` 은 `.gitignore` 로 제외됨)
2. https://share.streamlit.io → **Create app** → 저장소 / 브랜치 `main` / Main file `app.py`
3. **Advanced settings** → Python 3.12 선택, **Secrets** 에 `secrets.toml.example` 형식으로 키 입력
4. Deploy → 발급된 URL 접속
5. App settings → **Sharing** 에서 "Only specific people" 로 사내 이메일만 허용

## 주간 자동 리포트
`.github/workflows/weekly.yml` 이 매주 월요일 07:00(KST)에 수집·분석 후 `data/pmi.db` 를 커밋하고,
Streamlit Cloud 가 이를 감지해 앱을 갱신합니다. GitHub 저장소 Settings → Secrets and variables → Actions 에
같은 키 3개를 등록하세요. 수동 실행: `python scripts/weekly_job.py` (`--no-web` 시 웹검색 생략).

## 운영 전 교체할 값
- `pmi/config.py` `WAGE_SAMPLE` — **예시값**입니다. 대한건설협회 임금실태조사·엔지니어링협회 노임단가 공표값으로 교체
- `MINIMUM_WAGE` — 2027년 최저임금 고시값 추가
- 품목별 `cost_mix`(원가 구성비), `supply_concentration` — 실제 계약 원가내역 기준으로 조정
