#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Ticker Backtest — 등록 종목 전체 타이밍 신호 정확도 검증
F-페널티 포함 최신 auto_score() 로직 적용
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import os, datetime, json

# ── 설정 ─────────────────────────────────────────────────────────
TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickers.json")
try:
    with open(TICKERS_FILE) as f:
        _tj = json.load(f)
    TICKERS = _tj if isinstance(_tj, list) else _tj.get("tickers", [])
except Exception:
    TICKERS = ["NVDA", "TSLA", "GOOGL", "VOO", "QQQ", "IONQ", "PLTR", "SCHD"]

PERIOD   = "5y"
FWD_DAYS = [5, 10, 20]
LABELS   = ["매수 적기", "매수 검토", "관망", "비중 축소", "매도 적기"]
OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "cowork_agents", "reports")
os.makedirs(OUT_DIR, exist_ok=True)

COLOR_MAP = {
    "매수 적기": "#00C853", "매수 검토": "#69F0AE",
    "관망":      "#FFB300",
    "비중 축소": "#FF7043", "매도 적기": "#EF5350",
}

# ── 공통 함수 ────────────────────────────────────────────────────
def wilder_rsi(close, period=14):
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_indicators(df):
    close = df["Close"]; vol = df["Volume"]
    df["MA20"]     = close.rolling(20).mean()
    df["MA50"]     = close.rolling(50).mean()
    df["MA200"]    = close.rolling(200).mean()
    df["RSI"]      = wilder_rsi(close)
    ema12          = close.ewm(span=12, adjust=False).mean()
    ema26          = close.ewm(span=26, adjust=False).mean()
    df["MACD"]     = ema12 - ema26
    df["MACD_sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["BB_upper"] = close.rolling(20).mean() + 2 * close.rolling(20).std(ddof=0)
    df["BB_lower"] = close.rolling(20).mean() - 2 * close.rolling(20).std(ddof=0)
    df["AvgVol"]   = vol.rolling(50).mean()
    df["Chg"]      = close.pct_change() * 100
    return df.dropna()


def score_row(row):
    c   = row["Close"]; m20 = row["MA20"]; m50 = row["MA50"]; m200 = row["MA200"]
    rsi = row["RSI"];   mv  = row["MACD"]; ms  = row["MACD_sig"]
    bu  = row["BB_upper"]; bl = row["BB_lower"]
    vol_ = row["Volume"]; avg_v = row["AvgVol"]; chg = row["Chg"]

    above = sum([c > m20, c > m50, c > m200])
    a = min(above*5 + (3 if (m20>m50>m200) and above==3 else 0) + (2 if above>=2 else 0), 20)

    rsi_s  = (2 if rsi>=70 else 5 if rsi>=60 else 8 if rsi>=45 else 9 if rsi>=30 else 4)
    macd_s = (10 if mv>ms and mv>0 else 7 if mv>ms else 4 if mv>0 else 2)
    b = min(rsi_s + macd_s, 20)

    bb_r = bu - bl; bp = (c - bl) / bb_r if bb_r > 0 else 0.5
    c_s = (4 if bp<=0 else 13 if bp<=0.20 else 10 if bp<=0.45 else
           7 if bp<=0.60 else 5 if bp<=0.80 else 3)
    c_s = min(max(c_s, 0), 15)

    vr  = vol_ / max(avg_v, 1)
    d_s = (13 if chg>1.0 and vr>=1.5 else 10 if chg>0 and vr>=1.2 else
           2  if chg<-1.0 and vr>=1.5 else 4 if chg<0 and vr>=1.2 else 7)
    d_s = min(max(d_s, 0), 15)

    nm  = min(abs(c-m20)/max(m20,1), abs(c-m50)/max(m50,1), abs(c-m200)/max(m200,1))
    am  = c > m200
    e_s = (14 if am and nm<0.02 else 11 if am and nm<0.05 else
           8  if am and nm<0.10 else 6 if am else 4 if nm<0.03 else 2)
    e_s = min(max(e_s, 0), 15)

    # F. 매도 압력 페널티 (백테스트 기반)
    f_s = 0
    if c < m50 and mv < ms and mv > 0:  f_s -= 15
    if chg < -1.0 and vr >= 1.5:        f_s -= 8
    if bp >= 0.90:                       f_s -= 8
    elif bp >= 0.85 and rsi >= 65:      f_s -= 5
    f_s = max(f_s, -20)

    return max(0, a + b + c_s + d_s + e_s + f_s)


def timing_label(total):
    if total >= 63: return "매수 적기"
    if total >= 50: return "매수 검토"
    if total >= 37: return "관망"
    if total >= 24: return "비중 축소"
    return "매도 적기"


def buy_tier_row(row):
    """단계별 매수 신호 (0~3차)"""
    c   = row["Close"]; m20 = row["MA20"]; m200 = row["MA200"]
    rsi = row["RSI"];   mv  = row["MACD"]; ms  = row["MACD_sig"]
    vol_ = row["Volume"]; avg_v = row["AvgVol"]; chg = row["Chg"]
    vol_ratio   = vol_ / max(avg_v, 1)
    above_ma200 = c > m200
    macd_bull   = mv > ms
    near_ma20   = abs(c - m20) / max(m20, 1) <= 0.03

    if (above_ma200 and near_ma20 and macd_bull and mv > 0
            and vol_ratio >= 1.3 and chg > 0.5):
        return 3
    if (above_ma200 and 28 <= rsi <= 50 and macd_bull and vol_ratio >= 1.2):
        return 2
    if above_ma200 and rsi <= 40:
        return 1
    return 0


# ── 종목별 백테스트 ──────────────────────────────────────────────
all_results      = {}
all_tier_results = {}
all_dfs          = {}

print(f"종목: {', '.join(TICKERS)}")
print(f"기간: 5년  |  신호: {', '.join(LABELS)}\n")
tickers_valid = []

for ticker in TICKERS:
    print(f"[{ticker}] 다운로드 중...", end=" ", flush=True)
    try:
        raw = yf.download(ticker, period=PERIOD, interval="1d",
                          auto_adjust=True, progress=False)
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        raw = raw[["Open","High","Low","Close","Volume"]].dropna()
        df  = calc_indicators(raw.copy())
    except Exception as e:
        print(f"오류: {e}")
        continue

    df["Score"]  = df.apply(score_row, axis=1)
    df["Signal"] = df["Score"].apply(timing_label)
    df["Tier"]   = df.apply(buy_tier_row, axis=1)
    for n in FWD_DAYS:
        df[f"Fwd{n}"] = df["Close"].shift(-n) / df["Close"] - 1

    results = {}
    for lbl in LABELS:
        sub = df[df["Signal"] == lbl]
        row = {"n": len(sub)}
        for n in FWD_DAYS:
            valid = sub[f"Fwd{n}"].dropna()
            if lbl in ("매수 적기", "매수 검토"):
                hit = (valid > 0).mean() if len(valid) else np.nan
            elif lbl in ("비중 축소", "매도 적기"):
                hit = (valid < 0).mean() if len(valid) else np.nan
            else:
                hit = np.nan
            row[f"hit{n}"] = hit
            row[f"ret{n}"] = valid.mean() if len(valid) else np.nan
        results[lbl] = row

    # tier별 결과 저장
    tier_results = {}
    for t in [1, 2, 3]:
        sub = df[df["Tier"] == t]
        tr = {"n": len(sub)}
        for n in FWD_DAYS:
            valid = sub[f"Fwd{n}"].dropna()
            tr[f"hit{n}"] = (valid > 0).mean() if len(valid) else np.nan
            tr[f"ret{n}"] = valid.mean()        if len(valid) else np.nan
        tier_results[t] = tr
    all_results[ticker] = results
    all_dfs[ticker]     = df
    all_tier_results[ticker] = tier_results

    bnh = df["Close"].iloc[-1] / df["Close"].iloc[0] - 1
    n_days = len(df)
    tier_counts = {t: len(df[df["Tier"]==t]) for t in [1,2,3]}
    print(f"완료 ({n_days}일, BnH {bnh*100:+.0f}%, 1차:{tier_counts[1]} 2차:{tier_counts[2]} 3차:{tier_counts[3]})")
    tickers_valid.append(ticker)

# ── 콘솔 출력 ────────────────────────────────────────────────────
print("\n" + "="*100)
print("  멀티 종목 백테스트 결과  (20일 기준)")
print("="*100)
hdr = f"{'종목':<6}  {'신호':<10}  {'일수':>5}  {'5일 적중':>8}  {'10일 적중':>9}  {'20일 적중':>9}  {'5일 수익':>8}  {'10일 수익':>9}  {'20일 수익':>9}"
print(hdr)
print("-" * 100)

summary_buy  = {n: [] for n in FWD_DAYS}  # 매수 적기 hit rates across tickers
summary_sell = {n: [] for n in FWD_DAYS}  # 매도 적기 hit rates

for ticker in TICKERS:
    if ticker not in all_results:
        continue
    for lbl in LABELS:
        r = all_results[ticker][lbl]
        h = {n: (f"{r[f'hit{n}']*100:.1f}%" if not np.isnan(r.get(f'hit{n}', np.nan)) else " N/A") for n in FWD_DAYS}
        rv = {n: (f"{r[f'ret{n}']*100:+.2f}%" if not np.isnan(r.get(f'ret{n}', np.nan)) else " N/A") for n in FWD_DAYS}
        print(f"{ticker:<6}  {lbl:<10}  {r['n']:>5}  {h[5]:>8}  {h[10]:>9}  {h[20]:>9}  {rv[5]:>8}  {rv[10]:>9}  {rv[20]:>9}")
        if lbl == "매수 적기":
            for n in FWD_DAYS:
                if not np.isnan(r.get(f'hit{n}', np.nan)) and r['n'] >= 5:
                    summary_buy[n].append(r[f'hit{n}'])
        elif lbl == "매도 적기":
            for n in FWD_DAYS:
                if not np.isnan(r.get(f'hit{n}', np.nan)) and r['n'] >= 5:
                    summary_sell[n].append(r[f'hit{n}'])
    print()

# 평균 요약
print("="*100)
print("  전종목 평균 적중률 - 매수 적기: " +
      "  |  ".join(f"{n}일 {np.mean(v)*100:.1f}%" for n, v in summary_buy.items() if v))
print("  전종목 평균 적중률 - 매도 적기: " +
      "  |  ".join(f"{n}일 {np.mean(v)*100:.1f}%" if v else f"{n}일 N/A" for n, v in summary_sell.items()))

# ── 단계별 신호 결과 ──────────────────────────────────────────────
TIER_NAMES = {1: "1차 진입준비", 2: "2차 매수확정", 3: "3차 추세확인"}
print("\n" + "="*90)
print("  단계별 매수 신호 백테스트 결과")
print("="*90)
print(f"{'종목':<6}  {'단계':<12}  {'일수':>5}  {'5일 적중':>8}  {'10일 적중':>9}  {'20일 적중':>9}  {'5일 수익':>8}  {'20일 수익':>9}")
print("-"*90)

tier_hit_agg = {t: {n: [] for n in FWD_DAYS} for t in [1,2,3]}
tier_ret_agg = {t: {n: [] for n in FWD_DAYS} for t in [1,2,3]}

for ticker in tickers_valid:
    for t in [1, 2, 3]:
        tr = all_tier_results[ticker][t]
        if tr["n"] == 0:
            continue
        h = {n: (f"{tr[f'hit{n}']*100:.1f}%" if not np.isnan(tr.get(f'hit{n}', np.nan)) else " N/A") for n in FWD_DAYS}
        rv = {n: (f"{tr[f'ret{n}']*100:+.2f}%" if not np.isnan(tr.get(f'ret{n}', np.nan)) else " N/A") for n in FWD_DAYS}
        print(f"{ticker:<6}  {TIER_NAMES[t]:<12}  {tr['n']:>5}  {h[5]:>8}  {h[10]:>9}  {h[20]:>9}  {rv[5]:>8}  {rv[20]:>9}")
        for n in FWD_DAYS:
            if tr['n'] >= 5 and not np.isnan(tr.get(f'hit{n}', np.nan)):
                tier_hit_agg[t][n].append(tr[f'hit{n}'])
                tier_ret_agg[t][n].append(tr[f'ret{n}'])
    print()

print("-"*90)
print("  [전종목 평균]")
for t in [1, 2, 3]:
    h_avg = "  |  ".join(
        f"{n}일 {np.mean(v)*100:.1f}%" if v else f"{n}일 N/A"
        for n, v in tier_hit_agg[t].items()
    )
    r20 = np.mean(tier_ret_agg[t][20])*100 if tier_ret_agg[t][20] else float('nan')
    print(f"  {TIER_NAMES[t]}: 적중률 {h_avg}  |  20일 평균수익 {r20:+.2f}%")

# ── 시각화 ────────────────────────────────────────────────────────
print("\n차트 생성 중...")
N = len(tickers_valid)
BG = "#0F1117"; PANEL = "#1A1D27"; GRID = "#2A2D3A"; WHITE = "#FFFFFF"; GRAY = "#6B7280"

fig = plt.figure(figsize=(18, 5 + N * 2.2), facecolor=BG)
outer = gridspec.GridSpec(3, 1, figure=fig,
                          height_ratios=[2.5, 2.5, N * 0.95],
                          hspace=0.45, left=0.08, right=0.97,
                          top=0.95, bottom=0.04)

def style_ax(ax, title=""):
    ax.set_facecolor(PANEL)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID);   ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=GRAY, labelsize=8)
    ax.grid(True, color=GRID, lw=0.5, alpha=0.6)
    if title: ax.set_title(title, color=WHITE, fontsize=10, fontweight="bold", pad=8)

# ── (0) 신호 비율 히트맵 (종목 × 신호) ──────────────────────────
ax0 = fig.add_subplot(outer[0])
ax0.set_facecolor(PANEL)
ax0.set_title("종목별 신호 발생 비율 (%)", color=WHITE, fontsize=10, fontweight="bold", pad=8)
ax0.spines["top"].set_visible(False); ax0.spines["right"].set_visible(False)
ax0.spines["left"].set_color(GRID);   ax0.spines["bottom"].set_color(GRID)
matrix_pct = np.zeros((len(tickers_valid), len(LABELS)))
for ti, ticker in enumerate(tickers_valid):
    df = all_dfs[ticker]
    total_days = len(df)
    for li, lbl in enumerate(LABELS):
        matrix_pct[ti, li] = all_results[ticker][lbl]["n"] / total_days * 100

cmap_heat = LinearSegmentedColormap.from_list("bwr", ["#EF5350","#FFB300","#00C853"])
im = ax0.imshow(matrix_pct, cmap=cmap_heat, aspect="auto", vmin=0, vmax=60)
ax0.set_xticks(range(len(LABELS)))
ax0.set_xticklabels(LABELS, color=WHITE, fontsize=9)
ax0.set_yticks(range(len(tickers_valid)))
ax0.set_yticklabels(tickers_valid, color=WHITE, fontsize=9)
for ti in range(len(tickers_valid)):
    for li in range(len(LABELS)):
        ax0.text(li, ti, f"{matrix_pct[ti,li]:.0f}%",
                 ha="center", va="center", fontsize=8.5, color=WHITE, fontweight="bold")
plt.colorbar(im, ax=ax0, shrink=0.85, label="발생 비율(%)").ax.tick_params(colors=GRAY, labelsize=7)

# ── (1) 20일 적중률 히트맵 ──────────────────────────────────────
ax1 = fig.add_subplot(outer[1])
ax1.set_facecolor(PANEL)
ax1.set_title("20일 후 방향 적중률 (%) — 매수/매도 신호만", color=WHITE, fontsize=10, fontweight="bold", pad=8)
ax1.spines["top"].set_visible(False); ax1.spines["right"].set_visible(False)
ax1.spines["left"].set_color(GRID);   ax1.spines["bottom"].set_color(GRID)

eval_labels = ["매수 적기", "매수 검토", "비중 축소", "매도 적기"]
matrix_hit  = np.full((len(tickers_valid), len(eval_labels)), np.nan)
for ti, ticker in enumerate(tickers_valid):
    for li, lbl in enumerate(eval_labels):
        v = all_results[ticker][lbl].get("hit20", np.nan)
        if not np.isnan(v) and all_results[ticker][lbl]["n"] >= 5:
            matrix_hit[ti, li] = v * 100

# NaN → 50 for colormap centering
matrix_display = np.where(np.isnan(matrix_hit), 50, matrix_hit)
cmap_div = LinearSegmentedColormap.from_list("rg", ["#EF5350","#FFB300","#00C853"])
im2 = ax1.imshow(matrix_display, cmap=cmap_div, aspect="auto", vmin=30, vmax=80)
ax1.set_xticks(range(len(eval_labels)))
ax1.set_xticklabels(eval_labels, color=WHITE, fontsize=9)
ax1.set_yticks(range(len(tickers_valid)))
ax1.set_yticklabels(tickers_valid, color=WHITE, fontsize=9)
ax1.axvline(1.5, color=GRAY, lw=1, ls="--", alpha=0.5)
for ti in range(len(tickers_valid)):
    for li in range(len(eval_labels)):
        v = matrix_hit[ti, li]
        txt = f"{v:.0f}%" if not np.isnan(v) else "N/A"
        ax1.text(li, ti, txt, ha="center", va="center",
                 fontsize=8.5, color=WHITE, fontweight="bold")
plt.colorbar(im2, ax=ax1, shrink=0.85, label="적중률(%)").ax.tick_params(colors=GRAY, labelsize=7)
ax1.axvline(1.5, color=GRAY, lw=1.5, ls="--", alpha=0.4)

# ── (2) 종목별 20일 평균 수익률 막대 (신호별) ──────────────────
inner = gridspec.GridSpecFromSubplotSpec(
    1, len(tickers_valid), subplot_spec=outer[2], wspace=0.25)

for ti, ticker in enumerate(tickers_valid):
    ax = fig.add_subplot(inner[ti])
    style_ax(ax, ticker)

    df  = all_dfs[ticker]
    bnh = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100

    rets  = [all_results[ticker][lbl].get("ret20", np.nan) * 100 for lbl in LABELS]
    y_pos = np.arange(len(LABELS))
    colors_b = [COLOR_MAP[l] for l in LABELS]
    bars = ax.barh(y_pos, rets, color=colors_b, alpha=0.75, height=0.6)
    ax.axvline(0, color=GRAY, lw=0.7)
    ax.axvline(bnh / 250 * 20, color="#90CAF9", lw=1.2, ls="--", alpha=0.7,
               label=f"BnH/day")  # approximate daily BnH equivalent over 20 days
    ax.set_yticks(y_pos)
    ax.set_yticklabels(LABELS if ti == 0 else [""] * len(LABELS),
                       color=WHITE, fontsize=7.5)
    ax.set_xlabel("20일 수익(%)", color=GRAY, fontsize=7)
    for i, (bar, r) in enumerate(zip(bars, rets)):
        if not np.isnan(r):
            ax.text(r + (0.1 if r >= 0 else -0.1), i,
                    f"{r:+.1f}%", va="center",
                    ha="left" if r >= 0 else "right",
                    fontsize=6.5, color=WHITE)

fig.suptitle(
    f"멀티 종목 타이밍 신호 백테스트  ({', '.join(tickers_valid)})  |  5년  |  F-페널티 적용",
    color=WHITE, fontsize=13, fontweight="bold", y=0.98)

today_str = datetime.date.today().strftime("%Y%m%d")
out_path  = os.path.join(OUT_DIR, f"Backtest_Multi_{today_str}.png")
fig.savefig(out_path, dpi=130, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"차트 저장: {out_path}")

# ── CSV 저장 ──────────────────────────────────────────────────────
rows_csv = []
for ticker in tickers_valid:
    for lbl in LABELS:
        r = all_results[ticker][lbl]
        rows_csv.append({
            "종목": ticker, "신호": lbl, "일수": r["n"],
            "5일_적중(%)":  round(r["hit5"]*100,  1) if not np.isnan(r.get("hit5",  np.nan)) else None,
            "10일_적중(%)": round(r["hit10"]*100, 1) if not np.isnan(r.get("hit10", np.nan)) else None,
            "20일_적중(%)": round(r["hit20"]*100, 1) if not np.isnan(r.get("hit20", np.nan)) else None,
            "5일_수익(%)":  round(r["ret5"]*100,  2) if not np.isnan(r.get("ret5",  np.nan)) else None,
            "10일_수익(%)": round(r["ret10"]*100, 2) if not np.isnan(r.get("ret10", np.nan)) else None,
            "20일_수익(%)": round(r["ret20"]*100, 2) if not np.isnan(r.get("ret20", np.nan)) else None,
        })
csv_path = os.path.join(OUT_DIR, f"Backtest_Multi_{today_str}.csv")
pd.DataFrame(rows_csv).to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"CSV  저장: {csv_path}")
print("\n완료")
