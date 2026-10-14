#!/usr/bin/env python3
"""
히위고 HWG — 기존 데이터 재정리 (1회성)
- 새 규칙(코멘트·평가 기사 필터, HERE WE GO 판정 강화)으로 latest.json·아카이브를 다시 거름
- 잘린 선수명([Trent Alexander-] 등) 재추출, 진행 단계·신뢰도 재계산
- ANTHROPIC_API_KEY가 있으면 latest.json은 AI 검수까지 적용
※ fetch_rss.py v4.5 이상에서 실행
"""
import json
from pathlib import Path

import fetch_rss as fr

DATA = Path(__file__).resolve().parent.parent / "data"
TIERS = {f["name"]: f["tier"] for f in fr.FEEDS}


def keep(it):
    t = it.get("title", "")
    return not (fr.NON_TRANSFER_RE.search(t) or fr.ANALYSIS_RE.search(t) or fr.is_opinion(t))


def fix(it):
    p = it.get("player") or ""
    if not p or p.endswith("-"):
        it["player"] = fr.extract_player(it.get("title", ""), "")
    it["status"] = fr.classify_status(it.get("title", ""))
    it["lv"] = fr.reliability(TIERS.get(it.get("src"), 2), it["status"])
    return it


def process(path, use_ai=False):
    if not path.exists():
        return
    items = json.loads(path.read_text(encoding="utf-8"))
    before = len(items)
    items = [fix(it) for it in items if keep(it)]
    if use_ai:
        items = fr.ai_review(items)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.name}: {before}건 → {len(items)}건 ({before - len(items)}건 제외)")


def main():
    process(DATA / "latest.json", use_ai=bool(fr.AI_KEY))
    for p in sorted((DATA / "archive").glob("*.json")):
        process(p)


if __name__ == "__main__":
    main()
