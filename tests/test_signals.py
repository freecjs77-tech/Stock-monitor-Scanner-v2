"""test_signals.py — trading_signal() core tests."""

from signals import (
    trading_signal, S_3RD_BUY, S_2ND_BUY, S_1ST_BUY,
    S_WATCH, S_HOLD, S_CASH, S_BOND_WATCH,
    _get_strategy_type,
)


class TestTradingSignal:
    """trading_signal() returns correct signal for each strategy."""

    def test_growth_3rd_buy(self, growth_3rd_buy):
        sk, lbl, color = trading_signal(growth_3rd_buy)
        assert sk == S_3RD_BUY

    def test_growth_2nd_buy(self, growth_2nd_buy):
        sk, lbl, color = trading_signal(growth_2nd_buy)
        assert sk == S_2ND_BUY

    def test_growth_1st_buy(self, growth_1st_buy):
        sk, lbl, color = trading_signal(growth_1st_buy)
        assert sk == S_1ST_BUY

    def test_bil_always_cash(self, bil_stock):
        sk, lbl, color = trading_signal(bil_stock)
        assert sk == S_CASH

    def test_neutral_returns_hold_or_watch(self, base_stock):
        sk, lbl, color = trading_signal(base_stock)
        assert sk in (S_HOLD, S_WATCH)

    def test_return_is_3_tuple(self, base_stock):
        result = trading_signal(base_stock)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_etf_routing(self):
        d = {'ticker': 'QQQ', 'close': 100, 'ma20': 105, 'ma50': 110,
             'ma200': 115, 'rsi': 45, 'macd': -0.5, 'macd_signal': 0.2,
             'bb_upper': 120, 'bb_lower': 90, 'change_pct': -1,
             'high_52w': 150, 'low_52w': 80}
        assert _get_strategy_type(d) == 'etf'
        sk, _, _ = trading_signal(d)
        assert sk in (S_3RD_BUY, S_2ND_BUY, S_1ST_BUY, S_WATCH, S_HOLD)

    def test_bond_routing(self):
        d = {'ticker': 'TLT', 'close': 90, 'ma20': 92, 'ma50': 95,
             'ma200': 98, 'rsi': 40, 'macd': -0.3, 'macd_signal': -0.1,
             'bb_upper': 100, 'bb_lower': 85, 'change_pct': 0.5,
             'high_52w': 110, 'low_52w': 80, 'yield_30y': 4.5}
        assert _get_strategy_type(d) == 'bond'
        sk, _, _ = trading_signal(d)
        assert sk in (S_3RD_BUY, S_2ND_BUY, S_1ST_BUY, S_BOND_WATCH, S_HOLD)

    def test_metal_routing(self):
        d = {'ticker': 'GLD', 'close': 200, 'ma20': 195, 'ma50': 190,
             'ma200': 180, 'rsi': 55, 'macd': 1.0, 'macd_signal': 0.5,
             'bb_upper': 210, 'bb_lower': 185, 'change_pct': 0.8,
             'high_52w': 220, 'low_52w': 160}
        assert _get_strategy_type(d) == 'metal'

    def test_energy_routing(self):
        d = {'ticker': 'XOM', 'close': 100, 'ma20': 98, 'ma50': 95,
             'ma200': 90, 'rsi': 50, 'macd': 0.5, 'macd_signal': 0.3,
             'bb_upper': 110, 'bb_lower': 90, 'change_pct': 1,
             'high_52w': 120, 'low_52w': 75}
        assert _get_strategy_type(d) == 'energy'

    def test_5pct_drop_blocks_growth(self, growth_3rd_buy):
        growth_3rd_buy['sig_block_5pct_drop_all'] = True
        sk, _, _ = trading_signal(growth_3rd_buy)
        assert sk == S_HOLD
