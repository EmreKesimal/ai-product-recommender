"""
Product description generation and card formatting.

This module provides two utility functions:

* ``generate_product_description``: Uses the LLM (if available) to
  produce a natural language description of a product based on its
  features, ratings, reviews and Q&A data. When the LLM is not
  available or an error occurs, the function falls back to simply
  returning the product title.

* ``to_card``: Formats a product dictionary into a simplified card
  representation suitable for returning to the frontend. It attaches
  the generated description and extracts a handful of other useful
  fields like image, rating, price and URL.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import config
from services.utils import (
    _get_effective_rating,
    _get_effective_review_count,
)

__all__ = ["generate_product_description", "to_card"]


def generate_product_description(product: Dict[str, Any]) -> str:
    """
    Generate a concise description for a product.

    If the Gemini model is configured, this function sends a prompt
    instructing the model to compose a natural language summary. The
    summary describes the rating, highlights inferred from reviews and
    includes notable features. Certain rules are enforced to avoid
    quoting user reviews verbatim and to steer clear of marketing
    clichés.

    When no model is configured, the product's title is returned
    directly. A debug message is printed for each invocation so that
    callers can verify how many products have descriptions generated.

    Args:
        product: A product document with at least a title and rating.

    Returns:
        A descriptive paragraph about the product in Turkish.
    """
    title = product.get("title", "")
    # Debug: log that description generation is happening for this product
    print(f"DEBUG: generate_product_description called for '{title[:30]}...'", flush=True)

    rating = product.get("rating", 0)
    features = product.get("features", {}) or {}
    reviews = product.get("reviews", [])
    qa_data = product.get("qa", [])

    # Build a context string summarising the product
    context = f"Ürün: {title}\nPuan: {rating} / 5\n"
    if features:
        context += "Özellikler:\n"
        for i, (k, v) in enumerate(features.items()):
            if i >= 5:
                break
            context += f"- {k}: {v}\n"
    if reviews:
        context += "Kullanıcı Yorumları:\n"
        for i, review in enumerate(reviews[:3]):
            context += f"- {review}\n"
    if qa_data:
        context += "Soru-Cevaplar:\n"
        for i, qa in enumerate(qa_data[:2]):
            context += f"- {qa}\n"

    # Template for the generative model
    tpl = f"""
Bu ürün hakkında doğal ve bilgilendirici açıklama yaz.

**Ürün Bilgileri:**
{context}

**Yazma Kuralları:**

1. İLK CÜMLE - Rating ile başla ama her seferinde aşağıdakilerden rastgele birini kullan:
   • "{rating}/5 yıldız alan..."
   • "{rating} puan ortalamasına sahip..."  
   • "Kullanıcılardan {rating}/5 değerlendirme alan..."
   • "{rating} yıldızlı..."
   • "{rating} puanla dikkat çeken..."
   • "Ortalama {rating} yıldızla değerlendirilen..."
   • "Kullanıcılardan aldığı {rating}/5 puan ile öne çıkan..."
   • "{rating} yıldız alarak kullanıcıların beğenisini kazanan..."
   • "{rating} puanı ile dikkat çeken..."
   • "{rating} üzerinden değerlendirilen..."

2. YORUMLARDAN ÇIKARIM YAP - Direkt alıntı yapma:
   ✅ "Kullanıcılar ses kalitesinden övgüyle bahsediyor"
   ✅ "Pil ömrü konusunda olumlu geri dönüşler alıyor"
   ❌ "Ahmet yazdı: çok güzel ürün"

3. ÖZELLİKLERİ BELİRT:
   • Öne çıkan teknik özellikler
   • Kullanım alanları
   • Kalite unsurları
   • Olmayan özellikler hakkında yorum katmadan bilgi ver

4. YASAK:
   • Fiyat belirtme
   • Abartılı pazarlama dili
   • "Kesinlikle", "tam size göre" gibi klişeler
   • Direkt yorum alıntısı

**Format:** 4-5 cümle, tek paragraf, doğal dil.
    """

    model = config._model
    if model:
        try:
            resp = model.generate_content(tpl)
            return (resp.text or "").strip()
        except Exception as exc:
            print(f"Error generating product description: {exc}")
            return title
    # Fallback when no model is available
    return title


def to_card(prod: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a product document into a simplified card structure.

    The card includes the primary image, title, effective rating and
    review count, price, product URL and a short description. If
    multiple images are available, the first one is chosen. A debug
    message is printed each time a card is created to ensure that
    description generation is only triggered for the top-ranked
    products.

    Args:
        prod: A product document retrieved from the database.

    Returns:
        A dictionary containing key fields for display in the frontend.
    """
    # Debug: log card creation
    print(f"DEBUG: to_card called for '{prod.get('title', '')[:30]}...'", flush=True)

    images = prod.get("images") or []
    image: Optional[str] = images[0] if images else None
    return {
        "image": image,
        "title": prod.get("title"),
        "rating": _get_effective_rating(prod),
        "rating_count": _get_effective_review_count(prod),
        "price": (prod.get("price") or {}).get("current", "N/A"),
        "link": prod.get("product_url") or prod.get("productUrl"),
        "description": generate_product_description(prod),
    }