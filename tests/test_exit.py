"""test_exit.py — calc_exit_signal() tests."""

from signals import calc_exit_signal, E_TOP, E_TP2, E_TP1


class TestExitSignal:
    """calc_exit_signal() returns correct exit signals."""

    def test_rsi_75_triggers_top(self, exit_top_signal):
        name, lbl, color, detail = calc_exit_signal(exit_top_signal)
        assert name == E_TOP
        assert 'RSI' in detail

    def test_bb_2day_triggers_top(self, base_stock):
        base_stock['rsi'] = 60.0
        base_stock['bb_pct'] = 105.0
        base_stock['prev_bb_pct'] = 102.0
        name, _, _, detail = calc_exit_signal(base_stock)
        assert name == E_TOP
        assert 'BB' in detail

    def test_3day_10pct_triggers_top(self, base_stock):
        base_stock['rsi'] = 60.0
        base_stock['bb_pct'] = 50.0
        base_stock['prev_bb_pct'] = 50.0
        base_stock['change_3d_pct'] = 12.0
        name, _, _, detail = calc_exit_signal(base_stock)
        assert name == E_TOP
        assert '3일' in detail

    def test_dd_gate_blocks_tp(self, exit_dd_gate_closed):
        name, _, _, _ = calc_exit_signal(exit_dd_gate_closed)
        assert name is None

    def test_macd_guard_blocks_tp(self, base_stock):
        base_stock['rsi'] = 55.0
        base_stock['bb_pct'] = 50.0
        base_stock['prev_bb_pct'] = 50.0
        base_stock['exit_dd_gate'] = True
        base_stock['is_macd_bullish'] = True
        name, _, _, _ = calc_exit_signal(base_stock)
        assert name is None

    def test_tp2_conditions(self, base_stock):
        base_stock['rsi'] = 55.0
        base_stock['bb_pct'] = 50.0
        base_stock['prev_bb_pct'] = 50.0
        base_stock['exit_dd_gate'] = True
        base_stock['is_macd_bullish'] = False
        base_stock['macd_hist_recovering'] = False
        base_stock['exit_lower_low'] = True
        base_stock['macd_hist_trend'] = ''
        name, _, _, _ = calc_exit_signal(base_stock)
        assert name == E_TP2

    def test_tp1_needs_2_of_3(self, base_stock):
        base_stock['rsi'] = 55.0
        base_stock['bb_pct'] = 50.0
        base_stock['prev_bb_pct'] = 50.0
        base_stock['exit_dd_gate'] = True
        base_stock['is_macd_bullish'] = False
        base_stock['macd_hist_recovering'] = False
        base_stock['macd_hist_trend'] = ''
        base_stock['exit_macd_hist_3d_down'] = True
        base_stock['exit_rsi_divergence_above50'] = True
        base_stock['exit_ma20_break_1d'] = False
        name, _, _, _ = calc_exit_signal(base_stock)
        assert name == E_TP1

    def test_metal_rsi_80_forces_top(self, base_stock):
        base_stock['ticker'] = 'GLD'
        base_stock['rsi'] = 82.0
        base_stock['bb_pct'] = 50.0
        base_stock['prev_bb_pct'] = 50.0
        name, _, _, detail = calc_exit_signal(base_stock)
        assert name == E_TOP
        assert 'Metal' in detail

    def test_return_is_4_tuple(self, base_stock):
        result = calc_exit_signal(base_stock)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_no_exit_returns_none(self, base_stock):
        base_stock['rsi'] = 50.0
        base_stock['bb_pct'] = 50.0
        base_stock['prev_bb_pct'] = 50.0
        name, _, _, _ = calc_exit_signal(base_stock)
        assert name is None
