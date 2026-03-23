#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Report Manager — Streamlit Web App
종목 관리 UI: 추가 / 삭제 / 즉시 실행 / 최근 실행 현황
"""

import streamlit as st
import json, os, base64, requests
from datetime import datetime

# ══════════════════════════════════════════════════════════════════
#  페이지 설정
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Stock Report Manager",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* 전체 배경 */
    .stApp { background-color: #F7F9FC; }

    /* 헤더 */
    .app-header {
        display: flex; align-items: center; gap: 10px;
        margin-bottom: 4px;
    }
    .app-title {
        font-size: 26px; font-weight: 800;
        color: #0D2137; letter-spacing: -0.5px;
    }
    .app-sub {
        font-size: 13px; color: #7F8C8D; margin-top: 2px;
    }

    /* 섹션 레이블 */
    .section-label {
        font-size: 13px; font-weight: 700;
        color: #5D6D7E; text-transform: uppercase;
        letter-spacing: 0.8px; margin-bottom: 10px;
    }

    /* 뱃지 */
    .badge {
        background: #1565C0; color: white;
        border-radius: 20px; padding: 2px 11px;
        font-size: 12px; font-weight: 700;
        vertical-align: middle; margin-left: 6px;
    }

    /* 종목 카드 */
    .ticker-card {
        background: white;
        border: 1.5px solid #E0E3EB;
        border-radius: 14px;
        padding: 16px 10px 10px 10px;
        text-align: center;
        margin-bottom: 4px;
        transition: box-shadow 0.2s;
    }
    .ticker-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.09); }
    .ticker-symbol {
        font-size: 21px; font-weight: 800;
        color: #0D2137; letter-spacing: 1.5px;
    }
    .ticker-name {
        font-size: 10px; color: #95A5A6;
        margin-top: 3px; line-height: 1.3;
        min-height: 28px;
    }

    /* 삭제 버튼 커스터마이즈 */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important;
        border: 1px solid #E0E3EB !important;
        color: #C0392B !important;
        font-size: 11px !important;
        padding: 2px 8px !important;
        border-radius: 6px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: #FEF0F0 !important;
        border-color: #C0392B !important;
    }

    /* 추가 버튼 */
    div[data-testid="stButton"] button[kind="primary"] {
        border-radius: 10px !important;
        font-weight: 700 !important;
    }

    /* 상태바 */
    .status-bar {
        background: white;
        border: 1px solid #E0E3EB;
        border-radius: 12px;
        padding: 12px 18px;
        font-size: 13px;
        color: #5D6D7E;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .status-ok   { color: #1B5E20; font-weight: 700; }
    .status-fail { color: #B71C1C; font-weight: 700; }
    .status-run  { color: #E65100; font-weight: 700; }

    /* divider */
    hr { border-color: #E8ECF0 !important; margin: 18px 0 !important; }

    /* input 스타일 */
    .stTextInput input {
        border-radius: 10px !important;
        border: 1.5px solid #E0E3EB !important;
        font-size: 14px !important;
    }
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
    'HD':'Home Depot', 'MCD':'McDonald\'s', 'SBUX':'Starbucks',
    'KO':'Coca-Cola', 'PEP':'PepsiCo', 'DIS':'Disney',
    'LLY':'Eli Lilly', 'MRNA':'Moderna', 'PFE':'Pfizer',
    'JNJ':'J&J', 'UNH':'UnitedHealth', 'ABBV':'AbbVie',
    'XOM':'ExxonMobil', 'CVX':'Chevron', 'BA':'Boeing',
    'GE':'GE Aerospace', 'F':'Ford', 'GM':'General Motors',
    'RIVN':'Rivian', 'LCID':'Lucid', 'NIO':'NIO',
    'BABA':'Alibaba', 'JD':'JD.com', 'HOOD':'Robinhood',
}


# ══════════════════════════════════════════════════════════════════
#  GitHub API
# ══════════════════════════════════════════════════════════════════
REPO       = "freecjs77-tech/mag7-stock-report"
TICKERS_F  = "tickers.json"
API_BASE   = f"https://api.github.com/repos/{REPO}"


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
            d = r.json()
            content = base64.b64decode(d["content"]).decode()
            parsed  = json.loads(content)
            return parsed.get("tickers", []), d.get("sha", "")
    except Exception:
        pass
    # fallback: local file
    if os.path.exists(TICKERS_F):
        with open(TICKERS_F) as f:
            d = json.load(f)
        return d.get("tickers", []), ""
    return ["NVDA","PLTR","TSLA","AAPL","MSFT","GOOGL","AMZN","META"], ""


def save_tickers(tickers, sha):
    content = json.dumps(
        {"tickers": tickers, "updated": datetime.today().strftime("%Y-%m-%d")},
        indent=2
    )
    encoded = base64.b64encode(content.encode()).decode()
    payload = {
        "message": f"[UI] Update tickers ({len(tickers)}): {', '.join(tickers)}",
        "content": encoded,
        "sha": sha,
    }
    try:
        r = requests.put(f"{API_BASE}/contents/{TICKERS_F}",
                         json=payload, headers=gh_headers(), timeout=15)
        if r.status_code in (200, 201):
            load_tickers.clear()
            return True, "✅ 저장 완료"
        return False, f"❌ 저장 실패 ({r.status_code})"
    except Exception as e:
        return False, f"❌ 연결 오류: {e}"


def trigger_workflow():
    try:
        r = requests.post(
            f"{API_BASE}/actions/workflows/daily_report.yml/dispatches",
            json={"ref": "main"},
            headers=gh_headers(), timeout=15
        )
        return r.status_code == 204, "워크플로우 실행 요청됨" if r.status_code == 204 else f"오류 ({r.status_code})"
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=60)
def load_last_run():
    try:
        r = requests.get(
            f"{API_BASE}/actions/workflows/daily_report.yml/runs?per_page=1",
            headers=gh_headers(), timeout=10
        )
        if r.status_code == 200:
            runs = r.json().get("workflow_runs", [])
            if runs:
                run = runs[0]
                return {
                    "date":   run["created_at"][:10],
                    "status": run["conclusion"] or "in_progress",
                    "url":    run["html_url"],
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
if "toast" not in st.session_state:
    st.session_state.toast = None


# ══════════════════════════════════════════════════════════════════
#  헤더
# ══════════════════════════════════════════════════════════════════
col_h, col_btn = st.columns([3, 1])
with col_h:
    st.markdown("""
    <div class="app-header">
        <span style="font-size:30px">📈</span>
        <div>
            <div class="app-title">Stock Report Manager</div>
            <div class="app-sub">매일 오전 9시 KST · Yahoo Finance 실시간 데이터</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_btn:
    st.write("")
    st.write("")
    if st.button("▶ 지금 실행", type="primary", use_container_width=True):
        ok, msg = trigger_workflow()
        st.session_state.toast = ("success" if ok else "error", f"{'🚀' if ok else '❌'} {msg}")
        load_last_run.clear()
        st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# 토스트 메시지
if st.session_state.toast:
    kind, msg = st.session_state.toast
    if kind == "success": st.success(msg)
    else:                 st.error(msg)
    st.session_state.toast = None


# ══════════════════════════════════════════════════════════════════
#  등록 종목 그리드
# ══════════════════════════════════════════════════════════════════
n = len(st.session_state.tickers)
st.markdown(
    f'<div class="section-label">등록 종목 <span class="badge">{n}</span></div>',
    unsafe_allow_html=True,
)

to_remove = None
COLS = 4
rows = [st.session_state.tickers[i:i+COLS] for i in range(0, n, COLS)]

for row in rows:
    cols = st.columns(COLS)
    for j, ticker in enumerate(row):
        with cols[j]:
            name = KNOWN.get(ticker, ticker)
            st.markdown(f"""
            <div class="ticker-card">
                <div class="ticker-symbol">{ticker}</div>
                <div class="ticker-name">{name}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("✕ 삭제", key=f"del_{ticker}",
                         use_container_width=True):
                to_remove = ticker

# 빈 열 채우기
remainder = n % COLS
if remainder:
    cols = st.columns(COLS)
    # already handled in last row above

# 삭제 처리
if to_remove:
    st.session_state.tickers.remove(to_remove)
    ok, msg = save_tickers(st.session_state.tickers, st.session_state.sha)
    # sha 갱신
    _, new_sha = load_tickers()
    st.session_state.sha = new_sha
    st.session_state.toast = ("success" if ok else "error",
                               f"**{to_remove}** 삭제 · {msg}")
    st.rerun()


# ══════════════════════════════════════════════════════════════════
#  종목 추가
# ══════════════════════════════════════════════════════════════════
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown('<div class="section-label">종목 추가</div>', unsafe_allow_html=True)

col_in, col_add = st.columns([3, 1])
with col_in:
    new_t = st.text_input(
        "ticker_input",
        placeholder="예) NFLX, AMD, COIN, AVGO ...",
        label_visibility="collapsed",
    ).upper().strip()
with col_add:
    add_btn = st.button("＋ 추가", type="primary", use_container_width=True)

if add_btn:
    if not new_t:
        st.warning("종목 코드를 입력하세요.")
    elif new_t in st.session_state.tickers:
        st.warning(f"**{new_t}** 은(는) 이미 등록된 종목입니다.")
    elif len(st.session_state.tickers) >= 20:
        st.warning("종목은 최대 20개까지 등록할 수 있습니다.")
    else:
        st.session_state.tickers.append(new_t)
        ok, msg = save_tickers(st.session_state.tickers, st.session_state.sha)
        _, new_sha = load_tickers()
        st.session_state.sha = new_sha
        st.session_state.toast = ("success" if ok else "error",
                                   f"**{new_t}** 추가 · {msg}")
        st.rerun()


# ══════════════════════════════════════════════════════════════════
#  최근 실행 상태
# ══════════════════════════════════════════════════════════════════
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown('<div class="section-label">최근 실행</div>', unsafe_allow_html=True)

run = load_last_run()
if run:
    s = run["status"]
    if s == "success":
        icon, cls, txt = "✅", "status-ok",   "완료"
    elif s == "failure":
        icon, cls, txt = "❌", "status-fail", "실패"
    elif s == "in_progress":
        icon, cls, txt = "⏳", "status-run",  "실행 중"
    else:
        icon, cls, txt = "⚪", "status-run",  s

    st.markdown(f"""
    <div class="status-bar">
        {icon}&nbsp;
        <span class="{cls}">{txt}</span>
        &nbsp;·&nbsp; {run['date']}
        &nbsp;·&nbsp; <a href="{run['url']}" target="_blank" style="color:#1565C0">로그 보기 →</a>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="status-bar">⚪ &nbsp; 실행 기록 없음</div>
    """, unsafe_allow_html=True)

st.write("")
st.caption("💡 종목 변경 후 내일 오전 9시에 자동 반영됩니다. 즉시 적용하려면 **▶ 지금 실행** 버튼을 누르세요.")
