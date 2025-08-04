"""
Flask-based backend service for product recommendation and product
summarization powered by Gemini. Single-service architecture.

Endpoints:
  POST /analyze-prompt
  POST /recommendation

To run:
  export GEMINI_API_KEY=<your_google_generative_ai_key>
  export MONGO_URI=<your_mongo_uri>           # optional
  export MONGO_DB_NAME=scrapingdb             # optional
  export MONGO_COLLECTION_NAME=products       # optional
  export USE_HTTP_LOOPBACK=1                  # optional; 1 => /recommendation calls /analyze-prompt via HTTP
  python3 app.py
"""
import os
from dotenv import load_dotenv
load_dotenv()
import json
from typing import Any, Dict, List

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import google.generativeai as genai
import requests  # NEW

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Configuration
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "scrapingdb")
MONGO_COLLECTION_NAME = os.environ.get("MONGO_COLLECTION_NAME", "products")

# If set to "1", /recommendation calls /analyze-prompt via HTTP loopback.
USE_HTTP_LOOPBACK = os.environ.get("USE_HTTP_LOOPBACK", "0") == "1"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]
products_collection = db[MONGO_COLLECTION_NAME]

genai.configure(api_key=GEMINI_API_KEY)
generation_config = {"temperature": 0.4, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=generation_config)

# ---------------------------------------------------------------------------
# Helpers

def analyze_prompt(prompt: str) -> Dict[str, Any]:
    """Use Gemini to extract structured search criteria."""
    tpl = f"""
    Analyze the following user request for a product recommendation and extract the key criteria as a JSON object.
    The user request is in Turkish.
    The JSON object should have these keys:
    - "category": A single, most relevant category string (e.g., "kulaklık", "vantilatör").
    - "text_search": A string of keywords to search for in product titles, features, and reviews. Include synonyms.
    - "price_min": A number for the minimum price. Default to 0 if not specified.
    - "price_max": A number for the maximum price. Default to a high number like 99999 if not specified.
    - "min_rating": A number for the minimum acceptable rating. Default to 4.0.

    User Request: "{prompt}"
    JSON Output:
    """
    try:
        resp = _model.generate_content(tpl)
        cleaned = resp.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned)
    except Exception as exc:
        print(f"Error analyzing prompt: {exc}")
        return {"category": "", "text_search": prompt, "price_min": 0, "price_max": 99999, "min_rating": 0}

def find_products_by_criteria(criteria: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Query MongoDB with basic filters (regex-based matching for simplicity)."""
    q: Dict[str, Any] = {}
    text = criteria.get("text_search")
    if text:
        q["$or"] = [
            {"title": {"$regex": text, "$options": "i"}},
            {"categories": {"$regex": text, "$options": "i"}},
            {"brand": {"$regex": text, "$options": "i"}},
        ]
    price_min = criteria.get("price_min", 0)
    price_max = criteria.get("price_max", 99999)
    q["price.current"] = {"$gte": price_min, "$lte": price_max}
    min_rating = criteria.get("min_rating", 0)
    q["rating"] = {"$gte": min_rating}
    category = criteria.get("category")
    if category:
        q.setdefault("categories", {})
        q["categories"]["$regex"] = category
        q["categories"]["$options"] = "i"

    cursor = products_collection.find(q).limit(limit)
    docs: List[Dict[str, Any]] = []
    for d in cursor:
        d["_id"] = str(d.get("_id"))
        docs.append(d)
    return docs

def generate_product_description(product: Dict[str, Any]) -> str:
    """Short persuasive description in Turkish."""
    title = product.get("title", "")
    price = product.get("price", {}).get("current", "")
    rating = product.get("rating", 0)
    reviews = product.get("reviews", []) or []
    qa_list = product.get("qa", []) or []
    features = product.get("features", {}) or {}

    context = f"Ürün: {title}\nFiyat: {price} TL\nPuan: {rating} / 5\n"
    if features:
        context += "Öne çıkan özellikler:\n"
        for i, (k, v) in enumerate(features.items()):
            if i >= 5: break
            context += f"- {k}: {v}\n"
    if reviews:
        context += "İnceleme Özeti:\n"
        for r in reviews[:2]:
            context += f"- {r}\n"
    if qa_list:
        qa = qa_list[0]
        context += "Sık Sorulan Soru:\n"
        context += f"- Soru: {qa.get('question')}\n  Cevap: {qa.get('answer')}\n"

    tpl = f"""
    Sen, bir Türk e-ticaret sitesinde çalışan, kullanıcı odaklı bir ürün danışmanısın.
    Amacın satış yapmak değil; kullanıcının ihtiyacına, bütçesine ve önceliklerine en uygun seçimi kısa ve net biçimde önermektir.
    Abartılı/pazarlama dili kullanma; yalnızca verilen veriye (fiyat, puan, yorum temaları, özellikler, Soru-Cevap) dayan. Tüm yanıtların Türkçe olmalı.

    **Veritabanından Gelen Ürün Bilgileri:**
    {context}

    **Kurallar:**
    - Sabit bir açılış kullanma; ilk cümle veriye dayalı başlasın (örn. “4,7/5 puan, uyku ve nabız takibi, iOS uyumluluğu…” gibi).
    - Ardından ürün adını netçe belirt ve en fazla 3 somut gerekçe ile kısaca temellendir (fiyat aralığı uyumu, puan/yorum sayısı, öne çıkan 1–2 özellik, varsa ithalatçı/üretici garantisi gibi **nötr** ifadeler).
    - Yorumlar ve Soru-Cevap içeriğini **doğrudan alıntılamadan**, özellik odaklı biçimde sentezle (örn. “yorum analizinde pil süresinin beğenildiği”, “SSS’de suya dayanıklılığın belirtildiği”).
    - Uygunsa kısa bir kısıt/uyarı ekle (ör. suya dayanıklılık yok, batarya küçük). Veri yoksa o kısımdan bahsetme.
    - **Alternatif ürün verme.**
    - Toplam **4–5 cümle**, tek paragraf; başlık, madde işareti, emoji ve ünlem kullanma.
    - Bilgisayar & Tablet tek bir kategori olduğu için kullanıcı isteği bilgisayar mı tablet mi doğru analiz edip ürün başlığını kontrol ederek doğru ürün önerdiğine emin ol.

    **Yasak Kalıplar (kullanma):**
    “kesinlikle”, “tam size göre”, “almanızı öneririm”, “hemen sipariş verin/kaçırmayın”, “güvencemiz altında”, “tanıştırmama izin verin”.
    Ürün linkini asla açıklamada kullanma

    **Çıktı:**
    Düz metin, tek paragrafta 4–5 cümle; veriye dayalı cümleyle başla, en sonda “Bağlantı: <product_url>”.
    """
    try:
        resp = _model.generate_content(tpl)
        return (resp.text or "").strip()
    except Exception as exc:
        print(f"Error generating product description: {exc}")
        return ""

def generate_final_recommendation(user_prompt: str, products: List[Dict[str, Any]]) -> str:
    """Confident recommendation + one alternative, include each link once."""
    ctx = []
    for i, p in enumerate(products[:5]):
        ctx.append(f"--- Ürün {i+1} ---")
        ctx.append(f"Başlık: {p.get('title','N/A')}")
        ctx.append(f"Marka: {p.get('brand','N/A')}")
        ctx.append(f"Fiyat: {p.get('price',{}).get('current',0)} TL")
        ctx.append(f"Puan: {p.get('rating',0)} / 5")
        ctx.append(f"Link: {p.get('product_url') or p.get('productUrl') or 'N/A'}")
        feats = (p.get("features") or {})
        if feats:
            ctx.append("Özellikler:")
            for j, (k, v) in enumerate(feats.items()):
                if j >= 3: break
                ctx.append(f"- {k}: {v}")
        revs = (p.get("reviews") or [])
        if revs:
            ctx.append("Seçilen Yorumlar:")
            for r in revs[:2]:
                ctx.append(f"- {r}")
        qa = (p.get("qa") or [])
        if qa:
            ctx.append("Soru & Cevap:")
            ctx.append(f"- Soru: {qa[0].get('question')}")
            ctx.append(f"  Cevap: {qa[0].get('answer')}")
        ctx.append("")
    ctx_str = "\n".join(ctx)

    tpl = f"""
    Sen, bir Türk e-ticaret sitesinde çalışan, kullanıcı odaklı bir ürün danışmanısın.
    Amacın satış yapmak değil; kullanıcının ihtiyacına, bütçesine ve önceliklerine en uygun seçimi kısa ve net biçimde önermektir.
    Abartılı/pazarlama dili kullanma; yalnızca verilen veriye (fiyat, puan, yorum temaları, özellikler, Soru-Cevap) dayan. Genellemeden kaçın; tüm yanıtların Türkçe olmalı.

    **Müşterinin İsteği:**
    "{user_prompt}"

    **Veritabanı Bağlamı:**
    {ctx_str}

    **Kurallar:**
    - İlk cümlede doğrudan öneri yap: “Önerim: <Ürün adı>.” veya “Kriterlere göre <Ürün adı> uygun görünüyor.” gibi sade ve kararlı bir giriş kullan.
    - En fazla 3 somut gerekçe ver (ör. fiyat aralığı uyumu, puan/yorum sayısı, öne çıkan 1–2 özellik, varsa garanti bilgisi). Garanti varsa “ithalatçı/üretici garantisi” gibi **nötr** ifade kullan; “güvencemiz altında” deme.
    - Yorum ve Soru-Cevap bilgisini **doğrudan alıntılamadan** özetle; “yorum analizine göre pil süresi beğeniliyor”, “SSS’de iOS uyumluluğu belirtilmiş” gibi **özellik odaklı** cümleler kur. “çok beğendik/şiddetle tavsiye edilir” gibi genel övgülere dayanma.
    - Uygunsa kısa bir kısıt/uyarı ekle (örn. suya dayanıklılık yok, batarya küçük). Veri yoksa bu kısımdan **bahsetme**.
    - **Alternatif ürün verme.**
    - Son cümlede ürün bağlantısını **yalnızca bir kez** ekle.
    - Toplam **4–5 cümle**, tek paragraf yaz; başlık, madde işareti, emoji ve **ünlem** kullanma. “almanızı öneririm”, “hemen sipariş verin/kaçırmayın”, “kesinlikle” gibi CTA/iddialı kalıpları **kullanma**.

    **Çıktı:**
    Düz metin, tek paragrafta 4–5 cümle; en sonda “Bağlantı: <product_url>”.
    """
    try:
        resp = _model.generate_content(tpl)
        return (resp.text or "").strip()
    except Exception as exc:
        print(f"Error generating final recommendation: {exc}")
        return ""

def to_card(prod: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten product to frontend-ready 'card'."""
    images = prod.get("images") or []
    reviews = prod.get("reviews") or []

    # Counts
    review_count = len(reviews) if isinstance(reviews, list) else 0
    # Support both snake_case and camelCase just in case
    rating_count_raw = prod.get("rating_count", prod.get("rating_count", 0))

    try:
        rating_count_val = int(rating_count_raw) if rating_count_raw is not None else 0
    except (TypeError, ValueError):
        rating_count_val = 0

    # Fallback: if database rating_count is 0 or missing, use review_count
    effective_count = rating_count_val if rating_count_val > 0 else review_count

    return {
        "image": images[0] if images else None,
        "title": prod.get("title"),
        "rating": prod.get("rating", 0),
        "rating_count": effective_count,
        "price": (prod.get("price") or {}).get("current"),
        "link": (prod.get("product_url") or prod.get("productUrl")),
        "description": generate_product_description(prod),
    }

# ---------------------------------------------------------------------------
# Routes

@app.route("/analyze-prompt", methods=["POST"])
def analyze_prompt_endpoint():
    data = request.json or {}
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "'prompt' alanı gerekli"}), 400
    criteria = analyze_prompt(prompt)
    return jsonify(criteria)

@app.route("/recommendation", methods=["POST"])
def recommendation_endpoint():
    data = request.json or {}
    user_prompt = data.get("prompt")
    if not user_prompt:
        return jsonify({"error": "'prompt' alanı gerekli"}), 400

    # 1) /analyze-prompt çağrısı (HTTP veya fonksiyon içi)
    if USE_HTTP_LOOPBACK:
        try:
            resp = requests.post(
                "http://127.0.0.1:5001/analyze-prompt",
                json={"prompt": user_prompt},
                timeout=10,
            )
            resp.raise_for_status()
            criteria = resp.json()
        except Exception as exc:
            print(f"/analyze-prompt HTTP çağrısı hatası: {exc}")
            criteria = analyze_prompt(user_prompt)
    else:
        criteria = analyze_prompt(user_prompt)

    # 2) MongoDB’den aday ürünler
    products = find_products_by_criteria(criteria, limit=5)

    # Fallback: if no products, relax criteria (rating/text) and retry
    if not products:
        relaxed = dict(criteria)
        relaxed["min_rating"] = 0
        relaxed["text_search"] = ""  # drop keyword filter to broaden search
        products = find_products_by_criteria(relaxed, limit=5)

    # 3) Frontend kartları (flatten) hazırlanır
    cards = [to_card(p) for p in products]

    # 4) Satış danışmanı üslubunda nihai öneri metni
    recommendation_text = generate_final_recommendation(user_prompt, products)

    return jsonify({
        "criteria": criteria,
        "cards": cards,
        "recommendation": recommendation_text,
    })

# Health
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, threaded=True)