from decimal import Decimal as D
from compound_policy import decide_monthly_withdrawal, capital_units, max_monthly_withdrawal_capacity

def test_below_150k_retains_all_profit():
    d = decide_monthly_withdrawal(D("140000"), D("10000"))
    assert not d.eligible and d.amount_jpy == D("0")
    assert d.retained_profit_jpy == D("10000")

def test_at_150k_no_withdrawable_profit_above_floor():
    d = decide_monthly_withdrawal(D("150000"), D("5000"))
    assert not d.eligible and d.amount_jpy == D("0")

def test_above_floor_caps_at_30k_and_profit():
    d = decide_monthly_withdrawal(D("185000"), D("50000"))
    assert d.eligible and d.amount_jpy == D("30000")
    assert d.retained_profit_jpy == D("20000")

def test_preserves_floor_even_when_profit_claim_is_high():
    d = decide_monthly_withdrawal(D("160000"), D("50000"))
    assert d.amount_jpy == D("10000")

def test_respects_already_withdrawn_amount():
    d = decide_monthly_withdrawal(D("200000"), D("50000"), D("20000"))
    assert d.amount_jpy == D("10000")

def test_units_and_capacity_are_not_profit_forecasts():
    assert capital_units(D("149999")) == 0
    assert capital_units(D("300000")) == 2
    assert max_monthly_withdrawal_capacity(D("900000")) == D("180000")
