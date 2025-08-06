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
from formatting.mappings import FEATURE_MAPPINGS, CATEGORY_PREFERENCES, FEATURE_EQUALS_MAPPINGS, NEGATIVE_CATEGORY_ROUTING

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
    category_str: str = (criteria.get("category_search_string") or "").strip()
    text_search_str: str = (criteria.get("text_search") or "").strip()
    negative_text: str = (criteria.get("negative_text_search") or "").strip()
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
    # 1) Smart category switching based on negative keywords
    if category_str and negative_text:
        category_lower = category_str.lower()
        negative_lower = negative_text.lower()

        # New routing table (authoritative)
        routed = None
        for (cat_key, neg_key), target_cat in NEGATIVE_CATEGORY_ROUTING.items():
            if cat_key in category_lower and neg_key in negative_lower:
                routed = target_cat
                break

        # Fallback to legacy preferences if no new routing matched
        if not routed:
            for (cat_key, neg_key), preferred_cat in CATEGORY_PREFERENCES.items():
                if cat_key in category_lower and neg_key in negative_lower:
                    routed = preferred_cat
                    break

        if routed and routed != updated_category:
            print(
                f"DEBUG: Akıllı kategori yönlendirme: '{category_str}' + "
                f"'NOT {negative_text}' → '{routed}'"
            )
            updated_category = routed

    # ---------------------------------------------------------------------
    # 2) Smart feature filtering (positive & negative)
    #    - FEATURE_EQUALS_MAPPINGS → (field == value) or (field != value)
    #    - FEATURE_MAPPINGS → field:'Var' / field:'Yok' (legacy)
    features_filters: Dict[str, Any] = {}

    # 2a) Equality-based hints (positive)
    if text_search_str:
        t = text_search_str.lower()
        for key, (field, value) in FEATURE_EQUALS_MAPPINGS.items():
            if key in t:
                # If we already set a constraint for this field via negative, prefer explicit equality.
                features_filters[field] = value
                print(f"DEBUG: POZİTİF feature (equals): '{key}' → {field} == '{value}'")

    # 2b) Equality-based hints (negative → $ne), but do not override a positive equality set above
    if negative_text:
        n = negative_text.lower()
        for key, (field, value) in FEATURE_EQUALS_MAPPINGS.items():
            if key in n and field not in features_filters:
                features_filters[field] = {"$ne": value}
                print(f"DEBUG: NEGATİF feature (not equals): '{key}' → {field} != '{value}'")

    # 2c) Legacy Var/Yok mapping (positive)
    if text_search_str:
        text_lower = text_search_str.lower()
        for feature_key, mongo_field in FEATURE_MAPPINGS.items():
            if feature_key in text_lower and mongo_field not in features_filters:
                features_filters[mongo_field] = "Var"
                print(f"DEBUG: POZİTİF özellik (Var/Yok): '{feature_key}' → {mongo_field}:'Var'")

    # 2d) Legacy Var/Yok mapping (negative)
    if negative_text:
        negative_lower = negative_text.lower()
        for feature_key, mongo_field in FEATURE_MAPPINGS.items():
            if feature_key in negative_lower and mongo_field not in features_filters:
                features_filters[mongo_field] = "Yok"
                print(f"DEBUG: NEGATİF özellik (Var/Yok): '{feature_key}' → {mongo_field}:'Yok'")

    # Merge feature filters into the base query
    if features_filters:
        base_query.update(features_filters)
        print(f"DEBUG: Feature filtreleri eklendi: {features_filters}")

    return base_query, updated_category