"""
Flask application for the AI-powered product recommender service.

This module sets up the HTTP endpoints for analysing user prompts
(`/analyze-prompt`) and producing product recommendations
(`/recommendation`). It orchestrates the interactions between the
prompt analyser, query builder, LLM-based filtering and ranking
modules. A price-range expansion loop has been added so that narrowly
specified price queries are gradually widened until at least five
products are found.
"""

import json
from typing import Any, Dict, List

from flask import Flask, request, jsonify
from flask_cors import CORS

import os
from services import prompt_analyzer
from services.utils import normalize_criteria
from services.search import find_products_by_criteria, category_exists
from filters.llm_filter import comprehensive_llm_filter
from services.ranker import rank_products
from formatting.description import to_card



app = Flask(__name__)
CORS(app)


@app.route("/analyze-prompt", methods=["POST"])
def analyze_prompt_endpoint():
    data = request.json or {}
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "'prompt' alanı gerekli"}), 400
    criteria = prompt_analyzer.analyze_prompt(prompt)
    return jsonify(criteria)


@app.route("/recommendation", methods=["POST"])
def recommendation_endpoint():
    data = request.json or {}
    user_prompt: str = data.get("prompt")
    if not user_prompt:
        return jsonify({"error": "'prompt' alanı gerekli"}), 400

    # 1) Analyse + normalize
    criteria = prompt_analyzer.analyze_prompt(user_prompt)
    normalized_criteria = normalize_criteria(criteria)
    print(
        f"DEBUG: Analiz edilmiş kriterler: "
        f"{json.dumps(normalized_criteria, ensure_ascii=False, indent=2)}"
    )

    # 1a) Category must exist, otherwise we stop early
    target_category = (normalized_criteria.get("category_search_string") or "").strip()
    if not target_category:
        print("DEBUG: Kategori tespit edilemedi → kategorisiz arama yapılmayacak, boş dönülüyor.")
        return jsonify(
            {
                "criteria": normalized_criteria,
                "cards": [],
                "recommendation": f"Hata",
            }
        )

    if not category_exists(target_category):
        print(f"DEBUG: '{target_category}' kategorisi DB'de yok → erken çıkış (boş liste).")
        return jsonify(
            {
                "criteria": normalized_criteria,
                "cards": [],
                "recommendation": f"Hata",
            }
        )

    # 2) Category-locked search
    candidate_products = find_products_by_criteria(normalized_criteria, limit=300)
    print(f"DEBUG: Aday ürün sayısı: {len(candidate_products)}")

    # 3) Heuristic filtering/scoring (LLM only used later for descriptions)
    filtered_products, user_priority = comprehensive_llm_filter(
        candidate_products,
        normalized_criteria.get("text_search", ""),
        normalized_criteria.get("negative_text_search", ""),
    )

    # 4) Rank top-5
    ranked_products = rank_products(
        filtered_products, normalized_criteria, user_priority=user_priority, top_n=5
    )

    # 5) Progressive price widening (still category-locked)
    if len(ranked_products) < 5:
        pmin = normalized_criteria.get("price_min", 0)
        pmax = normalized_criteria.get("price_max", 99999)
        if (pmin > 0 or pmax < 99999):
            target = (pmin + pmax) // 2 if pmax >= pmin else pmin
            delta = max(100, int(max(1, target) * 0.1))
            new_min, new_max = pmin, pmax
            expansions = 0
            while len(ranked_products) < 5 and expansions < 3:
                new_min = max(0, new_min - delta)
                new_max = new_max + delta
                expanded = normalized_criteria.copy()
                expanded["price_min"] = new_min
                expanded["price_max"] = new_max
                print(
                    f"DEBUG: Fiyat aralığı genişletiliyor → {new_min}-{new_max} (deneme {expansions+1})"
                )
                candidates = find_products_by_criteria(expanded, limit=300)
                if candidates:
                    exp_filtered, exp_priority = comprehensive_llm_filter(
                        candidates,
                        expanded.get("text_search", ""),
                        expanded.get("negative_text_search", ""),
                    )
                    exp_ranked = rank_products(
                        exp_filtered, expanded, user_priority=exp_priority, top_n=5
                    )
                    if exp_ranked:
                        ranked_products = exp_ranked
                expansions += 1
                delta = max(100, int(delta * 1.5))

    # 6) Cards (LLM descriptions only for final results)
    cards: List[Dict[str, Any]] = [to_card(p) for p in ranked_products]

    if cards:
        rec_text = (
            f"İsteğiniz doğrultusunda '{user_prompt}' için en uygun {len(cards)} "
            f"{target_category.lower()} bulunmuştur."
        )
    else:
        rec_text = f"'{user_prompt}' için '{target_category}' kategorisinde uygun ürün bulunamadı."

    print(f"DEBUG: Final sonuç - {len(cards)} ürün döndürülüyor")
    return jsonify({"criteria": normalized_criteria, "cards": cards, "recommendation": rec_text})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, threaded=True)