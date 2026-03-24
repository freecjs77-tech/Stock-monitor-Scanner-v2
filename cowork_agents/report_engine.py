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
    c = d['close']; m20 = d['ma20']; m50 = d['ma50']; m200 = d['ma200']
    rsi = d['rsi']; macd_v = d['macd']; macd_s = d['macd_signal']

    # A. Trend (0-20)
    above = sum([c > m20, c > m50, c > m200])
    aligned = (m20 > m50 > m200) or (m20 < m50 < m200)
    a_score = above * 5 + (3 if aligned and above == 3 else 0) + (2 if above >= 2 else 0)
    a_score = min(a_score, 20)

    # B. Momentum (0-20)
    rsi_score = max(0, min(10, int((rsi - 30) / 4))) if rsi < 70 else 5
    macd_score = 8 if macd_v > macd_s else (5 if macd_v > 0 else 2)
    b_score = min(rsi_score + macd_score, 20)

    # C. Volatility (0-15)
    bb_pct = (c - d['bb_lower']) / (d['bb_upper'] - d['bb_lower']) if (d['bb_upper'] - d['bb_lower']) > 0 else 0.5
    c_score = int(bb_pct * 10) + 3 if 0.15 < bb_pct < 0.85 else int(bb_pct * 8)
    c_score = min(max(c_score, 0), 15)

    # D. Volume (0-15)
    vol_ratio = d.get('volume', 0) / d.get('avg_volume', 1)
    chg = d['change_pct']
    if chg > 0 and vol_ratio > 1.2:
        d_score = 11
    elif chg < 0 and vol_ratio > 1.2:
        d_score = 4
    else:
        d_score = 7
    d_score = min(d_score, 15)

    # E. Pattern/Support (0-15)
    range_52 = d['high_52w'] - d['low_52w']
    pos_52 = (c - d['low_52w']) / range_52 if range_52 > 0 else 0.5
    e_score = int(pos_52 * 12) + 2
    e_score = min(max(e_score, 2), 15)

    total = a_score + b_score + c_score + d_score + e_score
    return a_score, b_score, c_score, d_score, e_score, total


def opinion_label(total):
    if total >= 65: return '강매수', GREEN
    if total >= 50: return '매수',   GREEN
    if total >= 38: return '중립',   ORANGE
    if total >= 25: return '매도',   RED
    return '강매도', RED


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
    a_sc, b_sc, c_sc, d_sc, e_sc, total = auto_score(d)
    op_label, op_color = opinion_label(total)
    signals = auto_signals(d)
    ma200_status = '현재가 상향' if d['close'] > d['ma200'] else '현재가 하향 이탈'

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             leftMargin=M, rightMargin=M,
                             topMargin=9 * mm, bottomMargin=8 * mm)
    story = []

    # Header
    hdr = Table(
        [[Paragraph(d['company'], s('hc', 17, NAVY, TA_LEFT, bold=True)),
          Paragraph(f'{d["ticker"]}  |  {d["exchange"]}  |  {d["sector"]}\n2026년 3월 20일 기준',
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

    # Metrics bar
    lbl_row = [Paragraph(t, s(f'ml{i}', 7, DGRAY, TA_CENTER, bold=True))
               for i, t in enumerate(['종가', '52주 고점', '52주 저점', '200일 MA', '종합점수', '투자의견'])]
    val_row = [Paragraph(v, s(f'mv{i}', 12, c, TA_CENTER, bold=True))
               for i, (v, c) in enumerate([
                   (f'${d["close"]:.2f}',    RED if d['change_pct'] < 0 else GREEN),
                   (f'${d["high_52w"]:.2f}', NAVY),
                   (f'${d["low_52w"]:.2f}',  NAVY),
                   (f'${d["ma200"]:.2f}',    RED if d['close'] < d['ma200'] else GREEN),
                   (f'{total} / 85',         op_color),
                   (op_label,               op_color)])]
    chg_sign = '+' if d['change_pct'] >= 0 else ''
    sub_row = [Paragraph(v, s(f'ms{i}', 7, DGRAY, TA_CENTER))
               for i, v in enumerate([
                   f'전일 대비 {chg_sign}{d["change_pct"]:.2f}%',
                   d.get('high_52w_date', '2025년'),
                   d.get('low_52w_date',  '2026년'),
                   ma200_status, '/85점 만점',
                   d.get('opinion_note', '기술적 신호 기반')])]
    mt = Table([lbl_row, val_row, sub_row], colWidths=[CW / 6] * 6)
    mt.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), LGRAY),
        ('BACKGROUND',    (4,0),(-1,-1), colors.HexColor('#FEF0F0')),
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
        ('C. 변동성 (BB/ATR)',   c_sc, 15, RED if c_sc / 15 < 0.5 else GREEN),
        ('D. 거래량',            d_sc, 15, RED if d_sc / 15 < 0.5 else GREEN),
        ('E. 패턴 / 지지저항',   e_sc, 15, RED if e_sc / 15 < 0.5 else GREEN),
        ('보너스',               0,    5,  MGRAY),
    ]
    sc_rows = [[
        Paragraph('항목',  s('sh0', 7.5, WHITE, TA_LEFT,   bold=True)),
        Paragraph('점수',  s('sh1', 7.5, WHITE, TA_CENTER, bold=True)),
        Paragraph('바',    s('sh2', 7.5, WHITE, TA_CENTER, bold=True)),
    ]]
    for name, sc, mx, bc in sc_items:
        sc_rows.append([
            Paragraph(name, s(f'sn{name}', 7, NAVY)),
            Paragraph(f'{sc}/{mx}', s(f'sv{sc}', 8,
                       RED if sc / mx < 0.5 else GREEN, TA_CENTER, bold=True)),
            score_bar(sc, mx, bc, SC_BAR),
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

    # Strategy table
    entry = d.get('entry_cond',   'MA50 상향 돌파 확인')
    tgt1  = d.get('target1',      f'${d["ma50"]:.2f}  +{(d["ma50"]/d["close"]-1)*100:.1f}%')
    tgt2  = d.get('target2',      f'${d["ma200"]:.2f}  +{(d["ma200"]/d["close"]-1)*100:.1f}%')
    stop  = d.get('stop_loss',    f'${d["ma20"]*0.97:.2f}  -{(1-d["ma20"]*0.97/d["close"])*100:.1f}%')
    rr    = d.get('risk_reward',  '1 : 1.5')
    strat_t = Table(
        [[Paragraph(t, s('trh', 7, WHITE, TA_CENTER, bold=True))
          for t in ['진입 조건', '1차 목표가', '2차 목표가', '손절 기준', '리스크/리워드']],
         [Paragraph(v, s(f'tv{i}', 8, c, TA_CENTER, bold=True))
          for i, (v, c) in enumerate([(entry, NAVY), (tgt1, GREEN), (tgt2, GREEN), (stop, RED), (rr, NAVY)])],
         [Paragraph(v, s('trn', 7, DGRAY, TA_CENTER))
          for v in ['거래량 수반 필수', '단기 저항', 'MA 회복 시', 'MA20 이탈 기준', '반등 시나리오']]],
        colWidths=[CW / 5] * 5)
    strat_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  NAVY),
        ('BACKGROUND',    (0,1),(-1,1),  LGRAY),
        ('BACKGROUND',    (0,2),(-1,2),  WHITE),
        ('BOX',           (0,0),(-1,-1), 0.6, MGRAY),
        ('LINEAFTER',     (0,0),(3,-1),  0.4, MGRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(strat_t)
    story.append(Spacer(1, 3.5 * mm))

    # Opinion
    op_hdr = Table([[Paragraph('  종합 의견', s('oh', 9, WHITE, TA_LEFT, bold=True))]],
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
    c = d['close']; m20 = d['ma20']; m50 = d['ma50']; m200 = d['ma200']
    rsi = d['rsi']; macd_v = d['macd']

    above = sum([c > m20, c > m50, c > m200])
    trend = '완전 정배열 강세' if above == 3 else ('MA50/200 저항 구간' if above == 1 else ('MA200 저항 근접' if above == 2 else '완전 역배열 약세'))

    rsi_desc = '과매수' if rsi >= 70 else ('과매도 접근' if rsi <= 35 else ('중립권 상단' if rsi >= 50 else '중립권 하단'))
    macd_desc = '상승 모멘텀' if macd_v > d['macd_signal'] else '하락 모멘텀 (시그널선 하회)'

    chg_sign = '+' if d['change_pct'] >= 0 else ''
    return (
        f'{d["ticker"]}은 현재 {trend} 상태입니다. '
        f'현재가(${c:.2f})는 MA20(${m20:.2f}) {"상향" if c > m20 else "하향"}하며, '
        f'MA50(${m50:.2f}) / MA200(${m200:.2f})에 대해 {"상향" if c > m50 and c > m200 else "저항 구간에 위치"}합니다.<br/>'
        f'RSI({rsi:.1f})는 {rsi_desc}을 나타내며, MACD({macd_v:.2f})는 {macd_desc}입니다. '
        '당일 ' + chg_sign + f'{d["change_pct"]:.2f}% 변동으로 ' + ("매도 압력이 우세" if d["change_pct"] < -1.5 else ("매수 우위" if d["change_pct"] > 1.5 else "방향성 미결")) + '합니다.<br/>'
        f'종합점수 {total}/85점({op_label})으로, '
        f'{"MA50 돌파 여부가 핵심 분기점입니다" if abs(c - m50) / m50 < 0.08 else "현재 기술적 흐름을 유지하며 추이를 관찰하십시오"}. '
        f'손절은 MA20(${m20:.2f}) 이탈 시 원칙 적용을 권장합니다.'
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
        _, _, _, _, _, total = auto_score(d)
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
        ('강매수 (65+)', GREEN), ('매수 (50-64)', GREEN),
        ('중립 (38-49)', ORANGE), ('매도 (25-37)', RED), ('강매도 (-24)', RED),
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
        _, _, _, _, _, total = auto_score(d)
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
