"""Computed financial metrics and aggregations."""

from datetime import date, datetime

import pandas as pd


def global_balance(df: pd.DataFrame) -> float:
    """Total sum of all transactions."""
    if df.empty:
        return 0.0
    return round(df["amount"].sum(), 2)


def balance_yoy_rate(df: pd.DataFrame) -> float | None:
    """Year-over-year balance growth rate as a percentage.

    Compares cumulative balance at end of current year vs end of prior year.
    """
    if df.empty or "date" not in df.columns:
        return None

    today = date.today()
    current_year = today.year
    prior_year = current_year - 1

    bal_prior = df[df["date"].dt.year <= prior_year]["amount"].sum()
    bal_current = df[df["date"].dt.year <= current_year]["amount"].sum()

    if bal_prior == 0:
        return None

    return round((bal_current - bal_prior) / abs(bal_prior) * 100, 1)


def transaction_count(df: pd.DataFrame) -> int:
    """Total number of transactions."""
    return len(df)


def last_transaction_date(df: pd.DataFrame) -> date | None:
    """Date of the most recent transaction."""
    if df.empty:
        return None
    return df["date"].max().date()


def fiscal_period(ref: date | None = None) -> str:
    """Current fiscal period as YYYY-MM."""
    d = ref or date.today()
    return d.strftime("%Y-%m")


def month_total(df: pd.DataFrame, month: str) -> float:
    """Net total for a given month (YYYY-MM format)."""
    if df.empty:
        return 0.0
    mask = df["month"] == month
    return round(df.loc[mask, "amount"].sum(), 2)


def net_growth_mom(df: pd.DataFrame, ref: date | None = None) -> float:
    """Average monthly net change: mean(month_total) over months in the data."""
    if df.empty or "month" not in df.columns:
        return 0.0

    monthly_totals = df.groupby("month")["amount"].sum()
    if monthly_totals.empty:
        return 0.0

    return round(monthly_totals.mean(), 2)


def net_growth_mom_rate(df: pd.DataFrame) -> float | None:
    """Average monthly net as a percentage of average monthly income."""
    if df.empty or "month" not in df.columns:
        return None

    monthly_net = df.groupby("month")["amount"].sum()
    monthly_income = df[df["is_income"]].groupby("month")["amount"].sum()

    avg_income = monthly_income.mean() if not monthly_income.empty else 0.0
    if avg_income == 0:
        return None

    return round(monthly_net.mean() / avg_income * 100, 1)


def income_total(df: pd.DataFrame, month: str | None = None) -> float:
    """Total income, optionally filtered by month."""
    if df.empty:
        return 0.0
    filtered = df[df["is_income"]]
    if month:
        filtered = filtered[filtered["month"] == month]
    return round(filtered["amount"].sum(), 2)


def expense_total(df: pd.DataFrame, month: str | None = None) -> float:
    """Total expenses, optionally filtered by month."""
    if df.empty:
        return 0.0
    filtered = df[df["is_expense"]]
    if month:
        filtered = filtered[filtered["month"] == month]
    return round(filtered["amount"].sum(), 2)


def income_by_category(df: pd.DataFrame, month: str | None = None) -> dict[str, float]:
    """Income grouped by category."""
    if df.empty:
        return {}
    filtered = df[df["is_income"]]
    if month:
        filtered = filtered[filtered["month"] == month]
    return filtered.groupby("category")["amount"].sum().round(2).to_dict()


def expenses_by_category(df: pd.DataFrame, month: str | None = None) -> dict[str, float]:
    """Expenses grouped by category (values are negative)."""
    if df.empty:
        return {}
    filtered = df[df["is_expense"]]
    if month:
        filtered = filtered[filtered["month"] == month]
    return filtered.groupby("category")["amount"].sum().round(2).to_dict()


def balance_by_account(df: pd.DataFrame) -> dict[str, float]:
    """Balance per account."""
    if df.empty:
        return {}
    return df.groupby("account")["amount"].sum().round(2).to_dict()


def count_by_account(df: pd.DataFrame) -> dict[str, int]:
    """Transaction count per account."""
    if df.empty:
        return {}
    return df.groupby("account").size().to_dict()


def monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly net totals as a DataFrame with month and total columns."""
    if df.empty:
        return pd.DataFrame(columns=["month", "total"])
    return (
        df.groupby("month")["amount"]
        .sum()
        .round(2)
        .reset_index()
        .rename(columns={"amount": "total"})
    )


def monthly_running_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly cumulative balance."""
    mt = monthly_totals(df)
    mt["cumulative"] = mt["total"].cumsum().round(2)
    return mt


def daily_running_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Daily cumulative balance."""
    if df.empty:
        return pd.DataFrame(columns=["day", "total", "cumulative"])
    daily = (
        df.groupby(df["date"].dt.date)["amount"]
        .sum()
        .round(2)
        .reset_index()
        .rename(columns={"date": "day", "amount": "total"})
    )
    daily["day"] = daily["day"].astype(str)
    daily["cumulative"] = daily["total"].cumsum().round(2)
    return daily


def category_spend_vs_budget(
    df: pd.DataFrame,
    categories: dict[str, dict],
    month: str | None = None,
) -> list[dict]:
    """Compare actual spending to budget per category."""
    expenses = expenses_by_category(df, month)
    income = income_by_category(df, month)

    results = []
    for name, meta in sorted(categories.items()):
        budget = meta["budget"]
        if budget == 0 and not meta.get("track"):
            continue
        actual = expenses.get(name, 0.0) + income.get(name, 0.0)
        results.append({
            "category": name,
            "budget": budget,
            "actual": round(actual, 2),
            "remaining": round(budget - actual, 2) if budget != 0 else 0.0,
            "pct": round(abs(actual / budget) * 100, 1) if budget != 0 else 0.0,
        })
    return results


def months_over_budget(
    df: pd.DataFrame,
    categories: dict[str, dict],
) -> list[dict]:
    """Count unique months where spend exceeded budget per category.

    Spend = sum of amounts < 0 (expenses) for each category+month.
    """
    if df.empty:
        return []
    results = []
    for name, meta in sorted(categories.items()):
        budget = meta["budget"]
        if budget == 0:
            continue

        # Get monthly expense totals for this category
        cat_expenses = df[(df["category"] == name) & (df["is_expense"])]
        if cat_expenses.empty:
            all_months = df["month"].nunique()
            results.append({
                "category": name,
                "budget": budget,
                "months_over": 0,
                "total_months": all_months,
                "avg_overspend": 0.0,
            })
            continue

        monthly = cat_expenses.groupby("month")["amount"].sum()
        # Count months where absolute spend exceeded budget
        over_mask = monthly.abs() > budget
        months_over = int(over_mask.sum())
        total_months = df["month"].nunique()

        # Average overspend in months that exceeded budget
        if months_over > 0:
            avg_overspend = round(
                float((monthly.abs()[over_mask] - budget).mean()), 2
            )
        else:
            avg_overspend = 0.0

        results.append({
            "category": name,
            "budget": budget,
            "months_over": months_over,
            "total_months": total_months,
            "avg_overspend": avg_overspend,
        })

    return results
