"""
ta.py - Technical Analysis helper functions.

Extracted from report_engine.py for reuse across modules.
Provides SMA calculation, auto signal generation, scoring,
timing judgment, and opinion labeling.
"""

import numpy as np
from reportlab.lib import colors

GREEN  = colors.HexColor("#1A8C5A")
RED    = colors.HexColor("#C0392B")
ORANGE = colors.HexColor("#CC7A2A")


def sma_arr(arr, w, n):
    r = np.full(n, np.nan)
    for i in range(w - 1, n):
        r[i] = arr[i - w + 1:i + 1].mean()
    return r


def calc_ta(close, vol, d):
    n = len(close)

    def sma(w):
        r = np.full(n, np.nan)
        for i in range(w - 1, n): r[i] = close[i - w + 1:i + 1].mean()
        return r

    def ema(src, span):
        k, r = 2 / (span + 1), np.full(n, np.nan)
        first = span - 1
        if first >= n: return r
        r[first] = np.nanmean(src[:first + 1])
        for i in range(first + 1, n):
            r[i] = src[i] * k + r[i - 1] * (1 - k)
        return r

    ma20  = sma(20);  ma50 = sma(50);  ma200 = sma(200)
    ma20[-1]  = d['ma20'];  ma50[-1] = d['ma50'];  ma200[-1] = d['ma200']

    bb_u = np.full(n, np.nan); bb_l = np.full(n, np.nan)
    for i in range(19, n):
        std = close[i - 19:i + 1].std()
        bb_u[i] = ma20[i] + 2 * std
        bb_l[i] = ma20[i] - 2 * std
    bb_u[-1] = d['bb_upper']; bb_l[-1] = d['bb_lower']

    e12  = ema(close, 12); e26 = ema(close, 26)
    macd = e12 - e26
    sig  = ema(np.nan_to_num(macd), 9)
    hist = macd - sig
    macd[-1] = d['macd']; sig[-1] = d['macd_signal']; hist[-1] = macd[-1] - sig[-1]

    delta = np.diff(close, prepend=close[0])
    ag = sma_arr(np.where(delta > 0, delta, 0), 14, n)
    al = sma_arr(np.where(delta < 0, -delta, 0), 14, n)
    rsi = np.where(al == 0, 100, 100 - 100 / (1 + ag / np.where(al == 0, 1, al)))
    rsi[:13] = np.nan; rsi[-1] = d['rsi']

    return ma20, ma50, ma200, bb_u, bb_l, macd, sig, hist, rsi


def auto_signals(d):
    signals = []
    c = d['close']; m20 = d['ma20']; m50 = d['ma50']; m200 = d['ma200']
    rsi = d['rsi']; macd_v = d['macd']; macd_s = d['macd_signal']
    chg = d['change_pct']

    # MA signals
    above_count = sum([c > m20, c > m50, c > m200])
    if above_count == 0:
        signals.append(('매도', 'MA 역배열', f'현재가 MA20/50/200 전부 하향 - 완전 역배열'))
    elif above_count == 1:
        signals.append(('매수', 'MA20 상향', f'${c:.2f} - MA20(${m20:.2f}) 상향, MA50/200 저항'))
        signals.append(('매도', 'MA50/200 하향', f'MA50 ${m50:.2f} / MA200 ${m200:.2f} - 이중 저항'))
    elif above_count == 2:
        signals.append(('매수', 'MA20/50 상향', f'MA20/50 상향 유지 - 중기 강세'))
        signals.append(('중립', 'MA200 저항', f'MA200 ${m200:.2f} - 장기 저항 근접'))
    else:
        signals.append(('매수', 'MA 정배열', f'현재가 MA20/50/200 전부 상향 - 완전 정배열'))

    if c < m200:
        signals.append(('매도', 'MA200 이탈', f'${c:.2f} - MA200 ${m200:.2f} 하향 이탈'))

    # MACD
    if macd_v < macd_s:
        signals.append(('매도', 'MACD 매도', f'MACD {macd_v:.2f}, 시그널선({macd_s:.2f}) 하회'))
    else:
        signals.append(('매수', 'MACD 매수', f'MACD {macd_v:.2f}, 시그널선({macd_s:.2f}) 상회'))

    # RSI
    if rsi >= 70:
        signals.append(('매도', 'RSI 과매수', f'RSI {rsi:.1f} - 과매수 구간, 조정 주의'))
    elif rsi <= 30:
        signals.append(('매수', 'RSI 과매도', f'RSI {rsi:.1f} - 과매도 구간, 반등 가능'))
    elif rsi < 50:
        signals.append(('중립', 'RSI 중립', f'RSI {rsi:.1f} - 중립권 하단, 방향 미결'))
    else:
        signals.append(('매수', 'RSI 회복', f'RSI {rsi:.1f} - 중립권 상단, 상승 모멘텀'))

    # BB
    bb_pct = (c - d['bb_lower']) / (d['bb_upper'] - d['bb_lower']) if (d['bb_upper'] - d['bb_lower']) > 0 else 0.5
    if bb_pct > 0.85:
        signals.append(('매도', 'BB 상단', f'%B={bb_pct:.2f} - BB 상단 근접, 과열'))
    elif bb_pct < 0.15:
        signals.append(('매수', 'BB 하단', f'%B={bb_pct:.2f} - BB 하단, 반등 대기'))
    else:
        signals.append(('중립', 'BB 중립', f'%B={bb_pct:.2f} - BB 중간권'))

    # Volume + price action
    vol_ratio = d.get('volume', 0) / d.get('avg_volume', 1)
    if chg < -2 and vol_ratio > 1.3:
        signals.append(('매도', '거래량 급증 하락', f'{chg:.1f}% 하락 시 거래량 {vol_ratio:.1f}x - 매도 주도'))
    elif chg > 2 and vol_ratio > 1.3:
        signals.append(('매수', '거래량 급증 상승', f'+{chg:.1f}% 상승 시 거래량 {vol_ratio:.1f}x - 매수 주도'))

    # 52W position
    range_52 = d['high_52w'] - d['low_52w']
    pos_52 = (c - d['low_52w']) / range_52 if range_52 > 0 else 0.5
    if pos_52 > 0.85:
        signals.append(('중립', '52주 고점 근접', f'52주 고점(${d["high_52w"]:.2f}) 대비 {pos_52*100:.0f}% 위치'))
    elif pos_52 < 0.25:
        signals.append(('매수', '52주 저점 근접', f'52주 저점(${d["low_52w"]:.2f}) 근접 - 지지 구간'))

    return signals[:9]  # max 9 rows


def auto_score(d):
    """
    매수/매도 타이밍 관점의 기술적 점수 (0-85 + F페널티)
    A~E: 매수 타이밍 점수 (합계 최대 85)
    F: 백테스트 기반 매도 압력 페널티 (음수, 최대 -20)
    총점 = max(0, A+B+C+D+E+F)
    """
    c = d['close']; m20 = d['ma20']; m50 = d['ma50']; m200 = d['ma200']
    rsi = d['rsi']; macd_v = d['macd']; macd_s = d['macd_signal']

    # A. 추세 강도 (0-20)
    above = sum([c > m20, c > m50, c > m200])
    bullish_aligned = (m20 > m50 > m200)
    a_score = above * 5 + (3 if bullish_aligned and above == 3 else 0) + (2 if above >= 2 else 0)
    a_score = min(a_score, 20)

    # B. 모멘텀 (0-20)
    if rsi >= 70:      rsi_score = 2
    elif rsi >= 60:    rsi_score = 5
    elif rsi >= 45:    rsi_score = 8
    elif rsi >= 30:    rsi_score = 9
    else:              rsi_score = 4
    if macd_v > macd_s and macd_v > 0:   macd_score = 10
    elif macd_v > macd_s:                 macd_score = 7
    elif macd_v > 0:                      macd_score = 4
    else:                                 macd_score = 2
    b_score = min(rsi_score + macd_score, 20)

    # C. BB 위치 (0-15)
    bb_range = d['bb_upper'] - d['bb_lower']
    bb_pct = (c - d['bb_lower']) / bb_range if bb_range > 0 else 0.5
    if bb_pct <= 0.0:       c_score = 4
    elif bb_pct <= 0.20:    c_score = 13
    elif bb_pct <= 0.45:    c_score = 10
    elif bb_pct <= 0.60:    c_score = 7
    elif bb_pct <= 0.80:    c_score = 5
    else:                   c_score = 3
    c_score = min(max(c_score, 0), 15)

    # D. 거래량 (0-15)
    vol_ratio = d.get('volume', 0) / max(d.get('avg_volume', 1), 1)
    chg = d['change_pct']
    if chg > 1.0 and vol_ratio >= 1.5:    d_score = 13
    elif chg > 0 and vol_ratio >= 1.2:    d_score = 10
    elif chg < -1.0 and vol_ratio >= 1.5: d_score = 2
    elif chg < 0 and vol_ratio >= 1.2:    d_score = 4
    else:                                  d_score = 7
    d_score = min(max(d_score, 0), 15)

    # E. MA 지지선 근접도 (0-15)
    near_ma = min(
        abs(c - m20)  / max(m20,  1),
        abs(c - m50)  / max(m50,  1),
        abs(c - m200) / max(m200, 1),
    )
    above_ma200 = c > m200
    if above_ma200 and near_ma < 0.02:    e_score = 14
    elif above_ma200 and near_ma < 0.05:  e_score = 11
    elif above_ma200 and near_ma < 0.10:  e_score = 8
    elif above_ma200:                     e_score = 6
    elif near_ma < 0.03:                  e_score = 4
    else:                                 e_score = 2
    e_score = min(max(e_score, 0), 15)

    # F. 매도 압력 페널티 (0 ~ -20)  ← 백테스트 기반
    # 근거: GOOGL 5Y 분석 — 조건별 하락 예측력 (기준 21.7%)
    macd_dead = macd_v < macd_s
    f_score = 0
    # ① MA50 이탈 + MACD 데드크로스(제로선 위): 하락예측 38.5% (1.77x)
    if c < m50 and macd_dead and macd_v > 0:
        f_score -= 15
    # ② 거래량 급증 하락 -1%+: 하락예측 31.8% (1.47x)
    if chg < -1.0 and vol_ratio >= 1.5:
        f_score -= 8
    # ③ BB 극과열 + RSI 고점: 하락예측 25.9% (1.19x)
    if bb_pct >= 0.90:
        f_score -= 8
    elif bb_pct >= 0.85 and rsi >= 65:
        f_score -= 5
    f_score = max(f_score, -20)  # 최대 -20 페널티

    total = max(0, a_score + b_score + c_score + d_score + e_score + f_score)
    return a_score, b_score, c_score, d_score, e_score, f_score, total


def timing_judgment(d, total):
    """매수/매도 타이밍 종합 판정 — 관심종목(진입) + 보유종목(청산) 기준"""
    c = d['close']; m20 = d['ma20']; m50 = d['ma50']; m200 = d['ma200']
    rsi = d['rsi']; macd_v = d['macd']; macd_s = d['macd_signal']
    bb_range = d['bb_upper'] - d['bb_lower']
    bb_pct   = (c - d['bb_lower']) / bb_range if bb_range > 0 else 0.5

    above_ma200  = c > m200
    macd_bull    = macd_v > macd_s
    rsi_hot      = rsi >= 65
    rsi_cold     = rsi <= 35
    near_support = min(abs(c-m20)/max(m20,1), abs(c-m50)/max(m50,1)) < 0.04

    # 매수 진입 조건
    if above_ma200 and rsi_cold and macd_bull:
        buy_cond = f'현재 진입 검토 — RSI {rsi:.0f} 과매도 + MACD 골든크로스 동시 충족'
    elif above_ma200 and near_support and not rsi_hot:
        buy_cond = f'MA 지지 확인 후 진입 — 현재가 MA선 {min(abs(c-m20)/m20, abs(c-m50)/m50)*100:.1f}% 이격'
    elif above_ma200 and rsi < 45:
        buy_cond = f'RSI {rsi:.0f} — 추가 조정 시 분할 매수 검토 (목표 진입 RSI 30~35)'
    elif not above_ma200:
        buy_cond = f'MA200(${m200:.2f}) 회복 확인 후 진입 — 장기 추세 약세 구간'
    else:
        buy_cond = f'RSI {rsi:.0f} / BB {bb_pct:.2f} — 조정 후 MA 지지 확인 시 분할 진입'

    # 매도/차익실현 조건 — 백테스트 기반 우선순위
    vol_ratio = d.get('volume', 0) / max(d.get('avg_volume', 1), 1)
    chg = d['change_pct']
    # 조건①: MA50 이탈 + MACD 데드크로스(제로 위) — 38.5% 하락예측
    if c < m50 and not macd_bull and macd_v > 0:
        sell_cond = f'MA50(${m50:.2f}) 이탈 + MACD 데드크로스(제로선 위) — 단기 추세 붕괴, 비중 축소 권장'
    # 조건②: BB 극과열 — 28.2% 하락예측
    elif bb_pct >= 0.90:
        sell_cond = f'BB 극과열(%B={bb_pct:.2f}) — 단기 과매수 정점, 분할 차익실현 검토'
    # 조건③: 거래량 급증 하락 — 31.8% 하락예측
    elif chg < -1.0 and vol_ratio >= 1.5:
        sell_cond = f'하락 {chg:.1f}% + 거래량 {vol_ratio:.1f}x 급증 — 매도세 출현, 추가 하락 경계'
    # 조건④: BB 상단 + RSI 고점 — 25.9% 하락예측
    elif bb_pct >= 0.85 and rsi >= 65:
        sell_cond = f'BB 상단({bb_pct:.2f}) + RSI {rsi:.0f} 과열 — 조정 리스크, 보유자 차익실현 고려'
    elif not macd_bull and not above_ma200:
        sell_cond = f'MACD 데드크로스 + MA200(${m200:.2f}) 이탈 — 손절 또는 비중 축소 원칙 적용'
    elif c > m200 * 1.25:
        sell_cond = f'MA200 대비 {(c/m200-1)*100:.0f}% 과이격 — 분할 차익실현 후 재진입 전략 권장'
    else:
        sell_cond = f'현재 특이 매도 신호 없음 — MA20(${m20:.2f}) 종가 이탈 시 손절 원칙 적용'

    # 손절 기준
    stop_price = m20 * 0.97
    stop_pct   = (stop_price / c - 1) * 100
    stop_loss  = f'${stop_price:.2f}  ({stop_pct:.1f}%)  — MA20 -3% 이탈 기준'

    return buy_cond, sell_cond, stop_loss


def opinion_label(total):
    if total >= 63: return '매수 적기',  GREEN
    if total >= 50: return '매수 검토',  GREEN
    if total >= 37: return '관망',       ORANGE
    if total >= 24: return '비중 축소',  RED
    return '매도 적기', RED
