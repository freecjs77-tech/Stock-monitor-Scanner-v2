# Mag7 Stock Report + Telegram 자동 전송 설정 가이드

## 리포트 생성 방식 선택

| 방식 | 파일 | 장점 | 데이터 |
|------|------|------|--------|
| **로컬 (권장)** | `local_mag7_real.py` | 실제 Yahoo Finance 데이터, 정확한 차트 | ✅ 실제 |
| Cowork 스케줄 | `cowork_agents/daily_mag7.py` | 자동 실행 (PC 불필요) | ⚠️ 합성 (실제 지표값 사용) |

> **권장**: `local_mag7_real.py` 를 로컬에서 실행하면 yfinance로 실제 주가 데이터를 사용한 정확한 차트가 생성됩니다.

---

## 전체 구조 (로컬 실행 방식)

```
[Windows Task Scheduler - 오전 9:00]
  local_mag7_real.py 실행
  ↓
  yfinance로 8종목 실제 OHLCV 다운로드
  ↓
  MA/RSI/MACD/BB 실제 지표 계산
  ↓
  PDF 생성 → cowork_agents/reports/ 저장
  ↓
[Windows Task Scheduler - 오전 9:30]
  telegram_sender.py 실행
  ↓
  @MyStockMonitor_bot → Telegram 전송
```

또는 한 번에:
```
python local_mag7_real.py --send    # 생성 + 전송 동시
```

---

## STEP 1 — Python 및 라이브러리 설치

CMD 또는 PowerShell에서:
```
python --version
pip install yfinance requests pypdf reportlab matplotlib numpy pandas
```

---

## STEP 2 — Chat ID 확인

1. Telegram에서 **@MyStockMonitor_bot** 에 `/start` 전송
2. CMD에서 아래 명령 실행:

```
python "C:\Users\micke\Documents\Stock-Analyst\telegram_sender.py" --setup
```

3. 출력된 Chat ID(숫자)를 복사

4. `telegram_sender.py` 파일을 메모장으로 열어 아래 줄 수정:
```python
CHAT_ID = ""   # ← 여기에 숫자 붙여넣기
# 예: CHAT_ID = "123456789"
```

---

## STEP 3 — 연결 테스트

```
python "C:\Users\micke\Documents\Stock-Analyst\telegram_sender.py" --test
```

Telegram에 테스트 메시지가 오면 성공!

---

## STEP 4 — Windows 작업 스케줄러 등록

### 작업 1: 리포트 생성 (오전 9:00)

PowerShell을 관리자 권한으로 열고:

```powershell
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument '"C:\Users\micke\Documents\Stock-Analyst\local_mag7_real.py"' `
  -WorkingDirectory "C:\Users\micke\Documents\Stock-Analyst"

$trigger = New-ScheduledTaskTrigger `
  -Weekly `
  -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
  -At "09:00AM"

$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
  -TaskName "Mag7 Report Generator" `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -RunLevel Highest `
  -Force
```

### 작업 2: Telegram 전송 (오전 9:30)

```powershell
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument '"C:\Users\micke\Documents\Stock-Analyst\telegram_sender.py"' `
  -WorkingDirectory "C:\Users\micke\Documents\Stock-Analyst"

$trigger = New-ScheduledTaskTrigger `
  -Weekly `
  -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
  -At "09:30AM"

$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
  -TaskName "Mag7 Telegram Sender" `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -RunLevel Highest `
  -Force
```

> **대안**: `local_mag7_real.py --send` 를 9:00에 등록하면 생성+전송을 한 번에 처리합니다. (작업 2 불필요)

**GUI 등록 방법**

1. 작업 스케줄러 실행 (검색: `taskschd.msc`)
2. 기본 작업 만들기 클릭
3. 이름: `Mag7 Report Generator`
4. 트리거: 매주 → 월~금 → 오전 9:00
5. 동작: 프로그램 시작
   - 프로그램: `python`
   - 인수: `"C:\Users\micke\Documents\Stock-Analyst\local_mag7_real.py"`

---

## STEP 5 — 첫 실행 테스트

리포트가 이미 생성되어 있으면 바로 전송 테스트 가능:

```
python "C:\Users\micke\Documents\Stock-Analyst\telegram_sender.py" --all
```

---

## 파일 위치 요약

| 파일 | 역할 |
|------|------|
| `local_mag7_real.py` | ✅ **로컬 실행용** — yfinance 실제 데이터로 PDF 생성 |
| `telegram_sender.py` | Telegram 전송 스크립트 |
| `cowork_agents/report_engine.py` | PDF 생성 엔진 (공통 사용) |
| `cowork_agents/daily_mag7.py` | Cowork 스케줄용 — 합성 데이터 기반 |
| `cowork_agents/mag7_data.json` | 최신 주가 데이터 캐시 (local_mag7_real.py가 업데이트) |
| `cowork_agents/reports/` | 생성된 PDF 저장 폴더 |

---

## 일정 타임라인

| 시각 | 동작 |
|------|------|
| 오전 9:00 | Windows Task Scheduler → `local_mag7_real.py` 실행 |
| 오전 9:00~9:15 | yfinance로 8종목 실제 데이터 다운로드 + PDF 생성 |
| 오전 9:30 | Windows Task Scheduler → `telegram_sender.py` 실행 |
| 오전 9:31~9:33 | Telegram으로 통합 PDF 1개 전송 완료 |

---

## 빠른 테스트

```
# 오늘 리포트 한 번 직접 생성해보기
python "C:\Users\micke\Documents\Stock-Analyst\local_mag7_real.py"

# 특정 종목만
python "C:\Users\micke\Documents\Stock-Analyst\local_mag7_real.py" NVDA TSLA

# 생성 후 바로 텔레그램 전송
python "C:\Users\micke\Documents\Stock-Analyst\local_mag7_real.py" --send
```

## 문제 해결

**`yfinance` 없음**: `pip install yfinance` 실행
**PDF가 안 보임**: `cowork_agents/reports/` 폴더 확인, 스크립트 직접 실행해서 오류 확인
**Telegram 전송 실패**: `telegram_sender.py --test` 로 연결 확인
**오늘 날짜 PDF 없음**: `telegram_sender.py`가 30초 자동 대기 후 재시도함
**Yahoo Finance 연결 오류**: 인터넷 연결 확인, VPN 사용 시 해제 후 재시도
