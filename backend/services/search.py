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

from config import products_collection
from filters.smart_query import build_smart_query

__all__ = ["find_products_by_criteria"]

# ---------------------------------------------------------------------------
# Negative category exclusion mapping
#
# Some negative keywords correspond to specific categories that should be
# excluded from search results when they appear in the user's negative
# query. For example, a request like "dikey olmasın" should exclude
# products belonging to the "Dik Süpürge" category. This mapping can
# be extended to cover additional negative category intents.
def category_exists(category_name: str) -> bool:
    """
    Return True if there is at least one product in the given category
    across the entire DB (ignores price/rating/text filters).
    If category_name is empty, return False (we want to block category-less runs now).
    """
    if not category_name:
        print("DEBUG: category_exists: empty category_name -> False (block category-less search)")
        return False
    try:
        count = products_collection.count_documents({"categories": category_name}, limit=1)
        exists = count > 0
        print(f"DEBUG: category_exists('{category_name}') -> {exists}")
        return exists
    except Exception as e:
        # If DB check fails, be conservative and block.
        print(f"DEBUG: category_exists error: {e} -> returning False")
        return False


def find_products_by_criteria(criteria: Dict[str, Any], limit: int = 300) -> List[Dict[str, Any]]:
    """
    Layered MongoDB search STRICTLY LOCKED to category when provided.
    NEW RULES:
      - If no category can be determined, DO NOT perform category-less searches
        (return empty immediately).
      - If a category is provided, we NEVER drop it during relaxations.
    """
    if not criteria:
        return []

    base_query, updated_category = build_smart_query(criteria)

    # HARD-STOP: no category → no search
    if not updated_category:
        print("DEBUG: Kategori tespit edilemedi; kategorisiz arama devre dışı. Boş dönülüyor.")
        return []

    text_search_str = (criteria.get("text_search") or "").strip()

    print(
        f"DEBUG: Akıllı sorgulama - Kategori: '{updated_category}', "
        f"Features filtreli: {len([k for k in base_query.keys() if str(k).startswith('features')]) > 0}"
    )

    queries_to_try: List[Tuple[str, Dict[str, Any]]] = []

    # 1) Specific category (strict)
    specific_query = base_query.copy()
    specific_query["categories"] = updated_category
    queries_to_try.append(("Spesifik Kategori", specific_query))
    print(f"DEBUG: Spesifik kategori sorgusu: {specific_query}")

    # 1b) Category-only flexible (keep category, loosen price/rating)
    category_flexible_query = {
        "categories": updated_category,
        "price.current": {"$gte": 0, "$lte": 99999},
        "rating": {"$gte": 0.0},
        "rating_count": {"$gte": 0},
    }
    queries_to_try.append(("Kategori Fiyat Genişletilmiş", category_flexible_query))
    print(f"DEBUG: {updated_category} için fiyat genişletilmiş sorgu: {category_flexible_query}")

    # 1c) General category regex (still locked to category)
    category_words = [w.strip() for w in updated_category.split() if len(w.strip()) > 3]
    if category_words:
        for main_word in category_words:
            general_query = base_query.copy()
            general_query["categories"] = {"$regex": main_word, "$options": "i"}
            queries_to_try.append((f"Genel Kategori ({main_word})", general_query))

    # 2) Text search (LOCKED to category by keeping base_query fields)
    if text_search_str:
        text_query = base_query.copy()
        text_query["$text"] = {"$search": text_search_str}
        text_query["categories"] = updated_category
        queries_to_try.append(("Text Search (Kategori Kilitli)", text_query))

    # 3) Loose baseline (still LOCKED to category)
    loose_query = {
        "categories": updated_category,
        "price.current": {
            "$gte": criteria.get("price_min", 0),
            "$lte": criteria.get("price_max", 99999),
        },
        "rating": {"$gte": max(criteria.get("min_rating", 0.0), 0.0)},
        "rating_count": {"$gte": 0},
    }
    queries_to_try.append(("Gevşek Temel Filtreler (Kategori Kilitli)", loose_query))

    # Execute
    for query_name, query in queries_to_try:
        try:
            print(f"DEBUG: {query_name} Sorgusu:")
            candidates = products_collection.find(query).limit(limit)
            result = list(candidates)
            print(f"DEBUG: {query_name} - {len(result)} ürün bulundu")
            if result:
                return result
        except Exception as e:
            print(f"DEBUG: {query_name} sorgu hatası: {e}")
            continue

    print("DEBUG: Hiçbir sorguda ürün bulunamadı")
    return []