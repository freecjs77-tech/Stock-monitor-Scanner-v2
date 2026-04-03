"""conftest.py — pytest fixtures for stock signal testing."""

import sys, os

# cowork_agents/ 경로 추가 (signals, ta, charts 등 import 가능)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cowork_agents'))

import pytest


def _base_stock(**overrides):
    """Minimal stock data dict with sensible defaults."""
    d = {
        'ticker': 'TEST', 'company': 'Test Corp', 'sector': 'Tech',
        'exchange': 'NASDAQ',
        'close': 100.0, 'change_pct': -1.0,
        'high_52w': 150.0, 'low_52w': 80.0,
        'ma20': 105.0, 'ma50': 110.0, 'ma200': 115.0,
        'rsi': 45.0, 'macd': -0.5, 'macd_signal': 0.2,
        'bb_upper': 120.0, 'bb_lower': 90.0,
        'bb_pct': 33.0, 'prev_bb_pct': 30.0,
        'volume': 50e6, 'avg_volume': 40e6,
        'adx': 20.0, 'plus_di': 25.0, 'minus_di': 25.0,
    }
    d.update(overrides)
    return d


@pytest.fixture
def base_stock():
    """Base stock data with neutral conditions."""
    return _base_stock()


@pytest.fixture
def growth_3rd_buy():
    """Growth stock with all 3rd BUY conditions met."""
    return _base_stock(
        ticker='NVDA',
        close=120.0, ma20=115.0, ma50=110.0, ma200=100.0,
        rsi=60.0, macd=2.0, macd_signal=1.0,
        sig_above_ma20_2d=True,
        sig_below_ma20=False,
        sig_macd_above_zero=True,
        sig_macd_golden=True,
        sig_vol_1p3=True,
        sig_rsi_gt55=True,
        sig_rsi_gt75_block=False,
        sig_block_5pct_drop_all=False,
    )


@pytest.fixture
def growth_2nd_buy():
    """Growth stock with all 2nd BUY conditions met."""
    return _base_stock(
        ticker='TSLA',
        close=100.0, ma20=105.0, ma50=110.0, ma200=115.0,
        rsi=40.0, macd=0.5, macd_signal=0.3,
        sig_double_bottom_diff_3pct=True,
        sig_rsi_gt35=True,
        sig_macd_golden=True,
        sig_vol_1p2=True,
        sig_block_5pct_drop_all=False,
    )


@pytest.fixture
def growth_1st_buy():
    """Growth stock with 1st BUY conditions met."""
    return _base_stock(
        ticker='AAPL',
        close=90.0, ma20=100.0, ma50=110.0, ma200=115.0,
        rsi=35.0, macd=-1.0, macd_signal=-0.5,
        sig_rsi_le38=True,
        sig_below_ma20=True,
        sig_macd_hist_2d_up=True,
        sig_adx_le25=True,
        sig_near_bb_low=True,
        sig_bounce2pct=False,
        sig_rsi_gt55_block=False,
        sig_block_5pct_drop_all=False,
    )


@pytest.fixture
def bil_stock():
    """Cash asset (BIL)."""
    return _base_stock(ticker='BIL', strategy_type='bil')


@pytest.fixture
def exit_top_signal():
    """Stock with TOP_SIGNAL exit conditions."""
    return _base_stock(
        ticker='NVDA',
        rsi=78.0,
        bb_pct=110.0, prev_bb_pct=105.0,
        change_3d_pct=5.0,
    )


@pytest.fixture
def exit_dd_gate_closed():
    """Stock where DD gate is NOT met (no TP)."""
    return _base_stock(
        ticker='NVDA',
        rsi=55.0,
        exit_dd_gate=False,
    )
