"""The experienced-Java-developer headline filter behind ``connect --java-devs``."""
import pytest

from linkedin_bots.connecting.domain.java_dev import score_title

ACCEPTED = {
    # Composite: one phrase says it all.
    "Java Specialist | Spring Boot | AWS": 1.0,
    "Desenvolvedor Java Sênior": 1.0,
    "Senior Java Developer | We are hiring!": 1.0,
    "Especialista em Java e Arquitetura de Software": 1.0,
    "Engenheiro de Software Sr. | Java, Spring Boot, AWS": 1.0,
    # Seniority and Java in the same segment.
    "Engenheiro de Software Sênior em Java": 0.9,
    "Staff Engineer - JVM Platform": 0.9,
    # Seniority and Java in different bullets.
    "Senior Software Engineer | Java | Spring": 0.85,
    "Desenvolvedor Back-end Sênior | Spring Boot | Kotlin": 0.85,
    "Desenvolvedor Java Pleno/Sênior": 0.85,
    # Ordinary words one letter away from an exclusion term.
    "Senior Java Backend Engineer | Spring | Micronaut | AWS | NewRelic | Inter 🧡": 1.0,
    "Senior Java Developer | Internal Platforms": 1.0,
    "Senior Java Developer | Open Source": 1.0,
}

REJECTED = (
    # Java, but not experienced.
    "Desenvolvedor Java Júnior",
    "Desenvolvedor Java Pleno",
    # Experienced, but not Java.
    "Senior Frontend Engineer | JavaScript",
    "Senior Scrum Master | Sprint planning",
    "Staff Software Engineer at Acme",
    # Ambiguous seniority words away from the Java word.
    "Sr. João Silva | Java",
    "Principal | Consultoria em Java",
    "Staff Engineer, JVM platform",
    # Excluded outright, whatever else the headline says.
    "Tech Recruiter | Vagas Java Sênior",
    "Talent Acquisition | Senior Java Developers",
    "Estudante de Ciência da Computação | Java",
    "Senior Java Intern",
    "",
    None,
)


@pytest.mark.parametrize("title,score", ACCEPTED.items())
def test_experienced_java_developers_are_accepted(title, score):
    verdict = score_title(title)
    assert verdict.is_java_dev, verdict
    assert verdict.score == pytest.approx(score, abs=0.01), verdict


@pytest.mark.parametrize("title", REJECTED)
def test_everyone_else_is_rejected(title):
    verdict = score_title(title)
    assert not verdict.is_java_dev, verdict
    assert verdict.score == 0.0, verdict


def test_an_exclusion_names_its_reason():
    assert "recrutadora" in score_title("Recrutadora | Java Sênior").reason


def test_tolerates_typos():
    assert score_title("Desenvolvedor Java Senoir").is_java_dev
    assert score_title("Java Especialsta").is_java_dev
