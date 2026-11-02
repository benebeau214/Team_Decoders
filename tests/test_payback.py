import math

import pytest

from franchise_checkup.payback import calc_payback_months, simulate_payback

DISC = {"startup_cost": 10000, "avg_annual_sales": 24000}
USER = {"deposit": 2000, "key_money": 3000, "loan_amount": 0, "loan_rate": 0}
SCEN = {
    "보수": {"sales_factor": 0.8, "margin": 0.05},
    "평균": {"sales_factor": 1.0, "margin": 0.10},
    "낙관": {"sales_factor": 1.2, "margin": 0.15},
}


# 1. simulate_payback

def test_simulate_payback_normal():
    # 대출 없음
    df = simulate_payback(DISC, USER, SCEN)
    assert list(df.columns) == [
        "scenario", "monthly_net_profit", "payback_months", "uncertain"
    ]
    assert df["monthly_net_profit"].tolist() == [80.0, 200.0, 360.0]
    assert df["payback_months"].tolist() == [187.5, 75.0, 41.7]
    assert df["uncertain"].tolist() == [True, True, False]

    # 대출 이자(월 50) 반영
    user = {**USER, "loan_amount": 12000, "loan_rate": 5.0}
    df = simulate_payback(DISC, user, SCEN)
    assert df["monthly_net_profit"].tolist() == [30.0, 150.0, 310.0]
    assert df["payback_months"].tolist() == [500.0, 100.0, 48.4]


def test_simulate_payback_boundary():
    # 월 이자 200: 보수는 음수, 평균은 정확히 0 -> 회수 불가(NaN)
    user = {**USER, "loan_amount": 40000, "loan_rate": 6.0}
    df = simulate_payback(DISC, user, SCEN)
    assert math.isnan(df.loc[0, "payback_months"])
    assert math.isnan(df.loc[1, "payback_months"])
    assert df.loc[2, "payback_months"] == 93.8
    assert df["uncertain"].tolist() == [True, True, True]


def test_simulate_payback_exception():
    with pytest.raises(ValueError, match="평균매출 없음"):
        simulate_payback({**DISC, "avg_annual_sales": None}, USER, SCEN)

    with pytest.raises(ValueError, match="음수 입력"):
        simulate_payback(DISC, {**USER, "deposit": -1000}, SCEN)


# 2. calc_payback_months

def test_calc_payback_months_normal():
    assert calc_payback_months(15000, 200) == 75.0


def test_calc_payback_months_boundary():
    # 월 순이익 0 -> ZeroDivisionError 없이 NaN
    assert math.isnan(calc_payback_months(15000, 0))


def test_calc_payback_months_exception():
    # 월 순이익 음수 -> 회수 불가(NaN)
    assert math.isnan(calc_payback_months(15000, -5))
