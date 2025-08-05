"""
Helper functions for parsing and normalising product data and search criteria.

These functions encapsulate common operations such as safely parsing
numbers from arbitrary input, computing effective ratings from product
documents, and normalising user-provided search criteria. They are
extracted into a separate module to promote reusability and make the
business logic easier to follow.
"""

import re
from typing import Any, Dict, List

__all__ = [
    "_parse_int_safe",
    "_parse_float_safe",
    "_get_effective_rating",
    "_get_effective_review_count",
    "normalize_criteria",
]


def _parse_int_safe(x: Any) -> int:
    """Safely parse an integer from various input types."""
    if x is None:
        return 0
    if isinstance(x, (int, float)):
        return int(x)
    s = str(x)
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0


def _parse_float_safe(x: Any) -> float:
    """Safely parse a floating-point number from arbitrary input."""
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _get_effective_rating(p: Dict[str, Any]) -> float:
    """Return a product's rating as a float, defaulting to 0.0."""
    return max(_parse_float_safe(p.get("rating")), 0.0)


def _get_effective_review_count(p: Dict[str, Any]) -> int:
    """Return the effective number of reviews for a product."""
    rc_raw = p.get("rating_count") or p.get("ratingCount")
    rating_count_from_db = _parse_int_safe(rc_raw)
    reviews_list = p.get("reviews") or []
    num_of_reviews = len(reviews_list) if isinstance(reviews_list, list) else 0
    return max(rating_count_from_db, num_of_reviews)


def normalize_criteria(c: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise and validate user-provided search criteria.
    Expands an exact price (min == max > 0) by ±10 % (minimum ±100 TL)
    so that a query like “10 000 TL telefon” becomes 9 000–11 000 TL.
    """
    out: Dict[str, Any] = dict(c or {})
    # Normalise rating
    mr = _parse_float_safe(out.get("min_rating", 4.0))
    out["min_rating"] = max(0.0, min(5.0, mr if mr != 0.0 or "min_rating" in out else 4.0))
    # Parse price bounds
    out["price_min"] = max(0, int(_parse_float_safe(out.get("price_min", 0))))
    out["price_max"] = int(_parse_float_safe(out.get("price_max", 99999)))
    # Expand if exact price
    if out["price_min"] > 0 and out["price_min"] == out["price_max"]:
        target = out["price_min"]
        delta = max(100, int(target * 0.1))
        out["price_min"] = max(0, target - delta)
        out["price_max"] = target + delta
    # Ensure min/max order
    if out["price_max"] < out["price_min"]:
        out["price_max"] = out["price_min"]
    # Clean strings
    out["category_search_string"] = (out.get("category_search_string") or "").strip()
    out["text_search"] = (out.get("text_search") or "").strip()
    out["negative_text_search"] = (out.get("negative_text_search") or "").strip()
    return out