"""
Building smart MongoDB queries from user criteria.

The ``build_smart_query`` function encapsulates the logic for
constructing a MongoDB query based on high-level user criteria. It
handles price and rating filters, smart category redirection via
``CATEGORY_PREFERENCES``, and the translation of positive and negative
feature keywords into ``features`` subdocument filters via
``FEATURE_MAPPINGS``. The function returns both the base MongoDB
query and the potentially updated category after applying negative
preferences.
"""

from typing import Any, Dict, Tuple
from mappings import FEATURE_MAPPINGS, CATEGORY_PREFERENCES

__all__ = ["build_smart_query"]


def build_smart_query(criteria: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Construct a smart MongoDB query from the given criteria.

    Args:
        criteria: A dictionary containing parsed user criteria, such as
            category strings, text searches, price ranges and rating
            thresholds.

    Returns:
        A tuple ``(base_query, updated_category)`` where ``base_query``
        is a MongoDB filter dict and ``updated_category`` reflects any
        smart category redirection applied due to negative feature
        preferences.
    """
    category_str: str = criteria.get("category_search_string", "").strip()
    text_search_str: str = criteria.get("text_search", "").strip()
    negative_text: str = criteria.get("negative_text_search", "").strip()
    price_min: float = criteria.get("price_min", 0)
    price_max: float = criteria.get("price_max", 99999)
    min_rating: float = criteria.get("min_rating", 0.0)

    # Basic quality filters applied to every query.
    base_query: Dict[str, Any] = {
        "price.current": {"$gte": price_min, "$lte": price_max},
        "rating": {"$gte": max(min_rating, 2.5)},
        "rating_count": {"$gte": 1},  # Looser rating_count condition
    }

    updated_category: str = category_str

    # ---------------------------------------------------------------------
    # Smart category switching based on negative keywords
    if category_str and negative_text:
        category_lower = category_str.lower()
        negative_lower = negative_text.lower()
        for (cat_key, neg_key), preferred_cat in CATEGORY_PREFERENCES.items():
            if cat_key in category_lower and neg_key in negative_lower:
                updated_category = preferred_cat
                print(
                    f"DEBUG: Akıllı kategori: '{category_str}' + '{neg_key} olmasın' → '{preferred_cat}'"
                )
                break

    # ---------------------------------------------------------------------
    # Smart feature filtering based on positive and negative keywords
    features_filters: Dict[str, Any] = {}

    # Positive feature search
    if text_search_str:
        text_lower = text_search_str.lower()
        for feature_key, mongo_field in FEATURE_MAPPINGS.items():
            if feature_key in text_lower:
                features_filters[mongo_field] = "Var"
                print(
                    f"DEBUG: POZİTİF özellik: '{feature_key}' → {mongo_field}:'Var'"
                )

    # Negative feature search
    if negative_text:
        negative_lower = negative_text.lower()
        for feature_key, mongo_field in FEATURE_MAPPINGS.items():
            if feature_key in negative_lower and mongo_field not in features_filters:
                features_filters[mongo_field] = "Yok"
                print(
                    f"DEBUG: NEGATİF özellik: '{feature_key}' → {mongo_field}:'Yok'"
                )

    # Merge feature filters into the base query
    if features_filters:
        base_query.update(features_filters)
        print(f"DEBUG: Features filtreleri eklendi: {features_filters}")

    return base_query, updated_category