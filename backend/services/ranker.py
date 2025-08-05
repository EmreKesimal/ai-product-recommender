"""
Ranking products based on hybrid scores combining quality, LLM scores,
price-value considerations and text relevance.

The ``rank_products`` function sorts a list of products according to
the user's priority and the structure of the candidate set. It
implements a quartile-based price analysis and uses the LLM score
annotated on each product to weight the final ranking. This is a
straightforward extraction of the ranking logic from the original
monolithic script.
"""

import math
from typing import Any, Dict, List

from services.utils import (
    _parse_float_safe,
    _get_effective_rating,
    _get_effective_review_count,
)

__all__ = ["rank_products"]


def rank_products(
    products: List[Dict[str, Any]],
    criteria: Dict[str, Any],
    user_priority: str = "FİYAT_PERFORMANS",
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Rank products according to hybrid quality and relevance criteria.

    Args:
        products: A list of product documents that have already been
            scored by the LLM (i.e. contain an ``_llm_score`` field).
        criteria: The normalised search criteria (used for text
            relevance and price constraints).
        user_priority: The user's inferred priority, one of
            ``"KALİTE"``, ``"FİYAT_PERFORMANS"``, ``"BÜTÇELİ"`` or
            ``"ÖZEL_ÖZELLİK"``.
        top_n: The maximum number of products to return.

    Returns:
        A list of up to ``top_n`` products sorted by descending
        hybrid score.
    """
    if not products:
        return []
    # Compute price statistics
    prices = [
        _parse_float_safe((prod.get("price", {}) or {}).get("current", 0))
        for prod in products
    ]
    prices = [p for p in prices if p > 0]
    if prices:
        prices_sorted = sorted(prices)
        n = len(prices_sorted)
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = prices_sorted[q1_idx]
        q3 = prices_sorted[q3_idx]
        avg_price = sum(prices) / len(prices)
        print(
            f"DEBUG: Ranking Fiyat analizi ({user_priority}) - Q1: {q1:.0f}, Q3: {q3:.0f}, Ortalama: {avg_price:.0f}"
        )
    else:
        q1 = q3 = avg_price = 0
    ranked_list: List[tuple] = []
    text_to_search = criteria.get("text_search", "").lower().split()
    user_has_price_preference = (
        criteria.get("price_min", 0) > 0
        or criteria.get("price_max", 99999) < 99999
    )
    for prod in products:
        rating = _get_effective_rating(prod)
        review_count = _get_effective_review_count(prod)
        quality_score = rating * math.log(review_count + 2)
        llm_score = prod.get("_llm_score", 5.0)
        llm_relevance = llm_score / 10.0  # normalise 1-10 to 0.1-1.0
        # Text relevance
        text_relevance_score = 0
        if text_to_search:
            full_text = " ".join(
                [
                    prod.get("title", ""),
                    prod.get("brand", ""),
                ]
                + (prod.get("categories", []))
                + [f"{k} {v}" for k, v in (prod.get("features", {}) or {}).items()]
            ).lower()
            for keyword in text_to_search:
                if keyword in full_text:
                    text_relevance_score += 1
        text_relevance = (
            min(text_relevance_score / max(len(text_to_search), 1), 1.0)
            if text_to_search
            else 0.5
        )
        # Price-value score depending on user priority and price quartiles
        price = _parse_float_safe((prod.get("price", {}) or {}).get("current", 0))
        price_value_score = 1.0
        if price > 0 and not user_has_price_preference and avg_price > 0:
            if user_priority == "KALİTE":
                if price > q3:
                    price_value_score = 1.2
                elif price > avg_price:
                    price_value_score = 1.1
                elif price < q1:
                    price_value_score = 0.8
                else:
                    price_value_score = 1.0
            elif user_priority == "BÜTÇELİ":
                if price < q1:
                    price_value_score = 1.3
                elif price < avg_price:
                    price_value_score = 1.1
                elif price < q3:
                    price_value_score = 0.9
                else:
                    price_value_score = 0.7
            else:
                # FİYAT_PERFORMANS or ÖZEL_ÖZELLİK
                if q1 <= price <= q3:
                    price_value_score = 1.2
                elif price < q1:
                    price_value_score = 0.9
                else:
                    price_value_score = 0.8
        # Hybrid score combining quality, price value, LLM relevance and text relevance
        hybrid_score = (
            quality_score
            * price_value_score
            * (1 + llm_relevance)
            * (1 + text_relevance * 0.5)
        )
        # Determine the price segment for debug output
        segment = "Orta"
        if price < q1:
            segment = "Düşük"
        elif price > q3:
            segment = "Yüksek"
        print(
            f"DEBUG: Sıralama: {prod.get('title', '')[:30]}... | Fiyat: {price:.0f}TL ({segment}) | Kalite: {quality_score:.1f} | Heuristik Seçim: {llm_score:.1f}/10 | Final: {hybrid_score:.1f}"
        )
        ranked_list.append((hybrid_score, prod))
    ranked_list.sort(key=lambda x: x[0], reverse=True)
    return [prod for score, prod in ranked_list[:top_n]]