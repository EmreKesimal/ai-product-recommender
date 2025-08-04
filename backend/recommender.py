"""
Flask-based backend service for product recommendation and product
summarization powered by Gemini. Single-service architecture.

This version uses a two-step filtering process:
1. Fetch a broad set of candidates from MongoDB based on general criteria.
2. Use a second, LLM-powered step to perform detailed analysis on each candidate
   to filter out products based on negative requirements (e.g., "feature X should not exist").

Endpoints:
  POST /analyze-prompt
  POST /recommendation

To run:
  export GEMINI_API_KEY=<your_google_generative_ai_key>
  export MONGO_URI=<your_mongo_uri>
  python3 app.py

*** ÖNEMLİ KURULUM NOTU ***
Bu kodun verimli çalışması için MongoDB'de bir Text Index oluşturulmalıdır:
db.products.createIndex({ "$**": "text" })
"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv bulunamadı - environment variable'lar sistem ayarlarından alınacak")

import json
import re
import math
from typing import Any, Dict, List, Tuple

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, TEXT
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://scraper4253:yamandede403@cluster0.cv576qm.mongodb.net/scrapingdb?retryWrites=true&w=majority&appName=Cluster0")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "scrapingdb")
MONGO_COLLECTION_NAME = os.environ.get("MONGO_COLLECTION_NAME", "products")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]
products_collection = db[MONGO_COLLECTION_NAME]

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    generation_config = {"temperature": 0.2, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
    _model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=generation_config)
else:
    _model = None
    print("⚠️ GEMINI_API_KEY bulunamadı - basit kategori mapping sistemi aktif")

# ---------------------------------------------------------------------------
# AKILLI SORGULAMA SİSTEMİ - Genel çözüm tüm kategoriler için

# Özellik mapping sistemi - yeni özellikler kolayca eklenebilir
FEATURE_MAPPINGS = {
    "gürültü engelleme": "features.Aktif Gürültü Önleme (ANC)",
    "anc": "features.Aktif Gürültü Önleme (ANC)", 
    "aktif gürültü önleme": "features.Aktif Gürültü Önleme (ANC)",
    "kablosuz": "features.Bağlantı Türü",
    "bluetooth": "features.Bağlantı Türü",
    "pilli": "features.Güç Kaynağı",
    "şarjlı": "features.Güç Kaynağı",
    "su geçirmez": "features.Su Geçirmezlik",
    "toz geçirmez": "features.Toz Geçirmezlik"
}

# Kategori tercihleri - negatif durumda hangi kategoriye yönlendirilecek
CATEGORY_PREFERENCES = {
    ("süpürge", "dikey"): "Torbasız Süpürge",
    ("süpürge", "dik"): "Torbasız Süpürge", 
    ("kulaklık", "kulaküstü"): "Kulak İçi Bluetooth Kulaklık",
    ("kulaklık", "büyük"): "Kulak İçi Bluetooth Kulaklık",
    ("telefon", "android"): "iPhone IOS Cep Telefonları",
    ("telefon", "iphone"): "Android Cep Telefonu"
}

def build_smart_query(criteria: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Criteria'dan akıllı MongoDB query oluşturur.
    Return: (base_query, updated_category)
    """
    category_str = criteria.get("category_search_string", "").strip()
    text_search_str = criteria.get("text_search", "").strip()
    negative_text = criteria.get("negative_text_search", "").strip()
    price_min = criteria.get("price_min", 0)
    price_max = criteria.get("price_max", 99999)
    min_rating = criteria.get("min_rating", 0.0)
    
    # Temel kalite filtreleri
    base_query = {
        "price.current": {"$gte": price_min, "$lte": price_max},
        "rating": {"$gte": max(min_rating, 2.5)},
        "rating_count": {"$gte": 3}
    }
    
    updated_category = category_str
    
    # 1. AKILLI KATEGORİ DEĞİŞİMİ - Genel sistem
    if category_str and negative_text:
        category_lower = category_str.lower()
        negative_lower = negative_text.lower()
        
        for (cat_key, neg_key), preferred_cat in CATEGORY_PREFERENCES.items():
            if cat_key in category_lower and neg_key in negative_lower:
                updated_category = preferred_cat
                print(f"DEBUG: Akıllı kategori: '{category_str}' + '{neg_key} olmasın' → '{preferred_cat}'")
                break
    
    # 2. AKILLI ÖZELLİK FİLTRELEME - Genel sistem
    features_filters = {}
    
    # POZİTİF özellik arama (text_search'ten)
    if text_search_str:
        text_lower = text_search_str.lower()
        for feature_key, mongo_field in FEATURE_MAPPINGS.items():
            if feature_key in text_lower:
                features_filters[mongo_field] = "Var"
                print(f"DEBUG: POZİTİF özellik: '{feature_key}' → {mongo_field}:'Var'")
    
    # NEGATİF özellik arama (negative_text'ten)  
    if negative_text:
        negative_lower = negative_text.lower()
        for feature_key, mongo_field in FEATURE_MAPPINGS.items():
            if feature_key in negative_lower and mongo_field not in features_filters:
                features_filters[mongo_field] = "Yok"
                print(f"DEBUG: NEGATİF özellik: '{feature_key}' → {mongo_field}:'Yok'")
    
    # Features filtrelerini base_query'ye ekle
    if features_filters:
        base_query.update(features_filters)
        print(f"DEBUG: Features filtreleri eklendi: {features_filters}")
    
    return base_query, updated_category

# ---------------------------------------------------------------------------
# Helpers

def _parse_int_safe(x) -> int:
    if x is None: return 0
    if isinstance(x, (int, float)): return int(x)
    s = str(x)
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0


def _parse_float_safe(x) -> float:
    if x is None: return 0.0
    if isinstance(x, (int, float)): return float(x)
    s = str(x).strip().replace(",", ".")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try: return float(m.group(0))
        except ValueError: return 0.0
    try: return float(s)
    except ValueError: return 0.0


def _get_effective_rating(p: Dict[str, Any]) -> float:
    return max(_parse_float_safe(p.get("rating")), 0.0)


def _get_effective_review_count(p: Dict[str, Any]) -> int:
    rc_raw = p.get("rating_count") or p.get("ratingCount")
    rating_count_from_db = _parse_int_safe(rc_raw)
    reviews_list = p.get("reviews") or []
    num_of_reviews = len(reviews_list) if isinstance(reviews_list, list) else 0
    return max(rating_count_from_db, num_of_reviews)


def normalize_criteria(c: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(c or {})
    mr = _parse_float_safe(out.get("min_rating", 4.0))
    out["min_rating"] = max(0.0, min(5.0, mr if mr != 0.0 or "min_rating" in out else 4.0))
    out["price_min"] = max(0, int(_parse_float_safe(out.get("price_min", 0))))
    out["price_max"] = int(_parse_float_safe(out.get("price_max", 99999)))
    if out["price_max"] < out["price_min"]: out["price_max"] = out["price_min"]
    out["category_search_string"] = (out.get("category_search_string") or "").strip()
    out["text_search"] = (out.get("text_search") or "").strip()
    out["negative_text_search"] = (out.get("negative_text_search") or "").strip()
    return out


def analyze_prompt(prompt: str) -> Dict[str, Any]:
    """
    Kullanıcının isteğini, pozitif ve negatif anahtar kelimeleri ayıracak şekilde analiz eder.
    """
    if _model:
        # Online modda Gemini API kullan
        prompt_template = f"""
        Analyze the user's Turkish request to create a search query. Your goal is to separate desired features (positive) from undesired features (negative).

        MEVCUT KATEGORİLER (veritabanında bulunan ana kategoriler):
        
        KULAKLИK KATEGORİLERİ:
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
            response = _model.generate_content(prompt_template)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(cleaned_response)

            # Price validation
            if result.get("price_min", 0) > result.get("price_max", 99999):
                result["price_min"] = 0
            if result.get("price_max", 0) == 0:
                result["price_max"] = 99999

            return result
        except Exception as e:
            print(f"Gemini analiz hatası: {e}")
            # Fallback to simple mapping
            return _simple_category_mapping(prompt)
    else:
        # API yoksa basit mapping
        return _simple_category_mapping(prompt)

def _simple_category_mapping(prompt: str) -> Dict[str, Any]:
    """Basit kategori mapping - API olmadan"""
    prompt_lower = prompt.lower()
    category = ""
    
    # Basit kategori tespiti
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
        "min_rating": 0.0
    }


def find_products_by_criteria(criteria: Dict[str, Any], limit: int = 300) -> List[Dict[str, Any]]:
    """
    Genel akıllı sorgulama sistemi ile katmanlı MongoDB araması.
    Tüm özellik ve kategori mappingleri otomatik olarak uygulanır.
    """
    if not criteria: return []
    
    # Akıllı query oluştur
    base_query, updated_category = build_smart_query(criteria)
    
    # Text search string'i al
    text_search_str = criteria.get("text_search", "").strip()
    
    print(f"DEBUG: Akıllı sorgulama - Kategori: '{updated_category}', Features filtreli: {len([k for k in base_query.keys() if k.startswith('features')]) > 0}")
    
    queries_to_try = []

    # 1. Aşama: Güncellenmiş spesifik kategori varsa onu kullan
    if updated_category:
        specific_query = base_query.copy()
        # Array içinde exact match
        specific_query["categories"] = updated_category
        queries_to_try.append(("Spesifik Kategori", specific_query))
        
        # 2. Aşama: Genel kategori kelimeleri ile ara
        category_words = [word.strip() for word in updated_category.split() if len(word.strip()) > 3]
        if category_words:
            for main_word in category_words:
                general_query = base_query.copy()
                # Array içinde regex ile kelime arama
                general_query["categories"] = {"$regex": main_word, "$options": "i"}
                queries_to_try.append((f"Genel Kategori ({main_word})", general_query))

    # 3. Aşama: Text search varsa onu kullan
    if text_search_str:
        text_query = base_query.copy()
        text_query["$text"] = {"$search": text_search_str}
        queries_to_try.append(("Text Search", text_query))

    # 4. Aşama: Sadece temel filtreler (daha gevşek)
    loose_query = {
        "price.current": {"$gte": criteria.get("price_min", 0), "$lte": criteria.get("price_max", 99999)},
        "rating": {"$gte": max(criteria.get("min_rating", 0.0), 1.0)},
        "rating_count": {"$gte": 1}
    }
    queries_to_try.append(("Gevşek Temel Filtreler", loose_query))

    # Sorguları sırayla dene
    for query_name, query in queries_to_try:
        try:
            print(f"DEBUG: {query_name} Sorgusu:")
            candidates = products_collection.find(query).limit(limit)
            result = list(candidates)
            print(f"DEBUG: {query_name} - {len(result)} ürün bulundu")

            if result:  # Ürün bulundu, döndür
                return result

        except Exception as e:
            print(f"DEBUG: {query_name} sorgu hatası: {e}")
            continue

    # Hiçbir sorgu çalışmadıysa boş liste döndür
    print("DEBUG: Hiçbir sorguda ürün bulunamadı")
    return []


def comprehensive_llm_filter(products: List[Dict], positive_keywords: str, negative_keywords: str) -> Tuple[List[Dict], str]:
    """
    MongoDB filtrelemesinden sonra final LLM skorlama sistemi.
    Pre-filtering + LLM intent analizi + LLM skorlama.
    Return: (scored_products, user_priority)
    """
    if not products:
        return products, "FİYAT_PERFORMANS"

    # Negatif kelimeleri kontrol et
    has_negative = negative_keywords and negative_keywords.strip()

    print(f"DEBUG: Akıllı Scoring Sistemi - Pozitif: '{positive_keywords}', Negatif: '{negative_keywords}'. Aday: {len(products)}")

    # 1. AŞAMA: GÜÇLÜ PRE-FİLTERİNG (sadece çöp ürünleri ele)
    pre_filtered = []
    
    for product in products:
        title = product.get('title', '')
        title_lower = title.lower()
        features = product.get('features', {}) or {}
        rating = _get_effective_rating(product)
        review_count = _get_effective_review_count(product)
        
        should_exclude = False
        
        # Sadece çok kötü kaliteli ürünleri ele
        if rating < 2.5 or review_count < 3:
            should_exclude = True
            print(f"DEBUG: Kalite eleme: '{title[:25]}...' - Rating: {rating}, Reviews: {review_count}")
        
        if not should_exclude:
            pre_filtered.append(product)

    print(f"DEBUG: Pre-filtering sonrası: {len(pre_filtered)} ürün kaldı")

    if not pre_filtered:
        return [], "FİYAT_PERFORMANS"

    # 2. AŞAMA: AKILLI ÜRÜN SEÇİMİ (LLM'E GÖNDERİLECEK)
    # Çeşitli fiyat aralıklarından dengeli seçim
    prices = [_parse_float_safe((prod.get("price", {}) or {}).get("current", 0)) for prod in pre_filtered]
    prices = [p for p in prices if p > 0]

    # Text search kelimeleri hazırla
    text_keywords = [word.strip().lower() for word in positive_keywords.split() if len(word.strip()) > 2] if positive_keywords else []

    llm_candidates = []
    if len(pre_filtered) <= 24:
        # Az ürün varsa hepsini LLM'e gönder
        llm_candidates = pre_filtered
    else:
        # Fiyat segmentlerinden AKILLI seçim
        if prices:
            prices_sorted = sorted(prices)
            n = len(prices_sorted)

            # 4 fiyat segmenti oluştur
            segment_size = n // 4
            low_max = prices_sorted[segment_size] if segment_size < n else prices_sorted[-1]
            mid_low_max = prices_sorted[2 * segment_size] if 2 * segment_size < n else prices_sorted[-1]
            mid_high_max = prices_sorted[3 * segment_size] if 3 * segment_size < n else prices_sorted[-1]

            # Her segmentten hibrit skorla en iyileri seç
            segments = {"low": [], "mid_low": [], "mid_high": [], "high": []}

            for prod in pre_filtered:
                price = _parse_float_safe((prod.get("price", {}) or {}).get("current", 0))
                rating = _get_effective_rating(prod)
                review_count = _get_effective_review_count(prod)
                quality_score = rating * math.log(review_count + 2)

                # Text search alakası hesapla
                text_relevance = 0
                if text_keywords:
                    full_text = " ".join([
                        prod.get("title", ""),
                        prod.get("brand", ""),
                    ] + (prod.get("categories", [])) + [f"{k} {v}" for k, v in (prod.get("features", {}) or {}).items()]).lower()

                    for keyword in text_keywords:
                        if keyword in full_text:
                            text_relevance += 1

                    # Normalize et (0-1 arası)
                    text_relevance = min(text_relevance / len(text_keywords), 1.0)
                else:
                    text_relevance = 0.5  # Neutral

                # HİBRİT SKOR: Kalite + Text Alakası
                # Text alakası yüksek olanlar öncelikli olsun
                hybrid_selection_score = quality_score * (1 + text_relevance * 2)  # Text alakası 2x ağırlık

                if price <= low_max:
                    segments["low"].append((hybrid_selection_score, prod))
                elif price <= mid_low_max:
                    segments["mid_low"].append((hybrid_selection_score, prod))
                elif price <= mid_high_max:
                    segments["mid_high"].append((hybrid_selection_score, prod))
                else:
                    segments["high"].append((hybrid_selection_score, prod))

            # Orta segment ağırlıklı dağılım (toplamda ~24)
            segment_limits = {"low": 3, "mid_low": 8, "mid_high": 8, "high": 5}
            for segment_name, segment_products in segments.items():
                segment_products.sort(key=lambda x: x[0], reverse=True)
                limit = segment_limits[segment_name]
                selected_from_segment = [prod for score, prod in segment_products[:limit]]
                llm_candidates.extend(selected_from_segment)
                print(f"DEBUG: {segment_name} segmentinden {len(selected_from_segment)} ürün seçildi (hibrit skorla)")
        else:
            # Fiyat bilgisi yoksa hibrit skorla seç
            scored_products = []
            for prod in pre_filtered:
                rating = _get_effective_rating(prod)
                review_count = _get_effective_review_count(prod)
                quality_score = rating * math.log(review_count + 2)

                # Text alakası hesapla
                text_relevance = 0
                if text_keywords:
                    full_text = " ".join([
                        prod.get("title", ""),
                        prod.get("brand", ""),
                    ] + (prod.get("categories", [])) + [f"{k} {v}" for k, v in (prod.get("features", {}) or {}).items()]).lower()

                    for keyword in text_keywords:
                        if keyword in full_text:
                            text_relevance += 1
                    text_relevance = min(text_relevance / len(text_keywords), 1.0)
                else:
                    text_relevance = 0.5

                hybrid_selection_score = quality_score * (1 + text_relevance * 2)
                scored_products.append((hybrid_selection_score, prod))

            scored_products.sort(key=lambda x: x[0], reverse=True)
            llm_candidates = [prod for score, prod in scored_products[:24]]

    print(f"DEBUG: {len(llm_candidates)} ürün LLM scoring'e gönderiliyor (orta segment ağırlıklı - max 24)")

    # 3. AŞAMA: KULLANICI İNTENT ANALİZİ
    user_intent_prompt = f"""
Kullanıcının isteğini analiz et: "{positive_keywords} {negative_keywords}"

Bu istekten kullanıcının önceliğini belirle:
1. "KALİTE" - Premium, kaliteli, dayanıklı ürün istiyor
2. "FİYAT_PERFORMANS" - Uygun fiyata iyi özellik istiyor  
3. "BÜTÇELİ" - En ucuz seçenekleri istiyor
4. "ÖZEL_ÖZELLİK" - Belirli bir özelliğe odaklanmış

Sadece şu formatla cevap ver: "ÖNCELIK: [KALİTE/FİYAT_PERFORMANS/BÜTÇELİ/ÖZEL_ÖZELLİK]"
    """

    try:
        if _model:
            intent_response = _model.generate_content(user_intent_prompt)
            user_priority = intent_response.text.strip().upper()
            if "KALİTE" in user_priority:
                priority = "KALİTE"
            elif "FİYAT_PERFORMANS" in user_priority:
                priority = "FİYAT_PERFORMANS"
            elif "BÜTÇELİ" in user_priority:
                priority = "BÜTÇELİ"
            else:
                priority = "ÖZEL_ÖZELLİK"
        else:
            priority = "FİYAT_PERFORMANS"  # Varsayılan
    except Exception as e:
        print(f"Intent analiz hatası: {e}")
        priority = "FİYAT_PERFORMANS"  # Varsayılan

    print(f"DEBUG: Kullanıcı önceliği: {priority}")

    # 4. AŞAMA: LLM SCORING (ELEME DEĞİL!)
    scored_products = []
    for product in llm_candidates:
        title = product.get('title', '')
        features = product.get('features', {}) or {}
        reviews = product.get('reviews', [])[:2]  # İlk 2 yorum
        qa_data = product.get('qa', [])[:2]  # İlk 2 QA
        price = _parse_float_safe((product.get("price", {}) or {}).get("current", 0))

        # Detaylı context
        context = f"""
ÜRÜN: {title}
FİYAT: {price} TL
ÖZELLİKLER: {json.dumps(features, ensure_ascii=False)}
YORUMLAR: {json.dumps(reviews, ensure_ascii=False)}
SORU-CEVAP: {json.dumps(qa_data, ensure_ascii=False)}
        """

        llm_score = 5.0  # Varsayılan skor

        if _model:
            # LLM ile skorlama
            # İki aşamalı LLM kontrol
            # AŞAMA 1: ÇOK SIKI NEGATİF KONTROL
            if has_negative:
                negative_check_prompt = f"""
KULLANICI İSTEĞİ: "{positive_keywords} {negative_keywords}"
İSTENMEYEN: "{negative_keywords}"

ÜRÜN KONTROLÜ:
{context}

⚠️ MONGODB ZATEN FİLTRELEDİ - SEN SADECE ÇOK GEVŞEKçE KONTROL ET:

MongoDB zaten:
- Doğru kategoriyi seçti (Torbasız Süpürge vs Dik Süpürge)
- Doğru features'ı filtreledi (ANC: "Yok" olanları aldı)

SEN SADECE ÇOK AÇIK UYUMSUZLUK VARSA ELE:
- Başlık tamamen yanlış kategori (süpürge istedi → telefon geldi)
- Açıkça zıt bilgi var

NEREDEYSE HER DURUMDA "UYGUN" YAZ!

Sadece şunu yaz: "ELENMELİ" veya "UYGUN"
                """

                try:
                    negative_response = _model.generate_content(negative_check_prompt)
                    decision = negative_response.text.strip().upper()

                    if "ELENMELİ" in decision:
                        print(f"DEBUG: Negatif özellik eleme: '{title[:35]}...' - İstenmeyen özellik var")
                        continue  # Bu ürünü atla

                except Exception as e:
                    print(f"Negatif kontrol hatası: {e}")
                    # Hata durumunda ürünü koru

            # AŞAMA 2: Detaylı skorlama
            scoring_prompt = f"""
KULLANICI İSTEĞİ: "{positive_keywords} {negative_keywords}"
ÖNCELIK: {priority}

ÜRÜN DEĞERLENDİRMESİ:
        {context}

DETAYLI ANALİZ YAP:

1. ÖZELLİK UYUMU: İstenen özellikler (özellikle "{positive_keywords}") ne kadar mevcut?

2. YORUM ANALİZİ: Yorumlara DİKKAT! 
   - Olumlu: "memnunum, güzel, kaliteli, tavsiye, iyi" → PUANI ARTIR
   - Olumsuz: "kötü, berbat, sorunlu, pişman, gürültülü" → PUANI AZALT  
   - Fiyat yorumu: "fiyatına göre iyi, uygun fiyat" → {priority} için ÖNEMLI

3. {priority} UYUMU:
   - FİYAT_PERFORMANS: Yorumlarda "fiyatına göre değer" olmalı
   - KALİTE: Yorumlarda "sağlam, kaliteli, dayanıklı" olmalı
   - BÜTÇELİ: Düşük fiyat + temel fonksiyon yeterli

4. GERÇEK KULLANICI DENEYİMİ: Yorumlardaki problemler var mı?

PUANLAMA (her 0.1 artışı anlamlı):
- 8.5-10.0: Mükemmel + yorumlar çok olumlu
- 7.1-8.4: İyi + yorumlar genelde olumlu  
- 5.6-7.0: Orta + yorumlar karışık
- 4.1-5.5: Zayıf + yorumlar çoğunlukla olumsuz
- 1.0-4.0: Kötü + yorumlar çok olumsuz

Sadece şu formatla cevap ver: PUAN: [x.x]
            """

            try:
                response = _model.generate_content(scoring_prompt)
                response_text = response.text.strip()

                # PUAN: kısmını ara
                import re

                # "PUAN: x.x" formatını ara
                puan_match = re.search(r'PUAN:\s*(\d+\.?\d*)', response_text, re.IGNORECASE)
                if puan_match:
                    llm_score = min(max(float(puan_match.group(1)), 1.0), 10.0)
                else:
                    # Fallback: herhangi bir sayı ara
                    numbers = re.findall(r'\d+\.?\d*', response_text)
                    if numbers:
                        # Son sayıyı al (PUAN kısmında olması muhtemel)
                        llm_score = min(max(float(numbers[-1]), 1.0), 10.0)
                    else:
                        llm_score = 5.0  # Varsayılan

            except Exception as e:
                print(f"LLM scoring hatası: {e}. Varsayılan skor 5.0.")
                llm_score = 5.0
        else:
            # API yoksa basit scoring
            rating = _get_effective_rating(product)
            llm_score = rating * 2  # 5 yıldız → 10 puan

        # LLM skorunu ürüne ekle
        product_with_score = product.copy()
        product_with_score['_llm_score'] = llm_score
        scored_products.append(product_with_score)

        print(f"DEBUG: LLM Skor: {llm_score:.1f}/10 -> '{title[:25]}...'")

    print(f"DEBUG: LLM scoring tamamlandı. {len(scored_products)} ürün skorlandı")
    return scored_products, priority


def rank_products(products: List[Dict[str, Any]], criteria: Dict[str, Any], user_priority: str = "FİYAT_PERFORMANS", top_n: int = 5) -> List[Dict[str, Any]]:
    """
    LLM skorunu da kullanarak ürünleri sıralar.
    """
    if not products: return []

    # Fiyat aralığı analizi
    prices = [_parse_float_safe((prod.get("price", {}) or {}).get("current", 0)) for prod in products]
    prices = [p for p in prices if p > 0]

    if prices:
        prices_sorted = sorted(prices)
        n = len(prices_sorted)
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = prices_sorted[q1_idx]
        q3 = prices_sorted[q3_idx]
        avg_price = sum(prices) / len(prices)

        print(f"DEBUG: Ranking Fiyat analizi ({user_priority}) - Q1: {q1:.0f}, Q3: {q3:.0f}, Ortalama: {avg_price:.0f}")
    else:
        q1 = q3 = avg_price = 0

    ranked_list = []
    text_to_search = criteria.get("text_search", "").lower().split()
    user_has_price_preference = criteria.get("price_min", 0) > 0 or criteria.get("price_max", 99999) < 99999

    for prod in products:
        # Temel kalite skoru
        rating = _get_effective_rating(prod)
        review_count = _get_effective_review_count(prod)
        quality_score = rating * math.log(review_count + 2)

        # LLM alakalık skoru (1-10 → 0.1-1.0 aralığına normalize et)
        llm_score = prod.get('_llm_score', 5.0)
        llm_relevance = llm_score / 10.0  # 1-10 skorunu 0.1-1.0 aralığına çevir

        # Text search alakası
        text_relevance_score = 0
        if text_to_search:
            full_text = " ".join([
                prod.get("title", ""),
                prod.get("brand", ""),
            ] + (prod.get("categories", [])) + [f"{k} {v}" for k, v in (prod.get("features", {}) or {}).items()]).lower()
            for keyword in text_to_search:
                if keyword in full_text: text_relevance_score += 1

        # Normalleştirilmiş text alakası (0-1 arası)
        text_relevance = min(text_relevance_score / max(len(text_to_search), 1), 1.0) if text_to_search else 0.5

        # Kullanıcı önceliğine göre fiyat-değer skoru
        price = _parse_float_safe((prod.get("price", {}) or {}).get("current", 0))
        price_value_score = 1.0  # Varsayılan

        if price > 0 and not user_has_price_preference and avg_price > 0:
            if user_priority == "KALİTE":
                # Kalite öncelikli: Pahalı ürünler hafif bonus
                if price > q3:
                    price_value_score = 1.2
                elif price > avg_price:
                    price_value_score = 1.1
                elif price < q1:
                    price_value_score = 0.8
                else:
                    price_value_score = 1.0

            elif user_priority == "BÜTÇELİ":
                # Bütçe öncelikli: Ucuz ürünler bonus
                if price < q1:
                    price_value_score = 1.3
                elif price < avg_price:
                    price_value_score = 1.1
                elif price < q3:
                    price_value_score = 0.9
                else:
                    price_value_score = 0.7

            else:  # FİYAT_PERFORMANS ve ÖZEL_ÖZELLİK
                # Orta segment öncelikli
                if q1 <= price <= q3:
                    price_value_score = 1.2
                elif price < q1:
                    price_value_score = 0.9
                else:
                    price_value_score = 0.8

        # YENI HİBRİT SKOR: Kalite × Fiyat-değer × LLM Skoru × Text Alakası
        # LLM skoru en önemli faktör olsun
        hybrid_score = quality_score * price_value_score * (1 + llm_relevance) * (1 + text_relevance * 0.5)

        # Segment bilgisi
        segment = "Orta"
        if price < q1:
            segment = "Düşük"
        elif price > q3:
            segment = "Yüksek"

        ranked_list.append((hybrid_score, prod))
        print(f"DEBUG: Sıralama: {prod.get('title', '')[:30]}... | Fiyat: {price:.0f}TL ({segment}) | Kalite: {quality_score:.1f} | LLM: {llm_score:.1f}/10 | Final: {hybrid_score:.1f}")

    ranked_list.sort(key=lambda x: x[0], reverse=True)
    return [prod for score, prod in ranked_list[:top_n]]


def generate_product_description(product: Dict[str, Any]) -> str:
    title = product.get("title", "")
    rating = product.get("rating", 0)
    features = product.get("features", {}) or {}
    reviews = product.get("reviews", [])
    qa_data = product.get("qa", [])
    
    context = f"Ürün: {title}\nPuan: {rating} / 5\n"
    if features:
        context += "Özellikler:\n"
        for i, (k, v) in enumerate(features.items()):
            if i >= 5: break
            context += f"- {k}: {v}\n"
    if reviews:
        context += "Kullanıcı Yorumları:\n"
        for i, review in enumerate(reviews[:3]):  # İlk 3 yorum
            if i >= 3: break
            context += f"- {review}\n"
    if qa_data:
        context += "Soru-Cevaplar:\n"
        for i, qa in enumerate(qa_data[:2]):  # İlk 2 QA
            if i >= 2: break
            context += f"- {qa}\n"
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
    try:
        resp = _model.generate_content(tpl)
        return (resp.text or "").strip()
    except Exception as exc:
        print(f"Error generating product description: {exc}")
        return product.get('title', '')


def to_card(prod: Dict[str, Any]) -> Dict[str, Any]:
    images = prod.get("images") or []
    return {
        "image": images[0] if images else None,
        "title": prod.get("title"),
        "rating": _get_effective_rating(prod),
        "rating_count": _get_effective_review_count(prod),
        "price": (prod.get("price") or {}).get("current", "N/A"),
        "link": (prod.get("product_url") or prod.get("productUrl")),
        "description": generate_product_description(prod),
    }


# ---------------------------------------------------------------------------
# Routes

@app.route("/analyze-prompt", methods=["POST"])
def analyze_prompt_endpoint():
    data = request.json or {}
    prompt = data.get("prompt")
    if not prompt: return jsonify({"error": "'prompt' alanı gerekli"}), 400
    criteria = analyze_prompt(prompt)
    return jsonify(criteria)


@app.route("/recommendation", methods=["POST"])
def recommendation_endpoint():
    data = request.json or {}
    user_prompt = data.get("prompt")
    if not user_prompt: return jsonify({"error": "'prompt' alanı gerekli"}), 400

    # Adım 1: Kullanıcı isteğini pozitif/negatif olarak analiz et
    criteria = analyze_prompt(user_prompt)
    normalized_criteria = normalize_criteria(criteria)
    print(f"DEBUG: Analiz edilmiş kriterler: {json.dumps(normalized_criteria, ensure_ascii=False, indent=2)}")

    # Adım 2: Katmanlı sorgu ile aday havuzu al
    candidate_products = find_products_by_criteria(normalized_criteria, limit=300)
    print(f"DEBUG: Aday ürün sayısı: {len(candidate_products)}")

    # Adım 3: İstenmeyen özellikleri içeren ürünleri LLM ile ele
    filtered_products, user_priority = comprehensive_llm_filter(
        candidate_products,
        normalized_criteria.get("text_search", ""),
        normalized_criteria.get("negative_text_search", "")
    )

    # Adım 4: Kalan ürünleri kalite ve alaka düzeyine göre sırala
    ranked_products = rank_products(filtered_products, normalized_criteria, user_priority=user_priority, top_n=5)

    # Yedek stratejiler - hiç ürün yoksa
    if not ranked_products:
        print("DEBUG: Hiç ürün bulunamadı, yedek stratejiler devreye giriyor...")

        # Yedek 1: LLM filtreleme olmadan direkt sıralama
        if candidate_products:
            print("DEBUG: LLM filtresiz sıralama deneniyor...")
            ranked_products = rank_products(candidate_products[:50], normalized_criteria, user_priority=user_priority, top_n=5)

        # Yedek 2: Daha gevşek kriterlerle yeniden arama
        if not ranked_products:
            print("DEBUG: Gevşek kriterlerle yeniden arama...")
            loose_criteria = {
                "category_search_string": "",  # Kategori sınırlaması kaldır
                "text_search": normalized_criteria.get("text_search", ""),
                "negative_text_search": "",  # Negatif filtreleri kaldır
                "price_min": 0,
                "price_max": 99999,
                "min_rating": 0.0
            }
            loose_candidates = find_products_by_criteria(loose_criteria, limit=100)
            if loose_candidates:
                ranked_products = rank_products(loose_candidates, normalized_criteria, user_priority=user_priority, top_n=5)

    # Sonuçları kart formatına çevir
    cards = [to_card(p) for p in ranked_products]

    # Uygun mesaj oluştur
    if cards:
        recommendation_text = f"İsteğiniz doğrultusunda '{user_prompt}' için en uygun {len(cards)} ürün bulunmuştur."
    else:
        recommendation_text = "Üzgünüm, belirttiğiniz kriterlere uygun ürün bulunamadı. Lütfen kriterlerinizi gözden geçirerek tekrar deneyin."

    print(f"DEBUG: Final sonuç - {len(cards)} ürün döndürülüyor")

    return jsonify({
        "criteria": normalized_criteria,
        "cards": cards,
        "recommendation": recommendation_text,
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, threaded=True)
