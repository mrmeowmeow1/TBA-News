"""TBA AI/ML service layer.

Each module is independent of Flask so it can be unit-tested and explained on its own:

* ``config``        - environment-driven settings (no secrets in code)
* ``text_utils``    - cleaning, tokenising and light stemming shared by the ML modules
* ``sentiment``     - Positive / Negative / Neutral classification
* ``categorizer``   - topic classification (TF-IDF similarity to category vocabularies)
* ``similarity``    - TF-IDF + cosine similarity: duplicate grouping and recommendations
* ``ai_summarizer`` - optional, validated LLM summary (OpenAI-compatible API)
* ``enrichment``    - applies the local ML features to a list of feed items
"""
