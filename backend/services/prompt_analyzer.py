"""
Prompt analysis and simple category mapping.

The ``analyze_prompt`` function uses Gemini (if available) to parse a
user's natural language request into structured search criteria. It
extracts desired and undesired features, price ranges and category
preferences. When Gemini is unavailable or an error occurs, a
simplified heuristic-based category mapping is used instead.

This module isolates all prompt parsing logic so that it can be
maintained independently of the rest of the system.
"""

import json
import re
from typing import Dict, Any

import config

__all__ = ["analyze_prompt"]


def _simple_category_mapping(prompt: str) -> str:
    """
    Heuristic category mapping used when LLM is unavailable or leaves category empty.
    Extend with lightweight keyword checks. Turkish suffixes are naturally caught
    by 'in' checks (e.g., 'çantası', 'çantalı' still include 'çanta').
    """
    print("simplecategorymapping")
    p = (prompt or "").lower()

    # NEW: bag detection
    if "çanta" in p or "bag" in p:
        return "Çanta"

    # Existing electronics-focused hints (keep as before / expand if needed)
    if "akıllı saat" in p or "smart watch" in p:
        return "Akıllı Saat"
    if "kulak içi" in p and "kulaklık" in p:
        return "Kulak İçi Bluetooth Kulaklık"
    if "kulaklık" in p:
        return "Kulaklık"
    if "süpürge" in p:
        return "Süpürge"
    if "telefon" in p:
        return "Cep Telefonu"
    if "laptop" in p:
        return "Laptop"
    if "buzdolabı" in p:
        return "Buzdolabı"

    return ""


def analyze_prompt(prompt: str) -> Dict[str, Any]:
    """
    Analyse user's Turkish request and extract a structured criteria JSON.
    Prefers LLM (Gemini) when available; falls back to heuristics.
    IMPORTANT: We explicitly include 'Çanta' in the category list so that
    queries like 'kırmızı çanta' become category-locked and never leak into
    unrelated categories during fallbacks.
    """
    model = config._model

    if model:
        prompt_template = f"""
Analyze the user's Turkish request to create a search query. Your goal is to separate desired features (positive) from undesired features (negative).

MEVCUT KATEGORİLER (veritabanında bulunan ana kategoriler, mümkün olan en SPESİFİK olanı seç):
KULAKLIK:
- Kulak İçi Bluetooth Kulaklık
- Kulak üstü Bluetooth kulaklık
- Bluetooth Kulaklık
- Kulaklık

SOĞUTMA/ISITMA:
- Vantilatör
- Klima Isıtıcı

TEMİZLİK:
- Robot Süpürge
- Torbasız Süpürge
- Toz Torbalı Süpürge
- Dik Süpürge
- Süpürge
- Buharlı Temizleyici
- Halı Yıkama Makinesi

TELEFON/TABLET:
- Cep Telefonu
- Android Cep Telefonu
- iPhone IOS Cep Telefonları
- Tablet
- Telefon Aksesuarları

BİLGİSAYAR:
- Laptop
- Bilgisayar
- Oyuncu Dizüstü Bilgisayarı

AKILLI CİHAZLAR:
- Akıllı Saat
- Giyilebilir Teknoloji
- Akıllı Takip Cihazı

ŞARJ:
- Şarj Cihazları
- Araç Şarj Cihazı
- Şarj Kablosu

GENEL:
- Elektronik
- Elektrikli Ev Aletleri
- Buzdolabı



Generate a JSON object with these keys:
- "category_search_string": Choose the MOST SPECIFIC matching category from the list above, use empty string if no match
- "text_search": Keywords for desired features (e.g., "kırmızı", "omuz askılı", "deri")
- "negative_text_search": Keywords the user explicitly DOES NOT want
- "price_min": Minimum price (0 if not specified)
- "price_max": Maximum price (99999 if not specified)
- "min_rating": Minimum rating (0 if not specified)

PRICE HANDLING:
- "1500-2500 arası" → price_min: 1500, price_max: 2500
- "2000 TL altında" → price_min: 0, price_max: 2000
- "500 TL üstü" → price_min: 500, price_max: 99999
- Exact single price (e.g., "10000 TL") → DO NOT set both min and max to the same; leave as is (post-normalization will expand to ±10%)
- No price mentioned → price_min: 0, price_max: 99999

User Request: "{prompt}"

JSON Output:
        """.strip()

        try:
            response = model.generate_content(prompt_template)
            cleaned = (response.text or "").strip()
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()
            result = json.loads(cleaned)

            # Safety: ensure numeric sanity (post-normalize will also handle)
            if result.get("price_min", 0) > result.get("price_max", 99999):
                result["price_min"] = 0
            if result.get("price_max", 0) == 0:
                result["price_max"] = 99999

            # If LLM didn't pick any category but prompt clearly indicates one, map heuristically.
            if not (result.get("category_search_string") or "").strip():
                guessed = _simple_category_mapping(prompt)
                if guessed:
                    result["category_search_string"] = guessed

            return result
        except Exception as e:
            print(f"Gemini analiz hatası: {e}. Falling back to simple mapping.")

    # Fallback: simple mapping only
    category = _simple_category_mapping(prompt)
    return {
        "category_search_string": category,
        "text_search": (prompt or "").strip(),
        "negative_text_search": "",
        "price_min": 0,
        "price_max": 99999,
        "min_rating": 0.0,
    }