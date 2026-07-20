#!/usr/bin/env python3
"""
히위고 HWG — RSS 수집기 v4 (선수명 자동 추출 추가)
v3 추가사항:
 1. 소스 확장: 6개 → 13개 (독일·프랑스·이탈리아·스페인 현지 매체 + 영어권 루머 전문지)
 2. 다국어 이적 키워드 (Wechsel/transfert/colpo/fichaje 등)
 3. league_hint: 클럽명 매칭 실패 시 매체 기본 리그로 분류 (현지 매체 수집률 향상)
 4. skip_filter: 이적 전문 피드는 키워드 필터 면제 (전부 이적 기사이므로)
※ 피드 URL은 매체 사정으로 바뀔 수 있음. Actions 로그의 [SKIP] 표시가 계속되는 피드는
  해당 줄을 삭제하면 됨. 피드 하나가 죽어도 나머지 수집엔 영향 없음.
"""

import json, re, hashlib
from datetime import datetime, timezone
from pathlib import Path

import feedparser

try:
    from deep_translator import GoogleTranslator
    _translator = GoogleTranslator(source="auto", target="ko")
except Exception:
    _translator = None  # 라이브러리 없거나 실패해도 수집은 계속

# 일부 매체는 기본 봇 UA를 차단하므로 브라우저 UA로 요청
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
LATEST_FILE = DATA / "latest.json"
LATEST_LIMIT = 100

# league_hint: 클럽명 매칭 실패 시 적용할 기본 리그 (현지 매체용)
# skip_filter: True면 이적 키워드 필터 생략 (이적 전문 피드)
FEEDS = [
    # ── 영어권 종합 (1티어) ──
    {"name": "BBC Sport Football", "url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "tier": 1},
    {"name": "Sky Sports Football", "url": "https://www.skysports.com/rss/12040", "tier": 1},
    {"name": "Guardian Football", "url": "https://www.theguardian.com/football/rss", "tier": 1},
    # ── 독일 ──
    {"name": "kicker Bundesliga (DE)", "url": "https://newsfeed.kicker.de/news/bundesliga", "tier": 1, "league_hint": "BUND"},
    {"name": "kicker Fussball (DE)", "url": "https://newsfeed.kicker.de/news/fussball", "tier": 1, "league_hint": "BUND"},
    {"name": "Sport1 (DE)", "url": "https://www.sport1.de/news.rss", "tier": 2, "league_hint": "BUND"},
    # ── 프랑스 ──
    {"name": "RMC Sport (FR)", "url": "https://rmcsport.bfmtv.com/rss/football/", "tier": 1, "league_hint": "LIGUE1"},
    {"name": "Le10Sport (FR)", "url": "https://le10sport.com/feed", "tier": 3, "league_hint": "LIGUE1", "skip_filter": True},
    {"name": "Maxifoot (FR)", "url": "https://www.maxifoot.fr/rss.xml", "tier": 2, "league_hint": "LIGUE1"},
    # ── 스페인 ──
    {"name": "Marca (EN)", "url": "https://e00-marca.uecdn.es/rss/en/football.xml", "tier": 2, "league_hint": "LALIGA"},
    {"name": "Marca Primera (ES)", "url": "https://e00-marca.uecdn.es/rss/futbol/primera-division.xml", "tier": 1, "league_hint": "LALIGA"},
    {"name": "AS Futbol (ES)", "url": "https://as.com/rss/futbol/portada.xml", "tier": 1, "league_hint": "LALIGA"},
    {"name": "Fichajes (ES)", "url": "https://www.fichajes.net/rss", "tier": 3, "league_hint": "LALIGA", "skip_filter": True},
    # ── 이탈리아 ──
    {"name": "Gazzetta Calcio (IT)", "url": "https://www.gazzetta.it/rss/calcio.xml", "tier": 1, "league_hint": "SERIEA"},
    {"name": "Football Italia", "url": "https://football-italia.net/feed/", "tier": 2, "league_hint": "SERIEA"},
    # ── 영어권 타블로이드 (3티어) ──
    {"name": "Mirror Football", "url": "https://www.mirror.co.uk/sport/football/?service=rss", "tier": 3},
]

# ── 이적 키워드: 단어 단위 정규식 (오탐 방지) ─────────────────
TRANSFER_RE = re.compile(
    r"\b(transfers?|signs?|signing|signed|deal|deals|loan|loans|bid|bids|fee|fees|"
    r"medical|joins?|joined|move|moves|swap|agreement|agreed|contract|unveils?|"
    r"release clause|here we go|done deal|targets?|"
    r"wechsel|wechselt|verpflichtet|transfergerücht|ablöse|leihe|"      # 독일어
    r"transfert|signe|prêt|recrue|mercato|"                             # 프랑스어
    r"acquisto|cessione|trattativa|colpo|"                              # 이탈리아어
    r"fichajes?|ficha|traspaso|cesión|acuerdo)\b",                     # 스페인어
    re.I,
)

# ── 리그별 클럽 사전 (보강판) ────────────────────────────────
LEAGUE_CLUBS = {
    "EPL": [
        "arsenal", "man city", "manchester city", "man utd", "man united", "manchester united",
        "liverpool", "chelsea", "tottenham", "spurs", "newcastle", "aston villa", "west ham",
        "everton", "brighton", "bournemouth", "brentford", "fulham", "crystal palace",
        "wolves", "wolverhampton", "nottingham forest", "leeds", "sunderland", "burnley",
        "premier league",
    ],
    "LALIGA": [
        "real madrid", "barcelona", "barça", "barca", "atletico madrid", "atlético", "atletico",
        "sevilla", "villarreal", "athletic club", "athletic bilbao", "real sociedad", "real betis",
        "betis", "valencia", "girona", "celta", "getafe", "osasuna", "rayo vallecano", "mallorca",
        "alaves", "espanyol", "levante", "elche", "oviedo", "la liga", "laliga",
    ],
    "SERIEA": [
        "juventus", "juve", "inter milan", "inter", "ac milan", "milan", "napoli", "roma",
        "lazio", "atalanta", "fiorentina", "bologna", "torino", "genoa", "udinese", "cagliari",
        "verona", "parma", "como", "lecce", "sassuolo", "cremonese", "pisa", "serie a",
    ],
    "BUND": [
        "bayern", "dortmund", "bvb", "leverkusen", "rb leipzig", "leipzig", "frankfurt",
        "stuttgart", "gladbach", "monchengladbach", "wolfsburg", "freiburg", "mainz",
        "hoffenheim", "augsburg", "union berlin", "werder bremen", "st pauli", "cologne",
        "koln", "hamburg", "heidenheim", "bundesliga",
    ],
    "LIGUE1": [
        "psg", "paris saint-germain", "paris fc", "marseille", "monaco", "lyon", "lille",
        "nice", "lens", "rennes", "strasbourg", "toulouse", "nantes", "brest", "auxerre",
        "le havre", "lorient", "metz", "angers", "ligue 1", "ligue1",
    ],
}

STATUS_RULES = [
    ("official", ["official", "completed", "completes", "unveil", "announces signing",
                  "confirms signing", "done deal", "seals", "wraps up"]),
    ("herewego", ["here we go", "agreement reached", "medical booked", "medical scheduled",
                  "set to sign", "deal agreed"]),
    ("nego",     ["talks", "negotiat", "advanced", "bid", "offer", "close to", "closing in",
                  "agree personal terms", "push for", "in contact"]),
]

FEE_RE = re.compile(r"[€£$]\s?(\d+(?:\.\d+)?)\s?(m|mln|million|millionen|millones|bn)", re.I)


# ── 선수명 추출 ──────────────────────────────────────────────
# 대문자로 시작하는 2~3단어 인명 후보를 찾고, 클럽명·헤드라인 상용어를 제외
_NAME_RE = re.compile(r"\b([A-ZÀ-Þ][a-zà-ÿ'\-]+(?:\s(?:van|von|de|di|da|den|der|el|al)\s?)?(?:\s[A-ZÀ-Þ][a-zà-ÿ'\-]+){1,2})\b")

def _build_exclude():
    words = set()
    for clubs in LEAGUE_CLUBS.values():
        for c in clubs:
            words.update(c.split())
    words.update("""
        transfer transfers news live update updates official here we go done deal deals
        premier league champions europa cup city united town athletic club real sporting
        january june july august summer winter window deadline day exclusive report
        breaking rumour rumours gossip exit move loan bid fee medical talks agreement
        contract statement confirmed signing signs manager boss coach mercato fichajes
        saturday sunday monday tuesday wednesday thursday friday
        shock star stars blow twist boost race battle plan plans chief chiefs double
        triple final decision future major huge massive new next top the this that
        reds blues gunners citizens hammers toffees foxes saints villans magpies
        cherries seagulls bees eagles lilywhites baggies clarets terriers
        rossoneri nerazzurri bianconeri azzurri giallorossi blaugrana merengues
    """.split())
    return words

_EXCLUDE = None

def extract_player(title, summary=""):
    """제목(우선)·요약에서 선수명 후보 추출. 확신 없으면 None (오표기보다 미표기가 낫다)."""
    global _EXCLUDE
    if _EXCLUDE is None:
        _EXCLUDE = _build_exclude()
    for text in (title, summary):
        if not text:
            continue
        for m in _NAME_RE.finditer(text):
            toks = m.group(1).split()
            # 앞뒤에 붙은 헤드라인 상용어("Shock", "Boss" 등)를 잘라냄
            while toks and toks[0].lower().strip("'-") in _EXCLUDE:
                toks.pop(0)
            while toks and toks[-1].lower().strip("'-") in _EXCLUDE:
                toks.pop()
            if not (2 <= len(toks) <= 3):
                continue
            if any(t.lower().strip("'-") in _EXCLUDE for t in toks):
                continue
            cand = " ".join(toks)
            if len(cand) < 6:
                continue
            return cand
    return None



def norm_title(title: str) -> str:
    """중복 판정용 제목 정규화: 소문자 + 영숫자만"""
    return re.sub(r"[^a-z0-9가-힣]", "", title.lower())


def classify_league(text: str):
    """클럽명 일치 점수가 가장 높은 리그로 분류. 제목 앞 절반(영입 주체)은 2점."""
    t = text.lower()
    half = max(len(t) // 2, 1)
    scores = {}
    for league, clubs in LEAGUE_CLUBS.items():
        s = 0
        for c in clubs:
            pos = t.find(c)
            if pos >= 0:
                s += 2 if pos < half else 1
        if s:
            scores[league] = s
    if not scores:
        return None
    return max(scores, key=scores.get)


def classify_status(text: str) -> str:
    t = text.lower()
    for status, kws in STATUS_RULES:
        if any(k in t for k in kws):
            return status
    return "rumor"


def reliability(tier: int, status: str) -> int:
    base = {1: 4, 2: 3, 3: 2}.get(tier, 2)
    bonus = {"official": 1, "herewego": 1, "nego": 0, "rumor": -1}[status]
    return max(1, min(5, base + bonus))


def translate_ko(title: str):
    """제목 한글 번역. 실패하면 None (원문 표시)."""
    if _translator is None:
        return None
    try:
        ko = _translator.translate(title)
        if ko and ko.strip() and ko.strip() != title.strip():
            return ko.strip()
    except Exception:
        pass
    return None


def entry_to_item(entry, feed_cfg):
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    if not feed_cfg.get("skip_filter") and not TRANSFER_RE.search(title):
        return None
    league = classify_league(title) or feed_cfg.get("league_hint")
    if league is None:
        return None

    published = None
    for key in ("published_parsed", "updated_parsed"):
        if entry.get(key):
            published = datetime(*entry[key][:6], tzinfo=timezone.utc)
            break
    if published is None:
        published = datetime.now(timezone.utc)

    # RSS 요약문 (HTML 태그 제거) — 제목에 선수명이 없을 때 보조로 사용
    summary = re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "")[:400]

    status = classify_status(title)
    fee_match = FEE_RE.search(title)
    fee = fee_match.group(0).upper().replace("MILLION", "M") if fee_match else None

    return {
        "id": hashlib.md5(link.encode()).hexdigest()[:12],
        "title": title,
        "player": extract_player(title, summary),
        "title_ko": None,  # 신규 판정 후에만 번역 (호출 최소화)
        "league": league,
        "status": status,
        "lv": reliability(feed_cfg["tier"], status),
        "src": feed_cfg["name"],
        "url": link,
        "fee": fee,
        "published": published.isoformat(),
    }


def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    collected = []
    for feed_cfg in FEEDS:
        try:
            parsed = feedparser.parse(feed_cfg["url"], agent=AGENT)
            for entry in parsed.entries:
                item = entry_to_item(entry, feed_cfg)
                if item:
                    collected.append(item)
            tag = "[OK]" if parsed.entries else "[EMPTY]"
            print(f"{tag} {feed_cfg['name']}: {len(parsed.entries)}건 중 이적기사 추출")
        except Exception as e:
            print(f"[SKIP] {feed_cfg['name']}: {e}")

    latest = load_json(LATEST_FILE)

    # ── 중복 제거: URL + 정규화 제목 둘 다 확인 ──
    known_urls = {it["url"] for it in latest}
    known_titles = {norm_title(it["title"]) for it in latest}
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    for it in load_json(ARCHIVE / f"{this_month}.json"):
        known_urls.add(it["url"])
        known_titles.add(norm_title(it["title"]))

    new_items, seen_titles = [], set()
    for it in collected:
        nt = norm_title(it["title"])
        if it["url"] in known_urls or nt in known_titles or nt in seen_titles:
            continue
        seen_titles.add(nt)  # 이번 수집분 안에서의 중복도 제거
        new_items.append(it)

    print(f"신규 {len(new_items)}건 / 수집 {len(collected)}건")
    if not new_items:
        print("변경 없음 — 종료")
        return

    # ── 신규 기사만 번역 (기존 기사는 다시 번역하지 않음) ──
    for it in new_items:
        it["title_ko"] = translate_ko(it["title"])
    ok = sum(1 for it in new_items if it["title_ko"])
    print(f"번역 {ok}/{len(new_items)}건 성공")

    # ── 월별 아카이브 누적 ──
    by_month = {}
    for it in new_items:
        by_month.setdefault(it["published"][:7], []).append(it)
    for month, items in by_month.items():
        path = ARCHIVE / f"{month}.json"
        archive = load_json(path)
        archive_urls = {a["url"] for a in archive}
        archive += [it for it in items if it["url"] not in archive_urls]
        archive.sort(key=lambda x: x["published"], reverse=True)
        save_json(path, archive)
        print(f"아카이브 {month}: 총 {len(archive)}건")

    # ── latest.json 갱신 ──
    merged = new_items + latest
    merged.sort(key=lambda x: x["published"], reverse=True)
    save_json(LATEST_FILE, merged[:LATEST_LIMIT])
    print(f"latest.json: {min(len(merged), LATEST_LIMIT)}건 갱신 완료")


if __name__ == "__main__":
    main()
