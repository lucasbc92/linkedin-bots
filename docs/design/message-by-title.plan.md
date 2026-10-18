# `message --by-title` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** With `linkedin-bots message --by-title`, each contact gets the base (recruiter), `dev_` or `generic_` variant of the template the run already picks, chosen from the contact's LinkedIn headline.

**Architecture:**
- The connect bot's fuzzy headline matching moves to `shared/domain` so messaging can use it.
- A new messaging domain module classifies a headline into recruiter, dev or generic, and holds the template family for a base file.
- The thread adapter splits "open" from "send" and gains a headline reader.
- The use case gets a by-title path; the default path keeps today's calls unchanged.
- The CLI loads each family up front.

**Tech Stack:** Python ≥3.10, Selenium 4.33, pytest, import-linter, lxml (tests only).

**Spec:** `docs/design/message-by-title.spec.md`

## Global Constraints

- **Default runs unchanged.** Without `--by-title`, every run behaves exactly as today, `--dry-run` included (it never opens a conversation).
- **Import contracts.** `messaging` never imports `connecting`. Domain and application code never import Selenium or `shared.infrastructure`. `lint-imports` stays green.
- **Connect unchanged.** Existing `connect` classifier tests pass unchanged after the move.
- **Generic templates.** Shipped templates hold no personal data (`tests/test_shipped_templates.py`).
- **Test command:** `python -m pytest` and `lint-imports`, both green after every task.
- **Commits:** local only (conventional style: `feat(messaging): …`, `refactor(shared): …`), each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.

## Review Focus

1. **Headlines with `@`, `&`, entities or all caps.** "Software Engineer @ Nubank" and "DESENVOLVEDOR BACK-END &amp; INSTRUTOR" are dev. Pinned in Task 2.
2. **Management titles that fuzzy-match a dev term.** "Software Engineering Manager" scores 0.92 against "software engineer", but management is generic. Pinned in Task 2; it is why `EXCLUDED_DEV_TERMS` has management words.
3. **The panel switches contact between reading the headline and typing.** `send_open` must still skip. Pinned in Task 3.
4. **A family split across folders.** The user has their own `message.txt` but no `generic_message.txt`, so generic gets the shipped generic. A base given as a path looks for its siblings next to it. Pinned in Task 5.
5. **Ctrl+C mid-run.** The run still logs the per-audience tally. Pinned in Task 4.

---

### Task 1: Move headline matching to the shared kernel

**Files:**
- Create: `src/linkedin_bots/shared/domain/headline_matching.py`
- Modify: `src/linkedin_bots/connecting/domain/tech_recruiter.py` (moved code removed, imported from shared)
- Modify: `src/linkedin_bots/connecting/domain/java_dev.py:23-25` (import from shared)
- Test: `tests/shared/domain/test_headline_matching.py`

**Interfaces:**
- Produces, all unchanged in name and behavior, moved from `tech_recruiter.py`:
  - `normalize(text) -> str`
  - `split_segments(text) -> list[str]`
  - `_similarity(a, b) -> float`
  - `_best_phrase_match(tokens, phrase) -> tuple`
  - `_matches_in_segment(tokens, terms) -> list[tuple]`
  - `_token_distance(a, b) -> int`
  - `SIM_THRESHOLD`, `MIN_TOKEN_SIM`, `_SEGMENT_SPLIT`, `_NON_WORD`, `RECRUITER_TERMS`
- Keep the comments that explain each one.
- `tech_recruiter.py` imports these names from the shared module, so `from linkedin_bots.connecting.domain.tech_recruiter import normalize` keeps working.

- [ ] **Step 1: Write the failing test** in `tests/shared/domain/test_headline_matching.py`

```python
from linkedin_bots.shared.domain.headline_matching import (RECRUITER_TERMS, _matches_in_segment,
                                                           normalize, split_segments)

def test_normalize_strips_accents_case_and_punctuation():
    assert normalize("Engenheira de Software – Front-End") == "engenheira de software front end"

def test_segments_split_on_bullets_not_on_spaced_hyphens():
    assert split_segments("Tech Recruiter | Hiring • TI") == ["tech recruiter", "hiring", "ti"]

def test_recruiter_terms_match_fuzzily_within_a_segment():
    assert _matches_in_segment("recrutadora de ti".split(), RECRUITER_TERMS)
```

- [ ] **Step 2:** Run `python -m pytest tests/shared/domain/test_headline_matching.py -v`. Expected: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Move the code.**
  - Cut the listed names from `tech_recruiter.py` into `headline_matching.py`, with the imports they need (`html`, `re`, `unicodedata`, `SequenceMatcher`).
  - Import them back into `tech_recruiter.py`.
  - Point `java_dev.py` at the shared module.
  - Drop imports in `tech_recruiter.py` that are now unused.
- [ ] **Step 4:** Run `python -m pytest` and `lint-imports`. Expected: all green, `connect` tests unchanged.
- [ ] **Step 5: Commit:** `refactor(shared): headline matching lives in the shared kernel`

---

### Task 2: Classify a headline and pick from a template family

**Files:**
- Create: `src/linkedin_bots/messaging/domain/headline_audience.py`
- Test: `tests/messaging/domain/test_headline_audience.py`

**Interfaces:**
- Consumes (Task 1): `split_segments`, `_matches_in_segment` and `RECRUITER_TERMS` from `linkedin_bots.shared.domain.headline_matching`.
- Produces:
  - `class Audience(Enum)`, with members `RECRUITER = "recruiter"`, `DEV = "dev"` and `GENERIC = "generic"`.
  - `classify(headline: Optional[str]) -> Audience`
  - `@dataclass(frozen=True) class Variant`, with fields `templates: object` and `source: str` (the file name, for logs).
  - `@dataclass(frozen=True) class TemplateFamily`, with fields `recruiter: Variant`, `dev: Variant` and `generic: Variant`, and the method `pick(self, audience: Audience) -> Variant`.
- Dictionaries (normalized form, as `normalize` produces):
  - `DEV_TERMS = ("developer", "desenvolvedor", "desenvolvedora", "programmer", "programador", "programadora", "software engineer", "engenheiro de software", "engenheira de software", "software developer", "frontend", "front end", "backend", "back end", "fullstack", "full stack", "mobile developer", "mobile engineer", "tech lead", "software architect", "arquiteto de software", "arquiteta de software", "dev", "swe", "sde")`
  - `EXCLUDED_DEV_TERMS = ("business developer", "desenvolvedor de negocios", "desenvolvedora de negocios", "manager", "gerente", "head of", "director", "diretor", "diretora", "coordenador", "coordenadora")`

- [ ] **Step 1: Write the failing tests**

```python
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
    ("Software Engineer @ Nubank", Audience.DEV),                    # review focus 1
    ("DESENVOLVEDOR BACK-END &amp; INSTRUTOR", Audience.DEV),        # review focus 1
    ("Tech Lead | Engineering Manager", Audience.DEV),
    ("QA Analyst", Audience.GENERIC),
    ("Data Engineer", Audience.GENERIC),
    ("DevOps Engineer", Audience.GENERIC),
    ("Engineering Manager", Audience.GENERIC),
    ("Software Engineering Manager", Audience.GENERIC),              # review focus 2
    ("Head of Software Engineering", Audience.GENERIC),              # review focus 2
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
```

- [ ] **Step 2:** Run `python -m pytest tests/messaging/domain/test_headline_audience.py -v`. Expected: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `classify`. Check the rules in order:
  1. No segments → GENERIC.
  2. Any segment with a `RECRUITER_TERMS` hit → RECRUITER.
  3. Any segment with a `DEV_TERMS` hit and no `EXCLUDED_DEV_TERMS` hit → DEV.
  4. Otherwise → GENERIC.

  A segment's tokens are `segment.split()`.
- [ ] **Step 4:** Run the test file, then `python -m pytest` and `lint-imports`. Expected: PASS. If a case fails on fuzzy matching, adjust the dictionaries, never the shared thresholds.
- [ ] **Step 5: Commit:** `feat(messaging): classify a headline as recruiter, dev or generic`

---

### Task 3: Thread adapter: open, read the headline, send

**Files:**
- Modify: `src/linkedin_bots/messaging/application/ports.py` (the `Thread` protocol)
- Modify: `src/linkedin_bots/messaging/adapters/selenium/thread_page.py`
- Test: `tests/messaging/adapters/test_thread_page.py` (existing tests stay as they are)
- Test: `tests/messaging/adapters/test_saved_markup.py` (new; lxml, skip if absent, like `tests/connecting/adapters/test_saved_markup.py`)

**Interfaces:**
- Produces, on `Thread` (the protocol) and `SeleniumThreadPage`:
  - `open(self, card, name: str, ruled_out: frozenset = frozenset()) -> Optional[SendResult]`: `None` once the conversation is open as this contact. Otherwise a `SKIPPED` result (did not open, or a `ruled_out` thread) or an `ERROR` result. The thread ID is kept on the page for `send_open`.
  - `headline(self, name: str) -> Optional[str]`: never raises.
  - `send_open(self, name: str, message: str) -> SendResult`: the rest of today's `send`, unchanged, from `_get_compose_box` through the identity re-check, pause and typing.
  - `send(self, card, name, message, ruled_out=frozenset()) -> SendResult`: becomes `self.open(...) or self.send_open(...)`. The browser calls stay the same and in the same order.
- Module constants:
  - `PROFILE_CARD_XPATH = "//div[contains(concat(' ', normalize-space(@class), ' '), ' msg-s-profile-card ')]"`
  - `CARD_NAME_XPATH = ".//div[contains(concat(' ', normalize-space(@class), ' '), ' artdeco-entity-lockup__title ')]"`
  - `CARD_HEADLINE_XPATH = ".//div[contains(concat(' ', normalize-space(@class), ' '), ' artdeco-entity-lockup__subtitle ')]"`
  - `MESSAGE_LIST_CSS = "div.msg-s-message-list"`
  - `HEADLINE_SCROLLS = 3`
- Helpers, so tests can stub them:
  - `_profile_cards(self) -> list` (the `driver.find_elements(By.XPATH, PROFILE_CARD_XPATH)` call);
  - `_scroll_history_to_top(self) -> None`.

- [ ] **Step 1: Write the failing tests** in `test_thread_page.py`. Stub the elements with a small fake: `text`, `get_attribute("title")`, and `find_elements(by, xpath)` returning children keyed by the XPath constant.
  - `test_open_then_send_open_sends_once_and_reports_the_thread`:
    `page.open(object(), "Ana Silva") is None`, and
    `page.send_open("Ana Silva", "Olá") == SendResult(SendStatus.SENT, "2-ana")`.
  - `test_open_skips_a_ruled_out_thread`: `open(..., ruled_out={"2-ana"}).status is SendStatus.SKIPPED`.
  - `test_send_open_skips_when_the_panel_switched_contact` (review focus 3):
    the first `_wait_thread_open` call returns True, later ones False;
    `send_open(...).status is SendStatus.SKIPPED`; `page.typed == []`.
  - `test_the_headline_prefers_the_full_title_attribute`:
    the subtitle's inner div has `title="Senior Software Engineer | Java | Spring"` and the truncated text `"Senior Software Engineer | Ja…"`; the title attribute wins.
  - `test_the_headline_falls_back_to_the_subtitle_text` (no title attribute).
  - `test_a_card_for_someone_else_is_ignored`:
    the card's name is "Bruno Lima", and `headline("Ana Silva")` returns `None` after scrolling.
  - `test_no_card_scrolls_to_the_top_a_bounded_number_of_times`:
    `_profile_cards` returns `[]`; the result is `None`, and `_scroll_history_to_top` was called `HEADLINE_SCROLLS` times.
  - `test_a_card_that_loads_after_one_scroll_is_read`.
  - `test_reading_the_headline_never_raises`: `_profile_cards` raises; the result is `None`.
- [ ] **Step 2: Write the saved-markup test.**
  - Load `tests/fixtures/messaging/message-list-detail.html` and `message-list-detail-old.html` with lxml.
  - Inject a synthetic name and headline into the REDACTED nodes found by the constants: set the name span text, and set the subtitle inner div's `title` and text.
  - Assert:
    - `PROFILE_CARD_XPATH` finds exactly one card;
    - `CARD_NAME_XPATH` inside it holds the injected name;
    - `CARD_HEADLINE_XPATH` inside it holds a `div[@title]` with the injected headline.
- [ ] **Step 3:** Run `python -m pytest tests/messaging/adapters -v`. Expected: the new tests FAIL (`AttributeError` for `open`/`headline`/`send_open`, and `PROFILE_CARD_XPATH` not defined); the old tests pass.
- [ ] **Step 4: Implement.**
  - **Splitting `send`:** split today's `try` block into `open` and `send_open`. Each gets its own `except Exception` returning `SendResult(SendStatus.ERROR)`. `send_open` logs and returns ERROR if called before a successful `open`.
  - **`headline`:**
    1. Take the first name the way `_wait_thread_open` does: `name.split()[0].lower()`.
    2. Up to `HEADLINE_SCROLLS + 1` times, look at each card from `_profile_cards()`. Use one whose `CARD_NAME_XPATH` text contains that first name.
    3. Read its headline: the subtitle's first child `div` with a non-empty `title` attribute, else the subtitle's `text`. Strip it; empty → keep looking.
    4. Between attempts, call `_scroll_history_to_top()` (`scrollTop = 0` on `MESSAGE_LIST_CSS`), then `self.pause(1, 2)`.
    5. On any exception → `None`.
  - **Port:** update the `Thread` protocol with the three methods; keep `send`.
- [ ] **Step 5:** Run `python -m pytest` and `lint-imports`. Expected: green.
- [ ] **Step 6: Commit:** `feat(messaging): read a contact's headline from the open conversation`

---

### Task 4: Use case: the by-title path

**Files:**
- Modify: `src/linkedin_bots/messaging/application/send_follow_ups.py`
- Test: `tests/messaging/application/test_send_follow_ups.py`

**Interfaces:**
- Consumes:
  - from Task 2: `classify`, `Audience`, `TemplateFamily.pick -> Variant`;
  - from Task 3: `Thread.open`, `Thread.headline`, `Thread.send_open`.
- Produces:
  - `FollowUpSettings.by_title: bool = False`.
  - With `by_title`, the CLI (Task 5) puts a `TemplateFamily` wherever `Routing` holds templates, so `verdict.templates` is a family.
  - New state on `SendFollowUps`: `self.audiences: Counter` (keyed by `Audience`) and `self.unreadable: int`.

- [ ] **Step 1: Extend the fakes.**
  - `FakeThread` gains `headlines: dict` (name → headline, default `{}`) and `calls: list` of method names.
  - It implements `open`: the same `ruled_out`, `interrupt_after` and outcome rules, where SKIPPED/ERROR outcomes come back from `open`.
  - It implements `headline` (`self.headlines.get(name)`) and `send_open`, which appends to `sent` and jumps to the top on SENT.
  - `send` stays as it is and appends `"send"` to `calls`.
  - `_run` accepts `by_title=True` through `**settings`.
- [ ] **Step 2: Write the failing tests.** Use a `FAMILY` of `MessageTemplates(["Recruiter {name}"])`, `MessageTemplates(["Dev {name}"])` and `MessageTemplates(["Generic {name}"])`, with sources `message.txt`, `dev_message.txt` and `generic_message.txt`, wrapped in `Routing(default=FAMILY, default_source="message.txt")`.
  - `test_by_title_each_audience_gets_its_variant`:
    - headlines: Ana → "Tech Recruiter", Bruno → "Desenvolvedor Java", Carla → "CTO";
    - `thread.sent == [("Ana", "Recruiter Ana"), ("Bruno", "Dev Bruno"), ("Carla", "Generic Carla")]`.
  - `test_by_title_an_unreadable_headline_gets_generic_and_says_so`: no headline. The message is generic, and `'Ana: headline unreadable → generic → generic_message.txt'` is in caplog.
  - `test_by_title_logs_headline_audience_and_file`: `'Bruno: "Desenvolvedor Java" → dev → dev_message.txt'` is in caplog.
  - `test_by_title_dry_run_opens_but_never_sends`:
    `thread.calls` contains `"open"` and `"headline"` but no `"send_open"`/`"send"`;
    `history.recorded == []`; `"[DRY-RUN] Would send to Bruno (dev_message.txt): Dev Bruno"` is in caplog.
  - `test_without_by_title_the_thread_only_sees_send`: today's `ROUTING`; `set(thread.calls) == {"send"}`.
  - `test_without_by_title_a_dry_run_never_opens_a_thread`: the existing test, which must still pass.
  - `test_by_title_a_skip_on_open_counts_as_skipped`: a `ruled_out` thread; `use_case.skipped == 1`, nothing sent.
  - `test_by_title_tally_counts_each_audience`:
    after the three-contact run plus one unreadable,
    `"By title: recruiter=1, dev=1, generic=2 (1 unreadable)"` is in caplog.
  - `test_by_title_ctrl_c_still_reports_the_audience_tally` (review focus 5):
    `interrupt_after=1`; `"By title: recruiter=1, dev=0, generic=0 (0 unreadable)"` is in caplog.
- [ ] **Step 3:** Run `python -m pytest tests/messaging/application -v`. Expected: the new tests FAIL; the old ones still pass.
- [ ] **Step 4: Implement.**
  - **Split `_send`:** turn it into `_tally(self, result, card) -> bool` (today's body after the `thread.send` call). Today's path calls `self._tally(self.thread.send(...), card)`.
  - **By-title path** (inside the loop, after the namesake log, when `s.by_title`):
    1. In real runs, capture `next_card`/`next_name` first, as today.
    2. `refusal = self.thread.open(current, card.name, verdict.ruled_out)`. If not `None`, `_tally` it and move on: in dry runs `advance(current)`, otherwise `refresh(next_card, next_name)` with today's lost-track check.
    3. `headline = self.thread.headline(card.name)`, `audience = classify(headline)`, `variant = verdict.templates.pick(audience)`.
    4. Log `f'{card.name}: "{headline}" → {audience.value} → {variant.source}'`, or with `headline unreadable` in place of the quoted headline when it is empty.
    5. Dry run: log the `[DRY-RUN]` line with `variant.source`, count the audience, then `advance`.
    6. Real run: call `send_open` and `_tally` it, counting the audience only on SENT. Then the `--max` check and `refresh` as today.
  - **Tally:** in `run()`'s `finally`, when `by_title`, log `f"By title: recruiter={…}, dev={…}, generic={…} ({self.unreadable} unreadable)"`. The `unreadable` counter rises when a generic contact's headline was empty.
- [ ] **Step 5:** Run `python -m pytest` and `lint-imports`. Expected: green.
- [ ] **Step 6: Commit:** `feat(messaging): pick each follow-up by the contact's headline`

---

### Task 5: CLI flag, template families, shipped generic templates, docs

**Files:**
- Modify: `src/linkedin_bots/cli/message.py`
- Create: `src/linkedin_bots/messaging/templates/generic_message.txt`
- Create: `src/linkedin_bots/messaging/templates/generic_message_english.txt`
- Modify: `tests/test_shipped_templates.py` (`SHIPPED["messaging"]`)
- Modify: `docs/messaging.md` (both languages)
- Test: `tests/cli/test_cli.py`

**Interfaces:**
- Consumes: from Task 2, `TemplateFamily` and `Variant`; from Task 4, `FollowUpSettings.by_title`.
- Produces, in `cli/message.py`:
  - `sibling_name(value: str, prefix: str) -> str`: for a bare file name, `prefix + value`. For a path (contains `os.sep` or `/`), the same folder with `prefix` before the file name.
  - `load_family(value: str, base: Path, logger) -> TemplateFamily`:
    - each sibling goes through `resolve_template(sibling_name(value, prefix), "messaging")`, so the data home wins per file;
    - a missing sibling logs `f"{sibling} not found; {audience} contacts get {base.name}"` and reuses the base;
    - templates are loaded with `load_templates`.

- [ ] **Step 1: Write the failing tests** (in `tests/cli/test_cli.py`, with `isolated_data_home`):
  - `test_by_title_reaches_the_parser`: `parse_args(["message", "--by-title"]).by_title is True`, and it defaults to `False`.
  - `test_a_family_takes_each_sibling_from_the_data_home_first` (review focus 4):
    the data home holds `message.txt` and `dev_message.txt`;
    the family's `recruiter.source`/`dev.source` come from there, and `generic` is the shipped `generic_message.txt`.
  - `test_a_missing_sibling_falls_back_to_the_base_and_warns`:
    `load_family("reconnect.txt", …)` gives `dev.source == "dev_reconnect.txt"` and `generic.source == "reconnect.txt"`;
    `"generic_reconnect.txt not found; generic contacts get reconnect.txt"` is in caplog.
  - `test_a_base_given_as_a_path_finds_its_siblings_next_to_it` (review focus 4):
    `tmp_path/"x.txt"` and `tmp_path/"dev_x.txt"` exist; `dev.source == "dev_x.txt"`, and generic falls back to `x.txt`.
  - In `tests/test_shipped_templates.py`, add `"generic_message.txt"` and `"generic_message_english.txt"` to `SHIPPED["messaging"]`.
- [ ] **Step 2:** Run `python -m pytest tests/cli tests/test_shipped_templates.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - **Flag:** `mp.add_argument("--by-title", action="store_true", help=...)`, with the help text verbatim from the spec: "Read each contact's headline and send the recruiter (base), dev_ or generic_ variant of the template. Opens every conversation, also in --dry-run."
  - **EPILOG example:**
    ```
      linkedin-bots message --by-title --dry-run
          # recruiters get message.txt, devs dev_message.txt, everyone else generic_message.txt
    ```
  - **Banner line:** `f"  By title   : {'yes' if args.by_title else 'no'}"`.
  - **Wiring:** when `args.by_title`, build `Routing.default` and every `TemplateRoute.templates` with `load_family(...)` instead of `load_templates(...)`. That needs the original `-m`/FILE values, so keep them next to the resolved paths in `regex_templates`. Pass `by_title=args.by_title` to `FollowUpSettings`.
  - **Template files:** create both with the exact texts in the spec's "New templates" section, UTF-8, no trailing blank line beyond the shipped files' style.
  - **`docs/messaging.md`:**
    - add `--by-title` to the English and Portuguese options tables;
    - add a "Routing by title" / "Roteamento pelo título" section after "Routing by last message" / "Roteamento pela última mensagem", covering the three audiences, sibling naming, the fallback warning and the dry-run side effect (it opens conversations and marks unread ones read);
    - point the "Design docs" lists at `design/message-by-title.spec.md`.
- [ ] **Step 4:** Run `python -m pytest` and `lint-imports`. Then run `PYTHONIOENCODING=cp1252 python -m linkedin_bots message --help > /dev/null` (Git Bash). Expected: green, and help exits 0 under cp1252.
- [ ] **Step 5: Commit:** `feat(messaging): --by-title sends recruiters, devs and everyone else their own template`

---

## Self-review notes

- **Spec coverage:**
  - decisions 1–6 → Tasks 2, 4 and 5;
  - template loading and fallback → Task 5;
  - classification and the shared move → Tasks 1–2;
  - adapter, name check and bounded scroll → Task 3;
  - port and order of operations → Tasks 3–4;
  - log lines and tally → Task 4;
  - help, epilog, banner, docs and templates → Task 5.
- **Added beyond the spec's starting lists:** management words in `EXCLUDED_DEV_TERMS`. Without them "Software Engineering Manager" fuzzy-matches "software engineer" (0.92) and lands in dev, against decision 2.
