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
from typing import Dict

import config

__all__ = ["analyze_prompt"]


def _simple_category_mapping(prompt: str) -> Dict[str, any]:
    """Fallback category mapping when the LLM is unavailable.

    This simple mapping attempts to infer the product category from
    keywords present in the user's prompt. It mirrors the logic of
    the original ``_simple_category_mapping`` helper in the monolithic
    script.

    Args:
        prompt: The user's raw prompt string.

    Returns:
        A dictionary with default values filled in for all expected
        criteria keys.
    """
    prompt_lower = prompt.lower()
    category = ""

    # Basic keyword matching for category detection
    if "akıllı saat" in prompt_lower or "smart watch" in prompt_lower:
        category = "Akıllı Saat"
    elif "kulak içi" in prompt_lower and "kulaklık" in prompt_lower:
        category = "Kulak İçi Bluetooth Kulaklık"
    elif "kulaklık" in prompt_lower:
        category = "Kulaklık"
    elif "süpürge" in prompt_lower:
        category = "Süpürge"
    elif "telefon" in prompt_lower:
        category = "Cep Telefonu"
    elif "laptop" in prompt_lower:
        category = "Laptop"

    print(f"DEBUG: Basit kategori mapping: '{prompt_lower}' → '{category}'")

    return {
        "category_search_string": category,
        "text_search": prompt,
        "negative_text_search": "",
        "price_min": 0,
        "price_max": 99999,
        "min_rating": 0.0,
    }


def analyze_prompt(prompt: str) -> Dict[str, any]:
    """Analyse the user's request to produce structured search criteria.

    If a generative model is configured (``config._model`` is not
    ``None``), this function will delegate to Gemini to extract
    category, positive keywords, negative keywords and price ranges.
    Otherwise, or if an error occurs, it falls back to the simple
    keyword-based mapping.

    Args:
        prompt: The raw user prompt in Turkish.

    Returns:
        A dictionary containing the parsed criteria.
    """
    model = config._model
    if model:
        # Prepare the prompt for the LLM. The template is largely the
        # same as in the original script, instructing the model how to
        # parse the user's request into JSON.
        prompt_template = f"""
        Analyze the user's Turkish request to create a search query. Your goal is to separate desired features (positive) from undesired features (negative).

        MEVCUT KATEGORİLER (veritabanında bulunan ana kategoriler):
        
        KULAKLİK KATEGORİLERİ:
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

        Generate a JSON object with these keys:
        - "category_search_string": Choose the MOST SPECIFIC matching category from the list above, use empty string if no match
        - "text_search": Keywords for desired features (e.g., "büyük oda", "portatif", "sessiz")
        - "negative_text_search": Keywords for features the user explicitly DOES NOT want
        - "price_min": Minimum price (0 if not specified)
        - "price_max": Maximum price (99999 if not specified)  
        - "min_rating": Minimum rating (0 if not specified)

        CATEGORY MATCHING EXAMPLES:
        - "vantilatör" → "Vantilatör"
        - "fan" → "Vantilatör" 
        - "kulak içi kulaklık" → "Kulak İçi Bluetooth Kulaklık"
        - "robot süpürge" → "Robot Süpürge"
        - "laptop" → "Laptop"
        - "akıllı saat" → "Akıllı Saat"
        - "telefon" → "Cep Telefonu"

        PRICE HANDLING:
        - "1500-2500 arası" → price_min: 1500, price_max: 2500
        - "2000 TL altında" → price_min: 0, price_max: 2000
        - "500 TL üstü" → price_min: 500, price_max: 99999
        - No price mentioned → price_min: 0, price_max: 99999

        User Request: "{prompt}"

        Example 1: "bana büyük bir odayı serinletmek için kullanabileceğim vantilatör öner"
        {{
            "category_search_string": "Vantilatör",
            "text_search": "büyük oda serinletme portatif güçlü",
            "negative_text_search": "",
            "price_min": 0,
            "price_max": 99999,
            "min_rating": 0
        }}

        Example 2: "gürültü engelleme olmasın, 1000 liradan ucuz kulaklık"
        {{
            "category_search_string": "Kulaklık",
            "text_search": "",
            "negative_text_search": "gürültü engelleme anc aktif gürültü önleme",
            "price_min": 0,
            "price_max": 1000,
            "min_rating": 0
        }}

        Example 3: "sessiz çalışan robot süpürge 5000-10000 arası"
        {{
            "category_search_string": "Robot Süpürge",
            "text_search": "sessiz",
            "negative_text_search": "",
            "price_min": 5000,
            "price_max": 10000,
            "min_rating": 0
        }}

        Example 4: "gürültü engelleme özelliği olan kulak içi kulaklık"
        {{
            "category_search_string": "Kulak İçi Bluetooth Kulaklık",
            "text_search": "gürültü engelleme anc aktif gürültü önleme",
            "negative_text_search": "",
            "price_min": 0,
            "price_max": 99999,
            "min_rating": 0
        }}

        JSON Output:
        """
        try:
            response = model.generate_content(prompt_template)
            cleaned_response = (
                response.text.strip()
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )
            result = json.loads(cleaned_response)

            # Validate price bounds to avoid nonsensical output from the model
            if result.get("price_min", 0) > result.get("price_max", 99999):
                result["price_min"] = 0
            if result.get("price_max", 0) == 0:
                result["price_max"] = 99999

            return result
        except Exception as e:
            print(f"Gemini analiz hatası: {e}")
            # Fallback to simple mapping on any failure
            return _simple_category_mapping(prompt)
    else:
        # No model available → fallback to the simple mapping
        return _simple_category_mapping(prompt)