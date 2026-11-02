import math

import pandas as pd


UNCERTAIN_MONTHS = 60


def calc_payback_months(investment: float, profit: float) -> float:
    """Calculate the months needed to recover an investment.

    Args:
        investment: The total investment amount.
        profit: The monthly net profit.

    Returns:
        The payback period in months, or NaN if profit is not positive.

    Raises:
        None.
    """
    if profit <= 0:
        return float("nan")
    return investment / profit


def simulate_payback(
    disc_row: dict, user_input: dict, scenarios: dict
) -> pd.DataFrame:
    """Simulate payback periods for the supplied scenarios.

    Args:
        disc_row: Franchise data containing startup cost and average annual sales.
        user_input: User-provided deposit, key money, and loan details.
        scenarios: Named scenarios containing sales factors and margins.

    Returns:
        A DataFrame with scenario results in input order.

    Raises:
        ValueError: 평균매출이 없거나 0 이하, 창업비용이 없거나 음수,
            user_input 값이 없거나 음수, 시나리오가 비어 있는 경우.
    """
    if (
        "avg_annual_sales" not in disc_row
        or disc_row["avg_annual_sales"] is None
        or disc_row["avg_annual_sales"] <= 0
    ):
        raise ValueError("평균매출 없음")

    if (
        "startup_cost" not in disc_row
        or disc_row["startup_cost"] is None
        or disc_row["startup_cost"] < 0
    ):
        raise ValueError("창업비용 없음")

    input_fields = ("deposit", "key_money", "loan_amount", "loan_rate")
    # 수정 1: user_input 값 누락 검증
    if any(user_input.get(field) is None for field in input_fields):
        raise ValueError("입력 누락")
    if any(user_input[field] < 0 for field in input_fields):
        raise ValueError("음수 입력")

    if not scenarios:
        raise ValueError("시나리오 없음")

    total_investment = (
        disc_row["startup_cost"] + user_input["deposit"] + user_input["key_money"]
    )
    monthly_interest = (
        user_input["loan_amount"] * user_input["loan_rate"] / 100 / 12
    )
    monthly_sales = disc_row["avg_annual_sales"] / 12

    rows = []
    for scenario, values in scenarios.items():
        monthly_net_profit = (
            monthly_sales * values["sales_factor"] * values["margin"]
            - monthly_interest
        )
        payback_months = calc_payback_months(
            total_investment, monthly_net_profit
        )
        uncertain = math.isnan(payback_months) or payback_months > UNCERTAIN_MONTHS

        rows.append(
            {
                "scenario": scenario,
                "monthly_net_profit": round(monthly_net_profit, 1),
                # 수정 2: 불필요한 NaN 삼항식 단순화
                "payback_months": round(payback_months, 1),
                "uncertain": uncertain,
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "scenario",
            "monthly_net_profit",
            "payback_months",
            "uncertain",
        ],
    )