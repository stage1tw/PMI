"""외부 데이터 수집기.

- ECOS(한국은행): CPI, PPI, 기준금리 — ECOS_API_KEY 필요
- 나라장터(공공데이터포털): 용역 입찰공고 — DATA_GO_KR_KEY 필요
- Google News RSS: 품목 키워드 뉴스 — 키 불필요
- 최저임금 / 노임단가: config 기준표

협회·법규·공급사 정보 같은 비정형 정보는 analyzer.research() 의 Claude web_search 로 수집한다.
"""
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import feedparser
import requests

from . import storage
from .config import CATEGORIES, MACRO_SAMPLE, MINIMUM_WAGE, WAGE_SAMPLE

TIMEOUT = 15

# (지표키, 통계표코드, 주기, 항목코드)
ECOS_SERIES = {
    "cpi": ("901Y009", "M", "0"),  # 소비자물가지수 총지수
    "ppi": ("404Y014", "M", "*AA"),  # 생산자물가지수 총지수
    "base_rate": ("722Y001", "M", "0101000"),  # 한국은행 기준금리
}

G2B_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"


def yoy(series: dict, year: int):
    """series[year] 의 전년 대비 증감률(%)."""
    if year in series and year - 1 in series and series[year - 1]:
        return round((series[year] / series[year - 1] - 1) * 100, 2)
    return None


# ---------- 기준표 ----------

def minimum_wage_table():
    years = sorted(MINIMUM_WAGE)
    return [{"year": y, "wage": MINIMUM_WAGE[y], "yoy": yoy(MINIMUM_WAGE, y)} for y in years]


def wage_growth(occupation: str):
    s = WAGE_SAMPLE.get(occupation, {})
    if not s:
        return None
    return yoy(s, max(s))


# ---------- ECOS ----------

def fetch_ecos(api_key: str, months: int = 26):
    end = datetime.now()
    start = end - timedelta(days=31 * months)
    got = {}
    for key, (code, cycle, item) in ECOS_SERIES.items():
        url = (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/100/"
            f"{code}/{cycle}/{start:%Y%m}/{end:%Y%m}/{item}"
        )
        rows = requests.get(url, timeout=TIMEOUT).json().get("StatisticSearch", {}).get("row", [])
        for r in rows:
            storage.upsert_indicator(key, r["TIME"], float(r["DATA_VALUE"]), "한국은행 ECOS")
        got[key] = len(rows)
    return got


def macro_snapshot():
    """최근 CPI/PPI 전년동월비, 기준금리. ECOS 캐시가 없으면 샘플값."""
    out, sample = {}, False
    for key in ("cpi", "ppi"):
        s = storage.get_indicator_series(key)
        if len(s) >= 13:
            last, prev = s[-1], s[-13]
            out[f"{key}_yoy"] = round((last["value"] / prev["value"] - 1) * 100, 2)
            out[f"{key}_period"] = last["period"]
        else:
            out[f"{key}_yoy"] = MACRO_SAMPLE[f"{key}_yoy"]
            sample = True
    br = storage.get_indicator_series("base_rate")
    out["base_rate"] = br[-1]["value"] if br else MACRO_SAMPLE["base_rate"]
    sample = sample or not br
    out["is_sample"] = sample
    return out


# ---------- 나라장터 ----------

def fetch_g2b(api_key: str, keyword: str, days: int = 60):
    end = datetime.now()
    params = {
        "serviceKey": api_key,
        "numOfRows": 50,
        "pageNo": 1,
        "inqryDiv": 1,
        "inqryBgnDt": (end - timedelta(days=days)).strftime("%Y%m%d0000"),
        "inqryEndDt": end.strftime("%Y%m%d2359"),
        "bidNtceNm": keyword,
        "type": "json",
    }
    data = requests.get(G2B_URL, params=params, timeout=TIMEOUT).json()
    items = data.get("response", {}).get("body", {}).get("items") or []
    return [
        {
            "bid_no": f"{i.get('bidNtceNo')}-{i.get('bidNtceOrd')}",
            "title": i.get("bidNtceNm", ""),
            "agency": i.get("ntceInsttNm", ""),
            "notice_date": i.get("bidNtceDt", ""),
            "price": float(i.get("presmptPrce") or 0),
        }
        for i in items
    ]


# ---------- 뉴스 ----------

def fetch_news(keyword: str, limit: int = 8):
    url = f"https://news.google.com/rss/search?q={quote(keyword + ' when:30d')}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    return [
        {
            "title": e.get("title", ""),
            "link": e.get("link", ""),
            "published": e.get("published", ""),
            "source": e.get("source", {}).get("title", ""),
        }
        for e in feed.entries[:limit]
    ]


# ---------- 일괄 수집 ----------

def _run(source, fn):
    t = time.time()
    try:
        n = fn()
        storage.log_collect(source, "success", n, f"{time.time() - t:.1f}s")
    except Exception as e:  # 개별 소스 실패가 전체 수집을 멈추지 않도록
        storage.log_collect(source, "error", 0, f"{type(e).__name__}: {e}")


def collect_all(ecos_key=None, g2b_key=None, categories=None):
    cats = [CATEGORIES[k] for k in (categories or CATEGORIES)]

    storage.log_collect("고용노동부 (최저임금 고시)", "success", len(MINIMUM_WAGE), "기준표")
    storage.log_collect("대한건설협회/엔지니어링협회 (노임단가)", "sample", len(WAGE_SAMPLE), "예시 기준표 — 실제 공표값 교체 필요")

    if ecos_key:
        _run("한국은행 ECOS", lambda: sum(fetch_ecos(ecos_key).values()))
    else:
        storage.log_collect("한국은행 ECOS", "skipped", 0, "ECOS_API_KEY 미설정 — 샘플값 사용")

    def news():
        n = 0
        for c in cats:
            for kw in c.keywords:
                items = fetch_news(kw)
                storage.save_news(c.key, items)
                n += len(items)
        return n

    _run("뉴스 (Google News RSS)", news)

    if g2b_key:
        def bids():
            n = 0
            for c in cats:
                items = fetch_g2b(g2b_key, c.keywords[0])
                storage.save_bids(c.key, items)
                n += len(items)
            return n

        _run("나라장터 (공공데이터포털)", bids)
    else:
        storage.log_collect("나라장터 (공공데이터포털)", "skipped", 0, "DATA_GO_KR_KEY 미설정")
