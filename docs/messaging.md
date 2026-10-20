# Message bot

[English](#english) | [Português (Brasil)](#português-brasil)

## English

Walks your LinkedIn **Messaging** inbox (`linkedin.com/messaging`) newest-first
and sends a personalized follow-up to each existing conversation.

> See the [root README](../README.md) for the one-time setup (attaching Chrome,
> installing dependencies) and the conventions shared by both bots.

### What it does

Starting from an open **Messaging** tab, the bot:

1. Finds the messaging tab among your open Chrome tabs (falling back to the
   current tab).
2. Determines where to start (see [Where it starts](#where-it-starts) below).
3. Walks the conversation list **strictly in one direction, one card at a
   time** — downward (newer→older) by default, or upward (older→newer) with
   `-r`/`--reverse`. The next contact is always the adjacent card in that
   direction, never a rescan from the top. For each card it:
   - skips **Sponsored**, **InMail**, and **LinkedIn Offer** cards (identified
     by their pill label);
   - skips anyone already recorded in the send history;
   - optionally stops once a conversation crosses `--date-limit` (older than
     it going down, newer than it going up with `-r`);
   - opens the thread, types a personalized message into the compose box, and
     sends it.
4. Lazy-loads more conversations (by focusing the last card) until it reaches
   the bottom of the list (or hits `--max`). No lazy-loading is needed walking
   upward with `-r` — every card above the start point is already loaded.

Sending a message makes that conversation jump to the top of the list, so the
bot captures the *next* card **before** sending. That is what keeps the walk
anchored: nothing after the send is ever computed relative to the top of the
list, so already-messaged contacts up there can never become targets again.

The message text comes from a template in [`src/linkedin_bots/messaging/templates/`](../src/linkedin_bots/messaging/templates/).
`{name}` is replaced with the contact's first name. Unlike the connect bot,
direct messages have **no 300-character cap**, so templates are never truncated.
See [Templates](../README.md#templates) in the root README for the format.

The shipped templates are generic: one follow-up and one re-approach per
language, for recruiters and for developers, plus a hired notice for recruiters. Your own templates win over them by name (see
[Templates](../README.md#templates)).

| Template | Language | Use |
|----------|----------|-----|
| `message.txt` (default) | Portuguese | follow-up after an accepted invitation |
| `message_english.txt` | English | follow-up |
| `reconnect.txt` | Portuguese | re-approaching an old contact |
| `reconnect_english.txt` | English | re-approaching |
| `message_hired.txt` | Portuguese | telling recruiters you've been hired — no job-search pitch |
| `message_hired_english.txt` | English | telling recruiters you've been hired |
| `dev_message.txt` | Portuguese | follow-up for a developer met through `connect --java-devs` |
| `dev_message_english.txt` | English | follow-up for a developer |
| `dev_reconnect.txt` | Portuguese | re-approaching an old developer contact |
| `dev_reconnect_english.txt` | English | re-approaching a developer |

### Usage

```bash
linkedin-bots message                        # default template, whole inbox
linkedin-bots message --dry-run              # preview who/what — sends nothing
linkedin-bots message --max 10               # stop after 10 messages
linkedin-bots message --date-limit 2025/12/31  # stop at conversations older than this
linkedin-bots message --start-date 2025/07/30  # scroll down to this date and start there
linkedin-bots message -m reconnect.txt --max 5 --dry-run
linkedin-bots message -m dev_message.txt --max 10   # follow up with developers
linkedin-bots message -r -m reconnect_english.txt --date-limit 2024/10/20
    # click an old conversation first, then walk upward (older→newer),
    # stopping once a conversation is newer than the date limit
linkedin-bots message --last-message-regex ".*há 7.*" \
    --last-message-regex-custom ".*for 7.*" message_english.txt
    # Portuguese previews get message.txt, English ones message_english.txt
```

#### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `-m`, `--message FILE` | `message.txt` | Template file. A bare filename is looked up in your own templates folder, then in `src/linkedin_bots/messaging/templates/`; a path is used as-is. A file that doesn't exist stops the run. |
| `--date-limit YYYY/MM/DD` | none | Stop when a conversation is older than this date (or, with `-r`/`--reverse`, newer than this date). |
| `--start-date YYYY/MM/DD` | none | Scroll down the list (lazy-loading as needed), click the **first conversation dated on or before** this date, and start sending from there, inclusive. If no such conversation exists, the run ends without sending. |
| `-r`, `--reverse` | off | Walk the list **upward** (older → newer) instead of downward. Also flips `--date-limit` to mean "stop once a conversation is newer than this date." Useful for working through very old contacts from the bottom of the inbox up. |
| `--dry-run` | off | Log who would be messaged and the first line of the text, without opening threads or sending anything. |
| `--max N` | unlimited | Stop after sending `N` messages (a blast-radius cap). |
| `--last-message-regex REGEX` | none | Only message conversations whose last-message preview matches `REGEX`; they get the `-m` template. See [Routing by last message](#routing-by-last-message). |
| `--last-message-regex-custom REGEX FILE` | none | Send `FILE` instead of the `-m` template to conversations matching `REGEX`. Repeatable. |
| `--by-title` | off | Read each contact's headline and send the recruiter (base), `dev_` or `generic_` variant of the template. Opens every conversation, also in `--dry-run`. See [Routing by title](#routing-by-title). |
| `-l`, `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARN`, or `ERROR`. |

### Routing by last message

Each conversation card shows a preview of its last message, and that preview
can decide **whether** a card gets messaged and **which** template it gets.

- `--last-message-regex REGEX` — only cards whose preview matches are messaged,
  using the `-m` template (default `message.txt`).
- `--last-message-regex-custom REGEX FILE` — cards matching `REGEX` get `FILE`
  instead. Pass it as many times as you have templates.

```bash
linkedin-bots message --last-message-regex ".*há 7.*" \
    --last-message-regex-custom ".*for 7.*" message_english.txt
```

That run messages a contact whose preview says "há 7 anos" with `message.txt`,
one whose preview says "for 7 years" with `message_english.txt`, and skips
everyone else — a way to answer in whichever language the thread is already in.

Rules are evaluated **in order: the custom ones first (in the order given),
then `--last-message-regex` as the fallback**, and the first match wins. So a
broad `--last-message-regex` can never steal a card from a specific custom
rule; among custom rules, put the most specific pattern first.

Used **alone**, `--last-message-regex-custom` still filters: cards matching
none of the patterns are skipped. With neither flag, every card gets the `-m`
template as before.

Both flags take Python regular expressions, matched with `re.search` against
the preview text (so no need to anchor them). Every pattern is compiled and
every template file checked at startup — a bad regex or a filename typo stops
the run before the first thread is opened, rather than silently falling back to
generic text. Bare filenames are looked up as for `-m`: your own templates folder first, then
`src/linkedin_bots/messaging/templates/`.

A card whose preview LinkedIn hasn't rendered (occluded cards are emptied by
its virtualized list) matches nothing and is skipped, so `--dry-run` is worth a
pass before a real run: it logs each contact with the template that would be
used.

### Routing by title

With `--by-title`, the bot also reads who each contact is. It opens the
conversation, reads the headline on the profile card at the start of the
history, and sends one of three variants of the template the run already
picked (by `-m` or by the last-message rules, so the language is unchanged):

| Headline | Gets | Example (`-m message_english.txt`) |
|----------|------|------------------------------------|
| any recruiting term ("Tech Recruiter", "Talent Acquisition", "Recrutadora") | the base file | `message_english.txt` |
| someone who writes code (developer, software engineer, front/back end, full stack, mobile, tech lead, software architect) | `dev_` + base | `dev_message_english.txt` |
| everyone else (managers, CTOs, HR, QA, data, DevOps) | `generic_` + base | `generic_message_english.txt` |

Recruiting wins: "Tech Recruiter | Hiring Developers" is a recruiter. Students,
interns and trainees with a dev role in their headline are devs.

A contact whose headline can't be read is skipped, not sent a guess. They stay
out of the send history, so a later run tries them again.

The siblings are looked up like the base file, one by one: your own templates
folder first, then the shipped ones. When a sibling doesn't exist (there is no
`generic_reconnect.txt`, say), that audience gets the base file, and the run
says so once at startup.

Each contact's line in the log shows the headline, the audience and the file
used; the run ends with a count per audience and how many headlines could
not be read (and were skipped). If LinkedIn changes the profile card, everyone
is skipped: that count is where it shows.

`--dry-run --by-title` opens every conversation to read the headline, so it is
slower than a plain dry run and marks unread conversations as read. It still
never types anything.

### Where it starts

- **No conversation open** → starts from the top of the list (most recent), or
  the bottom (oldest) when `-r`/`--reverse` is given.
- **A conversation already open** (you clicked one before launching) → starts
  **from that conversation, inclusive**, and continues in the walk direction
  (downward by default, upward with `-r`). Every card on the other side of the
  active one is skipped. This lets you resume from a known point, e.g. click
  the oldest conversation in your inbox and run with `-r` to work upward
  through old contacts.
- **`--start-date` given** → the bot scrolls the list itself (focusing the last
  card to trigger lazy-loading, since plain scrolling doesn't reliably load
  more) until it finds the first conversation dated on or before that date,
  clicks it, and starts from there — same as if you had clicked it manually.
  This works the same way regardless of `-r`, since it only affects where the
  walk *starts*, not which direction it goes afterward.

Every contact a message is confirmed sent to is also recorded in
`messaging/sent_history.json` in the data directory (see
[Where data lives](../README.md#where-data-lives)). The conversation list re-sorts by
recent activity — a reply, or any other conversation getting activity — so it
isn't append-only between runs. The history is loaded on startup and used as a
skip check while walking, so someone already messaged in an earlier run is
never re-messaged even if they end up *below* wherever you resume. It is only
ever used to *skip* a card — navigation itself is purely "the next card down".

Two people can share a name, so each send also records the contact's photo ID
(the asset ID in the photo URL's path) and the conversation's thread ID. A card
whose name is in the history is skipped when its photo matches a recorded one;
otherwise its conversation is opened and skipped if it is a recorded thread.
Older entries hold only a name: a card counts as someone else only when its
last activity is newer than that send.

If the history file exists but cannot be read, the run stops before touching
any conversation instead of treating it as empty — an empty history would make
everyone in it look new. Writes go through a temporary file, so a crash cannot
leave it half-written, and a message that was sent but could not be recorded
(say, another program holds the file) stops the run, so no one is messaged twice.

### Date parsing

The `--date-limit` and `--start-date` checks rely on parsing LinkedIn's
conversation-card timestamps, which come in several formats. `parse_card_timestamp()` in
[`messaging/domain/card_date.py`](../src/linkedin_bots/messaging/domain/card_date.py) handles:

| Card shows | Interpreted as |
|------------|----------------|
| `10:01 PM` / `9:12 AM` | today |
| `Mon`, `Tue`, … | most recent past occurrence (last 7 days) |
| `Jun 27` | that day, this year (or last year if it's in the future) |
| `Jun 27, 2024` | explicit day + year |
| `Mar 2024` | the 1st of that month |
| anything else | unknown → treated as within range (does **not** stop the run) |

### How it works (implementation notes)

These details matter if you need to adapt the bot to LinkedIn UI changes — the
selectors live in [`messaging/adapters/selenium/`](../src/linkedin_bots/messaging/adapters/selenium/).

- **Layers.** `domain/` holds the pure rules — card dates, same-name contacts,
  template routing and `assess()`, the verdict for one card;
  `application/send_follow_ups.py` walks the list over ports; `adapters/` hold
  the Selenium Page Objects and the history file.
- **Send-on-Enter compose box.** LinkedIn's DM box is a `contenteditable` div
  that sends on Enter, so `send_keys` can't be used for multi-line text.
  `_insert_text()` injects the whole body (newlines as soft-breaks) in one
  atomic `execCommand('insertText')`, with an `innerText`-setter fallback.
- **Send + verification.** After inserting, the bot presses a trusted Enter; if
  the box doesn't clear it falls back to clicking the **Send** button. A send is
  considered successful only once the compose box is empty again.
- **Trusted clicks.** Conversation cards are opened with the same
  native → ActionChains → CDP → JS click ladder used by the connect bot.
- **Skip pills.** Sponsored ads, InMails, and LinkedIn Offers share the same
  pill component; the bot matches on the pill text
  (`sponsored` / `inmail` / `linkedin offer`) and skips those cards.

### Design docs

- [`design/messaging-bot.spec.md`](design/messaging-bot.spec.md) — the original spec
  (starting HTML and desired behavior).
- [`design/message-by-title.spec.md`](design/message-by-title.spec.md) — routing by
  title (`--by-title`).

## Português (Brasil)

Percorre a caixa de entrada do **Messaging** do LinkedIn (`linkedin.com/messaging`)
da mais recente para a mais antiga e envia uma mensagem de acompanhamento
personalizada para cada conversa existente.

> Veja o [README principal](../README.md#português-brasil) para a configuração única
> (conectar o Chrome, instalar as dependências) e as convenções comuns aos dois
> bots.

### O que ele faz

A partir de uma aba aberta do **Messaging**, o bot:

1. Encontra a aba do Messaging entre as abas abertas do Chrome (ou usa a aba
   atual).
2. Decide por onde começar (veja [Onde ele começa](#onde-ele-começa) abaixo).
3. Percorre a lista de conversas **estritamente numa direção, um card por
   vez** — para baixo (mais nova→mais antiga) por padrão, ou para cima (mais
   antiga→mais nova) com `-r`/`--reverse`. O próximo contato é sempre o card
   vizinho naquela direção, nunca uma nova varredura a partir do topo. Para
   cada card, ele:
   - pula cards **Sponsored**, **InMail** e **LinkedIn Offer** (identificados
     pela etiqueta, o "pill");
   - pula quem já está registrado no histórico de envios;
   - opcionalmente para quando uma conversa ultrapassa `--date-limit` (mais
     antiga que ele indo para baixo, mais nova indo para cima com `-r`);
   - abre a conversa, digita uma mensagem personalizada na caixa de texto e a
     envia.
4. Carrega mais conversas (focando o último card) até chegar ao fim da lista
   (ou atingir `--max`). Indo para cima com `-r` não é preciso carregar mais —
   todo card acima do ponto de partida já está carregado.

Enviar uma mensagem faz aquela conversa pular para o topo da lista, então o bot
guarda o *próximo* card **antes** de enviar. É isso que mantém a caminhada
ancorada: nada depois do envio é calculado em relação ao topo da lista, então
os contatos que já receberam mensagem e estão lá em cima nunca voltam a ser
alvo.

O texto da mensagem vem de um template em [`src/linkedin_bots/messaging/templates/`](../src/linkedin_bots/messaging/templates/).
`{name}` é trocado pelo primeiro nome do contato. Diferente do bot connect,
mensagens diretas **não têm limite de 300 caracteres**, então os templates
nunca são cortados. Veja [Templates](../README.md#templates-1) no README
principal para o formato.

Os templates distribuídos são genéricos: um de acompanhamento e um de
reabordagem por idioma, para recrutadores e para devs, mais um aviso de contratação para recrutadores. Seus próprios templates têm prioridade sobre eles pelo
nome (veja [Templates](../README.md#templates-1)).

| Template | Idioma | Uso |
|----------|--------|-----|
| `message.txt` (padrão) | português | acompanhamento depois de um convite aceito |
| `message_english.txt` | inglês | acompanhamento |
| `reconnect.txt` | português | reabordar um contato antigo |
| `reconnect_english.txt` | inglês | reabordagem |
| `message_hired.txt` | português | avisar recrutadores que você foi contratado — sem pedir vaga |
| `message_hired_english.txt` | inglês | avisar recrutadores que você foi contratado |
| `dev_message.txt` | português | acompanhamento para um dev conectado via `connect --java-devs` |
| `dev_message_english.txt` | inglês | acompanhamento para um dev |
| `dev_reconnect.txt` | português | reabordar um contato dev antigo |
| `dev_reconnect_english.txt` | inglês | reabordagem de um dev |

### Uso

```bash
linkedin-bots message                        # template padrão, caixa de entrada inteira
linkedin-bots message --dry-run              # mostra quem/o quê — não envia nada
linkedin-bots message --max 10               # para depois de 10 mensagens
linkedin-bots message --date-limit 2025/12/31  # para nas conversas mais antigas que esta data
linkedin-bots message --start-date 2025/07/30  # rola até esta data e começa por ali
linkedin-bots message -m reconnect.txt --max 5 --dry-run
linkedin-bots message -m dev_message.txt --max 10   # acompanhamento com devs
linkedin-bots message -r -m reconnect_english.txt --date-limit 2024/10/20
    # clique antes numa conversa antiga, depois caminhe para cima (mais antiga→mais nova),
    # parando quando uma conversa for mais nova que a data limite
linkedin-bots message --last-message-regex ".*há 7.*" \
    --last-message-regex-custom ".*for 7.*" message_english.txt
    # prévias em português recebem message.txt, as em inglês message_english.txt
```

#### Opções

| Flag | Padrão | Significado |
|------|--------|-------------|
| `-m`, `--message ARQUIVO` | `message.txt` | Arquivo de template. Um nome de arquivo sozinho é procurado na sua pasta de templates e depois em `src/linkedin_bots/messaging/templates/`; um caminho é usado como está. Um arquivo que não existe interrompe a execução. |
| `--date-limit AAAA/MM/DD` | nenhum | Para quando uma conversa for mais antiga que esta data (ou, com `-r`/`--reverse`, mais nova que esta data). |
| `--start-date AAAA/MM/DD` | nenhum | Rola a lista para baixo (carregando mais conforme preciso), clica na **primeira conversa com data igual ou anterior** a esta e começa a enviar a partir dela, inclusive. Se não existir conversa assim, a execução termina sem enviar. |
| `-r`, `--reverse` | desligado | Percorre a lista **para cima** (mais antiga → mais nova) em vez de para baixo. Também inverte `--date-limit`, que passa a significar "parar quando uma conversa for mais nova que esta data". Útil para trabalhar contatos muito antigos, do fim da caixa de entrada para cima. |
| `--dry-run` | desligado | Registra no log quem receberia mensagem e a primeira linha do texto, sem abrir conversas nem enviar nada. |
| `--max N` | ilimitado | Para depois de enviar `N` mensagens (um teto para limitar estragos). |
| `--last-message-regex REGEX` | nenhum | Só manda mensagem para conversas cuja prévia da última mensagem bate com `REGEX`; elas recebem o template de `-m`. Veja [Roteamento pela última mensagem](#roteamento-pela-última-mensagem). |
| `--last-message-regex-custom REGEX ARQUIVO` | nenhum | Envia `ARQUIVO` em vez do template de `-m` para as conversas que batem com `REGEX`. Pode ser repetido. |
| `--by-title` | desligado | Lê o título de cada contato e envia a variante de recrutador (o arquivo base), `dev_` ou `generic_` do template. Abre todas as conversas, inclusive com `--dry-run`. Veja [Roteamento pelo título](#roteamento-pelo-título). |
| `-l`, `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARN` ou `ERROR`. |

### Roteamento pela última mensagem

Cada card de conversa mostra uma prévia da última mensagem, e essa prévia pode
decidir **se** o card recebe mensagem e **qual** template ele recebe.

- `--last-message-regex REGEX` — só os cards cuja prévia bate recebem mensagem,
  com o template de `-m` (padrão `message.txt`).
- `--last-message-regex-custom REGEX ARQUIVO` — os cards que batem com `REGEX`
  recebem `ARQUIVO` no lugar. Passe a flag quantas vezes tiver templates.

```bash
linkedin-bots message --last-message-regex ".*há 7.*" \
    --last-message-regex-custom ".*for 7.*" message_english.txt
```

Essa execução manda `message.txt` para um contato cuja prévia diz "há 7 anos",
`message_english.txt` para um cuja prévia diz "for 7 years", e pula todos os
outros — um jeito de responder no idioma em que a conversa já está.

As regras são avaliadas **nesta ordem: primeiro as personalizadas (na ordem
dada), depois `--last-message-regex` como alternativa final**, e vence a
primeira que bater. Assim, um `--last-message-regex` amplo nunca rouba um card
de uma regra personalizada específica; entre as regras personalizadas, coloque
o padrão mais específico primeiro.

Usada **sozinha**, `--last-message-regex-custom` continua filtrando: cards que
não batem com nenhum padrão são pulados. Sem nenhuma das duas flags, todo card
recebe o template de `-m`, como antes.

As duas flags recebem expressões regulares do Python, aplicadas com
`re.search` ao texto da prévia (então não é preciso ancorá-las). Todo padrão é
compilado e todo arquivo de template é verificado na inicialização — uma regex
inválida ou um nome de arquivo errado interrompe a execução antes de abrir a
primeira conversa, em vez de cair silenciosamente num texto genérico. Os
nomes de arquivo sozinhos são procurados como no `-m`: primeiro na sua pasta de
templates, depois em `src/linkedin_bots/messaging/templates/`.

Um card cuja prévia o LinkedIn ainda não renderizou (cards fora da tela são
esvaziados pela lista virtualizada) não bate com nada e é pulado, então vale
uma passada de `--dry-run` antes de uma execução real: ela registra cada
contato com o template que seria usado.

### Roteamento pelo título

Com `--by-title`, o bot também lê quem é cada contato. Ele abre a conversa, lê
o título no cartão de perfil do início do histórico e envia uma de três
variantes do template que a execução já escolheu (pelo `-m` ou pelas regras da
última mensagem, então o idioma não muda):

| Título | Recebe | Exemplo (`-m message.txt`) |
|--------|--------|----------------------------|
| qualquer termo de recrutamento ("Tech Recruiter", "Talent Acquisition", "Recrutadora") | o arquivo base | `message.txt` |
| quem escreve código (desenvolvedor, engenheiro de software, front/back end, full stack, mobile, tech lead, arquiteto de software) | `dev_` + base | `dev_message.txt` |
| todos os outros (gestores, CTOs, RH, QA, dados, DevOps) | `generic_` + base | `generic_message.txt` |

Recrutamento vence: "Tech Recruiter | Hiring Developers" é recrutador.
Estudantes, estagiários e trainees com um cargo de dev no título são devs.

Um contato cujo título não pôde ser lido é pulado, em vez de receber um
palpite. Ele fica fora do histórico de envios, então uma próxima execução tenta
de novo.

As variantes são procuradas como o arquivo base, uma a uma: primeiro na sua
pasta de templates, depois nos templates do pacote. Quando uma não existe (não
há `generic_reconnect.txt`, por exemplo), essa audiência recebe o arquivo base,
e a execução avisa uma vez, na inicialização.

A linha de cada contato no log mostra o título, a audiência e o arquivo usado;
a execução termina com uma contagem por audiência e quantos títulos não
puderam ser lidos (e foram pulados). Se o LinkedIn mudar o cartão de perfil,
todo mundo é pulado: é nessa contagem que isso aparece.

`--dry-run --by-title` abre todas as conversas para ler o título, então é mais
lento que um dry run comum e marca as conversas não lidas como lidas. Ainda
assim, nunca digita nada.

### Onde ele começa

- **Nenhuma conversa aberta** → começa do topo da lista (a mais recente), ou do
  fim (a mais antiga) quando `-r`/`--reverse` é passado.
- **Uma conversa já aberta** (você clicou numa antes de iniciar) → começa
  **por essa conversa, inclusive**, e segue na direção da caminhada (para baixo
  por padrão, para cima com `-r`). Todo card do outro lado da conversa ativa é
  pulado. Isso permite retomar de um ponto conhecido, por exemplo: clicar na
  conversa mais antiga da caixa de entrada e rodar com `-r` para subir pelos
  contatos antigos.
- **`--start-date` passado** → o próprio bot rola a lista (focando o último
  card para disparar o carregamento, já que rolar simplesmente não carrega mais
  de forma confiável) até encontrar a primeira conversa com data igual ou
  anterior àquela, clica nela e começa dali — igual a ter clicado nela à mão.
  Funciona do mesmo jeito com ou sem `-r`, porque só afeta onde a caminhada
  *começa*, não a direção que ela segue depois.

Todo contato para quem uma mensagem foi enviada com confirmação também é
registrado em `messaging/sent_history.json`, na pasta de dados (veja
[Onde ficam os dados](../README.md#onde-ficam-os-dados)). A lista de
conversas se reordena por atividade recente — uma resposta, ou atividade em
qualquer outra conversa — então ela não é só acrescentada entre uma execução e
outra. O histórico é carregado na inicialização e usado como checagem para
pular cards durante a caminhada, então quem já recebeu mensagem numa execução
anterior nunca recebe de novo, mesmo que acabe ficando *abaixo* de onde você
retoma. Ele só serve para *pular* um card — a navegação em si é puramente "o
próximo card abaixo".

Duas pessoas podem ter o mesmo nome, então cada envio também registra o ID da
foto do contato (o ID do arquivo no caminho da URL da foto) e o ID da conversa
(thread). Um card cujo nome está no histórico é pulado quando a foto bate com
uma já registrada; senão, a conversa é aberta e pulada se for uma thread já
registrada. Registros mais antigos guardam só o nome: um card só conta como
outra pessoa quando a última atividade dele é mais recente que aquele envio.

Se o arquivo de histórico existir mas não puder ser lido, a execução para antes
de tocar em qualquer conversa, em vez de tratá-lo como vazio — um histórico
vazio faria todo mundo nele parecer novo. As gravações passam por um arquivo
temporário, então uma falha não o deixa pela metade, e uma mensagem enviada que
não pôde ser gravada (por exemplo, outro programa segura o arquivo) interrompe a
execução, para que ninguém receba mensagem duas vezes.

### Interpretação de datas

As checagens de `--date-limit` e `--start-date` dependem de interpretar as
datas dos cards de conversa do LinkedIn, que vêm em vários formatos.
`parse_card_timestamp()` em [`messaging/domain/card_date.py`](../src/linkedin_bots/messaging/domain/card_date.py) trata:

| O card mostra | Interpretado como |
|---------------|-------------------|
| `10:01 PM` / `9:12 AM` | hoje |
| `Mon`, `Tue`, … | a ocorrência passada mais recente (últimos 7 dias) |
| `Jun 27` | esse dia, neste ano (ou no ano passado, se cair no futuro) |
| `Jun 27, 2024` | dia + ano explícitos |
| `Mar 2024` | o dia 1º desse mês |
| qualquer outra coisa | desconhecido → tratado como dentro do intervalo (**não** para a execução) |

### Como funciona (notas de implementação)

Estes detalhes importam se você precisar adaptar o bot a mudanças na interface
do LinkedIn — os seletores ficam em [`messaging/adapters/selenium/`](../src/linkedin_bots/messaging/adapters/selenium/).

- **Camadas.** `domain/` guarda as regras puras — datas dos cards, contatos com
  o mesmo nome, roteamento de templates e o `assess()`, o veredito para um card;
  `application/send_follow_ups.py` percorre a lista por portas; `adapters/`
  guarda os Page Objects do Selenium e o arquivo de histórico.
- **Caixa de texto que envia com Enter.** A caixa de mensagem direta do
  LinkedIn é uma div `contenteditable` que envia ao apertar Enter, então
  `send_keys` não serve para texto com várias linhas. `_insert_text()` injeta o
  corpo inteiro (quebras de linha como quebras suaves) num único
  `execCommand('insertText')` atômico, com um setter de `innerText` como
  alternativa.
- **Envio + verificação.** Depois de inserir o texto, o bot aperta um Enter
  confiável; se a caixa não esvaziar, ele clica no botão **Send** como
  alternativa. Um envio só é considerado bem-sucedido quando a caixa de texto
  volta a ficar vazia.
- **Cliques confiáveis.** Os cards de conversa são abertos com a mesma escada
  de cliques nativo → ActionChains → CDP → JS usada pelo bot connect.
- **Etiquetas para pular.** Anúncios patrocinados, InMails e LinkedIn Offers
  usam o mesmo componente de etiqueta; o bot compara o texto da etiqueta
  (`sponsored` / `inmail` / `linkedin offer`) e pula esses cards.

### Documentos de design

- [`design/messaging-bot.spec.pt-BR.md`](design/messaging-bot.spec.pt-BR.md) — a spec
  original (HTML de partida e comportamento desejado).
- [`design/message-by-title.spec.md`](design/message-by-title.spec.md) — roteamento pelo
  título (`--by-title`), em inglês.
