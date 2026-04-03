#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_html.py — v5.2 캐시 데이터로 HTML 리포트 생성
Usage:
  python render_html.py              # 전체 종목
  python render_html.py NVDA         # 특정 종목
  python render_html.py --open       # 생성 후 브라우저 열기
"""

import os, sys, json, datetime, shutil

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("[ERROR] jinja2 미설치. pip install jinja2")
    sys.exit(1)

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH   = os.path.join(ROOT, 'cowork_agents', 'mag7_data.json')
TEMPLATE_DIR = os.path.join(ROOT, 'templates')
OUTPUT_DIR   = os.path.join(ROOT, 'docs')

sys.path.insert(0, os.path.join(ROOT, 'cowork_agents'))
from report_engine import (trading_signal, calc_exit_signal,
                           _stage_reason2, build_chart, _market_filter,
                           get_condition_breakdown, _get_strategy_type,
                           S_3RD_BUY, S_2ND_BUY, S_1ST_BUY, S_WATCH,
                           S_HOLD, S_CASH, S_BOND_WATCH,
                           E_TOP, E_TP2, E_TP1)

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

_DARK_TO_LIGHT = {
    '#34D399': '#059669', '#F87171': '#dc2626',
    '#FBBF24': '#d97706', '#A8C4DE': '#475569', '#EEF4FB': '#334155',
}
def color_for_print(dark_hex):
    return _DARK_TO_LIGHT.get(dark_hex, '#334155')


def get_badge_class(sk):
    return {
        S_3RD_BUY:    'entry3',
        S_2ND_BUY:    'entry2',
        S_1ST_BUY:    'entry1',
        S_WATCH:      'watch',
        S_HOLD:       'watch',
        S_CASH:       'watch',
        S_BOND_WATCH: 'entry1',
        # 하위호환
        'entry3': 'entry3', 'entry2': 'entry2', 'entry1': 'entry1',
        'caution_market': 'caution', 'watch_market': 'sell',
    }.get(sk, 'watch')


def get_exit_badge_class(ex_name):
    return {
        E_TOP: 'exit-hot',
        E_TP2: 'exit-break',
        E_TP1: 'exit-weak',
        # 하위호환 (숫자)
        99: 'exit-hot', 3: 'exit-break', 2: 'exit-weak', 1: 'exit-warn',
    }.get(ex_name, '')


def get_stype_label(d):
    stype = _get_strategy_type(d)
    return {
        'etf': 'ETF v2.4', 'energy': '에너지 v2.3', 'growth': '성장주 v2.3',
        'value': '가치주 v2.4', 'bond': '채권 v2.6', 'metal': '금속 v2.6',
        'speculative': '투기 v2.3', 'bil': '현금성',
    }.get(stype, 'v2.3')


def get_market_banner(d):
    ms = _market_filter(d)
    if ms == 'bear':
        return {'text': '하락장 — QQQ·SPY 모두 MA200 아래', 'color': '#EF5350', 'icon': '🚫'}
    elif ms == 'caution':
        return {'text': '경계장 — QQQ/SPY 중 하나만 MA200 위', 'color': '#FFA726', 'icon': '⚠️'}
    return {'text': '정상장 — QQQ·SPY 모두 MA200 위', 'color': '#00E676', 'icon': '✅'}


def build_metrics(d, sk):
    c = d['close']; m20 = d['ma20']; rsi = d['rsi']
    macd = d['macd']; macd_s = d.get('macd_signal', 0)
    vol = d.get('volume', 0); avg_v = d.get('avg_volume', 1)
    h52 = d.get('high_52w', c * 1.3)
    return [
        {'label': 'RSI (14)', 'value': f'{rsi:.1f}',
         'color': '#34D399' if rsi <= 35 else '#F87171' if rsi >= 70 else '#EEF4FB',
         'direction': '과매도' if rsi <= 30 else '과매수' if rsi >= 70 else '중립'},
        {'label': 'MA20', 'value': f'${m20:.2f}',
         'color': '#34D399' if c > m20 else '#F87171',
         'direction': '위' if c > m20 else '아래'},
        {'label': 'MACD', 'value': f'{macd:.3f}',
         'color': '#34D399' if macd > macd_s else '#F87171',
         'direction': '골든크로스' if macd > macd_s else '데드크로스'},
        {'label': '거래량 비율', 'value': f'{vol/max(avg_v,1):.1f}x',
         'color': '#34D399' if vol > avg_v else '#A8C4DE',
         'direction': '평균 이상' if vol > avg_v else '평균 이하'},
        {'label': '52주 고점 대비', 'value': f'-{(1-c/h52)*100:.1f}%',
         'color': '#F87171' if c >= h52*0.82 else '#FBBF24' if c >= h52*0.65 else '#34D399',
         'direction': '고점권' if c >= h52*0.82 else '중간권' if c >= h52*0.65 else '저점권'},
        {'label': 'Drawdown 20D', 'value': f'{d.get("drawdown_20d_pct", 0):.1f}%',
         'color': '#34D399' if d.get('drawdown_20d_pct', 0) > -5 else '#F87171',
         'direction': '고점근처' if d.get('drawdown_20d_pct', 0) > -5 else '하락중'},
    ]


def build_action(d, sk):
    c = d['close']; m20 = d.get('ma20', c); m50 = d.get('ma50', c)

    actions = {
        S_HOLD: {
            'wait_title': '지금은 기다리는 게 맞아요',
            'wait_cond': '진입 조건이 채워지지 않았어요. 서두르지 않아도 됩니다',
            'confirm_title': '이런 신호가 오면 주목하세요',
            'confirm_cond': f'RSI 38 이하 + 하락 멈춤 + MA20(${m20:.2f}) 아래 진입 시 1st BUY 검토',
            'stop_title': '보유 중이라면', 'stop_cond': 'HOLD — 하락장에서는 절대 매도하지 않음 (손절 없음)',
        },
        S_WATCH: {
            'wait_title': '관찰 중 — 조건 일부 충족',
            'wait_cond': '진입 조건 일부가 충족되었습니다. 추가 확인 후 1st BUY 전환 대기',
            'confirm_title': '이런 신호가 오면 진입',
            'confirm_cond': f'RSI ≤ 38 + MA20 이탈 + MACD hist 2일 증가 확인 시 1st BUY',
            'stop_title': '보유 중이라면', 'stop_cond': 'HOLD 유지',
        },
        S_1ST_BUY: {
            'wait_title': '1st BUY (자금의 20%)',
            'wait_cond': f'현재가 ${c:.2f} 근처에서 소액 분할 진입 — 추가 하락 여지를 남겨두세요',
            'confirm_title': '2nd BUY 신호를 기다리세요',
            'confirm_cond': '이중바닥 확인 + RSI 35 돌파 + MACD 골든크로스 시 2nd BUY(30%) 추가 진입',
            'stop_title': '익절 기준', 'stop_cond': 'Exit 시그널(TOP/TP2/TP1) 발동 시 익절',
        },
        S_2ND_BUY: {
            'wait_title': '2nd BUY (자금의 30%)',
            'wait_cond': f'이중바닥 + RSI 반등 + MACD 골든 확인 — ${c:.2f} 근처에서 비중 확대',
            'confirm_title': '3rd BUY 신호를 준비하세요',
            'confirm_cond': f'종가가 MA20(${m20:.2f}) 위 + MACD 0선 돌파 + RSI>55 시 3rd BUY(50%)',
            'stop_title': '익절 기준', 'stop_cond': 'Exit 시그널 발동 시 익절 — 손절 없음, HOLD로 버팀',
        },
        S_3RD_BUY: {
            'wait_title': '3rd BUY (자금의 50%)',
            'wait_cond': f'추세 전환 확인 — MA20 위 + MACD 0선 돌파 + RSI>55로 본격 상승 진입',
            'confirm_title': '목표가와 비중을 점검하세요',
            'confirm_cond': f'MA50(${m50:.2f}) 돌파 시 추가 상승 기대 — 익절 시그널로 수익 실현 준비',
            'stop_title': '익절 기준', 'stop_cond': 'TOP_SIGNAL/TAKE_PROFIT 발동 시 분할 익절',
        },
    }
    return actions.get(sk, actions[S_HOLD])


def render(target_tickers=None, open_browser=False):
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
    nav_stocks  = [{'ticker': d['ticker']} for d in stocks_all]

    # 시장 배너 (첫 번째 종목 기준)
    market_banner = get_market_banner(stocks_all[0]) if stocks_all else None

    # 요약 계산
    summary_stocks = []
    for d in stocks_all:
        sk, lbl, _ = trading_signal(d)
        try:
            reason = _stage_reason2(d, sk)
        except Exception:
            reason = lbl
        ex_name, ex_lbl, _, ex_detail = calc_exit_signal(d)
        streak_ann = d.get('streak_annotation', '')
        summary_stocks.append({
            'ticker':    d['ticker'],
            'sk':        get_badge_class(sk), 'lbl': lbl, 'reason': reason,
            'sk1':       get_badge_class(sk), 'lbl1': lbl, 'reason1': reason,
            'sk2':       get_badge_class(sk), 'lbl2': lbl, 'reason2': reason,
            'close':     d['close'],
            'chg':       d.get('change_pct', 0.0),
            'rsi':       d['rsi'],
            'ex_level':  1 if ex_name else 0,
            'ex_name':   ex_name or '',
            'ex_lbl':    ex_lbl,
            'ex_cls':    get_exit_badge_class(ex_name),
            'ex_detail': ex_detail,
            'stype_lbl': get_stype_label(d),
            'streak':    streak_ann,
        })

    # 요약 페이지
    tmpl = env.get_template('summary.html')
    html = tmpl.render(today_str=today_str, stocks=summary_stocks,
                       report_date=report_date, market_banner=market_banner)
    out = os.path.join(OUTPUT_DIR, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [HTML] index.html 생성 완료")

    # 종목별 페이지
    tmpl = env.get_template('stock.html')
    for d in stocks_all:
        sk, lbl, _ = trading_signal(d)
        c = d['close']; h52 = d.get('high_52w', c*1.3); l52 = d.get('low_52w', c*0.7)
        rng = max(h52 - l52, 0.01)
        pos_pct = max(0.0, min(1.0, (c - l52) / rng))
        chart_fn = f"{d['ticker']}_chart.png"
        chart_path = (f"charts/{chart_fn}"
                      if os.path.exists(os.path.join(charts_dst, chart_fn)) else None)
        try:
            reason = _stage_reason2(d, sk)
        except Exception:
            reason = lbl
        try:
            breakdown = get_condition_breakdown(d)
        except Exception:
            breakdown = None
        ex_name, ex_lbl, _, ex_detail = calc_exit_signal(d)
        streak_ann = d.get('streak_annotation', '')
        html = tmpl.render(
            d=d,
            sk1=get_badge_class(sk), lbl1=lbl, stage_desc1=reason,
            sk2=get_badge_class(sk), lbl2=lbl, stage_desc2=reason,
            today_str=today_str,
            action=build_action(d, sk),
            chart_path=chart_path,
            metrics=build_metrics(d, sk),
            pos_pct=pos_pct,
            stocks=nav_stocks,
            breakdown=breakdown,
            ex_level=1 if ex_name else 0,
            ex_lbl=ex_lbl,
            ex_cls=get_exit_badge_class(ex_name),
            ex_detail=ex_detail,
            stype_lbl=get_stype_label(d),
            market_banner=get_market_banner(d),
            streak=streak_ann,
        )
        out = os.path.join(OUTPUT_DIR, f"{d['ticker']}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  [HTML] {d['ticker']}.html 생성 완료")

    # print-all 페이지
    stocks_detail = []
    for d in stocks_all:
        sk, lbl, _ = trading_signal(d)
        c = d['close']; h52 = d.get('high_52w', c*1.3); l52 = d.get('low_52w', c*0.7)
        rng = max(h52 - l52, 0.01); pos_pct = max(0.0, min(1.0, (c - l52) / rng))
        chart_fn = f"{d['ticker']}_chart.png"
        chart_path = (f"charts/{chart_fn}"
                      if os.path.exists(os.path.join(charts_dst, chart_fn)) else None)
        try:
            reason = _stage_reason2(d, sk)
        except Exception:
            reason = lbl
        raw_metrics = build_metrics(d, sk)
        for m in raw_metrics:
            m['color_print'] = color_for_print(m['color'])
        try:
            breakdown = get_condition_breakdown(d)
        except Exception:
            breakdown = None
        ex_name, ex_lbl, _, ex_detail = calc_exit_signal(d)
        stocks_detail.append({
            'ticker': d['ticker'], 'company': d.get('company', d['ticker']),
            'exchange': d.get('exchange', ''), 'sector': d.get('sector', ''),
            'close': c, 'chg': d.get('change_pct', 0.0),
            'high_52w': h52, 'low_52w': l52, 'pos_pct': pos_pct,
            'sk1': get_badge_class(sk), 'lbl1': lbl, 'stage_desc1': reason,
            'sk2': get_badge_class(sk), 'lbl2': lbl, 'stage_desc2': reason,
            'metrics': raw_metrics, 'action': build_action(d, sk),
            'chart_path': chart_path, 'breakdown': breakdown,
            'ex_level': 1 if ex_name else 0, 'ex_lbl': ex_lbl,
            'ex_cls': get_exit_badge_class(ex_name), 'ex_detail': ex_detail,
            'stype_lbl': get_stype_label(d), 'streak': d.get('streak_annotation', ''),
        })

    tmpl = env.get_template('print_all.html')
    html = tmpl.render(today_str=today_str, stocks=summary_stocks,
                       stocks_detail=stocks_detail, market_banner=market_banner)
    out = os.path.join(OUTPUT_DIR, 'print-all.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [HTML] print-all.html 생성 완료")

    index = os.path.join(OUTPUT_DIR, 'index.html')
    print(f"\n  [완료] docs/ → {len(stocks_all)+2}개 HTML 파일")
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
