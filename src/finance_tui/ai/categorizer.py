"""AI auto-categorization using Claude Haiku."""

import hashlib
import json
import os

from finance_tui.ai.cache import cache_get, cache_set

CATEGORIES_PROMPT = """You are a financial transaction categorizer. Given transaction descriptions, suggest the most likely category.

Available categories:
- Food: Restaurants, groceries, cafes, food delivery
- Transportation: Gas, parking, uber, taxis, flights, trains, tolls
- Shopping: Clothing, electronics, gifts, online shopping
- Entertainment: Movies, concerts, sports, games, events
- Subscriptions: Recurring charges (Netflix, Spotify, software)
- Housing: Rent, hotels, accommodation, booking
- Wellbeing: Pharmacy, gym, haircut, spa, health
- Education: Courses, learning platforms, books
- Charity: Donations
- Savings: Savings transfers
- Investments: Investment transfers
- Sales: Income, salary, payments received
- Taxes: Government fees, fines
- Other: Transfers, fees, refunds, miscellaneous
- Passive: Passive income
- Debt: Debt payments

For each transaction, respond with a JSON array of objects:
[{"description": "...", "category": "...", "confidence": 0.0-1.0}]

Only use categories from the list above. Be concise."""


async def categorize_transactions(
    descriptions: list[str],
    categories: list[str],
) -> list[dict]:
    """Categorize transactions using Claude Haiku.

    Returns list of {description, category, confidence} dicts.
    Falls back gracefully if API key is not set.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return [
            {"description": d, "category": "Other", "confidence": 0.0}
            for d in descriptions
        ]

    # Check cache first
    results = []
    uncached = []
    uncached_indices = []

    for i, desc in enumerate(descriptions):
        cache_key = f"cat:{hashlib.md5(desc.encode()).hexdigest()}"
        cached = cache_get(cache_key)
        if cached:
            results.append(cached)
        else:
            results.append(None)
            uncached.append(desc)
            uncached_indices.append(i)

    if not uncached:
        return results

    # Batch API call
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()
        batch_text = "\n".join(f"- {d}" for d in uncached)

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"{CATEGORIES_PROMPT}\n\nTransactions:\n{batch_text}",
            }],
        )

        # Parse response
        text = response.content[0].text
        # Find JSON array in response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
            for idx, item in zip(uncached_indices, parsed):
                result = {
                    "description": descriptions[idx],
                    "category": item.get("category", "Other"),
                    "confidence": float(item.get("confidence", 0.5)),
                }
                results[idx] = result
                # Cache it
                cache_key = f"cat:{hashlib.md5(descriptions[idx].encode()).hexdigest()}"
                cache_set(cache_key, result)

    except Exception:
        pass

    # Fill any remaining None entries
    return [
        r if r else {"description": descriptions[i], "category": "Other", "confidence": 0.0}
        for i, r in enumerate(results)
    ]
