#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_engine.py — backward-compatible re-export layer.

All logic has been split into:
  signals.py     — signal constants, strategy routing, decision functions
  ta.py          — technical analysis helpers (calc_ta, auto_score, etc.)
  charts.py      — chart visualization (build_chart, make_price_series)
  pdf_builder.py — PDF generation (build_pdf, generate_report, etc.)

This file re-exports everything so existing imports continue to work.
"""

# ── Signal module ─────────────────────────────────────────────────
from signals import (
    S_3RD_BUY, S_2ND_BUY, S_1ST_BUY, S_WATCH, S_HOLD, S_CASH, S_BOND_WATCH,
    E_TOP, E_TP2, E_TP1,
    _SIGNAL_COLORS, _SIGNAL_LABELS,
    _sig_color, _sig_label,
    _BIL_LIST, _BOND_LIST, _METAL_LIST, _VALUE_LIST, _SPEC_LIST, _ETF_LIST, _ENERGY_LIST,
    _get_strategy_type, _market_filter,
    _signal_growth, _signal_etf, _signal_energy, _signal_value, _signal_bond, _signal_metal,
    trading_signal, calc_exit_signal, _stage_reason2,
    get_condition_breakdown,
    _BUY_SIGNALS, apply_streak, load_signal_history, save_signal_history,
)

# ── Technical analysis module ─────────────────────────────────────
from ta import sma_arr, calc_ta, auto_signals, auto_score, timing_judgment, opinion_label

# ── Charts module ─────────────────────────────────────────────────
from charts import make_price_series, build_chart

# ── PDF builder module ────────────────────────────────────────────
from pdf_builder import (
    score_bar, build_pdf, build_pdf_card, build_index_page,
    generate_summary_page, generate_report,
    s, se,
    NAVY, BLUE, BLUE2, GREEN, RED, ORANGE,
    C_ENTRY3, C_ENTRY2, C_ENTRY1, C_CAUTION, C_BEAR, C_WAIT,
    LGRAY, MGRAY, DGRAY, WHITE, SELL_BG, BUY_BG, NEUT_BG,
    PAGE_W, PAGE_H, M, CW, KF, EF, EFB, EFS,
)
