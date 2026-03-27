# StockReport — Claude 전역 작업 지침

이 프로젝트에서 Claude가 따라야 할 패턴과 지침입니다.
작업 전 반드시 이 파일을 읽고 준수하세요.

---

## 1. 프로젝트 개요

- **목적**: MAG7 + 관심 종목 매일 기술적 분석 리포트 자동 생성 및 GitHub Pages 배포
- **스택**: Python(yfinance, reportlab, Jinja2), Streamlit(app.py), GitHub Actions
- **배포**: `docs/` 폴더 → GitHub Pages (`https://freecjs77-tech.github.io/mag7-stock-report/`)
- **자동 실행**: 월~토 오전 7시 KST (`cron: '0 22 * * 0-5'` UTC)

---

## 2. v2.2 분할 매수 전략 — 핵심 규칙

### 스테이지 키 & 라벨 & 색상 (전파일 통일)

| stage_key | 라벨 | 색상 | 비고 |
|---|---|---|---|
| `entry3` | 본격 매수 | `#00E676` | 밝은 초록 |
| `entry2` | 바닥 확인 | `#26C6DA` | 청록 |
| `entry1` | 관심 진입 | `#FFEE58` | 노랑 |
| `caution_market` | 경계장 | `#FFA726` | 주황 |
| `watch_market` | 하락장 | `#EF5350` | 빨강 |
| `watch` | 대기 | `#FFFFFF` | 흰색 |

> **금지**: `buy3`, `buy2`, `buy1` 등 구버전 stage key 사용 절대 금지. 모든 파일에서 `entry3/entry2/entry1` 사용.

### 판정1 vs 판정2

- **판정1** (`trading_stage` / `trading_stage_v2`): QQQ+SPY Dual MA200 시장 필터 **포함**
- **판정2** (`trading_stage2` / `trading_stage2_v2`): 기술신호만, 시장 필터 **제외**

### 시장 필터 기준 (v2.2)

- 정상장: QQQ > MA200 AND SPY > MA200 → 전 단계(entry1/2/3) 허용
- 경계장: 둘 중 하나만 MA200 위 → entry1(20%)만 허용
- 하락장: QQQ·SPY 모두 MA200 아래 → 신규 매수 금지 (`watch_market`)

### RSI > 75 차단 규칙: 완전 제거됨 (v2.2에서 삭제)

---

## 3. 파일 역할 분리 원칙

| 파일 | 역할 |
|---|---|
| `local_mag7_real.py` | yfinance 데이터 수집 + PDF 생성 + `mag7_data.json` 저장 |
| `cowork_agents/report_engine.py` | PDF 리포트 엔진, `trading_stage()`, `trading_stage2()` 정의 |
| `render_html.py` | `mag7_data.json` → Jinja2 → `docs/*.html` 생성 |
| `templates/` | Jinja2 HTML 템플릿 (수정 시 render_html.py 재실행 필요) |
| `docs/` | GitHub Pages 서빙 디렉토리 (자동 생성됨, 직접 편집 금지) |
| `app.py` | Streamlit UI, 종목 관리, 워크플로우 트리거 |
| `tickers.json` | 관심 종목 목록 (GitHub API로 관리) |
| `.github/workflows/daily.yml` | 자동 실행 워크플로우 |

---

## 4. 코드 수정 시 준수 사항

### 스테이지 관련 수정
- 스테이지 키/라벨/색상 변경 시 **반드시 동시에** 수정해야 할 파일:
  1. `app.py` — `trading_stage_v2()`, `trading_stage2_v2()`, `stage_pill_cls()`
  2. `cowork_agents/report_engine.py` — `trading_stage()`, `trading_stage2()`, `_badge_stage()`
  3. `render_html.py` — `get_badge_class()`
  4. `.github/workflows/daily.yml` — 텔레그램/이메일 badge 딕셔너리
  5. `templates/print_all.html` — badge CSS 클래스

### 색상 시스템
- 다크 테마 기반: 배경 `#060D18`, 패널 `#0A1525`
- PDF 인쇄 시 다크 테마 보존: `* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }`
- 각 라벨은 고유 색상 유지 (대기=흰색, 관심 진입=노랑 등 변경 금지)

### HTML 템플릿 수정
- `templates/` 수정 후 반드시 `render_html.py` 실행하여 `docs/` 재생성
- `docs/*.html`은 직접 편집하지 말고 템플릿+렌더 파이프라인 사용

---

## 5. 종목 등록/수집 관련

### `tickers.json` 관리
- Streamlit UI의 "+ 추가"/"✕ 삭제" → GitHub API로 직접 커밋
- 워크플로우 트리거 전 `tickers.json` 최신 버전 보장 (workflow에 `git fetch` 포함)

### `mag7_data.json` 생성 원칙
- 수집 실패 종목은 **기존 데이터 유지** (덮어쓰기 금지)
- 최소 데이터 기준: 30일 이상
- 신규 상장 종목은 데이터 부족으로 처리될 수 있음 → UI에서 경고 표시

### `COMPANY_INFO` 딕셔너리 (`local_mag7_real.py`)
- 알려지지 않은 종목은 `COMPANY_INFO`에 없어도 처리 가능 (yfinance에서 자동 조회)
- 신규 주요 종목 추가 시 `COMPANY_INFO`에 수동 등록 권장

---

## 6. GitHub Actions 워크플로우 규칙

- 스케줄: `cron: '0 22 * * 0-5'` = **KST 월~토 오전 7시** (변경 금지)
- `[skip ci]` 태그로 Actions 루프 방지
- 배포 push는 `docs/`와 `cowork_agents/mag7_data.json`만 포함
- `tickers.json`은 UI에서 관리하므로 워크플로우에서 수정하지 않음

---

## 7. 커밋 & 배포 규칙

- `docs/` 변경만 있을 때: `render_html.py` 실행 후 커밋
- 로직 변경 시: `app.py` + `report_engine.py` + `render_html.py` 동시 일관성 확인
- 커밋 메시지 형식: `fix:`, `feat:`, `chore:` prefix 사용
- 강제 push (`--force`) 금지

---

## 8. 자주 발생하는 실수 방지

| 실수 | 방지책 |
|---|---|
| 구버전 stage key (`buy3` 등) 사용 | 항상 `entry3/entry2/entry1` 사용 |
| `docs/` 직접 편집 | 템플릿 수정 후 `render_html.py` 실행 |
| PDF 인쇄 시 흰 배경 변환 | `print-color-adjust: exact` 유지 |
| 신규 종목 "데이터 없음" | 기존 data fallback 로직 확인 |
| 레이스 컨디션 (tickers 저장 → 즉시 실행) | workflow에 `git fetch origin main -- tickers.json` 포함 |
| 텍스트에 잘못된 실행 시간 표시 | 항상 "월~토 오전 7시 KST"로 표기 |
