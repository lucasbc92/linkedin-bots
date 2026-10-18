"""Decide whether a LinkedIn headline belongs to a *tech* recruiter.

A people-search for "recruiter" returns every flavour of recruiter: health,
legal, retail, sales.  We only want the ones hiring for technology, so every
card's headline is scored before the Connect button is clicked.

The scoring is similarity-based (difflib, stdlib only) rather than exact
matching, so it survives typos, casing, accents and word padding:

    "Tech Recruiter | Recrutamento e seleção"  -> 1.00  (composite hit)
    "Recrutadora | Vagas de TI"                -> 0.90  (co-occurrence hit)
    "Web Development Student"                  -> 0.00  (tech, not a recruiter)
    "Recruiter | Saúde e Farmacêutico"         -> 0.00  (recruiter, not tech)

Two ways a headline can score:

1. COMPOSITE - one phrase that on its own proves it ("tech recruiter",
   "recrutador de ti").  Score = the similarity itself.
2. CO-OCCURRENCE - a recruiting word and a technology word inside the *same*
   segment of the headline ("recrutadora" + "ti").  Segments are the chunks
   between  |  /  •  ,  ;  -  so a tech word from an unrelated bullet cannot
   vouch for a recruiter word in another one.  Score = 0.9 * min(sims), i.e.
   always ranked below a clean composite hit.

Domain words that mark a *non*-tech specialisation subtract a small penalty,
enough to sink a borderline co-occurrence but never enough to sink a
composite hit ("Tech Recruiter | Vendas" is still a tech recruiter).
"""
from linkedin_bots.shared.domain.headline_matching import (RECRUITER_TERMS, SIM_THRESHOLD,
                                                           _best_phrase_match,
                                                           _matches_in_segment, _token_distance,
                                                           normalize, split_segments)

# ---------------------------------------------------------------- dictionaries

#: Phrases that identify a tech recruiter on their own.
COMPOSITE_TERMS = (
    # English
    "tech recruiter",
    "technical recruiter",
    "technology recruiter",
    "it recruiter",
    "software recruiter",
    "engineering recruiter",
    "developer recruiter",
    "dev recruiter",
    "data recruiter",
    "digital recruiter",
    "tech recruitment",
    "technical recruitment",
    "it recruitment",
    "tech talent acquisition",
    "technical talent acquisition",
    "it talent acquisition",
    "talent acquisition tech",
    "tech talent partner",
    "tech talent",
    "tech sourcer",
    "technical sourcer",
    "it sourcer",
    "tech headhunter",
    "headhunter tech",
    "tech hunter",
    "it hunter",
    "tech staffing",
    "it staffing",
    "tech hiring",
    "engineering hiring",
    # Portuguese
    "recrutador de ti",
    "recrutadora de ti",
    "recrutador tech",
    "recrutadora tech",
    "recrutador de tecnologia",
    "recrutadora de tecnologia",
    "recruiter de tecnologia",
    "recrutamento de ti",
    "recrutamento tech",
    "recrutamento de tecnologia",
    "recrutamento e selecao de ti",
    "selecao de ti",
    "hunter de ti",
    "headhunter de ti",
    "talentos de ti",
    "talentos tech",
    "vagas de ti",
    "vagas tech",
)

#: Words that mean "the hiring is for technology".
TECH_TERMS = (
    "tech",
    "techie",
    "technology",
    "technical",
    "tecnologia",
    "tecnologica",
    "ti",
    "it",
    "software",
    "hardware",
    "engineering",
    "engenharia",
    "developer",
    "developers",
    "desenvolvedor",
    "desenvolvedores",
    "dev",
    "devs",
    "programador",
    "programadores",
    "data",
    "dados",
    "cloud",
    "devops",
    "sre",
    "qa",
    "cyber",
    "cybersecurity",
    "ciberseguranca",
    "infosec",
    "digital",
    "sistemas",
    "informatica",
    "computacao",
    "frontend",
    "backend",
    "fullstack",
    "mobile",
    "ai",
    "ia",
    "machine learning",
    "startup",
    "startups",
    "saas",
    "fintech",
    "produto digital",
    "engenharia de software",
)

#: Domain words that point at a *different* recruiting specialisation.
NEGATIVE_TERMS = (
    "saude",
    "health",
    "healthcare",
    "medico",
    "medicina",
    "enfermagem",
    "hospitalar",
    "farmaceutico",
    "pharma",
    "juridico",
    "advocacia",
    "contabil",
    "agro",
    "agronegocio",
    "industrial",
    "construcao civil",
    "engenharia civil",
    "logistica",
    "varejo",
    "retail",
    "hotelaria",
    "gastronomia",
    "automotivo",
    "offshore",
    "petroleo",
)

#: Short tokens that are also ordinary words ("it", "ia", "data"...). They only
#: count as tech evidence next to the recruiting word, never across a clause.
AMBIGUOUS_TECH_TERMS = frozenset({"it", "ia", "ai", "ti", "qa", "data", "dev"})

#: How close (in tokens) an ambiguous tech word must sit to the recruiting word.
AMBIGUOUS_MAX_DISTANCE = 3

#: Minimum overall score for a headline to be treated as a tech recruiter.
DEFAULT_MIN_SCORE = 0.80

#: Score penalty per non-tech domain word, and the cap on the total penalty.
#: Calibrated so a single penalty sinks a co-occurrence hit (0.90 -> 0.75) while
#: even the maximum leaves a clean composite hit alive (1.00 -> 0.80): "Tech
#: Recruiter | Vendas" recruits for tech, "Recrutador de Engenharia Civil" does
#: not.
NEGATIVE_PENALTY = 0.15
MAX_NEGATIVE_PENALTY = 0.20

# ---------------------------------------------------------------------- public

class TitleVerdict:
    """Outcome of scoring one headline."""

    __slots__ = ("title", "score", "is_tech_recruiter", "reason", "matched")

    def __init__(self, title, score, is_tech_recruiter, reason, matched):
        self.title = title
        self.score = score
        self.is_tech_recruiter = is_tech_recruiter
        self.reason = reason
        self.matched = matched

    # Deliberately not truthy: `if verdict:` reads as "a verdict came back",
    # which is a different question from "they are a tech recruiter". Callers
    # must say which one they mean — `is not None` or `.is_tech_recruiter`.
    __bool__ = None

    def __repr__(self):
        return (f"TitleVerdict(score={self.score:.2f}, "
                f"tech_recruiter={self.is_tech_recruiter}, "
                f"reason={self.reason!r}, matched={self.matched!r})")


def score_title(title):
    """Score a headline in [0.0, 1.0] and explain the verdict.

    Returns a :class:`TitleVerdict`; ``is_tech_recruiter`` uses
    :data:`DEFAULT_MIN_SCORE`. Use :func:`is_tech_recruiter` to pass your own
    threshold.
    """
    segments = split_segments(title)
    if not segments:
        return TitleVerdict(title, 0.0, False, "empty title", [])

    best_score = 0.0
    reason = "no recruiting + technology evidence"
    matched = []

    # 1. Composite phrases, searched across the whole headline: a phrase such
    #    as "recrutamento de ti" may straddle a separator we split on.
    whole = normalize(title).split()
    for term in COMPOSITE_TERMS:
        score, _, _ = _best_phrase_match(whole, term)
        if score >= SIM_THRESHOLD and score > best_score:
            best_score = score
            reason = f"composite term {term!r} (similarity {score:.2f})"
            matched = [term]

    # 2. Recruiting word and technology word inside the same segment.
    if best_score < 1.0:
        for segment in segments:
            tokens = segment.split()
            recruiter_hits = _matches_in_segment(tokens, RECRUITER_TERMS)
            if not recruiter_hits:
                continue
            tech_hits = _matches_in_segment(tokens, TECH_TERMS)
            for tech_hit in tech_hits:
                for recruiter_hit in recruiter_hits:
                    if (tech_hit[0] in AMBIGUOUS_TECH_TERMS
                            and _token_distance(tech_hit, recruiter_hit)
                            > AMBIGUOUS_MAX_DISTANCE):
                        continue
                    score = 0.9 * min(tech_hit[1], recruiter_hit[1])
                    if score > best_score:
                        best_score = score
                        reason = (f"{recruiter_hit[0]!r} + {tech_hit[0]!r} "
                                  f"in segment {segment!r}")
                        matched = [recruiter_hit[0], tech_hit[0]]

    # 2b. Same two words, but in different bullets ("Talent Acquisition |
    #     Technology"). Scored lower than a same-segment hit, and closed to the
    #     ambiguous short tokens — "Recruiter | Making it happen" is not a
    #     match for "it".
    if best_score < SIM_THRESHOLD:
        whole_recruiter = _matches_in_segment(whole, RECRUITER_TERMS)
        whole_tech = [hit for hit in _matches_in_segment(whole, TECH_TERMS)
                      if hit[0] not in AMBIGUOUS_TECH_TERMS]
        if whole_recruiter and whole_tech:
            recruiter_hit = max(whole_recruiter, key=lambda hit: hit[1])
            tech_hit = max(whole_tech, key=lambda hit: hit[1])
            score = 0.85 * min(recruiter_hit[1], tech_hit[1])
            if score > best_score:
                best_score = score
                reason = (f"{recruiter_hit[0]!r} + {tech_hit[0]!r} "
                          f"in separate segments")
                matched = [recruiter_hit[0], tech_hit[0]]

    # 3. Non-tech specialisations pull the score down.
    normalized = normalize(title)
    negatives = [term for term in NEGATIVE_TERMS
                 if _best_phrase_match(normalized.split(), term)[0] >= SIM_THRESHOLD]
    if negatives and best_score > 0.0:
        penalty = min(len(negatives) * NEGATIVE_PENALTY, MAX_NEGATIVE_PENALTY)
        best_score = max(0.0, best_score - penalty)
        reason += f"; -{penalty:.2f} for {', '.join(negatives)}"

    return TitleVerdict(title, round(best_score, 4),
                        best_score >= DEFAULT_MIN_SCORE, reason, matched)


def is_tech_recruiter(title, min_score=DEFAULT_MIN_SCORE):
    """True when `title` scores at or above `min_score`."""
    return score_title(title).score >= min_score
