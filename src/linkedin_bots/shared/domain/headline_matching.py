"""Fuzzy matching of LinkedIn headlines: normalizing, segmenting and finding terms.

Shared by every bot that reads a headline: the connect bot's audience scorers
and the message bot's audience classifier.
"""
import html
import re
import unicodedata
from difflib import SequenceMatcher

#: Words that mean "this person recruits".
RECRUITER_TERMS = (
    "recruiter",
    "recruiting",
    "recruitment",
    "recrutador",
    "recrutadora",
    "recrutamento",
    "recruta",
    "selecao",
    "talent acquisition",
    "talent acquisition partner",
    "talent partner",
    "talent sourcing",
    "aquisicao de talentos",
    "atracao de talentos",
    "captacao de talentos",
    "headhunter",
    "head hunter",
    "hunter",
    "hunting",
    "sourcer",
    "sourcing",
    "staffing",
    "hiring",
    "talent scout",
)

#: Minimum per-phrase similarity for a dictionary term to count as present.
SIM_THRESHOLD = 0.85

#: Minimum similarity for each individual word of a multi-word phrase. Without
#: it, "sales recruiter" scores 0.86 against "it recruiter" — the long shared
#: tail drowns out the one word that carries the meaning.
MIN_TOKEN_SIM = 0.82

# Bullet separators only. A spaced hyphen is not one: "Recruiting Manager -
# Engineering" is a single thought and must keep its two halves together.
_SEGMENT_SPLIT = re.compile(r"[|/•·,;\n\r]+|\s{2,}")
_NON_WORD = re.compile(r"[^a-z0-9]+")


# ------------------------------------------------------------------- internals

def normalize(text):
    """Lowercase, unescape, strip accents and punctuation. '' for falsy input."""
    if not text:
        return ""
    text = html.unescape(str(text))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    return _NON_WORD.sub(" ", text).strip()


def split_segments(text):
    """Split a headline into its bullet-separated clauses, normalized."""
    if not text:
        return []
    raw = _SEGMENT_SPLIT.split(html.unescape(str(text)))
    return [seg for seg in (normalize(part) for part in raw) if seg]


def _similarity(a, b):
    """Fuzzy string ratio, with short strings compared exactly.

    'ti' vs 'tv' scores 0.5 under SequenceMatcher — far too generous for
    two-letter tokens, so anything up to 3 characters must match exactly.
    """
    if len(a) <= 3 or len(b) <= 3:
        return 1.0 if a == b else 0.0
    return SequenceMatcher(None, a, b).ratio()


def _best_phrase_match(tokens, phrase):
    """Best (similarity, start_index, end_index) of `phrase` over the tokens.

    The comparison is word-aligned: only windows of exactly the phrase's word
    count are considered, and *every* word pair must clear
    :data:`MIN_TOKEN_SIM`. Scoring whole windows as one string instead lets a
    long shared word carry a short mismatched one ("sales recruiter" reading as
    "it recruiter"), which is precisely the confusion this filter exists to
    avoid.
    """
    words = phrase.split()
    span = len(words)
    best = (0.0, -1, -1)
    for start in range(0, len(tokens) - span + 1):
        window = tokens[start:start + span]
        sims = [_similarity(a, b) for a, b in zip(window, words)]
        if min(sims) < MIN_TOKEN_SIM:
            continue
        score = sum(sims) / span
        if score > best[0]:
            best = (score, start, start + span)
    return best


def _matches_in_segment(tokens, terms):
    """Every term at/above threshold, as (term, similarity, start, end)."""
    hits = []
    for term in terms:
        score, start, end = _best_phrase_match(tokens, term)
        if score >= SIM_THRESHOLD:
            hits.append((term, score, start, end))
    return hits


def _token_distance(a, b):
    """Gap between two token spans (0 when they touch or overlap)."""
    _, _, a_start, a_end = a
    _, _, b_start, b_end = b
    if a_start < b_start:
        return max(0, b_start - a_end)
    return max(0, a_start - b_end)
