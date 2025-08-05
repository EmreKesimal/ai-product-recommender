# ai-product-recommender/backend/llm_filter.py
"""
DEPRECATION NOTICE

This module is kept for backward compatibility. The original implementation
performed LLM-based filtering and scoring at this stage, but repeated model
calls significantly slowed the pipeline under real traffic. To keep response
times predictable, this stage now uses a non-LLM, heuristic approach implemented
in `heuristic_filter.py` (database-driven filtering + lightweight scoring).
LLM usage is preserved where it adds the most value (e.g., final text
descriptions), but not for per-candidate filtering/scoring.

For API stability, we continue to export the same symbol:
`comprehensive_llm_filter` now re-exports
`heuristic_filter.heuristic_filter_and_score`.

If you ever reintroduce model-based filtering here, you can replace the shim
below with a direct implementation while keeping the public function name.
"""

# Import as a thin shim so existing imports keep working.
# Supports both package and script execution contexts.
try:
    from filters.heuristic_filter import heuristic_filter_and_score as comprehensive_llm_filter
except ImportError:
    from filters.heuristic_filter import heuristic_filter_and_score as comprehensive_llm_filter

__all__ = ["comprehensive_llm_filter"]