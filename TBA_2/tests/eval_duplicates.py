"""Threshold study for duplicate detection (hand-written headline pairs).

Similarity is computed the way the app does it: TF-IDF is fitted on a *whole feed* of headlines (here all
64 unique headlines below), so word rarity is meaningful.  A 2-document corpus would be unrealistic.

    python tests/eval_duplicates.py

POSITIVE pairs describe the same event with different wording (as two publishers might).
NEGATIVE pairs are *hard*: same topic or sharing names/numbers, but different events.
The pairs are synthetic, written by the project author; they illustrate the precision/recall trade-off
of the threshold and are not a benchmark.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from services import config  # noqa: E402
from services.similarity import similarity_matrix  # noqa: E402
from services.text_utils import tokens  # noqa: E402

POSITIVE = [
    ("RBI keeps repo rate unchanged at 6.5%", "Reserve Bank holds repo rate steady at 6.5 per cent"),
    ("Pune metro Line 3 extension approved by council", "Council approves Line 3 metro extension in Pune"),
    ("India beat Australia by five wickets in Mumbai ODI", "Australia lose to India by five wickets in the Mumbai ODI"),
    ("Fire at chemical factory in Surat kills six", "Six dead after chemical factory fire in Surat"),
    ("Apple unveils iPhone 17 with new camera system", "Apple launches iPhone 17 featuring upgraded camera system"),
    ("Heavy rain floods Mumbai streets, local trains delayed", "Mumbai floods: heavy rain disrupts local trains and streets"),
    ("Supreme Court stays High Court order on land acquisition", "Land acquisition: Supreme Court stays High Court order"),
    ("Sensex crashes 900 points as global markets slide", "Sensex plunges 900 points amid global market sell-off"),
    ("Government announces new scholarship scheme for girl students", "New scholarship scheme for girl students announced by government"),
    ("Earthquake of magnitude 6.1 strikes northern Japan", "Magnitude 6.1 earthquake hits northern Japan"),
    ("Delhi air quality turns severe, schools shut", "Schools shut as Delhi air quality turns severe"),
    ("Tata Motors reports 18 percent jump in quarterly profit", "Tata Motors quarterly profit jumps 18 percent"),
    ("Opposition walks out of Lok Sabha over fuel price hike", "Lok Sabha: opposition stages walkout over fuel price hike"),
    ("NASA confirms water ice found near lunar south pole", "Water ice near lunar south pole confirmed by NASA"),
    ("Dengue cases cross 2,000 in Pune this season", "Pune dengue cases cross 2,000 this season"),
    ("Neeraj Chopra wins gold at Diamond League final", "Diamond League final: Neeraj Chopra clinches gold"),
]

NEGATIVE = [
    ("RBI keeps repo rate unchanged at 6.5%", "US Federal Reserve keeps interest rates unchanged"),
    ("India beat Australia by five wickets in Mumbai ODI", "India women beat England in T20 opener at Pune"),
    ("Fire at chemical factory in Surat kills six", "Fire at textile market in Surat causes losses worth crores"),
    ("Apple unveils iPhone 17 with new camera system", "Samsung unveils Galaxy foldable with new camera system"),
    ("Heavy rain floods Mumbai streets, local trains delayed", "Heavy rain floods Chennai streets, schools closed"),
    ("Supreme Court stays High Court order on land acquisition", "Supreme Court seeks reply on electoral bonds petition"),
    ("Sensex crashes 900 points as global markets slide", "Sensex rises 400 points on banking rally"),
    ("Government announces new scholarship scheme for girl students", "Government announces new highway project in Gujarat"),
    ("Earthquake of magnitude 6.1 strikes northern Japan", "Earthquake of magnitude 5.2 strikes southern Peru"),
    ("Delhi air quality turns severe, schools shut", "Delhi Metro adds new trains on Blue Line"),
    ("Tata Motors reports 18 percent jump in quarterly profit", "Infosys reports 12 percent rise in quarterly profit"),
    ("Opposition walks out of Lok Sabha over fuel price hike", "Opposition walks out of Rajya Sabha over farm bill"),
    ("NASA confirms water ice found near lunar south pole", "ISRO schedules lunar orbiter launch next month"),
    ("Dengue cases cross 2,000 in Pune this season", "Dengue cases cross 500 in Kolkata this season"),
    ("Neeraj Chopra wins gold at Diamond League final", "Neeraj Chopra to skip Asian Games with injury"),
    ("Pune metro Line 3 extension approved by council", "Mumbai metro Line 3 extension delayed by court case"),
    ("Parliament passes Finance Bill after long debate", "Parliament adjourned amid opposition protests"),
    ("Tech company announces layoffs of 2,000 workers", "Tech company announces new AI chip for data centres"),
    ("Cricket team announces squad for Asia Cup", "Football team announces squad for Asian Games"),
    ("Hospital reports rise in flu cases among children", "Hospital opens new cancer treatment wing"),
    ("Film breaks box office record on opening weekend", "Film festival announces jury for this year's awards"),
    ("Students protest hostel fee hike at university", "Students celebrate record placements at university"),
    ("Gold prices rise as dollar weakens", "Gold smuggling racket busted at airport"),
    ("Floods displace thousands in Assam", "Floods displace thousands in Bangladesh"),
]


CORPUS = []
for _a, _b in POSITIVE + NEGATIVE:
    for _t in (_a, _b):
        if _t not in CORPUS:
            CORPUS.append(_t)
SIMS = similarity_matrix(CORPUS)
INDEX = {t: i for i, t in enumerate(CORPUS)}


def is_same(a, b, threshold, min_shared=2):
    """Pair decision identical to the grouping rule (threshold + minimum shared informative words)."""
    return SIMS[INDEX[a], INDEX[b]] >= threshold and len(set(tokens(a)) & set(tokens(b))) >= min_shared


def score_pairs(threshold):
    tp = fn = fp = tn = 0
    errors = []
    for a, b in POSITIVE:
        same = is_same(a, b, threshold)
        tp, fn = tp + same, fn + (not same)
        if not same:
            errors.append(("FALSE NEGATIVE", round(float(SIMS[INDEX[a], INDEX[b]]), 2), a, b))
    for a, b in NEGATIVE:
        same = is_same(a, b, threshold)
        fp, tn = fp + same, tn + (not same)
        if same:
            errors.append(("FALSE POSITIVE", round(float(SIMS[INDEX[a], INDEX[b]]), 2), a, b))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, precision=precision, recall=recall, f1=f1, errors=errors)


if __name__ == "__main__":
    print(f"{len(POSITIVE)} same-story pairs, {len(NEGATIVE)} different-story pairs, {len(CORPUS)} headlines in the corpus")
    print("threshold  precision  recall   F1    FP  FN")
    for t in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70):
        r = score_pairs(t)
        print(f"  {t:.2f}      {r['precision']:.2f}      {r['recall']:.2f}   {r['f1']:.2f}   {r['fp']:>2}  {r['fn']:>2}")
    threshold = config.duplicate_threshold()
    print(f"\nErrors at the configured threshold ({threshold}):")
    for kind, sim, a, b in score_pairs(threshold)["errors"]:
        print(f"  {kind} (cosine {sim}): {a!r}  <->  {b!r}")
