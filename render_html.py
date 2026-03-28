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
from report_engine import (trading_stage, trading_stage2, auto_score,
                           _stage_reason, _stage_reason2, build_chart,
                           get_condition_breakdown, calc_exit_signal, _get_strategy_type)

# Jinja2 환경
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

_DARK_TO_LIGHT = {
    '#34D399': '#059669',
    '#F87171': '#dc2626',
    '#FBBF24': '#d97706',
    '#A8C4DE': '#475569',
    '#EEF4FB': '#334155',
}
def color_for_print(dark_hex):
    return _DARK_TO_LIGHT.get(dark_hex, '#334155')

def get_badge_class(sk):
    return {
        'entry3':        'entry3',
        'entry2':        'entry2',
        'entry1':        'entry1',
        'caution_market':'caution',
        'watch_market':  'sell',
    }.get(sk, 'watch')

def get_exit_badge_class(level):
    return {99:'exit-hot', 3:'exit-break', 2:'exit-weak', 1:'exit-warn'}.get(level, '')

def get_stype_label(d):
    stype = _get_strategy_type(d)
    return {'etf':'ETF v2.4', 'energy':'에너지 v2.3', 'growth':'성장주 v2.2'}.get(stype, 'v2.2')

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
    """판정2 기준 v2.0 단계별 맞춤 액션 (entry1/entry2/entry3/watch/watch_market)"""
    c    = d['close']
    m20  = d.get('ma20', c)
    m50  = d.get('ma50', c)
    rsi  = d['rsi']
    stop_1 = c * 0.95          # 1차: -5% 손절
    stop_2 = m20 * 0.97        # 2·3차: MA20 -3% 손절

    actions = {
        # ── 관망: 조건 미충족 ──────────────────────────────────────
        'watch': {
            'wait_title':    '지금은 기다리는 게 맞아요',
            'wait_cond':     '아직 1차 매수 조건(6개 중 3개)이 채워지지 않았어요. 서두르지 않아도 됩니다',
            'confirm_title': '이런 신호가 오면 주목하세요',
            'confirm_cond':  f'RSI 38 이하 + 하락 멈춤 + MA20(${m20:.2f}) 아래 진입 시 1차 매수 검토',
            'stop_title':    '이미 갖고 있다면',
            'stop_cond':     f'${stop_2:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
        },
        # ── 시장 관망: QQQ MA200 아래 ─────────────────────────────
        'watch_market': {
            'wait_title':    '시장 전체가 약세예요 (판정1 기준)',
            'wait_cond':     'QQQ가 200일선 아래에 있어 매수 환경이 아닙니다. 현금 비중을 유지하세요',
            'confirm_title': '판정2 기술 신호는 참고만 하세요',
            'confirm_cond':  '시장 필터 제외 시 종목 자체 신호를 확인하려면 판정2를 참고하세요',
            'stop_title':    '이미 갖고 있다면',
            'stop_cond':     f'${stop_2:.2f} 아래로 내려가면 미련 없이 일부 정리하세요',
        },
        # ── 1차 매수: 자금의 20% ──────────────────────────────────
        'entry1': {
            'wait_title':    '1차 매수 타이밍이에요 (자금의 20%)',
            'wait_cond':     f'현재가 ${c:.2f} 근처에서 소액 분할 진입 — 추가 하락 여지를 남겨두세요',
            'confirm_title': '2차 매수 신호를 기다리세요',
            'confirm_cond':  f'이중 바닥 확인 + RSI 35 돌파 + 거래량 증가 시 2차(30%) 추가 진입',
            'stop_title':    '손절 기준',
            'stop_cond':     f'${stop_1:.2f} 아래로 내려가면 손절 — 진입가 대비 -5% 룰을 지키세요',
        },
        # ── 2차 매수: 자금의 30% ──────────────────────────────────
        'entry2': {
            'wait_title':    '2차 매수 타이밍이에요 (자금의 30%)',
            'wait_cond':     f'이중 바닥 + RSI 반등 + MACD 개선 확인 — ${c:.2f} 근처에서 비중 확대',
            'confirm_title': '3차 매수 신호를 준비하세요',
            'confirm_cond':  f'종가가 MA20(${m20:.2f}) 위로 2일 연속 마감 + MACD 0선 돌파 시 3차(50%) 진입',
            'stop_title':    '손절 기준',
            'stop_cond':     f'${stop_2:.2f} 아래로 내려가면 전량 손절 — MA20 -3% 이탈 시 포지션 정리',
        },
        # ── 3차 매수: 자금의 50% ──────────────────────────────────
        'entry3': {
            'wait_title':    '3차 매수 타이밍이에요 (자금의 50%)',
            'wait_cond':     f'추세 전환 확인 — MA20(${m20:.2f}) 위 안착 + MACD 0선 돌파로 본격 상승 진입',
            'confirm_title': '목표가와 비중을 점검하세요',
            'confirm_cond':  f'MA50(${m50:.2f}) 돌파 시 추가 상승 기대 — 분할 매도로 수익 실현 준비',
            'stop_title':    '손절 기준',
            'stop_cond':     f'${stop_2:.2f} 아래로 내려가면 전량 손절 — MA20 -3% 이탈 시 즉시 정리',
        },
    }

    watch_default = actions['watch']
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
        ex_level, ex_lbl, _, ex_detail = calc_exit_signal(d)
        summary_stocks.append({
            'ticker':     d['ticker'],
            'sk1':        get_badge_class(sk1), 'lbl1': lbl1, 'reason1': reason1,
            'sk2':        get_badge_class(sk2), 'lbl2': lbl2, 'reason2': reason2,
            'close':      d['close'],
            'chg':        d.get('change_pct', d.get('chg_pct', 0.0)),
            'rsi':        d['rsi'],
            'ex_level':   ex_level,
            'ex_lbl':     ex_lbl,
            'ex_cls':     get_exit_badge_class(ex_level),
            'ex_detail':  ex_detail,
            'stype_lbl':  get_stype_label(d),
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

        try:
            breakdown = get_condition_breakdown(d)
        except Exception:
            breakdown = None

        ex_level, ex_lbl, _, ex_detail = calc_exit_signal(d)
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
            breakdown=breakdown,
            ex_level=ex_level,
            ex_lbl=ex_lbl,
            ex_cls=get_exit_badge_class(ex_level),
            ex_detail=ex_detail,
            stype_lbl=get_stype_label(d),
        )
        out = os.path.join(OUTPUT_DIR, f"{d['ticker']}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  [HTML] {d['ticker']}.html 생성 완료")

    # 전체 리포트 PDF 저장용 페이지
    stocks_detail = []
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
                      else None)
        try:
            sd1 = get_stage_desc(d, sk1, lbl1)
            sd2 = get_stage_desc(d, sk2, lbl2)
        except Exception:
            sd1, sd2 = lbl1, lbl2
        raw_metrics = build_metrics(d, sk2)
        for m in raw_metrics:
            m['color_print'] = color_for_print(m['color'])
        try:
            breakdown = get_condition_breakdown(d)
        except Exception:
            breakdown = None
        ex_level2, ex_lbl2, _, ex_detail2 = calc_exit_signal(d)
        stocks_detail.append({
            'ticker':      d['ticker'],
            'company':     d.get('company', d['ticker']),
            'exchange':    d.get('exchange', ''),
            'sector':      d.get('sector', ''),
            'close':       c,
            'chg':         d.get('change_pct', d.get('chg_pct', 0.0)),
            'high_52w':    h52,
            'low_52w':     l52,
            'pos_pct':     pos_pct,
            'sk1':         get_badge_class(sk1), 'lbl1': lbl1, 'stage_desc1': sd1,
            'sk2':         get_badge_class(sk2), 'lbl2': lbl2, 'stage_desc2': sd2,
            'metrics':     raw_metrics,
            'action':      build_action(d, sk2),
            'chart_path':  chart_path,
            'breakdown':   breakdown,
            'ex_level':    ex_level2,
            'ex_lbl':      ex_lbl2,
            'ex_cls':      get_exit_badge_class(ex_level2),
            'ex_detail':   ex_detail2,
            'stype_lbl':   get_stype_label(d),
        })
    tmpl = env.get_template('print_all.html')
    html = tmpl.render(today_str=today_str, stocks=summary_stocks, stocks_detail=stocks_detail)
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
