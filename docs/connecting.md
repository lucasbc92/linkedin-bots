# Connect bot

[English](#english) | [Português (Brasil)](#português-brasil)

## English

Walks your LinkedIn **people-search results** and sends personalized connection
invitations, page by page, until it runs out of results or hits LinkedIn's
weekly invitation limit.

> See the [root README](../README.md) for the one-time setup (attaching Chrome,
> installing dependencies) and the conventions shared by both bots.

### What it does

Starting from an open **people-search results** tab
(`linkedin.com/search/results/people/…`), the bot:

1. Finds the people-search tab among your open Chrome tabs (falling back to any
   search-results tab, then the current tab).
2. On each results page, scrolls to lazy-load every card, then walks the
   people on it top-to-bottom.
3. Reads each person's headline off their card and skips anyone who is not a
   **tech** recruiter — see [Tech-recruiter filter](#tech-recruiter-filter).
   Skipped cards are never clicked, so they cost nothing against your weekly
   invitation quota.
4. Opens the invite modal for each remaining person — from the **"Invite … to
   connect"** control on their card, or, when their card offers only
   **Follow**, from their profile page instead (see
   [Reaching people who only offer Follow](#reaching-people-who-only-offer-follow))
   — and either:
   - clicks **Add a note**, types a personalized message, and clicks
     **Send invitation**; or
   - clicks **Send without a note** (when run with `-n`).
5. Verifies the invite registered (the Connect control turns **Pending**), then
   pages forward (or backward with `-r`) and repeats.

The message text comes from a template in [`src/linkedin_bots/connecting/templates/`](../src/linkedin_bots/connecting/templates/).
`{name}` is replaced with the contact's first name; see
[Templates](../README.md#templates) in the root README for the format.

### Usage

```bash
linkedin-bots connect                       # default template, personalized note
linkedin-bots connect -m message_english.txt # invite in English
linkedin-bots connect -n                    # send invitations with no note
linkedin-bots connect -y -l INFO            # auto-continue past the warning, quieter
linkedin-bots connect -r                    # page backwards (Previous instead of Next)
linkedin-bots connect --max 80              # stop after 80 invitations sent
linkedin-bots connect --any-title           # invite every recruiter, not just tech
linkedin-bots connect --title-score 0.9     # stricter tech-recruiter filter
linkedin-bots connect -f                    # fast: minimal pauses between invites
```

#### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `-m`, `--message FILE` | `message.txt` | Template file. A bare filename is looked up in your own templates folder (see [Templates](../README.md#templates)), then in `src/linkedin_bots/connecting/templates/`; a path is used as-is. A file that doesn't exist stops the run (unless `-n` makes it moot). |
| `-n`, `--no-message` | off | Send invitations **without** a note (clicks "Send without a note"). |
| `-r`, `--reverse` | off | Navigate results in reverse (click **Previous** instead of **Next**). |
| `-y`, `--yes` | off | Auto-continue past the "close to the weekly invitation limit" warning instead of prompting. |
| `--max N` | unlimited | Stop after sending `N` invitations (blast-radius limit, independent of LinkedIn's own weekly cap). |
| `--any-title` | off | Invite **every** recruiter, skipping the tech-recruiter headline filter. |
| `--title-score S` | `0.80` | Minimum tech-recruiter similarity score (`0.0`–`1.0`). Raise it to be stricter, lower it to be more permissive. |
| `-f`, `--fast` | off | Shrink the randomized pauses to a minimum — see [Pacing](#pacing). |
| `-l`, `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARN`, or `ERROR`. |

### Pacing

Between actions the bot waits a random interval, so the rhythm doesn't read as
a script: 2–5 s before opening an invite modal, 8–18 s after each invitation,
12–25 s between result pages.

`-f` / `--fast` keeps the same randomness but scales every one of those windows
to a tenth, with a 0.5 s floor (`FAST_PAUSE_FACTOR` / `MIN_FAST_PAUSE` in
[`shared/infrastructure/pacing.py`](../src/linkedin_bots/shared/infrastructure/pacing.py)) — roughly 0.5 s, 0.8–1.8 s and 1.2–2.5 s. The floor
is there because LinkedIn's UI still needs a moment to settle between clicks.

Fixed waits that exist to let the page render (the modal opening, a page
loading) are unaffected — `--fast` only touches the humanizing pauses. Use it
for short or test runs; a full run at this pace is a much more obviously
automated pattern, and LinkedIn's weekly invitation cap applies either way.

### Reaching people who only offer Follow

LinkedIn keeps shrinking how many search results offer **Connect**. A card that
offers only **Follow** cannot be invited from the results list at all — but the
person behind it can still be invited from their own profile, where Connect
sits behind the three-dots **More** menu.

That is not a separate mode: it is one walk down the page, and each person is
invited whichever way their own card allows. Where the card has a Connect
control, it is clicked in place. Where it has only Follow, the bot:

1. Scores the headline first, exactly as usual. Someone who fails the
   [tech-recruiter filter](#tech-recruiter-filter) never costs a page load.
2. Opens their profile (`linkedin.com/in/…`, read off the person's own link in
   their card — not off a shared connection's).
3. Uses the profile's Connect control if it shows one, otherwise opens the
   **More** menu and takes Connect from there. The menu item labels its
   *inner div*, not the link around it, so the search matches any tag and
   then clicks the enclosing `<a href="/preload/custom-invite/…">`.
4. Runs the same modal ritual: **Add a note**, the personalized message,
   **Send invitation**, then the confirmation check and the ledger entry.
5. Steps **back** into the results, which resume from the person just handled.
   Everyone already processed on that page is remembered by their card's
   label, so nobody is invited twice.

The session summary reports how many invitations took the long way round:

```
Session summary — sent: 34 (of which 9 via the profile detour) | failed: 0 | skipped: 12
```

**What it costs.** Two page loads per Follow-only person, plus the usual 8–18 s
pause, so a page thick with them takes minutes rather than seconds. It spends
the same weekly invitation quota as any other invite — the detour reaches *more
people*, not more invitations.

**Three things it refuses to do:**

- **Invite the wrong person.** A profile page also shows Connect buttons for
  other people (the "More profiles for you" rail). The control that gets
  clicked is matched against the name on the card the detour started from, so
  a rail button is never the one clicked.
- **Lose your place.** Leaving the results page is only safe when coming back
  lands on the same page, which needs `page=N` in the search URL (page 1 works
  without it). Where that is missing, the detour is skipped for that page, with
  a warning, and its Follow-only people are left alone rather than risking a
  restart from page 1. If the results cannot be restored after a detour, the
  run stops instead of paging on from somewhere unknown.
- **Pay for a page LinkedIn has merely stripped.** After a burst of invitations
  LinkedIn starts serving pages where *no* card offers Connect. Before spending
  a detour on each of ten people, such a page is reloaded once — the controls
  usually come straight back.

### Tech-recruiter filter

A people-search for "recruiter" returns every flavour of recruiter — health,
legal, retail, sales — plus people who are not recruiters at all. By default the
bot invites only the ones hiring for **technology**, scoring each card's
headline with [`connecting/domain/tech_recruiter.py`](../src/linkedin_bots/connecting/domain/tech_recruiter.py) before clicking
anything.

Scoring is similarity-based (stdlib `difflib`), so it survives typos, casing,
accents and padding words. A headline scores through one of three routes:

| Route | Example | Score |
|-------|---------|-------|
| **Composite** — one phrase that proves it on its own | `Tech Recruiter \| Recrutamento e seleção` | 1.00 |
| **Co-occurrence** — a recruiting word and a technology word in the *same* segment | `Recrutamento de Desenvolvedores` | 0.90 |
| **Separate segments** — the same two words in different bullets | `Talent Acquisition Specialist \| Technology` | 0.85 |

Segments are the chunks between `|`, `/`, `•`, `,` and `;`, so a technology word
in an unrelated bullet cannot vouch for a recruiting word in another one.
Domain words that mark a *non*-tech specialisation (`saúde`, `jurídico`,
`varejo`, `engenharia civil`, …) subtract a penalty — enough to sink a
borderline match, never enough to sink a clean composite hit, since
`Tech Recruiter | Vendas` still recruits for tech.

Headlines below the threshold are logged with their score and reason and
counted separately in the run summary:

```
Skipping Ana — not a tech recruiter: 'Sales Recruiter' (score 0.00 < 0.80; ...)
Session summary — sent: 42 | failed: 0 | skipped: 11 (of which 9 not tech recruiters)
```

The word lists (`COMPOSITE_TERMS`, `RECRUITER_TERMS`, `TECH_TERMS`,
`NEGATIVE_TERMS`) live at the top of `src/linkedin_bots/connecting/domain/tech_recruiter.py` and are meant
to be edited. After changing them, re-run the tests:

```bash
python -m pytest
```

To turn the filter off for one run, pass `--any-title`.

### Connection-request limits

LinkedIn caps invitations at roughly **100–200 per week**. The bot watches for
two kinds of limit signals and stops or prompts accordingly:

- **"Close to the weekly invitation limit"** — a warning. By default the bot
  prompts you (`Use remaining invites? (y/N)`); `-y` auto-continues.
- **"Reached the weekly invitation limit"** — a hard stop. The bot dismisses the
  dialog and ends the run.
- **HTTP 429** on LinkedIn's invitation endpoint — the quota can be exhausted
  with no on-screen dialog at all. When Chrome performance logging is available
  (see the root README), the bot detects this at the network level and stops.

When the limit is reached mid-run, the bot ends gracefully and prints the
session summary (`sent / failed / skipped`).

### Counting invitations

Every confirmed invitation is appended immediately to `connecting/invites.jsonl`
in the data directory (outside the repository — it holds real contact names;
see [Where data lives](../README.md#where-data-lives)). Because it's written the moment the
invite registers, the count survives a `Ctrl+C`, a crash, or a run at a log
level that hides INFO lines.

Every run — including one you interrupt — ends with the session summary plus
the running weekly total. To check the totals at any time:

```bash
linkedin-bots stats             # invitations per week
linkedin-bots stats --weeks 4   # last 4 weeks only
linkedin-bots stats --backfill  # import past runs from the connecting logs (idempotent)
```

A logging week runs Sunday 21:00 → Sunday 21:00 (America/São_Paulo), matching
the weekly log filenames.

### How it works (implementation notes)

These details matter if you need to adapt the bot to LinkedIn UI changes — the
selectors live in [`connecting/adapters/selenium/`](../src/linkedin_bots/connecting/adapters/selenium/).

- **Layers.** `domain/` holds the pure rules — names in labels, the
  tech-recruiter score, the stripped-page rule; `application/send_invitations.py`
  walks the pages and takes the detours over ports; `adapters/` hold the Page
  Objects (search results, profile, invite modal, limit guard) and the invite ledger.
- **Scanning a page of results.** The results are a virtualized `LazyColumn`
  inside the app shell's own scroll container — the document itself does not
  scroll, so `window.scrollTo` moves nothing (see
  [`shared/infrastructure/scrolling.py`](../src/linkedin_bots/shared/infrastructure/scrolling.py)). The scan drives that inner
  container from top to bottom, re-scanning as rows mount, and only calls a
  page finished once the list stops growing. A page whose cards all offer
  Follow or Message is reported with its breakdown
  (`10 result(s), 0 connectable (7 follow-only, 3 message-only)`) so a page
  with nobody to invite is never confused with a page the bot failed to read.
- **Pages that come back empty.** After a burst of invitations LinkedIn starts
  serving result pages where no card offers Connect at all. Before accepting
  that verdict the bot reloads the page once — `page=N` in the search URL
  means the reload lands back where it was — and rescans. A page that renders
  no cards at all is also reloaded, and if it stays empty the run stops rather
  than paging past people it never saw.
- **Shadow DOM modal.** LinkedIn renders the invite modal inside an open Shadow
  DOM host (`#interop-outlet`). Selenium's XPath can't reach into shadow roots,
  so every modal interaction (Add a note, the textarea, Send) goes through
  `get_modal_shadow_root()` using **CSS selectors only**.
- **Trusted clicks.** LinkedIn ignores synthetic clicks for some controls, so
  `_robust_click()` tries, in order: native `.click()` → ActionChains → a
  Chrome DevTools Protocol mouse event (`isTrusted=true`, works inside shadow
  DOM) → a JavaScript `.click()` fallback.
- **Emoji-safe typing.** ChromeDriver's `send_keys` chokes on non-BMP characters
  (emoji). `fill_message_box()` types the plain part first to activate
  LinkedIn's input binding, then injects the full text via the native value
  setter and fires `input`/`change` events.
- **Name extraction.** The first name for `{name}` is pulled from the
  `Invite <Full Name> to connect` aria-label, with fallbacks that read the modal
  body and the surrounding profile card. Compound Brazilian first names are
  preserved (see [`shared/domain/names.py`](../src/linkedin_bots/shared/domain/names.py)).
- **"Enter their email to connect" screen.** Some profiles require an email to
  invite; the bot detects this, cancels, and skips the person.
- **The profile detour.** Follow-only people are reached through their profile
  page (see [above](#reaching-people-who-only-offer-follow)). The Connect
  control there is found by name — on the page or inside the **More** menu,
  light DOM or shadow DOM, on whatever tag carries the label — because the
  page also carries Connect buttons for other people. Where nothing matches
  the name, the Connect item of the open menu is taken instead (by its label,
  or failing that by its text): inside that person's own menu there is only
  one person it can mean. Both routes into the invite modal share one implementation
  (`SeleniumInviteModal.complete()`), so the note, the Send, the confirmation and the
  ledger behave identically whichever way the modal was opened.

#### Reference HTML

[`tests/fixtures/connecting/`](../tests/fixtures/connecting/) holds saved LinkedIn HTML snippets (the invite
modal, note modal, email-input screen, follow-person card, a full profile page,
that profile's open **More** menu, old/new search-results containers) used as
fixtures when updating selectors.
`tests/connecting/adapters/test_saved_markup.py` runs the Follow, More and Connect
selectors against those files (lxml, in the dev extra, makes them run rather than skip), so a LinkedIn markup change shows up as a failing test
rather than as a silent run that invites nobody.

## Português (Brasil)

Percorre os **resultados da busca de pessoas** do LinkedIn e envia convites de
conexão personalizados, página por página, até acabarem os resultados ou
atingir o limite semanal de convites do LinkedIn.

> Veja o [README principal](../README.md#português-brasil) para a configuração única
> (conectar o Chrome, instalar as dependências) e as convenções comuns aos dois
> bots.

### O que ele faz

A partir de uma aba aberta de **resultados da busca de pessoas**
(`linkedin.com/search/results/people/…`), o bot:

1. Encontra a aba da busca de pessoas entre as abas abertas do Chrome (ou, na
   falta dela, qualquer aba de resultados de busca, e por fim a aba atual).
2. Em cada página de resultados, rola a lista para carregar todos os cards e
   percorre as pessoas de cima para baixo.
3. Lê o título (headline) de cada pessoa no próprio card e pula quem não é
   recrutador de **tecnologia** — veja
   [Filtro de recrutador tech](#filtro-de-recrutador-tech). Cards pulados
   nunca são clicados, então não gastam nada da sua cota semanal de convites.
4. Abre o modal de convite para cada pessoa restante — pelo controle
   **"Invite … to connect"** do card ou, quando o card só oferece **Follow**,
   pela página de perfil da pessoa (veja
   [Alcançando quem só oferece Follow](#alcançando-quem-só-oferece-follow))
   — e então:
   - clica em **Add a note**, digita uma mensagem personalizada e clica em
     **Send invitation**; ou
   - clica em **Send without a note** (quando rodado com `-n`).
5. Confere se o convite foi registrado (o controle Connect vira **Pending**) e
   avança de página (ou volta, com `-r`) e repete.

O texto da mensagem vem de um template em [`src/linkedin_bots/connecting/templates/`](../src/linkedin_bots/connecting/templates/).
`{name}` é trocado pelo primeiro nome do contato; veja
[Templates](../README.md#templates-1) no README principal para o formato.

### Uso

```bash
linkedin-bots connect                       # template padrão, nota personalizada
linkedin-bots connect -m message_english.txt # convite em inglês
linkedin-bots connect -n                    # envia convites sem nota
linkedin-bots connect -y -l INFO            # segue além do aviso automaticamente, com menos log
linkedin-bots connect -r                    # navega para trás (Previous em vez de Next)
linkedin-bots connect --max 80              # para depois de 80 convites enviados
linkedin-bots connect --any-title           # convida todo recrutador, não só os de tech
linkedin-bots connect --title-score 0.9     # filtro de recrutador tech mais rígido
linkedin-bots connect -f                    # rápido: pausas mínimas entre convites
```

#### Opções

| Flag | Padrão | Significado |
|------|--------|-------------|
| `-m`, `--message ARQUIVO` | `message.txt` | Arquivo de template. Um nome de arquivo sozinho é procurado na sua pasta de templates (veja [Templates](../README.md#templates-1)) e depois em `src/linkedin_bots/connecting/templates/`; um caminho é usado como está. Um arquivo que não existe interrompe a execução (a menos que `-n` o torne irrelevante). |
| `-n`, `--no-message` | desligado | Envia convites **sem** nota (clica em "Send without a note"). |
| `-r`, `--reverse` | desligado | Navega pelos resultados ao contrário (clica em **Previous** em vez de **Next**). |
| `-y`, `--yes` | desligado | Segue automaticamente além do aviso "close to the weekly invitation limit", em vez de perguntar. |
| `--max N` | ilimitado | Para depois de enviar `N` convites (limite de estrago, independente do teto semanal do próprio LinkedIn). |
| `--any-title` | desligado | Convida **todo** recrutador, pulando o filtro de título de recrutador tech. |
| `--title-score S` | `0.80` | Pontuação mínima de similaridade de recrutador tech (`0.0`–`1.0`). Aumente para ser mais rígido, diminua para ser mais permissivo. |
| `-f`, `--fast` | desligado | Reduz as pausas aleatórias ao mínimo — veja [Ritmo](#ritmo). |
| `-l`, `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARN` ou `ERROR`. |

### Ritmo

Entre uma ação e outra o bot espera um intervalo aleatório, para que o ritmo
não pareça de um script: 2–5 s antes de abrir um modal de convite, 8–18 s
depois de cada convite, 12–25 s entre páginas de resultados.

`-f` / `--fast` mantém a mesma aleatoriedade, mas reduz cada uma dessas janelas
a um décimo, com piso de 0,5 s (`FAST_PAUSE_FACTOR` / `MIN_FAST_PAUSE` em
[`shared/infrastructure/pacing.py`](../src/linkedin_bots/shared/infrastructure/pacing.py)) — cerca de 0,5 s, 0,8–1,8 s e 1,2–2,5 s. O piso
existe porque a interface do LinkedIn ainda precisa de um instante para se
acomodar entre cliques.

Esperas fixas que servem para a página renderizar (o modal abrindo, uma página
carregando) não mudam — `--fast` só mexe nas pausas que imitam uma pessoa. Use
para execuções curtas ou de teste; uma execução inteira nesse ritmo é um padrão
de automação bem mais óbvio, e o teto semanal de convites do LinkedIn vale do
mesmo jeito.

### Alcançando quem só oferece Follow

O LinkedIn vem diminuindo cada vez mais quantos resultados de busca oferecem
**Connect**. Um card que só oferece **Follow** não pode ser convidado pela
lista de resultados — mas a pessoa por trás dele ainda pode ser convidada pelo
próprio perfil, onde o Connect fica atrás do menu de três pontos **More**.

Isso não é um modo separado: é uma única passada pela página, e cada pessoa é
convidada do jeito que o próprio card permite. Onde o card tem um controle
Connect, ele é clicado ali mesmo. Onde só tem Follow, o bot:

1. Pontua o título primeiro, como sempre. Quem não passa no
   [filtro de recrutador tech](#filtro-de-recrutador-tech) nunca custa o
   carregamento de uma página.
2. Abre o perfil da pessoa (`linkedin.com/in/…`, lido do link da própria pessoa
   no card — não do de uma conexão em comum).
3. Usa o controle Connect do perfil, se houver; senão abre o menu **More** e
   pega o Connect de lá. O item do menu rotula a *div interna*, não o link em
   volta dela, então a busca aceita qualquer tag e depois clica no
   `<a href="/preload/custom-invite/…">` que a envolve.
4. Segue o mesmo ritual do modal: **Add a note**, a mensagem personalizada,
   **Send invitation**, depois a checagem de confirmação e o registro no
   histórico.
5. **Volta** para os resultados, que continuam a partir da pessoa recém-tratada.
   Todo mundo já processado naquela página é lembrado pelo rótulo do card,
   então ninguém é convidado duas vezes.

O resumo da sessão informa quantos convites fizeram o caminho mais longo:

```
Session summary — sent: 34 (of which 9 via the profile detour) | failed: 0 | skipped: 12
```

**Quanto custa.** Dois carregamentos de página por pessoa que só oferece Follow,
mais a pausa habitual de 8–18 s, então uma página cheia delas leva minutos em
vez de segundos. Gasta a mesma cota semanal de convites que qualquer outro
convite — o desvio alcança *mais pessoas*, não mais convites.

**Três coisas que ele se recusa a fazer:**

- **Convidar a pessoa errada.** Uma página de perfil também mostra botões
  Connect de outras pessoas (a faixa "More profiles for you"). O controle
  clicado é comparado com o nome do card de onde o desvio partiu, então um
  botão da faixa nunca é o clicado.
- **Perder o lugar.** Sair da página de resultados só é seguro quando voltar
  cai na mesma página, o que exige `page=N` na URL da busca (a página 1
  funciona sem). Onde isso falta, o desvio é pulado naquela página, com um
  aviso, e as pessoas que só oferecem Follow ficam de fora, em vez de arriscar
  recomeçar da página 1. Se os resultados não puderem ser restaurados depois de
  um desvio, a execução para em vez de seguir paginando a partir de um ponto
  desconhecido.
- **Pagar por uma página que o LinkedIn só esvaziou.** Depois de uma rajada de
  convites, o LinkedIn passa a servir páginas em que *nenhum* card oferece
  Connect. Antes de gastar um desvio com cada uma de dez pessoas, uma página
  assim é recarregada uma vez — os controles costumam voltar na hora.

### Filtro de recrutador tech

Uma busca de pessoas por "recruiter" traz todo tipo de recrutador — saúde,
jurídico, varejo, vendas — e ainda pessoas que nem são recrutadoras. Por padrão
o bot convida só quem contrata para **tecnologia**, pontuando o título de cada
card com [`connecting/domain/tech_recruiter.py`](../src/linkedin_bots/connecting/domain/tech_recruiter.py) antes de clicar em
qualquer coisa.

A pontuação é baseada em similaridade (`difflib`, da biblioteca padrão), então
resiste a erros de digitação, maiúsculas/minúsculas, acentos e palavras de
enchimento. Um título pontua por um de três caminhos:

| Caminho | Exemplo | Pontuação |
|---------|---------|-----------|
| **Composto** — uma expressão que prova sozinha | `Tech Recruiter \| Recrutamento e seleção` | 1.00 |
| **Coocorrência** — uma palavra de recrutamento e uma de tecnologia no *mesmo* segmento | `Recrutamento de Desenvolvedores` | 0.90 |
| **Segmentos separados** — as mesmas duas palavras em tópicos diferentes | `Talent Acquisition Specialist \| Technology` | 0.85 |

Segmentos são os trechos entre `|`, `/`, `•`, `,` e `;`, então uma palavra de
tecnologia num tópico sem relação não serve de aval para uma palavra de
recrutamento em outro. Palavras de domínio que marcam uma especialização *não*
tech (`saúde`, `jurídico`, `varejo`, `engenharia civil`, …) aplicam uma
penalidade — suficiente para derrubar um caso no limite, nunca para derrubar um
acerto composto limpo, já que `Tech Recruiter | Vendas` continua recrutando
para tech.

Títulos abaixo do limite são registrados no log com a pontuação e o motivo, e
contados à parte no resumo da execução:

```
Skipping Ana — not a tech recruiter: 'Sales Recruiter' (score 0.00 < 0.80; ...)
Session summary — sent: 42 | failed: 0 | skipped: 11 (of which 9 not tech recruiters)
```

As listas de palavras (`COMPOSITE_TERMS`, `RECRUITER_TERMS`, `TECH_TERMS`,
`NEGATIVE_TERMS`) ficam no topo de `src/linkedin_bots/connecting/domain/tech_recruiter.py` e foram feitas
para serem editadas. Depois de mudá-las, rode os testes de novo:

```bash
python -m pytest
```

Para desligar o filtro numa execução, passe `--any-title`.

### Limites de convites de conexão

O LinkedIn limita os convites a cerca de **100–200 por semana**. O bot fica de
olho em dois tipos de sinal de limite e para ou pergunta conforme o caso:

- **"Close to the weekly invitation limit"** — um aviso. Por padrão o bot
  pergunta (`Use remaining invites? (y/N)`); `-y` segue automaticamente.
- **"Reached the weekly invitation limit"** — uma parada definitiva. O bot
  fecha o diálogo e encerra a execução.
- **HTTP 429** no endpoint de convites do LinkedIn — a cota pode se esgotar sem
  nenhum diálogo na tela. Quando o log de desempenho do Chrome está disponível
  (veja o README principal), o bot detecta isso no nível da rede e para.

Quando o limite é atingido no meio da execução, o bot encerra de forma limpa e
mostra o resumo da sessão (`sent / failed / skipped`).

### Contagem de convites

Todo convite confirmado é gravado na hora em `connecting/invites.jsonl`,
na pasta de dados (fora do repositório — guarda nomes reais de contatos;
veja [Onde ficam os dados](../README.md#onde-ficam-os-dados)). Como é gravado no
instante em que o convite é registrado, a contagem sobrevive a um `Ctrl+C`, a
uma falha ou a uma execução num nível de log que esconde as linhas INFO.

Toda execução — inclusive uma que você interrompe — termina com o resumo da
sessão mais o total semanal acumulado. Para ver os totais a qualquer momento:

```bash
linkedin-bots stats             # convites por semana
linkedin-bots stats --weeks 4   # só as últimas 4 semanas
linkedin-bots stats --backfill  # importa execuções passadas dos logs do connecting (idempotente)
```

Uma semana de log vai de domingo 21:00 → domingo 21:00 (America/São_Paulo),
batendo com os nomes dos arquivos de log semanais.

### Como funciona (notas de implementação)

Estes detalhes importam se você precisar adaptar o bot a mudanças na interface
do LinkedIn — os seletores ficam em [`connecting/adapters/selenium/`](../src/linkedin_bots/connecting/adapters/selenium/).

- **Camadas.** `domain/` guarda as regras puras — nomes nos rótulos, a pontuação
  de recrutador tech, a regra da página esvaziada; `application/send_invitations.py`
  percorre as páginas e faz os desvios por portas; `adapters/` guarda os Page
  Objects (resultados da busca, perfil, modal de convite, limites) e o registro
  de convites.
- **Varrendo uma página de resultados.** Os resultados são uma `LazyColumn`
  virtualizada dentro do próprio contêiner de rolagem do app — o documento em
  si não rola, então `window.scrollTo` não move nada (veja
  [`shared/infrastructure/scrolling.py`](../src/linkedin_bots/shared/infrastructure/scrolling.py)). A varredura move esse
  contêiner interno de cima a baixo, varrendo de novo à medida que as linhas
  aparecem, e só dá a página por terminada quando a lista para de crescer. Uma
  página cujos cards oferecem só Follow ou Message é informada com o detalhamento
  (`10 result(s), 0 connectable (7 follow-only, 3 message-only)`), para que uma
  página sem ninguém para convidar nunca seja confundida com uma página que o
  bot não conseguiu ler.
- **Páginas que voltam vazias.** Depois de uma rajada de convites, o LinkedIn
  passa a servir páginas de resultados em que nenhum card oferece Connect.
  Antes de aceitar esse veredito, o bot recarrega a página uma vez — `page=N`
  na URL da busca faz o reload cair de volta no mesmo lugar — e varre de novo.
  Uma página que não renderiza card nenhum também é recarregada e, se continuar
  vazia, a execução para em vez de passar por pessoas que o bot nunca viu.
- **Modal no Shadow DOM.** O LinkedIn renderiza o modal de convite dentro de um
  host de Shadow DOM aberto (`#interop-outlet`). O XPath do Selenium não
  alcança shadow roots, então toda interação com o modal (Add a note, a área de
  texto, Send) passa por `get_modal_shadow_root()` usando **apenas seletores
  CSS**.
- **Cliques confiáveis.** O LinkedIn ignora cliques sintéticos em alguns
  controles, então `_robust_click()` tenta, em ordem: `.click()` nativo →
  ActionChains → um evento de mouse via Chrome DevTools Protocol
  (`isTrusted=true`, funciona dentro do shadow DOM) → um `.click()` em
  JavaScript como último recurso.
- **Digitação segura para emoji.** O `send_keys` do ChromeDriver engasga com
  caracteres fora do BMP (emoji). `fill_message_box()` digita primeiro a parte
  simples para ativar o binding de entrada do LinkedIn, depois injeta o texto
  completo pelo setter nativo de value e dispara os eventos `input`/`change`.
- **Extração do nome.** O primeiro nome para `{name}` sai do aria-label
  `Invite <Nome Completo> to connect`, com alternativas que leem o corpo do
  modal e o card de perfil em volta. Primeiros nomes compostos brasileiros são
  preservados (veja [`shared/domain/names.py`](../src/linkedin_bots/shared/domain/names.py)).
- **Tela "Enter their email to connect".** Alguns perfis exigem um e-mail para
  convidar; o bot detecta isso, cancela e pula a pessoa.
- **O desvio pelo perfil.** Quem só oferece Follow é alcançado pela página de
  perfil (veja [acima](#alcançando-quem-só-oferece-follow)). O controle Connect
  ali é encontrado pelo nome — na página ou dentro do menu **More**, no DOM
  normal ou no shadow DOM, em qualquer tag que carregue o rótulo — porque a
  página também traz botões Connect de outras pessoas. Quando nada bate com o
  nome, o item Connect do menu aberto é usado (pelo rótulo ou, na falta dele,
  pelo texto): dentro do menu da própria pessoa só existe uma pessoa a quem ele
  pode se referir. Os dois caminhos até o modal de convite compartilham uma
  única implementação (`SeleniumInviteModal.complete()`), então a nota, o Send, a
  confirmação e o registro se comportam igual, seja qual for o jeito como o
  modal foi aberto.

#### HTML de referência

[`tests/fixtures/connecting/`](../tests/fixtures/connecting/) guarda trechos de HTML do LinkedIn salvos (o
modal de convite, o modal de nota, a tela de e-mail, o card de quem só oferece
Follow, uma página de perfil completa, o menu **More** aberto desse perfil, os
contêineres antigo/novo dos resultados de busca) usados como fixtures ao
atualizar seletores. `tests/connecting/adapters/test_saved_markup.py` roda os
seletores de Follow, More e Connect contra esses arquivos (o lxml, no extra de
desenvolvimento, faz com que rodem em vez de serem pulados), então uma mudança no markup do
LinkedIn aparece como um teste falhando, e não como uma execução silenciosa que
não convida ninguém.
