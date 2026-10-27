# PMI 단계별 개발 프롬프트

각 단계는 새 Claude Code 세션에 그대로 붙여넣어 쓸 수 있도록 작성했다.
모든 단계는 같은 폴더(`외주용역 PMI/`)의 `PRD.md` 를 기준 문서로 삼는다.
한 단계가 끝나면 결과를 확인하고 다음 단계로 넘어간다.

---

## 1단계 — 기초 뼈대 구성

```
PRD.md 를 먼저 끝까지 읽고, "Procurement Market Intelligence(PMI)" Streamlit 앱의 기초 뼈대만 만들어줘.
이번 단계에서는 기능 구현보다 구조와 실행 가능성이 목표다.

[만들 것]
1. 디렉터리 구조 (PRD 7장 기준)
   app.py / pmi/{__init__,config,storage,collectors,analyzer,report}.py / scripts/weekly_job.py
   .streamlit/{config.toml, secrets.toml.example} / data/ / requirements.txt / .gitignore / README.md
2. pmi/config.py
   - 품목 8개(비파괴검사(NDT), 설비 정비, 플랜트 보수공사, 건축·토목 도급, 청소·미화, 경비·보안, 안전관리 대행, 엔지니어링 용역)를
     dataclass 로 정의: key, 이름, 원가구성비(노무비/자재비/경비, 합계 1.0), 관련 직종, 검색 키워드, 관련 법규 키워드, 공급집중도(0~15)
   - 수집 대상 9개 기관 + 뉴스 목록 (이름, URL, 수집 데이터, 수집 방식)
   - 최저임금 연도별 고시값 (2020~2026), 압력지수 구간(낮음/보통/높음/매우 높음)
3. pmi/storage.py — SQLite(data/pmi.db) 테이블: indicators, news, bids, reports, collect_log 와 기본 CRUD 함수
4. app.py — 사이드바 메뉴 5개(대시보드, 품목 리포트, 시장 지표, 리포트 아카이브, 수집 현황·설정)와
   각 페이지 함수의 placeholder(제목 + "구현 예정" 문구)만
5. API 키는 st.secrets → 환경변수 순서로 읽는 secret() 헬퍼. 키(ANTHROPIC_API_KEY, ECOS_API_KEY, DATA_GO_KR_KEY)가 없어도 앱이 떠야 한다.
6. requirements.txt: streamlit, anthropic, pandas, plotly, feedparser, requests, pydantic, markdown-it-py

[규칙]
- .venv 를 만들어 설치하고 `streamlit run app.py` 로 실제 실행해 5개 메뉴가 오류 없이 열리는지 확인
- secrets.toml 은 .gitignore 에 포함, 예시 파일만 커밋 대상
- 아직 외부 API 호출·AI 호출 코드는 작성하지 말 것 (함수 시그니처와 docstring 만)

[완료 기준] 앱이 실행되고 메뉴 전환 시 예외가 없음. 만든 파일 목록과 각 역할을 요약해서 보고.
```

---

## 2단계 — 기능 추가

```
PRD.md 의 5장(기능 요구사항) P0·P1 항목을 1단계 뼈대 위에 구현해줘.

[데이터 수집 — pmi/collectors.py]
- 최저임금 기준표 → 전년 대비 상승률 계산
- 직종별 노임단가 기준표 (데모용 예시값임을 코드와 화면에 명시, is_sample 표시)
- 한국은행 ECOS OpenAPI: CPI(901Y009), PPI(404Y014), 기준금리(722Y001) — 키 없으면 샘플값으로 대체하고 샘플임을 표시
- 나라장터 공공데이터포털 입찰공고 API (용역 키워드 검색) — 키 없으면 건너뜀
- Google News RSS 품목 키워드 뉴스
- collect_all(): 소스별 try/except 로 한 소스 실패가 전체를 멈추지 않게 하고, 결과를 collect_log 에 기록 (success/error/skipped/sample)

[분석 엔진 — pmi/analyzer.py]
- PRD 의 Price Pressure Index 산출식을 그대로 구현 (노무비 = 0.6×직종 노임 + 0.4×최저임금, 자재비 = PPI, 경비 = CPI,
  원가구성비 가중합 + AI 조정 ±2%p, 법규리스크 0~15, 공급집중도 0~15, 0~100 clip)
- Claude 연동 (Anthropic Python SDK, 모델 claude-opus-5-5, adaptive thinking):
  1) research(): web_search 서버 도구로 PRD 4장 기관들의 최근 시장동향·노임·최저임금·법규·공급사 뉴스를 조사, 출처 URL 수집, pause_turn 처리
  2) analyze(): 정량지표 + 리서치 + 뉴스 + 나라장터 공고를 넣고 pydantic 스키마(MarketReport)로 구조화 출력
     (headline, 예상 인상률 하단/상단, AI 조정폭과 사유, 법규리스크, key_items[지표/값/설명/출처/신뢰도], 시장동향, 법규, 공급시장,
      구매전략, 협상포인트, 리스크)
  3) 할루시네이션 방지: "제공 자료에 없는 수치 생성 금지, 출처 없으면 source='추정', confidence='low'"
  4) stop_reason == "refusal" 처리
- rule_based_report(): API 키가 없을 때 같은 MarketReport 형식을 정량지표만으로 생성

[리포트 — pmi/report.py]
- PRD 5장 F5 표준 템플릿대로 Markdown 생성 (주차, 종합판단, 핵심지표 표, 법규, 공급시장, 구매전략, 원가분해, 출처, 면책문구)
- Markdown → 인쇄 가능한 HTML 변환

[화면 — app.py]
- 대시보드: KPI 타일(최저임금, 노임 평균, CPI, PPI, 고위험 품목 수), 품목별 압력지수 가로 막대, 품목 요약 표, 주요 뉴스
- 품목 리포트: 품목 선택, "리포트 생성" 버튼(진행 상태 표시), 압력 게이지, 원가 기여도 Waterfall, 결과 섹션, MD/HTML 다운로드
- 시장 지표: 최저임금 추이, 직종별 노임 상승률, ECOS 시계열, 원본 표 + CSV 다운로드
- 리포트 아카이브: 생성 이력 표 + 선택해서 보기
- 수집 현황·설정: 수동 수집 버튼, 소스별 최근 상태, API 키 설정 여부
- 최초 실행 시 수집 로그가 비어 있으면 자동 수집 1회

[배치]
- scripts/weekly_job.py: 수집 → 전 품목 리포트 생성 → DB 저장 (--no-web 옵션)
- .github/workflows/weekly.yml: 매주 월 07:00 KST, Secrets 로 키 주입, data/pmi.db 커밋

[완료 기준]
- API 키 없이 모든 페이지가 동작하고 NDT 리포트가 생성·다운로드됨
- streamlit.testing AppTest 로 5개 페이지와 리포트 생성 버튼을 자동 점검해 예외 0건
- 구현한 기능을 PRD 요구사항 ID(F1-1 …)와 매핑한 표로 보고
```

---

## 3단계 — UI 디자인 (현대제철 남색 톤)

```
기능은 유지한 채 PMI 앱의 UI를 현대제철 기업 이미지에 맞는 남색(Navy) 톤의 신뢰감 있는 B2B 대시보드로 다듬어줘.

[컬러 시스템] — 공식 CI 색상값을 받으면 그것으로 교체할 수 있게 상수로 분리 (pmi/theme.py)
- Primary Navy  #0B2A4A (헤더·사이드바 배경)
- Navy 600      #003876 (강조 텍스트, 버튼)
- Accent Blue   #2A78D6 (차트 기본 시리즈, 링크)
- Surface       #F5F7FA (본문 배경), Card #FFFFFF, Border #DDE3EC
- Text          #0B0B0B / Secondary #52514E
- 상태색은 압력 수준 전용으로만 사용: 낮음 #0CA30C, 보통 #FAB219, 높음 #EC835A, 매우 높음 #D03B3B
  (상태색은 항상 아이콘+라벨과 함께, 색만으로 의미 전달 금지)

[적용 범위]
1. .streamlit/config.toml 테마 (primaryColor, backgroundColor, secondaryBackgroundColor, textColor, font)
2. 사이드바: 남색 배경 + 흰색 텍스트, 상단에 "PMI | Procurement Market Intelligence" 로고 영역, 하단에 AI 활성 상태 배지
3. 페이지 상단 헤더 바: 남색 그라데이션 배너에 페이지 제목, 기준일, 데이터 출처 상태(실데이터/샘플) 배지
4. KPI 타일을 카드 컴포넌트로: 흰 카드, 얇은 테두리, 좌측 남색 4px 강조선, 라벨/값/증감 위계 정리, 값 잘림(…) 없게
5. Plotly 공통 템플릿: 투명 배경, 옅은 그리드, 한글 폰트(Pretendard 또는 Noto Sans KR, Google Fonts),
   막대 끝 4px 라운드, 단일 시리즈는 Accent Blue, 범례/툴팁 한국어, 이중 Y축 금지
6. 리포트 화면: 종합판단을 큰 카드(압력지수 + 수준 배지 + 예상 인상률 범위)로, 구매전략·협상포인트는 남색 테두리 박스
7. HTML 리포트 출력도 같은 남색 톤 (표지 헤더, 표 헤더 남색, 인쇄 시 A4 여백)
8. 반응형: 1024px 이하에서 컬럼이 세로로 쌓이고 텍스트·숫자가 잘리지 않을 것

[규칙]
- CSS 는 st.markdown(<style>) 한 곳(pmi/theme.py 의 inject_css())에서만 주입, 페이지 코드에 인라인 스타일 흩뿌리지 말 것
- 현대제철 로고 이미지는 사용하지 말고 텍스트 워드마크로 대체 (CI 사용 승인 필요)
- 변경 후 앱을 실행해 5개 페이지의 스크린샷을 찍어 확인하고, 잘림·겹침·대비 문제를 고친 뒤 전/후 요약 보고
```

---

## 4단계 — PRD 기준 테스트·검토 및 버그 수정 (Playwright)

```
PMI 앱이 PRD.md 대로 구현됐는지 Playwright 로 E2E 검증하고, 발견한 버그를 수정해줘.

[준비]
- `streamlit run app.py --server.port 8599 --server.headless true` 를 백그라운드로 실행
- tests/e2e/ 에 pytest + playwright(python) 테스트 작성 (pip install pytest pytest-playwright && playwright install chromium)
- 테스트 전 data/pmi.db 를 임시 경로로 분리해 실제 데이터를 오염시키지 말 것 (환경변수 PMI_DB_PATH 지원 추가)
- Streamlit 은 렌더링이 비동기이므로 고정 sleep 대신 텍스트/요소 대기(wait_for) 사용

[검증 시나리오 — PRD 10장 수용 기준 + 5장 기능]
1. 앱 기동: 키 없이 실행 → 사이드바 5개 메뉴 표시, "샘플" 안내 문구 노출 (수용기준 2)
2. 대시보드: KPI 타일 5개, 8개 품목 압력지수 막대·표 모두 표시, 값 잘림 없음 (F4-1, 수용기준 1)
3. 품목 리포트: 8개 품목 각각 선택 → "리포트 생성" → 압력지수·예상 인상률 범위·핵심지표 표·구매전략 표시 (F3, F4-2)
4. 다운로드: Markdown·HTML 다운로드 파일이 생성되고, 표준 템플릿 섹션(종합 판단, 핵심 지표, 구매전략 제안, 면책문구) 포함 (F5, 수용기준 4)
5. 시장 지표: 차트 렌더링, CSV 다운로드 (F4-3)
6. 리포트 아카이브: 3번에서 만든 리포트가 이력에 쌓이고 열람 가능 (F4-4)
7. 수집 현황: "지금 수집 실행" 후 소스별 상태·시각 갱신, API 키 상태 표시 (F2-7, F4-5, 수용기준 5)
8. 압력지수 산식 단위 테스트(pytest): PRD 산식과 수작업 계산값 일치, 경계값(0, 30, 55, 75, 100) 수준 판정
9. 실패 경로: 잘못된 Anthropic 키 입력 시 앱이 죽지 않고 오류 메시지 표시
10. 반응형: 뷰포트 1440 / 1024 / 390 에서 스크린샷, 가로 스크롤·텍스트 잘림 여부 확인
11. ANTHROPIC_API_KEY 가 환경에 있으면 NDT 1개 품목만 AI 리포트 생성 → 출처 URL 1개 이상, confidence 값 존재 확인 (없으면 skip)

[산출물]
- tests/e2e/*.py, tests/test_analyzer.py
- 발견 이슈 표: 번호 | PRD 항목 | 현상 | 원인 | 조치 | 재검증 결과
- 수정 후 전체 테스트 재실행 결과 (통과/실패/skip 수 그대로 보고, 실패를 숨기지 말 것)
- PRD 수용기준 6개 체크리스트의 최종 충족 여부 (배포 항목은 배포 전이면 "미완"으로 표시)
- 스크린샷은 tests/e2e/screenshots/ 에 저장
```
