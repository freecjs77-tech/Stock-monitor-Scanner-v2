"""test_streak.py — apply_streak() tests."""

from signals import apply_streak, S_1ST_BUY, S_2ND_BUY, S_3RD_BUY, S_HOLD


class TestApplyStreak:
    """apply_streak() tracks consecutive BUY days correctly."""

    def test_first_buy_day_streak_1(self):
        streak, confirmed, annotation = apply_streak('NVDA', S_1ST_BUY, {})
        assert streak == 1
        assert confirmed is False
        assert '대기' in annotation

    def test_second_consecutive_buy_confirmed(self):
        history = {'NVDA': {'prev_signal': S_1ST_BUY, 'buy_streak': 1}}
        streak, confirmed, annotation = apply_streak('NVDA', S_2ND_BUY, history)
        assert streak == 2
        assert confirmed is True
        assert '확정' in annotation

    def test_buy_to_hold_resets(self):
        history = {'NVDA': {'prev_signal': S_1ST_BUY, 'buy_streak': 3}}
        streak, confirmed, annotation = apply_streak('NVDA', S_HOLD, history)
        assert streak == 0
        assert confirmed is False
        assert annotation == ''

    def test_upgrade_preserves_streak(self):
        history = {'NVDA': {'prev_signal': S_1ST_BUY, 'buy_streak': 2}}
        streak, confirmed, annotation = apply_streak('NVDA', S_2ND_BUY, history)
        assert streak == 3
        assert confirmed is True

    def test_hold_to_hold_stays_zero(self):
        history = {'NVDA': {'prev_signal': S_HOLD, 'buy_streak': 0}}
        streak, confirmed, annotation = apply_streak('NVDA', S_HOLD, history)
        assert streak == 0
        assert confirmed is False

    def test_new_ticker_no_history(self):
        streak, confirmed, annotation = apply_streak('NEW', S_3RD_BUY, {})
        assert streak == 1
        assert confirmed is False
