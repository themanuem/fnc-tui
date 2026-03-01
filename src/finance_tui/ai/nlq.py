"""Natural language queries using Claude with tool use."""

import json
import os
from datetime import date

import pandas as pd

from finance_tui import analytics


def _get_tools(df: pd.DataFrame, categories: dict) -> list[dict]:
    """Define the tools available for NLQ."""
    return [
        {
            "name": "get_total_spending",
            "description": "Get total spending (expenses) for a period or category",
            "input_schema": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Month in YYYY-MM format"},
                    "category": {"type": "string", "description": "Category name"},
                },
            },
        },
        {
            "name": "get_top_expenses",
            "description": "Get the N largest expenses",
            "input_schema": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Number of top expenses", "default": 10},
                    "month": {"type": "string", "description": "Month in YYYY-MM format"},
                },
            },
        },
        {
            "name": "get_category_breakdown",
            "description": "Get spending breakdown by category",
            "input_schema": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Month in YYYY-MM format"},
                },
            },
        },
        {
            "name": "compare_periods",
            "description": "Compare spending between two months",
            "input_schema": {
                "type": "object",
                "properties": {
                    "month1": {"type": "string", "description": "First month YYYY-MM"},
                    "month2": {"type": "string", "description": "Second month YYYY-MM"},
                },
                "required": ["month1", "month2"],
            },
        },
        {
            "name": "search_transactions",
            "description": "Search transactions by description text",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_budget_status",
            "description": "Get budget status for tracked categories",
            "input_schema": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Month in YYYY-MM format"},
                },
            },
        },
    ]


def _execute_tool(
    name: str,
    args: dict,
    df: pd.DataFrame,
    categories: dict,
) -> str:
    """Execute a tool call and return the result as a string."""

    if name == "get_total_spending":
        month = args.get("month")
        category = args.get("category")
        filtered = df[df["is_expense"]]
        if month:
            filtered = filtered[filtered["month"] == month]
        if category:
            filtered = filtered[filtered["category"] == category]
        total = round(filtered["amount"].sum(), 2)
        count = len(filtered)
        return json.dumps({"total": total, "count": count, "currency": "EUR"})

    elif name == "get_top_expenses":
        n = args.get("n", 10)
        month = args.get("month")
        filtered = df[df["is_expense"]]
        if month:
            filtered = filtered[filtered["month"] == month]
        top = filtered.nsmallest(n, "amount")
        items = [
            {"date": r["date"].strftime("%Y-%m-%d"), "amount": r["amount"],
             "description": r["description"], "category": r["category"]}
            for _, r in top.iterrows()
        ]
        return json.dumps(items)

    elif name == "get_category_breakdown":
        month = args.get("month")
        expenses = analytics.expenses_by_category(df, month)
        income = analytics.income_by_category(df, month)
        return json.dumps({"expenses": expenses, "income": income})

    elif name == "compare_periods":
        m1 = args["month1"]
        m2 = args["month2"]
        t1 = analytics.month_total(df, m1)
        t2 = analytics.month_total(df, m2)
        e1 = analytics.expense_total(df, m1)
        e2 = analytics.expense_total(df, m2)
        i1 = analytics.income_total(df, m1)
        i2 = analytics.income_total(df, m2)
        return json.dumps({
            m1: {"net": t1, "expenses": e1, "income": i1},
            m2: {"net": t2, "expenses": e2, "income": i2},
            "difference": {"net": round(t2 - t1, 2), "expenses": round(e2 - e1, 2)},
        })

    elif name == "search_transactions":
        query = args["query"]
        limit = args.get("limit", 20)
        mask = df["description"].str.contains(query, case=False, na=False)
        results = df[mask].head(limit)
        items = [
            {"date": r["date"].strftime("%Y-%m-%d"), "amount": r["amount"],
             "description": r["description"], "category": r["category"],
             "account": r["account"]}
            for _, r in results.iterrows()
        ]
        return json.dumps(items)

    elif name == "get_budget_status":
        month = args.get("month", date.today().strftime("%Y-%m"))
        status = analytics.category_spend_vs_budget(df, categories, month)
        return json.dumps(status)

    return json.dumps({"error": f"Unknown tool: {name}"})


async def query_nlq(
    question: str,
    df: pd.DataFrame,
    categories: dict,
) -> str:
    """Answer a natural language question about finances using Claude with tools.

    Returns the final text response.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY not set. Please set it to use AI features.\n\nExport it: `export ANTHROPIC_API_KEY=sk-...`"

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()
        tools = _get_tools(df, categories)

        system = (
            f"You are a personal finance assistant. The user tracks finances in EUR. "
            f"Today is {date.today().isoformat()}. Current fiscal period: {date.today().strftime('%Y-%m')}. "
            f"Use the available tools to answer questions about their finances. "
            f"Always show amounts with 2 decimal places and the € symbol. "
            f"Be concise and helpful."
        )

        messages = [{"role": "user", "content": question}]

        # Tool use loop (max 5 iterations)
        for _ in range(5):
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=system,
                tools=tools,
                messages=messages,
            )

            # Check if there are tool calls
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                # Extract text response
                text_blocks = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_blocks) if text_blocks else "No response generated."

            # Execute tool calls and add results
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                result = _execute_tool(tool_use.name, tool_use.input, df, categories)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        return "Query required too many tool calls. Please try a simpler question."

    except Exception as e:
        return f"Error: {e}"
