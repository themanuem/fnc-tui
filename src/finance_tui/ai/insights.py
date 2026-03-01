"""Anomaly detection and spending insights."""

import json
import os
from datetime import date

import pandas as pd

from finance_tui import analytics


def detect_outliers(df: pd.DataFrame, z_threshold: float = 2.5) -> list[dict]:
    """Find transactions that are statistical outliers by amount."""
    if df.empty:
        return []

    expenses = df[df["is_expense"]].copy()
    if len(expenses) < 10:
        return []

    mean = expenses["amount"].mean()
    std = expenses["amount"].std()
    if std == 0:
        return []

    expenses = expenses.copy()
    expenses["z_score"] = (expenses["amount"] - mean) / std
    outliers = expenses[expenses["z_score"].abs() > z_threshold]

    return [
        {
            "type": "outlier",
            "id": int(row["id"]),
            "description": row["description"],
            "amount": row["amount"],
            "date": row["date"].strftime("%Y-%m-%d"),
            "category": row["category"],
            "z_score": round(row["z_score"], 2),
            "message": f"Unusual expense: {row['description']} ({row['amount']:.2f} €)",
        }
        for _, row in outliers.iterrows()
    ]


def detect_duplicates(df: pd.DataFrame, window_days: int = 3) -> list[dict]:
    """Find potential duplicate charges (same amount + similar date)."""
    if df.empty:
        return []

    dupes = []
    expenses = df[df["is_expense"]].sort_values("date")

    for i, row in expenses.iterrows():
        matches = expenses[
            (expenses.index != i)
            & (expenses["amount"] == row["amount"])
            & (abs((expenses["date"] - row["date"]).dt.days) <= window_days)
            & (expenses["description"] == row["description"])
        ]
        if not matches.empty:
            dupes.append({
                "type": "duplicate",
                "id": int(row["id"]),
                "description": row["description"],
                "amount": row["amount"],
                "date": row["date"].strftime("%Y-%m-%d"),
                "count": len(matches) + 1,
                "message": f"Possible duplicate: {row['description']} ({row['amount']:.2f} €) appears {len(matches) + 1} times within {window_days} days",
            })

    # Deduplicate alerts
    seen = set()
    unique = []
    for d in dupes:
        key = (d["description"], d["amount"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def detect_budget_alerts(
    df: pd.DataFrame,
    categories: dict,
    month: str | None = None,
) -> list[dict]:
    """Check for categories at or over budget."""
    month = month or date.today().strftime("%Y-%m")
    budget_status = analytics.category_spend_vs_budget(df, categories, month)

    alerts = []
    for item in budget_status:
        if item["budget"] == 0:
            continue
        pct = item["pct"]
        if pct >= 100:
            alerts.append({
                "type": "budget_over",
                "category": item["category"],
                "actual": item["actual"],
                "budget": item["budget"],
                "pct": pct,
                "message": f"Over budget: {item['category']} at {pct:.0f}% ({item['actual']:.2f} / {item['budget']:.2f} €)",
            })
        elif pct >= 80:
            alerts.append({
                "type": "budget_warning",
                "category": item["category"],
                "actual": item["actual"],
                "budget": item["budget"],
                "pct": pct,
                "message": f"Budget warning: {item['category']} at {pct:.0f}% ({item['actual']:.2f} / {item['budget']:.2f} €)",
            })

    return alerts


def get_all_insights(df: pd.DataFrame, categories: dict) -> list[dict]:
    """Run all anomaly detections and return combined alerts."""
    insights = []
    insights.extend(detect_budget_alerts(df, categories))
    insights.extend(detect_outliers(df))
    # Duplicate detection is expensive, limit to recent data
    recent = df[df["date"] >= pd.Timestamp(date.today().replace(day=1))]
    insights.extend(detect_duplicates(recent))
    return insights


async def summarize_insights(
    insights: list[dict],
    df: pd.DataFrame,
) -> str:
    """Use Claude to create a human-friendly summary of insights."""
    if not insights:
        return "No anomalies or alerts detected. Your finances look good!"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # Fallback to plain text
        lines = ["Detected insights:\n"]
        for i in insights:
            lines.append(f"  - {i['message']}")
        return "\n".join(lines)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()

        balance = analytics.global_balance(df)
        prompt = (
            f"Summarize these financial insights for the user. "
            f"Current balance: {balance:,.2f} €. "
            f"Be concise, actionable, and friendly.\n\n"
            f"Insights:\n{json.dumps(insights, indent=2)}"
        )

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    except Exception as e:
        # Fallback
        lines = ["Detected insights:\n"]
        for i in insights:
            lines.append(f"  - {i['message']}")
        return "\n".join(lines)
