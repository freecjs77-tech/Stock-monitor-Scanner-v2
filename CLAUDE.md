# StockReport v5.2 — Claude 전역 작업 지침

이 프로젝트에서 Claude가 따라야 할 패턴과 지침입니다.
작업 전 반드시 이 파일을 읽고 준수하세요.

---

## 1. 프로젝트 개요

- **목적**: 관심 종목 매일 기술적 분석 리포트 자동 생성 및 GitHub Pages 배포
- **스택**: Python(yfinance, reportlab, Jinja2), Streamlit(app.py), GitHub Actions
- **배포**: `docs/` 폴더 → GitHub Pages (`https://freecjs77-tech.github.io/mag7-stock-report/`)
- **자동 실행**: 월~토 오전 7시 KST (`cron: '0 22 * * 0-5'` UTC)

---

## 2. 시그널 시스템 (v5.2)

### 핵심 원칙
- 시그널은 **순수 기술지표**로만 판정
- **시장 필터(QQQ/SPY MA200, VIX)는 참고용** — 판정에 사용하지 않음
- BLOCKED 시그널 없음 — 어떤 시장 상황에서도 BUY 가능
- **확실한 매수 타이밍**: 과매도 확인 + 반전 확인 + **2일 연속 유지**
- **Exit 시그널은 고점에서 익절용으로만 사용** — 하락장에서는 HOLD (손절 없음)

### Entry 시그널
| 시그널 | 의미 | 비중 | 확정 기준 |
|--------|------|------|----------|
| `3rd_BUY` | 추세 전환 확정 | 50% | 2일 연속 |
| `2nd_BUY` | 바닥 확인 + 반전 확인 | 30% | 2일 연속 |
| `1st_BUY` | 과매도 바닥에서 첫 진입 | 20% | 2일 연속 |
| `WATCH` | 진입 조건 일부 충족 | - | - |
| `HOLD` | 보유 유지, 특별한 액션 없음 | - | - |
| `CASH` | 현금성 자산 (BIL) | - | - |
| `BOND_WATCH` | 채권 금리 트리거 직전 | - | - |

### Exit 시그널 (익절 전용)
| 시그널 | 의미 | 조치 |
|--------|------|------|
| `TOP_SIGNAL` | 강한 과열 (RSI≥75/BB 2일/3일+10%) | 즉시 일부 익절 |
| `TAKE_PROFIT_2` | 상승 종료 (고점게이트+MACD가드) | 대량 익절 50% |
| `TAKE_PROFIT_1` | 상승 둔화 (고점게이트+MACD가드) | 1차 익절 30% |

### 시그널 색상
| 시그널 | 색상 |
|--------|------|
| `3rd_BUY` | `#00E676` (밝은 초록) |
| `2nd_BUY` | `#26C6DA` (청록) |
| `1st_BUY` | `#FFEE58` (노랑) |
| `WATCH` | `#B0BEC5` (회색) |
| `HOLD` | `#FFFFFF` (흰색) |
| `TOP_SIGNAL` | `#FF1744` (빨강) |
| `TAKE_PROFIT_2` | `#EF5350` (연빨강) |
| `TAKE_PROFIT_1` | `#FFA726` (주황) |

---

## 3. 전략 유형 (8종)

| 전략 | strategy_type | 대상 종목 |
|------|--------------|----------|
| Growth v2.3 | `growth` | NVDA, TSLA, PLTR, AAPL, MSFT, GOOGL, AMZN 등 |
| ETF v2.4 | `etf` | QQQ, SPY, VOO, SCHD, JEPI 등 |
| Energy v2.3 | `energy` | XOM, CVX, OXY 등 |
| Value v2.4 | `value` | O, UNH |
| Bond v2.6 | `bond` | TLT |
| Metal v2.6 | `metal` | GLD, SLV |
| Speculative | `speculative` | TQQQ, SOXL, CRCL 등 |
| Cash | `bil` | BIL (항상 CASH) |

---

## 4. BUY 연속일 확인제

- BUY 시그널은 **2일 연속** 유지해야 확정
- 1일차: 시그널 + "확인 대기 1/2일" 배지
- 2일차+: "확정 N일 연속" 배지 → 실제 매수 고려
- 승격(1st→2nd→3rd) 시 연속 누적
- 비BUY 전환 시 카운트 리셋
- Exit 시그널은 연속일 확인 없이 즉시 발동
- 이력: `history/signals_history.json`

---

## 5. 파일 역할 분리 원칙

| 파일 | 역할 |
|------|------|
| `local_mag7_real.py` | yfinance 데이터 수집 + 시그널 플래그 계산 + streak 적용 + `mag7_data.json` 저장 |
| `cowork_agents/report_engine.py` | `trading_signal()`, `calc_exit_signal()`, `apply_streak()`, PDF 생성 |
| `render_html.py` | `mag7_data.json` → Jinja2 → `docs/*.html` 생성 |
| `templates/` | Jinja2 HTML 템플릿 |
| `docs/` | GitHub Pages 서빙 디렉토리 (직접 편집 금지) |
| `app.py` | Streamlit UI — report_engine import로 판정 위임 |
| `tickers.json` | 관심 종목 목록 |
| `history/signals_history.json` | BUY 연속일 이력 |
| `.github/workflows/daily.yml` | 자동 실행 워크플로우 |

---

## 6. 핵심 함수 (report_engine.py)

| 함수 | 용도 |
|------|------|
| `trading_signal(d)` | v5.2 통합 시그널 판정 (시장필터 미사용) |
| `calc_exit_signal(d)` | v5.2 익절 전용 Exit (고점게이트+MACD가드) |
| `apply_streak(ticker, signal, history)` | BUY 연속일 확인 |
| `_get_strategy_type(d)` | 8종 전략 분류 |
| `_market_filter(d)` | QQQ/SPY MA200 (참고용) |
| `get_condition_breakdown(d)` | HTML 조건 breakdown |
| `trading_stage(d)` / `trading_stage2(d)` | 하위호환 래퍼 → trading_signal() 위임 |

---

## 7. 금지 사항

| 금지 | 이유 |
|------|------|
| 시장필터로 시그널 차단 | v5.2: 시장필터는 참고용 |
| `entry3/entry2/entry1` 키 사용 | `3rd_BUY/2nd_BUY/1st_BUY` 사용 |
| `watch_market/caution_market` 키 사용 | 삭제됨. `HOLD` 사용 |
| Exit에서 -8% 트레일링 스탑 | 삭제됨. 손절 없음 |
| Exit Level 1 (Early Warning) | 삭제됨 |
| auto_score로 판정 | 제거됨 (PDF 내부에서만 잔존) |
| `docs/` 직접 편집 | 템플릿 수정 후 render_html.py 실행 |

---

## 8. 커밋 & 배포 규칙

- 커밋 메시지: `fix:`, `feat:`, `chore:` prefix
- `docs/` 변경: `render_html.py` 실행 후 커밋
- 로직 변경 시: `report_engine.py` + `render_html.py` + `app.py` 일관성 확인
- 강제 push 금지
- `history/signals_history.json`도 배포 커밋에 포함
