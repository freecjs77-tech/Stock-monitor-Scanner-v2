#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
백테스트 심층 분석 — 실제 하락 전 선행 지표 패턴 추출
결과를 바탕으로 비중 축소/매도 적기 조건을 재설계
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os, datetime

TICKER  = "GOOGL"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "cowork_agents", "reports")
os.makedirs(OUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────────
def wilder_rsi(close, period=14):
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

raw = yf.download(TICKER, period="5y", interval="1d",
                  auto_adjust=True, progress=False)
raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
raw = raw[["Open","High","Low","Close","Volume"]].dropna()

df = raw.copy()
close = df["Close"]
df["MA20"]        = close.rolling(20).mean()
df["MA50"]        = close.rolling(50).mean()
df["MA200"]       = close.rolling(200).mean()
df["RSI"]         = wilder_rsi(close)
ema12             = close.ewm(span=12, adjust=False).mean()
ema26             = close.ewm(span=26, adjust=False).mean()
df["MACD"]        = ema12 - ema26
df["MACD_sig"]    = df["MACD"].ewm(span=9, adjust=False).mean()
df["BB_upper"]    = close.rolling(20).mean() + 2 * close.rolling(20).std(ddof=0)
df["BB_lower"]    = close.rolling(20).mean() - 2 * close.rolling(20).std(ddof=0)
df["AvgVol"]      = df["Volume"].rolling(50).mean()
df["Chg"]         = close.pct_change() * 100

# 파생 지표
df["BB_pct"]      = (close - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"]).replace(0, np.nan)
df["MA200_gap"]   = (close / df["MA200"] - 1) * 100
df["MACD_bull"]   = (df["MACD"] > df["MACD_sig"]).astype(int)
df["VolRatio"]    = df["Volume"] / df["AvgVol"].replace(0, np.nan)
df["AboveMA200"]  = (close > df["MA200"]).astype(int)
df["RSI_lag3"]    = df["RSI"].shift(3)         # 3일 전 RSI
df["RSI_delta"]   = df["RSI"] - df["RSI_lag3"] # RSI 변화 방향
df["MACD_slope"]  = df["MACD"] - df["MACD"].shift(3)  # MACD 기울기

# 순방향 수익률
for n in [5, 10, 20]:
    df[f"Fwd{n}"] = close.shift(-n) / close - 1

df = df.dropna()
print(f"GOOGL 유효 데이터: {len(df)}일")

# ──────────────────────────────────────────────────────────────────
# 분석 1: 실제 하락 선행 조건 vs 상승 선행 조건
# ──────────────────────────────────────────────────────────────────
DROP_THRESH = -0.05   # 20일 내 -5% 이하 하락
RISE_THRESH =  0.05   # 20일 내 +5% 이상 상승

drop_days = df[df["Fwd20"] < DROP_THRESH]
rise_days = df[df["Fwd20"] > RISE_THRESH]
other     = df[(df["Fwd20"] >= DROP_THRESH) & (df["Fwd20"] <= RISE_THRESH)]

print(f"\n하락 선행일 (20일후 -5%+): {len(drop_days)}일")
print(f"상승 선행일 (20일후 +5%+): {len(rise_days)}일")
print(f"중립:                      {len(other)}일")

metrics = {
    "RSI": "RSI",
    "BB_pct": "BB %B",
    "MA200_gap": "MA200 이격(%)",
    "MACD_bull": "MACD 골든크로스 비율",
    "VolRatio": "거래량 배율",
    "RSI_delta": "RSI 3일 변화",
    "MACD_slope": "MACD 기울기(3일)",
}

print("\n[지표 평균값 비교]")
print(f"{'지표':<22}  {'하락 선행':>12}  {'상승 선행':>12}  {'전체 평균':>12}")
print("-" * 62)
for col, label in metrics.items():
    d_mean = drop_days[col].mean()
    r_mean = rise_days[col].mean()
    a_mean = df[col].mean()
    print(f"{label:<22}  {d_mean:>12.2f}  {r_mean:>12.2f}  {a_mean:>12.2f}")

# ──────────────────────────────────────────────────────────────────
# 분석 2: 조건별 하락 예측력 (비중 축소/매도 신호 후보)
# ──────────────────────────────────────────────────────────────────
print("\n[조건별 20일 후 평균 수익률 및 하락 비율]")
print(f"{'조건':<45}  {'일수':>5}  {'평균수익':>9}  {'하락비율':>9}  {'상승비율':>9}")
print("-" * 85)

conditions = [
    # (설명, boolean series)
    ("RSI >= 70",
     df["RSI"] >= 70),
    ("RSI >= 65",
     df["RSI"] >= 65),
    ("RSI >= 70 + MACD 데드크로스",
     (df["RSI"] >= 70) & (df["MACD_bull"] == 0)),
    ("RSI >= 65 + MACD 데드크로스",
     (df["RSI"] >= 65) & (df["MACD_bull"] == 0)),
    ("RSI >= 65 + RSI 하락(3일 -3p+)",
     (df["RSI"] >= 65) & (df["RSI_delta"] < -3)),
    ("BB%B >= 0.9",
     df["BB_pct"] >= 0.9),
    ("BB%B >= 0.9 + RSI >= 65",
     (df["BB_pct"] >= 0.9) & (df["RSI"] >= 65)),
    ("MA200 이격 >= 20%",
     df["MA200_gap"] >= 20),
    ("MA200 이격 >= 20% + MACD 데드크로스",
     (df["MA200_gap"] >= 20) & (df["MACD_bull"] == 0)),
    ("MA200 이격 >= 25% + MACD 데드크로스",
     (df["MA200_gap"] >= 25) & (df["MACD_bull"] == 0)),
    ("MACD 데드크로스 (제로선 위)",
     (df["MACD_bull"] == 0) & (df["MACD"] > 0)),
    ("MACD 데드크로스 + RSI 하락",
     (df["MACD_bull"] == 0) & (df["RSI_delta"] < -2)),
    ("RSI 70+ + BB0.85+ + MACD 데드",
     (df["RSI"] >= 70) & (df["BB_pct"] >= 0.85) & (df["MACD_bull"] == 0)),
    ("RSI 65+ + MA200갭 15%+ + MACD 데드",
     (df["RSI"] >= 65) & (df["MA200_gap"] >= 15) & (df["MACD_bull"] == 0)),
    ("하락(-1%+) + 거래량 1.5x+",
     (df["Chg"] < -1) & (df["VolRatio"] >= 1.5)),
    ("MA50 아래 + MACD 데드크로스(제로상)",
     (df["Close"] < df["MA50"]) & (df["MACD_bull"] == 0) & (df["MACD"] > 0)),
]

cond_results = []
for label, cond in conditions:
    sub = df[cond]
    if len(sub) < 5:
        continue
    fwd20 = sub["Fwd20"].dropna()
    avg_ret  = fwd20.mean() * 100
    drop_pct = (fwd20 < -0.03).mean() * 100  # 3% 이상 하락
    rise_pct = (fwd20 > 0.03).mean() * 100
    cond_results.append({
        "label": label, "n": len(sub),
        "avg_ret": avg_ret, "drop_pct": drop_pct, "rise_pct": rise_pct
    })
    print(f"{label:<45}  {len(sub):>5}  {avg_ret:>+8.2f}%  {drop_pct:>8.1f}%  {rise_pct:>8.1f}%")

# 가장 하락 예측력 높은 조건 TOP5
print("\n[하락 예측력 TOP 5 조건]")
cond_results.sort(key=lambda x: x["drop_pct"], reverse=True)
for r in cond_results[:5]:
    print(f"  {r['label'][:50]:<50}  하락비율={r['drop_pct']:.1f}%  n={r['n']}")

# 평균 수익률이 가장 낮은 (매도 신호로 유효) TOP5
print("\n[평균 수익률 최저 TOP 5 조건]")
cond_results.sort(key=lambda x: x["avg_ret"])
for r in cond_results[:5]:
    print(f"  {r['label'][:50]:<50}  평균수익={r['avg_ret']:+.2f}%  n={r['n']}")

# ──────────────────────────────────────────────────────────────────
# 분석 3: 시각화
# ──────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 12), facecolor="#0F1117")
gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35,
                        left=0.07, right=0.97, top=0.91, bottom=0.07)

BG    = "#0F1117"; PANEL = "#1A1D27"; GRID  = "#2A2D3A"
WHITE = "#FFFFFF"; GRAY  = "#6B7280"
RED   = "#EF5350"; GREEN = "#66BB6A"; ORANGE = "#FFA726"

def style_ax(ax, title=""):
    ax.set_facecolor(PANEL)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID);   ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=GRAY, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.7)
    if title: ax.set_title(title, color=WHITE, fontsize=9, fontweight="bold", pad=8)

# (0,0) RSI 분포: 하락 선행 vs 상승 선행
ax = fig.add_subplot(gs[0, 0])
style_ax(ax, "RSI 분포: 하락/상승 선행일")
bins = np.linspace(20, 90, 30)
ax.hist(rise_days["RSI"].clip(20, 90), bins=bins, alpha=0.5, color=GREEN,  label="상승 선행 (+5%+)", density=True)
ax.hist(drop_days["RSI"].clip(20, 90), bins=bins, alpha=0.5, color=RED,    label="하락 선행 (-5%+)", density=True)
ax.axvline(65, color=ORANGE, lw=1.2, ls="--", alpha=0.8, label="RSI=65")
ax.axvline(70, color=RED,    lw=1.2, ls="--", alpha=0.8, label="RSI=70")
ax.set_xlabel("RSI", color=GRAY, fontsize=8)
ax.legend(fontsize=7, facecolor=PANEL, labelcolor=WHITE, framealpha=0.7)

# (0,1) BB%B 분포
ax = fig.add_subplot(gs[0, 1])
style_ax(ax, "BB %B 분포")
bins2 = np.linspace(-0.2, 1.2, 30)
ax.hist(rise_days["BB_pct"].clip(-0.2, 1.2), bins=bins2, alpha=0.5, color=GREEN, label="상승 선행", density=True)
ax.hist(drop_days["BB_pct"].clip(-0.2, 1.2), bins=bins2, alpha=0.5, color=RED,   label="하락 선행", density=True)
ax.axvline(0.85, color=ORANGE, lw=1.2, ls="--", alpha=0.8, label="BB%B=0.85")
ax.set_xlabel("BB %B", color=GRAY, fontsize=8)
ax.legend(fontsize=7, facecolor=PANEL, labelcolor=WHITE, framealpha=0.7)

# (0,2) MA200 이격 분포
ax = fig.add_subplot(gs[0, 2])
style_ax(ax, "MA200 이격 분포 (%)")
bins3 = np.linspace(-40, 60, 30)
ax.hist(rise_days["MA200_gap"].clip(-40, 60), bins=bins3, alpha=0.5, color=GREEN, label="상승 선행", density=True)
ax.hist(drop_days["MA200_gap"].clip(-40, 60), bins=bins3, alpha=0.5, color=RED,   label="하락 선행", density=True)
ax.axvline(20, color=ORANGE, lw=1.2, ls="--", alpha=0.8, label="+20%")
ax.set_xlabel("MA200 이격 (%)", color=GRAY, fontsize=8)
ax.legend(fontsize=7, facecolor=PANEL, labelcolor=WHITE, framealpha=0.7)

# (1,0~1) 조건별 평균 수익률 vs 하락 비율
ax2 = fig.add_subplot(gs[1, :2])
style_ax(ax2, "조건별 20일 후 평균 수익률 (하락 신호 후보 정렬)")
cond_results_all = sorted(
    [r for r in cond_results if r["n"] >= 8],
    key=lambda x: x["avg_ret"]
)[:12]
labels_c = [r["label"][:38] for r in cond_results_all]
rets_c   = [r["avg_ret"] for r in cond_results_all]
drop_c   = [r["drop_pct"] for r in cond_results_all]
y_pos = np.arange(len(labels_c))
colors_bar = [RED if r < 0 else ORANGE for r in rets_c]
ax2.barh(y_pos, rets_c, color=colors_bar, alpha=0.7, height=0.5)
ax2.set_yticks(y_pos)
ax2.set_yticklabels(labels_c, color=WHITE, fontsize=7.5)
ax2.axvline(0, color=GRAY, lw=0.8)
ax2.axvline(bnh_20 := df["Fwd20"].mean()*100, color=GREEN, lw=1, ls="--", alpha=0.6, label=f"전체 평균 {bnh_20:+.2f}%")
ax2.set_xlabel("20일 평균 수익률 (%)", color=GRAY, fontsize=8)
ax2.legend(fontsize=7, facecolor=PANEL, labelcolor=WHITE, framealpha=0.7)

# (1,2) MACD 골든/데드 별 RSI 조건 매트릭스
ax3 = fig.add_subplot(gs[1, 2])
style_ax(ax3, "RSI x MACD 조합 20일 평균수익")
rsi_bins   = [0, 30, 45, 60, 70, 100]
rsi_labels = ["<30","30-45","45-60","60-70","70+"]
matrix = np.zeros((2, len(rsi_bins)-1))
counts = np.zeros((2, len(rsi_bins)-1))
for mi, macd_cond in enumerate([(df["MACD"] > df["MACD_sig"]), (df["MACD"] <= df["MACD_sig"])]):
    for ri in range(len(rsi_bins)-1):
        rsi_cond = (df["RSI"] >= rsi_bins[ri]) & (df["RSI"] < rsi_bins[ri+1])
        sub = df[macd_cond & rsi_cond]["Fwd20"].dropna()
        matrix[mi, ri] = sub.mean() * 100 if len(sub) > 0 else 0
        counts[mi, ri] = len(sub)

im = ax3.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-5, vmax=8)
ax3.set_xticks(range(len(rsi_labels)))
ax3.set_xticklabels(rsi_labels, color=WHITE, fontsize=8)
ax3.set_yticks([0, 1])
ax3.set_yticklabels(["MACD 골든", "MACD 데드"], color=WHITE, fontsize=8)
for mi in range(2):
    for ri in range(len(rsi_labels)):
        ax3.text(ri, mi, f"{matrix[mi,ri]:+.1f}%\n(n={counts[mi,ri]:.0f})",
                 ha="center", va="center", fontsize=7, color=WHITE, fontweight="bold")
ax3.set_title("RSI x MACD 20일 평균수익 히트맵", color=WHITE, fontsize=9, fontweight="bold", pad=8)
plt.colorbar(im, ax=ax3, shrink=0.8).ax.tick_params(colors=GRAY)

fig.suptitle(f"{TICKER}  매도 신호 조건 분석  (하락 선행 지표 탐색)",
             color=WHITE, fontsize=13, fontweight="bold", y=0.96)

out_path = os.path.join(OUT_DIR, f"SellSignal_Analysis_{TICKER}_{datetime.date.today()}.png")
fig.savefig(out_path, dpi=140, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"\n[차트 저장] {out_path}")
print("\n[완료]")
