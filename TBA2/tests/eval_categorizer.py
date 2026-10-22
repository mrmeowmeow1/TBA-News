"""Small, hand-written evaluation of the topic categoriser.

    python tests/eval_categorizer.py

IMPORTANT - how to read the result
* The headlines below were written by the project author in the style of news headlines.  They are
  NOT a public benchmark and NOT real publisher headlines, so the numbers are indicative only.
* ``DEV`` was used while choosing MIN_SCORE / MIN_MARGIN.  ``TEST`` was written separately and
  scored without tuning on it.  Both sets share one author with the vocabulary lists, so real-world
  accuracy will probably be lower.
* "General" rows check that uninformative text is NOT forced into a category.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from services.categorizer import CATEGORIES, FALLBACK, classify_topic  # noqa: E402

DEV = [
    ("Opposition parties stage walkout in Lok Sabha over fuel price hike", "Politics"),
    ("Chief minister announces cabinet reshuffle ahead of assembly polls", "Politics"),
    ("Senate votes on funding bill as shutdown deadline nears", "Politics"),
    ("BJP and Congress trade charges as campaign enters final week", "Politics"),
    ("Sensex ends 600 points higher as banking stocks lead rally", "Business"),
    ("RBI holds repo rate steady, flags inflation risks", "Business"),
    ("Startup raises $40 million in Series B funding led by global investors", "Business"),
    ("Quarterly profit jumps 18% as retail sales improve", "Business"),
    ("New AI chatbot can write code and summarise documents", "Technology"),
    ("Apple unveils new iPhone with faster chip and better camera", "Technology"),
    ("Hackers breach database exposing millions of user passwords", "Technology"),
    ("Microsoft rolls out cloud update for developers", "Technology"),
    ("India beat Australia by five wickets to level the ODI series", "Sports"),
    ("Messi scores twice as Inter Miami reach the final", "Sports"),
    ("Neeraj Chopra wins gold at the athletics meet", "Sports"),
    ("Coach names squad for the Asia Cup tournament", "Sports"),
    ("Bollywood actor's new film opens strongly at the box office", "Entertainment"),
    ("Netflix series renewed for a third season, trailer released", "Entertainment"),
    ("Singer announces world concert tour after album release", "Entertainment"),
    ("Filmmaker's biopic to premiere at the international film festival", "Entertainment"),
    ("Ceasefire talks resume between Israel and Hamas in Cairo", "World"),
    ("NATO leaders meet as war in Ukraine enters another winter", "World"),
    ("UN warns of refugee crisis after fresh airstrikes", "World"),
    ("Earthquake strikes Japan coast, tsunami alert issued", "World"),
    ("ISRO schedules satellite launch for next month", "Science"),
    ("Researchers discover new species of frog in rainforest", "Science"),
    ("NASA telescope captures image of distant galaxy", "Science"),
    ("Study links rising ocean temperatures to climate change", "Science"),
    ("Dengue cases rise sharply as hospitals report full wards", "Health"),
    ("Doctors say new cancer treatment shows promise in clinical trial", "Health"),
    ("Health ministry issues advisory as flu infections spread", "Health"),
    ("Vaccine drive targets children under five", "Health"),
    ("CBSE announces Class 12 board exam results", "Education"),
    ("University opens admissions for undergraduate degree courses", "Education"),
    ("NEET aspirants demand revised syllabus and fair counselling", "Education"),
    ("Students protest hostel fee hike on campus", "Education"),
    ("Weather today", FALLBACK),
    ("Live updates", FALLBACK),
    ("Here's what happened", FALLBACK),
    ("", FALLBACK),
]

TEST = [
    ("Parliament session ends early after opposition protests over election law", "Politics"),
    ("Prime minister to address nation as coalition talks continue", "Politics"),
    ("Governor refers bill to president, state government objects", "Politics"),
    ("Voters queue up as polling begins in three constituencies", "Politics"),
    ("Candidate files nomination ahead of by-election", "Politics"),
    ("Gold prices slip as dollar strengthens against the rupee", "Business"),
    ("Company announces merger, shares surge on stock exchange", "Business"),
    ("GDP growth forecast cut as exports slow", "Business"),
    ("Bank profits rise but bad loans worry investors", "Business"),
    ("Retail giant plans layoffs to cut costs, earnings miss estimates", "Business"),
    ("Chipmaker unveils processor for next generation of laptops", "Technology"),
    ("Social media platform adds new privacy feature after outage", "Technology"),
    ("Cybersecurity firm warns of ransomware attack on hospitals software", "Technology"),
    ("Smartphone maker launches 5G handset at lower price", "Technology"),
    ("Open-source developers release major update to programming tool", "Technology"),
    ("Captain hits century as team wins third T20 against rivals", "Sports"),
    ("Tennis star advances to Wimbledon quarter-final", "Sports"),
    ("Football club sacks coach after league defeat", "Sports"),
    ("Olympic medallist returns home to a grand welcome", "Sports"),
    ("Kabaddi league final set for Sunday at city stadium", "Sports"),
    ("Hollywood director's sequel tops weekend box office", "Entertainment"),
    ("Actress opens up about role in upcoming web series", "Entertainment"),
    ("Music festival lineup announced, fans react", "Entertainment"),
    ("Oscar nominations: full list of films and actors", "Entertainment"),
    ("Reality show contestant evicted in dramatic episode", "Entertainment"),
    ("Russia and China sign trade agreement at summit", "World"),
    ("Floods displace thousands in neighbouring country, rescue under way", "World"),
    ("Sanctions imposed as diplomatic row between two nations deepens", "World"),
    ("Troops deployed along border after missile strike", "World"),
    ("Prime ministers meet at G20 to discuss global debt", "World"),
    ("Astronomers detect signal from black hole merger", "Science"),
    ("Scientists publish study on fossil of ancient dinosaur", "Science"),
    ("Mars orbiter sends new data on planet's atmosphere", "Science"),
    ("Physicists achieve record in quantum experiment", "Science"),
    ("Researchers develop battery that charges in minutes", "Science"),
    ("Hospital reports surge in viral infection among children", "Health"),
    ("Doctors warn about rising diabetes and obesity", "Health"),
    ("Mental health helpline sees record number of calls", "Health"),
    ("Drug trial shows reduced risk of heart disease", "Health"),
    ("Outbreak of malaria prompts health department alert", "Health"),
    ("Schools to reopen as board announces exam timetable", "Education"),
    ("IIT announces new scholarship for women students", "Education"),
    ("Teachers' association demands better pay in colleges", "Education"),
    ("Entrance exam results declared, merit list out", "Education"),
    ("University revises curriculum to include AI courses", "Education"),
    ("Top stories", FALLBACK),
    ("Breaking", FALLBACK),
    ("You won't believe what happened next", FALLBACK),
    ("Update", FALLBACK),
]


def evaluate(rows):
    right, confusion, misses = 0, Counter(), []
    per_class = {}
    for text, expected in rows:
        got = classify_topic(text)["label"]
        ok = got == expected
        right += ok
        per_class.setdefault(expected, [0, 0])
        per_class[expected][0] += ok
        per_class[expected][1] += 1
        if not ok:
            confusion[(expected, got)] += 1
            misses.append((text, expected, got))
    return right / len(rows), per_class, confusion, misses


def accuracy(rows):
    return evaluate(rows)[0]


if __name__ == "__main__":
    for name, rows in (("DEV", DEV), ("TEST", TEST)):
        acc, per_class, confusion, misses = evaluate(rows)
        print(f"\n== {name}: {len(rows)} headlines, accuracy {acc:.1%}")
        for label in CATEGORIES + [FALLBACK]:
            if label in per_class:
                hit, total = per_class[label]
                print(f"   {label:<14}{hit}/{total}")
        for text, expected, got in misses:
            print(f"   MISS expected {expected:<13} got {got:<13} | {text}")
