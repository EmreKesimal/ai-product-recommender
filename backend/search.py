"""
High-level product search routines.

The ``find_products_by_criteria`` function implements a layered
search strategy on top of MongoDB. It first constructs a smart query
using ``smart_query.build_smart_query`` and then tries multiple
variants in sequence, progressively relaxing constraints until a
non-empty result set is found. This mirrors the behaviour of the
original monolithic implementation.
"""

from typing import Any, Dict, List, Tuple

import config
from smart_query import build_smart_query

__all__ = ["find_products_by_criteria"]

# ---------------------------------------------------------------------------
# Negative category exclusion mapping
#
# Some negative keywords correspond to specific categories that should be
# excluded from search results when they appear in the user's negative
# query. For example, a request like "dikey olmasın" should exclude
# products belonging to the "Dik Süpürge" category. This mapping can
# be extended to cover additional negative category intents.
NEGATIVE_CATEGORY_EXCLUSIONS = {
    # Süpürge/Kategori
    "dik": "Dik Süpürge",
    "dikey": "Dik Süpürge",
    # Kulaklık kategorileri
    "kulaküstü": "Kulak üstü Bluetooth kulaklık",
    "kulak üstü": "Kulak üstü Bluetooth kulaklık",
    "büyük": "Kulak üstü Bluetooth kulaklık",
    # Cep telefonu kategorileri
    "android": "Android Cep Telefonu",
    "iphone": "iPhone IOS Cep Telefonları",
}


def find_products_by_criteria(criteria: Dict[str, Any], limit: int = 300) -> List[Dict[str, Any]]:
    """Execute a layered MongoDB search based on the provided criteria.

    This function tries increasingly broad queries until it finds at
    least one product. It first applies the full smart query, then
    progressively relaxes category and price constraints. The search
    order and logic are identical to those in the original code.

    Args:
        criteria: The parsed and normalised search criteria.
        limit: Maximum number of products to retrieve per query.

    Returns:
        A list of product documents matching the search criteria.
    """
    if not criteria:
        return []

    # Build the base query and determine any updated category based on
    # negative preferences.
    base_query, updated_category = build_smart_query(criteria)

    # Prepare search strings
    text_search_str: str = criteria.get("text_search", "").strip()

    print(
        f"DEBUG: Akıllı sorgulama - Kategori: '{updated_category}', Features filtreli: {len([k for k in base_query.keys() if k.startswith('features')]) > 0}"
    )

    queries_to_try: List[Tuple[str, Dict[str, Any]]] = []

    # Phase 1: use the updated specific category if present
    if updated_category:
        specific_query = base_query.copy()
        specific_query["categories"] = updated_category
        queries_to_try.append(("Spesifik Kategori", specific_query))
        print(f"DEBUG: Spesifik kategori sorgusu: {specific_query}")

        # A more relaxed version of the specific category query (no price or rating constraints)
        category_flexible_query = {
            "categories": updated_category,
            "price.current": {"$gte": 0, "$lte": 99999},
            "rating": {"$gte": 0.0},
            "rating_count": {"$gte": 0},
        }
        queries_to_try.append(("Kategori Fiyat Genişletilmiş", category_flexible_query))
        print(f"DEBUG: {updated_category} için fiyat genişletilmiş sorgu: {category_flexible_query}")

        # Additional generic category search using regex on category words
        category_words = [word.strip() for word in updated_category.split() if len(word.strip()) > 3]
        if category_words:
            for main_word in category_words:
                general_query = base_query.copy()
                general_query["categories"] = {"$regex": main_word, "$options": "i"}
                queries_to_try.append((f"Genel Kategori ({main_word})", general_query))

    # Phase 2: text search if provided
    if text_search_str:
        text_query = base_query.copy()
        text_query["$text"] = {"$search": text_search_str}
        queries_to_try.append(("Text Search", text_query))

    # Phase 3: only basic filters (completely relaxed rating and rating_count)
    loose_query = {
        "price.current": {
            "$gte": criteria.get("price_min", 0),
            "$lte": criteria.get("price_max", 99999),
        },
        "rating": {"$gte": max(criteria.get("min_rating", 0.0), 0.0)},
        "rating_count": {"$gte": 0},
    }
    queries_to_try.append(("Gevşek Temel Filtreler", loose_query))

    # ---------------------------------------------------------------------
    # Apply negative category exclusions to all queries if necessary.
    # Determine which categories should be excluded based on the
    # negative_text_search in the criteria.
    exclude_categories: List[str] = []
    negative_lower = (criteria.get("negative_text_search", "") or "").lower()
    for keyword, cat_to_exclude in NEGATIVE_CATEGORY_EXCLUSIONS.items():
        if keyword in negative_lower:
            exclude_categories.append(cat_to_exclude)
    # If exclusions are present, wrap each query in an $and clause that
    # enforces the categories must not include any of the excluded
    # categories. This ensures, for example, that a "dikey" negative
    # keyword will prevent "Dik Süpürge" products from being returned
    # even during the general regex search phase.
    if exclude_categories:
        updated_queries: List[Tuple[str, Dict[str, Any]]] = []
        for query_name, query in queries_to_try:
            # Build a list of top-level conditions from the existing query
            conditions: List[Dict[str, Any]] = []
            for key, value in query.items():
                # When combining conditions into $and, $text should remain
                # intact as its own condition object.
                conditions.append({key: value})
            # Append the exclusion condition on categories
            conditions.append({"categories": {"$nin": exclude_categories}})
            # Assemble a new query using $and to combine all conditions
            new_query: Dict[str, Any] = {"$and": conditions}
            updated_queries.append((query_name, new_query))
        queries_to_try = updated_queries

    # Execute queries in order until we get results
    for query_name, query in queries_to_try:
        try:
            print(f"DEBUG: {query_name} Sorgusu:")
            candidates = config.products_collection.find(query).limit(limit)
            result = list(candidates)
            print(f"DEBUG: {query_name} - {len(result)} ürün bulundu")
            if result:
                return result
        except Exception as e:
            print(f"DEBUG: {query_name} sorgu hatası: {e}")
            continue

    # No results found after all strategies
    print("DEBUG: Hiçbir sorguda ürün bulunamadı")
    return []