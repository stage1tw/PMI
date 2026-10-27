"""품목·수집소스·기준 데이터 정의.

수치 중 is_sample=True 로 표시된 값은 데모용 예시값이다.
운영 전 실제 공표값(대한건설협회 임금실태조사, 엔지니어링협회 노임단가 등)으로 교체해야 한다.
"""
from dataclasses import dataclass, field

MODEL = "claude-opus-5-5"


@dataclass
class Category:
    key: str
    name: str
    # 원가 구성비 (합계 1.0): 노무비 / 자재비 / 경비
    cost_mix: dict
    occupations: list  # 노임단가 직종명
    keywords: list  # 뉴스·나라장터 검색 키워드
    regulation_keywords: list
    supply_concentration: int  # 공급 집중도 0~15 (높을수록 소수 업체 의존)
    description: str = ""
    examples: list = field(default_factory=list)


CATEGORIES = {
    c.key: c
    for c in [
        Category(
            "ndt", "비파괴검사(NDT)",
            {"labor": 0.72, "material": 0.08, "expense": 0.20},
            ["비파괴시험공"], ["비파괴검사", "NDT 검사"],
            ["비파괴검사 기술의 진흥 및 관리에 관한 법률", "중량물 검사주기", "안전검사"],
            11, "UT·RT·MT·PT 등 설비·구조물 비파괴검사 연간계약",
        ),
        Category(
            "maintenance", "설비 정비",
            {"labor": 0.60, "material": 0.25, "expense": 0.15},
            ["기계설비공", "용접공", "배관공"], ["제철소 설비정비", "플랜트 정비"],
            ["산업안전보건법", "중대재해처벌법"],
            8, "압연·제강 설비 예방/돌발 정비 도급",
        ),
        Category(
            "plant", "플랜트 보수공사",
            {"labor": 0.50, "material": 0.38, "expense": 0.12},
            ["배관공", "용접공", "철골공"], ["플랜트 보수공사", "플랜트 수주"],
            ["건설산업기본법", "중대재해처벌법"],
            7, "대수리·셧다운 보수 공사",
        ),
        Category(
            "construction", "건축·토목 도급",
            {"labor": 0.42, "material": 0.45, "expense": 0.13},
            ["보통인부", "철근공", "형틀목공"], ["건설 공사비", "건설자재 가격"],
            ["건설산업기본법", "건설근로자법"],
            5, "사내 건축·토목 공사",
        ),
        Category(
            "cleaning", "청소·미화",
            {"labor": 0.88, "material": 0.05, "expense": 0.07},
            ["청소원"], ["시설관리 용역", "청소 용역 단가"],
            ["최저임금법", "파견법"],
            3, "사무동·현장 청소 및 미화 용역",
        ),
        Category(
            "security", "경비·보안",
            {"labor": 0.90, "material": 0.02, "expense": 0.08},
            ["경비원"], ["경비 용역", "보안 용역 단가"],
            ["경비업법", "최저임금법"],
            4, "출입관리·순찰 경비 용역",
        ),
        Category(
            "safety", "안전관리 대행",
            {"labor": 0.80, "material": 0.03, "expense": 0.17},
            ["산업안전기사"], ["안전관리 대행", "안전관리자 인력난"],
            ["산업안전보건법", "중대재해처벌법", "안전보건관리체계"],
            9, "안전관리자·보건관리자 위탁, 안전점검",
        ),
        Category(
            "engineering", "엔지니어링 용역",
            {"labor": 0.78, "material": 0.02, "expense": 0.20},
            ["엔지니어링 기술자(고급)"], ["엔지니어링 용역", "엔지니어링 노임단가"],
            ["엔지니어링산업 진흥법"],
            8, "설계·감리·기술진단 용역",
        ),
    ]
}

# 최저임금 (고용노동부 고시, 원/시간). 2027년 고시값이 확정되면 추가할 것.
MINIMUM_WAGE = {
    2020: 8590, 2021: 8720, 2022: 9160, 2023: 9620,
    2024: 9860, 2025: 10030, 2026: 10320,
}

# 직종별 일 노임단가 (원/일) — 데모용 예시값. 실제 공표값으로 교체 필요.
WAGE_SAMPLE = {
    "비파괴시험공": {2024: 251_000, 2025: 265_600, 2026: 281_000},
    "기계설비공": {2024: 241_000, 2025: 250_400, 2026: 260_900},
    "용접공": {2024: 266_000, 2025: 276_100, 2026: 287_400},
    "배관공": {2024: 245_000, 2025: 253_800, 2026: 263_200},
    "철골공": {2024: 268_000, 2025: 277_100, 2026: 287_900},
    "보통인부": {2024: 165_000, 2025: 169_800, 2026: 175_000},
    "철근공": {2024: 275_000, 2025: 280_200, 2026: 287_600},
    "형틀목공": {2024: 280_000, 2025: 285_600, 2026: 292_400},
    "청소원": {2024: 82_000, 2025: 83_400, 2026: 85_900},
    "경비원": {2024: 83_000, 2025: 84_500, 2026: 87_000},
    "산업안전기사": {2024: 310_000, 2025: 324_000, 2026: 342_500},
    "엔지니어링 기술자(고급)": {2024: 340_000, 2025: 352_500, 2026: 366_200},
}

# 거시지표 샘플 (전년동기 대비 %) — ECOS 키가 없을 때 사용.
MACRO_SAMPLE = {
    "cpi_yoy": 2.1,
    "ppi_yoy": 1.4,
    "base_rate": 2.50,
}

SOURCES = [
    {"key": "moel", "name": "고용노동부", "url": "https://www.moel.go.kr", "data": "최저임금, 임금통계, 법령 개정", "method": "고시값 + AI 웹검색"},
    {"key": "g2b", "name": "나라장터", "url": "https://www.g2b.go.kr", "data": "용역·공사 입찰공고, 참여업체", "method": "공공데이터포털 API"},
    {"key": "kostat", "name": "통계청(KOSIS)", "url": "https://kosis.kr", "data": "CPI, 업종별 임금", "method": "AI 웹검색 (KOSIS API 확장 예정)"},
    {"key": "bok", "name": "한국은행(ECOS)", "url": "https://ecos.bok.or.kr", "data": "CPI, PPI, 기준금리", "method": "ECOS OpenAPI"},
    {"key": "commodity", "name": "원자재가격", "url": "https://www.komis.or.kr", "data": "철강·비철·유가", "method": "AI 웹검색"},
    {"key": "cak", "name": "대한건설협회", "url": "https://www.cak.or.kr", "data": "건설업 시중노임단가", "method": "기준표 + AI 웹검색"},
    {"key": "kopia", "name": "한국플랜트산업협회", "url": "https://www.kopia.or.kr", "data": "플랜트 시장·수주 동향", "method": "AI 웹검색"},
    {"key": "kenca", "name": "한국엔지니어링협회", "url": "https://www.kenca.or.kr", "data": "엔지니어링 노임단가", "method": "기준표 + AI 웹검색"},
    {"key": "kosha", "name": "안전보건공단", "url": "https://www.kosha.or.kr", "data": "안전검사·고시 개정, 재해 동향", "method": "AI 웹검색"},
    {"key": "news", "name": "뉴스 (Google News RSS)", "url": "https://news.google.com", "data": "공급사·업계 뉴스", "method": "RSS"},
]

LEVELS = [
    (30, "낮음", "#0ca30c", "현 단가 유지 협상 가능"),
    (55, "보통", "#fab219", "물가 수준 인상 예상"),
    (75, "높음", "#ec835a", "물가 상회 인상 요구 예상 — 근거 기반 방어 필요"),
    (101, "매우 높음", "#d03b3b", "공급 부족·법규 강화 동반 — 대체 공급원 확보 시급"),
]
LEVEL_ICON = {"낮음": "🟢", "보통": "🟡", "높음": "🟠", "매우 높음": "🔴"}
SERIES_COLOR = "#2a78d6"


def level_of(index: float):
    for upper, label, color, note in LEVELS:
        if index < upper:
            return label, color, note
    return LEVELS[-1][1:]
