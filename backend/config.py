"""
Configuration and shared resources for the product recommendation service.

This module centralises the setup of environment variables, database
connections and large language model (LLM) configuration. It mirrors
the behaviour of the original monolithic script without altering any
functional logic. If ``GEMINI_API_KEY`` is provided, the Gemini API
will be configured. Otherwise a fallback mode is enabled which will
trigger simple category mapping in other modules.

Note: dotenv is optional. If the ``python-dotenv`` package is not
available the service will fall back to reading environment variables
directly from the operating system, exactly as in the original code.
"""

import os
from typing import Optional

try:
    # Attempt to load environment variables from a .env file.
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    # dotenv is optional; fall back to OS environment variables.
    print(
        "⚠️ dotenv bulunamadı - environment variable'lar sistem ayarlarından alınacak"
    )

import google.generativeai as genai  # type: ignore
from pymongo import MongoClient
import certifi


__all__ = [
    "MONGO_URI",
    "MONGO_DB_NAME",
    "MONGO_COLLECTION_NAME",
    "GEMINI_API_KEY",
    "mongo_client",
    "db",
    "products_collection",
    "_model",
]

# ---------------------------------------------------------------------------
# Configuration

# MongoDB connection settings. Default values mirror those used in the
# original monolithic recommender script.
MONGO_URI: str = os.environ["MONGO_URI"]
MONGO_DB_NAME: str = os.environ.get("MONGO_DB_NAME", "scrapingdb")
MONGO_COLLECTION_NAME: str = os.environ.get("MONGO_COLLECTION_NAME", "products")

# Gemini API configuration.
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# Initialise the MongoDB client and collection handles. These are shared
# across the application so that multiple requests reuse the same
# underlying connection pool.
mongo_client: MongoClient = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo_client[MONGO_DB_NAME]
products_collection = db[MONGO_COLLECTION_NAME]

# Initialise the Gemini model if an API key is provided. Otherwise
# fallback to None which signals to other modules that they should use
# simplified logic instead of LLM-based analysis.
if GEMINI_API_KEY:
    # Configure the generative AI client using the provided API key.
    genai.configure(api_key=GEMINI_API_KEY)
    generation_config = {
        "temperature": 0.2,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048,
    }
    _model: Optional[genai.GenerativeModel] = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite", generation_config=generation_config
    )
else:
    _model = None
    print(
        "⚠️ GEMINI_API_KEY bulunamadı - basit kategori mapping sistemi aktif"
    )