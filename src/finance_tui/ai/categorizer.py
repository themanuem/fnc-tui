"""AI auto-categorization using LLM (Ollama or Anthropic)."""

import hashlib
import json
import logging

from finance_tui.ai.cache import cache_get, cache_set
from finance_tui.importers.llm import Provider, llm_complete

log = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """You are a financial transaction categorizer.

Available categories:
{categories}

For each transaction below, pick the single best category from the list above.
Respond with a JSON array — one object per transaction, in the same order:
[{{"description": "...", "category": "...", "confidence": 0.0-1.0}}]

JSON only, no explanation.

Transactions:
{transactions}"""

_BATCH_SIZE = 10


def categorize_transactions(
    descriptions: list[str],
    categories: list[str],
    provider: Provider = Provider.OLLAMA,
    on_batch: callable = None,
) -> list[dict]:
    """Categorize transactions using an LLM.

    Args:
        on_batch: Optional callback(done, total, batch_results, error) called after each batch.

    Returns list of {description, category, confidence} dicts.
    """
    results: list[dict | None] = [None] * len(descriptions)
    uncached: list[tuple[int, str]] = []

    for i, desc in enumerate(descriptions):
        cache_key = f"cat:{hashlib.md5(desc.encode()).hexdigest()}"
        cached = cache_get(cache_key)
        if cached:
            results[i] = cached
        else:
            uncached.append((i, desc))

    total = len(descriptions)
    cached_count = total - len(uncached)

    if cached_count and on_batch:
        on_batch(cached_count, total, [(i, r) for i, r in enumerate(results) if r is not None], None)

    if not uncached:
        return [r for r in results if r is not None]

    cat_list = "\n".join(f"- {c}" for c in categories)
    done = cached_count

    for batch_start in range(0, len(uncached), _BATCH_SIZE):
        batch = uncached[batch_start : batch_start + _BATCH_SIZE]
        batch_text = "\n".join(f"- {desc}" for _, desc in batch)
        prompt = _PROMPT_TEMPLATE.format(categories=cat_list, transactions=batch_text)

        batch_results = []
        error = None
        try:
            response = llm_complete(prompt, provider=provider)
            parsed = _extract_json_array(response)

            for (idx, desc), item in zip(batch, parsed):
                result = {
                    "description": desc,
                    "category": item.get("category", "Other"),
                    "confidence": float(item.get("confidence", 0.5)),
                }
                results[idx] = result
                batch_results.append((idx, result))
                cache_key = f"cat:{hashlib.md5(desc.encode()).hexdigest()}"
                cache_set(cache_key, result)
        except Exception as e:
            error = str(e)
            log.warning("Categorization batch failed: %s", e)

        done += len(batch)
        if on_batch:
            on_batch(done, total, batch_results, error)

    return [
        r if r else {"description": descriptions[i], "category": "Other", "confidence": 0.0}
        for i, r in enumerate(results)
    ]


def _extract_json_array(text: str) -> list[dict]:
    import re
    text = re.sub(r"```\w*\n?", "", text)
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        return []
    return json.loads(text[start:end])
