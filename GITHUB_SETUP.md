# GitHub Actions 자동화 설정 가이드

## 전체 흐름

```
[매일 오전 9:00 KST — GitHub 서버 자동 실행]
  ↓
  Python + 라이브러리 설치
  ↓
  local_mag7_real.py → yfinance 실제 데이터 → PDF 생성
  ↓
  telegram_sender.py → @MyStockMonitor_bot → 내 Telegram
```

PC를 켜지 않아도 매일 자동 실행됩니다.

---

## STEP 1 — GitHub 저장소 만들기

1. https://github.com 접속 → 로그인
2. 우상단 **+** → **New repository**
3. Repository name: `mag7-stock-report` (원하는 이름)
4. **Private** 선택 (토큰 정보 보호)
5. **Create repository** 클릭

---

## STEP 2 — 코드 업로드

PowerShell에서 실행:

```powershell
cd "C:\Users\micke\Documents\Stock-Analyst"

# Git 초기화
git init
git add .
git commit -m "Initial commit: Mag7 stock report system"

# GitHub 저장소 연결 (YOUR_USERNAME을 본인 GitHub 아이디로 변경)
git remote add origin https://github.com/YOUR_USERNAME/mag7-stock-report.git
git branch -M main
git push -u origin main
```

> Git이 없으면: https://git-scm.com/download/win 에서 설치

---

## STEP 3 — Telegram Secrets 등록

GitHub에서 민감한 정보(Bot Token, Chat ID)는 **Secrets**로 안전하게 보관합니다.

1. GitHub 저장소 페이지 → **Settings** 탭
2. 왼쪽 메뉴 → **Secrets and variables** → **Actions**
3. **New repository secret** 클릭

| Secret 이름 | 값 |
|------------|-----|
| `BOT_TOKEN` | `8627861470:AAHkv4tuLdJfmx-BqKfF_3bb0eYZu-yZGr4` |
| `CHAT_ID`   | `8615904260` |

두 개 모두 등록합니다.

---

## STEP 4 — 수동으로 테스트 실행

1. GitHub 저장소 → **Actions** 탭
2. 왼쪽 **Mag7 Daily Report** 클릭
3. **Run workflow** → **Run workflow** 버튼 클릭
4. 실행 로그 확인 (약 3~5분 소요)
5. Telegram에서 PDF 수신 확인 ✅

---

## STEP 5 — 자동 스케줄 확인

`.github/workflows/daily_report.yml`에 설정된 스케줄:

```
cron: '0 0 * * 1-5'   →  매주 월~금 오전 9:00 KST
```

GitHub Actions는 UTC 기준으로 동작하며, KST(UTC+9) 오전 9시 = UTC 자정(0:00)입니다.

> ⚠️ GitHub의 무료 플랜은 월 2,000분 제공. 하루 5분 × 22일 = 110분/월 사용 → 충분합니다.

---

## 파일 구조 (저장소)

```
mag7-stock-report/
├── .github/
│   └── workflows/
│       └── daily_report.yml     ← GitHub Actions 스케줄
├── cowork_agents/
│   ├── report_engine.py         ← PDF 생성 엔진
│   └── daily_mag7.py            ← (참고용)
├── local_mag7_real.py           ← 메인 실행 파일
├── telegram_sender.py           ← Telegram 전송
├── requirements.txt             ← 라이브러리 목록
├── .gitignore                   ← reports/ 폴더 제외
└── GITHUB_SETUP.md              ← 이 파일
```

---

## 문제 해결

**Actions 탭이 안 보임**: Settings → Actions → General → Allow all actions 확인

**Telegram 전송 실패**: Secrets에 BOT_TOKEN, CHAT_ID가 정확히 입력됐는지 확인

**yfinance 오류**: 마켓이 닫혀있는 시간에도 히스토리 데이터는 받아올 수 있음. 주말/공휴일에는 최근 데이터 기준으로 생성됨

**스케줄이 안 실행됨**: GitHub은 저장소가 60일 이상 비활성화되면 스케줄을 자동 중지함. Actions 탭에서 **Enable** 클릭으로 재활성화
