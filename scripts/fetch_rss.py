#!/usr/bin/env python3
"""
TRANSFER RADAR — 1단계 RSS 수집기
- 여러 매체의 RSS를 긁어 이적 관련 기사만 추립니다.
- data/latest.json  : 최신 100건 (메인 페이지가 읽는 파일 → 항상 작고 빠름)
- data/archive/YYYY-MM.json : 월별 전체 아카이브 (쌓여도 메인 속도에 영향 없음)
- 링크(URL) 기준으로 중복을 제거하므로 여러 번 실행해도 같은 기사가 두 번 쌓이지 않습니다.
"""

import json, re, hashlib
from datetime import datetime, timezone
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
LATEST_FILE = DATA / "latest.json"
LATEST_LIMIT = 100  # 메인 페이지에 노출할 최대 건수

# ── 수집 대상 피드 ──────────────────────────────────────────
# tier: 매체 신뢰도 (1=최상급 → 신뢰도 점수 계산에 사용)
# 피드는 자유롭게 추가/삭제하세요. RSS가 없는 매체는 rss.app 등 변환 서비스 이용.
FEEDS = [
    {"name": "BBC Sport Football", "url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "tier": 1},
    {"name": "Sky Sports Football", "url": "https://www.skysports.com/rss/12040", "tier": 1},
    {"name": "Guardian Football", "url": "https://www.theguardian.com/football/rss", "tier": 1},
    {"name": "Marca (EN)", "url": "https://e00-marca.uecdn.es/rss/en/football.xml", "tier": 2},
    {"name": "Football Italia", "url": "https://football-italia.net/feed/", "tier": 2},
    {"name": "Mirror Football", "url": "https://www.mirror.co.uk/sport/football/?service=rss", "tier": 3},
]

# ── 이적 기사 필터 키워드 ───────────────────────────────────
TRANSFER_KEYWORDS = [
    "transfer", "signs", "signing", "sign ", "deal", "move", "moves",
    "joins", "join ", "loan", "bid", "fee", "medical", "here we go",
    "agreement", "agreed", "contract", "release clause", "swap",
]

# ── 리그 분류: 제목에 클럽명이 있으면 해당 리그로 ─────────────
LEAGUE_CLUBS = {
    "EPL": ["arsenal", "man city", "manchester city", "man utd", "manchester united",
            "liverpool", "chelsea", "tottenham", "spurs", "newcastle", "aston villa",
            "west ham", "everton", "brighton", "premier league"],
    "LALIGA": ["real madrid", "barcelona", "barça", "atletico", "atlético", "sevilla",
               "villarreal", "athletic", "real sociedad", "la liga", "laliga"],
    "SERIEA": ["juventus", "inter", "milan", "napoli", "roma", "lazio", "atalanta",
               "fiorentina", "serie a"],
    "BUND": ["bayern", "dortmund", "leverkusen", "leipzig", "frankfurt", "stuttgart",
             "bundesliga"],
    "LIGUE1": ["psg", "paris saint-germain", "marseille", "monaco", "lyon", "lille",
               "ligue 1"],
}

# ── 단계 분류 키워드 ────────────────────────────────────────
STATUS_RULES = [
    ("official", ["official", "completed", "unveil", "announces signing", "confirms signing", "done deal"]),
    ("herewego", ["here we go", "agreement reached", "medical booked", "medical scheduled"]),
    ("nego",     ["talks", "negotiat", "advanced", "bid", "offer", "close to", "closing in", "agree personal terms"]),
]

FEE_RE = re.compile(r"[€£$]\s?(\d+(?:\.\d+)?)\s?(m|million|bn)", re.I)


def classify_league(text: str):
    """클럽명 일치 수가 가장 많은 리그로 분류.
    (예: 'Real Madrid complete signing of Liverpool full-back'
     → 영입 주체인 앞쪽 클럽에 가중치를 주기 위해 제목 앞 절반 매치는 2점)"""
    t = text.lower()
    half = len(t) // 2
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
        return None  # 5대 리그 무관 기사는 제외
    return max(scores, key=scores.get)


def classify_status(text: str) -> str:
    t = text.lower()
    for status, kws in STATUS_RULES:
        if any(k in t for k in kws):
            return status
    return "rumor"


def reliability(tier: int, status: str) -> int:
    """매체 신뢰도 + 진행 단계 → 1~5점"""
    base = {1: 4, 2: 3, 3: 2}.get(tier, 2)
    bonus = {"official": 1, "herewego": 1, "nego": 0, "rumor": -1}[status]
    return max(1, min(5, base + bonus))


def is_transfer_news(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in TRANSFER_KEYWORDS)


def entry_to_item(entry, feed_cfg):
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    if not is_transfer_news(title):
        return None
    league = classify_league(title)
    if league is None:
        return None

    # 발행 시각 → ISO (UTC)
    published = None
    for key in ("published_parsed", "updated_parsed"):
        if entry.get(key):
            published = datetime(*entry[key][:6], tzinfo=timezone.utc)
            break
    if published is None:
        published = datetime.now(timezone.utc)

    status = classify_status(title)
    fee_match = FEE_RE.search(title)
    fee = fee_match.group(0).upper().replace("MILLION", "M") if fee_match else None

    return {
        "id": hashlib.md5(link.encode()).hexdigest()[:12],
        "title": title,
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
            parsed = feedparser.parse(feed_cfg["url"])
            for entry in parsed.entries:
                item = entry_to_item(entry, feed_cfg)
                if item:
                    collected.append(item)
            print(f"[OK] {feed_cfg['name']}: {len(parsed.entries)}건 중 이적기사 추출")
        except Exception as e:  # 피드 하나가 죽어도 전체는 계속
            print(f"[SKIP] {feed_cfg['name']}: {e}")

    # ── 기존 데이터와 병합 + 중복 제거 (URL 기준) ──
    latest = load_json(LATEST_FILE)
    known_urls = {it["url"] for it in latest}

    new_items = [it for it in collected if it["url"] not in known_urls]
    print(f"신규 {len(new_items)}건 / 수집 {len(collected)}건")

    if not new_items:
        print("변경 없음 — 종료")
        return

    # ── 월별 아카이브에 누적 (전체 기록 보존) ──
    by_month = {}
    for it in new_items:
        month = it["published"][:7]  # YYYY-MM
        by_month.setdefault(month, []).append(it)

    for month, items in by_month.items():
        path = ARCHIVE / f"{month}.json"
        archive = load_json(path)
        archive_urls = {it["url"] for it in archive}
        archive += [it for it in items if it["url"] not in archive_urls]
        archive.sort(key=lambda x: x["published"], reverse=True)
        save_json(path, archive)
        print(f"아카이브 {month}: 총 {len(archive)}건")

    # ── latest.json은 항상 최신 N건만 유지 → 메인 페이지 속도 고정 ──
    merged = new_items + latest
    merged.sort(key=lambda x: x["published"], reverse=True)
    save_json(LATEST_FILE, merged[:LATEST_LIMIT])
    print(f"latest.json: {min(len(merged), LATEST_LIMIT)}건 갱신 완료")


if __name__ == "__main__":
    main()
