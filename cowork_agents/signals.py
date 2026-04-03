#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signals.py -- v5.2 Signal Decision System (extracted from report_engine.py)

Signal constants, strategy classification, entry/exit signal functions,
condition breakdown helpers, and the BUY streak confirmation system.
"""

import os, json
from reportlab.lib import colors


# ══════════════════════════════════════════════════════════════════
#  v5.2 Signal Decision System
# ══════════════════════════════════════════════════════════════════

# ── 시그널 상수 ──────────────────────────────────────────────────
S_3RD_BUY    = '3rd_BUY'
S_2ND_BUY    = '2nd_BUY'
S_1ST_BUY    = '1st_BUY'
S_WATCH      = 'WATCH'
S_HOLD       = 'HOLD'
S_CASH       = 'CASH'
S_BOND_WATCH = 'BOND_WATCH'

E_TOP  = 'TOP_SIGNAL'
E_TP2  = 'TAKE_PROFIT_2'
E_TP1  = 'TAKE_PROFIT_1'

# 시그널별 색상
_SIGNAL_COLORS = {
    S_3RD_BUY:    '#00E676',
    S_2ND_BUY:    '#26C6DA',
    S_1ST_BUY:    '#FFEE58',
    S_WATCH:      '#B0BEC5',
    S_HOLD:       '#FFFFFF',
    S_CASH:       '#FFFFFF',
    S_BOND_WATCH: '#90CAF9',
    E_TOP:        '#FF1744',
    E_TP2:        '#EF5350',
    E_TP1:        '#FFA726',
}

# 시그널별 한글 라벨
_SIGNAL_LABELS = {
    S_3RD_BUY:    '3rd BUY (50%)',
    S_2ND_BUY:    '2nd BUY (30%)',
    S_1ST_BUY:    '1st BUY (20%)',
    S_WATCH:      'WATCH',
    S_HOLD:       'HOLD',
    S_CASH:       'CASH',
    S_BOND_WATCH: 'BOND WATCH',
}

def _sig_color(sk):
    return colors.HexColor(_SIGNAL_COLORS.get(sk, '#FFFFFF'))

def _sig_label(sk):
    return _SIGNAL_LABELS.get(sk, sk)

# ── 전략 유형 분류 (v5.2: 8종) ────────────────────────────────────
_BIL_LIST    = {'BIL'}
_BOND_LIST   = {'TLT'}
_METAL_LIST  = {'GLD', 'SLV'}
_VALUE_LIST  = {'O', 'UNH'}
_SPEC_LIST   = {'TQQQ', 'SOXL', 'CRCL', 'BTDR', 'ETHU'}
_ETF_LIST    = {'QQQ','SPY','VOO','SCHD','JEPI',
                'IWM','XLF','XLE','IYR','VNQ','HYG','LQD','TIP',
                'SQQQ','UVXY','QLD','SSO','UPRO'}
_ENERGY_LIST = {'XOM','CVX','OXY','COP','BP','SLB','EOG','MPC',
                'PSX','VLO','HAL','BKR','DVN','FANG'}

def _get_strategy_type(d):
    st = d.get('strategy_type', '')
    if st in ('etf','energy','growth','value','bond','metal','speculative','bil'):
        return st
    ticker = d.get('ticker','')
    if ticker in _BIL_LIST:    return 'bil'
    if ticker in _BOND_LIST:   return 'bond'
    if ticker in _METAL_LIST:  return 'metal'
    if ticker in _VALUE_LIST:  return 'value'
    if ticker in _SPEC_LIST:   return 'speculative'
    if ticker in _ETF_LIST:    return 'etf'
    if ticker in _ENERGY_LIST: return 'energy'
    return 'growth'


def _market_filter(d):
    """QQQ+SPY Dual MA200 시장 필터 → 'normal'|'caution'|'bear' (참고용)"""
    qqq = bool(d.get('qqq_above_ma200', True))
    spy = bool(d.get('spy_above_ma200', True))
    ms  = d.get('market_state', 'normal' if (qqq and spy) else 'caution' if (qqq or spy) else 'bear')
    return ms


# ── Entry 전략 함수들 (v5.2) ─────────────────────────────────────

def _signal_growth(d):
    """Growth v2.3 — NVDA, TSLA, PLTR, AAPL, MSFT, GOOGL, AMZN 등"""
    def sig(k): return bool(d.get(k, False))

    # 전 단계 거부: -5% 급락
    if sig('sig_block_5pct_drop_all'):
        return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))

    # 3rd BUY (50%) — ALL 4 + RSI>75 차단
    if not sig('sig_rsi_gt75_block'):
        cond3 = [
            sig('sig_above_ma20_2d') or (not sig('sig_below_ma20')),  # 종가 > MA20
            sig('sig_macd_above_zero') and sig('sig_macd_golden'),     # MACD>0 + 골든크로스
            sig('sig_vol_1p3') or sig('sig_vol_5d_2up'),               # 거래량 ≥ 1.3x
            sig('sig_rsi_gt55'),                                        # RSI > 55
        ]
        if all(cond3):
            return (S_3RD_BUY, _sig_label(S_3RD_BUY), _sig_color(S_3RD_BUY))

    # 2nd BUY (30%) — ALL 4
    cond2 = [
        sig('sig_double_bottom_diff_3pct'),  # 이중바닥 diff ≤ 3%
        sig('sig_rsi_gt35'),                  # RSI > 35
        sig('sig_macd_golden'),               # MACD > signal (필수)
        sig('sig_vol_1p2'),                   # 거래량 ≥ 1.2x
    ]
    if all(cond2):
        return (S_2ND_BUY, _sig_label(S_2ND_BUY), _sig_color(S_2ND_BUY))

    # 1st BUY (20%) — 필수 ALL 3 + 선택 2/3
    if not sig('sig_rsi_gt55_block'):  # RSI > 55 → 1st만 차단
        mandatory = [sig('sig_rsi_le38'), sig('sig_below_ma20'), sig('sig_macd_hist_2d_up')]
        optional  = [sig('sig_adx_le25'), sig('sig_near_bb_low'), sig('sig_bounce2pct')]
        if all(mandatory) and sum(optional) >= 2:
            return (S_1ST_BUY, _sig_label(S_1ST_BUY), _sig_color(S_1ST_BUY))

    # WATCH — 부분 조건 충족
    mandatory_cnt = sum([sig('sig_rsi_le38'), sig('sig_below_ma20'), sig('sig_macd_hist_2d_up')])
    optional_cnt  = sum([sig('sig_adx_le25'), sig('sig_near_bb_low'), sig('sig_bounce2pct')])
    if (mandatory_cnt >= 2 and optional_cnt >= 1) or (mandatory_cnt >= 1 and optional_cnt >= 2):
        return (S_WATCH, _sig_label(S_WATCH), _sig_color(S_WATCH))

    return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))


def _signal_etf(d):
    """ETF v2.4 — QQQ, SPY, VOO, SCHD, JEPI 등"""
    def sig(k): return bool(d.get(k, False))

    # RSI > 70 → 전 단계 금지
    if sig('sig_rsi_gt70_block'):
        return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))

    # 3rd BUY (50%) — ALL 3
    cond3 = [
        sig('sig_above_ma20_2d') or (not sig('sig_below_ma20')),
        sig('sig_rsi_gt55'),
        sig('sig_macd_above_zero') and sig('sig_macd_golden'),
    ]
    if all(cond3):
        return (S_3RD_BUY, _sig_label(S_3RD_BUY), _sig_color(S_3RD_BUY))

    # 2nd BUY (30%) — Pick 3/4
    cond2 = [sig('sig_rsi_gt42'), sig('sig_macd_golden'),
             sig('sig_above_ma20_2d') or not sig('sig_below_ma20'),
             sig('sig_higher_low')]
    if sum(cond2) >= 3:
        return (S_2ND_BUY, _sig_label(S_2ND_BUY), _sig_color(S_2ND_BUY))

    # 1st BUY (20%) — 필수 2 + 선택 1/3
    mandatory = [sig('sig_rsi_le35'), sig('sig_correction_5pct')]
    optional  = [sig('sig_below_ma20'), sig('sig_near_bb_low'), sig('sig_low_stopped')]
    if all(mandatory) and sum(optional) >= 1:
        return (S_1ST_BUY, _sig_label(S_1ST_BUY), _sig_color(S_1ST_BUY))

    # WATCH — 1st 필수 1개 + 선택 1개
    if sum(mandatory) >= 1 and sum(optional) >= 1:
        return (S_WATCH, _sig_label(S_WATCH), _sig_color(S_WATCH))

    return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))


def _signal_energy(d):
    """Energy v2.3 — XOM, CVX 등 (시장필터 차단 제거)"""
    def sig(k): return bool(d.get(k, False))

    if sig('sig_rsi_gt70_block'):
        return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))

    if sig('sig_block_5pct_drop_all'):
        return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))

    # 3차 (50%): 4개 중 3개 이상
    cond3 = [sig('sig_above_ma20_2d'), sig('sig_ma20_slope_pos'),
             sig('sig_macd_golden'),   sig('sig_rsi_gt45')]
    if sum(cond3) >= 3:
        return (S_3RD_BUY, _sig_label(S_3RD_BUY), _sig_color(S_3RD_BUY))

    # 2차 (30%): 4개 중 3개 이상
    cond2 = [sig('sig_double_bottom_3pct'), sig('sig_rsi_gt40'),
             sig('sig_macd_golden'),         not sig('sig_below_ma20')]
    if sum(cond2) >= 3:
        return (S_2ND_BUY, _sig_label(S_2ND_BUY), _sig_color(S_2ND_BUY))

    # 1차 (20%): 필수 ALL 3 + 선택 2/3 (Growth와 동일)
    if not sig('sig_rsi_gt55_block'):
        mandatory = [sig('sig_rsi_le38'), sig('sig_below_ma20'), sig('sig_macd_hist_2d_up')]
        optional  = [sig('sig_adx_le25'), sig('sig_near_bb_low'), sig('sig_bounce2pct')]
        if all(mandatory) and sum(optional) >= 2:
            return (S_1ST_BUY, _sig_label(S_1ST_BUY), _sig_color(S_1ST_BUY))

    return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))


def _signal_value(d):
    """Value v2.4 — O, UNH (Growth와 동일하되 RSI 거부 55→70)"""
    def sig(k): return bool(d.get(k, False))

    if sig('sig_block_5pct_drop_all'):
        return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))

    # 3rd BUY — Growth와 동일
    if not sig('sig_rsi_gt75_block'):
        cond3 = [
            sig('sig_above_ma20_2d') or (not sig('sig_below_ma20')),
            sig('sig_macd_above_zero') and sig('sig_macd_golden'),
            sig('sig_vol_1p3') or sig('sig_vol_5d_2up'),
            sig('sig_rsi_gt55'),
        ]
        if all(cond3):
            return (S_3RD_BUY, _sig_label(S_3RD_BUY), _sig_color(S_3RD_BUY))

    # 2nd BUY — Growth와 동일
    cond2 = [sig('sig_double_bottom_diff_3pct'), sig('sig_rsi_gt35'),
             sig('sig_macd_golden'), sig('sig_vol_1p2')]
    if all(cond2):
        return (S_2ND_BUY, _sig_label(S_2ND_BUY), _sig_color(S_2ND_BUY))

    # 1st BUY — RSI 거부 70 (Growth는 55)
    if not sig('sig_rsi_gt70_block'):
        mandatory = [sig('sig_rsi_le38'), sig('sig_below_ma20'), sig('sig_macd_hist_2d_up')]
        optional  = [sig('sig_adx_le25'), sig('sig_near_bb_low'), sig('sig_bounce2pct')]
        if all(mandatory) and sum(optional) >= 2:
            return (S_1ST_BUY, _sig_label(S_1ST_BUY), _sig_color(S_1ST_BUY))

    return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))


def _signal_bond(d):
    """Bond v2.6 — TLT (30Y 금리 기반)"""
    def sig(k): return bool(d.get(k, False))
    y30 = float(d.get('yield_30y', 0))

    # 3rd BUY: TLT > MA20 2일 + 금리 피크 대비 하락 전환
    if sig('sig_above_ma20_2d') and d.get('yield_30y_declining', False):
        return (S_3RD_BUY, _sig_label(S_3RD_BUY), _sig_color(S_3RD_BUY))

    # 2nd BUY: 금리 ≥ 5.2% OR MACD 골든크로스
    if y30 >= 5.2 or sig('sig_macd_golden'):
        return (S_2ND_BUY, _sig_label(S_2ND_BUY), _sig_color(S_2ND_BUY))

    # 1st BUY: 금리 ≥ 5.0% AND RSI ≤ 35
    if y30 >= 5.0 and sig('sig_rsi_le35'):
        return (S_1ST_BUY, _sig_label(S_1ST_BUY), _sig_color(S_1ST_BUY))

    # BOND_WATCH: 금리 4.9~5.0%
    if 4.9 <= y30 < 5.0:
        return (S_BOND_WATCH, _sig_label(S_BOND_WATCH), _sig_color(S_BOND_WATCH))

    return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))


def _signal_metal(d):
    """Metal v2.6 — GLD, SLV"""
    def sig(k): return bool(d.get(k, False))
    rsi = float(d.get('rsi', 50))

    # RSI > 80 → TOP_SIGNAL 강제
    if rsi > 80:
        return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))  # Exit에서 처리

    # 3rd BUY: Pick 2/3
    cond3 = [sig('sig_above_ma20_2d'), sig('sig_ma20_rising'), sig('sig_macd_above_zero')]
    if sum(cond3) >= 2:
        return (S_3RD_BUY, _sig_label(S_3RD_BUY), _sig_color(S_3RD_BUY))

    # 2nd BUY: Pick 2/4
    cond2 = [sig('sig_macd_golden'), sig('sig_rsi_gt42'),
             sig('sig_higher_low'), sig('sig_ma20_flattening')]
    if sum(cond2) >= 2:
        return (S_2ND_BUY, _sig_label(S_2ND_BUY), _sig_color(S_2ND_BUY))

    # 1st BUY: Pick 2/4
    vix_high = float(d.get('vix_close', 0)) > 25
    cond1 = [sig('sig_rsi_le40'), sig('sig_below_ma20'), vix_high, sig('sig_near_bb_low')]
    if sum(cond1) >= 2:
        return (S_1ST_BUY, _sig_label(S_1ST_BUY), _sig_color(S_1ST_BUY))

    return (S_HOLD, _sig_label(S_HOLD), _sig_color(S_HOLD))


# ── 통합 시그널 판정 (v5.2) ──────────────────────────────────────

def trading_signal(d):
    """
    v5.2 통합 시그널 판정 — 순수 기술지표, 시장필터 미사용
    Returns: (signal_key, label, color)
    """
    stype = _get_strategy_type(d)
    if stype == 'bil':
        return (S_CASH, _sig_label(S_CASH), _sig_color(S_CASH))

    router = {
        'growth':      _signal_growth,
        'etf':         _signal_etf,
        'energy':      _signal_energy,
        'value':       _signal_value,
        'bond':        _signal_bond,
        'metal':       _signal_metal,
        'speculative': _signal_growth,
    }
    fn = router.get(stype, _signal_growth)
    return fn(d)


# ── Exit Signal v5.2 (익절 전용) ─────────────────────────────────

def calc_exit_signal(d):
    """
    v5.2 익절 전용 Exit 시스템
    Returns: (signal_name|None, label, color, detail)
      TOP_SIGNAL    → 과열 즉시 발동
      TAKE_PROFIT_2 → 대량 익절 50% (고점게이트 + MACD가드)
      TAKE_PROFIT_1 → 1차 익절 30% (고점게이트 + MACD가드)
      None          → 없음
    """
    def ex(k): return bool(d.get(k, False))
    rsi = float(d.get('rsi', 50))
    bb_pct = float(d.get('bb_pct', 50))
    prev_bb_pct = float(d.get('prev_bb_pct', 50))

    # Metal RSI > 80 → TOP_SIGNAL 강제
    stype = _get_strategy_type(d)
    if stype == 'metal' and rsi > 80:
        return (E_TOP, '⚠️ 과열 경보', colors.HexColor('#FF1744'), f'Metal RSI {rsi:.0f}>80')

    # ① TOP_SIGNAL — 과열은 무조건 발동 (게이트/가드 없음)
    top_conds = []
    if rsi >= 75:
        top_conds.append(f'RSI {rsi:.0f}≥75')
    if bb_pct > 100 and prev_bb_pct > 100:
        top_conds.append('BB상단 2일연속')
    change_3d = float(d.get('change_3d_pct', 0))
    if change_3d >= 10:
        top_conds.append(f'3일+{change_3d:.1f}%')
    if top_conds:
        return (E_TOP, '⚠️ 과열 경보', colors.HexColor('#FF1744'), ' + '.join(top_conds))

    # ② 고점 영역 게이트: DD > -5% 여야 TP 발동
    if not ex('exit_dd_gate'):
        return (None, '', colors.HexColor('#FFFFFF'), '')

    # ③ MACD 가드: 반등 중이면 TP 면제
    if ex('is_macd_bullish') or ex('macd_hist_recovering'):
        return (None, '', colors.HexColor('#FFFFFF'), '')

    # ④ TAKE_PROFIT_2 — 1개라도 충족 → 대량 익절 50%
    hist_trend = d.get('macd_hist_trend', '')
    tp2_parts = []
    # TP2①: MA20 2일 이탈 + hist 감소
    if ex('exit_ma20_break_2d') and 'decreasing' in hist_trend:
        tp2_parts.append('MA20 2일이탈+hist↓')
    # TP2②: Higher Low 붕괴
    if ex('exit_lower_low'):
        tp2_parts.append('저점하향돌파')
    # TP2③: MACD 데드크로스 + hist 감소
    if ex('exit_macd_dead_cross') and 'decreasing' in hist_trend:
        tp2_parts.append('MACD데드크로스+hist↓')
    if tp2_parts:
        return (E_TP2, 'TAKE PROFIT 2', colors.HexColor('#EF5350'), ' + '.join(tp2_parts))

    # ⑤ TAKE_PROFIT_1 — 2/3 충족 → 1차 익절 30%
    tp1_conds = [
        ex('exit_macd_hist_3d_down'),        # hist 3일 감소
        ex('exit_rsi_divergence_above50'),    # RSI 다이버전스 (둘 다 ≥ 50)
        ex('exit_ma20_break_1d'),             # MA20 1일 이탈
    ]
    tp1_parts = []
    if ex('exit_macd_hist_3d_down'):      tp1_parts.append('MACD hist 3일↓')
    if ex('exit_rsi_divergence_above50'): tp1_parts.append('RSI다이버전스')
    if ex('exit_ma20_break_1d'):          tp1_parts.append('MA20이탈')
    if sum(tp1_conds) >= 2:
        return (E_TP1, 'TAKE PROFIT 1', colors.HexColor('#FFA726'), ' + '.join(tp1_parts))

    return (None, '', colors.HexColor('#FFFFFF'), '')


def _stage_reason2(d, sk):
    """v5.2 시그널 근거 텍스트"""
    rsi = d.get('rsi', 50)
    chg = d.get('change_pct', 0.0)
    stype = _get_strategy_type(d)
    def sig(k): return bool(d.get(k, False))

    if sk == S_CASH:
        return '현금성 자산 — 판정 없음'
    if sk == S_BOND_WATCH:
        y30 = d.get('yield_30y', 0)
        return f'30Y 금리 {y30:.2f}% (4.9~5.0%) — 채권 트리거 직전'

    if sk == S_3RD_BUY:
        parts = []
        if stype == 'bond':
            if sig('sig_above_ma20_2d'): parts.append('MA20 2일↑')
            if d.get('yield_30y_declining'): parts.append('금리하락전환')
        elif stype == 'metal':
            if sig('sig_above_ma20_2d'): parts.append('MA20 2일↑')
            if sig('sig_ma20_rising'):   parts.append('MA20상승')
            if sig('sig_macd_above_zero'): parts.append('MACD>0')
        else:
            if not sig('sig_below_ma20'): parts.append('종가>MA20')
            if sig('sig_macd_golden'):    parts.append('MACD골든')
            if sig('sig_macd_above_zero'):parts.append('MACD>0')
            if sig('sig_vol_1p3'):        parts.append('거래량1.3x')
            if sig('sig_rsi_gt55'):       parts.append(f'RSI{rsi:.0f}>55')
        return '3rd BUY: ' + ' + '.join(parts) if parts else '3rd BUY'

    if sk == S_2ND_BUY:
        parts = []
        if stype == 'bond':
            y30 = d.get('yield_30y', 0)
            if y30 >= 5.2: parts.append(f'금리{y30:.1f}%≥5.2%')
            if sig('sig_macd_golden'): parts.append('MACD골든')
        elif stype == 'etf':
            if sig('sig_rsi_gt42'):    parts.append(f'RSI{rsi:.0f}>42')
            if sig('sig_macd_golden'): parts.append('MACD골든')
            if sig('sig_higher_low'):  parts.append('HigherLow')
        else:
            if sig('sig_double_bottom_diff_3pct'): parts.append('이중바닥')
            if sig('sig_rsi_gt35'):    parts.append(f'RSI{rsi:.0f}>35')
            if sig('sig_macd_golden'): parts.append('MACD골든')
            if sig('sig_vol_1p2'):     parts.append('거래량1.2x')
        return '2nd BUY: ' + ' + '.join(parts) if parts else '2nd BUY'

    if sk == S_1ST_BUY:
        parts = []
        if stype == 'bond':
            y30 = d.get('yield_30y', 0)
            parts.append(f'금리{y30:.1f}%≥5.0%')
            parts.append(f'RSI{rsi:.0f}≤35')
        elif stype == 'etf':
            if sig('sig_rsi_le35'):        parts.append(f'RSI{rsi:.0f}≤35')
            if sig('sig_correction_5pct'): parts.append('52주-5%')
            if sig('sig_below_ma20'):      parts.append('MA20↓')
            if sig('sig_near_bb_low'):     parts.append('BB하단')
            if sig('sig_low_stopped'):     parts.append('하락멈춤')
        else:
            m = [('RSI≤38', sig('sig_rsi_le38')), ('MA20↓', sig('sig_below_ma20')),
                 ('hist2일↑', sig('sig_macd_hist_2d_up'))]
            o = [('ADX≤25', sig('sig_adx_le25')), ('BB하단', sig('sig_near_bb_low')),
                 ('+2%반등', sig('sig_bounce2pct'))]
            parts = [n for n, v in m if v] + [n for n, v in o if v]
        return '1st BUY: ' + ' + '.join(parts) if parts else '1st BUY'

    if sk == S_WATCH:
        return '진입 조건 일부 충족 — 관찰 중'

    # HOLD 이유
    if sig('sig_block_5pct_drop_all'):
        return f'장대음봉 {chg:.1f}% → 전단계 차단'
    if stype in ('etf','energy') and sig('sig_rsi_gt70_block'):
        return f'RSI {rsi:.1f} > 70 → 과열 차단'
    if stype == 'growth' and sig('sig_rsi_gt55_block'):
        return f'RSI {rsi:.1f} > 55 → 1st BUY 차단'
    return 'HOLD — 진입 조건 미충족'


# ══════════════════════════════════════════════════════════════════
#  조건 체크 상세 분해
# ══════════════════════════════════════════════════════════════════

def get_condition_breakdown(d):
    """v5.2 각 단계별 조건 체크 결과 반환 (HTML 표시용) — strategy_type 분기"""
    stype = _get_strategy_type(d)
    if stype == 'etf':
        return _breakdown_etf(d)
    if stype == 'energy':
        return _breakdown_energy(d)
    if stype in ('value', 'speculative'):
        return _breakdown_growth(d)  # Growth 로직 공유
    if stype in ('bond', 'metal', 'bil'):
        return _breakdown_growth(d)  # 기본 breakdown 사용
    return _breakdown_growth(d)


def _breakdown_growth(d):
    """v2.2 성장주 판정 근거"""
    def sig(key, default=False): return bool(d.get(key, default))
    rsi   = d.get('rsi', 0);  adx  = d.get('adx', 0)
    chg   = d.get('change_pct', 0)
    close = d.get('close', 0); ma20 = d.get('ma20', close)

    block1       = sig('sig_block_rsi50') or sig('sig_block_bigdrop')
    macd_hist_2d = sig('sig_macd_hist_2d_up')
    cond1 = [
        {'name': '[필수] MACD 히스토그램 2일 연속 증가',
         'pass': macd_hist_2d,
         'ok':  '하락 에너지가 이틀 연속 줄어들고 있어요',
         'fail':'하락 에너지가 아직 줄어들지 않았어요 (필수 미충족)'},
        {'name': 'RSI(14) ≤ 38',
         'pass': sig('sig_rsi_le38'),
         'ok':  f'RSI {rsi:.1f} — 충분히 과매도 상태예요',
         'fail':f'RSI {rsi:.1f} — 기준(38)보다 아직 높아요'},
        {'name': 'ADX(14) ≤ 25',
         'pass': sig('sig_adx_le25'),
         'ok':  f'ADX {adx:.1f} — 하락 에너지가 약해지고 있어요',
         'fail':f'ADX {adx:.1f} — 아직 추세가 강하게 지속 중이에요'},
        {'name': '종가 < MA20',
         'pass': sig('sig_below_ma20'),
         'ok':  f'${close:.2f} < ${ma20:.2f} — 단기 이평선 아래에 있어요',
         'fail':f'${close:.2f} ≥ ${ma20:.2f} — 이평선 위에 있어요'},
        {'name': '하락 멈춤',
         'pass': sig('sig_low_stopped'),
         'ok':  '최근 3일 저점보다 높아요 — 하락이 일단 멈췄어요',
         'fail':'아직 저점을 갱신 중이에요 — 하락이 계속되고 있어요'},
        {'name': 'BB 하단 근처',
         'pass': sig('sig_near_bb_low'),
         'ok':  '볼린저 밴드 하단 지지구간에 있어요',
         'fail':'밴드 하단에서 아직 멀리 있어요'},
        {'name': '당일 +2% 이상 몸통 양봉 (윗꼬리≤2%)',
         'pass': sig('sig_bounce2pct'),
         'ok':  f'오늘 {chg:+.1f}% — 꽉 찬 양봉 반등 신호가 나왔어요',
         'fail':f'오늘 {chg:+.1f}% — 반등 or 몸통 기준 미충족'},
    ]
    met1 = sum(1 for c in cond1[1:] if c['pass'])

    cond2 = [
        {'name': '이중 바닥 패턴',
         'pass': sig('sig_double_bottom'),
         'ok':  'W자 바닥 패턴이 확인됐어요',
         'fail':'바닥 패턴이 아직 만들어지지 않았어요'},
        {'name': 'RSI > 35 + 3일 연속 상승',
         'pass': sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'),
         'ok':  f'RSI {rsi:.1f} — 반등 흐름이 이어지고 있어요',
         'fail':f'RSI {rsi:.1f} — 반등이 아직 확인되지 않았어요'},
        {'name': 'MACD 골든크로스 or 히스토그램 3일↑',
         'pass': sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'),
         'ok':  '상승 전환 신호가 나왔어요',
         'fail':'상승 전환 신호를 기다리는 중이에요'},
        {'name': '거래량 평균 1.2배 이상',
         'pass': sig('sig_vol_1p2'),
         'ok':  '평균보다 거래량이 많아요',
         'fail':'거래량이 평균 이하예요 — 아직 조용한 상태예요'},
    ]
    met2 = sum(1 for c in cond2 if c['pass'])

    cond3 = [
        {'name': 'MA20 위에서 2일 연속',
         'pass': sig('sig_above_ma20_2d'),
         'ok':  '이평선 위에 안착했어요 — 추세 전환 확인',
         'fail':'이평선 위로 아직 안착하지 못했어요'},
        {'name': 'MA20 기울기 상향',
         'pass': sig('sig_ma20_slope_pos'),
         'ok':  '이평선이 위를 향하고 있어요',
         'fail':'이평선이 아직 내려가고 있어요'},
        {'name': 'MACD 0선 위',
         'pass': sig('sig_macd_above_zero'),
         'ok':  '상승 모멘텀이 확실히 살아났어요',
         'fail':'모멘텀이 아직 음수 영역이에요'},
        {'name': '거래량 1.3배 이상 or 최근 5일 중 2일 증가',
         'pass': sig('sig_vol_1p3') or sig('sig_vol_5d_2up'),
         'ok':  '거래량 조건 충족 — 추세 신뢰도 높아요',
         'fail':'거래량이 충분하지 않아요'},
    ]
    met3 = sum(1 for c in cond3 if c['pass'])
    sk, lbl, _ = trading_signal(d)
    return {
        'stage': sk, 'label': lbl,
        'ai_explanation': d.get('condition_explanation', ''),
        'entry1': {
            'title': '🟡 1차 매수 조건 — 성장주 v2.2 ([필수] MACD히스토2일증가 + 6개 중 3개 이상)',
            'conditions': cond1, 'met': met1, 'required': 3, 'total': 6,
            'mandatory_ok': macd_hist_2d, 'blocked': block1,
            'block_reason': ('RSI > 50 — 아직 과열 구간이에요' if sig('sig_block_rsi50')
                             else '장대음봉 발생 (-5% 이상)' if sig('sig_block_bigdrop')
                             else None if macd_hist_2d
                             else 'MACD 히스토그램 2일 연속 증가 미충족 (필수조건)'),
        },
        'entry2': {
            'title': '🔵 2차 매수 조건 — 성장주 v2.2 (4개 모두 충족)',
            'conditions': cond2, 'met': met2, 'required': 4, 'total': 4,
            'blocked': False, 'block_reason': None,
        },
        'entry3': {
            'title': '🟢 3차 매수 조건 — 성장주 v2.2 (4개 모두 충족)',
            'conditions': cond3, 'met': met3, 'required': 4, 'total': 4,
            'blocked': False, 'block_reason': None,
        },
    }


def _breakdown_etf(d):
    """v2.4 ETF 판정 근거"""
    def sig(key, default=False): return bool(d.get(key, default))
    rsi   = d.get('rsi', 0)
    close = d.get('close', 0); ma20 = d.get('ma20', close)
    h52   = d.get('high_52w', close * 1.3)

    rsi_block = sig('sig_rsi_gt70_block')
    # 1차: 5조건 중 3개 (MACD 필수 없음)
    cond1 = [
        {'name': 'RSI(14) ≤ 40',
         'pass': sig('sig_rsi_le40'),
         'ok':  f'RSI {rsi:.1f} — 과매도 구간 진입',
         'fail':f'RSI {rsi:.1f} — 아직 40 초과 (기준 미달)'},
        {'name': '종가 < MA20',
         'pass': sig('sig_below_ma20'),
         'ok':  f'${close:.2f} < ${ma20:.2f} — MA20 아래에 있어요',
         'fail':f'${close:.2f} ≥ ${ma20:.2f} — MA20 위에 있어요'},
        {'name': 'BB 하단 근접',
         'pass': sig('sig_near_bb_low'),
         'ok':  '볼린저 밴드 하단 지지구간이에요',
         'fail':'밴드 하단에서 아직 멀리 있어요'},
        {'name': '하락 멈춤',
         'pass': sig('sig_low_stopped'),
         'ok':  '최근 3일 저점보다 높아요 — 하락이 일단 멈췄어요',
         'fail':'아직 저점을 갱신 중이에요'},
        {'name': f'52주 고점 대비 -5% 이상 조정 (고점 ${h52:.2f})',
         'pass': sig('sig_correction_5pct'),
         'ok':  f'고점 대비 충분히 조정됐어요',
         'fail':f'고점 대비 조정 폭이 아직 부족해요'},
    ]
    met1 = sum(1 for c in cond1 if c['pass'])

    # 2차: 4조건 중 3개
    cond2 = [
        {'name': 'RSI > 42',
         'pass': sig('sig_rsi_gt42'),
         'ok':  f'RSI {rsi:.1f} — 반등 흐름 시작',
         'fail':f'RSI {rsi:.1f} — 아직 42 미만'},
        {'name': 'MACD 골든크로스',
         'pass': sig('sig_macd_golden'),
         'ok':  'MACD 상향 교차 — 상승 전환 신호',
         'fail':'MACD 골든크로스 아직 미발생'},
        {'name': 'MA20 위 또는 근접 (이탈 아님)',
         'pass': sig('sig_above_ma20_2d') or not sig('sig_below_ma20'),
         'ok':  'MA20 위에 있거나 근접해요',
         'fail':'MA20 아래 이탈 중'},
        {'name': 'Higher Low (고점 하락 멈춤)',
         'pass': sig('sig_higher_low'),
         'ok':  '저점이 높아지고 있어요 — 매도 압력 감소',
         'fail':'저점이 아직 낮아지고 있어요'},
    ]
    met2 = sum(1 for c in cond2 if c['pass'])

    # 3차: 4조건 중 3개
    cond3 = [
        {'name': 'MA20 위에서 2일 연속',
         'pass': sig('sig_above_ma20_2d'),
         'ok':  'MA20 위에 안착 — 추세 전환 확인',
         'fail':'MA20 위로 아직 안착하지 못했어요'},
        {'name': 'MA20 기울기 상향',
         'pass': sig('sig_ma20_slope_pos'),
         'ok':  '이평선이 위를 향하고 있어요',
         'fail':'이평선이 아직 내려가고 있어요'},
        {'name': 'RSI > 48',
         'pass': sig('sig_rsi_gt48'),
         'ok':  f'RSI {rsi:.1f} — 중립선 위 상승 모멘텀',
         'fail':f'RSI {rsi:.1f} — 48 미만 (모멘텀 부족)'},
        {'name': 'MACD 0선 위',
         'pass': sig('sig_macd_above_zero'),
         'ok':  '상승 모멘텀이 확실히 살아났어요',
         'fail':'모멘텀이 아직 음수 영역이에요'},
    ]
    met3 = sum(1 for c in cond3 if c['pass'])
    sk, lbl, _ = trading_signal(d)
    return {
        'stage': sk, 'label': lbl,
        'ai_explanation': d.get('condition_explanation', ''),
        'entry1': {
            'title': '🟡 1차 매수 조건 — ETF v2.4 (5개 중 3개 이상, MACD 필수 없음)',
            'conditions': cond1, 'met': met1, 'required': 3, 'total': 5,
            'mandatory_ok': True, 'blocked': rsi_block,
            'block_reason': f'RSI {rsi:.1f} > 70 — ETF 과열 차단 (전 단계 진입 불가)' if rsi_block else None,
        },
        'entry2': {
            'title': '🔵 2차 매수 조건 — ETF v2.4 (4개 중 3개 이상)',
            'conditions': cond2, 'met': met2, 'required': 3, 'total': 4,
            'blocked': rsi_block, 'block_reason': None,
        },
        'entry3': {
            'title': '🟢 3차 매수 조건 — ETF v2.4 (4개 중 3개 이상)',
            'conditions': cond3, 'met': met3, 'required': 3, 'total': 4,
            'blocked': rsi_block, 'block_reason': None,
        },
    }


def _breakdown_energy(d):
    """v2.3 에너지 판정 근거"""
    def sig(key, default=False): return bool(d.get(key, default))
    rsi   = d.get('rsi', 0);  adx  = d.get('adx', 0)
    chg   = d.get('change_pct', 0)
    close = d.get('close', 0); ma20 = d.get('ma20', close)

    rsi_block    = sig('sig_rsi_gt70_block')
    block1       = sig('sig_block_rsi50') or sig('sig_block_bigdrop')
    macd_hist_2d = sig('sig_macd_hist_2d_up')
    # 1차: 성장주 v2.2 동일 조건 | RSI > 70 차단
    cond1 = [
        {'name': '[필수] MACD 히스토그램 2일 연속 증가',
         'pass': macd_hist_2d,
         'ok':  '하락 에너지가 이틀 연속 줄어들고 있어요',
         'fail':'하락 에너지가 아직 줄어들지 않았어요 (필수 미충족)'},
        {'name': 'RSI(14) ≤ 38',
         'pass': sig('sig_rsi_le38'),
         'ok':  f'RSI {rsi:.1f} — 충분히 과매도 상태예요',
         'fail':f'RSI {rsi:.1f} — 기준(38)보다 아직 높아요'},
        {'name': 'ADX(14) ≤ 25',
         'pass': sig('sig_adx_le25'),
         'ok':  f'ADX {adx:.1f} — 하락 에너지가 약해지고 있어요',
         'fail':f'ADX {adx:.1f} — 아직 추세가 강하게 지속 중이에요'},
        {'name': '종가 < MA20',
         'pass': sig('sig_below_ma20'),
         'ok':  f'${close:.2f} < ${ma20:.2f} — 단기 이평선 아래에 있어요',
         'fail':f'${close:.2f} ≥ ${ma20:.2f} — 이평선 위에 있어요'},
        {'name': '하락 멈춤',
         'pass': sig('sig_low_stopped'),
         'ok':  '최근 3일 저점보다 높아요 — 하락이 일단 멈췄어요',
         'fail':'아직 저점을 갱신 중이에요'},
        {'name': 'BB 하단 근처',
         'pass': sig('sig_near_bb_low'),
         'ok':  '볼린저 밴드 하단 지지구간에 있어요',
         'fail':'밴드 하단에서 아직 멀리 있어요'},
        {'name': '당일 +2% 이상 몸통 양봉 (윗꼬리≤2%)',
         'pass': sig('sig_bounce2pct'),
         'ok':  f'오늘 {chg:+.1f}% — 꽉 찬 양봉 반등 신호가 나왔어요',
         'fail':f'오늘 {chg:+.1f}% — 반등 or 몸통 기준 미충족'},
    ]
    met1 = sum(1 for c in cond1[1:] if c['pass'])

    # 2차: 4조건 중 3개 (이중바닥±3%, RSI>40, MACD골든, 종가>MA20)
    cond2 = [
        {'name': '이중 바닥 (±3% 허용)',
         'pass': sig('sig_double_bottom_3pct'),
         'ok':  '에너지 섹터 바닥 패턴 확인 (±3%)',
         'fail':'바닥 패턴이 아직 확인되지 않았어요'},
        {'name': 'RSI > 40',
         'pass': sig('sig_rsi_gt40'),
         'ok':  f'RSI {rsi:.1f} — 과매도 탈출 신호',
         'fail':f'RSI {rsi:.1f} — 아직 40 미만'},
        {'name': 'MACD 골든크로스',
         'pass': sig('sig_macd_golden'),
         'ok':  'MACD 상향 교차 — 상승 전환 신호',
         'fail':'MACD 골든크로스 아직 미발생'},
        {'name': '종가 > MA20',
         'pass': not sig('sig_below_ma20'),
         'ok':  f'${close:.2f} > ${ma20:.2f} — MA20 위에 안착',
         'fail':f'${close:.2f} ≤ ${ma20:.2f} — 아직 MA20 아래'},
    ]
    met2 = sum(1 for c in cond2 if c['pass'])

    # 3차: 4조건 중 3개 (MA20 2일↑, 기울기↑, MACD골든, RSI>45)
    cond3 = [
        {'name': 'MA20 위에서 2일 연속',
         'pass': sig('sig_above_ma20_2d'),
         'ok':  'MA20 위에 안착 — 추세 전환 확인',
         'fail':'MA20 위로 아직 안착하지 못했어요'},
        {'name': 'MA20 기울기 상향',
         'pass': sig('sig_ma20_slope_pos'),
         'ok':  '이평선이 위를 향하고 있어요',
         'fail':'이평선이 아직 내려가고 있어요'},
        {'name': 'MACD 골든크로스',
         'pass': sig('sig_macd_golden'),
         'ok':  '상승 전환 신호가 나왔어요',
         'fail':'골든크로스를 기다리는 중이에요'},
        {'name': 'RSI > 45',
         'pass': sig('sig_rsi_gt45'),
         'ok':  f'RSI {rsi:.1f} — 상승 모멘텀 확인',
         'fail':f'RSI {rsi:.1f} — 45 미만 (모멘텀 부족)'},
    ]
    met3 = sum(1 for c in cond3 if c['pass'])
    sk, lbl, _ = trading_signal(d)
    return {
        'stage': sk, 'label': lbl,
        'ai_explanation': d.get('condition_explanation', ''),
        'entry1': {
            'title': '🟡 1차 매수 조건 — 에너지 v2.3 ([필수] MACD히스토2일증가 + 6개 중 3개 이상)',
            'conditions': cond1, 'met': met1, 'required': 3, 'total': 6,
            'mandatory_ok': macd_hist_2d,
            'blocked': rsi_block or block1,
            'block_reason': (f'RSI {rsi:.1f} > 70 — 에너지 전략 과열 차단' if rsi_block
                             else 'RSI > 50' if sig('sig_block_rsi50')
                             else '장대음봉 발생' if sig('sig_block_bigdrop')
                             else None if macd_hist_2d
                             else 'MACD 히스토그램 2일 연속 증가 미충족 (필수조건)'),
        },
        'entry2': {
            'title': '🔵 2차 매수 조건 — 에너지 v2.3 (4개 중 3개 이상)',
            'conditions': cond2, 'met': met2, 'required': 3, 'total': 4,
            'blocked': rsi_block, 'block_reason': None,
        },
        'entry3': {
            'title': '🟢 3차 매수 조건 — 에너지 v2.3 (4개 중 3개 이상)',
            'conditions': cond3, 'met': met3, 'required': 3, 'total': 4,
            'blocked': rsi_block, 'block_reason': None,
        },
    }


# ══════════════════════════════════════════════════════════════════
#  BUY 연속일 확인 시스템 (v5.2)
# ══════════════════════════════════════════════════════════════════

_BUY_SIGNALS = {S_3RD_BUY, S_2ND_BUY, S_1ST_BUY}

def apply_streak(ticker, today_signal, history):
    """
    BUY 연속일 확인 — 2일 연속 유지 시 확정
    Returns: (streak, confirmed, annotation)
    """
    prev = history.get(ticker, {})
    prev_signal = prev.get('prev_signal', '')
    prev_streak = prev.get('buy_streak', 0)

    is_buy  = today_signal in _BUY_SIGNALS
    was_buy = prev_signal in _BUY_SIGNALS

    if is_buy and was_buy:
        streak = prev_streak + 1
    elif is_buy:
        streak = 1
    else:
        streak = 0

    confirmed = streak >= 2
    if streak == 1:
        annotation = '확인 대기 1/2일 ⏳'
    elif streak >= 2:
        annotation = f'확정 {streak}일 연속 ✅'
    else:
        annotation = ''

    return (streak, confirmed, annotation)


def load_signal_history(path):
    """signals_history.json 로드"""
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_signal_history(path, history):
    """signals_history.json 저장"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
