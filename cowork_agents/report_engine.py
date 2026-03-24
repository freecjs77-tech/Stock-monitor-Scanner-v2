#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parameterized Stock Technical Analysis Report Engine
Usage: pass a stock_data dict to generate_report(stock_data, output_path)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import datetime, os, tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, Image)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

try:
    pdfmetrics.registerFont(UnicodeCIDFont('HYGothic-Medium'))
except Exception:
    pass

# ── Palette ──────────────────────────────────────────────────────
NAVY    = colors.HexColor("#0D2137")
BLUE    = colors.HexColor("#1B4F8A")
GREEN   = colors.HexColor("#1E8449")
RED     = colors.HexColor("#C0392B")
ORANGE  = colors.HexColor("#CA6F1E")
LGRAY   = colors.HexColor("#F4F6F7")
MGRAY   = colors.HexColor("#BDC3C7")
DGRAY   = colors.HexColor("#5D6D7E")
WHITE   = colors.white
SELL_BG = colors.HexColor("#FDECEA")
BUY_BG  = colors.HexColor("#EAFAF1")
NEUT_BG = colors.HexColor("#FEF9E7")

PAGE_W, PAGE_H = A4
M  = 13 * mm
CW = PAGE_W - 2 * M
KF = 'HYGothic-Medium'


def s(name, sz=9, c=colors.black, a=TA_LEFT, bold=False, lead=None, sa=1, sb=0):
    fsz = sz + (0.5 if bold else 0)
    return ParagraphStyle(name, fontName=KF,
                          fontSize=fsz, textColor=c, alignment=a,
                          leading=lead or fsz * 1.45, spaceAfter=sa, spaceBefore=sb)


def sma_arr(arr, w, n):
    r = np.full(n, np.nan)
    for i in range(w - 1, n):
        r[i] = arr[i - w + 1:i + 1].mean()
    return r


def score_bar(score, max_score, fill_color, container_w, empty_color=colors.HexColor('#D5D8DC')):
    cw = container_w / max_score
    cells = [[''] * max_score]
    t = Table(cells, colWidths=[cw] * max_score, rowHeights=[5 * mm])
    ts = [
        ('BACKGROUND',   (0, 0), (-1, -1), empty_color),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('GRID',         (0, 0), (-1, -1), 0.5, colors.white),
    ]
    if score > 0:
        ts.append(('BACKGROUND', (0, 0), (score - 1, 0), fill_color))
    t.setStyle(TableStyle(ts))
    return t


# ══════════════════════════════════════════════════════════════════
#  Price series + TA calculation
# ══════════════════════════════════════════════════════════════════

def make_price_series(d):
    """Build price series for charting.

    Priority order:
    1. 'price_series': list of actual close prices from yfinance (real data)
    2. 'price_path': list of (day_index, price) anchor tuples (synthetic with shape)
    3. Auto-generate from indicator values only

    day 0 = ~1 year ago, last element = today.
    """
    np.random.seed(hash(d['ticker']) % (2**31))

    close_val = d['close']
    high_52w  = d['high_52w']
    low_52w   = d['low_52w']

    # ── Option 1: Real price series from yfinance ──────────────────
    if 'price_series' in d:
        close = np.array(d['price_series'], dtype=float)
        close[-1] = close_val  # ensure last point matches stated close
        n = len(close)
        atr_ratio = d.get('atr', close_val * 0.025) / close_val
        high = close + np.abs(np.random.normal(0.4, 0.3, n)) * close * atr_ratio
        low  = close - np.abs(np.random.normal(0.4, 0.3, n)) * close * atr_ratio
        avg_vol  = d.get('avg_volume', 30e6)
        vol = np.abs(np.random.normal(avg_vol, avg_vol * 0.25, n))
        chg = np.abs(np.diff(close, prepend=close[0]))
        vol *= (1 + chg / close * 2.5)
        vol[-1] = d.get('volume', avg_vol)
        return close, high, low, vol

    # ── Option 2: Custom anchor path (synthetic with shape) ────────
    # Use custom anchor path if provided, else auto-generate
    if 'price_path' in d:
        anchor = d['price_path']   # [(day, price), ...]
        idx = [pt[0] for pt in anchor]
        px  = [pt[1] for pt in anchor]
    else:
        ma200     = d['ma200']
        est_start = max(low_52w * 0.82, ma200 * 0.65)
        if close_val > ma200:
            idx = [0,   40,   90,   150,  200,  220,  245,  261]
            px  = [est_start, est_start*1.15, low_52w,
                   (low_52w+high_52w)*0.5, high_52w,
                   high_52w*0.90, close_val*0.97, close_val]
        else:
            idx = [0,   50,   100,  180,  210,  235,  250,  261]
            px  = [est_start, est_start*1.2, low_52w*1.15,
                   high_52w, (high_52w+low_52w)*0.55,
                   close_val*1.04, close_val*1.01, close_val]

    t    = np.arange(262)
    base = np.interp(t, idx, px)
    noise = np.cumsum(np.random.normal(0, 0.5, 262))
    noise -= np.linspace(noise[0], noise[-1], 262)
    close = np.clip(base + noise, low_52w * 0.75, high_52w * 1.05)
    close[-1] = close_val

    atr_ratio = d.get('atr', close_val * 0.025) / close_val
    high = close + np.abs(np.random.normal(0.4, 0.3, 262)) * close * atr_ratio
    low  = close - np.abs(np.random.normal(0.4, 0.3, 262)) * close * atr_ratio

    avg_vol  = d.get('avg_volume', 30e6)
    vol = np.abs(np.random.normal(avg_vol, avg_vol * 0.25, 262))
    chg = np.abs(np.diff(close, prepend=close[0]))
    vol *= (1 + chg / close * 2.5)
    vol[-1] = d.get('volume', avg_vol)
    return close, high, low, vol


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


# ══════════════════════════════════════════════════════════════════
#  Auto signal generator
# ══════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════
#  단계별 매수 신호 (1차~3차)
# ══════════════════════════════════════════════════════════════════
TIER_META = {
    0: ('',           '',        MGRAY),
    1: ('1차 진입준비', '#FFB300', ORANGE),
    2: ('2차 매수확정', '#69F0AE', GREEN),
    3: ('3차 추세확인', '#00C853', GREEN),
}
TIER_DESC = {
    1: 'RSI 과매도 진입 + MA200 지지 유지 — 소량 분할매수 시작, 추가 하락 가능성 대비',
    2: 'RSI 과매도 회복 + MACD 골든크로스 + 거래량 동반 — 주력 매수 진입 타이밍',
    3: 'MA20 지지 + MACD 제로선 위 + 거래량 + 양봉 — 추세 재개 확인, 풀포지션 가능',
}


def buy_tier(d):
    """
    단계별 매수 신호 판정
    Returns: tier (int 0~3)
      0: 신호 없음
      1: 진입 준비  — RSI ≤40 + MA200 위
      2: 매수 확정  — RSI 28~50 + MACD 골든크로스 + 거래량 1.2x+
      3: 추세 확인  — MA20 근접(3%) + MACD 제로 위 + 거래량 1.3x+ + 양봉
    """
    c   = d['close']; m20 = d['ma20']; m200 = d['ma200']
    rsi = d['rsi'];   macd_v = d['macd']; macd_s = d['macd_signal']
    vol_ratio   = d.get('volume', 0) / max(d.get('avg_volume', 1), 1)
    chg         = d['change_pct']
    above_ma200 = c > m200
    macd_bull   = macd_v > macd_s
    near_ma20   = abs(c - m20) / max(m20, 1) <= 0.03

    # 3차: 추세 재개 확인 (모든 조건 충족)
    if (above_ma200 and near_ma20
            and macd_bull and macd_v > 0
            and vol_ratio >= 1.3 and chg > 0.5):
        return 3

    # 2차: 반전 확정
    if (above_ma200 and 28 <= rsi <= 50
            and macd_bull and vol_ratio >= 1.2):
        return 2

    # 1차: 진입 준비
    if above_ma200 and rsi <= 40:
        return 1

    return 0


# ══════════════════════════════════════════════════════════════════
#  Chart
# ══════════════════════════════════════════════════════════════════

def build_chart(d, path):
    close, high, low, vol = make_price_series(d)
    ma20, ma50, ma200, bb_u, bb_l, macd, sig, hist, rsi = calc_ta(close, vol, d)

    SHOW = 175
    sl   = slice(-SHOW, None)
    x    = np.arange(SHOW)

    # Approximate open from previous close
    open_arr          = np.roll(close, 1)
    open_arr[0]       = close[0]
    op = open_arr[sl]; cl = close[sl]
    hi = high[sl];     lo = low[sl]

    # Date labels (trading days backwards from today)
    end = datetime.date.today()
    dates, dt = [], end
    for _ in range(SHOW):
        while dt.weekday() >= 5:
            dt -= datetime.timedelta(1)
        dates.insert(0, dt)
        dt -= datetime.timedelta(1)

    # ── Dark theme palette ────────────────────────────────────────
    BG      = '#FFFFFF'   # figure background
    PANEL   = '#FAFAFA'   # axes background
    GRID_C  = '#E0E3EB'   # grid lines
    TICK_C  = '#5D6D7E'   # tick label color
    UP_C    = '#1565C0'   # 상승 캔들 (한국식: 파란색)
    DN_C    = '#C62828'   # 하락 캔들 (한국식: 빨간색)
    MA20_C  = '#E65100'   # MA20 orange
    MA50_C  = '#6A1B9A'   # MA50 purple
    MA200_C = '#B71C1C'   # MA200 dark red
    BB_C    = '#0277BD'   # Bollinger blue
    MACD_C  = '#1565C0'   # MACD line
    SIG_C   = '#E65100'   # Signal line
    RSI_C   = '#7B1FA2'   # RSI line

    fig = plt.figure(figsize=(11.5, 9), facecolor=BG)
    gs  = gridspec.GridSpec(4, 1, figure=fig,
                            height_ratios=[4.2, 1.3, 1.5, 1.5],
                            hspace=0.04, left=0.068, right=0.975, top=0.92, bottom=0.07)
    ax1 = fig.add_subplot(gs[0])              # Price
    ax2 = fig.add_subplot(gs[1], sharex=ax1)  # Volume
    ax3 = fig.add_subplot(gs[2], sharex=ax1)  # RSI
    ax4 = fig.add_subplot(gs[3], sharex=ax1)  # MACD

    for ax in (ax1, ax2, ax3, ax4):
        ax.set_facecolor(PANEL)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(GRID_C)
        ax.spines['bottom'].set_color(GRID_C)
        ax.tick_params(colors=TICK_C, labelsize=7.5)
        ax.grid(True, color=GRID_C, linewidth=0.5, zorder=0)

    # ── Panel 1: Candlestick + MA + BB ───────────────────────────
    # Bollinger Bands
    ax1.fill_between(x, bb_u[sl], bb_l[sl], alpha=0.07, color=BB_C, zorder=1)
    ax1.plot(x, bb_u[sl], lw=0.7, ls='--', color=BB_C, alpha=0.55,
             label=f'BB  ${bb_u[-1]:.2f} / ${bb_l[-1]:.2f}')
    ax1.plot(x, bb_l[sl], lw=0.7, ls='--', color=BB_C, alpha=0.55)

    # Candlesticks (vectorized with bar + vlines)
    is_up   = cl >= op
    body_lo = np.where(is_up, op, cl)
    body_hi = np.where(is_up, cl, op)
    body_h  = np.maximum(body_hi - body_lo, (hi - lo) * 0.01)  # min 1% height

    # Draw bodies: up (blue) / down (red)
    ax1.bar(x[is_up],  body_h[is_up],  bottom=body_lo[is_up],
            color=UP_C, width=0.6, zorder=5)
    ax1.bar(x[~is_up], body_h[~is_up], bottom=body_lo[~is_up],
            color=DN_C, width=0.6, zorder=5)

    # Draw wicks
    up_idx  = np.where(is_up)[0]
    dn_idx  = np.where(~is_up)[0]
    ax1.vlines(up_idx,  lo[up_idx],  hi[up_idx],  color=UP_C, lw=0.8, zorder=4)
    ax1.vlines(dn_idx,  lo[dn_idx],  hi[dn_idx],  color=DN_C, lw=0.8, zorder=4)

    # MA lines
    ax1.plot(x, ma20[sl],  lw=1.1, color=MA20_C,  label=f'MA20  ${ma20[-1]:.2f}',  zorder=6)
    ax1.plot(x, ma50[sl],  lw=1.1, color=MA50_C,  label=f'MA50  ${ma50[-1]:.2f}',  zorder=6)
    ax1.plot(x, ma200[sl], lw=1.3, ls='--', color=MA200_C,
             label=f'MA200  ${ma200[-1]:.2f}', zorder=6)

    # 52W reference lines
    ax1.axhline(d['high_52w'], color='#1B5E20', lw=0.8, ls=':', alpha=0.7)
    ax1.axhline(d['low_52w'],  color=DN_C,      lw=0.8, ls=':', alpha=0.5)
    ax1.text(2, d['high_52w'] * 1.005, f'52W H  ${d["high_52w"]:.2f}',
             fontsize=7, color='#1B5E20', va='bottom', fontweight='bold')
    ax1.text(2, d['low_52w']  * 0.993, f'52W L  ${d["low_52w"]:.2f}',
             fontsize=7, color=DN_C, va='top')

    # Current price annotation
    chg_sign  = '+' if d['change_pct'] >= 0 else ''
    ann_color = UP_C if d['change_pct'] >= 0 else DN_C
    ax1.scatter([SHOW - 1], [d['close']], color=ann_color, s=55, zorder=10)
    ax1.annotate(f'  ${d["close"]:.2f}  {chg_sign}{d["change_pct"]:.2f}%',
                 xy=(SHOW - 1, d['close']), xytext=(-95, 14),
                 textcoords='offset points', fontsize=8.5,
                 color=ann_color, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=ann_color, lw=1.0))

    ax1.set_ylabel('Price (USD)', fontsize=8, color=TICK_C)
    ax1.legend(loc='upper left', fontsize=7, framealpha=0.5, ncol=2,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor='#2C3E50')
    today_label = datetime.date.today().strftime('%b %d, %Y')
    ax1.set_title(
        f'{d["company"]} ({d["ticker"]})  ·  {d["exchange"]}  ·  Technical Analysis  ·  {today_label}',
        fontsize=10.5, fontweight='bold', color='#0D2137', pad=9)

    # ── Panel 2: Volume ───────────────────────────────────────────
    vcol = [UP_C if (cl[i] >= op[i]) else DN_C for i in range(SHOW)]
    vsl  = vol[sl] / 1e6
    avg_v = float(np.nanmean(vsl))
    ax2.bar(x, vsl, color=vcol, alpha=0.8, width=0.9, zorder=3)
    # 20-day volume MA line
    vol_ma = np.full(SHOW, np.nan)
    for i in range(19, SHOW):
        vol_ma[i] = vsl[i - 19:i + 1].mean()
    ax2.plot(x, vol_ma, lw=1.0, color=MA20_C, label=f'Vol MA(20)  {avg_v:.0f}M')
    ax2.set_ylabel('Vol (M)', fontsize=7.5, color=TICK_C)
    ax2.legend(loc='upper left', fontsize=7, framealpha=0.5,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor='#2C3E50')
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:.0f}'))

    # ── Panel 3: RSI ──────────────────────────────────────────────
    rsl = rsi[sl]
    ax3.fill_between(x, 30, 70, alpha=0.08, color=RSI_C, zorder=1)  # 30-70 band
    ax3.plot(x, rsl, lw=1.3, color=RSI_C, label='RSI (14)', zorder=4)
    ax3.axhline(70, lw=0.8, ls='--', color=DN_C,   alpha=0.8)
    ax3.axhline(50, lw=0.5, ls=':',  color=TICK_C, alpha=0.5)
    ax3.axhline(30, lw=0.8, ls='--', color=UP_C,   alpha=0.8)
    ax3.fill_between(x, rsl, 70, where=(rsl >= 70), alpha=0.18, color=DN_C)
    ax3.fill_between(x, rsl, 30, where=(rsl <= 30), alpha=0.18, color=UP_C)
    ax3.set_ylim(10, 90)
    ax3.set_yticks([30, 50, 70])
    ax3.set_ylabel('RSI', fontsize=7.5, color=TICK_C)
    ax3.legend(loc='upper left', fontsize=7, framealpha=0.5,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor='#2C3E50')
    ax3.annotate(f'  {d["rsi"]:.1f}', xy=(SHOW - 1, d['rsi']), xytext=(-34, 6),
                 textcoords='offset points', fontsize=7.5, color=RSI_C, fontweight='bold')

    # ── Panel 4: MACD ─────────────────────────────────────────────
    hsl  = hist[sl]
    hpos = np.where(hsl >= 0, hsl, 0)
    hneg = np.where(hsl <  0, hsl, 0)
    ax4.bar(x, hpos, color=UP_C, alpha=0.70, width=0.9, zorder=3)
    ax4.bar(x, hneg, color=DN_C, alpha=0.70, width=0.9, zorder=3)
    ax4.plot(x, macd[sl], lw=1.2, color=MACD_C,
             label=f'MACD ({d["macd"]:.2f})')
    ax4.plot(x, sig[sl],  lw=1.0, color=SIG_C,
             label=f'Signal ({d["macd_signal"]:.2f})')
    ax4.axhline(0, color=TICK_C, lw=0.5)
    ax4.set_ylabel('MACD', fontsize=7.5, color=TICK_C)
    ax4.legend(loc='upper left', fontsize=7, framealpha=0.5, ncol=2,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor='#2C3E50')
    ax4.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f'))

    # ── X-axis date labels ────────────────────────────────────────
    tpos, tlbl, seen = [], [], set()
    for i, dt in enumerate(dates):
        k = (dt.year, dt.month)
        if k not in seen:
            seen.add(k)
            tpos.append(i)
            tlbl.append(dt.strftime('%b %Y'))
    ax4.set_xticks(tpos)
    ax4.set_xticklabels(tlbl, fontsize=7.5, color=TICK_C)
    for ax in (ax1, ax2, ax3):
        plt.setp(ax.get_xticklabels(), visible=False)

    plt.savefig(path, dpi=155, bbox_inches='tight', facecolor=BG)
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════
#  PDF builder
# ══════════════════════════════════════════════════════════════════

def build_pdf(d, chart_path, output_path):
    a_sc, b_sc, c_sc, d_sc, e_sc, f_sc, total = auto_score(d)
    op_label, op_color = opinion_label(total)
    tier = buy_tier(d)
    tier_lbl, tier_hex, tier_color = TIER_META[tier]
    signals = auto_signals(d)
    ma200_status = '현재가 상향' if d['close'] > d['ma200'] else '현재가 하향 이탈'

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             leftMargin=M, rightMargin=M,
                             topMargin=9 * mm, bottomMargin=8 * mm)
    story = []

    # Header
    hdr = Table(
        [[Paragraph(d['company'], s('hc', 17, NAVY, TA_LEFT, bold=True)),
          Paragraph(f'{d["ticker"]}  |  {d["exchange"]}  |  {d["sector"]}\n{datetime.date.today().strftime("%Y년 %m월 %d일")} 기준',
                    s('ex', 8, DGRAY, TA_RIGHT))]],
        colWidths=[CW * 0.60, CW * 0.40])
    hdr.setStyle(TableStyle([
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0),(-1,-1), 0), ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING', (0,0),(-1,-1), 0), ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width='100%', thickness=3, color=BLUE,
                             spaceBefore=2 * mm, spaceAfter=2.5 * mm))

    # Metrics bar (7 columns: 종가/고점/저점/MA200/점수/판정/단계신호)
    tier_bg = colors.HexColor('#E8F5E9') if tier >= 2 else (colors.HexColor('#FFF8E1') if tier == 1 else colors.HexColor('#FEF0F0'))
    chg_sign = '+' if d['change_pct'] >= 0 else ''
    lbl_row = [Paragraph(t, s(f'ml{i}', 7, DGRAY, TA_CENTER, bold=True))
               for i, t in enumerate(['종가', '52주 고점', '52주 저점', '200일 MA', '종합점수', '타이밍 판정', '단계 신호'])]
    val_row = [Paragraph(v, s(f'mv{i}', 11, c, TA_CENTER, bold=True))
               for i, (v, c) in enumerate([
                   (f'${d["close"]:.2f}',    RED if d['change_pct'] < 0 else GREEN),
                   (f'${d["high_52w"]:.2f}', NAVY),
                   (f'${d["low_52w"]:.2f}',  NAVY),
                   (f'${d["ma200"]:.2f}',    RED if d['close'] < d['ma200'] else GREEN),
                   (f'{total} / 85',         op_color),
                   (op_label,                op_color),
                   (tier_lbl if tier else '—', tier_color)])]
    sub_row = [Paragraph(v, s(f'ms{i}', 7, DGRAY, TA_CENTER))
               for i, v in enumerate([
                   f'{chg_sign}{d["change_pct"]:.2f}%',
                   d.get('high_52w_date', ''),
                   d.get('low_52w_date',  ''),
                   ma200_status, '/85점 만점',
                   '기술지표 종합',
                   TIER_DESC.get(tier, '매수 조건 미충족')[:14] if tier else '해당 없음'])]
    col7 = [CW * 0.145] * 6 + [CW * 0.13]
    mt = Table([lbl_row, val_row, sub_row], colWidths=col7)
    mt.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), LGRAY),
        ('BACKGROUND',    (4,0),(5,-1),  colors.HexColor('#FEF0F0')),
        ('BACKGROUND',    (6,0),(6,-1),  tier_bg),
        ('BOX',           (0,0),(-1,-1), 0.8, MGRAY),
        ('LINEAFTER',     (0,0),(5,-1),  0.4, MGRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ]))
    story.append(mt)
    story.append(Spacer(1, 3 * mm))

    # Chart
    img_h = CW * (9 / 11.5)
    story.append(Image(chart_path, width=CW, height=img_h))
    story.append(Spacer(1, 3 * mm))

    # Score card + Signals
    LEFT_W  = CW * 0.41
    GAP_W   = 3 * mm
    RIGHT_W = CW - LEFT_W - GAP_W
    SC_NAME = LEFT_W * 0.57
    SC_PTS  = LEFT_W * 0.18
    SC_BAR  = LEFT_W * 0.25

    sc_items = [
        ('A. 추세 (이동평균)',    a_sc, 20, RED if a_sc / 20 < 0.5 else GREEN),
        ('B. 모멘텀 (RSI/MACD)', b_sc, 20, RED if b_sc / 20 < 0.5 else GREEN),
        ('C. BB 위치 (매수구간)', c_sc, 15, RED if c_sc / 15 < 0.5 else GREEN),
        ('D. 거래량',            d_sc, 15, RED if d_sc / 15 < 0.5 else GREEN),
        ('E. MA 지지 근접도',    e_sc, 15, RED if e_sc / 15 < 0.5 else GREEN),
        ('F. 매도 압력 페널티',  f_sc,  0, RED if f_sc < 0 else MGRAY),
    ]
    sc_rows = [[
        Paragraph('항목',  s('sh0', 7.5, WHITE, TA_LEFT,   bold=True)),
        Paragraph('점수',  s('sh1', 7.5, WHITE, TA_CENTER, bold=True)),
        Paragraph('바',    s('sh2', 7.5, WHITE, TA_CENTER, bold=True)),
    ]]
    for name, sc, mx, bc in sc_items:
        if name.startswith('F.'):
            # F는 페널티(음수) — 별도 표시
            lbl_txt = f'{sc:+d}'
            lbl_col = RED if sc < 0 else MGRAY
            bar_w = score_bar(abs(sc), 20, RED if sc < 0 else MGRAY, SC_BAR)
        else:
            lbl_txt = f'{sc}/{mx}'
            lbl_col = RED if (mx > 0 and sc / mx < 0.5) else GREEN
            bar_w = score_bar(sc, mx, bc, SC_BAR)
        sc_rows.append([
            Paragraph(name,    s(f'sn{name}', 7, NAVY)),
            Paragraph(lbl_txt, s(f'sv{sc}',   8, lbl_col, TA_CENTER, bold=True)),
            bar_w,
        ])
    sc_rows.append([
        Paragraph('합계', s('tot', 8.5, NAVY, bold=True)),
        Paragraph(f'{total}/85', s('totv', 9, op_color, TA_CENTER, bold=True)),
        Paragraph('', s('x', 7)),
    ])
    sc_t = Table(sc_rows, colWidths=[SC_NAME, SC_PTS, SC_BAR])
    sc_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('BACKGROUND',    (0,-1), (-1,-1),  SELL_BG if total < 50 else BUY_BG),
        ('ROWBACKGROUNDS',(0, 1), (-1,-2),  [WHITE, LGRAY]),
        ('BOX',           (0, 0), (-1,-1),  0.5, MGRAY),
        ('INNERGRID',     (0, 0), (-1,-1),  0.3, colors.HexColor('#E5E8EA')),
        ('VALIGN',        (0, 0), (-1,-1),  'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1,-1),  3),
        ('BOTTOMPADDING', (0, 0), (-1,-1),  3),
        ('LEFTPADDING',   (0, 0), (-1,-1),  5),
        ('RIGHTPADDING',  (0, 0), (-1,-1),  3),
        ('LEFTPADDING',   (2, 0), (2,  -1), 0),
        ('RIGHTPADDING',  (2, 0), (2,  -1), 0),
    ]))

    sig_hdr = [
        Paragraph('신호', s('sgh',  7.5, WHITE, TA_CENTER, bold=True)),
        Paragraph('지표', s('sgh2', 7.5, WHITE, TA_LEFT,   bold=True)),
        Paragraph('내용', s('sgh3', 7.5, WHITE, TA_LEFT,   bold=True)),
    ]
    sig_rows   = [sig_hdr]
    sig_styles = []
    for i, (typ, lbl, dsc) in enumerate(signals, 1):
        bg = SELL_BG if typ == '매도' else (BUY_BG if typ == '매수' else NEUT_BG)
        tc = RED     if typ == '매도' else (GREEN   if typ == '매수' else ORANGE)
        sig_rows.append([
            Paragraph(typ, s(f'st{i}', 7.5, tc, TA_CENTER, bold=True)),
            Paragraph(lbl, s(f'sl{i}', 7.5, NAVY)),
            Paragraph(dsc, s(f'sd{i}', 7,   DGRAY)),
        ])
        sig_styles.append(('BACKGROUND', (0, i), (-1, i), bg))
    sig_cw = [RIGHT_W * 0.13, RIGHT_W * 0.30, RIGHT_W * 0.57]
    sig_t = Table(sig_rows, colWidths=sig_cw)
    sig_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  NAVY),
        ('BOX',           (0,0),(-1,-1), 0.5, MGRAY),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, colors.HexColor('#E5E8EA')),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 2.5),
        ('LEFTPADDING',   (0,0),(-1,-1), 4),
        ('RIGHTPADDING',  (0,0),(-1,-1), 3),
    ] + sig_styles))

    sbs = Table([[sc_t, Spacer(GAP_W, 1), sig_t]], colWidths=[LEFT_W, GAP_W, RIGHT_W])
    sbs.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0), ('RIGHTPADDING',  (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0), ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(sbs)
    story.append(Spacer(1, 3 * mm))

    # Strategy table — timing-focused (buy / sell / stop-loss)
    buy_cond, sell_cond, stop_loss = timing_judgment(d, total)
    STRAT_HDR_COLS = [CW * 0.36, CW * 0.36, CW * 0.28]
    strat_t = Table(
        [[Paragraph(t, s('trh', 7, WHITE, TA_CENTER, bold=True))
          for t in ['매수 진입 조건', '매도 · 차익실현 조건', '손절 기준']],
         [Paragraph(v, s(f'tv{i}', 8, c, TA_LEFT, lead=12))
          for i, (v, c) in enumerate([(buy_cond, GREEN), (sell_cond, RED), (stop_loss, RED)])]],
        colWidths=STRAT_HDR_COLS)
    strat_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  NAVY),
        ('BACKGROUND',    (0,1),(-1,1),  LGRAY),
        ('BOX',           (0,0),(-1,-1), 0.6, MGRAY),
        ('LINEAFTER',     (0,0),(1,-1),  0.4, MGRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('RIGHTPADDING',  (0,0),(-1,-1), 6),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(strat_t)
    story.append(Spacer(1, 3.5 * mm))

    # Opinion
    op_hdr = Table([[Paragraph('  타이밍 종합 판정', s('oh', 9, WHITE, TA_LEFT, bold=True))]],
                   colWidths=[CW])
    op_hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), BLUE),
        ('TOPPADDING',    (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
    ]))
    story.append(op_hdr)

    opinion = d.get('opinion_text', _auto_opinion(d, total, op_label, a_sc, b_sc))
    op_body = Table([[Paragraph(opinion, s('ob', 8, NAVY, lead=13))]], colWidths=[CW])
    op_body.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#EBF5FB')),
        ('BOX',           (0,0),(-1,-1), 0.5, BLUE),
        ('TOPPADDING',    (0,0),(-1,-1), 7), ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('LEFTPADDING',   (0,0),(-1,-1), 8), ('RIGHTPADDING',  (0,0),(-1,-1), 8),
    ]))
    story.append(op_body)
    story.append(Spacer(1, 3 * mm))

    # Footer
    story.append(HRFlowable(width='100%', thickness=0.6, color=MGRAY,
                             spaceBefore=1 * mm, spaceAfter=1.5 * mm))
    story.append(Paragraph(
        f'본 보고서는 AI 기반 자동 기술적 분석으로, 투자 권유가 아닙니다. '
        f'(종가 ${d["close"]:.2f} / MA20 ${d["ma20"]:.2f} / MA50 ${d["ma50"]:.2f} / '
        f'MA200 ${d["ma200"]:.2f} / RSI {d["rsi"]:.1f} / MACD {d["macd"]:.2f} / '
        f'52주 H/L ${d["high_52w"]:.2f}-${d["low_52w"]:.2f})  |  AI Chart Analyst (c) 2026',
        s('foot', 6.5, DGRAY, TA_CENTER)))

    doc.build(story)


def _auto_opinion(d, total, op_label, a_sc, b_sc):
    """타이밍 중심 종합 의견 — 관심 종목 매수 적기 / 보유 종목 매도 적기 판단"""
    c = d['close']; m20 = d['ma20']; m50 = d['ma50']; m200 = d['ma200']
    rsi = d['rsi']; macd_v = d['macd']; macd_s = d['macd_signal']

    buy_cond, sell_cond, stop_loss = timing_judgment(d, total)

    above = sum([c > m20, c > m50, c > m200])
    ma_state = {3: 'MA 정배열 (장·중·단기 모두 지지)', 2: 'MA200 하향 이탈 (장기 지지선 회복 필요)',
                1: 'MA50/200 이중 저항권', 0: 'MA 완전 역배열 (강한 하락 추세)'}[above]

    # RSI 타이밍 설명
    if rsi >= 70:
        rsi_timing = f'RSI {rsi:.0f} — 과매수 구간, 신규 진입 비권장 / 보유자는 차익실현 검토'
    elif rsi >= 60:
        rsi_timing = f'RSI {rsi:.0f} — 모멘텀 상단, 추세 유지 중이나 추가 상승 여력 제한적'
    elif rsi >= 45:
        rsi_timing = f'RSI {rsi:.0f} — 중립 구간, 방향 확인 후 진입 유효'
    elif rsi >= 30:
        rsi_timing = f'RSI {rsi:.0f} — 과매도 회복 구간, 분할 매수 관심 구간'
    else:
        rsi_timing = f'RSI {rsi:.0f} — 심각 과매도, 추세 바닥 확인 전 진입 위험'

    # MACD 상태
    macd_state = ('MACD 골든크로스' if macd_v > macd_s else 'MACD 데드크로스') + \
                 (' (제로선 상방)' if macd_v > 0 else ' (제로선 하방)')

    tier = buy_tier(d)
    tier_lbl = TIER_META[tier][0]
    tier_line = (f'<b>[매수 단계 신호: {tier_lbl}]</b>  {TIER_DESC[tier]}<br/><br/>'
                 if tier else '')

    return (
        f'[타이밍 판정: {op_label}  {total}/85점]<br/>'
        f'{d["ticker"]}의 현재 기술적 상태는 <b>{ma_state}</b>입니다. '
        f'{rsi_timing}. {macd_state}.<br/><br/>'
        + tier_line +
        f'<b>관심 종목 (매수 관점):</b> {buy_cond}<br/>'
        f'<b>보유 종목 (매도 관점):</b> {sell_cond}<br/>'
        f'<b>손절 기준:</b> {stop_loss}'
    )


# ══════════════════════════════════════════════════════════════════
#  Summary page (all tickers on one page)
# ══════════════════════════════════════════════════════════════════

def generate_summary_page(stocks_list, output_path):
    """
    Generate a single-page PDF summary of all tickers.
    stocks_list: list of stock_data dicts (same format as generate_report input)
    output_path: full path for the output PDF
    """
    today_str = datetime.date.today().strftime('%Y년 %m월 %d일')

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             leftMargin=M, rightMargin=M,
                             topMargin=10 * mm, bottomMargin=8 * mm)
    story = []

    # ── Title ─────────────────────────────────────────────────────
    title_tbl = Table(
        [[Paragraph('Mag7 Daily Report', s('tt', 20, NAVY, TA_LEFT, bold=True)),
          Paragraph(f'{today_str}  |  기술적 분석 종합', s('td', 9, DGRAY, TA_RIGHT))]],
        colWidths=[CW * 0.60, CW * 0.40])
    title_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0),(-1,-1), 0), ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING', (0,0),(-1,-1), 0), ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(title_tbl)
    story.append(HRFlowable(width='100%', thickness=3, color=BLUE,
                             spaceBefore=2 * mm, spaceAfter=3 * mm))

    # ── Summary table ─────────────────────────────────────────────
    COL_W = [
        CW * 0.065,   # 티커
        CW * 0.155,   # 회사명
        CW * 0.085,   # 종가
        CW * 0.075,   # 등락
        CW * 0.085,   # MA 상태
        CW * 0.065,   # RSI
        CW * 0.095,   # MACD
        CW * 0.065,   # BB%B
        CW * 0.085,   # 52주 위치
        CW * 0.065,   # 점수
        CW * 0.055,   # 의견
    ]

    HDR = ['티커', '회사명', '종가', '등락률', 'MA 상태', 'RSI', 'MACD',
           'BB%B', '52주', '점수', '의견']
    hdr_row = [Paragraph(h, s(f'sh{i}', 7.5, WHITE, TA_CENTER, bold=True))
               for i, h in enumerate(HDR)]
    rows = [hdr_row]
    row_styles = []

    for ri, d in enumerate(stocks_list, 1):
        _, _, _, _, _, _, total = auto_score(d)
        op_label, op_color = opinion_label(total)

        c    = d['close']
        chg  = d['change_pct']
        rsi  = d['rsi']
        macd_v = d['macd']
        macd_s = d['macd_signal']

        # MA 상태
        above = sum([c > d['ma20'], c > d['ma50'], c > d['ma200']])
        ma_txt   = {3: '정배열', 2: 'MA200↓', 1: 'MA50↓', 0: '역배열'}[above]
        ma_color = GREEN if above == 3 else (ORANGE if above == 2 else RED)

        # MACD 상태
        macd_txt   = f'{macd_v:.2f}' + (' ↑' if macd_v > macd_s else ' ↓')
        macd_color = GREEN if macd_v > macd_s else RED

        # BB%B
        bb_range = d['bb_upper'] - d['bb_lower']
        bb_pct   = (c - d['bb_lower']) / bb_range if bb_range > 0 else 0.5
        bb_txt   = f'{bb_pct:.2f}'
        bb_color = RED if bb_pct > 0.85 else (GREEN if bb_pct < 0.15 else DGRAY)

        # 52주 위치
        range_52 = d['high_52w'] - d['low_52w']
        pos_52   = (c - d['low_52w']) / range_52 if range_52 > 0 else 0.5
        pos_txt  = f'{pos_52*100:.0f}%'

        # RSI 색상
        rsi_color = RED if rsi >= 70 else (GREEN if rsi <= 30 else DGRAY)

        # 등락 색상
        chg_color = GREEN if chg >= 0 else RED
        chg_txt   = f'+{chg:.2f}%' if chg >= 0 else f'{chg:.2f}%'

        row = [
            Paragraph(d['ticker'],          s(f'r{ri}0', 8,   NAVY,      TA_CENTER, bold=True)),
            Paragraph(d['company'],          s(f'r{ri}1', 7,   DGRAY,     TA_LEFT)),
            Paragraph(f'${c:.2f}',           s(f'r{ri}2', 8,   colors.black, TA_CENTER, bold=True)),
            Paragraph(chg_txt,               s(f'r{ri}3', 8,   chg_color, TA_CENTER, bold=True)),
            Paragraph(ma_txt,                s(f'r{ri}4', 7.5, ma_color,  TA_CENTER, bold=True)),
            Paragraph(f'{rsi:.1f}',          s(f'r{ri}5', 8,   rsi_color, TA_CENTER, bold=True)),
            Paragraph(macd_txt,              s(f'r{ri}6', 7.5, macd_color,TA_CENTER, bold=True)),
            Paragraph(bb_txt,                s(f'r{ri}7', 7.5, bb_color,  TA_CENTER)),
            Paragraph(pos_txt,               s(f'r{ri}8', 7.5, DGRAY,     TA_CENTER)),
            Paragraph(f'{total}/85',         s(f'r{ri}9', 8,   op_color,  TA_CENTER, bold=True)),
            Paragraph(op_label,              s(f'r{ri}a', 7.5, op_color,  TA_CENTER, bold=True)),
        ]
        rows.append(row)

        bg = BUY_BG if total >= 50 else (NEUT_BG if total >= 38 else SELL_BG)
        row_styles.append(('BACKGROUND', (0, ri), (-1, ri), bg))

    summary_t = Table(rows, colWidths=COL_W)
    summary_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('BOX',           (0, 0), (-1, -1), 0.6, MGRAY),
        ('INNERGRID',     (0, 0), (-1, -1), 0.3, colors.HexColor('#E5E8EA')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ] + row_styles))
    story.append(summary_t)
    story.append(Spacer(1, 5 * mm))

    # ── Score legend ──────────────────────────────────────────────
    legend_items = [
        ('매수 적기 (63+)', GREEN), ('매수 검토 (50-62)', GREEN),
        ('관망 (37-49)', ORANGE), ('비중 축소 (24-36)', RED), ('매도 적기 (0-23)', RED),
    ]
    legend_cells = []
    for lbl, lc in legend_items:
        legend_cells.append(Paragraph(f'● {lbl}', s(f'lg{lbl}', 7, lc, TA_CENTER)))
    legend_t = Table([legend_cells], colWidths=[CW / 5] * 5)
    legend_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), LGRAY),
        ('BOX',           (0,0),(-1,-1), 0.5, MGRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
    ]))
    story.append(legend_t)
    story.append(Spacer(1, 4 * mm))

    # ── MA 상태 설명 ──────────────────────────────────────────────
    story.append(Paragraph(
        '* MA 상태: 정배열=현재가가 MA20/50/200 모두 상향 | MA200↓=MA200 하향 이탈 | MA50↓=MA50/200 하향 | 역배열=전부 하향  '
        '/ BB%B: 0=BB하단, 0.5=중앙, 1=BB상단  / 52주: 52주 고저 범위 내 현재 위치',
        s('note', 6.5, DGRAY, TA_LEFT)))
    story.append(Spacer(1, 3 * mm))

    # ── Market heatmap bar ────────────────────────────────────────
    scores  = []
    for d in stocks_list:
        _, _, _, _, _, _, total = auto_score(d)
        scores.append(total)
    avg_score = sum(scores) / len(scores) if scores else 0
    bull_count = sum(1 for sc in scores if sc >= 50)
    bear_count = sum(1 for sc in scores if sc < 38)
    neut_count = len(scores) - bull_count - bear_count

    mkt_label, mkt_color = opinion_label(int(avg_score))
    mkt_cells = [
        Paragraph('시장 전체 평균', s('mk0', 8, DGRAY, TA_CENTER, bold=True)),
        Paragraph(f'{avg_score:.1f} / 85  ({mkt_label})', s('mk1', 10, mkt_color, TA_CENTER, bold=True)),
        Paragraph(f'강세 {bull_count}종목', s('mk2', 8, GREEN, TA_CENTER, bold=True)),
        Paragraph(f'중립 {neut_count}종목', s('mk3', 8, ORANGE, TA_CENTER, bold=True)),
        Paragraph(f'약세 {bear_count}종목', s('mk4', 8, RED, TA_CENTER, bold=True)),
    ]
    mkt_t = Table([mkt_cells], colWidths=[CW / 5] * 5)
    mkt_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,-1),  LGRAY),
        ('BACKGROUND',    (1,0),(1,-1),  colors.HexColor('#EBF5FB')),
        ('BACKGROUND',    (2,0),(2,-1),  BUY_BG),
        ('BACKGROUND',    (3,0),(3,-1),  NEUT_BG),
        ('BACKGROUND',    (4,0),(4,-1),  SELL_BG),
        ('BOX',           (0,0),(-1,-1), 0.6, MGRAY),
        ('LINEAFTER',     (0,0),(3,-1),  0.4, MGRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 7),
        ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(mkt_t)
    story.append(Spacer(1, 4 * mm))

    # ── Footer ────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.6, color=MGRAY,
                             spaceBefore=1 * mm, spaceAfter=1.5 * mm))
    story.append(Paragraph(
        f'본 보고서는 AI 기반 자동 기술적 분석으로, 투자 권유가 아닙니다. '
        f'데이터 소스: Yahoo Finance (yfinance)  |  AI Chart Analyst (c) 2026',
        s('foot', 6.5, DGRAY, TA_CENTER)))

    doc.build(story)
    return output_path


# ══════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════

def generate_report(stock_data, output_dir):
    """
    Generate a full PDF technical analysis report for a stock.

    stock_data: dict with keys:
        ticker, company, sector, exchange,
        close, change_pct, high_52w, low_52w,
        ma20, ma50, ma200,
        rsi, macd, macd_signal,
        bb_upper, bb_lower,
        atr (optional), volume (optional), avg_volume (optional)
    output_dir: directory to save PDF
    Returns: path to generated PDF
    """
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.date.today().strftime('%Y%m%d')
    ticker   = stock_data['ticker']

    chart_path  = os.path.join(tempfile.gettempdir(), f'{ticker}_chart_{date_str}.png')
    output_path = os.path.join(output_dir, f'{ticker}_Technical_Analysis_{date_str}.pdf')

    build_chart(stock_data, chart_path)
    build_pdf(stock_data, chart_path, output_path)

    if os.path.exists(chart_path):
        os.remove(chart_path)

    return output_path


if __name__ == '__main__':
    # Quick test with PLTR data
    test = {
        'ticker': 'PLTR', 'company': 'Palantir Technologies', 'sector': 'AI / 방산 소프트웨어',
        'exchange': 'NASDAQ', 'close': 150.68, 'change_pct': -3.21,
        'high_52w': 207.51, 'low_52w': 126.23,
        'ma20': 138.50, 'ma50': 158.97, 'ma200': 161.80,
        'rsi': 41.5, 'macd': 2.85, 'macd_signal': 4.20,
        'bb_upper': 162.50, 'bb_lower': 114.50,
        'volume': 88e6, 'avg_volume': 60e6,
    }
    out = generate_report(test, '/tmp/test_reports')
    print(f'Test report: {out}')
