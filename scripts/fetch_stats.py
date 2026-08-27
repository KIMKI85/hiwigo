#!/usr/bin/env python3
"""
히위고 HWG — 리그 통계 수집기 (football-data.org 무료 티어)
- 5대 리그 + 챔피언스리그의 순위표 / 최근 결과 / 득점 순위를 수집
- 결과는 data/stats.json 하나로 저장 (페이지가 이 파일만 읽음)
- API 키는 환경변수 FOOTBALL_DATA_TOKEN 으로 주입 (GitHub Secrets)
- 무료 티어 분당 10회 제한 → 호출 사이 7초 대기
"""

import json, os, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "stats.json"

TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")
BASE = "https://api.football-data.org/v4"

# football-data.org 대회 코드
COMPETITIONS = [
    {"code": "PL",  "key": "EPL",    "name": "프리미어리그"},
    {"code": "PD",  "key": "LALIGA", "name": "라리가"},
    {"code": "SA",  "key": "SERIEA", "name": "세리에 A"},
    {"code": "BL1", "key": "BUND",   "name": "분데스리가"},
    {"code": "FL1", "key": "LIGUE1", "name": "리그 1"},
    {"code": "CL",  "key": "UCL",    "name": "챔피언스리그"},
]


def api(path):
    """API 호출 (무료 티어 속도 제한 준수). HTTP 에러 시 본문을 로그로 남김."""
    req = urllib.request.Request(BASE + path, headers={"X-Auth-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        print(f"    [HTTP {e.code}] {path} → {body}")
        time.sleep(7)
        raise
    time.sleep(7)  # 분당 10회 제한 준수
    return data


def get_standings(code):
    # 시즌 지정 없이 기본 호출 (무료 티어는 현재 시즌을 자동으로 줌).
    # 응답 구조를 진단 로그로 남겨서 문제를 정확히 파악.
    data = api(f"/competitions/{code}/standings")
    tables = data.get("standings", [])
    if not tables:
        # 응답에 standings가 없으면 무슨 키가 왔는지, 시즌이 뭔지 로그로 남김
        season = data.get("season", {})
        print(f"    [진단] {code}: standings 비어있음. 응답키={list(data.keys())} "
              f"시즌={season.get('startDate','?')}~{season.get('endDate','?')} "
              f"currentMatchday={season.get('currentMatchday','?')}")
        return []
    rows_out = []
    for table in tables:
        if table.get("type") == "TOTAL":
            for row in table.get("standings", []):
                rows_out.append({
                    "pos": row.get("position"),
                    "team": (row.get("team") or {}).get("shortName") or (row.get("team") or {}).get("name", "?"),
                    "crest": (row.get("team") or {}).get("crest", ""),
                    "played": row.get("playedGames", 0), "won": row.get("won", 0),
                    "draw": row.get("draw", 0), "lost": row.get("lost", 0),
                    "gd": row.get("goalDifference", 0), "pts": row.get("points", 0),
                })
            break
    return rows_out


def get_results(code, limit=8):
    data = api(f"/competitions/{code}/matches?status=FINISHED")
    matches = data.get("matches", [])[-limit:]
    return [{
        "date": m["utcDate"][:10],
        "home": m["homeTeam"].get("shortName") or m["homeTeam"]["name"],
        "away": m["awayTeam"].get("shortName") or m["awayTeam"]["name"],
        "hs": m["score"]["fullTime"]["home"],
        "as": m["score"]["fullTime"]["away"],
    } for m in reversed(matches)]


def get_scorers(code, limit=10):
    data = api(f"/competitions/{code}/scorers?limit={limit}")
    return [{
        "name": s["player"]["name"],
        "team": s["team"].get("shortName") or s["team"]["name"],
        "goals": s.get("goals") or 0,
        "assists": s.get("assists") or 0,
    } for s in data.get("scorers", [])]


def main():
    if not TOKEN:
        raise SystemExit("FOOTBALL_DATA_TOKEN 환경변수가 없습니다. GitHub Secrets 설정을 확인하세요.")

    out = {"updated": datetime.now(timezone.utc).isoformat(), "competitions": {}}
    for comp in COMPETITIONS:
        entry = {"name": comp["name"]}
        try:
            entry["standings"] = get_standings(comp["code"])
            entry["results"] = get_results(comp["code"])
            entry["scorers"] = get_scorers(comp["code"])
            print(f"[OK] {comp['name']}: 순위 {len(entry['standings'])}팀 / "
                  f"결과 {len(entry['results'])}건 / 득점자 {len(entry['scorers'])}명")
        except Exception as e:
            # 대회 하나가 실패해도 (비시즌·API 오류) 나머지는 계속
            print(f"[SKIP] {comp['name']}: {e}")
            entry.setdefault("standings", [])
            entry.setdefault("results", [])
            entry.setdefault("scorers", [])
        out["competitions"][comp["key"]] = entry

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"stats.json 저장 완료 ({OUT})")


if __name__ == "__main__":
    main()
