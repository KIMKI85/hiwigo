#!/usr/bin/env python3
"""
히위고 HWG — 미번역 기사 소급 번역 (1회성)
- title_ko 가 없거나(null/누락) 오염된(에러 문자열) 기사를 재번역합니다.
- latest.json 과 data/archive/*.json 전체 처리.
※ fetch_rss.py 가 번역 가드 포함(v4.2+)일 때 실행 — translate_ko 재사용.
"""

import json
from pathlib import Path

from fetch_rss import translate_ko

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

BAD_SIGNALS = [
    "error 500", "server error", "that's an error", "that\u2019s an error",
    "there was an error", "try again later", "that's all we know",
    "that\u2019s all we know", "too many requests", "service unavailable",
    "bad gateway", "429", "captcha",
]


def needs_translation(it) -> bool:
    ko = it.get("title_ko")
    if not ko:                       # null 또는 필드 없음 → 미번역
        return True
    low = ko.lower()
    return any(b in low for b in BAD_SIGNALS)  # 오염된 번역


def process(path: Path):
    if not path.exists():
        return 0, 0
    items = json.loads(path.read_text(encoding="utf-8"))
    done = 0
    for it in items:
        if not needs_translation(it):
            continue
        ko = translate_ko(it.get("title", ""))
        it["title_ko"] = ko  # 성공하면 한글, 실패하면 None(원문 표시)
        if ko:
            done += 1
    if done:
        path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items), done


def main():
    targets = [DATA / "latest.json"] + sorted((DATA / "archive").glob("*.json"))
    total = 0
    for path in targets:
        n, d = process(path)
        if d:
            print(f"{path.name}: {d}건 번역")
        total += d
    print(f"완료: 총 {total}건 소급 번역")


if __name__ == "__main__":
    main()
