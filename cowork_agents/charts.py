"""charts.py -- Chart generation for StockReport v5.2.

Extracted from report_engine.py.
  - make_price_series(d): build price series (real or synthetic) for charting
  - build_chart(d, path): render 4-panel technical analysis chart (PNG)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import datetime

from ta import sma_arr, calc_ta


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
