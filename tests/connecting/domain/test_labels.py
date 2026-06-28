"""Names read out of a card's action label."""
from linkedin_bots.connecting.domain.labels import (first_name_from_label, full_name_from_label,
                                                    same_person)


def test_reads_the_name_out_of_both_kinds_of_label():
    assert full_name_from_label("Invite Ana Lima to connect") == "Ana Lima"
    assert full_name_from_label("Follow Ana Lima") == "Ana Lima"
    assert full_name_from_label("Send a message to Ana") is None
    assert full_name_from_label(None) is None


def test_the_first_name_comes_off_a_follow_label_too():
    assert first_name_from_label("Follow Silvana Ferreira Alcides") == "Silvana"
    assert first_name_from_label("Invite João Victor Souza to connect") == "João Victor"


def test_names_compare_across_unicode_forms_case_and_spacing():
    assert same_person("Alex Nájera  Arcia", "alex nájera arcia")
    assert not same_person("Ana Lima", "Ana Souza")
