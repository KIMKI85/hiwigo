#!/usr/bin/env python3
"""
히위고 HWG — 오염된 번역 정리 (1회성)
- 번역 서버 에러 문자열이 title_ko에 저장된 기사를 찾아 재번역합니다.
- 재번역도 실패하면 title_ko를 null로 비웁니다(페이지가 원문 영어를 표시 → 최소한 뜻은 통함).
- latest.json 과 data/archive/*.json 모두 처리.
※ fetch_rss.py 가 번역 가드 포함(v4.2+)일 때 실행하세요 — translate_ko를 재사용합니다.
"""

import json
from pathlib import Path

from fetch_rss import translate_ko

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 오염 판정용 신호 (title_ko 안에 이런 게 있으면 잘못된 번역)
BAD_SIGNALS = [
    "error 500", "server error", "that's an error", "that\u2019s an error",
    "there was an error", "try again later", "that's all we know",
    "that\u2019s all we know", "too many requests", "service unavailable",
    "bad gateway", "429", "captcha",
]


def is_polluted(ko: str) -> bool:
    if not ko:
        return False
    low = ko.lower()
    return any(b in low for b in BAD_SIGNALS)


def process(path: Path):
    if not path.exists():
        return 0, 0, 0
    items = json.loads(path.read_text(encoding="utf-8"))
    fixed = cleared = 0
    for it in items:
        ko = it.get("title_ko")
        if not is_polluted(ko):
            continue
        retry = translate_ko(it.get("title", ""))  # 가드 적용된 재번역
        if retry:
            it["title_ko"] = retry
            fixed += 1
        else:
            it["title_ko"] = None  # 원문 영어로 폴백
            cleared += 1
    if fixed or cleared:
        path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items), fixed, cleared


def main():
    targets = [DATA / "latest.json"] + sorted((DATA / "archive").glob("*.json"))
    tf = tc = 0
    for path in targets:
        n, f, c = process(path)
        if f or c:
            print(f"{path.name}: 재번역 {f}건 / 원문폴백 {c}건")
        tf += f
        tc += c
    print(f"완료: 재번역 {tf}건, 원문폴백 {tc}건")


if __name__ == "__main__":
    main()
