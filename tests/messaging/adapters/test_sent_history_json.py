"""The send history on disk."""
import json
from datetime import datetime

import pytest

from linkedin_bots.messaging.adapters import sent_history_json
from linkedin_bots.messaging.adapters.sent_history_json import JsonSentHistory, default_history_file
from linkedin_bots.messaging.application.ports import HistoryUnreadable, HistoryUnwritable
from linkedin_bots.messaging.domain.past_sends import PastSend


@pytest.fixture
def path(tmp_path):
    return tmp_path / "sent_history.json"


def test_it_lives_in_the_data_directory(isolated_data_home):
    assert default_history_file() == isolated_data_home / "messaging" / "sent_history.json"


def test_a_missing_file_is_an_empty_history(path):
    assert JsonSentHistory(path).load() == {}


def test_legacy_name_only_entries_load_as_one_send(path):
    path.write_text(json.dumps({"Beatriz Teixeira": "2026-07-25T03:18:19"}), encoding="utf-8")
    assert JsonSentHistory(path).load() == {
        "Beatriz Teixeira": [PastSend(datetime(2026, 7, 25, 3, 18, 19))]}


def test_a_second_person_with_the_name_is_appended(path):
    path.write_text(json.dumps({"Beatriz Teixeira": "2026-07-25T03:18:19"}), encoding="utf-8")
    JsonSentHistory(path).record("Beatriz Teixeira", photo="D4D03AQF", thread="2-abc")
    sends = JsonSentHistory(path).load()["Beatriz Teixeira"]
    assert sends[0] == PastSend(datetime(2026, 7, 25, 3, 18, 19))
    assert (sends[1].photo, sends[1].thread) == ("D4D03AQF", "2-abc")


def test_unknown_photo_and_thread_are_left_out(path):
    JsonSentHistory(path).record("Ana Silva")
    assert set(json.loads(path.read_text(encoding="utf-8"))["Ana Silva"][0]) == {"ts"}


def test_unreadable_history_raises(path):
    path.write_text('{"Ana Silva": [{"ts": "2026-', encoding="utf-8")
    with pytest.raises(HistoryUnreadable):
        JsonSentHistory(path).load()


def test_a_corrupt_file_is_never_overwritten(path):
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(HistoryUnwritable):
        JsonSentHistory(path).record("Ana Silva")
    assert path.read_text(encoding="utf-8") == "not json"


def test_a_write_that_fails_midway_leaves_the_file_intact(path, monkeypatch):
    JsonSentHistory(path).record("Ana Silva")
    before = path.read_text(encoding="utf-8")

    def half_written(data, f, **kwargs):
        f.write('{"Ana Si')
        raise OSError("disk full")

    monkeypatch.setattr(sent_history_json.json, "dump", half_written)
    with pytest.raises(HistoryUnwritable):
        JsonSentHistory(path).record("Bruno Lima")
    assert path.read_text(encoding="utf-8") == before


def test_a_file_locked_by_another_program_is_retried(path, monkeypatch):
    real_replace = sent_history_json.os.replace
    attempts = []

    def locked_once(src, dst):
        attempts.append(1)
        if len(attempts) == 1:
            raise PermissionError(5, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(sent_history_json.os, "replace", locked_once)
    monkeypatch.setattr(sent_history_json.time, "sleep", lambda s: None)
    JsonSentHistory(path).record("Ana Silva")
    assert "Ana Silva" in json.loads(path.read_text(encoding="utf-8"))


def test_a_file_that_stays_locked_raises(path, monkeypatch):
    def locked(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(sent_history_json.os, "replace", locked)
    monkeypatch.setattr(sent_history_json.time, "sleep", lambda s: None)
    with pytest.raises(HistoryUnwritable):
        JsonSentHistory(path).record("Ana Silva")
    assert not path.exists()


def test_writes_leave_no_temporary_file_behind(path):
    JsonSentHistory(path).record("Ana Silva")
    assert [p.name for p in path.parent.iterdir()] == ["sent_history.json"]
