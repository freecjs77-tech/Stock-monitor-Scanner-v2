#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_html.py — 캐시 데이터로 HTML 리포트 생성
Usage:
  python render_html.py              # 전체 7종목
  python render_html.py NVDA         # 특정 종목
  python render_html.py --open       # 생성 후 브라우저 열기
"""

import os, sys, json, datetime, shutil

# Jinja2 확인
try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("[ERROR] jinja2 미설치. pip install jinja2")
    sys.exit(1)

# 프로젝트 루트
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH   = os.path.join(ROOT, 'cowork_agents', 'mag7_data.json')
TEMPLATE_DIR = os.path.join(ROOT, 'templates')
OUTPUT_DIR   = os.path.join(ROOT, 'docs')   # GitHub Pages는 docs/ 사용

sys.path.insert(0, os.path.join(ROOT, 'cowork_agents'))
from report_engine import trading_stage, trading_stage2, auto_score, _stage_reason, _stage_reason2, build_chart

# Jinja2 환경
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

def get_badge_class(sk):
    return {
        'entry3': 'buy',
        'entry2': 'entry',
        'entry1': 'entry',
        'watch_market': 'sell',
    }.get(sk, 'watch')

def get_stage_desc(d, sk, lbl):
    c    = d['close']
    m20  = d['ma20']
    rsi  = d['rsi']
    desc_map = {
        'buy':      f'MA20(${m20:.2f}) 돌파 + MACD 골든크로스 + 거래량 동반 — 적극 매수 구간',
        'entry':    f'과매도 탈출 초기 신호 — RSI {rsi:.1f}, 소액 분할 진입 고려',
        'sell':     f'고점 과열 또는 약세 전환 — 수익 30~50% 현금화 권장',
        'sell_div': f'약세 다이버전스 발생 — 최우선 매도 경고',
        'watch':    f'아직 진입 신호 없음 — 현금 보유 대기',
    }
    return desc_map.get(sk, '신호 대기 중')

def build_metrics(d, sk):
    c      = d['close']
    m20    = d['ma20']
    m200   = d.get('ma200', 0)
    rsi    = d['rsi']
    macd   = d['macd']
    macd_s = d.get('macd_signal', 0)
    vol    = d.get('volume', 0)
    avg_v  = d.get('avg_volume', 1)
    h52    = d.get('high_52w', c * 1.3)
    stop   = m20 * 0.97

    return [
        {'label': 'RSI (14)',      'value': f'{rsi:.1f}',
         'color': '#34D399' if rsi <= 35 else '#F87171' if rsi >= 70 else '#EEF4FB',
         'direction': '과매도' if rsi <= 30 else '과매수' if rsi >= 70 else '중립'},
        {'label': 'MA20',          'value': f'${m20:.2f}',
         'color': '#34D399' if c > m20 else '#F87171',
         'direction': '위' if c > m20 else '아래'},
        {'label': 'MACD',          'value': f'{macd:.3f}',
         'color': '#34D399' if macd > macd_s else '#F87171',
         'direction': '골든크로스' if macd > macd_s else '데드크로스'},
        {'label': '거래량 비율',   'value': f'{vol/max(avg_v,1):.1f}x',
         'color': '#34D399' if vol > avg_v else '#A8C4DE',
         'direction': '평균 이상' if vol > avg_v else '평균 이하'},
        {'label': '52주 고점 대비','value': f'-{(1-c/h52)*100:.1f}%',
         'color': '#F87171' if c >= h52*0.82 else '#FBBF24' if c >= h52*0.65 else '#34D399',
         'direction': '고점권' if c >= h52*0.82 else '중간권' if c >= h52*0.65 else '저점권'},
        {'label': '손절 기준',     'value': f'${stop:.2f}',
         'color': '#EEF4FB',
         'direction': 'MA20 -3%'},
    ]

def build_action(d, sk):
    c    = d['close']
    m20  = d['ma20']
    rsi  = d['rsi']
    h52  = d.get('high_52w', c*1.3)
    stop = m20 * 0.97

    watch_default = {
        'wait_title':    '지금은 기다리는 게 맞아요',
        'wait_cond':     '아직 진입 신호가 안 왔어요. 서두르지 않아도 됩니다',
        'confirm_title': '더 확신이 서려면',
        'confirm_cond':  'MACD가 위로 꺾이고 거래량까지 늘어날 때 진입하면 더 안전해요',
        'stop_title':    '이미 갖고 있다면',
        'stop_cond':     f'${stop:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
    }

    actions = {
        'buy': {
            'wait_title':    '이럴 때 들어가세요',
            'wait_cond':     f'${c:.2f} 위로 올라서거나, RSI가 30 이하로 떨어질 때',
            'confirm_title': '더 확신이 서려면',
            'confirm_cond':  'MACD가 위로 꺾이고 거래량까지 늘어날 때 진입하면 더 안전해요',
            'stop_title':    '이미 갖고 있다면',
            'stop_cond':     f'${stop:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
        },
        'entry': {
            'wait_title':    '이럴 때 들어가세요',
            'wait_cond':     f'RSI가 더 내려오거나, 하락이 멈추는 신호가 보일 때 소액 진입',
            'confirm_title': '더 확신이 서려면',
            'confirm_cond':  f'MA20(${m20:.2f}) 위로 종가가 올라서면 2단계 진입 고려',
            'stop_title':    '이미 갖고 있다면',
            'stop_cond':     f'${stop:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
        },
        'sell': {
            'wait_title':    '지금은 기다리는 게 맞아요',
            'wait_cond':     '이미 진입 신호가 아니에요. 서두르지 않아도 됩니다',
            'confirm_title': '더 확신이 서려면',
            'confirm_cond':  f'MA20(${m20:.2f}) 아래 유지 + RSI 하락세 지속 확인 후 추가 매도',
            'stop_title':    '이미 갖고 있다면',
            'stop_cond':     f'${stop:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
        },
        'sell_div': {
            'wait_title':    '매도를 우선 고려하세요',
            'wait_cond':     '약세 다이버전스 발생 — 추가 상승보다 하락 위험이 높습니다',
            'confirm_title': '더 확신이 서려면',
            'confirm_cond':  f'MA20(${m20:.2f}) 아래로 종가 이탈 시 추가 매도 신호',
            'stop_title':    '이미 갖고 있다면',
            'stop_cond':     f'${stop:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
        },
    }
    return actions.get(sk, watch_default)

def render(target_tickers=None, open_browser=False):
    # 캐시 로드
    if not os.path.exists(CACHE_PATH):
        print(f"[ERROR] 캐시 없음: {CACHE_PATH}")
        sys.exit(1)
    with open(CACHE_PATH, encoding='utf-8') as f:
        cache = json.load(f)

    stocks_all = cache.get('stocks', [])
    if target_tickers:
        stocks_all = [d for d in stocks_all if d['ticker'] in target_tickers]

    if not stocks_all:
        print(f"[ERROR] 종목 없음. 티커 확인: {target_tickers}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 차트 직접 생성 → docs/charts/
    charts_dst = os.path.join(OUTPUT_DIR, 'charts')
    os.makedirs(charts_dst, exist_ok=True)
    for d in stocks_all:
        chart_fn  = f"{d['ticker']}_chart.png"
        chart_out = os.path.join(charts_dst, chart_fn)
        try:
            build_chart(d, chart_out)
            print(f"  [CHART] {d['ticker']} 생성 완료")
        except Exception as e:
            print(f"  [CHART] {d['ticker']} 실패: {e}")

    today_str   = datetime.date.today().strftime('%Y년 %m월 %d일')
    report_date = datetime.date.today().strftime('%Y%m%d')

    # 네비게이션용 전체 종목 리스트
    nav_stocks = [{'ticker': d['ticker']} for d in stocks_all]

    # 종목별 판정 계산
    summary_stocks = []
    for d in stocks_all:
        sk1, lbl1, _ = trading_stage(d)
        sk2, lbl2, _ = trading_stage2(d)
        try:
            reason1 = _stage_reason(d, sk1)
        except Exception:
            reason1 = lbl1
        try:
            reason2 = _stage_reason2(d, sk2)
        except Exception:
            reason2 = lbl2
        summary_stocks.append({
            'ticker':  d['ticker'],
            'sk1':     get_badge_class(sk1), 'lbl1': lbl1, 'reason1': reason1,
            'sk2':     get_badge_class(sk2), 'lbl2': lbl2, 'reason2': reason2,
            'close':   d['close'],
            'chg':     d.get('change_pct', d.get('chg_pct', 0.0)),
            'rsi':     d['rsi'],
        })

    # 요약 페이지
    tmpl = env.get_template('summary.html')
    html = tmpl.render(today_str=today_str, stocks=summary_stocks, report_date=report_date)
    out = os.path.join(OUTPUT_DIR, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [HTML] index.html 생성 완료")

    # 종목별 페이지
    tmpl = env.get_template('stock.html')
    for d in stocks_all:
        sk1, lbl1, _ = trading_stage(d)
        sk2, lbl2, _ = trading_stage2(d)
        c   = d['close']
        h52 = d.get('high_52w', c * 1.3)
        l52 = d.get('low_52w',  c * 0.7)
        rng = max(h52 - l52, 0.01)
        pos_pct = max(0.0, min(1.0, (c - l52) / rng))

        chart_fn   = f"{d['ticker']}_chart.png"
        chart_path = (f"charts/{chart_fn}"
                      if os.path.exists(os.path.join(charts_dst, chart_fn))
                      else None) if os.path.exists(charts_dst) else None

        try:
            stage_desc1 = get_stage_desc(d, sk1, lbl1)
            stage_desc2 = get_stage_desc(d, sk2, lbl2)
        except Exception:
            stage_desc1 = lbl1
            stage_desc2 = lbl2

        html = tmpl.render(
            d=d,
            sk1=get_badge_class(sk1), lbl1=lbl1, stage_desc1=stage_desc1,
            sk2=get_badge_class(sk2), lbl2=lbl2, stage_desc2=stage_desc2,
            today_str=today_str,
            action=build_action(d, sk2),   # 액션은 판정2(기술신호) 기준
            chart_path=chart_path,
            metrics=build_metrics(d, sk2),
            pos_pct=pos_pct,
            stocks=nav_stocks,
        )
        out = os.path.join(OUTPUT_DIR, f"{d['ticker']}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  [HTML] {d['ticker']}.html 생성 완료")

    index = os.path.join(OUTPUT_DIR, 'index.html')
    print(f"\n  [완료] docs/ → {len(stocks_all)+1}개 HTML 파일")
    print(f"  [URL]  file://{index}")

    if open_browser:
        import webbrowser
        webbrowser.open(f"file://{index}")

    return OUTPUT_DIR

if __name__ == '__main__':
    args   = sys.argv[1:]
    open_b = '--open' in args
    tickers = [a.upper() for a in args if not a.startswith('--')]
    render(tickers or None, open_browser=open_b)
