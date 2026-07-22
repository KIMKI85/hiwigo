#!/usr/bin/env python3
"""
히위고 HWG — 비이적 기사 청소 (1회성)
- 이미 수집된 데이터에서 지분·감독선임·부상·분석칼럼 등 이적과 무관한 기사를 제거합니다.
- latest.json 과 data/archive/*.json 모두 처리.
※ fetch_rss.py 가 v4.3(비이적 필터 포함)일 때 실행하세요.
"""

import json
from pathlib import Path

from fetch_rss import NON_TRANSFER_RE, ANALYSIS_RE, TRANSFER_RE

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def keep(item) -> bool:
    t = item.get("title", "")
    if NON_TRANSFER_RE.search(t) or ANALYSIS_RE.search(t):
        return False
    return True


def process(path: Path):
    if not path.exists():
        return 0, 0
    items = json.loads(path.read_text(encoding="utf-8"))
    kept = [it for it in items if keep(it)]
    removed = len(items) - len(kept)
    if removed:
        path.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items), removed


def main():
    targets = [DATA / "latest.json"] + sorted((DATA / "archive").glob("*.json"))
    total = 0
    for path in targets:
        n, r = process(path)
        if r:
            print(f"{path.name}: {n}건 중 {r}건 제거")
        total += r
    print(f"완료: 비이적 기사 {total}건 제거")


if __name__ == "__main__":
    main()
