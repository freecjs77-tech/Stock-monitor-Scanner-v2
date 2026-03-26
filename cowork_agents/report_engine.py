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
from reportlab.platypus import (SimpleDocTemplate, PageBreak,
                                 Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, Image)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

try:
    pdfmetrics.registerFont(UnicodeCIDFont('HYGothic-Medium'))
except Exception:
    pass

# Geist 폰트 등록 (영문/숫자 전용 — Vercel)
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts')
try:
    pdfmetrics.registerFont(TTFont('Inter',         os.path.join(_FONTS_DIR, 'Geist-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Inter-Bold',    os.path.join(_FONTS_DIR, 'Geist-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('Inter-SemiBold',os.path.join(_FONTS_DIR, 'Geist-SemiBold.ttf')))
    _INTER_OK = True
except Exception:
    _INTER_OK = False

# ── Palette  (Dark-Blue Theme) ────────────────────────────────────
NAVY    = colors.HexColor("#0C1E35")   # 최심 네이비 — 헤더·타이틀
BLUE    = colors.HexColor("#1A4A8A")   # 진한 파란 — 섹션선·강조
BLUE2   = colors.HexColor("#2471A3")   # 중간 파란 — 보더·서브헤더
GREEN   = colors.HexColor("#1A8C5A")   # 매수 시그널 (청록-그린)
RED     = colors.HexColor("#C0392B")   # 매도 시그널
ORANGE  = colors.HexColor("#CC7A2A")   # 중립
LGRAY   = colors.HexColor("#D4E6F1")   # 연한 파란 배경 (교대행·섹션)
MGRAY   = colors.HexColor("#7BAED6")   # 파란 그레이 — 테두리·구분선
DGRAY   = colors.HexColor("#3C6080")   # 파란 진회색 — 보조 텍스트
WHITE   = colors.white
SELL_BG = colors.HexColor("#FDEDEC")   # 매도행 배경
BUY_BG  = colors.HexColor("#E3F0EA")   # 매수행 배경
NEUT_BG = colors.HexColor("#EAF2F8")   # 중립행 배경 (연한 파란)

PAGE_W, PAGE_H = A4
M  = 13 * mm
CW = PAGE_W - 2 * M
KF  = 'HYGothic-Medium'
EF  = 'Inter'           if _INTER_OK else 'HYGothic-Medium'   # Geist-Regular
EFB = 'Inter-Bold'      if _INTER_OK else 'HYGothic-Medium'   # Geist-Bold
EFS = 'Inter-SemiBold'  if _INTER_OK else 'HYGothic-Medium'   # Geist-SemiBold


def s(name, sz=9, c=colors.black, a=TA_LEFT, bold=False, lead=None, sa=1, sb=0):
    """한글 혼용 스타일 (HYGothic 기반)"""
    fsz = sz + (0.5 if bold else 0)
    return ParagraphStyle(name, fontName=KF,
                          fontSize=fsz, textColor=c, alignment=a,
                          leading=lead or fsz * 1.45, spaceAfter=sa, spaceBefore=sb)


def se(name, sz=9, c=colors.black, a=TA_LEFT, bold=False, semi=False, lead=None, sa=1, sb=0):
    """영문/숫자 전용 스타일 (Inter 기반)"""
    fn  = EFB if bold else (EFS if semi else EF)
    fsz = sz
    return ParagraphStyle(name, fontName=fn,
                          fontSize=fsz, textColor=c, alignment=a,
                          leading=lead or fsz * 1.45, spaceAfter=sa, spaceBefore=sb)


def sma_arr(arr, w, n):
    r = np.full(n, np.nan)
    for i in range(w - 1, n):
        r[i] = arr[i - w + 1:i + 1].mean()
    return r


def score_bar(score, max_score, fill_color, container_w, empty_color=colors.HexColor('#B8D0E8')):
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
#  조건 체크 상세 분해
# ══════════════════════════════════════════════════════════════════

def get_condition_breakdown(d):
    """판정2 기준 각 단계별 조건 체크 결과 반환 (HTML 표시용)"""
    def sig(key, default=False):
        return bool(d.get(key, default))

    rsi  = d.get('rsi', 0)
    adx  = d.get('adx', 0)
    chg  = d.get('change_pct', 0)
    close = d.get('close', 0)
    ma20  = d.get('ma20', close)
    bb_l  = d.get('bb_lower', 0)

    # ── 1차 매수 조건 (6개 중 3개 이상) ─────────────────────────
    block1 = sig('sig_block_rsi50') or sig('sig_block_bigdrop')
    cond1 = [
        {'name': 'RSI(14) ≤ 38',
         'pass': sig('sig_rsi_le38'),
         'ok':   f'RSI {rsi:.1f} — 충분히 과매도 상태예요',
         'fail': f'RSI {rsi:.1f} — 기준(38)보다 아직 높아요'},
        {'name': 'ADX(14) ≤ 25',
         'pass': sig('sig_adx_le25'),
         'ok':   f'ADX {adx:.1f} — 하락 에너지가 약해지고 있어요',
         'fail': f'ADX {adx:.1f} — 아직 추세가 강하게 지속 중이에요'},
        {'name': '종가 < MA20',
         'pass': sig('sig_below_ma20'),
         'ok':   f'${close:.2f} < ${ma20:.2f} — 단기 이평선 아래에 있어요',
         'fail': f'${close:.2f} ≥ ${ma20:.2f} — 이평선 위에 있어요'},
        {'name': '하락 멈춤',
         'pass': sig('sig_low_stopped'),
         'ok':   '최근 3일 저점보다 높아요 — 하락이 일단 멈췄어요',
         'fail': '아직 저점을 갱신 중이에요 — 하락이 계속되고 있어요'},
        {'name': 'BB 하단 근처',
         'pass': sig('sig_near_bb_low'),
         'ok':   f'볼린저 밴드 하단 지지구간에 있어요',
         'fail': f'밴드 하단에서 아직 멀리 있어요'},
        {'name': '당일 +2% 이상 반등',
         'pass': sig('sig_bounce2pct'),
         'ok':   f'오늘 {chg:+.1f}% — 반등 신호가 나왔어요',
         'fail': f'오늘 {chg:+.1f}% — 아직 반등 신호가 없어요'},
    ]
    met1 = sum(1 for c in cond1 if c['pass'])

    # ── 2차 매수 조건 (4개 ALL) ──────────────────────────────────
    cond2 = [
        {'name': '이중 바닥 패턴',
         'pass': sig('sig_double_bottom'),
         'ok':   'W자 바닥 패턴이 확인됐어요',
         'fail': '바닥 패턴이 아직 만들어지지 않았어요'},
        {'name': 'RSI > 35 + 3일 연속 상승',
         'pass': sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'),
         'ok':   f'RSI {rsi:.1f} — 반등 흐름이 이어지고 있어요',
         'fail': f'RSI {rsi:.1f} — 반등이 아직 확인되지 않았어요'},
        {'name': 'MACD 골든크로스 or 히스토그램 3일↑',
         'pass': sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'),
         'ok':   '상승 전환 신호가 나왔어요',
         'fail': '상승 전환 신호를 기다리는 중이에요'},
        {'name': '거래량 평균 1.2배 이상',
         'pass': sig('sig_vol_1p2'),
         'ok':   '평균보다 거래량이 많아요 — 매수 세력이 들어오고 있어요',
         'fail': '거래량이 평균 이하예요 — 아직 조용한 상태예요'},
    ]
    met2 = sum(1 for c in cond2 if c['pass'])

    # ── 3차 매수 조건 (4개 ALL) ──────────────────────────────────
    block3 = sig('sig_block_rsi75') or sig('sig_block_bigdrop')
    cond3 = [
        {'name': 'MA20 위에서 2일 연속',
         'pass': sig('sig_above_ma20_2d'),
         'ok':   '이평선 위에 안착했어요 — 추세 전환 확인',
         'fail': '이평선 위로 아직 안착하지 못했어요'},
        {'name': 'MA20 기울기 상향',
         'pass': sig('sig_ma20_slope_pos'),
         'ok':   '이평선이 위를 향하고 있어요',
         'fail': '이평선이 아직 내려가고 있어요'},
        {'name': 'MACD 0선 위',
         'pass': sig('sig_macd_above_zero'),
         'ok':   '상승 모멘텀이 확실히 살아났어요',
         'fail': '모멘텀이 아직 음수 영역이에요'},
        {'name': '거래량 평균 1.3배 이상',
         'pass': sig('sig_vol_1p3'),
         'ok':   '강한 거래량이 동반됐어요 — 추세 신뢰도 높아요',
         'fail': '거래량이 충분하지 않아요'},
    ]
    met3 = sum(1 for c in cond3 if c['pass'])

    # 현재 판정
    sk, lbl, _ = trading_stage2(d)

    return {
        'stage': sk,
        'label': lbl,
        'ai_explanation': d.get('condition_explanation', ''),
        'entry1': {
            'title': '🟡 1차 매수 조건 (6개 중 3개 이상)',
            'conditions': cond1,
            'met': met1, 'required': 3, 'total': 6,
            'blocked': block1,
            'block_reason': ('RSI > 50 — 아직 과열 구간이에요' if sig('sig_block_rsi50')
                             else '장대음봉 발생 (-5% 이상) — 추세가 강하게 꺾였어요' if sig('sig_block_bigdrop')
                             else None),
        },
        'entry2': {
            'title': '🟢 2차 매수 조건 (4개 모두 충족)',
            'conditions': cond2,
            'met': met2, 'required': 4, 'total': 4,
            'blocked': False, 'block_reason': None,
        },
        'entry3': {
            'title': '🟢 3차 매수 조건 (4개 모두 충족)',
            'conditions': cond3,
            'met': met3, 'required': 4, 'total': 4,
            'blocked': block3,
            'block_reason': ('RSI > 75 — 과매수 구간이에요' if sig('sig_block_rsi75')
                             else '장대음봉 발생 (-5% 이상)' if sig('sig_block_bigdrop')
                             else None),
        },
    }


# ══════════════════════════════════════════════════════════════════
#  4단계 타이밍 판정
# ══════════════════════════════════════════════════════════════════

def trading_stage(d):
    """
    분할 매수 전략 v2.0
    우선순위: 0 시장필터 > 3차매수 > 2차매수 > 1차매수 > 관망

    0️⃣ 시장 필터: QQQ MA200 아래 → 전종목 매수 금지
    1️⃣ 1차 매수 (20%): 6조건 중 3개 이상 + 금지조건 없음
    2️⃣ 2차 매수 (30%): 4조건 ALL + 금지조건 없음
    3️⃣ 3차 매수 (50%): 4조건 ALL + 금지조건 없음

    Returns: (stage_key, label, color)
    """
    # 사전 계산된 신호 플래그 읽기 (local_mag7_real이 저장)
    def sig(key, default=False):
        return bool(d.get(key, default))

    # ─────────────────────────────────────────────────────────
    # 0️⃣ 시장 필터 — QQQ MA200 아래면 전종목 관망
    # ─────────────────────────────────────────────────────────
    if not sig('qqq_above_ma200', True):
        return ('watch_market', '시장 관망', MGRAY)

    # ─────────────────────────────────────────────────────────
    # 3️⃣ 3차 매수 (50%) — 추세 전환 확인 후 본격 진입
    #   조건 4가지 ALL + 금지: RSI>75 또는 장대음봉(-5%)
    # ─────────────────────────────────────────────────────────
    block3 = sig('sig_block_rsi75') or sig('sig_block_bigdrop')
    if not block3:
        cond3 = [
            sig('sig_above_ma20_2d'),    # MA20 2일 연속 위
            sig('sig_ma20_slope_pos'),   # MA20 기울기 양수
            sig('sig_macd_above_zero'),  # MACD 0선 위
            sig('sig_vol_1p3'),          # 거래량 평균 1.3배 이상
        ]
        if all(cond3):
            return ('entry3', '3차 매수', GREEN)

    # ─────────────────────────────────────────────────────────
    # 2️⃣ 2차 매수 (30%) — 바닥 확인 후 추가 진입
    #   조건 4가지 ALL
    # ─────────────────────────────────────────────────────────
    cond2 = [
        sig('sig_double_bottom'),                            # 이중 바닥
        sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'),       # RSI>35 + 3일 연속 상승
        sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'), # MACD 골든크로스 or 히스토그램 3일 증가
        sig('sig_vol_1p2'),                                  # 거래량 평균 1.2배 이상
    ]
    if all(cond2):
        return ('entry2', '2차 매수', ORANGE)

    # ─────────────────────────────────────────────────────────
    # 1️⃣ 1차 매수 (20%) — 초기 진입 정찰대
    #   6조건 중 3개 이상 + 금지: RSI>50 또는 장대음봉(-5%)
    # ─────────────────────────────────────────────────────────
    block1 = sig('sig_block_rsi50') or sig('sig_block_bigdrop')
    if not block1:
        cond1_list = [
            sig('sig_rsi_le38'),      # RSI <= 38
            sig('sig_adx_le25'),      # ADX <= 25
            sig('sig_near_bb_low'),   # 종가 <= BB하단 x 1.02
            sig('sig_below_ma20'),    # 종가 < MA20
            sig('sig_low_stopped'),   # 하락 멈춤
            sig('sig_bounce2pct'),    # 당일 +2% 이상 반등
        ]
        if sum(cond1_list) >= 3:
            return ('entry1', '1차 매수', ORANGE)

    # ─────────────────────────────────────────────────────────
    # 관망 — 조건 미충족
    # ─────────────────────────────────────────────────────────
    return ('watch', '관망', MGRAY)


def trading_stage2(d):
    """
    분할 매수 전략 v2.0 — 판정2 (QQQ 시장 필터 제외)
    종목 자체 기술 신호만으로 판정 (시장 환경 무관)
    """
    def sig(key, default=False):
        return bool(d.get(key, default))

    # 3차 매수
    block3 = sig('sig_block_rsi75') or sig('sig_block_bigdrop')
    if not block3:
        if all([sig('sig_above_ma20_2d'), sig('sig_ma20_slope_pos'),
                sig('sig_macd_above_zero'), sig('sig_vol_1p3')]):
            return ('entry3', '3차 매수', GREEN)

    # 2차 매수
    if all([
        sig('sig_double_bottom'),
        sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'),
        sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'),
        sig('sig_vol_1p2'),
    ]):
        return ('entry2', '2차 매수', ORANGE)

    # 1차 매수
    block1 = sig('sig_block_rsi50') or sig('sig_block_bigdrop')
    if not block1:
        cond1_list = [
            sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_near_bb_low'),
            sig('sig_below_ma20'), sig('sig_low_stopped'), sig('sig_bounce2pct'),
        ]
        if sum(cond1_list) >= 3:
            return ('entry1', '1차 매수', ORANGE)

    return ('watch', '관망', MGRAY)


def _stage_reason2(d, sk):
    """판정2 근거 텍스트 (QQQ 필터 제외 버전)"""
    rsi = d['rsi']
    chg = d.get('change_pct', 0.0)

    def sig(key, default=False):
        return bool(d.get(key, default))

    if sk == 'entry3':
        parts = []
        if sig('sig_above_ma20_2d'):   parts.append('MA20 2일↑')
        if sig('sig_ma20_slope_pos'):  parts.append('MA20기울기+')
        if sig('sig_macd_above_zero'): parts.append('MACD 0선↑')
        if sig('sig_vol_1p3'):         parts.append('거래량 1.3배')
        return '3차: ' + ' + '.join(parts)

    if sk == 'entry2':
        parts = []
        if sig('sig_double_bottom'):     parts.append('이중바닥')
        if sig('sig_rsi_3d_up'):         parts.append(f'RSI {rsi:.1f} 3일↑')
        if sig('sig_macd_golden'):       parts.append('MACD골든')
        elif sig('sig_macd_hist_3d_up'): parts.append('히스토3일↑')
        if sig('sig_vol_1p2'):           parts.append('거래량 1.2배')
        return '2차: ' + ' + '.join(parts)

    if sk == 'entry1':
        met = []
        if sig('sig_rsi_le38'):    met.append(f'RSI {rsi:.1f}≤38')
        if sig('sig_adx_le25'):    met.append('ADX≤25')
        if sig('sig_near_bb_low'): met.append('BB하단')
        if sig('sig_below_ma20'):  met.append('MA20아래')
        if sig('sig_low_stopped'): met.append('하락멈춤')
        if sig('sig_bounce2pct'):  met.append(f'+{chg:.1f}%')
        return f'1차({len(met)}/6): ' + ' + '.join(met)

    # 관망 — 이유
    if sig('sig_block_rsi50'):
        return f'RSI {rsi:.1f} > 50 → 1차 금지'
    if sig('sig_block_bigdrop'):
        return f'장대음봉 {chg:.1f}%'
    cnt = sum([sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_near_bb_low'),
               sig('sig_below_ma20'), sig('sig_low_stopped'), sig('sig_bounce2pct')])
    return f'1차 {cnt}/6개 충족'


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
    BG      = '#060D18'   # figure background
    PANEL   = '#0A1525'   # axes background
    GRID_C  = '#1A3050'   # grid lines
    TICK_C  = '#A8C4DE'   # tick label
    UP_C    = '#34D399'   # 상승 캔들 (에메랄드 그린)
    DN_C    = '#F87171'   # 하락 캔들 (코럴 레드)
    MA20_C  = '#FBBF24'   # MA20 앰버
    MA50_C  = '#A78BFA'   # MA50 바이올렛
    MA200_C = '#FB923C'   # MA200 오렌지
    BB_C    = '#60A5FA'   # Bollinger 스카이블루
    MACD_C  = '#60A5FA'   # MACD line
    SIG_C   = '#FBBF24'   # Signal line
    RSI_C   = '#A78BFA'   # RSI line
    TEXT_C  = '#EEF4FB'   # title/label text

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
        ax.grid(True, color=GRID_C, linewidth=0.4, linestyle='--', zorder=0)

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
    ax1.axhline(d['high_52w'], color=UP_C, lw=0.8, ls=':', alpha=0.6)
    ax1.axhline(d['low_52w'],  color=DN_C, lw=0.8, ls=':', alpha=0.6)
    ax1.text(2, d['high_52w'] * 1.005, f'52W H  ${d["high_52w"]:.2f}',
             fontsize=7, color=UP_C, va='bottom', fontweight='bold')
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
    ax1.legend(loc='upper left', fontsize=7, framealpha=0.7, ncol=2,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor=TICK_C)
    today_label = datetime.date.today().strftime('%b %d, %Y')
    ax1.set_title(
        f'{d["company"]} ({d["ticker"]})  ·  {d["exchange"]}  ·  Technical Analysis  ·  {today_label}',
        fontsize=10.5, fontweight='bold', color=TEXT_C, pad=9)

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
    ax2.legend(loc='upper left', fontsize=7, framealpha=0.7,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor=TICK_C)
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
    ax3.legend(loc='upper left', fontsize=7, framealpha=0.7,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor=TICK_C)
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
    ax4.legend(loc='upper left', fontsize=7, framealpha=0.7, ncol=2,
               edgecolor=GRID_C, facecolor=PANEL, labelcolor=TICK_C)
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

    plt.savefig(path, dpi=155, bbox_inches='tight', facecolor=BG, edgecolor='none')
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════
#  PDF builder
# ══════════════════════════════════════════════════════════════════

_INDEX_H = 42 * mm   # 1페이지 하단에 고정 예약 높이


def _draw_p1_index(canvas, doc):
    """1페이지 하단 고정: 타이밍 단계 + 티어 인덱스 캔버스 직접 드로잉"""
    canvas.saveState()
    x  = M
    cw = PAGE_W - 2 * M
    y0 = _INDEX_H - 4 * mm   # 인덱스 블록 상단 Y

    # HR 구분선
    canvas.setStrokeColor(MGRAY)
    canvas.setLineWidth(0.5)
    canvas.line(x, y0, x + cw, y0)

    # 섹션 제목
    y = y0 - 4.5 * mm
    canvas.setFont(KF, 7.5)
    canvas.setFillColor(DGRAY)
    canvas.drawString(x, y, '타이밍 단계 안내')

    # 5단계 타이밍 행
    timing_rows = [
        (colors.HexColor('#1E8449'), '● 매수 적기  63+',   'RSI 과매도 회복 + MACD 상승 전환 + 거래량 동반. 적극적 매수 진입 구간'),
        (colors.HexColor('#1A5276'), '● 매수 검토  50~62', '기술적 지표 개선 중. 분할 매수 또는 소량 선진입 고려 가능'),
        (colors.HexColor('#7D6608'), '● 관망  37~49',      '방향성 불명확. 신규 진입보다 보유 포지션 유지 또는 현금 대기'),
        (colors.HexColor('#784212'), '● 비중 축소  24~36', '약세 신호 감지. 보유 비중 단계적 축소 또는 손절 검토'),
        (colors.HexColor('#922B21'), '● 매도 적기  ~23',   'MA50 이탈 + MACD 하락 or BB 과열 + 거래량 급증. 적극적 매도·청산 구간'),
    ]
    lbl_w = cw * 0.22
    y -= 2 * mm
    canvas.setFont(KF, 7)
    for clr, lbl, desc in timing_rows:
        canvas.setFillColor(clr)
        canvas.drawString(x, y, lbl)
        canvas.setFillColor(DGRAY)
        canvas.drawString(x + lbl_w, y, desc)
        y -= 4.2 * mm

    # 4단계 타이밍 범례
    y -= 1 * mm
    stage_items = [
        (0,          colors.HexColor('#FF6F00'), '■ 1차 진입', 'RSI 과매도 탈출 — 소량 분할매수'),
        (cw * 0.28,  GREEN,                      '■ 매수 적기', 'MA20 돌파+MACD 골든크로스+거래량 동반'),
        (cw * 0.56,  RED,                        '■ 매도 시작', 'MA200/BB상단 근접 또는 약세 다이버전스'),
        (cw * 0.80,  MGRAY,                      '■ 관망', '조건 미충족 — 신호 대기'),
    ]
    canvas.setFont(KF, 7)
    for dx, clr, badge, desc in stage_items:
        canvas.setFillColor(clr)
        canvas.drawString(x + dx, y, badge)
        bw = canvas.stringWidth(badge, KF, 7)
        canvas.setFillColor(DGRAY)
        canvas.drawString(x + dx + bw + 1.5 * mm, y, desc)

    canvas.restoreState()


def build_pdf(d, chart_path, output_path):
    a_sc, b_sc, c_sc, d_sc, e_sc, f_sc, total = auto_score(d)
    op_label, op_color = opinion_label(total)
    stage_key, stage_lbl, stage_clr = trading_stage(d)
    signals = auto_signals(d)
    ma200_status = '현재가 상향' if d['close'] > d['ma200'] else '현재가 하향 이탈'

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             leftMargin=M, rightMargin=M,
                             topMargin=9 * mm, bottomMargin=8 * mm)
    story = []

    # Header
    hdr = Table(
        [[Paragraph(d['company'], se('hc', 17, NAVY, TA_LEFT, bold=True)),
          Paragraph(f'{d["ticker"]}  |  {d["exchange"]}  |  {d["sector"]}  ·  {datetime.date.today().strftime("%b %d, %Y")}',
                    se('ex', 8, DGRAY, TA_RIGHT, semi=True))]],
        colWidths=[CW * 0.60, CW * 0.40])
    hdr.setStyle(TableStyle([
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0),(-1,-1), 0), ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING', (0,0),(-1,-1), 0), ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width='100%', thickness=3, color=BLUE,
                             spaceBefore=2 * mm, spaceAfter=2.5 * mm))

    # Metrics bar (6 columns: 종가/고점/저점/MA200/점수/타이밍단계)
    stage_bg = (colors.HexColor('#D8EEE6') if stage_key == 'buy'
                else colors.HexColor('#FFF3E0') if stage_key == 'entry'
                else colors.HexColor('#FDEAEA') if stage_key in ('sell','sell_div')
                else LGRAY)
    chg_sign = '+' if d['change_pct'] >= 0 else ''
    lbl_row = [Paragraph(t, s(f'ml{i}', 7, DGRAY, TA_CENTER, bold=True))
               for i, t in enumerate(['종가', '52주 고점', '52주 저점', '200일 MA', '종합점수', '타이밍 단계'])]
    val_row = [
        Paragraph(f'${d["close"]:.2f}',    se(f'mv0', 12, RED if d['change_pct'] < 0 else GREEN, TA_CENTER, bold=True)),
        Paragraph(f'${d["high_52w"]:.2f}', se(f'mv1', 12, NAVY,  TA_CENTER, bold=True)),
        Paragraph(f'${d["low_52w"]:.2f}',  se(f'mv2', 12, NAVY,  TA_CENTER, bold=True)),
        Paragraph(f'${d["ma200"]:.2f}',    se(f'mv3', 12, RED if d['close'] < d['ma200'] else GREEN, TA_CENTER, bold=True)),
        Paragraph(f'{total} / 85',         se(f'mv4', 12, op_color, TA_CENTER, bold=True)),
        Paragraph(f'<b>{stage_lbl}</b>',   s(f'mv5',  12, DGRAY if stage_clr == MGRAY else stage_clr, TA_CENTER, bold=True)),
    ]
    sub_row = [Paragraph(v, s(f'ms{i}', 7, DGRAY, TA_CENTER))
               for i, v in enumerate([
                   f'{chg_sign}{d["change_pct"]:.2f}%',
                   d.get('high_52w_date', ''),
                   d.get('low_52w_date',  ''),
                   ma200_status, '/85점 만점',
                   '4단계 판정'])]
    col6 = [CW * 0.16] * 5 + [CW * 0.20]
    mt = Table([lbl_row, val_row, sub_row], colWidths=col6)
    mt.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), LGRAY),
        ('BACKGROUND',    (4,0),(4,-1),  colors.HexColor('#FEF0F0')),
        ('BACKGROUND',    (5,0),(5,-1),  stage_bg),
        ('BOX',           (0,0),(-1,-1), 0.8, MGRAY),
        ('LINEAFTER',     (0,0),(4,-1),  0.4, MGRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ]))
    story.append(mt)
    story.append(Spacer(1, 3 * mm))

    # Chart
    img_h = CW * (9 / 11.5)
    story.append(Image(chart_path, width=CW, height=img_h))
    story.append(Spacer(1, 3 * mm))


    # Opinion — 초보자 친화적 구조화 섹션
    for fl in _build_opinion_flowables(d, total, op_label, a_sc, b_sc):
        story.append(fl)
    story.append(Spacer(1, 2 * mm))

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

    return (
        f'[타이밍 판정: {op_label}  {total}/85점]<br/>'
        f'{d["ticker"]}의 현재 기술적 상태는 <b>{ma_state}</b>입니다. '
        f'{rsi_timing}. {macd_state}.<br/><br/>'
        f'<b>관심 종목 (매수 관점):</b> {buy_cond}<br/>'
        f'<b>보유 종목 (매도 관점):</b> {sell_cond}<br/>'
        f'<b>손절 기준:</b> {stop_loss}'
    )


def _build_opinion_flowables(d, total, op_label, a_sc, b_sc):
    """초보자 친화적 타이밍 종합 판정 — 지표 현황·전략·시나리오·결론 플로어블 리스트 반환"""
    c     = d['close'];  m20  = d['ma20'];  m50  = d['ma50'];  m200 = d['ma200']
    rsi   = d['rsi'];    macd_v = d['macd']; macd_s = d['macd_signal']
    bb_u  = d['bb_upper']; bb_l = d['bb_lower']
    bb_range = bb_u - bb_l
    bb_pct   = (c - bb_l) / bb_range if bb_range > 0 else 0.5
    stop_price = m20 * 0.97

    # ── 방향성·ADX·다이버전스 데이터 ──────────────────────────────
    rsi_slope   = d.get('rsi_slope',        0.0)
    rsi_slope3  = d.get('rsi_slope3',       0.0)   # 단기 3일
    hist_slope  = d.get('macd_hist_slope',  0.0)
    hist_slope3 = d.get('macd_hist_slope3', 0.0)   # 단기 3일
    ma20_slope  = d.get('ma20_slope',       0.0)
    adx_val     = d.get('adx',      20.0)
    plus_di     = d.get('plus_di',  25.0)
    minus_di    = d.get('minus_di', 25.0)
    divergence  = d.get('rsi_divergence', 'none')

    def _dir(slope, thr=0.8):
        """기울기 → 방향 화살표"""
        if slope >  thr: return ' ↑'
        if slope < -thr: return ' ↓'
        return ' →'

    def _dir_combo(slope5, slope3, thr5=0.8, thr3=0.5):
        """5일 추세 + 3일 단기 반등을 함께 반영한 화살표
        5일 하락 중이라도 3일이 반등이면 '↗ 단기반등' 표시"""
        if slope5 > thr5 and slope3 > thr3:   return '↑'
        if slope5 < -thr5 and slope3 > thr3:  return '↗'   # 단기 반등!
        if slope5 < -thr5 and slope3 < -thr3: return '↓'
        if slope5 > thr5 and slope3 < -thr3:  return '↘'   # 단기 조정
        return '→'

    flowables = []

    # ── 섹션 헤더 ──────────────────────────────────────────────────
    op_hdr = Table(
        [[Paragraph('  타이밍 종합 판정  |  초보자 가이드 포함', s('oh', 9, WHITE, TA_LEFT, bold=True))]],
        colWidths=[CW])
    op_hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), BLUE),
        ('TOPPADDING',    (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
    ]))
    flowables.append(op_hdr)

    # ── 1. 지표별 현황 ─────────────────────────────────────────────
    # RSI (방향 화살표 포함)
    _rsi_dir = _dir(rsi_slope, 1.0)
    if rsi >= 70:
        rsi_c, rsi_st, rsi_ex = RED,    f'RSI {rsi:.1f}{_rsi_dir} — 과열', '지금 사면 꼭대기에 물릴 수 있어요. 보유자라면 일부 팔아 수익을 챙기세요'
    elif rsi >= 60:
        rsi_c, rsi_st, rsi_ex = ORANGE, f'RSI {rsi:.1f}{_rsi_dir} — 상단', '잘 오르고 있지만 더 크게 오르긴 어려울 수 있어요. 추격 매수는 조심하세요'
    elif rsi >= 45:
        rsi_c, rsi_st, rsi_ex = ORANGE, f'RSI {rsi:.1f}{_rsi_dir} — 중립', '아직 방향을 못 잡고 눈치 보는 중이에요. 조금 더 기다려 보는 게 좋아요'
    elif rsi >= 30:
        rsi_c = GREEN if rsi_slope > 0 else ORANGE
        rsi_c, rsi_st, rsi_ex = rsi_c, f'RSI {rsi:.1f}{_rsi_dir} — 반등 구간', '매도 압력이 줄어들고 반등 모멘텀이 시작되고 있어요. 관심을 가져볼 구간이에요'
    else:
        rsi_c, rsi_st, rsi_ex = RED,    f'RSI {rsi:.1f}{_rsi_dir} — 급락', '많이 떨어졌지만 아직 바닥인지 확신하기 어려워요. 급하게 사지 마세요'

    # MACD (히스토그램 방향 화살표 포함)
    _macd_dir = _dir(hist_slope, 0.05)
    if macd_v > macd_s and macd_v > 0:
        macd_c, macd_st, macd_ex = GREEN,  f'MACD {macd_v:+.2f}{_macd_dir} — 상승 전환', '좋은 신호예요! 올라가는 힘이 본격적으로 붙기 시작했어요'
    elif macd_v > macd_s and macd_v <= 0:
        macd_c, macd_st, macd_ex = ORANGE, f'MACD {macd_v:+.2f}{_macd_dir} — 수렴 중',  '아직 힘이 부족하지만 서서히 방향을 바꾸고 있어요. 긍정적인 변화예요'
    elif macd_v <= macd_s and macd_v >= 0:
        macd_c, macd_st, macd_ex = ORANGE, f'MACD {macd_v:+.2f}{_macd_dir} — 약화 중',  '오르다가 꺾이는 중이에요. 잠깐 쉬어갈 수 있으니 주의하세요'
    else:
        macd_c, macd_st, macd_ex = RED,    f'MACD {macd_v:+.2f}{_macd_dir} — 하락 중',  '아직 하락 흐름이 남아 있어요. 완전히 돌아섰다고 보긴 일러요'

    # MA200
    ma200_pct = (c / m200 - 1) * 100
    if c > m200:
        ma200_c, ma200_st = GREEN, f'MA200 ${m200:.2f} — 지지 중'
        ma200_ex = f'MA200이 {abs(ma200_pct):.0f}% 아래서 든든하게 받쳐주고 있어요. 장기적으로 안심할 수 있는 구간이에요'
    else:
        ma200_c, ma200_st = RED, f'MA200 ${m200:.2f} — 이탈'
        ma200_ex = f'장기적으로 봐도 아직 힘든 구간이에요. ${m200:.2f}를 다시 넘어서야 비로소 안심할 수 있어요'

    # BB 위치
    if bb_pct <= 0.15:
        bb_c, bb_st, bb_ex = GREEN,  f'BB하단 ${bb_l:.2f} — 근접', '가격이 볼린저 밴드 아래쪽 끝에 가까워요. 여기서 튀어오를 수 있는 자리예요'
    elif bb_pct >= 0.85:
        bb_c, bb_st, bb_ex = RED,    f'BB상단 ${bb_u:.2f} — 근접', '가격이 너무 많이 올라온 상태예요. 잠깐 쉬어갈 수 있으니 조심하세요'
    else:
        bb_c, bb_st, bb_ex = ORANGE, f'BB 중간 ({bb_pct:.0%})',     '어느 쪽으로도 치우치지 않은 중간 구간이에요. 방향성을 조금 더 지켜봐야 해요'

    # MA20/50 지지·저항
    above_ma20 = c > m20;  above_ma50 = c > m50
    if above_ma20 and above_ma50:
        ma_c, ma_st, ma_ex = GREEN,  'MA20/50 지지', f'단기적으로 안정적인 흐름이에요. MA20(${m20:.0f})/MA50(${m50:.0f})이 아래서 잘 받쳐주고 있어요'
    elif not above_ma20 and not above_ma50:
        ma_c, ma_st, ma_ex = RED,    'MA20/50 저항', f'${m20:.0f}~${m50:.0f} 구간을 뚫어야 본격 반등이 시작돼요. 지금은 그 벽 아래에 있어요'
    elif above_ma20:
        ma_c, ma_st, ma_ex = ORANGE, 'MA50 저항',   f'MA20(${m20:.0f})은 넘었지만 MA50(${m50:.0f})이 아직 저항으로 남아 있어요'
    else:
        ma_c, ma_st, ma_ex = ORANGE, 'MA20 저항',   f'MA20(${m20:.0f})을 아직 못 넘은 상태예요. 이 선 위로 올라서는지 확인이 필요해요'

    # ADX 추세 강도 행
    if adx_val >= 30:
        adx_c  = GREEN if plus_di > minus_di else RED
        adx_st = f'ADX {adx_val:.0f} — 추세 강함 (+DI {plus_di:.0f} / -DI {minus_di:.0f})'
        adx_ex = f'현재 추세가 강해요. {"상승" if plus_di > minus_di else "하락"} 방향 신호를 더 신뢰하세요'
    elif adx_val >= 20:
        adx_c  = ORANGE
        adx_st = f'ADX {adx_val:.0f} — 추세 형성 중 (+DI {plus_di:.0f} / -DI {minus_di:.0f})'
        adx_ex = '추세가 서서히 생기고 있어요. 방향을 확인한 뒤 진입하세요'
    else:
        adx_c  = ORANGE
        adx_st = f'ADX {adx_val:.0f} — 추세 없음'
        adx_ex = '지금은 뚜렷한 추세 없이 흔들리는 구간이에요. RSI·볼린저밴드 중심으로 판단하세요'

    ind_rows = [
        ('RSI',     rsi_c,    rsi_st,    rsi_ex),
        ('MACD',    macd_c,   macd_st,   macd_ex),
        ('MA200',   ma200_c,  ma200_st,  ma200_ex),
        ('BB 위치', bb_c,     bb_st,     bb_ex),
        ('MA20/50', ma_c,     ma_st,     ma_ex),
        ('ADX',     adx_c,    adx_st,    adx_ex),
    ]
    ind_data = [[Paragraph(t, s('ith', 7.5, WHITE, TA_CENTER, bold=True))
                 for t in ['지표', '지금 상태', '쉬운 설명']]]
    for lbl, clr, st, ex in ind_rows:
        ind_data.append([
            Paragraph(lbl, s('itd', 7.5, NAVY, TA_CENTER, bold=True)),
            Paragraph(st,  s('its', 7.5, clr,  TA_LEFT,   bold=True)),
            Paragraph(ex,  s('ite', 7.5, NAVY, TA_LEFT)),
        ])
    ind_t = Table(ind_data, colWidths=[CW*0.11, CW*0.35, CW*0.54])
    ind_sty = [
        ('BACKGROUND', (0,0),(-1,0),  NAVY),
        ('BOX',        (0,0),(-1,-1), 0.5, MGRAY),
        ('INNERGRID',  (0,0),(-1,-1), 0.3, colors.HexColor('#C0D8EE')),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 3), ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING',(0,0),(-1,-1), 5), ('RIGHTPADDING',  (0,0),(-1,-1), 5),
    ]
    for i in range(1, len(ind_data)):
        ind_sty.append(('BACKGROUND', (0,i),(-1,i), LGRAY if i % 2 == 1 else NEUT_BG))
    ind_t.setStyle(TableStyle(ind_sty))

    flowables.append(Spacer(1, 2.5*mm))
    flowables.append(Paragraph('지금 상황은 어떤가요?', s('sec_hd', 7.5, BLUE, bold=True)))
    flowables.append(Spacer(1, 1*mm))
    flowables.append(ind_t)

    # ── 2. 현재 상황 스캔 + 실전 매매 타이밍 ──────────────────────
    tk         = d['ticker']
    up_cnt     = sum([rsi_slope > 1.0,  hist_slope > 0.05,  ma20_slope > 1.0])
    dn_cnt     = sum([rsi_slope < -1.0, hist_slope < -0.05, ma20_slope < -1.0])
    stop_price = m20 * 0.97
    macd_positive = (macd_v > 0)

    rsi_dir_txt  = _dir_combo(rsi_slope,  rsi_slope3,  thr5=1.0,  thr3=0.5)
    macd_dir_txt = _dir_combo(hist_slope, hist_slope3, thr5=0.05, thr3=0.02)

    # 단기 반등 여부 플래그
    rsi_rebounding  = (rsi_slope  < -1.0 and rsi_slope3  > 0.5)
    macd_rebounding = (hist_slope < -0.05 and hist_slope3 > 0.02)

    stage_key, stage_lbl, stage_clr = trading_stage(d)

    # ─ 동적 헤드라인 (trading_stage 결과 기반) ─
    if stage_key == 'sell_div':
        headline = f'{tk} — 가짜 상승 경보! 약세 다이버전스 감지'
    elif stage_key == 'buy':
        headline = f'{tk} — 매수 적기! MA20 돌파 + MACD 상승 확인'
    elif stage_key == 'entry':
        headline = f'{tk} — 바닥 탈출 신호! 발가락 담그기 구간'
    elif stage_key == 'sell':
        headline = f'{tk} — 저항선 도달, 수익 지키기 구간 (보유자 주의)'
    else:
        headline = f'{tk} — 방향 탐색 중, 관망이 정답'

    # ─ 내러티브 문단 (stage_key 기반) ─
    if stage_key == 'sell_div':
        narrative = (
            '차는 달리고 있지만 기름이 빠르게 소진되고 있어요. '
            '주가는 올랐지만 내부 에너지(RSI)는 이미 꺾이는 <b>약세 다이버전스</b>가 감지됐어요. '
            '지금 추격해서 사면 꼭대기에서 잡을 가능성이 높아요. 기다리는 게 정답입니다.'
        )
    elif stage_key == 'buy':
        narrative = (
            f'MA20 돌파, MACD 골든크로스, 거래량 동반 — 세 가지 조건이 모두 충족됐어요. '
            '엔진이 풀 파워로 작동하고 있는 구간이에요. '
            '단, 한 번에 다 사기보단 나눠서 담는 전략이 더 안전해요.'
        )
    elif stage_key == 'entry':
        narrative = (
            '공이 바닥으로 떨어지다가 튕겨 올라오려는 탄성(RSI)이 살아나고 있어요. '
            'RSI가 과매도 구간에서 반등을 시작했어요. '
            '완전한 추세 전환 전 <b>소액으로 먼저 탐색</b>하기 좋은 타이밍이에요.'
        )
    elif stage_key == 'sell':
        narrative = (
            '주가가 강력한 저항선에 다가왔어요. '
            'MA200이나 볼린저 밴드 상단 근처는 많은 매도 물량이 기다리는 구간이에요. '
            '보유자라면 수익 일부를 현금화하고, 신규 진입은 신중하게 기다리세요.'
        )
    else:
        narrative = (
            '지표 방향이 아직 뚜렷하지 않아요. '
            'RSI와 MACD가 방향을 탐색 중이고, MA20 근처에서 지지·저항을 확인하는 구간이에요. '
            '신규 진입보단 현금 대기가 무난해요.'
        )

    # ─ 불렛 — RSI ─
    if divergence == 'bearish':
        rsi_bullet = f'차는 달리는데 엔진 출력이 떨어지고 있어요 (약세 다이버전스, RSI {rsi:.1f} {rsi_dir_txt})'
    elif divergence == 'bullish':
        rsi_bullet = f'주가는 내려왔지만 엔진이 다시 살아나고 있어요 (강세 다이버전스, RSI {rsi:.1f} {rsi_dir_txt})'
    elif rsi < 30 and rsi_rebounding:
        rsi_bullet = (f'RSI({rsi:.1f}) {rsi_dir_txt} — 과매도 바닥권에서 단기 반등 시작! '
                      f'5일 추세는 아직 하락이지만, 최근 3일은 올라오고 있어요. 바닥 신호를 주시하세요')
    elif rsi < 30:
        rsi_bullet = f'RSI({rsi:.1f}) {rsi_dir_txt} — 과매도 구간. 바닥권이지만 아직 반등 신호가 확인되지 않았어요'
    elif rsi > 70:
        rsi_bullet = f'RSI({rsi:.1f}) {rsi_dir_txt} — 과매수 구간. 많이 올라왔어요. 추격 매수는 위험할 수 있어요'
    elif rsi_rebounding:
        rsi_bullet = (f'RSI({rsi:.1f}) {rsi_dir_txt} — 5일 추세는 하락이지만 최근 3일은 반등 중! '
                      f'(5일 {rsi_slope:+.1f} / 3일 {rsi_slope3:+.1f})  단기 바닥 가능성을 주목하세요')
    elif rsi_slope < -1.0:
        rsi_bullet = f'RSI({rsi:.1f}) {rsi_dir_txt} — 계속 내려가고 있어요. 엔진이 꺼지려는 느낌이에요'
    elif rsi_slope > 1.0:
        rsi_bullet = f'RSI({rsi:.1f}) {rsi_dir_txt} — 방향을 바꿔 올라오고 있어요. 모멘텀이 살아나는 신호예요'
    else:
        rsi_bullet = f'RSI({rsi:.1f}) {rsi_dir_txt} — 중립 구간에서 방향을 탐색 중이에요'

    # ─ 불렛 — MACD ─
    if macd_rebounding:
        macd_bullet = (f'히스토그램 {macd_dir_txt} — 5일 추세는 감소 중이지만 최근 3일 반등 중! '
                       f'(5일 {hist_slope:+.3f} / 3일 {hist_slope3:+.3f})'
                       + ('' if macd_positive else '  제로선은 아직 하방'))
    elif hist_slope < -0.05:
        macd_bullet = (f'히스토그램이 빠르게 줄어들고 있어요 {macd_dir_txt} — 하락 압력이 커지고 있어요'
                       + ('' if macd_positive else '  (제로선 아래 — 아직 매수 신호 아님)'))
    elif hist_slope > 0.05:
        macd_bullet = (f'히스토그램이 점점 커지고 있어요 {macd_dir_txt} — 상승 동력이 강해지고 있는 좋은 신호예요'
                       + (' (제로선 위 돌파 — 강력한 매수 신호!)' if macd_positive else ''))
    else:
        macd_bullet = f'MACD가 방향을 탐색 중이에요 {macd_dir_txt} — 아직 뚜렷한 추세가 잡히지 않았어요'

    # ─ 불렛 — MA (MA200 심리적 의미 포함) ─
    res_list = []
    sup_list = []
    if c < m20:  res_list.append(f'MA20(${m20:.2f})')
    else:        sup_list.append(f'MA20(${m20:.2f})')
    if c < m50:  res_list.append(f'MA50(${m50:.2f})')
    else:        sup_list.append(f'MA50(${m50:.2f})')
    if c < m200: res_list.append(f'MA200(${m200:.2f})')
    else:        sup_list.append(f'MA200(${m200:.2f})')
    m200_note = f'  ※ MA200(${m200:.2f})은 지난 1년 평균가 — 여기까지 오면 사려는 대기 수요가 많아요'
    if res_list and sup_list:
        ma_bullet = (f'{" · ".join(res_list)}이 위에서 저항 중이에요. '
                     f'돌파해야 본격 상승이 가능해요. '
                     f'아래엔 {" · ".join(sup_list)} 지지선이 버티고 있어요.'
                     + (m200_note if c < m200 else ''))
    elif res_list:
        ma_bullet = (f'모든 이동평균선 아래에 있어요. {" · ".join(res_list)} 위에서 누르는 어려운 상황이에요.'
                     + (m200_note if c < m200 else ''))
    else:
        ma_bullet = f'모든 이동평균선 위에 있어요. {" · ".join(sup_list)} 아래에서 지지해주는 좋은 상황이에요'

    # ─ 신규 진입: 3단계 전략 ─
    if divergence == 'bearish' or total < 50:
        entry_quote = '"지금 바로 사지 마세요! 먼저 지지를 확인하세요."'
    elif total >= 63:
        entry_quote = '"신호가 강해요! 분할로 나눠서 담아가세요."'
    else:
        entry_quote = '"신호가 나오면 조금씩 분할로 접근하세요."'
    step1 = f'지금 (정찰대): ${c:.2f} 근처에서 소량만 먼저 사두세요. 틀려도 손실이 작아요'
    step2 = f'확인 후 (2차): MA20(${m20:.2f}) 위로 종가가 올라서는 걸 확인하고 추가 매수하세요'
    if c < m200:
        step3 = (f'최종 보루: MA200(${m200:.2f})는 지난 1년 평균가예요. '
                 f'여기까지 밀리면 겁내지 말고 오히려 모아가는 구간이에요')
    elif c < m50:
        step3 = f'최종 보루: MA50(${m50:.2f}) 근처까지 밀리면 오히려 모아가는 구간이에요'
    else:
        step3 = f'최종 보루: ${bb_l:.2f}(볼린저 하단) 근처까지 밀리면 오히려 모아가는 구간이에요'
    macd_hint = (f'※ MACD 히스토그램이 아직 마이너스 영역이에요. '
                 f'플러스로 돌아설 때까지는 "공격"보다 "매집" 자세가 필요해요'
                 if not macd_positive else '')

    # ─ 보유자 대응 ─
    if divergence == 'bearish' or dn_cnt >= 2:
        hold_quote = '"수익은 챙기고, 손실은 짧게 끊으세요."'
    elif total >= 63:
        hold_quote = '"추세가 살아있어요! 너무 빨리 팔지 마세요."'
    else:
        hold_quote = '"손절선을 지키면서 상황을 지켜보세요."'
    if c > m200:
        take_profit = (f'MA50(${m50:.2f})~MA200(${m200:.2f}) 구간에서 주춤거리면 '
                       f'일부 수익을 실현하고 현금을 확보하세요')
    else:
        take_profit = (f'MA20(${m20:.2f}) 근처에서 반등이 막히면 '
                       f'일부 수익을 실현하고 현금을 확보하세요')
    danger_line = (f'${stop_price:.2f}(MA20 -3%) 아래로 종가가 내려가면 추가 하락 압력이 강해져요. '
                   f'미련 없이 비중을 줄이세요')

    # ── 레이아웃 조립 ─────────────────────────────────────────────

    # ① 헤드라인 배너 (좌: 제목, 우: 타이밍 단계)
    hdl_tbl = Table(
        [[Paragraph(headline, s('hdl', 9, WHITE, TA_LEFT, bold=True)),
          Paragraph(f'[ {stage_lbl} ]', s('stg', 9, WHITE, TA_RIGHT, bold=True))]],
        colWidths=[CW * 0.65, CW * 0.35])
    hdl_tbl.setStyle(TableStyle([
        ('BACKGROUND',  (0,0),(-1,-1), NAVY),
        ('TOPPADDING',  (0,0),(-1,-1), 7), ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('LEFTPADDING', (0,0),(-1,-1), 10), ('RIGHTPADDING', (0,0),(-1,-1), 8),
        ('VALIGN',      (0,0),(-1,-1), 'MIDDLE'),
    ]))

    # ② Section 1 헤더 (Signal 배지 제거)
    scan_hdr = Table(
        [[Paragraph('1. 현재 상황 스캔', s('sch', 8, WHITE, TA_LEFT, bold=True))]],
        colWidths=[CW])
    scan_hdr.setStyle(TableStyle([
        ('BACKGROUND',  (0,0),(-1,-1), colors.HexColor('#2C3E50')),
        ('TOPPADDING',  (0,0),(-1,-1), 4), ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING', (0,0),(-1,-1), 8),
    ]))

    rsi_bl_clr  = RED if rsi_slope < -1.0 else (GREEN if rsi_slope > 1.0 else NAVY)
    macd_bl_clr = RED if hist_slope < -0.05 else (GREEN if hist_slope > 0.05 else NAVY)
    ma_bl_clr   = RED if res_list else GREEN

    # ③ 내러티브 + 불렛 3행
    scan_rows = [
        [Paragraph(narrative, s('nb', 8, NAVY, lead=13))],
        [Paragraph(f'<b>▶ 투자 심리 (RSI):</b>  {rsi_bullet}',
                   s('bl1', 7.5, rsi_bl_clr, lead=12))],
        [Paragraph(f'<b>▶ 추세 힘 (MACD):</b>  {macd_bullet}',
                   s('bl2', 7.5, macd_bl_clr, lead=12))],
        [Paragraph(f'<b>▶ 저항/지지 (MA):</b>  {ma_bullet}',
                   s('bl3', 7.5, ma_bl_clr, lead=12))],
    ]
    scan_body = Table(scan_rows, colWidths=[CW])
    scan_body.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,0),  NEUT_BG),
        ('BACKGROUND',   (0,1),(-1,1),  LGRAY),
        ('BACKGROUND',   (0,2),(-1,2),  NEUT_BG),
        ('BACKGROUND',   (0,3),(-1,3),  LGRAY),
        ('BOX',          (0,0),(-1,-1), 0.5, MGRAY),
        ('LINEBELOW',    (0,0),(-1,-2), 0.3, colors.HexColor('#C0D8EE')),
        ('TOPPADDING',   (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',  (0,0),(-1,-1), 10), ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
    ]))

    # ④ Section 2 헤더
    timing_hdr = Table(
        [[Paragraph('2. 초보자를 위한 실전 매매 타이밍', s('tch', 8, WHITE, TA_LEFT, bold=True))]],
        colWidths=[CW])
    timing_hdr.setStyle(TableStyle([
        ('BACKGROUND',  (0,0),(-1,-1), BLUE2),
        ('TOPPADDING',  (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING', (0,0),(-1,-1), 8),
    ]))

    # ⑤ 타이밍 단계별 전략 블록
    CART_BG  = colors.HexColor('#E8F5E9')
    CART_HDR = colors.HexColor('#C8E6C9')
    SELL_BG2 = colors.HexColor('#FDEAEA')
    SELL_HDR2= colors.HexColor('#FFCDD2')
    HOLD_BG  = colors.HexColor('#E3F2FD')
    HOLD_HDR = colors.HexColor('#BBDEFB')
    WATCH_BG = colors.HexColor('#F5F5F5')
    WATCH_HDR= colors.HexColor('#E0E0E0')
    ENTRY_BG = colors.HexColor('#FFF3E0')
    ENTRY_HDR= colors.HexColor('#FFE0B2')

    if stage_key == 'entry':
        stg_rows = [
            [Paragraph('[1단계 진입] 발가락 담그기 — RSI 과매도 탈출 감지', s('sh1', 9, colors.HexColor('#BF4600'), TA_LEFT, bold=True))],
            [Paragraph('"틀려도 괜찮다는 마음으로, 소액만 먼저 넣어보세요."', s('sq1', 8, NAVY, lead=12))],
            [Paragraph(f'<b>진입 금액:</b>  전체 예산의 10~15%만 먼저 진입하세요. 추가 하락에도 버틸 수 있는 금액이어야 해요', s('se1', 7.5, NAVY, lead=12))],
            [Paragraph(f'<b>진입 기준:</b>  RSI {rsi:.1f}이 30선을 회복하며 올라오는 중 — 지금이 그 시점이에요', s('se2', 7.5, ORANGE, lead=12))],
            [Paragraph(f'<b>다음 단계:</b>  MA20(${m20:.2f}) 위로 종가가 올라서면 2단계(본격 매수)로 전환하세요', s('se3', 7.5, NAVY, lead=12))],
        ]
        stg_bg = ENTRY_BG; stg_hdr_bg = ENTRY_HDR; stg_clr2 = ORANGE
    elif stage_key == 'buy':
        stg_rows = [
            [Paragraph('[매수 적기] 본격 승부 — MA20 돌파 + MACD 골든크로스 + 거래량 확인', s('sh2', 9, colors.HexColor('#0E6E3F'), TA_LEFT, bold=True))],
            [Paragraph('"추세가 확인됐어요! 이제 본격적으로 비중을 높여도 좋아요."', s('sq2', 8, NAVY, lead=12))],
            [Paragraph(f'<b>매수 금액:</b>  전체 예산의 30~50%까지 비중을 높이세요. 추세를 타는 구간이에요', s('sb1', 7.5, NAVY, lead=12))],
            [Paragraph(f'<b>핵심 조건:</b>  MA20(${m20:.2f}) 위 안착 + MACD 골든크로스 + 거래량 평균 이상', s('sb2', 7.5, GREEN, lead=12))],
            [Paragraph(f'<b>손절 기준:</b>  MA20(${m20:.2f}) 아래로 다시 내려가면 진입 취소 고려하세요', s('sb3', 7.5, RED, lead=12))],
        ]
        stg_bg = CART_BG; stg_hdr_bg = CART_HDR; stg_clr2 = GREEN
    elif stage_key in ('sell', 'sell_div'):
        reason_str = '약세 다이버전스 감지' if stage_key == 'sell_div' else ma_bullet[:30]
        stg_rows = [
            [Paragraph('[매도 시작] 수익 지키기 — 강력한 저항선 도달 또는 이탈 신호 (보유자 해당)', s('sh3', 9, colors.HexColor('#A93226'), TA_LEFT, bold=True))],
            [Paragraph('"수익은 챙기고, 손실은 짧게 끊으세요."', s('sq3', 8, NAVY, lead=12))],
            [Paragraph(f'<b>1차 매도:</b>  보유 수익의 30~50%를 먼저 현금화하세요. 나머지는 추세 확인 후 판단하세요', s('sd1', 7.5, NAVY, lead=12))],
            [Paragraph(f'<b>위험 라인:</b>  ${stop_price:.2f}(MA20 -3%) 아래로 내려가면 미련 없이 비중을 줄이세요', s('sd2', 7.5, RED, lead=12))],
            [Paragraph(f'<b>신규 진입:</b>  지금은 새로 사지 마세요. 조정 후 지지를 확인한 뒤 재진입을 노리세요', s('sd3', 7.5, ORANGE, lead=12))],
        ]
        stg_bg = SELL_BG2; stg_hdr_bg = SELL_HDR2; stg_clr2 = RED
    else:  # watch
        stg_rows = [
            [Paragraph('[관망] 신호 대기 중 — 아직 진입 조건 미충족', s('sh4', 9, DGRAY, TA_LEFT, bold=True))],
            [Paragraph('"지금은 기다리는 것도 훌륭한 전략이에요."', s('sq4', 8, NAVY, lead=12))],
            [Paragraph(f'<b>진입 대기:</b>  RSI가 30 이하로 떨어지거나 MA20(${m20:.2f})을 돌파할 때까지 현금을 보유하세요', s('sw1', 7.5, NAVY, lead=12))],
            [Paragraph(f'<b>관심 기준:</b>  MACD 골든크로스 + 거래량 증가가 동반되면 그때 진입을 검토하세요', s('sw2', 7.5, NAVY, lead=12))],
            [Paragraph(f'<b>손절 기준:</b>  이미 보유 중이라면 ${stop_price:.2f}(MA20 -3%) 이탈 시 비중 축소를 고려하세요', s('sw3', 7.5, MGRAY, lead=12))],
        ]
        stg_bg = WATCH_BG; stg_hdr_bg = WATCH_HDR; stg_clr2 = MGRAY

    stg_blk = Table(stg_rows, colWidths=[CW])
    stg_st = [
        ('BACKGROUND',  (0,0),(-1,0),  stg_hdr_bg),
        ('BACKGROUND',  (0,1),(-1,-1), stg_bg),
        ('BOX',         (0,0),(-1,-1), 0.5, stg_clr2),
        ('LINEBELOW',   (0,0),(-1,-2), 0.3, colors.HexColor('#E0E0E0')),
        ('TOPPADDING',  (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING', (0,0),(-1,-1), 10), ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',      (0,0),(-1,-1), 'MIDDLE'),
    ]
    stg_blk.setStyle(TableStyle(stg_st))

    # ⑥ 보유자 대응 블록 (항상 표시)
    if c > m200:
        take_profit = f'MA50(${m50:.2f})~MA200(${m200:.2f}) 구간에서 주춤거리면 일부 수익을 실현하고 현금을 확보하세요'
    else:
        take_profit = f'MA20(${m20:.2f}) 근처에서 반등이 막히면 일부 수익을 실현하고 현금을 확보하세요'
    danger_line = f'${stop_price:.2f}(MA20 -3%) 아래로 종가가 내려가면 미련 없이 비중을 줄이세요'

    hold_blk = Table([
        [Paragraph('[보유자 대응]  이미 가지고 있다면?', s('hsh', 8, BLUE, TA_LEFT, bold=True))],
        [Paragraph('"손절선을 지키면서 수익을 관리하세요."', s('hq', 8, NAVY, lead=12))],
        [Paragraph(f'<b>익절 라인:</b>  {take_profit}', s('hp', 8, NAVY, lead=12))],
        [Paragraph(f'<b>위험 라인:</b>  {danger_line}', s('hd', 8, RED,  lead=12))],
    ], colWidths=[CW])
    hold_blk.setStyle(TableStyle([
        ('BACKGROUND',  (0,0),(-1,0),  HOLD_HDR),
        ('BACKGROUND',  (0,1),(-1,-1), HOLD_BG),
        ('BOX',         (0,0),(-1,-1), 0.5, BLUE),
        ('LINEBELOW',   (0,0),(-1,-2), 0.3, colors.HexColor('#90CAF9')),
        ('TOPPADDING',  (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING', (0,0),(-1,-1), 10), ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',      (0,0),(-1,-1), 'MIDDLE'),
    ]))

    flowables.append(Spacer(1, 2.5*mm))
    flowables.append(hdl_tbl)
    flowables.append(scan_hdr)
    flowables.append(scan_body)
    flowables.append(Spacer(1, 1.5*mm))
    flowables.append(timing_hdr)
    flowables.append(stg_blk)
    flowables.append(Spacer(1, 1*mm))
    flowables.append(hold_blk)

    # ── 6. 주요 뉴스 (최근 7일) ───────────────────────────────────
    news_list = d.get('news', [])

    news_hdr = Table(
        [[Paragraph('  최근 주요 뉴스 (7일 이내)', s('nh', 8, WHITE, TA_LEFT, bold=True))]],
        colWidths=[CW])
    news_hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), BLUE2),
        ('TOPPADDING',    (0,0),(-1,-1), 4), ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
    ]))
    flowables.append(Spacer(1, 2.5*mm))
    flowables.append(news_hdr)

    if not news_list:
        no_news = Table(
            [[Paragraph('최근 7일 이내 주요 뉴스가 없어요.', s('nn', 8, DGRAY, TA_CENTER))]],
            colWidths=[CW])
        no_news.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), LGRAY),
            ('BOX',           (0,0),(-1,-1), 0.5, MGRAY),
            ('TOPPADDING',    (0,0),(-1,-1), 7), ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ]))
        flowables.append(no_news)
    else:
        news_data = [[Paragraph(t, s('nthh', 7.5, WHITE, TA_CENTER, bold=True))
                      for t in ['날짜', '핵심 내용 요약', '출처']]]
        for i, n in enumerate(news_list):
            news_data.append([
                Paragraph(n.get('date', ''),    s(f'nd{i}', 7.5, DGRAY, TA_CENTER)),
                Paragraph(n.get('summary', ''), s(f'nt{i}', 7.5, NAVY,  TA_LEFT, lead=11)),
                Paragraph(n.get('publisher',''),s(f'np{i}', 7,   DGRAY, TA_CENTER)),
            ])
        news_t = Table(news_data, colWidths=[CW*0.09, CW*0.73, CW*0.18])
        news_sty = [
            ('BACKGROUND', (0,0),(-1,0),  NAVY),
            ('BOX',        (0,0),(-1,-1), 0.5, MGRAY),
            ('INNERGRID',  (0,0),(-1,-1), 0.3, colors.HexColor('#C0D8EE')),
            ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0),(-1,-1), 3.5), ('BOTTOMPADDING', (0,0),(-1,-1), 3.5),
            ('LEFTPADDING',(0,0),(-1,-1), 5),   ('RIGHTPADDING',  (0,0),(-1,-1), 5),
        ]
        for i in range(1, len(news_data)):
            news_sty.append(('BACKGROUND', (0,i),(-1,i), LGRAY if i % 2 == 1 else NEUT_BG))
        news_t.setStyle(TableStyle(news_sty))
        flowables.append(news_t)

    return flowables


# ══════════════════════════════════════════════════════════════════
#  Summary page (all tickers on one page)
# ══════════════════════════════════════════════════════════════════

def build_index_page(output_path):
    """타이밍 단계 + 티어 안내 전용 페이지 — 다크 테마"""
    D_BG     = colors.HexColor('#0D1525')
    D_CARD   = colors.HexColor('#1A2B40')
    D_ROW1   = colors.HexColor('#162235')
    D_ROW2   = colors.HexColor('#1A2B40')
    D_BORDER = colors.HexColor('#2A4060')
    D_LINE   = colors.HexColor('#1F6BB5')
    D_TEXT   = colors.HexColor('#E8F0F8')
    D_SUB    = colors.HexColor('#7FA8C8')

    def _draw_dark_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(D_BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=14 * mm, bottomMargin=14 * mm)
    story = []

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph('타이밍 단계 안내', s('idx_title', 16, D_TEXT, TA_LEFT, bold=True)))
    story.append(HRFlowable(width='100%', thickness=2, color=D_LINE,
                             spaceBefore=3 * mm, spaceAfter=5 * mm))

    timing_rows = [
        (colors.HexColor('#2ECC71'), '● 매수 적기    63점 이상',  'RSI 과매도 회복 + MACD 상승 전환 + 거래량 동반. 적극적 매수 진입 구간'),
        (colors.HexColor('#5DADE2'), '● 매수 검토    50~62점',   '기술적 지표 개선 중. 분할 매수 또는 소량 선진입 고려 가능'),
        (colors.HexColor('#FFA726'), '● 관망            37~49점', '방향성 불명확. 신규 진입보다 보유 포지션 유지 또는 현금 대기'),
        (colors.HexColor('#FF8A65'), '● 비중 축소    24~36점',   '약세 신호 감지. 보유 비중 단계적 축소 또는 손절 검토'),
        (colors.HexColor('#FF5252'), '● 매도 적기    23점 이하', 'MA50 이탈 + MACD 하락 or BB 과열 + 거래량 급증. 적극적 매도·청산 구간'),
    ]
    idx_data = []
    for i, (clr, lbl, desc) in enumerate(timing_rows):
        bg = D_ROW1 if i % 2 == 0 else D_ROW2
        idx_data.append([
            Paragraph(f'<font color="{clr.hexval()}"><b>{lbl}</b></font>',
                      s(f'il{i}', 11, D_TEXT, TA_LEFT)),
            Paragraph(desc, s(f'id{i}', 10, D_SUB, TA_LEFT)),
        ])
    idx_t = Table(idx_data, colWidths=[CW * 0.30, CW * 0.70])
    idx_t.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,0), (-1,-1), [D_ROW1, D_ROW2]),
        ('LEFTPADDING',   (0,0), (-1,-1), 12), ('RIGHTPADDING',  (0,0), (-1,-1), 12),
        ('TOPPADDING',    (0,0), (-1,-1), 9),  ('BOTTOMPADDING', (0,0), (-1,-1), 9),
        ('LINEBELOW',     (0,0), (-1,-2), 0.3, D_BORDER),
        ('BOX',           (0,0), (-1,-1), 0.8, D_BORDER),
    ]))
    story.append(idx_t)
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph('4단계 타이밍 판정 기준', s('stage_title', 16, D_TEXT, TA_LEFT, bold=True)))
    story.append(HRFlowable(width='100%', thickness=2, color=D_LINE,
                             spaceBefore=3 * mm, spaceAfter=5 * mm))

    stage_rows = [
        ('#FF6F00', '1차 진입',  'RSI < 35 + 3일 기울기 반등',
         '과매도 탈출 초기 신호. 전체 예산 10~15% 소액 분할 진입'),
        ('#00C853', '매수 적기', 'MA20 돌파 + MACD 골든크로스 + 거래량 1.2배 이상',
         '추세 전환 확인. 전체 예산 30~50%까지 비중 확대'),
        ('#E53935', '매도 시작', 'MA200/BB상단 근접 OR MA20 이탈 OR 약세 다이버전스',
         '수익 30~50% 현금화. 약세 다이버전스 발생시 최우선 매도 경고'),
        ('#9E9E9E', '관망',     '위 조건 미충족',
         '진입 조건 대기. 현금 보유가 최선인 구간'),
    ]
    stage_data = []
    for i, (hex_c, badge, cond, desc) in enumerate(stage_rows):
        stage_data.append([
            Paragraph(f'<font color="{hex_c}"><b>{badge}</b></font>',
                      s(f'sl{i}', 11, D_TEXT, TA_LEFT)),
            Paragraph(cond, se(f'sc{i}', 10, D_SUB, TA_LEFT)),
            Paragraph(desc, s(f'sd{i}', 10, D_SUB, TA_LEFT)),
        ])
    stage_t = Table(stage_data, colWidths=[CW * 0.18, CW * 0.38, CW * 0.44])
    stage_t.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,0), (-1,-1), [D_ROW1, D_ROW2, D_ROW1, D_ROW2]),
        ('LEFTPADDING',   (0,0), (-1,-1), 12), ('RIGHTPADDING',  (0,0), (-1,-1), 12),
        ('TOPPADDING',    (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW',     (0,0), (-1,-2), 0.3, D_BORDER),
        ('BOX',           (0,0), (-1,-1), 0.8, D_BORDER),
    ]))
    story.append(stage_t)

    doc.build(story, onFirstPage=_draw_dark_bg, onLaterPages=_draw_dark_bg)


def _stage_reason(d, sk):
    """v2.0 판정 근거 텍스트 생성"""
    rsi  = d['rsi']
    chg  = d.get('change_pct', 0.0)

    def sig(key, default=False):
        return bool(d.get(key, default))

    if sk == 'watch_market':
        return 'QQQ MA200 아래 → 대세 하락장, 전종목 매수 금지'

    if sk == 'entry3':
        parts = []
        if sig('sig_above_ma20_2d'):   parts.append('MA20 2일 연속 위')
        if sig('sig_ma20_slope_pos'):  parts.append('MA20 기울기 양수')
        if sig('sig_macd_above_zero'): parts.append('MACD 0선 위')
        if sig('sig_vol_1p3'):         parts.append('거래량 1.3배↑')
        return '3차: ' + ' + '.join(parts) if parts else '3차 매수 조건 충족'

    if sk == 'entry2':
        parts = []
        if sig('sig_double_bottom'):   parts.append('이중바닥')
        if sig('sig_rsi_3d_up'):       parts.append(f'RSI {rsi:.1f} 3일 상승')
        if sig('sig_macd_golden'):     parts.append('MACD 골든크로스')
        elif sig('sig_macd_hist_3d_up'): parts.append('히스토그램 3일↑')
        if sig('sig_vol_1p2'):         parts.append('거래량 1.2배↑')
        return '2차: ' + ' + '.join(parts) if parts else '2차 매수 조건 충족'

    if sk == 'entry1':
        met = []
        if sig('sig_rsi_le38'):    met.append(f'RSI {rsi:.1f}≤38')
        if sig('sig_adx_le25'):    met.append('ADX≤25')
        if sig('sig_near_bb_low'): met.append('BB하단근접')
        if sig('sig_below_ma20'):  met.append('MA20아래')
        if sig('sig_low_stopped'): met.append('하락멈춤')
        if sig('sig_bounce2pct'):  met.append(f'+{chg:.1f}%반등')
        return f'1차({len(met)}/6): ' + ' + '.join(met)

    # 관망 — 왜 안됐는지
    if not sig('qqq_above_ma200', True):
        return 'QQQ MA200 아래 → 매수 금지'
    if sig('sig_block_rsi50'):
        return f'RSI {rsi:.1f} > 50 → 1차 매수 금지'
    if sig('sig_block_bigdrop'):
        return f'장대음봉 {chg:.1f}% → 매수 금지'
    cond1_count = sum([
        sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_near_bb_low'),
        sig('sig_below_ma20'), sig('sig_low_stopped'), sig('sig_bounce2pct')
    ])
    return f'1차 조건 {cond1_count}/6개 충족 (3개 필요)'


def generate_summary_page(stocks_list, output_path, ai_data=None):
    """판정 요약 테이블 — 다크 테마 리디자인 + Geist 영문"""

    # ══ 팔레트 ══════════════════════════════════════════════════════
    D_BG      = colors.HexColor('#060D18')   # 최심 배경
    D_PANEL   = colors.HexColor('#0A1525')   # 헤더·패널
    D_ROW1    = colors.HexColor('#0D1B2C')   # 홀수 행
    D_ROW2    = colors.HexColor('#111F30')   # 짝수 행
    D_HDR_ROW = colors.HexColor('#081220')   # 컬럼명 행
    D_BORDER  = colors.HexColor('#1A3050')   # 선
    D_ACCENT  = colors.HexColor('#2563EB')   # 파란 강조선
    D_ACCENT2 = colors.HexColor('#1D4ED8')   # 어두운 강조
    D_TEXT    = colors.HexColor('#EEF4FB')   # 기본 텍스트
    D_MID     = colors.HexColor('#A8C4DE')   # 중간 텍스트
    D_SUB     = colors.HexColor('#4E6E8E')   # 흐린 텍스트
    # 판정 색상
    S_GREEN   = colors.HexColor('#34D399')   # 매수 (에메랄드)
    S_ORANGE  = colors.HexColor('#FBBF24')   # 진입 (앰버)
    S_RED     = colors.HexColor('#F87171')   # 매도 (코럴)
    S_GRAY    = colors.HexColor('#64748B')   # 관망
    # 판정 배지 배경
    BADGE_G   = colors.HexColor('#052E16')   # 매수 배지 bg
    BADGE_G_B = colors.HexColor('#166534')   # 매수 배지 border
    BADGE_O   = colors.HexColor('#292524')   # 진입 배지 bg
    BADGE_O_B = colors.HexColor('#92400E')   # 진입 배지 border
    BADGE_R   = colors.HexColor('#2A0A0A')   # 매도 배지 bg
    BADGE_R_B = colors.HexColor('#7F1D1D')   # 매도 배지 border
    BADGE_S   = colors.HexColor('#0D1B2C')   # 관망 배지 bg
    BADGE_S_B = colors.HexColor('#1E3A5F')   # 관망 배지 border

    def _draw_dark_bg(canvas, doc):
        canvas.saveState()
        # 배경
        canvas.setFillColor(D_BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # 상단 강조 줄 (4px)
        canvas.setFillColor(D_ACCENT)
        canvas.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)
        canvas.restoreState()

    def _badge_stage(sk, lbl):
        """판정 배지 — 색상 박스 안에 텍스트"""
        clr = (S_GREEN if sk == 'buy'
               else S_ORANGE if sk == 'entry'
               else S_RED    if sk in ('sell', 'sell_div')
               else S_GRAY)
        return Paragraph(f'<b>{lbl}</b>',
                         s(f'badge_{sk}', 8, clr, TA_CENTER, bold=True))

    def _badge_bg(sk):
        return (BADGE_G if sk == 'buy'
                else BADGE_O if sk == 'entry'
                else BADGE_R if sk in ('sell', 'sell_div')
                else BADGE_S)

    today_str = datetime.date.today().strftime('%Y년 %m월 %d일')

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=12 * mm, bottomMargin=8 * mm)
    story = []

    # ── 사전 계산
    scored = []
    for d in stocks_list:
        _, _, _, _, _, _, total = auto_score(d)
        sk, lbl, _ = trading_stage(d)
        scored.append((d, total, sk, lbl))

    # ══ 헤더 블록 ══════════════════════════════════════════════════
    hdr = Table([[
        Paragraph('타이밍 판정 요약',
                  s('smh1', 20, D_TEXT, TA_LEFT, bold=True)),
        Paragraph(f'{today_str}  |  기술적  분석',
                  s('smh2', 8, D_SUB, TA_RIGHT)),
    ]], colWidths=[CW * 0.58, CW * 0.42])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), D_PANEL),
        ('TOPPADDING',   (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 14),
        ('LEFTPADDING',  (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW',    (0, 0), (-1, -1), 2.5, D_ACCENT),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 5 * mm))

    # ══ 판정 요약 테이블 ════════════════════════════════════════════
    # 컬럼 너비: 티커 | 판정 | RSI | rsi_s3 | near_high | h_down | 근거
    COL_W = [CW*0.09, CW*0.11, CW*0.07, CW*0.08, CW*0.10, CW*0.08, CW*0.47]

    # 컬럼 헤더 행
    tbl_hdr = [
        Paragraph('티커',      s('th0', 7.5, D_MID, TA_CENTER, bold=True)),
        Paragraph('판정',      s('th1', 7.5, D_MID, TA_CENTER, bold=True)),
        Paragraph('RSI',       se('th2', 7.5, D_MID, TA_CENTER, bold=True)),
        Paragraph('rsi_s3',    se('th3', 7.5, D_MID, TA_CENTER, bold=True)),
        Paragraph('near_high', se('th4', 7.5, D_MID, TA_CENTER, bold=True)),
        Paragraph('h_down',    se('th5', 7.5, D_MID, TA_CENTER, bold=True)),
        Paragraph('근거',      s('th6', 7.5, D_MID, TA_LEFT,   bold=True)),
    ]
    tbl_rows = [tbl_hdr]
    row_metas = []   # (row_bg, badge_bg)

    for idx, (d, total, sk, lbl) in enumerate(scored):
        c         = d['close']
        rsi       = d['rsi']
        rsi_s3    = d.get('rsi_slope3', 0.0)
        high_52w  = d.get('high_52w', c * 1.3)
        near_high = c >= high_52w * 0.82
        h_down    = c <= high_52w * 0.80
        reason    = _stage_reason(d, sk)

        s3_clr = S_GREEN if rsi_s3 > 0 else S_RED
        s3_str = f'+{rsi_s3:.2f}' if rsi_s3 >= 0 else f'{rsi_s3:.2f}'

        # RSI 색상: 과매도/과매수 구분
        rsi_clr = (S_RED    if rsi >= 70
                   else S_GREEN  if rsi <= 35
                   else D_TEXT)

        nh_str = 'True'   if near_high else 'False'
        hd_str = 'True'   if h_down    else 'False'
        nh_clr = S_RED    if near_high else D_SUB
        hd_clr = S_ORANGE if h_down    else D_SUB

        row_bg   = D_ROW1 if idx % 2 == 0 else D_ROW2
        badge_bg = _badge_bg(sk)

        tbl_rows.append([
            Paragraph(f'<b>{d["ticker"]}</b>',
                      se(f'stk{idx}', 10, D_TEXT, TA_CENTER, bold=True)),
            _badge_stage(sk, lbl),
            Paragraph(f'{rsi:.1f}',
                      se(f'srsi{idx}', 9, rsi_clr, TA_CENTER, bold=(rsi<=35 or rsi>=70))),
            Paragraph(s3_str,
                      se(f'ss3{idx}',  9, s3_clr, TA_CENTER)),
            Paragraph(nh_str,
                      se(f'snh{idx}',  8, nh_clr, TA_CENTER, bold=near_high)),
            Paragraph(hd_str,
                      se(f'shd{idx}',  8, hd_clr, TA_CENTER, bold=h_down)),
            Paragraph(reason,
                      s(f'sreason{idx}', 7.5, D_MID, lead=12)),
        ])
        row_metas.append((row_bg, badge_bg))

    main_tbl = Table(tbl_rows, colWidths=COL_W)
    style_cmds = [
        # 외곽선
        ('BOX',           (0, 0), (-1, -1), 1.0, D_BORDER),
        # 컬럼 구분선
        ('LINEBELOW',     (0, 0), (-1, -1), 0.3, D_BORDER),
        ('LINEBEFORE',    (1, 0), (-1, -1), 0.3, D_BORDER),
        # 헤더 행
        ('BACKGROUND',    (0, 0), (-1,  0), D_HDR_ROW),
        ('LINEBELOW',     (0, 0), (-1,  0), 1.5, D_ACCENT),
        # 여백
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        # 정렬
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN',         (6, 0), (6,  -1), 'LEFT'),
        ('LEFTPADDING',   (6, 0), (6,  -1), 10),
    ]
    for i, (rbg, bbg) in enumerate(row_metas, start=1):
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), rbg))
        style_cmds.append(('BACKGROUND', (1, i), (1,  i), bbg))
    main_tbl.setStyle(TableStyle(style_cmds))
    story.append(main_tbl)
    story.append(Spacer(1, 7 * mm))

    # ══ 판정 조건 기준 테이블 ═══════════════════════════════════════
    # 섹션 레이블
    cond_label = Table([[
        Paragraph('판정 조건 기준',
                  s('cond_ttl', 9, D_MID, TA_LEFT, bold=True)),
        Paragraph('타이밍 판단에 사용된 기술적 조건 요약',
                  s('cond_sub', 7.5, D_SUB, TA_RIGHT)),
    ]], colWidths=[CW * 0.45, CW * 0.55])
    cond_label.setStyle(TableStyle([
        ('LINEBELOW', (0,0),(-1,-1), 0.8, D_ACCENT2),
        ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ('TOPPADDING',(0,0),(-1,-1), 0),
        ('LEFTPADDING',(0,0),(-1,-1), 2),
        ('RIGHTPADDING',(0,0),(-1,-1), 2),
    ]))
    story.append(cond_label)
    story.append(Spacer(1, 3 * mm))

    # 조건 정의: (라벨, 텍스트색, 배지배경, 조건 설명)
    stage_defs = [
        ('매수 적기', S_GREEN,  BADGE_G,
         '다음 중 2가지 이상 충족  +  양봉 마감  +  RSI < 75\n'
         '① MA20 돌파    ② MACD 골든크로스    ③ 거래량 평균 이상'),
        ('1차 진입',  S_ORANGE, BADGE_O,
         'A.  RSI < 35  +  RSI 3일 기울기 양전환  +  하락 멈춤\n'
         'B.  RSI < 40  +  52주 고점 -20% 이상  +  하락 둔화  +  하락 멈춤\n'
         'C.  RSI < 30  +  급락 아님 (rsi_s3 >= -2)  +  하락 멈춤'),
        ('매도 시작', S_RED,    BADGE_R,
         '전제:  고점 대비 -20% 이내  +  RSI >= 45 (과매도 제외)\n'
         'A.  MA200 위 5% 이내  +  RSI 기울기 음수\n'
         'B.  BB 상단 3% 이내  +  음봉 마감\n'
         'C.  고점권(82%)에서 MA20 이탈  +  RSI 5일 급락'),
        ('매도 주의', S_RED,    BADGE_R,
         '약세 다이버전스 (RSI 하락 + 주가 상승)  +  52주 고점 82% 이상 (near_high = True)'),
        ('관망',     S_GRAY,   BADGE_S,
         '위 조건 미충족  —  신호 대기 구간.  현금 보유가 최선인 구간'),
    ]

    LBL_W = CW * 0.13
    TXT_W = CW * 0.87
    ref_rows  = []
    ref_metas = []

    for lbl, clr, bg, cond_txt in stage_defs:
        ref_rows.append([
            Paragraph(f'<b>{lbl}</b>',
                      s(f'rlbl_{lbl}', 7.5, clr, TA_CENTER, bold=True)),
            Paragraph(cond_txt,
                      s(f'rcond_{lbl}', 7, D_MID, lead=11.5)),
        ])
        ref_metas.append(bg)

    ref_tbl = Table(ref_rows, colWidths=[LBL_W, TXT_W])
    ref_style_cmds = [
        ('BOX',           (0, 0), (-1, -1), 0.8, D_BORDER),
        ('LINEBELOW',     (0, 0), (-1, -2), 0.3, D_BORDER),
        ('LINEBEFORE',    (1, 0), (1,  -1), 0.6, D_BORDER),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (0,  -1), 5),
        ('RIGHTPADDING',  (0, 0), (0,  -1), 5),
        ('LEFTPADDING',   (1, 0), (1,  -1), 10),
        ('RIGHTPADDING',  (1, 0), (1,  -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (0,  -1), 'CENTER'),
    ]
    for i, bg in enumerate(ref_metas):
        row_bg = D_ROW1 if i % 2 == 0 else D_ROW2
        ref_style_cmds.append(('BACKGROUND', (0, i), (-1, i), row_bg))
        ref_style_cmds.append(('BACKGROUND', (0, i), (0,  i), bg))
    ref_tbl.setStyle(TableStyle(ref_style_cmds))
    story.append(ref_tbl)
    story.append(Spacer(1, 5 * mm))

    # ── 푸터
    story.append(HRFlowable(width='100%', thickness=0.4,
                             color=D_BORDER, spaceBefore=2 * mm, spaceAfter=2 * mm))
    story.append(Paragraph(
        '본 보고서는 AI 기반 자동 기술적 분석으로, 투자 권유가 아닙니다.',
        s('smfoot', 6.5, D_SUB, TA_CENTER)))
    story.append(Paragraph(
        'Data: Yahoo Finance (yfinance)  |  AI Chart Analyst 2026',
        se('smfooten', 6.5, D_SUB, TA_CENTER)))

    doc.build(story, onFirstPage=_draw_dark_bg, onLaterPages=_draw_dark_bg)
    return output_path


# ══════════════════════════════════════════════════════════════════
#  Card-style layout (v2)
# ══════════════════════════════════════════════════════════════════

def build_pdf_card(d, chart_path, output_path):
    """카드형 종목 분석 페이지 (스크린샷 스타일)"""

    a_sc, b_sc, c_sc, d_sc, e_sc, f_sc, total = auto_score(d)
    op_label, op_color = opinion_label(total)
    stage_key, stage_lbl, stage_clr = trading_stage(d)
    stage_display_clr = DGRAY if stage_clr == MGRAY else stage_clr

    # ── 주요 값 ───────────────────────────────────────────────────
    c    = d['close'];  chg  = d['change_pct']
    m20  = d['ma20'];   m50  = d['ma50'];   m200 = d['ma200']
    rsi  = d['rsi'];    rsi_slope = d.get('rsi_slope', 0)
    macd_v = d['macd']; macd_s = d['macd_signal']
    bb_u = d['bb_upper']; bb_l = d['bb_lower']
    bb_range = bb_u - bb_l
    bb_pct   = (c - bb_l) / bb_range * 100 if bb_range > 0 else 50
    adx  = d.get('adx', 20)
    pdi  = d.get('plus_di', 25);  ndi = d.get('minus_di', 25)
    h52  = d['high_52w'];  l52  = d['low_52w']
    stop_price  = m20 * 0.97
    hist_slope  = d.get('macd_hist_slope', 0)
    vol  = d.get('volume', 0);  avg_vol = max(d.get('avg_volume', 1), 1)

    # 52주 범위 내 현재 위치 (0~1)
    range_52 = max(h52 - l52, 0.01)
    pos_pct  = max(0.0, min(1.0, (c - l52) / range_52))

    chg_clr  = GREEN if chg >= 0 else RED
    chg_sign = '+' if chg >= 0 else ''

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=9 * mm, bottomMargin=8 * mm)
    story = []

    # ── 1. 종목 헤더 ─────────────────────────────────────────────
    hdr_tbl = Table([
        [Paragraph(f'<font face="{EFB}">{d["ticker"]}</font>  {d["company"]}',
                   se('hd_l', 13, NAVY, TA_LEFT, semi=True)),
         Paragraph(f'${c:.2f}',
                   se('hd_r', 18, NAVY, TA_RIGHT, bold=True))],
        [Paragraph(f'{d["exchange"]}  |  <font face="{KF}">{d["sector"]}</font>  |  '
                   f'{datetime.date.today().strftime("%b %d, %Y")}',
                   se('hd_sub', 7.5, DGRAY, TA_LEFT)),
         Paragraph(f'{chg_sign}{chg:.2f}%',
                   se('hd_chg', 10, chg_clr, TA_RIGHT, bold=True))],
    ], colWidths=[CW * 0.65, CW * 0.35])
    hdr_tbl.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 1),
        ('BOTTOMPADDING',(0,0),(-1,-1), 1),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── 3. 52주 범위 바 ──────────────────────────────────────────
    BAR_N   = 30
    bar_col = CW / BAR_N
    marker  = max(0, min(BAR_N - 1, int(pos_pct * BAR_N)))
    FILLED  = colors.HexColor('#1A4A8A')
    MARKER  = colors.HexColor('#C0392B')
    EMPTY   = colors.HexColor('#D4E6F1')

    bar_row   = [''] * BAR_N
    bar_tbl   = Table([bar_row], colWidths=[bar_col] * BAR_N)
    bar_style = [
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
        ('RIGHTPADDING',  (0,0),(-1,-1), 0),
        ('GRID',          (0,0),(-1,-1), 0.3, colors.HexColor('#F0F0F0')),
    ]
    for i in range(BAR_N):
        bg = FILLED if i < marker else (MARKER if i == marker else EMPTY)
        bar_style.append(('BACKGROUND', (i,0),(i,0), bg))
    bar_tbl.setStyle(TableStyle(bar_style))

    lbl_tbl = Table([[
        Paragraph(f'52주 저점  ${l52:.2f}', s('bl1', 7, DGRAY, TA_LEFT)),
        Paragraph(f'현재  ${c:.2f}',         s('bl2', 7, chg_clr, TA_CENTER)),
        Paragraph(f'52주 고점  ${h52:.2f}', s('bl3', 7, DGRAY, TA_RIGHT)),
    ]], colWidths=[CW/3]*3)
    lbl_tbl.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 1),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]))
    story.append(bar_tbl)
    story.append(lbl_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── 4. 종합 판정 박스 ─────────────────────────────────────────
    _sum_bg = {'buy': colors.HexColor('#E8F5E9'),
               'entry': colors.HexColor('#FFF3E0'),
               'sell': colors.HexColor('#FDEAEA'),
               'sell_div': colors.HexColor('#FDEAEA')}.get(stage_key, LGRAY)
    _sum_txt = {
        'buy':      '매수 적기 — MA20 돌파 확인. 분할 매수 시작 권장',
        'entry':    '1차 진입 — 과매도 탈출 신호. 소액 분할 진입 타이밍',
        'sell':     '매도 시작 — 저항선 도달. 보유자 수익 일부 실현 권장',
        'sell_div': '매도 주의 — 약세 다이버전스 감지. 신규 진입 금지',
        'watch':    '관망 — 아직 진입 신호 없음. 현금 보유 유지',
    }.get(stage_key, '관망 — 신호 대기 중')

    sum_box = Table([
        [Paragraph(f'종합 판정  {total}/85점',
                   s('sb_l', 8, DGRAY, TA_LEFT, bold=True)),
         Paragraph(f'<b>{stage_lbl}</b>',
                   s('sb_r', 10, stage_display_clr, TA_RIGHT, bold=True))],
        [Paragraph(_sum_txt, s('sb_d', 8, NAVY, TA_LEFT)),
         Paragraph('', s('sb_e', 8))],
    ], colWidths=[CW * 0.70, CW * 0.30])
    sum_box.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), _sum_bg),
        ('SPAN',         (0,1),(1,1)),
        ('BOX',          (0,0),(-1,-1), 1.2, stage_display_clr),
        ('TOPPADDING',   (0,0),(-1,-1), 5),
        ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(sum_box)
    story.append(Spacer(1, 3 * mm))

    # ── 4-b. 차트 ────────────────────────────────────────────────
    if chart_path and os.path.exists(chart_path):
        story.append(Image(chart_path, width=CW, height=105 * mm))
    story.append(Spacer(1, 3 * mm))

    # ── 5. 메트릭 카드 (2행 × 3열) ────────────────────────────────
    CARD_BDR = colors.HexColor('#D4E6F1')
    CARD_BG  = WHITE
    cw3 = (CW - 4 * mm) / 3   # 카드 1개 너비 (간격 2mm × 2 포함)

    def _dot(clr):
        """컬러 사각 표시 (HYGothic 안전 문자)"""
        hex_str = clr.hexval() if hasattr(clr, 'hexval') else '#7BAED6'
        return f'<font color="{hex_str}"><b> </b></font>'

    def metric_card(name, num_str, dir_str, desc, val_clr=NAVY, dot_clr=None):
        """
        name     : 카드 제목 (한글, HYGothic)
        num_str  : 숫자 부분 (영문/숫자, Inter bold)
        dir_str  : 방향 텍스트 (한글, HYGothic) — 숫자 뒤에 붙음
        desc     : 설명 한줄 (한글, HYGothic small)
        """
        dc = dot_clr or MGRAY
        hex_dc = dc.hexval() if hasattr(dc, 'hexval') else '#7BAED6'
        # 값 행: 숫자(Inter bold) + 방향(HYGothic) 분리해서 나란히
        val_row_content = (
            f'<font name="{EFB}" size="13">{num_str}</font>'
            + (f' <font name="{KF}" size="9">{dir_str}</font>' if dir_str else '')
        )
        rows = [
            [Paragraph(f'<font color="{hex_dc}">|</font> {name}',
                       s('cn', 7, DGRAY, TA_LEFT))],
            [Paragraph(val_row_content,
                       ParagraphStyle('cv_mix', fontName=KF, fontSize=13,
                                      textColor=val_clr, leading=16, spaceAfter=0))],
            [Paragraph(desc, s('cd', 6.5, DGRAY, TA_LEFT, lead=9))],
        ]
        t = Table(rows, colWidths=[cw3])
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), CARD_BG),
            ('BOX',          (0,0),(-1,-1), 0.6, CARD_BDR),
            ('TOPPADDING',   (0,0),(-1,-1), 6),
            ('BOTTOMPADDING',(0,0),(-1,-1), 6),
            ('LEFTPADDING',  (0,0),(-1,-1), 8),
            ('RIGHTPADDING', (0,0),(-1,-1), 5),
        ]))
        return t

    # RSI 카드
    rsi_dir  = '하락 중' if rsi_slope < -0.5 else ('상승 중' if rsi_slope > 0.5 else '')
    rsi_clr  = RED if rsi < 30 else (colors.HexColor('#E67E22') if rsi > 70 else NAVY)
    rsi_dot  = RED if rsi < 30 or rsi > 70 else MGRAY
    rsi_desc = ('과매도 구간. 반등 가능성 주시' if rsi < 30 else
                '과매수 구간. 추격 매수 주의' if rsi > 70 else
                '하락 압력 남아있음. 30 이하면 과매도' if rsi_slope < -0.5 else
                '회복 중. 방향 전환 주시')

    # MACD 카드
    hist_val = macd_v - macd_s
    macd_dir = '하락 중' if hist_slope < -0.02 else ('상승 중' if hist_slope > 0.02 else '')
    macd_clr = GREEN if macd_v > macd_s else RED
    macd_dot = GREEN if macd_v > macd_s else RED
    macd_desc= ('골든크로스. 상승 모멘텀 확인' if macd_v > macd_s and hist_slope > 0 else
                '아직 하락 흐름. 반등 신호 아님' if macd_v < macd_s and hist_slope < 0 else
                '방향 전환 탐색 중')

    # MA200 카드
    ma200_clr  = GREEN if c > m200 else RED
    ma200_dot  = GREEN if c > m200 else RED
    ma200_dir  = '상향' if c > m200 else '이탈'
    ma200_desc = ('현재가 위. 장기 상승 추세 유지' if c > m200 else
                  '현재가 아래. 회복해야 안심')

    # 볼린저밴드 카드
    bb_pct_v = min(100, max(0, bb_pct))
    bb_clr   = RED if bb_pct_v > 80 else (GREEN if bb_pct_v < 20 else DGRAY)
    bb_dot   = RED if bb_pct_v > 80 else (GREEN if bb_pct_v < 20 else MGRAY)
    bb_dir   = '과열' if bb_pct_v > 80 else ('과매도' if bb_pct_v < 20 else '')
    bb_desc  = ('상단 과열. 조정 주의' if bb_pct_v > 80 else
                '하단 과매도. 반등 가능성' if bb_pct_v < 20 else
                '방향 탐색. 관망 구간')

    # MA20/MA50 카드
    ma_clr   = GREEN if c > m20 else RED
    ma_dot   = GREEN if c > m20 else RED
    ma_dir   = '위' if c > m20 else '아래'
    ma_desc  = ('지지선. 이 위로 올라서야 반등' if c < m20 else
                'MA20 위 안착. 상승 추세 유지')

    # ADX 카드
    adx_clr   = GREEN if adx > 25 else DGRAY
    adx_dot   = GREEN if adx > 25 else MGRAY
    adx_trend = '추세 강함' if adx > 25 else '추세 없음'
    adx_desc  = ('강한 추세 진행 중' if adx > 25 else
                 '방향성 약함. RSI/BB로 판단')

    c1 = metric_card('RSI',         f'{rsi:.1f}',          rsi_dir,   rsi_desc,  rsi_clr,  rsi_dot)
    c2 = metric_card('MACD',        f'{hist_val:+.2f}',    macd_dir,  macd_desc, macd_clr, macd_dot)
    c3 = metric_card('MA200',       f'${m200:.2f}',        ma200_dir, ma200_desc,ma200_clr,ma200_dot)
    c4 = metric_card('볼린저밴드',  f'{bb_pct_v:.0f}%',    bb_dir,    bb_desc,   bb_clr,   bb_dot)
    c5 = metric_card('MA20 / MA50', f'${m20:.0f}~${m50:.0f}', ma_dir, ma_desc,   ma_clr,   ma_dot)
    c6 = metric_card('ADX',         f'{adx:.0f}',          adx_trend, adx_desc,  adx_clr,  adx_dot)

    GAP = 1.5 * mm
    cards_tbl = Table(
        [[c1, c2, c3],
         [c4, c5, c6]],
        colWidths=[cw3] * 3)
    cards_tbl.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), GAP),
        ('RIGHTPADDING', (0,0),(-1,-1), GAP),
        ('TOPPADDING',   (0,0),(-1,-1), GAP),
        ('BOTTOMPADDING',(0,0),(-1,-1), GAP),
        ('VALIGN',       (0,0),(-1,-1), 'TOP'),
    ]))
    story.append(cards_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── 6. 지금 어떻게 할까? (친근한 어조) ──────────────────────
    _act_title = {
        'buy':      '지금이 좋은 타이밍이에요',
        'entry':    '슬슬 들어가볼 만해요',
        'sell':     '수익 좀 챙겨도 좋아요',
        'sell_div': '잠깐, 조심해야 해요',
        'watch':    '지금은 기다리는 게 맞아요',
    }.get(stage_key, '지금은 기다리는 게 맞아요')

    _act_sub = {
        'buy':      '매수 신호가 나왔어요. 분할 매수 시작해볼게요.',
        'entry':    '과매도 탈출 신호가 보여요. 소량 분할 진입해보세요.',
        'sell':     '저항선 근처예요. 보유 중이라면 일부 수익 실현 고려해보세요.',
        'sell_div': '약세 신호가 감지됐어요. 신규 진입은 잠시 미뤄요.',
        'watch':    '아직 진입 신호가 안 왔어요. 서두르지 않아도 됩니다.',
    }.get(stage_key, '아직 진입 신호가 안 왔어요. 서두르지 않아도 됩니다.')

    if c < m20:
        entry_friendly = f'MA20(${m20:.2f}) 위로 올라서거나, RSI가 30 이하로 떨어질 때'
    else:
        entry_friendly = f'MA20(${m20:.2f}) 위에서 버텨주는지 확인 후 추가 진입해요'

    vol_note2    = '거래량까지 늘어날 때' if vol < avg_vol else '거래량도 받쳐줄 때'
    buy_friendly  = f'MACD가 위로 꺾이고 {vol_note2} 진입하면 더 안전해요'
    stop_friendly = f'${stop_price:.2f} 아래로 내려가면 미련 없이 일부 정리하세요'

    ACT_BG   = colors.HexColor('#F8FBFF')
    ACT_HDR  = colors.HexColor('#F0F2F5')
    IND_BLUE = colors.HexColor('#4A90D9')
    IND_GRN  = colors.HexColor('#27AE60')
    IND_RED  = colors.HexColor('#E74C3C')
    IND_W    = 3.5 * mm
    LBL_W    = CW * 0.29
    DESC_W   = CW - IND_W - LBL_W

    # 단일 플랫 테이블 (중첩 없음)
    act_tbl = Table([
        [Paragraph('', s('_ai0', 6)),
         Paragraph(f'<b>{_act_title}</b>', s('_aht', 10, NAVY, TA_LEFT, bold=True)),
         Paragraph(_act_sub, s('_ahs', 8, DGRAY, TA_LEFT))],
        [Paragraph('', s('_ai1', 6)),
         Paragraph('<b>이럴 때 들어가세요</b>', s('_al1', 8, NAVY, TA_LEFT, bold=True)),
         Paragraph(entry_friendly, s('_ad1', 7.5, DGRAY, TA_LEFT))],
        [Paragraph('', s('_ai2', 6)),
         Paragraph('<b>더 확신이 서려면</b>', s('_al2', 8, NAVY, TA_LEFT, bold=True)),
         Paragraph(buy_friendly, s('_ad2', 7.5, DGRAY, TA_LEFT))],
        [Paragraph('', s('_ai3', 6)),
         Paragraph('<b>이미 갖고 있다면</b>', s('_al3', 8, RED, TA_LEFT, bold=True)),
         Paragraph(stop_friendly, s('_ad3', 7.5, RED, TA_LEFT))],
    ], colWidths=[IND_W, LBL_W, DESC_W])
    act_tbl.setStyle(TableStyle([
        ('BOX',           (0,0),(-1,-1), 0.6, CARD_BDR),
        # 헤더 행 배경
        ('BACKGROUND',    (0,0),(-1,0),  ACT_HDR),
        # 데이터 행 배경
        ('BACKGROUND',    (1,1),(-1,-1), ACT_BG),
        # 인디케이터 색상
        ('BACKGROUND',    (0,1),(0,1),   IND_BLUE),
        ('BACKGROUND',    (0,2),(0,2),   IND_GRN),
        ('BACKGROUND',    (0,3),(0,3),   IND_RED),
        # 구분선
        ('LINEBELOW',     (0,1),(-1,2),  0.3, colors.HexColor('#EAF2F8')),
        # 패딩 — 헤더 행
        ('TOPPADDING',    (0,0),(-1,0),  10),
        ('BOTTOMPADDING', (0,0),(-1,0),  10),
        # 패딩 — 데이터 행
        ('TOPPADDING',    (0,1),(-1,-1), 8),
        ('BOTTOMPADDING', (0,1),(-1,-1), 8),
        # 좌우 패딩
        ('LEFTPADDING',   (0,0),(0,-1),  0),   # 인디케이터 col
        ('RIGHTPADDING',  (0,0),(0,-1),  0),   # 인디케이터 col: 우측 0
        ('LEFTPADDING',   (1,0),(1,-1),  10),
        ('LEFTPADDING',   (2,0),(2,-1),  6),
        ('RIGHTPADDING',  (1,0),(-1,-1), 10),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(act_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── 푸터 ─────────────────────────────────────────────────────
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f'Data: Yahoo Finance (yfinance)  |  {datetime.date.today().strftime("%Y-%m-%d")}  |  본 자료는 참고용이며 투자 판단의 책임은 본인에게 있습니다.',
        se('ft', 6.5, MGRAY, TA_CENTER)))

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
    build_pdf_card(stock_data, chart_path, output_path)

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
