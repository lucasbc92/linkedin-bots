"""Who a contact is, from their headline, and which template that earns them."""
import pytest

from linkedin_bots.messaging.domain.headline_audience import (Audience, TemplateFamily, Variant,
                                                              classify)

CASES = [
    ("Tech Recruiter | Hiring Developers", Audience.RECRUITER),
    ("Recrutadora | Vagas de TI", Audience.RECRUITER),
    ("Talent Acquisition Partner", Audience.RECRUITER),
    ("Senior Software Engineer | Java | Spring", Audience.DEV),
    ("Desenvolvedor Full Stack", Audience.DEV),
    ("Front-end Developer | React", Audience.DEV),
    ("Tech Lead at Acme", Audience.DEV),
    ("Engenheira de Software", Audience.DEV),
    ("Estudante | Desenvolvedor Front-end", Audience.DEV),
    ("Desenvolvedor Trainee", Audience.DEV),
    ("Software Engineer @ Nubank", Audience.DEV),
    ("DESENVOLVEDOR BACK-END &amp; INSTRUTOR", Audience.DEV),
    ("Tech Lead | Engineering Manager", Audience.DEV),
    ("Senior Java Developer | Open Source", Audience.DEV),
    ("QA Analyst", Audience.GENERIC),
    ("Data Engineer", Audience.GENERIC),
    ("DevOps Engineer", Audience.GENERIC),
    ("Engineering Manager", Audience.GENERIC),
    ("Software Engineering Manager", Audience.GENERIC),
    ("Head of Software Engineering", Audience.GENERIC),
    ("CTO", Audience.GENERIC),
    ("Analista de RH", Audience.GENERIC),
    ("Estudante de Medicina", Audience.GENERIC),
    ("Business Developer", Audience.GENERIC),
    ("", Audience.GENERIC),
    (None, Audience.GENERIC),
]


@pytest.mark.parametrize("headline,audience", CASES)
def test_each_headline_lands_in_its_audience(headline, audience):
    assert classify(headline) is audience


def test_a_family_hands_out_the_variant_for_each_audience():
    family = TemplateFamily(Variant("R", "message.txt"), Variant("D", "dev_message.txt"),
                            Variant("G", "generic_message.txt"))
    assert [family.pick(a).source for a in Audience] == [
        "message.txt", "dev_message.txt", "generic_message.txt"]
