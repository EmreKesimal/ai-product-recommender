from __future__ import annotations

import math
from typing import Dict, List, Tuple, Any

from services.utils import (
    _parse_float_safe,
    _get_effective_rating,
    _get_effective_review_count,
)

__all__ = ["heuristic_filter_and_score"]

def heuristic_filter_and_score(
    products: List[Dict[str, Any]], positive_keywords: str, negative_keywords: str
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Heuristic (non-LLM) filtering + scoring.

    - Stage 1: Pre-filtering (rating >= 2.5 and >= 3 reviews)
    - Stage 2: Smart selection (up to 10 candidates across price segments)
    - Stage 3: Default priority: 'FİYAT_PERFORMANS'
    - Stage 4: Simplified scoring: _llm_score = rating * 2
    """
    if not products:
        return products, "FİYAT_PERFORMANS"

    # Stage 1
    pre_filtered: List[Dict[str, Any]] = []
    for product in products:
        rating = _get_effective_rating(product)
        reviews = _get_effective_review_count(product)
        if rating >= 2.5 and reviews >= 3:
            pre_filtered.append(product)

    if not pre_filtered:
        return [], "FİYAT_PERFORMANS"

    # Stage 2
    text_keywords = [
        word.strip().lower()
        for word in (positive_keywords or "").split()
        if len(word.strip()) > 2
    ]
    llm_candidates: List[Dict[str, Any]] = []
    if len(pre_filtered) <= 10:
        llm_candidates = pre_filtered
    else:
        prices = [
            _parse_float_safe((prod.get("price", {}) or {}).get("current", 0))
            for prod in pre_filtered
        ]
        prices = [p for p in prices if p > 0]
        if prices:
            prices_sorted = sorted(prices)
            n = len(prices_sorted)
            s = n // 4
            low_max = prices_sorted[s] if s < n else prices_sorted[-1]
            mid_low_max = prices_sorted[2 * s] if 2 * s < n else prices_sorted[-1]
            mid_high_max = prices_sorted[3 * s] if 3 * s < n else prices_sorted[-1]
            segments = {"low": [], "mid_low": [], "mid_high": [], "high": []}
            for prod in pre_filtered:
                price_val = _parse_float_safe((prod.get("price", {}) or {}).get("current", 0))
                rating_val = _get_effective_rating(prod)
                review_val = _get_effective_review_count(prod)
                quality = rating_val * math.log(review_val + 2)
                text_rel = 0.5
                if text_keywords:
                    full_text = " ".join(
                        [prod.get("title", ""), prod.get("brand", "")]
                        + (prod.get("categories", []) or [])
                        + [f"{k} {v}" for k, v in (prod.get("features", {}) or {}).items()]
                    ).lower()
                    count = sum(1 for kw in text_keywords if kw in full_text)
                    text_rel = min(count / len(text_keywords), 1.0)
                score = quality * (1 + 2 * text_rel)
                if price_val <= low_max:
                    segments["low"].append((score, prod))
                elif price_val <= mid_low_max:
                    segments["mid_low"].append((score, prod))
                elif price_val <= mid_high_max:
                    segments["mid_high"].append((score, prod))
                else:
                    segments["high"].append((score, prod))
            limits = {"low": 0, "mid_low": 2, "mid_high": 5, "high": 3}
            for name, items in segments.items():
                items.sort(key=lambda x: x[0], reverse=True)
                llm_candidates += [prod for _, prod in items[:limits[name]]]
        else:
            scored: List[Tuple[float, Dict[str, Any]]] = []
            for prod in pre_filtered:
                rating_val = _get_effective_rating(prod)
                review_val = _get_effective_review_count(prod)
                quality = rating_val * math.log(review_val + 2)
                text_rel = 0.5
                if text_keywords:
                    full_text = " ".join(
                        [prod.get("title", ""), prod.get("brand", "")]
                        + (prod.get("categories", []) or [])
                        + [f"{k} {v}" for k, v in (prod.get("features", {}) or {}).items()]
                    ).lower()
                    count = sum(1 for kw in text_keywords if kw in full_text)
                    text_rel = min(count / len(text_keywords), 1.0)
                scored.append((quality * (1 + 2 * text_rel), prod))
            scored.sort(key=lambda x: x[0], reverse=True)
            llm_candidates = [prod for _, prod in scored[:10]]

    # Stage 3
    priority = "FİYAT_PERFORMANS"

    # Stage 4
    scored_products: List[Dict[str, Any]] = []
    for prod in llm_candidates:
        new_prod = prod.copy()
        new_prod["_llm_score"] = _get_effective_rating(prod) * 2
        scored_products.append(new_prod)

    return scored_products, priority