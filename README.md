# 히위고 HWG — 5대 리그 이적시장 트래커 (1단계: 정적 JSON 구조)

RSS를 자동 수집해 정적 JSON으로 쌓는 구조입니다. 서버·DB 없이 GitHub 저장소 하나로
수집(Actions) + 저장(JSON) + 호스팅(Pages)이 전부 해결되며, 전부 무료입니다.

## 구조

```
index.html                      ← 메인 페이지 (data/latest.json만 읽음 → 항상 빠름)
scripts/fetch_rss.py            ← RSS 수집기 (필터링·리그/단계 분류·중복 제거)
.github/workflows/collect.yml   ← 30분마다 수집기를 자동 실행하는 스케줄러
data/latest.json                ← 최신 100건 (자동 생성)
data/archive/YYYY-MM.json       ← 월별 전체 아카이브 (자동 생성, 계속 쌓여도 메인 속도 무관)
```

## 배포 순서

1. **GitHub 저장소 생성** — Public으로 만들어야 GitHub Pages가 무료입니다.
2. **이 폴더 전체를 업로드** — 웹에서 "Add file → Upload files"로 드래그해도 되고,
   Git을 쓰면 `git add . && git commit -m "init" && git push`.
   (`.github` 폴더는 숨김 폴더이므로 웹 업로드 시 누락되지 않게 주의)
3. **Actions 권한 확인** — 저장소 Settings → Actions → General →
   Workflow permissions에서 **"Read and write permissions"** 선택 후 저장.
   (수집 결과를 봇이 커밋하려면 필요)
4. **첫 수집 실행** — Actions 탭 → "RSS 수집" → "Run workflow" 버튼.
   1~2분 뒤 `data/latest.json`이 생기면 성공. 이후엔 30분마다 자동 실행됩니다.
5. **GitHub Pages 켜기** — Settings → Pages → Source를
   "Deploy from a branch", 브랜치 `main` / 폴더 `/ (root)`로 설정.
   몇 분 뒤 `https://<아이디>.github.io/hwg-kr/` 에서 페이지가 뜹니다.

페이지가 데이터를 못 찾으면 자동으로 샘플 데이터를 표시하고, `data/latest.json`이
있으면 상단 배지가 "● LIVE"로 바뀝니다.

## 피드 추가/수정

`scripts/fetch_rss.py`의 `FEEDS` 리스트에 한 줄 추가하면 됩니다.
RSS가 없는 소스(X 계정 등)는 rss.app 같은 변환 서비스로 피드 URL을 만들 수 있습니다.
`tier`(1~3)는 매체 신뢰도이며 카드의 신뢰도 점수 계산에 반영됩니다.

## 다음 단계 (트래픽이 붙으면)

- 아카이브 페이지(월별 JSON을 읽는 "지난 이적시장" 뷰) 추가 → SEO 유입용
- Next.js + Supabase로 이관: 검색, 선수별 페이지, 무한 스크롤
- 자체 도메인 연결 후 애드센스 신청 (index.html의 광고 자리 2곳 교체)

## 로컬 테스트

```bash
pip install feedparser
python scripts/fetch_rss.py     # data/ 폴더에 JSON 생성
python -m http.server 8000      # http://localhost:8000 에서 확인
```
(파일을 더블클릭으로 열면 브라우저 보안 정책상 fetch가 막혀 샘플 데이터가 표시됩니다.
 `http.server`로 띄워야 실제 수집 데이터가 보입니다.)
