[English](README.md) | [Português (Brasil)](README.pt-BR.md)

# linkedin-bots

A small set of Python + Selenium bots that automate LinkedIn outreach by driving
**your own already-logged-in Chrome session**. Three bots, one command:

| Bot | Command | What it does | Docs |
|-----|---------|--------------|------|
| **Connect** | `linkedin-bots connect` | Walks people-search results and sends personalized connection invitations. | [docs/connecting.md](docs/connecting.md) |
| **Message** | `linkedin-bots message` | Walks the Messaging inbox and sends a personalized follow-up to each conversation. | [docs/messaging.md](docs/messaging.md) |
| **Withdraw** | `linkedin-bots withdraw` | Withdraws sent invitations older than a cutoff date, oldest first, to free the capped pending list. | [docs/withdrawing.md](docs/withdrawing.md) |

Each bot has its own guide with the full option reference and implementation
notes. This page covers everything they share: installation, configuration,
conventions and the architecture.

> **Heads-up.** Automating LinkedIn is against its Terms of Service and can get
> your account restricted. These tools throttle themselves with human-like
> delays and respect LinkedIn's limits, but you use them at your own risk. Keep
> volumes modest.

## How they work (the shared model)

All three bots **attach to an existing Chrome instance** over the DevTools protocol
rather than launching their own browser. That means:

- you log in to LinkedIn yourself, in a normal browser session, once; and
- the bots act as that session — no credential handling, no separate login.

You navigate to the right page (people-search results for `connect`, the
Messaging inbox for `message`, the sent-invitation manager for `withdraw`),
leave that tab open, and run the bot. It finds
the correct tab among your open tabs, then walks the page sending messages with
randomized pauses, keeping the PC awake until it finishes.

## Requirements and installation

- **Python 3.10+** (developed on 3.14)
- **Google Chrome**

Install the package into a virtual environment — editable, so code and
template changes apply without reinstalling:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
```

That puts a `linkedin-bots` command on the environment's PATH. Dependencies
are declared in [`pyproject.toml`](pyproject.toml).

Selenium 4.33 has **Selenium Manager** built in, so a matching ChromeDriver is
downloaded automatically the first time you run a bot — no manual driver setup.

## Setup: attach Chrome to the bots

The bots connect to Chrome on `127.0.0.1:9222`, so Chrome must be started with
remote debugging enabled. **Fully quit Chrome first**, then relaunch it with the
flags below.

> **Note:** recent Chrome versions silently refuse to open the DevTools port
> when using the **default** user-data-dir (a security measure against
> cookie-theft malware that scans for open 9222 ports). You must also pass
> `--user-data-dir` pointing at a separate, dedicated profile folder — you'll
> need to log in to LinkedIn once in that new profile.

**Windows (PowerShell):**
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebugProfile"
```

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeDebugProfile"
```

**Linux:**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeDebugProfile"
```

Then, in that Chrome window:

1. Log in to LinkedIn.
2. Open the page the bot needs:
   - **connect** → a people-search results page (`linkedin.com/search/results/people/…`)
   - **message** → the Messaging inbox (`linkedin.com/messaging`)
   - **withdraw** → the sent-invitation manager (`linkedin.com/mynetwork/invitation-manager/sent/`; the bot opens it if no tab shows it)
3. Run the bot, from any folder.

If no matching tab is found, each bot falls back to the current tab and warns
you.

## Running

```bash
linkedin-bots connect [options]     # send connection requests
linkedin-bots message [options]     # send follow-up messages
linkedin-bots withdraw [options]    # withdraw old sent invitations
linkedin-bots stats                 # invitations sent per week
linkedin-bots                       # prints help
linkedin-bots connect --help        # per-command help + examples
python -m linkedin_bots …           # the same, without the console script
```

See each bot's guide for its full option list:
[connect](docs/connecting.md#options) · [message](docs/messaging.md#options) · [withdraw](docs/withdrawing.md#usage).

## Templates

The connect and message bots read their message text from plain-text template files, so you can
edit wording without touching code.

```
src/linkedin_bots/connecting/templates/   # used by `linkedin-bots connect`
├── message.txt                           (default, Portuguese)
└── message_english.txt

src/linkedin_bots/messaging/templates/    # used by `linkedin-bots message`
├── message.txt                           (default, Portuguese)
├── message_english.txt
├── message_extended.txt                  (long version of each)
├── message_english_extended.txt
└── reconnect*.txt                        (re-approaching old contacts)
```

**Format** (handled by [`messages.py`](src/linkedin_bots/shared/domain/messages.py)):

- A file may hold **several variations separated by a line of three or more
  dashes** (`---`). The bot picks one at random per send, so your outreach
  doesn't look identical to everyone.
- `{name}` anywhere in the text is replaced with the contact's first name.
- If the contact's name can't be determined, `{name}` (and an adjacent comma /
  space) is dropped so the greeting still reads cleanly.

**Picking a template:** pass `-m <filename>` (resolved inside that bot's
templates folder), or `-m <path>` to point anywhere. With no `-m`, the
bot uses `message.txt`.

**Character limits:** connection-request notes are capped by LinkedIn at **300
characters** (counted as UTF-16 code units, so emoji = 2). The connect bot
enforces this — it drops `{name}` first, then truncates without splitting an emoji.
Direct messages have no cap, so the message bot never truncates.

### First-name handling

`{name}` is filled with the contact's first name via
[`names.py`](src/linkedin_bots/shared/domain/names.py), which is tuned for **Brazilian names**: it
keeps compound first names like *João Victor*, *Ana Júlia*, and
*Maria de Lourdes*, while dropping surnames such as *Silva* or *Santos*.

## Where data lives

Logs and the records of who was contacted are personal data, so they live
outside the repository, in your user data directory:

| OS | Folder |
|---|---|
| Windows | `%LOCALAPPDATA%\linkedin-bots\` |
| macOS | `~/Library/Application Support/linkedin-bots/` |
| Linux | `~/.local/share/linkedin-bots/` |

```
linkedin-bots/
├── connecting/
│   ├── invites.jsonl        # every confirmed invitation
│   └── logs/week-YYYY-MM-DD.log
├── messaging/
│   ├── sent_history.json    # everyone already messaged
│   └── logs/
└── withdrawing/
    └── logs/
```

Set `LINKEDIN_BOTS_HOME` to use another folder. Every run logs the path of its
log file when it starts and when it ends.

## Shared behavior & configuration

These apply to all three bots and are configured per-run via flags (there is no
config file):

- **Human-like delays.** Randomized pauses between actions and pages to avoid
  looking like a script.
- **Sleep prevention.** On Windows, the PC is kept awake during a run and
  restored afterward ([`sleep.py`](src/linkedin_bots/shared/infrastructure/sleep.py)). A no-op on other
  platforms.
- **Logging.** Every run is appended to that bot's weekly log file in the data
  directory (see [Where data lives](#where-data-lives); a week starts Sunday
  21:00, America/São_Paulo), and echoed to the console. Control verbosity with
  `-l / --log-level` (`INFO` default, or `DEBUG` / `WARN` / `ERROR`). Configured in
  [`logging_setup.py`](src/linkedin_bots/shared/infrastructure/logging_setup.py).
- **Run summary.** Each bot ends by printing a `sent / failed / skipped` tally.
- **Robust clicking.** LinkedIn ignores some synthetic clicks, so all three bots use
  a native → ActionChains → Chrome DevTools Protocol → JavaScript click ladder
  to produce trusted events (including inside Shadow DOM).
- **Graceful stop.** `Ctrl+C` stops a run cleanly and still restores power
  settings.

## Shell tab-completion (optional)

The `linkedin-bots` command ships argcomplete hooks, including completion of template filenames for
`-m`. One-time setup:

**Bash / Git Bash** — add to `~/.bashrc`:
```bash
eval "$(register-python-argcomplete linkedin-bots)"
```

**Zsh:**
```zsh
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete linkedin-bots)"
```

**PowerShell:**
```powershell
Register-ArgumentCompleter -Native -CommandName linkedin-bots -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $env:_ARGCOMPLETE = 1
    $env:COMP_LINE = $commandAst.ToString()
    $env:COMP_POINT = $cursorPosition
    linkedin-bots 2>&1 | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
```

## Project layout

```
linkedin-bots/
├── pyproject.toml               # package, dependencies, console script
├── src/linkedin_bots/
│   ├── cli/                     # composition root: one module per command
│   ├── connecting/              # Connect bot   → docs/connecting.md
│   ├── messaging/               # Message bot   → docs/messaging.md
│   ├── withdrawing/             # Withdraw bot  → docs/withdrawing.md
│   │   ├── domain/              #   pure rules: invitation ages, what to withdraw
│   │   ├── application/         #   use case + the ports it drives
│   │   └── adapters/selenium/   #   Page Objects for LinkedIn
│   └── shared/
│       ├── domain/              # first names, message templates
│       └── infrastructure/      # Chrome attach, clicks, scrolling, logs, data paths
├── tests/                       # mirrors src/; fixtures/ holds saved LinkedIn HTML
└── docs/                        # bot guides, design/ specs, reference/
```

All three contexts follow the same hexagonal shape. Dependencies point
inward (adapters → application → domain), and contexts never import each other.

## Running the tests

```bash
python -m pytest     # the whole suite; tests never touch your real data directory
```

Run them with pytest, not `unittest`: `tests/conftest.py` points every test at
a throwaway data directory, and only pytest loads it.

## License

[MIT](LICENSE) © Lucas Bueno Cesario.
