# TBA — AI/ML Documentation

> **Honesty statement.** No neural network was trained for this project and no model was fine-tuned.
> The local features use *pretrained rules/lexicons* (sentiment) and *classic information-retrieval
> maths* (TF-IDF + cosine similarity). The only "generative AI" is an **optional** external API for
> Quick Read summaries, and its output is verified against the article before it is shown.

## 1. Architecture

```
Google News RSS ──► parse_feed() ──► enrich_items()  ──► /api/news  (cached per feed)
                                      │  topic      services/categorizer.py
                                      │  sentiment  services/sentiment.py
                                      └─ duplicates services/similarity.py
Card click ──► /api/article/<id> ──► extract article text ──► services/ai_summarizer.py  (optional, validated)
                                                          └─► extractive summary (local fallback, existing code)
Quick Read modal ──► /api/recommendations/<id> ──► services/similarity.py
Images: existing pipeline (RSS media fields → og:image/twitter:image → SSRF-safe proxy → placeholder)
```

`services/` contains no Flask code, so each module can be unit-tested and explained alone. The Flask
routes only call these modules. ML failure never hides the news: if enrichment raises, the feed is
returned without the ML fields and the UI renders exactly as before.

## 2. Features and purpose

| Feature | What the reader sees | Needs paid API? |
|---|---|---|
| AI Smart Summary | Detailed overview in Quick Read, labelled **AI SUMMARY** or **ARTICLE SUMMARY** | Optional |
| Sentiment | Positive / Neutral / Negative pill on each card; "Headline tone" and "Article tone" in Quick Read | No |
| Categorisation | Detected topic replaces the generic tag; **Topic** filter | No |
| Duplicate grouping | `+N sources` on the card, "Also covered by" in Quick Read, **Duplicates** selector | No |
| Recommendations | "Related stories" in Quick Read | No |
| Images | Real images where publishers provide them; clean placeholder otherwise (pipeline pre-existing, re-verified) | No |

## 3. Models and algorithms

**Sentiment (`services/sentiment.py`).** Default: **VADER** (Hutto & Gilbert, 2014): a *pretrained
lexicon + rule* analyser inside the `vaderSentiment` pip package (no download, no GPU). We add a small
inspectable `NEWS_LEXICON` (≈70 words such as *layoffs, plunge, surge, falls*). The compound score
(−1…+1) is thresholded: headlines ±0.25, article text (mean of sentence scores) ±0.10; anything
between is Neutral. The number is shown as **"lexicon polarity"**, never as confidence.
Optional backend (`TBA_SENTIMENT_BACKEND=transformers`): a pretrained Hugging Face classifier
(default `cardiffnlp/twitter-roberta-base-sentiment-latest`), needs `pip install transformers torch` and
downloads ≈500 MB on first use. Only this backend reports `confidence` (its softmax probability, which is
a raw model output and not guaranteed to be calibrated). If it cannot load, VADER is used and the `method`
field says so. Financial wording adds the note *"not investment advice"*.

**Categorisation (`services/categorizer.py`).** A similarity baseline. Each of 9 categories has a
hand-written vocabulary; TF-IDF is fitted on those 9 vocabularies; the headline (+ real description) is
compared with each by cosine similarity. A category is returned only if the best score ≥ 0.05 **and** it
leads the runner-up by ≥ 0.012; otherwise **General**. The score is a *similarity*, not a probability.
The UI shows the matched words, so the decision is explainable.

**Duplicate grouping (`services/similarity.py`).** TF-IDF over stemmed words and word pairs, cosine
similarity, threshold **0.50** (`TBA_DUPLICATE_THRESHOLD`). Articles are processed in feed order; one joins
a group if its best match inside the group ≥ threshold, it still resembles the group's lead (≥ 60 % of the
threshold) and shares ≥ 2 informative words. Nothing is deleted; publisher, link and time stay on every item.

**Recommendations.** `score = cosine(open article, candidate) + 0.08 if same topic + 0.35 × cosine(candidate,
saved-story centroid)`. Excluded: the open article, copies of the same story, and all but the best article
per duplicate group. Below score 0.08 nothing is shown as "related"; if fewer than 2 qualify, recent
different stories are added and the section is titled **"More from your feed"**. Saved stories *re-rank*
candidates that are already related; they cannot pull in unrelated news.

**Summary (`services/ai_summarizer.py`).** Any OpenAI-compatible `/chat/completions` endpoint. The model gets
only the headline and extracted text, with instructions to use nothing else. Its JSON answer is then checked:
every **number, quotation and capitalised name** must occur in the article text (numbers may be written as
words in the source), otherwise the answer is discarded and the local extractive summary is shown with an
explanation. Timeouts, 429, 5xx, bad JSON, and bad credentials are handled; 429/401 start a cool-down.
Plain-HTTP endpoints are refused except on localhost. The key is read from the environment only, sent only in
the `Authorization` header, never logged, never returned to the browser.

## 4. Training data and training performed

**None.** VADER's lexicon was built by its authors (not by us). The category vocabularies and the news lexicon
extension were written by hand. TF-IDF vectors are *fitted* to the current headlines at run time (that is
vocabulary/IDF statistics, not model training). If you later want a trained classifier, use a labelled corpus
(e.g. the public BBC News dataset) with TF-IDF + logistic regression.

## 5. Limitations and evaluation (measured)

Run `python tests/eval_categorizer.py` and `python tests/eval_duplicates.py`. **All evaluation data is
synthetic: headlines written by the project author, not a public benchmark.** The author also wrote the
vocabularies, so real-world accuracy is likely lower.

*Categoriser* — DEV (40, used for threshold choice): **97.5 %**. TEST (49, not tuned on): **95.9 %**. Misses:
*"Prime ministers meet at G20 to discuss global debt"* → Politics (World expected; genuinely ambiguous) and
*"Researchers develop battery that charges in minutes"* → General (missing vocabulary). Includes
uninformative headlines that must stay General.

*Duplicates* — 16 same-story pairs, 24 hard different-story pairs, TF-IDF fitted on all 64 headlines:

| Threshold | Precision | Recall | F1 | False + | False − |
|---|---|---|---|---|---|
| 0.40 | 0.83 | 0.94 | 0.88 | 3 | 1 |
| 0.45 | 0.82 | 0.88 | 0.85 | 3 | 2 |
| **0.50 (chosen)** | **0.93** | **0.88** | **0.90** | **1** | **2** |
| 0.55 | 0.92 | 0.75 | 0.83 | 1 | 4 |
| 0.60 | 0.89 | 0.50 | 0.64 | 1 | 8 |

Why 0.50: wrongly merging two *different* stories hides information, which is worse than leaving a near-duplicate
visible, so precision is favoured. Known errors: **false negative** *"RBI keeps repo rate…"* vs *"Reserve Bank holds
repo rate…"* (cosine 0.28, TF-IDF has no idea RBI = Reserve Bank); **false positive** *"Floods displace thousands in
Assam"* vs *"…in Bangladesh"* (cosine 0.66, nearly identical wording, different event). Sentence embeddings would
fix the first, not necessarily the second.

*Sentiment* — VADER is English-only (non-English text returns "unavailable") and reads wording, not meaning:
*"Opposition walkout"* reads negative; *"scientists celebrate cancer breakthrough"* is damped by the word
"cancer"; sarcasm and neutral-sounding bad news are missed. Not evaluated on a labelled news corpus.
*Summaries* — the AI path could not be tested against a real provider here (see §8).
*Google News* — many RSS descriptions only repeat the headline, so topic/duplicate decisions rest on the headline alone.

## 6. Installation and run

Windows, VS Code terminal (PowerShell):
```powershell
cd TBA
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt       # scikit-learn, numpy, vaderSentiment are the new ones (no model download)
python app.py                         # http://127.0.0.1:5000
```
Offline demo with fictional stories (no internet needed): `python tests/demo_offline.py` → http://127.0.0.1:5055
Optional transformer sentiment: `pip install transformers torch` and set `TBA_SENTIMENT_BACKEND=transformers`.

## 7. API configuration (optional)

PowerShell: `$env:TBA_AI_API_KEY="your-key"; $env:TBA_AI_MODEL="gpt-4o-mini"; python app.py`
Or copy `.env.example` to `.env` and export it. Variables: `TBA_AI_API_KEY`, `TBA_AI_BASE_URL`,
`TBA_AI_MODEL`, `TBA_AI_TIMEOUT`, `TBA_AI_MAX_INPUT_CHARS`, `TBA_AI_STRICT_GROUNDING`,
`TBA_SENTIMENT_BACKEND`, `TBA_SENTIMENT_MODEL`, `TBA_DUPLICATE_THRESHOLD`, `TBA_RECOMMENDATIONS`.
`GET /api/health` reports only whether AI is configured (boolean). Never commit `.env`.

## 8. Testing results

`python -m unittest discover -s tests` → **135 tests pass** (73 original + 62 new, including real-socket tests of the AI client against a local stand-in server). `node tests/frontend_smoke.js`
→ **23 pass** (11 original + 12 new). Tests never contact a real provider (they blank the key). Five deliberate
code mutations (grounding check off, current article not excluded, threshold ignored, lexicon score shown as
confidence, General fallback removed) were each caught by the suite. UI was also checked in headless Chromium
(desktop, dark mode, mobile 390 px: no horizontal overflow, no JavaScript errors), using the real `feedparser` package.
**Not tested:** a real AI provider; real transformer weights; live Google News / publisher pages (no internet in
the build sandbox); accuracy on real feeds; Safari/Firefox; a Windows machine. See `docs/TESTING.md`.

## 9. Viva demonstration script

1. **Sentiment** — point at the pill on cards; open Quick Read → *Headline tone: Negative · lexicon polarity −0.69*. Say: "lexicon score, not confidence." Show a Business story's *not investment advice* note.
2. **Categorisation** — change **Topic** to *Technology*; open a card → *matched: ai, chip*. Show a vague headline landing in *General*.
3. **Duplicates** — find a card with `+1 source`; open it → *Also covered by* shows the other publisher's link. Switch **Duplicates** to *Show all*. Run `python tests/eval_duplicates.py` and explain the threshold table and the two error examples.
4. **Recommendations** — scroll to *Related stories*; explain the formula; save a story and reopen another to show the "Matches your saved stories" reason; click a related story.
5. **Summary** — without a key: *ARTICLE SUMMARY* (extractive, every sentence from the article). With a key: *AI SUMMARY*; then set a wrong key to show the honest fallback note and the retry button.
6. **Images** — cards with RSS/og images vs the placeholder; mention SSRF-safe proxy and no retry loops.
7. Run the tests live: `python -m unittest discover -s tests`.

## 10. Future improvements

Sentence-embedding duplicate detection and recommendations (e.g. `all-MiniLM-L6-v2`); a trained TF-IDF + logistic
regression categoriser on a labelled corpus; a finance-specific sentiment model (FinBERT) and multilingual support;
persistent summary cache (SQLite); background pre-computation; per-publisher feedback ("wrong topic") to build a labelled set.
