"""Who a contact is, read from their headline, and the template that earns them.

Recruiting wins: a headline with any recruiting term is a recruiter, even
when it also names a dev role ("Tech Recruiter | Hiring Developers"). A dev
is anyone who writes code; QA, data, DevOps and management are generic, as is
a headline that could not be read.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from linkedin_bots.shared.domain.headline_matching import (RECRUITER_TERMS, _matches_in_segment,
                                                           split_segments)


class Audience(Enum):
    RECRUITER = "recruiter"
    DEV = "dev"
    GENERIC = "generic"


#: Roles of people who write code.
DEV_TERMS = (
    "developer",
    "desenvolvedor",
    "desenvolvedora",
    "programmer",
    "programador",
    "programadora",
    "software engineer",
    "engenheiro de software",
    "engenheira de software",
    "software developer",
    "frontend",
    "front end",
    "backend",
    "back end",
    "fullstack",
    "full stack",
    "mobile developer",
    "mobile engineer",
    "tech lead",
    "software architect",
    "arquiteto de software",
    "arquiteta de software",
    "dev",
    "swe",
    "sde",
)

#: Words that, in the same segment, keep a dev term from counting: a sales
#: role named "developer", and management ("Software Engineering Manager"
#: scores 0.92 against "software engineer").
EXCLUDED_DEV_TERMS = (
    "business developer",
    "desenvolvedor de negocios",
    "desenvolvedora de negocios",
    "manager",
    "gerente",
    "head of",
    "director",
    "diretor",
    "diretora",
    "coordenador",
    "coordenadora",
)


def classify(headline: Optional[str]) -> Audience:
    """The audience a headline belongs to; GENERIC when it is empty."""
    segments = [segment.split() for segment in split_segments(headline)]
    if any(_matches_in_segment(tokens, RECRUITER_TERMS) for tokens in segments):
        return Audience.RECRUITER
    if any(_matches_in_segment(tokens, DEV_TERMS)
           and not _matches_in_segment(tokens, EXCLUDED_DEV_TERMS) for tokens in segments):
        return Audience.DEV
    return Audience.GENERIC


@dataclass(frozen=True)
class Variant:
    """One template of a family, and the file it came from (for the log)."""

    templates: object
    source: str


@dataclass(frozen=True)
class TemplateFamily:
    """A base template and its ``dev_`` and ``generic_`` siblings."""

    recruiter: Variant
    dev: Variant
    generic: Variant

    def pick(self, audience: Audience) -> Variant:
        return {Audience.RECRUITER: self.recruiter, Audience.DEV: self.dev,
                Audience.GENERIC: self.generic}[audience]
