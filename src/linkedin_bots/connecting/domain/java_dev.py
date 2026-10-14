"""Decide whether a LinkedIn headline belongs to an *experienced* Java developer.

The counterpart of :mod:`tech_recruiter` for ``linkedin-bots connect
--java-devs``: a people-search for "java" returns students, juniors,
recruiters hiring Java developers and JavaScript people alongside the senior
Java engineers we want, so every card's headline is scored before the Connect
button is clicked.

It uses the same fuzzy, word-aligned matching as the recruiter filter, and the
same three routes, with a seniority word in place of the recruiting one:

    "Desenvolvedor Java Sênior"                    -> 1.00  (composite hit)
    "Engenheiro de Software Sênior em Java"        -> 0.90  (co-occurrence hit)
    "Senior Software Engineer | Java | Spring"     -> 0.85  (separate segments)
    "Desenvolvedor Java Júnior"                    -> 0.00  (Java, not senior)
    "Senior Frontend Engineer | JavaScript"        -> 0.00  (senior, not Java)
    "Tech Recruiter | Vagas Java Sênior"           -> 0.00  (excluded: recruiter)

There is no penalty scale here: a headline naming a recruiter, a student or an
intern is excluded outright, since "senior" and "java" in it describe the
vacancy or the course, not the person.
"""
from linkedin_bots.connecting.domain.tech_recruiter import (SIM_THRESHOLD, _best_phrase_match,
                                                            _matches_in_segment, _token_distance,
                                                            normalize, split_segments)

# ---------------------------------------------------------------- dictionaries

#: Phrases that identify an experienced Java developer on their own.
COMPOSITE_TERMS = (
    "senior java",
    "java senior",
    "sr java",
    "java sr",
    "java specialist",
    "java expert",
    "especialista java",
    "especialista em java",
    "staff java",
    "principal java",
    "java architect",
    "arquiteto java",
    "java tech lead",
    "tech lead java",
)

#: Words that mean "this person is experienced".
SENIORITY_TERMS = (
    "senior",
    "sr",
    "especialista",
    "specialist",
    "expert",
    "experiente",
    "experienced",
    "staff",
    "principal",
    "tech lead",
    "lider tecnico",
    "arquiteto",
    "architect",
)

#: Words that mean "the work is Java".
JAVA_TERMS = (
    "java",
    "jvm",
    "spring",
    "spring boot",
    "springboot",
    "java ee",
    "jakarta ee",
    "j2ee",
    "quarkus",
    "micronaut",
)

#: Words that rule a headline out whatever else it says.
EXCLUDED_TERMS = (
    "recruiter",
    "recruiting",
    "recruitment",
    "recrutador",
    "recrutadora",
    "recrutamento",
    "talent acquisition",
    "headhunter",
    "sourcer",
    "student",
    "estudante",
    "estagiario",
    "estagiaria",
    "intern",
    "internship",
    "trainee",
)

#: Short seniority tokens that are also ordinary words ("Sr." as a title,
#: "IT staff", "principal" as "main"). They only count right next to the Java
#: word, never across a clause.
AMBIGUOUS_SENIORITY_TERMS = frozenset({"sr", "staff", "principal"})

#: How close (in tokens) an ambiguous seniority word must sit to the Java word.
AMBIGUOUS_MAX_DISTANCE = 3

#: Minimum overall score for a headline to be treated as an experienced Java dev.
DEFAULT_MIN_SCORE = 0.80


# ---------------------------------------------------------------------- public

class DevVerdict:
    """Outcome of scoring one headline."""

    __slots__ = ("title", "score", "is_java_dev", "reason", "matched")

    def __init__(self, title, score, is_java_dev, reason, matched):
        self.title = title
        self.score = score
        self.is_java_dev = is_java_dev
        self.reason = reason
        self.matched = matched

    # Not truthy, for the same reason as TitleVerdict: "a verdict came back"
    # and "they are a senior Java dev" are different questions.
    __bool__ = None

    def __repr__(self):
        return (f"DevVerdict(score={self.score:.2f}, "
                f"java_dev={self.is_java_dev}, "
                f"reason={self.reason!r}, matched={self.matched!r})")


def score_title(title):
    """Score a headline in [0.0, 1.0] and explain the verdict."""
    segments = split_segments(title)
    if not segments:
        return DevVerdict(title, 0.0, False, "empty title", [])

    whole = normalize(title).split()

    excluded = [term for term in EXCLUDED_TERMS
                if _best_phrase_match(whole, term)[0] >= SIM_THRESHOLD]
    if excluded:
        return DevVerdict(title, 0.0, False,
                          f"excluded: {', '.join(excluded)}", excluded)

    best_score = 0.0
    reason = "no seniority + Java evidence"
    matched = []

    # 1. Composite phrases, searched across the whole headline.
    for term in COMPOSITE_TERMS:
        score, _, _ = _best_phrase_match(whole, term)
        if score >= SIM_THRESHOLD and score > best_score:
            best_score = score
            reason = f"composite term {term!r} (similarity {score:.2f})"
            matched = [term]

    # 2. Seniority word and Java word inside the same segment.
    if best_score < 1.0:
        for segment in segments:
            tokens = segment.split()
            java_hits = _matches_in_segment(tokens, JAVA_TERMS)
            if not java_hits:
                continue
            for seniority_hit in _matches_in_segment(tokens, SENIORITY_TERMS):
                for java_hit in java_hits:
                    if (seniority_hit[0] in AMBIGUOUS_SENIORITY_TERMS
                            and _token_distance(seniority_hit, java_hit)
                            > AMBIGUOUS_MAX_DISTANCE):
                        continue
                    score = 0.9 * min(seniority_hit[1], java_hit[1])
                    if score > best_score:
                        best_score = score
                        reason = (f"{seniority_hit[0]!r} + {java_hit[0]!r} "
                                  f"in segment {segment!r}")
                        matched = [seniority_hit[0], java_hit[0]]

    # 3. Same two words in different bullets ("Senior Software Engineer |
    #    Java"), closed to the ambiguous seniority tokens.
    if best_score < SIM_THRESHOLD:
        whole_seniority = [hit for hit in _matches_in_segment(whole, SENIORITY_TERMS)
                           if hit[0] not in AMBIGUOUS_SENIORITY_TERMS]
        whole_java = _matches_in_segment(whole, JAVA_TERMS)
        if whole_seniority and whole_java:
            seniority_hit = max(whole_seniority, key=lambda hit: hit[1])
            java_hit = max(whole_java, key=lambda hit: hit[1])
            score = 0.85 * min(seniority_hit[1], java_hit[1])
            if score > best_score:
                best_score = score
                reason = (f"{seniority_hit[0]!r} + {java_hit[0]!r} "
                          f"in separate segments")
                matched = [seniority_hit[0], java_hit[0]]

    return DevVerdict(title, round(best_score, 4),
                      best_score >= DEFAULT_MIN_SCORE, reason, matched)


def is_java_dev(title, min_score=DEFAULT_MIN_SCORE):
    """True when `title` scores at or above `min_score`."""
    return score_title(title).score >= min_score
