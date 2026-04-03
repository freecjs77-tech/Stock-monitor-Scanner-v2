"""test_ta.py — Technical analysis utility tests."""

from signals import _get_strategy_type
from ta import auto_score, opinion_label


class TestStrategyType:
    """_get_strategy_type() correctly classifies tickers."""

    def test_growth_default(self):
        assert _get_strategy_type({'ticker': 'NVDA'}) == 'growth'

    def test_etf(self):
        assert _get_strategy_type({'ticker': 'QQQ'}) == 'etf'
        assert _get_strategy_type({'ticker': 'SPY'}) == 'etf'
        assert _get_strategy_type({'ticker': 'SCHD'}) == 'etf'

    def test_bond(self):
        assert _get_strategy_type({'ticker': 'TLT'}) == 'bond'

    def test_metal(self):
        assert _get_strategy_type({'ticker': 'GLD'}) == 'metal'
        assert _get_strategy_type({'ticker': 'SLV'}) == 'metal'

    def test_energy(self):
        assert _get_strategy_type({'ticker': 'XOM'}) == 'energy'
        assert _get_strategy_type({'ticker': 'CVX'}) == 'energy'

    def test_bil(self):
        assert _get_strategy_type({'ticker': 'BIL'}) == 'bil'

    def test_speculative(self):
        assert _get_strategy_type({'ticker': 'SOXL'}) == 'speculative'
        assert _get_strategy_type({'ticker': 'TQQQ'}) == 'speculative'

    def test_value(self):
        assert _get_strategy_type({'ticker': 'UNH'}) == 'value'
        assert _get_strategy_type({'ticker': 'O'}) == 'value'

    def test_explicit_strategy_type(self):
        assert _get_strategy_type({'ticker': 'XYZ', 'strategy_type': 'bond'}) == 'bond'

    def test_unknown_defaults_to_growth(self):
        assert _get_strategy_type({'ticker': 'UNKNOWN'}) == 'growth'


class TestAutoScore:
    """auto_score() returns proper structure."""

    def test_returns_7_tuple(self, base_stock):
        result = auto_score(base_stock)
        assert isinstance(result, tuple)
        assert len(result) == 7

    def test_total_is_sum(self, base_stock):
        a, b, c, d, e, f, total = auto_score(base_stock)
        assert total == max(0, a + b + c + d + e + f)

    def test_total_non_negative(self, base_stock):
        _, _, _, _, _, _, total = auto_score(base_stock)
        assert total >= 0


class TestOpinionLabel:
    """opinion_label() maps scores to correct labels."""

    def test_high_score_buy(self):
        label, color = opinion_label(65)
        assert '매수' in label

    def test_mid_score_neutral(self):
        label, color = opinion_label(40)
        assert '관망' in label

    def test_low_score_sell(self):
        label, color = opinion_label(20)
        assert '매도' in label
