#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=======================================================
  Mag7 Daily Report — Real Data Version (Windows Local)
  yfinance로 실제 OHLCV 데이터를 받아 정확한 기술적 지표 계산
=======================================================

필요 라이브러리:
    pip install yfinance pandas pypdf reportlab matplotlib numpy

실행 방법:
    python local_mag7_real.py              # 8종목 전체 리포트 생성
    python local_mag7_real.py --send       # 생성 후 Telegram 전송
    python local_mag7_real.py NVDA TSLA    # 특정 종목만 생성
"""

import os, sys, datetime, json, time
import numpy as np

try:
    import yfinance as yf
except ImportError:
    print("[ERROR] yfinance 미설치. 실행: pip install yfinance")
    sys.exit(1)

try:
    from pypdf import PdfWriter
except ImportError:
    print("[ERROR] pypdf 미설치. 실행: pip install pypdf")
    sys.exit(1)

# ── 경로 설정 ──────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR  = os.path.join(SCRIPT_DIR, 'cowork_agents')
REPORTS_DIR = os.path.join(AGENTS_DIR, 'reports')
DATA_FILE   = os.path.join(AGENTS_DIR, 'mag7_data.json')

sys.path.insert(0, AGENTS_DIR)

try:
    from report_engine import generate_report, generate_summary_page, build_index_page
except ImportError as e:
    print(f"[ERROR] report_engine 로드 실패: {e}")
    print(f"        cowork_agents/ 폴더가 {AGENTS_DIR} 에 있는지 확인하세요.")
    sys.exit(1)

try:
    from ai_summary import generate_ai_summary
except ImportError:
    generate_ai_summary = None

# ── tickers.json에서 종목 목록 로드 ────────────────────────────────
TICKERS_FILE = os.path.join(SCRIPT_DIR, 'tickers.json')

def load_tickers_from_config():
    """tickers.json에서 종목 목록을 읽어옴. 없으면 기본값 사용."""
    if os.path.exists(TICKERS_FILE):
        try:
            with open(TICKERS_FILE, encoding='utf-8') as f:
                data = json.load(f)
            tickers = data.get('tickers', [])
            if tickers:
                print(f"  [CONFIG] tickers.json 로드: {', '.join(tickers)}")
                return tickers
        except Exception as e:
            print(f"  [WARN] tickers.json 읽기 실패: {e}")
    default = ['NVDA', 'PLTR', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    print(f"  [CONFIG] 기본 종목 사용: {', '.join(default)}")
    return default

ALL_TICKERS = load_tickers_from_config()

COMPANY_INFO = {
    'NVDA':  {'company': 'NVIDIA Corporation',    'sector': 'AI / 반도체',          'exchange': 'NASDAQ'},
    'PLTR':  {'company': 'Palantir Technologies',  'sector': 'AI / 방산 소프트웨어', 'exchange': 'NASDAQ'},
    'TSLA':  {'company': 'Tesla Inc.',              'sector': 'EV / 에너지',          'exchange': 'NASDAQ'},
    'AAPL':  {'company': 'Apple Inc.',              'sector': '소비자 전자기기',       'exchange': 'NASDAQ'},
    'MSFT':  {'company': 'Microsoft Corporation',  'sector': '클라우드 / AI 플랫폼', 'exchange': 'NASDAQ'},
    'GOOGL': {'company': 'Alphabet Inc.',           'sector': '검색 / 클라우드 / AI', 'exchange': 'NASDAQ'},
    'AMZN':  {'company': 'Amazon.com Inc.',         'sector': '이커머스 / 클라우드',  'exchange': 'NASDAQ'},
    'META':  {'company': 'Meta Platforms Inc.',     'sector': 'SNS / AI 광고',        'exchange': 'NASDAQ'},
}


# ══════════════════════════════════════════════════════════════════
#  기술적 지표 계산 함수
# ══════════════════════════════════════════════════════════════════

def calc_rsi(close_arr, period=14):
    """Wilder 평활 RSI"""
    delta = np.diff(close_arr.astype(float))
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    n = len(close_arr)
    rsi_full = np.full(n, np.nan)
    if len(delta) < period:
        return rsi_full
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    if avg_loss == 0:
        rsi_full[period] = 100.0
    else:
        rsi_full[period] = 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0:
            rsi_full[i + 1] = 100.0
        else:
            rsi_full[i + 1] = 100 - 100 / (1 + avg_gain / avg_loss)
    return rsi_full


def calc_macd(close_arr, fast=12, slow=26, signal=9):
    """MACD / Signal / Histogram"""
    c = close_arr.astype(float)
    n = len(c)

    def ema(arr, span):
        k = 2 / (span + 1)
        r = np.full(n, np.nan)
        if span - 1 >= n:
            return r
        r[span - 1] = arr[:span].mean()
        for i in range(span, n):
            if np.isnan(arr[i]):
                r[i] = r[i - 1]
            else:
                r[i] = arr[i] * k + r[i - 1] * (1 - k)
        return r

    e12   = ema(c, fast)
    e26   = ema(c, slow)
    macd  = e12 - e26
    sig   = ema(np.nan_to_num(macd), signal)
    hist  = macd - sig
    return macd, sig, hist


def calc_adx(high_arr, low_arr, close_arr, period=14):
    """ADX / +DI / -DI (Wilder 평활법)
    TR/+DM/-DM : Wilder sum-init  (누적합으로 시작 — 표준)
    DX → ADX  : Wilder mean-init  (단순평균으로 시작 — ADX 표준)
    """
    n = len(close_arr)
    h = high_arr.astype(float); l = low_arr.astype(float); c = close_arr.astype(float)
    tr = np.zeros(n); pdm = np.zeros(n); ndm = np.zeros(n)
    for i in range(1, n):
        tr[i]  = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
        up = h[i]-h[i-1]; dn = l[i-1]-l[i]
        pdm[i] = up if (up > dn and up > 0) else 0
        ndm[i] = dn if (dn > up and dn > 0) else 0

    def wilder_sum(arr, p):
        """TR/DM용: 첫 값 = 구간 합계 (Wilder 원래 방식)"""
        s = np.full(n, np.nan)
        if p >= n: return s
        s[p] = arr[1:p+1].sum()
        for i in range(p+1, n):
            s[i] = s[i-1] - s[i-1]/p + arr[i]
        return s

    def wilder_mean(arr, p):
        """ADX용: 첫 값 = 구간 평균, 이후 = (prev*(p-1) + cur) / p
        → 항상 0~100 스케일 유지 (sum-scale Wilder와 공식이 다름)"""
        s = np.full(n, np.nan)
        start = np.where(~np.isnan(arr))[0]
        if len(start) < p: return s
        idx = start[0] + p - 1
        if idx >= n: return s
        s[idx] = np.nanmean(arr[start[0]:idx+1])   # 단순평균으로 초기화
        for i in range(idx+1, n):
            cur = arr[i] if not np.isnan(arr[i]) else s[i-1]
            s[i] = (s[i-1] * (p - 1) + cur) / p   # 평균 스케일 업데이트
        return s

    atr  = wilder_sum(tr,  period)
    apdm = wilder_sum(pdm, period)
    andm = wilder_sum(ndm, period)
    pdi  = np.where(atr > 0, 100*apdm/atr, 0.0)
    ndi  = np.where(atr > 0, 100*andm/atr, 0.0)
    dsum = pdi + ndi
    dx   = np.where(dsum > 0, 100*np.abs(pdi-ndi)/dsum, 0.0)
    dx[np.isnan(atr)] = np.nan
    return wilder_mean(dx, period), pdi, ndi


def detect_rsi_divergence(close_arr, rsi_arr, lookback=30):
    """
    RSI 다이버전스 감지 (최근 lookback일 기준)
    Returns: 'bullish' | 'bearish' | 'none'
    - 강세: 가격 신저점 + RSI 고저점 → 반전 매수 신호
    - 약세: 가격 신고점 + RSI 저고점 → 조정 경고
    """
    if len(close_arr) < lookback + 3:
        return 'none'
    c   = close_arr[-lookback:].astype(float)
    rsi = rsi_arr[-lookback:].astype(float)
    if np.isnan(rsi).sum() > lookback // 2:
        return 'none'
    mid     = lookback // 2
    cur_c   = float(c[-3:].mean())
    cur_rsi = float(np.nanmean(rsi[-3:]))
    # 강세 다이버전스
    if cur_c <= float(c[:mid].min()) * 1.02 and cur_rsi >= float(np.nanmin(rsi[:mid])) + 5:
        return 'bullish'
    # 약세 다이버전스
    if cur_c >= float(c[:mid].max()) * 0.98 and cur_rsi <= float(np.nanmax(rsi[:mid])) - 5:
        return 'bearish'
    return 'none'


def calc_bollinger(close_arr, period=20, std_dev=2):
    n = len(close_arr)
    c = close_arr.astype(float)
    ma  = np.full(n, np.nan)
    bbu = np.full(n, np.nan)
    bbl = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = c[i - period + 1:i + 1]
        m = window.mean()
        s = window.std(ddof=0)
        ma[i]  = m
        bbu[i] = m + std_dev * s
        bbl[i] = m - std_dev * s
    return ma, bbu, bbl


# ══════════════════════════════════════════════════════════════════
#  yfinance 데이터 다운로드 + 지표 계산
# ══════════════════════════════════════════════════════════════════

def _translate_ko(text):
    """영문 텍스트를 한국어로 번역 — 실패 시 원문 반환"""
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='auto', target='ko').translate(text[:500])
        return result or text
    except Exception:
        return text


def fetch_news(tk, ticker):
    """최근 7일 뉴스 수집 + 한글 번역 (최대 5건)"""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    news_list = []
    try:
        raw = tk.news or []
    except Exception:
        return []

    for item in raw:
        try:
            content   = item.get('content', item)           # 신/구 구조 모두 대응
            title_en  = (content.get('title') or '').strip()
            pub_date  = content.get('pubDate') or ''
            publisher = ''
            provider  = content.get('provider', {})
            if isinstance(provider, dict):
                publisher = (provider.get('displayName') or '')[:18]
            else:
                publisher = str(provider)[:18]

            if not title_en:
                continue

            # 날짜 파싱 (ISO 8601: "2026-03-24T22:00:10Z")
            if pub_date:
                pub_dt = datetime.datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            else:
                continue

            if pub_dt < cutoff.replace(tzinfo=datetime.timezone.utc):
                continue

            date_str   = pub_dt.strftime('%m/%d')
            # 요약 내용 우선, 없으면 제목 사용
            summary_en = (content.get('summary') or title_en)[:400]
            summary_ko = _translate_ko(summary_en)
            news_list.append({'date': date_str, 'summary': summary_ko, 'publisher': publisher})

            if len(news_list) >= 5:
                break
        except Exception:
            continue

    return news_list


def fetch_stock_data(ticker, retry=2):
    """실제 1년 OHLCV 다운로드 및 기술적 지표 계산"""
    for attempt in range(1, retry + 1):
        try:
            print(f"  [{ticker}] Yahoo Finance 다운로드 중... (시도 {attempt}/{retry})")
            tk   = yf.Ticker(ticker)
            hist = tk.history(period='1y', interval='1d', auto_adjust=True)

            if hist.empty or len(hist) < 50:
                print(f"  [{ticker}] 경고: 데이터 부족 ({len(hist)}일)")
                if attempt < retry:
                    time.sleep(2)
                    continue
                return None

            # 기본 배열
            close = hist['Close'].values.astype(float)
            high  = hist['High'].values.astype(float)
            low_h = hist['Low'].values.astype(float)
            vol   = hist['Volume'].values.astype(float)
            n     = len(close)

            # SMA
            def sma(w):
                r = np.full(n, np.nan)
                for i in range(w - 1, n):
                    r[i] = close[i - w + 1:i + 1].mean()
                return r

            ma20_arr  = sma(20)
            ma50_arr  = sma(50)
            ma200_arr = sma(200)

            # Bollinger Bands
            _, bb_u_arr, bb_l_arr = calc_bollinger(close, 20, 2)

            # RSI
            rsi_arr = calc_rsi(close, 14)

            # MACD (히스토그램 포함)
            macd_arr, macd_sig_arr, hist_arr = calc_macd(close)

            # 현재값 추출
            cur_close  = float(close[-1])
            prev_close = float(close[-2]) if n >= 2 else cur_close
            change_pct = (cur_close - prev_close) / prev_close * 100

            # 52주 고저 및 날짜
            high_52w     = float(high.max())
            low_52w      = float(low_h.min())
            high_52w_idx = np.argmax(high)
            low_52w_idx  = np.argmin(low_h)

            dates = hist.index
            high_52w_date = dates[high_52w_idx].strftime('%Y년 %m월') if len(dates) > high_52w_idx else '최근'
            low_52w_date  = dates[low_52w_idx].strftime('%Y년 %m월')  if len(dates) > low_52w_idx  else '최근'

            # 최종 지표값 (NaN 처리)
            def safe(arr, fallback):
                v = arr[-1]
                return float(v) if not np.isnan(v) else fallback

            ma20_val   = safe(ma20_arr,  cur_close)
            ma50_val   = safe(ma50_arr,  cur_close)
            ma200_val  = safe(ma200_arr, cur_close)
            bb_u_val   = safe(bb_u_arr,  cur_close * 1.10)
            bb_l_val   = safe(bb_l_arr,  cur_close * 0.90)
            rsi_val    = safe(rsi_arr,   50.0)
            macd_val   = safe(macd_arr,  0.0)
            macd_s_val = safe(macd_sig_arr, 0.0)

            avg_vol = float(vol[-20:].mean())
            cur_vol = float(vol[-1])

            # ── 방향성 지표 (5일·3일 기울기) ────────────────────────────
            def slope_n(arr, n):
                """최근 n일 기울기 (끝에서 n+1번째 → 어제)"""
                seg = arr[-(n+1):-1]; v = seg[~np.isnan(seg)]
                return float(v[-1] - v[0]) if len(v) >= 2 else 0.0

            rsi_slope        = slope_n(rsi_arr,  5)   # 5일 추세
            rsi_slope3       = slope_n(rsi_arr,  3)   # 3일 단기 반등 감지
            macd_hist_slope  = slope_n(hist_arr, 5)
            macd_hist_slope3 = slope_n(hist_arr, 3)
            ma20_slope       = slope_n(ma20_arr, 5)

            # ADX / +DI / -DI
            adx_arr, pdi_arr, ndi_arr = calc_adx(high, low_h, close, 14)

            # RSI 다이버전스
            divergence = detect_rsi_divergence(close, rsi_arr)

            # 의견 메모
            above_ma = sum([cur_close > ma20_val, cur_close > ma50_val, cur_close > ma200_val])
            if above_ma == 3:
                opinion = '강세 유지'
            elif above_ma == 2:
                opinion = '중립/강세'
            elif above_ma == 1:
                opinion = '중립/약세'
            else:
                opinion = '약세 지속'

            info = COMPANY_INFO.get(ticker, {'company': ticker, 'sector': 'N/A', 'exchange': 'NASDAQ'})

            print(f"  [{ticker}] 완료  종가=${cur_close:.2f}  MA20={ma20_val:.2f}  RSI={rsi_val:.1f}  MACD={macd_val:.3f}")

            print(f"  [{ticker}] 뉴스 수집 중...")
            news = fetch_news(tk, ticker)
            print(f"  [{ticker}] 뉴스 {len(news)}건 (7일 이내)")

            return {
                'ticker':        ticker,
                'company':       info['company'],
                'sector':        info['sector'],
                'exchange':      info['exchange'],
                'close':         round(cur_close, 2),
                'change_pct':    round(change_pct, 2),
                'high_52w':      round(high_52w, 2),
                'low_52w':       round(low_52w, 2),
                'ma20':          round(ma20_val, 2),
                'ma50':          round(ma50_val, 2),
                'ma200':         round(ma200_val, 2),
                'rsi':           round(rsi_val, 2),
                'macd':          round(macd_val, 4),
                'macd_signal':   round(macd_s_val, 4),
                'bb_upper':      round(bb_u_val, 2),
                'bb_lower':      round(bb_l_val, 2),
                'volume':        cur_vol,
                'avg_volume':    avg_vol,
                'high_52w_date': high_52w_date,
                'low_52w_date':  low_52w_date,
                'opinion_note':     opinion,
                # 방향성 지표 (5일 추세 + 3일 단기)
                'rsi_slope':         round(rsi_slope,        2),
                'rsi_slope3':        round(rsi_slope3,       2),
                'macd_hist_slope':   round(macd_hist_slope,  4),
                'macd_hist_slope3':  round(macd_hist_slope3, 4),
                'ma20_slope':        round(ma20_slope,       2),
                'adx':               round(safe(adx_arr, 20.0), 1),
                'plus_di':           round(safe(pdi_arr, 25.0), 1),
                'minus_di':          round(safe(ndi_arr, 25.0), 1),
                'rsi_divergence':    divergence,
                'news':             news,
                # 실제 가격 시계열 → report_engine이 차트에 직접 사용
                'price_series':  close.tolist(),
            }

        except Exception as e:
            print(f"  [{ticker}] 오류: {e}")
            if attempt < retry:
                print(f"  [{ticker}] {2}초 후 재시도...")
                time.sleep(2)

    return None


# ══════════════════════════════════════════════════════════════════
#  PDF 병합
# ══════════════════════════════════════════════════════════════════

def merge_pdfs(pdf_paths, output_path):
    writer = PdfWriter()
    for path in pdf_paths:
        writer.append(path)
    with open(output_path, 'wb') as f:
        writer.write(f)
    writer.close()


# ══════════════════════════════════════════════════════════════════
#  메인 실행
# ══════════════════════════════════════════════════════════════════

def run(tickers=None, send_telegram=False):
    today     = datetime.date.today().strftime('%Y-%m-%d')
    today_str = datetime.date.today().strftime('%Y%m%d')
    tickers   = tickers or ALL_TICKERS

    print(f"\n{'='*60}")
    print(f"  Mag7 Real-Data Report  |  {today}")
    print(f"  데이터 소스: yfinance (Yahoo Finance)")
    print(f"  종목 수:     {len(tickers)}  →  {' / '.join(tickers)}")
    print(f"{'='*60}")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    tmp_dir = os.path.join(REPORTS_DIR, '_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    stocks_data = []
    generated   = []

    for ticker in tickers:
        sd = fetch_stock_data(ticker)
        if sd is None:
            print(f"  [{ticker}] SKIP (데이터 없음)")
            continue

        stocks_data.append(sd)

        print(f"  [{ticker}] PDF 생성 중...")
        try:
            path = generate_report(sd, tmp_dir)
            generated.append((ticker, path))
            print(f"  [{ticker}] PDF OK")
        except Exception as e:
            import traceback
            print(f"  [{ticker}] PDF 오류: {e}")
            traceback.print_exc()

    # JSON 저장 (price_series 제외 — 파일 크기 절약)
    if stocks_data:
        data_out = {
            'last_updated': today,
            'source': 'yfinance',
            'stocks': [
                {k: v for k, v in s.items() if k != 'price_series'}
                for s in stocks_data
            ]
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_out, f, ensure_ascii=False, indent=2)
        print(f"\n  [DATA] {DATA_FILE} 업데이트 완료")

    # PDF 병합 (요약 페이지 → 개별 종목 순)
    merged_path = os.path.join(REPORTS_DIR, f'Mag7_Daily_Report_{today_str}.pdf')
    if generated:
        pdf_paths = [p for _, p in generated]

        # AI 요약 생성 (GROQ_API_KEY 있을 때만)
        ai_data = None
        if generate_ai_summary:
            print(f"\n  [AI] Groq 시장 요약 생성 중...")
            try:
                ai_data = generate_ai_summary(stocks_data)
            except Exception as e:
                print(f"  [AI] 오류 (규칙 기반으로 계속): {e}")

        # 요약 페이지 생성
        summary_path = os.path.join(tmp_dir, f'_summary_{today_str}.pdf')
        print(f"\n  [SUMMARY] 요약 페이지 생성 중...")
        try:
            generate_summary_page(stocks_data, summary_path, ai_data=ai_data)
            print(f"  [SUMMARY] 완료")
            pdf_paths = [summary_path] + pdf_paths
        except Exception as e:
            import traceback
            print(f"  [SUMMARY] 오류 (요약 없이 계속): {e}")
            traceback.print_exc()

        print(f"\n  [MERGE] {len(pdf_paths)}개 PDF 병합 중...")
        merge_pdfs(pdf_paths, merged_path)
        print(f"  [MERGE] 완료 → {os.path.basename(merged_path)}")

        # 임시 파일 삭제
        for p in pdf_paths:
            try:
                os.remove(p)
            except Exception:
                pass
        try:
            os.rmdir(tmp_dir)
        except Exception:
            pass

        print(f"\n  [REPORT] {merged_path}")
    else:
        print("\n  [WARN] 생성된 PDF 없음")
        return None

    # 요약 파일 (telegram_sender.py 트리거용)
    summary_path = os.path.join(REPORTS_DIR, f'daily_summary_{today}.txt')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"generated_date={today}\n")
        f.write(f"source=yfinance\n")
        f.write(f"merged={merged_path}\n")
        for ticker, _ in generated:
            f.write(f"{ticker}=OK\n")

    print(f"  [DONE] {len(generated)}/{len(tickers)} 종목 완료")

    # Telegram 전송 (--send 플래그)
    if send_telegram:
        sender = os.path.join(SCRIPT_DIR, 'telegram_sender.py')
        if os.path.exists(sender):
            import subprocess
            print(f"\n  [TELEGRAM] 전송 시작...")
            subprocess.run([sys.executable, sender], check=False)
        else:
            print(f"\n  [WARN] telegram_sender.py 없음: {sender}")

        # Email 전송 (GMAIL_USER 환경변수 있을 때만)
        if os.environ.get('GMAIL_USER'):
            email_sender = os.path.join(SCRIPT_DIR, 'email_sender.py')
            if os.path.exists(email_sender):
                import subprocess
                print(f"\n  [EMAIL] 전송 시작...")
                subprocess.run([sys.executable, email_sender], check=False)
        else:
            print(f"\n  [EMAIL] GMAIL_USER 미설정 — 이메일 전송 건너뜀")

    return merged_path


# ── main ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]

    send_flag = '--send' in args
    # --send 제거 후 남은 인수를 종목 코드로 해석
    tickers_arg = [a for a in args if not a.startswith('--')]
    tickers_arg = [t.upper() for t in tickers_arg if t.upper() in ALL_TICKERS] or None

    run(tickers=tickers_arg, send_telegram=send_flag)
