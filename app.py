#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Report Manager — Streamlit Web App
종목 관리 UI: 추가 / 삭제 / 즉시 실행 / 최근 실행 현황
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import json, os, base64, requests, time
import yfinance as yf
from datetime import datetime, timezone

st.set_page_config(
    page_title="Stock Report Manager",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #0F1117; }

/* 헤더 */
.header-wrap {
    background: linear-gradient(135deg, #0D2137 0%, #1B4F8A 60%, #0D2137 100%);
    border-radius: 20px;
    padding: 28px 36px;
    margin-bottom: 24px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.header-left { display: flex; align-items: center; gap: 16px; }
.header-icon {
    font-size: 42px;
    background: rgba(255,255,255,0.1);
    border-radius: 14px;
    padding: 8px 12px;
}
.header-title {
    font-size: 28px; font-weight: 800;
    color: #FFFFFF; letter-spacing: -0.5px;
    line-height: 1.1;
}
.header-sub {
    font-size: 13px; color: rgba(255,255,255,0.80);
    margin-top: 4px; font-weight: 400;
}
.header-stats { display: flex; gap: 24px; }
.stat-box {
    text-align: center;
    background: rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 10px 20px;
    border: 1px solid rgba(255,255,255,0.1);
}
.stat-val {
    font-size: 22px; font-weight: 800; color: #fff;
    line-height: 1.1;
}
.stat-lbl {
    font-size: 11px; color: rgba(255,255,255,0.70);
    font-weight: 500; margin-top: 2px;
    text-transform: uppercase; letter-spacing: 0.5px;
}

/* 섹션 레이블 */
.section-label {
    font-size: 11px; font-weight: 700;
    color: rgba(255,255,255,0.65);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 14px;
    margin-top: 4px;
}

/* 종목 카드 */
.ticker-card {
    background: #1A1D27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 18px 16px 14px 16px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    display: flex;
    flex-direction: column;
    height: 370px;
    box-sizing: border-box;
}
.ticker-card:hover {
    border-color: rgba(27,79,138,0.6);
    box-shadow: 0 4px 20px rgba(27,79,138,0.2);
    transform: translateY(-1px);
}
.ticker-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
}
.ticker-card.up::before   { background: linear-gradient(90deg, #00C853, #69F0AE); }
.ticker-card.down::before { background: linear-gradient(90deg, #D32F2F, #FF5252); }
.ticker-card.neu::before  { background: linear-gradient(90deg, #F57C00, #FFB300); }

.ticker-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
}
.ticker-symbol {
    font-size: 26px; font-weight: 800;
    color: #FFFFFF; letter-spacing: 1px;
}
.ticker-exchange {
    font-size: 13px; color: rgba(255,255,255,0.65);
    font-weight: 500; margin-top: 2px;
}
.price-badge {
    text-align: right;
}
.price-val {
    font-size: 22px; font-weight: 700; color: #fff;
    line-height: 1.1;
}
.price-chg {
    font-size: 13px; font-weight: 600;
    border-radius: 6px; padding: 2px 7px;
    display: inline-block; margin-top: 3px;
}
.price-chg.up   { background: rgba(0,200,83,0.15);  color: #00E676; }
.price-chg.down { background: rgba(211,47,47,0.15); color: #FF5252; }
.price-chg.neu  { background: rgba(245,124,0,0.12); color: #FFB300; }

.ticker-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 10px 0;
}

.ticker-stats {
    display: flex;
    justify-content: space-around;
    margin-top: 4px;
}
.ts-item { text-align: center; }
.ts-val {
    font-size: 16px; font-weight: 700;
    color: rgba(255,255,255,0.8);
}
.ts-lbl {
    font-size: 11px; color: rgba(255,255,255,0.65);
    text-transform: uppercase; letter-spacing: 0.4px;
    margin-top: 1px;
}

.opinion-pill {
    display: inline-block;
    font-size: 10px; font-weight: 700;
    border-radius: 20px; padding: 2px 9px;
    margin-bottom: 8px;
}
.op-bull { background: rgba(0,200,83,0.12);  color: #00E676; border: 1px solid rgba(0,200,83,0.2); }
.op-bear { background: rgba(211,47,47,0.12); color: #FF5252; border: 1px solid rgba(211,47,47,0.2); }
.op-neut { background: rgba(245,124,0,0.12); color: #FFB300; border: 1px solid rgba(245,124,0,0.2); }

/* 스코어 바 */
.score-bar-wrap {
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    margin: 6px 0 4px;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.4s ease;
}

/* 타이밍 판정 하단 행 */
.timing-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
}
.timing-pill {
    font-size: 13px; font-weight: 700;
    border-radius: 20px; padding: 4px 12px;
    border: 1px solid;
}
.tp-bull { background: rgba(0,200,83,0.12);  color: #00E676; border-color: rgba(0,200,83,0.25); }
.tp-bear { background: rgba(211,47,47,0.12); color: #FF5252; border-color: rgba(211,47,47,0.25); }
.tp-neut { background: rgba(245,124,0,0.12); color: #FFB300; border-color: rgba(245,124,0,0.25); }
.tp-gray { background: rgba(100,116,139,0.12); color: #94A3B8; border-color: rgba(100,116,139,0.25); }
.score-txt {
    font-size: 11px; font-weight: 700;
    color: rgba(255,255,255,0.65);
}

/* 빈 카드 (데이터 없음) */
.ticker-card-empty {
    background: #1A1D27;
    border: 1.5px dashed rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 18px 16px 14px 16px;
    height: 370px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
}
.ticker-symbol-empty {
    font-size: 20px; font-weight: 800;
    color: rgba(255,255,255,0.75); letter-spacing: 1px;
}
.no-data-label {
    font-size: 10px; color: rgba(255,255,255,0.55);
    margin-top: 4px;
}

/* 종목 추가 섹션 */
.add-section {
    background: #1A1D27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 8px;
}

/* 상태 카드 */
.run-card {
    background: #1A1D27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 18px 24px;
    display: flex;
    align-items: center;
    gap: 14px;
}
.run-icon { font-size: 26px; }
.run-info-title { font-size: 13px; font-weight: 700; color: #fff; }
.run-info-sub   { font-size: 12px; color: rgba(255,255,255,0.65); margin-top: 2px; }
.run-status-ok   { color: #00E676; }
.run-status-fail { color: #FF5252; }
.run-status-prog { color: #FFB300; }

/* 데이터 갱신 배너 */
.data-banner {
    background: linear-gradient(90deg, rgba(27,79,138,0.3), rgba(27,79,138,0.1));
    border: 1px solid rgba(27,79,138,0.4);
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 12px;
    color: rgba(255,255,255,0.75);
    margin-bottom: 16px;
}

/* 삭제 버튼 */
div[data-testid="stButton"] button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    transition: all 0.15s !important;
}

/* 텍스트 인풋 */
.stTextInput input {
    background: #0F1117 !important;
    border: 1.5px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-size: 14px !important;
}
.stTextInput input:focus {
    border-color: #1B4F8A !important;
    box-shadow: 0 0 0 3px rgba(27,79,138,0.2) !important;
}

/* 토스트 */
.stAlert {
    border-radius: 12px !important;
}

/* 스크롤바 */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }

/* 신호 힌트 고정 영역 — 항상 52px 고정, 초과 태그는 숨김 */
.signal-hint-area {
    height: 52px;
    flex-shrink: 0;
    margin-top: auto;
    padding-top: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: flex-start;
    align-content: flex-start;
    overflow: hidden;
}

/* Streamlit 기본 요소 숨기기 */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; max-width: 1200px !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  종목명 사전
# ══════════════════════════════════════════════════════════════════
KNOWN = {
    'NVDA':'NVIDIA', 'PLTR':'Palantir', 'TSLA':'Tesla',
    'AAPL':'Apple', 'MSFT':'Microsoft', 'GOOGL':'Alphabet',
    'GOOG':'Alphabet', 'AMZN':'Amazon', 'META':'Meta',
    'NFLX':'Netflix', 'AMD':'AMD', 'INTC':'Intel',
    'AVGO':'Broadcom', 'QCOM':'Qualcomm', 'ARM':'Arm Holdings',
    'SMCI':'Super Micro', 'ASML':'ASML', 'TSM':'TSMC',
    'CRM':'Salesforce', 'NOW':'ServiceNow', 'ADBE':'Adobe',
    'INTU':'Intuit', 'ORCL':'Oracle', 'IBM':'IBM',
    'SNOW':'Snowflake', 'DDOG':'Datadog', 'MDB':'MongoDB',
    'CRWD':'CrowdStrike', 'PANW':'Palo Alto', 'NET':'Cloudflare',
    'ZS':'Zscaler', 'WDAY':'Workday', 'TTD':'Trade Desk',
    'UBER':'Uber', 'LYFT':'Lyft', 'COIN':'Coinbase',
    'SQ':'Block', 'PYPL':'PayPal', 'SHOP':'Shopify',
    'SPOT':'Spotify', 'RBLX':'Roblox', 'ROKU':'Roku',
    'V':'Visa', 'MA':'Mastercard', 'JPM':'JPMorgan',
    'BAC':'Bank of America', 'GS':'Goldman Sachs',
    'BRK.B':'Berkshire', 'WMT':'Walmart', 'COST':'Costco',
    'HD':'Home Depot', 'MCD':"McDonald's", 'SBUX':'Starbucks',
    'KO':'Coca-Cola', 'PEP':'PepsiCo', 'DIS':'Disney',
    'LLY':'Eli Lilly', 'MRNA':'Moderna', 'PFE':'Pfizer',
    'JNJ':'J&J', 'UNH':'UnitedHealth', 'ABBV':'AbbVie',
    'XOM':'ExxonMobil', 'CVX':'Chevron', 'BA':'Boeing',
    'GE':'GE Aerospace', 'F':'Ford', 'GM':'General Motors',
    'RIVN':'Rivian', 'LCID':'Lucid', 'NIO':'NIO',
    'BABA':'Alibaba', 'JD':'JD.com', 'HOOD':'Robinhood',
    'VOO':'Vanguard S&P500', 'QQQ':'Nasdaq 100 ETF',
    'IONQ':'IonQ', 'MSTR':'MicroStrategy', 'IBIT':'iShares Bitcoin ETF',
}

def trading_stage_v2(p):
    """v2.2 판정1: QQQ+SPY Dual MA200 필터 포함"""
    def sig(key, default=False): return bool(p.get(key, default))
    qqq_above = sig('qqq_above_ma200', True)
    spy_above = sig('spy_above_ma200', True)
    market_state = p.get('market_state',
        'normal' if (qqq_above and spy_above) else
        'caution' if (qqq_above or spy_above) else 'bear')

    if market_state == 'bear':
        return 'watch_market', '시장 관망', '#94A3B8'

    if market_state == 'normal':
        # 3차: RSI75 차단 제거, 거래량 조건 완화
        if all([sig('sig_above_ma20_2d'), sig('sig_ma20_slope_pos'),
                sig('sig_macd_above_zero'),
                sig('sig_vol_1p3') or sig('sig_vol_5d_2up')]):
            return 'buy3', '3차 매수', '#00E676'
        # 2차
        if all([sig('sig_double_bottom'),
                sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'),
                sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'),
                sig('sig_vol_1p2')]):
            return 'buy2', '2차 매수', '#69F0AE'

    # 1차: [필수] MACD 히스토그램 2일 증가 + 6조건 중 3개 이상
    if not (sig('sig_block_rsi50') or sig('sig_block_bigdrop')) and sig('sig_macd_hist_2d_up'):
        conds = [sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_near_bb_low'),
                 sig('sig_below_ma20'), sig('sig_low_stopped'), sig('sig_bounce2pct')]
        if sum(conds) >= 3:
            return 'buy1', '1차 매수', '#FBBF24'

    if market_state == 'caution':
        return 'caution_market', '경계 관망', '#F59E0B'
    return 'watch', '관망', '#94A3B8'


def trading_stage2_v2(p):
    """v2.2 판정2: 기술신호만 (시장 필터 없음)"""
    def sig(key, default=False): return bool(p.get(key, default))
    # 3차: RSI75 차단 제거
    if all([sig('sig_above_ma20_2d'), sig('sig_ma20_slope_pos'),
            sig('sig_macd_above_zero'),
            sig('sig_vol_1p3') or sig('sig_vol_5d_2up')]):
        return 'buy3', '3차 매수', '#00E676'
    # 2차
    if all([sig('sig_double_bottom'),
            sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'),
            sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'),
            sig('sig_vol_1p2')]):
        return 'buy2', '2차 매수', '#69F0AE'
    # 1차: [필수] MACD 히스토그램 2일 증가
    if not (sig('sig_block_rsi50') or sig('sig_block_bigdrop')) and sig('sig_macd_hist_2d_up'):
        conds = [sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_near_bb_low'),
                 sig('sig_below_ma20'), sig('sig_low_stopped'), sig('sig_bounce2pct')]
        if sum(conds) >= 3:
            return 'buy1', '1차 매수', '#FBBF24'
    return 'watch', '관망', '#94A3B8'


def stage_pill_cls(sk):
    return {'buy3': 'tp-bull', 'buy2': 'tp-bull', 'buy1': 'tp-neut',
            'watch': 'tp-gray', 'watch_market': 'tp-gray',
            'caution_market': 'tp-neut'}.get(sk, 'tp-gray')


def get_signal_hint(p):
    """1차 조건 충족 신호 힌트 HTML — 항상 .signal-hint-area 래핑"""
    def sig(key): return bool(p.get(key, False))
    names = {
        'sig_rsi_le38':    'RSI≤38',
        'sig_adx_le25':    'ADX≤25',
        'sig_near_bb_low': 'BB하단',
        'sig_below_ma20':  'MA20↓',
        'sig_low_stopped': '하락멈춤',
        'sig_bounce2pct':  '반등+2%',
    }
    met = [v for k, v in names.items() if sig(k)]
    cnt = len(met)
    if cnt == 0:
        return '<div class="signal-hint-area"></div>'
    color = '#00E676' if cnt >= 3 else '#FFB300' if cnt >= 2 else 'rgba(255,255,255,0.6)'
    visible = met[:5]   # 최대 5개 표시 (1행 내 수용 가능)
    tags = ''.join(
        f'<span style="font-size:11px;color:{color};background:rgba(255,255,255,0.05);'
        f'border:1px solid rgba(255,255,255,0.08);border-radius:4px;padding:2px 6px">{m}</span>'
        for m in visible
    )
    return (f'<div class="signal-hint-area">'
            f'<span style="font-size:11px;color:rgba(255,255,255,0.65);margin-right:2px">'
            f'1차 {cnt}/6</span>{tags}</div>')

# ══════════════════════════════════════════════════════════════════
#  GitHub API
# ══════════════════════════════════════════════════════════════════
REPO      = "freecjs77-tech/mag7-stock-report"
TICKERS_F = "tickers.json"
API_BASE  = f"https://api.github.com/repos/{REPO}"
PAGES_URL = f"https://freecjs77-tech.github.io/mag7-stock-report"


def gh_token():
    try:    return st.secrets["GITHUB_TOKEN"]
    except: return os.environ.get("GITHUB_TOKEN", "")


def gh_headers():
    t = gh_token()
    return {"Authorization": f"token {t}", "Accept": "application/vnd.github+json"} if t else {}


@st.cache_data(ttl=30)
def load_tickers():
    try:
        r = requests.get(f"{API_BASE}/contents/{TICKERS_F}", headers=gh_headers(), timeout=10)
        if r.status_code == 200:
            d       = r.json()
            content = base64.b64decode(d["content"]).decode()
            parsed  = json.loads(content)
            return parsed.get("tickers", []), d.get("sha", "")
    except Exception:
        pass
    if os.path.exists(TICKERS_F):
        with open(TICKERS_F) as f:
            d = json.load(f)
        return d.get("tickers", []), ""
    return ["NVDA","PLTR","TSLA","AAPL","MSFT","GOOGL","AMZN","META"], ""


def save_tickers(tickers, sha):
    content = json.dumps(
        {"tickers": tickers, "updated": datetime.today().strftime("%Y-%m-%d")}, indent=2
    )
    encoded = base64.b64encode(content.encode()).decode()
    payload = {
        "message": f"[UI] Update tickers ({len(tickers)}): {', '.join(tickers)}",
        "content": encoded, "sha": sha,
    }
    try:
        r = requests.put(f"{API_BASE}/contents/{TICKERS_F}",
                         json=payload, headers=gh_headers(), timeout=15)
        if r.status_code in (200, 201):
            load_tickers.clear()
            return True, "저장 완료"
        return False, f"저장 실패 ({r.status_code})"
    except Exception as e:
        return False, f"연결 오류: {e}"


def trigger_workflow():
    try:
        r = requests.post(
            f"{API_BASE}/actions/workflows/daily.yml/dispatches",
            json={"ref": "main"}, headers=gh_headers(), timeout=15,
        )
        return r.status_code == 204, ("워크플로우 실행 요청됨" if r.status_code == 204 else f"오류 ({r.status_code})")
    except Exception as e:
        return False, str(e)



@st.cache_data(ttl=60, show_spinner=False)
def load_price_data():
    """GitHub repo의 mag7_data.json 우선 로드, 없으면 로컬 파일 (60초 캐시)"""
    # GitHub repo에서 최신 데이터 시도
    try:
        r = requests.get(f"{API_BASE}/contents/cowork_agents/mag7_data.json",
                         headers=gh_headers(), timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode()
            d = json.loads(content)
            return {s["ticker"]: s for s in d.get("stocks", [])}, d.get("last_updated", "")
    except Exception:
        pass
    # 로컬 파일 fallback
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "cowork_agents", "mag7_data.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return {s["ticker"]: s for s in d.get("stocks", [])}, d.get("last_updated", "")
        except Exception:
            pass
    return {}, ""


@st.cache_data(ttl=3600, show_spinner=False)
def validate_ticker(ticker: str) -> bool:
    """yfinance로 티커 유효성 확인 (1시간 캐시) — 빈 데이터면 유효하지 않은 티커"""
    try:
        hist = yf.Ticker(ticker).history(period='5d', interval='1d')
        return not hist.empty
    except Exception:
        return False


@st.cache_data(ttl=10)
def get_latest_run():
    """최근 워크플로우 실행 정보 반환"""
    try:
        r = requests.get(
            f"{API_BASE}/actions/workflows/daily.yml/runs?per_page=1",
            headers=gh_headers(), timeout=10,
        )
        if r.status_code == 200:
            runs = r.json().get("workflow_runs", [])
            if runs:
                run = runs[0]
                return {
                    "id":         run["id"],
                    "date":       run["created_at"][:16].replace("T", " "),
                    "status":     run["status"],        # queued / in_progress / completed
                    "conclusion": run["conclusion"],    # success / failure / None
                    "url":        run["html_url"],
                }
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
#  Session state 초기화
# ══════════════════════════════════════════════════════════════════
if "tickers" not in st.session_state or "sha" not in st.session_state:
    t, s = load_tickers()
    st.session_state.tickers = t
    st.session_state.sha     = s
if "toast"       not in st.session_state: st.session_state.toast        = None
if "polling"     not in st.session_state: st.session_state.polling      = False
if "run_id_seen" not in st.session_state: st.session_state.run_id_seen  = None
if "price_map"   not in st.session_state: st.session_state.price_map    = {}
if "last_updated" not in st.session_state: st.session_state.last_updated = ""

# 가격 데이터 로드 (60초 캐시 — force_reload 시 캐시 클리어 후 재요청)
if not st.session_state.price_map or st.session_state.get("force_reload"):
    if st.session_state.get("force_reload"):
        load_price_data.clear()          # 워크플로우 완료 후 강제 갱신
    pm, lu = load_price_data()
    if pm:
        st.session_state.price_map    = pm
        st.session_state.last_updated = lu
    st.session_state.force_reload = False

price_map    = st.session_state.price_map
last_updated = st.session_state.last_updated

# tickers에 있는데 data에 없는 종목 감지
missing = [t for t in st.session_state.tickers if t not in price_map]


# ══════════════════════════════════════════════════════════════════
#  헤더
# ══════════════════════════════════════════════════════════════════
n          = len(st.session_state.tickers)
buy_count  = sum(1 for t in st.session_state.tickers
                 if price_map.get(t) and trading_stage_v2(price_map[t])[0] in ('buy1','buy2','buy3'))
sell_count = sum(1 for t in st.session_state.tickers
                 if price_map.get(t) and trading_stage_v2(price_map[t])[0] in ('watch_market', 'caution_market'))

st.markdown(f"""
<div class="header-wrap">
  <div class="header-left">
    <div class="header-icon">📈</div>
    <div>
      <div class="header-title">Stock Report Manager</div>
      <div class="header-sub">매일 오전 9시 KST · Yahoo Finance 실시간 데이터</div>
    </div>
  </div>
  <div class="header-stats">
    <div class="stat-box">
      <div class="stat-val">{n}</div>
      <div class="stat-lbl">종목 수</div>
    </div>
    <div class="stat-box">
      <div class="stat-val" style="color:#00E676">{buy_count}</div>
      <div class="stat-lbl">매수 신호</div>
    </div>
    <div class="stat-box">
      <div class="stat-val" style="color:#FF5252">{sell_count}</div>
      <div class="stat-lbl">시장 관망</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# 토스트
if st.session_state.toast:
    kind, msg = st.session_state.toast
    if kind == "success": st.success(msg)
    else:                 st.error(msg)
    st.session_state.toast = None


# ══════════════════════════════════════════════════════════════════
#  데이터 갱신일 배너
# ══════════════════════════════════════════════════════════════════
if last_updated:
    st.markdown(
        f'<div class="data-banner">📊 최근 데이터 업데이트: {last_updated} &nbsp;·&nbsp; '
        f'종가 기준 기술적 지표 (yfinance)</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════
#  종목 그리드
# ══════════════════════════════════════════════════════════════════
if missing:
    st.markdown(
        f'<div class="data-banner" style="border-color:rgba(255,179,0,0.4);background:linear-gradient(90deg,rgba(255,179,0,0.12),rgba(255,179,0,0.04))">'
        f'⚠️ &nbsp;<b style="color:#FFB300">{", ".join(missing)}</b> — 아직 데이터 없음.'
        f' &nbsp;▶ 지금 실행을 눌러 리포트를 생성하세요.</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-label">등록 종목</div>', unsafe_allow_html=True)

COLS      = 4
to_remove = None
tickers   = st.session_state.tickers
rows      = [tickers[i:i+COLS] for i in range(0, len(tickers), COLS)]

for row in rows:
    cols = st.columns(COLS, gap="small")
    for j, ticker in enumerate(row):
        with cols[j]:
            p    = price_map.get(ticker, {})
            name = KNOWN.get(ticker, p.get("company", ticker))

            if p:
                close = p["close"]
                chg   = p["change_pct"]
                rsi   = p["rsi"]

                chg_sign = "+" if chg >= 0 else ""
                card_cls = "up" if chg >= 0 else "down"
                chg_cls  = "up" if chg >= 0 else "down"

                # MA 상태 — MA별 개별 체크로 정확한 설명·색상 결정
                _ma20  = p.get("ma20")
                _ma50  = p.get("ma50")
                _ma200 = p.get("ma200")
                above_ma20  = _ma20  is not None and close > _ma20
                above_ma50  = _ma50  is not None and close > _ma50
                above_ma200 = _ma200 is not None and close > _ma200
                above = sum([above_ma20, above_ma50, above_ma200])
                _above_list = [m for m, a in [("MA20", above_ma20), ("MA50", above_ma50), ("MA200", above_ma200)] if a]
                _below_list = [m for m, a in [("MA20", above_ma20), ("MA50", above_ma50), ("MA200", above_ma200)] if not a]
                if above == 3:
                    ma_desc = "종가 &gt; MA20, MA50, MA200"
                    ma_col  = "#00E676"
                elif above == 0:
                    ma_desc = "종가 &lt; MA20, MA50, MA200 모두"
                    ma_col  = "#FF5252"
                else:
                    _as = ", ".join(_above_list)
                    _bs = ", ".join(_below_list)
                    ma_desc = f"종가 &gt; {_as} &nbsp;<span style='opacity:.55'>({_bs} 아래)</span>"
                    ma_col  = "#FFB300" if above >= 1 else "#FF5252"

                rsi_col = "#FF5252" if rsi >= 70 else ("#00E676" if rsi <= 35 else "rgba(255,255,255,0.7)")

                # v2.0 판정1 + 판정2
                sk1, v1_lbl, v1_color = trading_stage_v2(p)
                sk2, v2_lbl, v2_color = trading_stage2_v2(p)
                v1_cls = stage_pill_cls(sk1)
                v2_cls = stage_pill_cls(sk2)

                # QQQ MA200 필터 상태
                qqq_above = p.get('qqq_above_ma200', True)
                qqq_txt   = 'MA200↑' if qqq_above else 'MA200↓'
                qqq_col   = '#00E676' if qqq_above else '#FF5252'

                # 1차 조건 신호 힌트
                signal_hint = get_signal_hint(p)

                st.markdown(f"""
                <div class="ticker-card {card_cls}">
                  <div class="ticker-top">
                    <div>
                      <div class="ticker-symbol">{ticker}</div>
                      <div class="ticker-exchange">{name}</div>
                    </div>
                    <div class="price-badge">
                      <div class="price-val">${close:,.2f}</div>
                      <span class="price-chg {chg_cls}">{chg_sign}{chg:.2f}%</span>
                    </div>
                  </div>
                  <hr class="ticker-divider">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                    <div>
                      <div class="ts-lbl" style="margin-bottom:4px;text-align:left">판정1 시장필터</div>
                      <span class="timing-pill {v1_cls}" style="color:{v1_color}">{v1_lbl}</span>
                    </div>
                    <div style="text-align:right">
                      <div class="ts-lbl" style="margin-bottom:4px">판정2 기술신호</div>
                      <span class="timing-pill {v2_cls}" style="color:{v2_color}">{v2_lbl}</span>
                    </div>
                  </div>
                  <div class="ticker-stats">
                    <div class="ts-item">
                      <div class="ts-val" style="color:{rsi_col}">{rsi:.0f}</div>
                      <div class="ts-lbl">RSI</div>
                    </div>
                    <div class="ts-item">
                      <div class="ts-val" style="color:{qqq_col}">{qqq_txt}</div>
                      <div class="ts-lbl">QQQ MA200</div>
                    </div>
                  </div>
                  <div style="font-size:11px;color:{ma_col};margin-top:7px;
                              padding:5px 8px;border-radius:5px;
                              background:rgba(255,255,255,0.04);
                              border-left:2px solid {ma_col};">
                    {ma_desc}
                  </div>
                  {signal_hint}
                </div>

                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="ticker-card-empty">
                  <div class="ticker-symbol-empty">{ticker}</div>
                  <div class="no-data-label">{KNOWN.get(ticker, "")}</div>
                  <div class="no-data-label" style="margin-top:8px">데이터 없음 — 다음 실행 후 표시</div>
                </div>
                """, unsafe_allow_html=True)

            btn_col, del_col = st.columns([1, 1], gap="small")
            with btn_col:
                st.link_button("📊 리포트", f"{PAGES_URL}/{ticker}.html", use_container_width=True)
            with del_col:
                if st.button("✕ 삭제", key=f"del_{ticker}", use_container_width=True):
                    to_remove = ticker

if to_remove:
    st.session_state.tickers.remove(to_remove)
    ok, msg = save_tickers(st.session_state.tickers, st.session_state.sha)
    _, new_sha = load_tickers()
    st.session_state.sha = new_sha
    st.session_state.toast = ("success" if ok else "error",
                               f"**{to_remove}** 삭제 완료 — {msg}")
    st.rerun()


# ══════════════════════════════════════════════════════════════════
#  종목 추가 + 실행 버튼
# ══════════════════════════════════════════════════════════════════
st.write("")
st.markdown('<div class="section-label">종목 추가 · 실행</div>', unsafe_allow_html=True)

st.markdown("""
<style>
/* 종목 추가 행: 버튼을 입력창 하단에 맞춤 */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stTextInput"]) {
    align-items: flex-end !important;
}
</style>
""", unsafe_allow_html=True)

col_in, col_add, col_run, col_report = st.columns([3, 1, 1.2, 1.4], gap="small")

with col_in:
    new_t = st.text_input(
        "ticker_input",
        placeholder="종목 코드 입력  (예: NFLX, AMD, COIN ...)",
        label_visibility="collapsed",
    ).upper().strip()

with col_add:
    add_btn = st.button("＋ 추가", type="primary", use_container_width=True)

with col_run:
    run_btn = st.button("▶ 지금 실행", use_container_width=True)

with col_report:
    st.link_button("📊 레포트 보기", PAGES_URL, use_container_width=True)

if add_btn:
    if not new_t:
        st.warning("종목 코드를 입력하세요.")
    elif new_t in st.session_state.tickers:
        st.warning(f"**{new_t}** 은(는) 이미 등록된 종목입니다.")
    elif len(st.session_state.tickers) >= 20:
        st.warning("종목은 최대 20개까지 등록할 수 있습니다.")
    else:
        with st.spinner(f"**{new_t}** 유효성 확인 중..."):
            valid = validate_ticker(new_t)
        if not valid:
            st.error(f"❌ **{new_t}** — Yahoo Finance에서 데이터를 찾을 수 없는 티커입니다. 종목 코드를 확인해 주세요.")
        else:
            st.session_state.tickers.append(new_t)
            ok, msg = save_tickers(st.session_state.tickers, st.session_state.sha)
            _, new_sha = load_tickers()
            st.session_state.sha = new_sha
            st.session_state.toast = ("success" if ok else "error",
                                       f"**{new_t}** 추가 완료 — {msg}")
            st.rerun()

if run_btn:
    ok, msg = trigger_workflow()
    if ok:
        st.session_state.polling     = True
        st.session_state.run_id_seen = None
        get_latest_run.clear()
        st.session_state.toast = ("success", "🚀 리포트 생성 시작 — 완료되면 자동으로 데이터가 갱신됩니다")
    else:
        st.session_state.toast = ("error", f"❌ {msg}")
    st.rerun()


# ══════════════════════════════════════════════════════════════════
#  실행 상태 + 폴링
# ══════════════════════════════════════════════════════════════════
st.write("")
st.markdown('<div class="section-label">실행 상태</div>', unsafe_allow_html=True)

run_info = get_latest_run()
status_placeholder = st.empty()

if run_info:
    raw_status = run_info["status"]       # queued / in_progress / completed
    conclusion = run_info["conclusion"]   # success / failure / None

    is_running = raw_status in ("queued", "in_progress")

    if is_running:
        # 실행 중 — 애니메이션 카드
        label = "대기 중..." if raw_status == "queued" else "실행 중..."
        status_placeholder.markdown(f"""
        <div class="run-card" style="border-color:rgba(255,179,0,0.3);background:rgba(255,179,0,0.05)">
          <div class="run-icon">⏳</div>
          <div style="flex:1">
            <div class="run-info-title">
              <span class="run-status-prog">{label}</span>
              &nbsp;·&nbsp; {run_info['date']} UTC
            </div>
            <div class="run-info-sub">yfinance 데이터 수집 → PDF 생성 → Telegram 전송 (약 3~5분 소요)</div>
          </div>
          <a href="{run_info['url']}" target="_blank"
             style="color:rgba(255,179,0,0.6);font-size:12px;text-decoration:none;white-space:nowrap">
            로그 보기 →
          </a>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.polling = True

    elif conclusion == "success":
        # 방금 완료됐고 아직 데이터 미갱신이면 갱신
        if st.session_state.polling and st.session_state.run_id_seen != run_info["id"]:
            st.session_state.run_id_seen  = run_info["id"]
            st.session_state.polling      = False
            st.session_state.price_map    = {}   # 캐시 클리어 → 다음 렌더에서 재로드
            st.session_state.force_reload = True
            st.session_state.toast = ("success", "✅ 리포트 완료 — 종목 데이터가 최신으로 갱신됐습니다")
            st.rerun()

        status_placeholder.markdown(f"""
        <div class="run-card" style="border-color:rgba(0,200,83,0.3);background:rgba(0,200,83,0.04)">
          <div class="run-icon">✅</div>
          <div style="flex:1">
            <div class="run-info-title">
              <span class="run-status-ok">완료</span>
              &nbsp;·&nbsp; {run_info['date']} UTC
            </div>
            <div class="run-info-sub">PDF 생성 및 Telegram 전송 완료 · 종목 카드 데이터 최신 반영됨</div>
          </div>
          <a href="{run_info['url']}" target="_blank"
             style="color:rgba(0,200,83,0.6);font-size:12px;text-decoration:none;white-space:nowrap">
            로그 보기 →
          </a>
        </div>
        """, unsafe_allow_html=True)

    else:
        # 실패
        status_placeholder.markdown(f"""
        <div class="run-card" style="border-color:rgba(211,47,47,0.3);background:rgba(211,47,47,0.04)">
          <div class="run-icon">❌</div>
          <div style="flex:1">
            <div class="run-info-title">
              <span class="run-status-fail">실패</span>
              &nbsp;·&nbsp; {run_info['date']} UTC
            </div>
            <div class="run-info-sub">오류 발생 — 로그에서 원인을 확인하세요</div>
          </div>
          <a href="{run_info['url']}" target="_blank"
             style="color:rgba(211,47,47,0.6);font-size:12px;text-decoration:none;white-space:nowrap">
            로그 보기 →
          </a>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.polling = False

else:
    status_placeholder.markdown("""
    <div class="run-card">
      <div class="run-icon">⚪</div>
      <div><div class="run-info-title" style="color:rgba(255,255,255,0.55)">실행 기록 없음</div></div>
    </div>
    """, unsafe_allow_html=True)

# 폴링 중이면 15초마다 자동 새로고침 (UI 블로킹 없음)
if st.session_state.polling:
    st_autorefresh(interval=15_000, key="workflow_poller")

st.write("")
st.markdown(
    '<div style="font-size:11px;color:rgba(255,255,255,0.50);text-align:center;padding-bottom:16px">'
    '종목 변경 후 내일 오전 9시에 자동 반영 · 즉시 적용하려면 ▶ 지금 실행 클릭'
    '</div>',
    unsafe_allow_html=True,
)
