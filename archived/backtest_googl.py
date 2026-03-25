#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GOOGL 5-Year Backtest  —  auto_score() 타이밍 신호 정확도 검증
매수 적기(>=63) / 매수 검토(50-62) / 관망(37-49) / 비중 축소(24-36) / 매도 적기(<24)
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import os, datetime

TICKER      = "GOOGL"
PERIOD      = "5y"
FWD_DAYS    = [5, 10, 20]   # 신호 후 N거래일 수익률 측정
OUT_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "cowork_agents", "reports")
os.makedirs(OUT_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────
#  1.  데이터 다운로드
# ──────────────────────────────────────────────────────────────────
print(f"[1] {TICKER} 5Y 데이터 다운로드...")
raw = yf.download(TICKER, period=PERIOD, interval="1d", auto_adjust=True, progress=False)
raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
raw = raw[["Open","High","Low","Close","Volume"]].dropna()
print(f"    {len(raw)}일 로드 완료  ({raw.index[0].date()} ~ {raw.index[-1].date()})")


# ──────────────────────────────────────────────────────────────────
#  2.  지표 계산 (report_engine과 동일 파라미터)
# ──────────────────────────────────────────────────────────────────
def wilder_rsi(close: pd.Series, period=14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


df = raw.copy()
close = df["Close"]
vol   = df["Volume"]

df["MA20"]  = close.rolling(20).mean()
df["MA50"]  = close.rolling(50).mean()
df["MA200"] = close.rolling(200).mean()
df["RSI"]   = wilder_rsi(close, 14)

ema12 = close.ewm(span=12, adjust=False).mean()
ema26 = close.ewm(span=26, adjust=False).mean()
df["MACD"]        = ema12 - ema26
df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

df["BB_mid"]   = close.rolling(20).mean()
df["BB_std"]   = close.rolling(20).std(ddof=0)
df["BB_upper"] = df["BB_mid"] + 2 * df["BB_std"]
df["BB_lower"] = df["BB_mid"] - 2 * df["BB_std"]

df["AvgVol50"] = vol.rolling(50).mean()

# 52주 고저 (롤링)
df["High52w"] = df["High"].rolling(252).max()
df["Low52w"]  = df["Low"].rolling(252).min()

df = df.dropna()
print(f"    지표 계산 완료  (유효 데이터: {len(df)}일)")


# ──────────────────────────────────────────────────────────────────
#  3.  auto_score() 롤링 적용
# ──────────────────────────────────────────────────────────────────
def auto_score_row(row) -> int:
    c    = row["Close"];  m20 = row["MA20"];  m50 = row["MA50"];  m200 = row["MA200"]
    rsi  = row["RSI"];    macd_v = row["MACD"]; macd_s = row["MACD_signal"]
    bu   = row["BB_upper"]; bl = row["BB_lower"]
    vol_ = row["Volume"];   avg_v = row["AvgVol50"]
    chg  = row["Chg"]

    # A. 추세 (0-20)
    above = sum([c > m20, c > m50, c > m200])
    bull_align = (m20 > m50 > m200)
    a = min(above * 5 + (3 if bull_align and above == 3 else 0) + (2 if above >= 2 else 0), 20)

    # B. 모멘텀 (0-20)
    rsi_s  = (2 if rsi >= 70 else 5 if rsi >= 60 else 8 if rsi >= 45 else 9 if rsi >= 30 else 4)
    macd_sc = (10 if macd_v > macd_s and macd_v > 0 else
               7  if macd_v > macd_s else
               4  if macd_v > 0 else 2)
    b = min(rsi_s + macd_sc, 20)

    # C. BB 위치 (0-15)
    bb_r = bu - bl
    bp   = (c - bl) / bb_r if bb_r > 0 else 0.5
    c_s  = (4  if bp <= 0.00 else 13 if bp <= 0.20 else 10 if bp <= 0.45 else
            7  if bp <= 0.60 else 5  if bp <= 0.80 else 3)
    c_s  = min(max(c_s, 0), 15)

    # D. 거래량 (0-15)
    vr  = vol_ / max(avg_v, 1)
    d_s = (13 if chg > 1.0 and vr >= 1.5 else 10 if chg > 0 and vr >= 1.2 else
           2  if chg < -1.0 and vr >= 1.5 else 4  if chg < 0 and vr >= 1.2 else 7)
    d_s = min(max(d_s, 0), 15)

    # E. MA 지지 근접도 (0-15)
    nm  = min(abs(c-m20)/max(m20,1), abs(c-m50)/max(m50,1), abs(c-m200)/max(m200,1))
    am  = c > m200
    e_s = (14 if am and nm < 0.02 else 11 if am and nm < 0.05 else
           8  if am and nm < 0.10 else 6  if am else
           4  if nm < 0.03 else 2)
    e_s = min(max(e_s, 0), 15)

    # F. 매도 압력 페널티 (백테스트 기반)
    macd_dead = macd_v < macd_s
    f_s = 0
    if c < m50 and macd_dead and macd_v > 0:      f_s -= 15
    if chg < -1.0 and vol_ / max(avg_v, 1) >= 1.5: f_s -= 8
    if bp >= 0.90:                                  f_s -= 8
    elif bp >= 0.85 and rsi >= 65:                 f_s -= 5
    f_s = max(f_s, -20)

    return max(0, a + b + c_s + d_s + e_s + f_s)


def timing_label(total: int) -> str:
    if total >= 63: return "매수 적기"
    if total >= 50: return "매수 검토"
    if total >= 37: return "관망"
    if total >= 24: return "비중 축소"
    return "매도 적기"


df["Chg"] = df["Close"].pct_change() * 100
df = df.dropna(subset=["Chg"])

print("[2] 전체 기간 신호 계산 중...")
df["Score"]  = df.apply(auto_score_row, axis=1)
df["Signal"] = df["Score"].apply(timing_label)
print(f"    완료  총 {len(df)}일")


# ──────────────────────────────────────────────────────────────────
#  4.  순방향 수익률 계산
# ──────────────────────────────────────────────────────────────────
for n in FWD_DAYS:
    df[f"Fwd{n}"] = df["Close"].shift(-n) / df["Close"] - 1

# 매수 신호 = Score >= 50 → 가격 상승 예측
# 매도 신호 = Score <  37 → 가격 하락 예측
df["BuySignal"]  = df["Score"] >= 50
df["SellSignal"] = df["Score"] <  37


# ──────────────────────────────────────────────────────────────────
#  5.  정확도 분석
# ──────────────────────────────────────────────────────────────────
LABELS  = ["매수 적기", "매수 검토", "관망", "비중 축소", "매도 적기"]
COLORS  = ["#00C853", "#69F0AE", "#FFB300", "#FF7043", "#D32F2F"]
COLOR_MAP = dict(zip(LABELS, COLORS))

print("\n" + "="*62)
print(f"  GOOGL 5Y  백테스트 결과  ({df.index[0].date()} ~ {df.index[-1].date()})")
print("="*62)

results = {}
for lbl in LABELS:
    sub = df[df["Signal"] == lbl].copy()
    row = {"n": len(sub), "color": COLOR_MAP[lbl]}
    for n in FWD_DAYS:
        col = f"Fwd{n}"
        valid = sub[col].dropna()
        if lbl in ("매수 적기", "매수 검토"):
            hit = (valid > 0).mean()
        elif lbl in ("비중 축소", "매도 적기"):
            hit = (valid < 0).mean()
        else:
            hit = np.nan
        row[f"hit{n}"]  = hit
        row[f"ret{n}"]  = valid.mean()
        row[f"std{n}"]  = valid.std()
    results[lbl] = row

# 콘솔 출력
print(f"\n{'신호':<12} {'일수':>5}  {'5일 적중':>8}  {'10일 적중':>9}  {'20일 적중':>9}  {'5일 평균수익':>11}  {'20일 평균수익':>12}")
print("-"*75)
for lbl in LABELS:
    r = results[lbl]
    h5  = f"{r['hit5']*100:.1f}%"  if not np.isnan(r['hit5'])  else "  N/A"
    h10 = f"{r['hit10']*100:.1f}%" if not np.isnan(r['hit10']) else "  N/A"
    h20 = f"{r['hit20']*100:.1f}%" if not np.isnan(r['hit20']) else "  N/A"
    ret5  = f"{r['ret5']*100:+.2f}%"
    ret20 = f"{r['ret20']*100:+.2f}%"
    print(f"{lbl:<12} {r['n']:>5}  {h5:>8}  {h10:>9}  {h20:>9}  {ret5:>11}  {ret20:>12}")

# Buy-and-Hold 비교
bnh_5  = df["Fwd5"].dropna().mean()
bnh_20 = df["Fwd20"].dropna().mean()
bnh_tot = df["Close"].iloc[-1] / df["Close"].iloc[0] - 1
print("-"*75)
print(f"{'Buy & Hold':<12} {'-':>5}  {'-':>8}  {'-':>9}  {'-':>9}  {bnh_5*100:>+10.2f}%  {bnh_20*100:>+11.2f}%")
print(f"\n  5년 총 수익 (Buy & Hold): {bnh_tot*100:+.1f}%")


# ──────────────────────────────────────────────────────────────────
#  6.  시각화
# ──────────────────────────────────────────────────────────────────
print("\n[3] 차트 생성 중...")

fig = plt.figure(figsize=(16, 18), facecolor="#0F1117")
gs  = gridspec.GridSpec(4, 2, figure=fig,
                        height_ratios=[2.8, 1.2, 1.2, 1.4],
                        hspace=0.42, wspace=0.32,
                        left=0.07, right=0.97, top=0.94, bottom=0.05)

BG    = "#0F1117"
PANEL = "#1A1D27"
GRID  = "#2A2D3A"
WHITE = "#FFFFFF"
GRAY  = "#6B7280"

def style_ax(ax, title=""):
    ax.set_facecolor(PANEL)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=GRAY, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.7)
    if title:
        ax.set_title(title, color=WHITE, fontsize=10, fontweight="bold", pad=8)

# ── (0,0)~(0,1) 가격 + 신호 ─────────────────────────────────────
ax_price = fig.add_subplot(gs[0, :])
style_ax(ax_price, f"{TICKER}  5년 가격 + 타이밍 신호")
ax_price.plot(df.index, df["Close"], color="#90CAF9", lw=1.2, zorder=3, label="종가")
ax_price.plot(df.index, df["MA50"],  color="#FFB300", lw=0.8, alpha=0.6, label="MA50")
ax_price.plot(df.index, df["MA200"], color="#FF7043", lw=0.9, ls="--", alpha=0.7, label="MA200")

# 신호 마커
buy_strong = df[df["Signal"] == "매수 적기"]
buy_look   = df[df["Signal"] == "매수 검토"]
sell_weak  = df[df["Signal"] == "비중 축소"]
sell_str   = df[df["Signal"] == "매도 적기"]

ax_price.scatter(buy_strong.index, buy_strong["Close"], marker="^", s=28,
                 color="#00C853", alpha=0.8, zorder=5, label="매수 적기")
ax_price.scatter(buy_look.index,   buy_look["Close"],   marker="^", s=14,
                 color="#69F0AE", alpha=0.5, zorder=4, label="매수 검토")
ax_price.scatter(sell_str.index,   sell_str["Close"],   marker="v", s=28,
                 color="#D32F2F", alpha=0.8, zorder=5, label="매도 적기")
ax_price.scatter(sell_weak.index,  sell_weak["Close"],  marker="v", s=14,
                 color="#FF7043", alpha=0.5, zorder=4, label="비중 축소")

ax_price.set_ylabel("주가 ($)", color=GRAY, fontsize=8)
ax_price.legend(loc="upper left", fontsize=7.5, facecolor=PANEL,
                labelcolor=WHITE, framealpha=0.8, ncol=4)

# ── (1,0) 스코어 히스토그램 ──────────────────────────────────────
ax_hist = fig.add_subplot(gs[1, 0])
style_ax(ax_hist, "일별 타이밍 점수 분포 (0-85)")
bins = np.arange(0, 86, 3)
ax_hist.hist(df["Score"], bins=bins, color="#1B4F8A", edgecolor=PANEL, linewidth=0.3)
# 구간 표시
for x, c in zip([24, 37, 50, 63], ["#FF5252","#FF7043","#69F0AE","#00C853"]):
    ax_hist.axvline(x, color=c, lw=1.2, ls="--", alpha=0.8)
ax_hist.set_xlabel("점수", color=GRAY, fontsize=8)
ax_hist.set_ylabel("빈도 (일)", color=GRAY, fontsize=8)

# ── (1,1) 신호 비율 파이 ─────────────────────────────────────────
ax_pie = fig.add_subplot(gs[1, 1])
ax_pie.set_facecolor(PANEL)
ax_pie.set_title("신호 비율", color=WHITE, fontsize=10, fontweight="bold", pad=8)
sizes  = [results[l]["n"] for l in LABELS]
colors = [COLOR_MAP[l] for l in LABELS]
wedges, texts, autotexts = ax_pie.pie(
    sizes, labels=LABELS, colors=colors,
    autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
    pctdistance=0.75, startangle=90,
    wedgeprops={"edgecolor": PANEL, "linewidth": 1.5}
)
for t in texts:    t.set_color(WHITE); t.set_fontsize(8)
for a in autotexts: a.set_color(WHITE); a.set_fontsize(7)

# ── (2,0) 적중률 막대 ────────────────────────────────────────────
ax_hit = fig.add_subplot(gs[2, 0])
style_ax(ax_hit, "신호별 예측 적중률  (N일 후 방향 일치)")

lbl_buy  = ["매수 적기", "매수 검토"]
lbl_sell = ["비중 축소", "매도 적기"]
lbl_eval = lbl_buy + lbl_sell
x_pos = np.arange(len(lbl_eval))
w = 0.25

for ki, n in enumerate(FWD_DAYS):
    hits = [results[l][f"hit{n}"] * 100 for l in lbl_eval]
    bars = ax_hit.bar(x_pos + ki * w, hits, width=w,
                      color=[COLOR_MAP[l] for l in lbl_eval],
                      alpha=0.5 + ki * 0.15, label=f"{n}일 후",
                      edgecolor=PANEL, linewidth=0.5)

ax_hit.axhline(50, color=GRAY, lw=0.8, ls="--", alpha=0.5, label="기준선 50%")
ax_hit.set_xticks(x_pos + w)
ax_hit.set_xticklabels(lbl_eval, color=WHITE, fontsize=8)
ax_hit.set_ylabel("적중률 (%)", color=GRAY, fontsize=8)
ax_hit.set_ylim(0, 100)
ax_hit.legend(fontsize=7, facecolor=PANEL, labelcolor=WHITE, framealpha=0.7)

# ── (2,1) 평균 수익률 ────────────────────────────────────────────
ax_ret = fig.add_subplot(gs[2, 1])
style_ax(ax_ret, "신호별 평균 순방향 수익률  (%)")

x_pos2 = np.arange(len(LABELS))
for ki, n in enumerate(FWD_DAYS):
    rets = [results[l][f"ret{n}"] * 100 for l in LABELS]
    ax_ret.bar(x_pos2 + ki * w, rets, width=w,
               color=[COLOR_MAP[l] for l in LABELS],
               alpha=0.5 + ki * 0.15, label=f"{n}일 후",
               edgecolor=PANEL, linewidth=0.5)

ax_ret.axhline(0, color=GRAY, lw=0.8, ls="-", alpha=0.5)
ax_ret.set_xticks(x_pos2 + w)
ax_ret.set_xticklabels(LABELS, color=WHITE, fontsize=8)
ax_ret.set_ylabel("평균 수익률 (%)", color=GRAY, fontsize=8)
ax_ret.legend(fontsize=7, facecolor=PANEL, labelcolor=WHITE, framealpha=0.7)

# ── (3,:) 누적 수익률 비교 ───────────────────────────────────────
ax_cum = fig.add_subplot(gs[3, :])
style_ax(ax_cum, "전략별 누적 수익률 비교  (20일 신호 기준)")

# Buy & Hold
bnh = (df["Close"] / df["Close"].iloc[0] - 1) * 100
ax_cum.plot(df.index, bnh, color=GRAY, lw=1.2, label="Buy & Hold", alpha=0.7)

# 매수 적기 신호 → 20일 후 매도 전략
equity_buy = [0.0]
cash = 1.0
i_list = list(range(len(df)))
signal_dates_buy = set(df[df["Signal"] == "매수 적기"].index)
in_trade = False
entry_price = None
entry_date  = None
daily_equity = np.zeros(len(df))
daily_equity[0] = 0.0
for i in range(len(df)):
    date = df.index[i]
    price = df["Close"].iloc[i]
    if in_trade:
        daily_equity[i] = (price / entry_price - 1 + 1) * (daily_equity[i-1] / 100 + 1) * 100 - 100
        if i - entry_idx >= 20:
            cash *= price / entry_price
            in_trade = False
    else:
        daily_equity[i] = daily_equity[i-1] if i > 0 else 0.0
        if date in signal_dates_buy and i + 20 < len(df):
            in_trade    = True
            entry_price = price
            entry_idx   = i

ax_cum.plot(df.index, daily_equity, color="#00C853", lw=1.2,
            label="매수 적기 신호 전략 (보유 20일)", alpha=0.9)

# 매도 적기 신호 → 현금 보유 전략 (매도 적기 신호 시 보유 안 함)
# 간단 버전: 매도 적기 신호가 없는 날만 보유
mask_hold = df["Signal"] != "매도 적기"
daily_ret = df["Close"].pct_change().fillna(0)
filtered_ret = daily_ret.where(mask_hold, 0)
cum_sell_avoid = (1 + filtered_ret).cumprod()
ax_cum.plot(df.index, (cum_sell_avoid - 1) * 100, color="#FF7043", lw=1.2,
            label="매도 적기 회피 전략 (신호 시 현금)", alpha=0.9)

ax_cum.axhline(0, color=GRAY, lw=0.5, ls="-", alpha=0.4)
ax_cum.set_ylabel("누적 수익률 (%)", color=GRAY, fontsize=8)
ax_cum.legend(loc="upper left", fontsize=8, facecolor=PANEL, labelcolor=WHITE, framealpha=0.8)

# 제목
fig.suptitle(f"{TICKER}  타이밍 신호 백테스트  ·  5년  ({df.index[0].strftime('%Y.%m')} ~ {df.index[-1].strftime('%Y.%m')})",
             color=WHITE, fontsize=14, fontweight="bold", y=0.97)

out_path = os.path.join(OUT_DIR, f"Backtest_{TICKER}_{datetime.date.today()}.png")
fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"    차트 저장: {out_path}")


# ──────────────────────────────────────────────────────────────────
#  7.  요약 CSV
# ──────────────────────────────────────────────────────────────────
rows_csv = []
for lbl in LABELS:
    r = results[lbl]
    rows_csv.append({
        "신호": lbl, "일수": r["n"],
        "5일_적중률(%)":  round(r["hit5"]*100,  1) if not np.isnan(r["hit5"])  else None,
        "10일_적중률(%)": round(r["hit10"]*100, 1) if not np.isnan(r["hit10"]) else None,
        "20일_적중률(%)": round(r["hit20"]*100, 1) if not np.isnan(r["hit20"]) else None,
        "5일_평균수익(%)":  round(r["ret5"]*100,  3),
        "10일_평균수익(%)": round(r["ret10"]*100, 3),
        "20일_평균수익(%)": round(r["ret20"]*100, 3),
        "20일_수익_표준편차(%)": round(r["std20"]*100, 3),
    })
csv_path = os.path.join(OUT_DIR, f"Backtest_{TICKER}_{datetime.date.today()}.csv")
pd.DataFrame(rows_csv).to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"    CSV  저장: {csv_path}")

print("\n[완료]")
