"""Automatic topic categorisation (a similarity baseline - NOT a trained classifier).

How it works
------------
1. Each category has a hand-written vocabulary (``VOCABULARY``): words and short phrases that
   typically appear in that kind of story.  Each vocabulary is one "document".
2. A TF-IDF vectoriser is fitted on those ten documents, so a word that is specific to one category
   (``wicket``) counts for more than a word shared by several (``government``).
3. The article text (headline repeated for emphasis, plus a real description or the first part of
   the article when available) is vectorised with the same vocabulary and compared to each
   category with **cosine similarity**.
4. The best category wins only if it is similar enough *and* clearly ahead of the runner-up.
   Otherwise the result is ``General`` (no claim is made).

What it is not
--------------
No model was trained and no labelled dataset was used to fit weights; the "knowledge" is the
vocabulary list.  The returned ``score`` is a cosine similarity (0-1), not a probability, and
``confidence`` is always ``None``.  Accuracy was only measured on a small hand-written sample
(``tests/eval_categorizer.py``), so treat it as a demonstration baseline.
Possible upgrade: a zero-shot transformer or a TF-IDF + logistic regression trained on a labelled
news corpus (e.g. the public BBC News or 20 Newsgroups-style datasets).
"""
from __future__ import annotations

import logging
import re
import threading

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .text_utils import STOP, analyzer, clean_text, stem, tokens

log = logging.getLogger("tba.categorizer")

CATEGORIES = ["Politics", "Business", "Technology", "Sports", "Entertainment",
              "World", "Science", "Health", "Education"]
FALLBACK = "General"

# Decision rules (tuned on tests/eval_categorizer.py DEV set only)
MIN_SCORE = 0.05        # best cosine similarity must reach this
MIN_MARGIN = 0.012      # and beat the runner-up by at least this much

VOCABULARY = {
    "Politics": """election elections vote voting voters poll polls polling ballot campaign candidate candidates
        party parties bjp congress aap tmc dmk shiv sena ncp opposition ruling coalition alliance government
        minister ministers cabinet parliament lok sabha rajya sabha assembly legislature mla mp mps senator senate
        congress house representatives president prime minister chief minister governor speaker bill bills law
        lawmakers legislation manifesto rally mandate constituency by-election resign resigns resignation
        secretary leader leaders politician politicians political politics policy reshuffle no-confidence
        trump biden modi kejriwal rahul gandhi yogi nitish stalin democrat republican whitehouse white house
        election commission opposition walkout speech chief minister's council councillor councillors municipal
        corporation civic mayor panchayat""",
    "Business": """market markets sensex nifty stock stocks share shares investor investors investment equity
        rbi reserve bank repo rate interest rates inflation gdp economy economic growth fiscal budget tax taxes gst
        profit profits loss revenue earnings quarterly results sales ipo merger acquisition acquires deal deals
        company companies corporate ceo firm firms bank banks banking loan loans rupee dollar forex crude oil
        prices price startup startups funding valuation unicorn exports imports trade tariff tariffs
        industry manufacturing retail consumer brand layoffs jobs employment unemployment mutual fund insurance
        billion crore lakh trillion bond bonds yields commodity gold silver real estate housing""",
    "Technology": """technology tech ai artificial intelligence machine learning chatbot generative openai chatgpt gemini
        llm software hardware app apps smartphone smartphones iphone android samsung apple google microsoft meta
        amazon nvidia intel chip chips semiconductor processor laptop gadget gadgets device devices launch launches
        cybersecurity cyber hack hacked hackers hacking breach ransomware malware data privacy password
        internet online platform social media instagram whatsapp x twitter youtube tiktok 5g 6g network
        cloud computing quantum robot robots robotics drone drones electric vehicle ev tesla battery
        startup developer developers code coding open-source gaming console playstation xbox update feature""",
    "Sports": """cricket match matches ipl bcci test series odi t20 innings wicket wickets runs batter batsman bowler
        captain squad team teams coach football soccer fifa premier league la liga goal goals striker
        tennis grand slam wimbledon open djokovic nadal federer sinner hockey kabaddi badminton olympics olympic
        paralympic medal medals gold athlete athletes tournament championship champion champions final semi-final
        stadium league season player players win wins won defeat defeats beat beats score scored scores
        fixture fixtures trophy cup world cup asia cup formula f1 grand prix race racing boxing wrestling
        marathon sprint swimming golf nba nfl mlb kohli rohit dhoni bumrah messi ronaldo""",
    "Entertainment": """film films movie movies cinema bollywood hollywood tollywood kollywood actor actress star stars
        director producer trailer teaser release releases box office collection collections blockbuster sequel
        series web series show shows netflix prime video disney hotstar ott streaming episode episodes season
        album song songs singer music concert tour band rapper grammy oscar oscars bafta filmfare awards award
        festival premiere celebrity celebrities wedding fans cast casting script screenplay biopic
        khan kapoor bachchan shah rukh salman aamir deepika ranveer alia priyanka television tv reality
        comedian comedy drama thriller romantic""",
    "World": """foreign international global world united nations un nato eu european union china russia ukraine
        gaza israel hamas palestine iran iraq syria pakistan bangladesh sri lanka nepal afghanistan taliban
        usa america american britain british uk france germany japan korea taiwan canada australia
        war conflict ceasefire truce peace talks diplomatic diplomacy embassy ambassador sanctions summit treaty
        border troops military missile missiles airstrike strikes attack refugees migrants asylum
        earthquake tsunami hurricane typhoon flood floods wildfire disaster killed casualties rescue
        g20 g7 brics imf world bank who global leaders""",
    "Science": """science scientist scientists researchers research study studies discovery discover discovers
        nasa isro esa spacex space satellite satellites rocket launch mission moon lunar mars planet planets
        telescope galaxy asteroid comet black hole astronomy astronomers orbit orbiter probe
        climate change warming emissions carbon species biodiversity fossil fossils dinosaur ocean
        physics chemistry biology genetics gene dna evolution experiment laboratory particle quantum
        energy fusion renewable solar discovery journal published nature peer-reviewed""",
    "Health": """health healthcare hospital hospitals doctor doctors patients patient medical medicine drug drugs
        vaccine vaccines vaccination virus viral infection outbreak epidemic pandemic covid dengue malaria
        cancer diabetes heart disease diseases symptoms treatment therapy surgery clinical trial
        mental health depression anxiety obesity diet nutrition fitness who ministry health
        cases deaths flu influenza tuberculosis fda icmr aiims pharmaceutical pharma
        wellness sleep blood pressure cholesterol pregnancy""",
    "Education": """education school schools student students teacher teachers university universities college colleges
        campus exam exams examination neet jee cuet cbse icse board boards result results syllabus curriculum
        admission admissions scholarship scholarships tuition degree degrees graduate graduates
        ugc aicte iit iim nit ncert nep literacy classroom classrooms learning academic academics
        professor lecturer phd research scholars dropout enrolment enrollment hostel convocation""",
}

_lock = threading.Lock()
_model = None   # (vectorizer, category matrix)


def _build():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                vec = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
                matrix = vec.fit_transform([VOCABULARY[c] for c in CATEGORIES])
                _model = (vec, matrix)
    return _model


def _matched_terms(text: str, category: str, limit: int = 5) -> list[str]:
    """Words from ``text`` (as written, not stemmed) that belong to the winning vocabulary."""
    vocab = set(tokens(VOCABULARY[category]))
    seen, out = set(), []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        key = stem(word)
        if key in vocab and key not in seen and word not in STOP:
            seen.add(key)
            out.append(word)
    return out[:limit]


def classify_topic(title, description: str = "", body: str = "") -> dict:
    """Return ``{label, score, method, matched, reason}``.  Never raises.

    ``label`` is one of ``CATEGORIES`` or ``General`` when the text is empty, uninformative or
    the best two categories are too close to call.  ``score`` is only set for a real category.
    """
    base = {"label": FALLBACK, "score": None, "confidence": None, "method": "tfidf-vocabulary-similarity",
            "matched": [], "reason": None}
    try:
        headline = clean_text(title, 400)
        if not headline and not clean_text(description, 50):
            return {**base, "reason": "empty"}
        text = " ".join(part for part in (headline, headline, clean_text(description, 600), clean_text(body, 600)) if part)
        if not tokens(text):
            return {**base, "reason": "no_informative_words"}
        vec, matrix = _build()
        sims = cosine_similarity(vec.transform([text]), matrix)[0]
        order = sims.argsort()[::-1]
        best, runner = float(sims[order[0]]), float(sims[order[1]])
        if best < MIN_SCORE:
            return {**base, "reason": "low_similarity"}
        if best - runner < MIN_MARGIN:
            return {**base, "reason": "ambiguous"}
        label = CATEGORIES[int(order[0])]
        return {**base, "label": label, "score": round(best, 3), "matched": _matched_terms(text, label)}
    except Exception as exc:
        log.warning("Categorisation failed: %s", type(exc).__name__)
        return {**base, "reason": "error"}
