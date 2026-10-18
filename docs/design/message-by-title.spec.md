# `message --by-title`: pick the follow-up by who the contact is

## Why

`linkedin-bots message` sends every contact the same text. The job hunt
reaches three kinds of people, and each needs a different follow-up:

- **recruiters** get the job-seeking pitch;
- **developers** get the peer conversation;
- **everyone else** (managers, CTOs, HR, students, unknown) gets a short
  note: "open to opportunities, think of me if something fits".

The contact's LinkedIn headline (the title under the name) says which group
they belong to. With `--by-title` the bot reads that headline and sends the
matching template.

## Decisions (the user's)

1. **The language still comes from today's routing.** The default `-m`
   template, `--last-message-regex` and `--last-message-regex-custom` pick
   the *base* file exactly as they do now (`message.txt`,
   `message_english.txt`, `reconnect.txt`, …). The headline only picks the
   audience variant of that base:

   | Audience  | File                    | Example (base `message_english.txt`) |
   |-----------|-------------------------|--------------------------------------|
   | recruiter | the base itself         | `message_english.txt`                |
   | dev       | `dev_` + base           | `dev_message_english.txt`            |
   | generic   | `generic_` + base       | `generic_message_english.txt`        |

2. **Who counts as a dev:** people who write code. That covers
   developer/desenvolvedor, programmer/programador, software
   engineer/engenheiro de software, front end, back end, full stack, mobile,
   tech lead and software architect/arquiteto de software. QA, data, DevOps
   and management roles are **generic**.
3. **Recruiting wins.** A headline with any recruiting term is a recruiter,
   even if it also has dev terms ("Tech Recruiter | Hiring Developers").
4. **Everything else is generic**, including a headline that could not be
   read.
5. **`--by-title` is opt-in.** Without the flag, every run behaves exactly
   as it does today, `--dry-run` included.
6. **Students, interns and trainees are not excluded.** With a dev term in
   the headline they are devs: they are good contacts for mentoring.
   Without one, they are generic, like anyone else.

## Goals

- `linkedin-bots message --by-title` (combined with any existing options)
  sends each contact the template for their audience in the run's language.
- The log shows, per contact, the headline, the audience and the file used.
  The end of the run reports how many contacts went to each audience.
- `--dry-run --by-title` shows which file each contact would get, without
  typing anything.
- New shipped templates `generic_message.txt` and
  `generic_message_english.txt` (texts below).

## Non-goals

- No change to how the language is chosen.
- No `generic_` siblings for `reconnect*` or `message_hired*`. Those runs
  fall back to the base file (see "Missing sibling").
- No change to the Windows `.exe` packaging. It ships one template per bot
  on purpose, so `--by-title` there falls back to the base unless the user
  adds siblings to the data home.
- No headline scoring thresholds or tuning flags. The audience is a plain
  three-way choice.

## Anti-goals (what would make this a failure even if it works)

- **Sending to the wrong person.** Opening the conversation earlier must not
  weaken the identity checks: the thread must open as this contact, the
  `ruled_out` thread check must run, and the name must be re-confirmed just
  before typing.
- **A silent fallback.** If LinkedIn changes its HTML, every contact lands
  in generic. That has to be obvious in the log (each contact shows
  "headline unreadable") and in the end-of-run counts.
- **Changing the connect bot.** Moving the shared matching code must not
  change any `connect` verdict. The existing `tech_recruiter` and `java_dev`
  tests must pass unchanged.
- **Personal data in the repo.** Shipped templates stay generic
  (`tests/test_shipped_templates.py`).

## How it works

### Templates

- For every base file in the run's routing (the `-m` default and each
  `--last-message-regex-custom` FILE), the CLI resolves `dev_<base>` and
  `generic_<base>` the same way it resolves the base: the data home wins
  over the shipped folder.
- The CLI loads all of them **at startup**, before the first conversation,
  as today. The domain never touches files.
- **Missing sibling:** that audience uses the base file. The CLI logs one
  warning per missing sibling at startup, e.g.
  `generic_reconnect.txt not found; generic contacts get reconnect.txt`.
  The per-contact log line then names the file actually used.
- An `-m` that already starts with `dev_` or `generic_` gets no special
  treatment. Its siblings (`dev_dev_…`) will not exist, so every audience
  falls back to it, with the warnings.
- The startup banner shows `By title : yes/no`.

### Classifying a headline

New module `messaging/domain/` (suggested name: `headline_audience.py`):
`classify(headline) -> Audience`, where Audience is one of RECRUITER, DEV
and GENERIC. In order:

1. Empty or `None` headline → GENERIC (reason: unreadable).
2. Any `RECRUITER_TERMS` hit in any segment → RECRUITER. This means any
   recruiting term, not only tech recruiting.
3. A dev term with no excluded term in the same segment → DEV.
4. Otherwise → GENERIC.

Requirements:

- Reuse the connect bot's fuzzy, segment-based matching (accent and case
  insensitive, `|`/`•`/`,` segments, word-aligned fuzzy match, short tokens
  matched exactly).
- The import contract forbids `messaging` from importing `connecting`.
  Move `normalize`, `split_segments`, `_similarity`, `_best_phrase_match`,
  `_matches_in_segment`, `_token_distance`, `SIM_THRESHOLD`,
  `MIN_TOKEN_SIM` and `RECRUITER_TERMS` to
  `shared/domain/headline_matching.py`.
- `tech_recruiter.py` and `java_dev.py` import them from there. Names stay
  as they are, so existing imports from `tech_recruiter` keep working.
- Dev terms (starting list; the builder may extend it, tests pin the
  examples below): developer, desenvolvedor, desenvolvedora, programmer,
  programador, programadora, software engineer, engenheiro de software,
  engenheira de software, software developer, frontend, front end, backend,
  back end, fullstack, full stack, mobile developer, mobile engineer,
  tech lead, software architect, arquiteto de software, arquiteta de
  software, dev, swe, sde.
- Excluded terms (keep these out of DEV): business developer,
  desenvolvedor de negocios, desenvolvedora de negocios.

Examples the tests must pin:

| Headline | Audience |
|---|---|
| `Tech Recruiter \| Hiring Developers` | recruiter |
| `Recrutadora \| Vagas de TI` | recruiter |
| `Talent Acquisition Partner` | recruiter |
| `Senior Software Engineer \| Java \| Spring` | dev |
| `Desenvolvedor Full Stack` | dev |
| `Front-end Developer \| React` | dev |
| `Tech Lead at Acme` | dev |
| `Engenheira de Software` | dev |
| `QA Analyst` | generic |
| `Data Engineer` | generic |
| `DevOps Engineer` | generic |
| `Engineering Manager` | generic |
| `CTO` | generic |
| `Analista de RH` | generic |
| `Estudante \| Desenvolvedor Front-end` | dev |
| `Desenvolvedor Trainee` | dev |
| `Estudante de Medicina` | generic |
| `Business Developer` | generic |
| `""` / `None` | generic |

### Reading the headline (Selenium adapter)

- The conversation list does not show headlines. The open conversation
  does: the profile card at the very start of its history,
  `div.msg-s-profile-card` (the `li` after
  `li.msg-s-message-list__top-of-list` in
  `ul.msg-s-message-list-content`). The headline is
  `.artdeco-entity-lockup__subtitle`.
- Prefer the inner `div[title]` attribute, which holds the full headline
  even when the text is truncated. Fall back to the element's text.
- **Only trust a card for this contact.** Its profile-link name must contain
  the contact's first name (the same rule as `_wait_thread_open`).
  Otherwise the card may be a stale one from the previous conversation.
- In long conversations the start of the history loads on demand
  (`li.msg-s-message-list__loader`). If the card is not there, scroll the
  message list to the top and wait for the loader, a bounded number of
  times (3 is the suggested bound). Still nothing → `None`, which becomes
  generic.
- Any exception while reading → `None`. Reading the headline never fails
  the send.

### Use case and port

Today `Thread.send(card, name, message, ruled_out)` opens and sends in one
call, so the message is fixed before the conversation opens. With
`--by-title` the order becomes:

1. `assess` decides, as today (date limits, pills, history, routing). The
   routing result now carries the base's audience family instead of a single
   template.
2. The bot opens the conversation: click, wait for it to open as this
   contact, `ruled_out` check. A skip or error here ends this contact, as
   today.
3. It reads the headline, classifies it and picks the template.
4. It logs `Name: "headline" → dev → dev_message_english.txt` (or
   `headline unreadable → generic → …`).
5. Dry run: it logs the `[DRY-RUN]` line and moves on without typing.
   Otherwise it captures the next card, re-confirms identity and sends, as
   today.

**Port shape (builder's call):** split `Thread` into an *open* step (which
returns the open conversation, or a skip/error `SendResult`), a *headline*
read and a *send* step. The required properties:

- without `--by-title`, the browser does exactly what it does today, in the
  same order;
- the identity re-check right before typing stays.

Without `--by-title`, `--dry-run` still never opens a conversation.

**Known side effect:** `--dry-run --by-title` opens each conversation,
which marks unread ones as read, and it is slower (human-like pauses per
open). The `--by-title` help text says so.

### End-of-run summary

When `--by-title` is on, the bot logs one line at the end with sent (or,
in dry runs, would-send) counts per audience, plus how many of the generic
ones were unreadable. For example:
`By title: recruiter=4, dev=7, generic=3 (1 unreadable)`.

### CLI and docs

- Flag: `--by-title`, with this help text:
  "Read each contact's headline and send the recruiter (base), dev_ or
  generic_ variant of the template. Opens every conversation, also in
  --dry-run."
- Add an example to the EPILOG.
- `docs/messaging.md`: add a "Routing by title" section in both languages
  (English and Português) and add the option to both options tables.

### New templates

`src/linkedin_bots/messaging/templates/generic_message_english.txt`:

```
Hi {name}, how are you?

Thanks for accepting my connection request! 😊

I'm a full stack developer who uses AI end to end in my workflow, from specs and design to code, tests and delivery. I'm currently open to new job opportunities.

If you hear of a role that might fit, at your company or elsewhere, I'd really appreciate it if you thought of me. And if you'd just like to chat, feel free to reach out!

Best regards
```

`src/linkedin_bots/messaging/templates/generic_message.txt`:

```
Olá, {name}, tudo bem?

Agradeço por aceitar a conexão! 😊

Sou dev full stack e uso IA de ponta a ponta no meu fluxo de trabalho, da especificação e do design ao código, aos testes e à entrega. Estou em busca de novas oportunidades de trabalho.

Se souber de alguma vaga que combine com o meu perfil, na sua empresa ou em outro lugar, agradeço muito se lembrar de mim. E se quiser só trocar uma ideia, é só chamar!

Um abraço
```

Add both to `SHIPPED["messaging"]` in `tests/test_shipped_templates.py`.

## Testing

- Domain: the table above, plus the existing `connect` classifier tests,
  unchanged and green after the move.
- Template families: sibling resolution (data home over shipped), the
  missing-sibling fallback and its warning.
- Use case (fakes): each audience gets its file; unreadable → generic;
  dry run with `--by-title` opens but never sends; without `--by-title` the
  fake thread sees the same calls as today; a skip/error on open counts as
  today; the end-of-run counts.
- Adapter: inject a synthetic headline into the
  `tests/fixtures/messaging/message-list-detail*.html` profile card (the
  fixtures are REDACTED) and check:
  - `title` attribute preferred over text;
  - a card for another name ignored;
  - no card → `None`.
  Scroll-to-top retries are stubbed.
- `lint-imports` stays green, with the new shared module in
  `shared.domain`.

## Calls made by the spec author (check these)

- **"Business Developer" → generic.** It is a sales role, despite the word
  "developer".
- **`RECRUITER_TERMS` reused as-is.** Its loose terms ("hiring", "hunter",
  "hunting") turn "Software Engineer | Hiring" and "Bug Hunter" into
  recruiters. That follows rule 3 (recruiting wins), but these are the
  likeliest misfires.
- **Profile card name check,** so a stale card never decides the template.
- **Missing-sibling warnings at startup,** once per file, not once per
  contact.
- **Spec in English, one file.** I can add a pt-BR copy if you want the
  pair, like `messaging-bot.spec.md`.
