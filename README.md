# linkedin-bots

[![CI](https://github.com/lucasbc92/linkedin-bots/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasbc92/linkedin-bots/actions/workflows/ci.yml)

[English](#english) | [Português (Brasil)](#português-brasil)

## English

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

### How they work (the shared model)

All three bots **attach to an existing Chrome instance** over the DevTools protocol
rather than launching their own browser. That means:

- you log in to LinkedIn yourself, in a normal browser session, once; and
- the bots act as that session — no credential handling, no separate login.

You navigate to the right page (people-search results for `connect`, the
Messaging inbox for `message`, the sent-invitation manager for `withdraw`),
leave that tab open, and run the bot. It finds
the correct tab among your open tabs, then walks the page sending messages with
randomized pauses, keeping the PC awake until it finishes.

### Requirements and installation

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

#### Windows executable

On Windows you can skip Python entirely: download
`linkedin-bots-<version>-windows-x64.exe` from the
[latest release](https://github.com/lucasbc92/linkedin-bots/releases/latest)
and run it in place of `linkedin-bots`
(e.g. `linkedin-bots-1.1.0-windows-x64.exe connect`). Chrome is still required.

- It ships one generic English `message.txt` per bot (the shipped
  `message_english.txt`), built in and not editable. Put your own templates in
  your data directory (see [Templates](#templates)), or point `-m` at a file
  (`-m C:\path\to\message.txt`).
- The executable isn't code-signed, so SmartScreen shows "Windows protected
  your PC" the first time: choose **More info → Run anyway**.

It is built from the release tag by
[`.github/workflows/release.yml`](.github/workflows/release.yml).

### Setup: attach Chrome to the bots

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

### Running

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

### Templates

The connect and message bots read their message text from plain-text template files, so you can
edit wording without touching code.

```
src/linkedin_bots/connecting/templates/   # used by `linkedin-bots connect`
├── message.txt                           (default, Portuguese)
└── message_english.txt

src/linkedin_bots/messaging/templates/    # used by `linkedin-bots message`
├── message.txt                           (default, Portuguese)
├── message_english.txt
├── reconnect.txt                         (re-approaching old contacts)
└── reconnect_english.txt
```

The shipped templates are generic. **Your own templates** go in your data
directory (see [Where data lives](#where-data-lives)), under
`<context>/templates/`. A file there wins over the shipped one with the same
name, so a personal `message.txt` becomes your default and the shipped files
fill in for the rest. They stay out of the repository and are also picked up by
the Windows executable.

**Format** (handled by [`messages.py`](src/linkedin_bots/shared/domain/messages.py)):

- A file may hold **several variations separated by a line of three or more
  dashes** (`---`). The bot picks one at random per send, so your outreach
  doesn't look identical to everyone.
- `{name}` anywhere in the text is replaced with the contact's first name.
- If the contact's name can't be determined, `{name}` (and an adjacent comma /
  space) is dropped so the greeting still reads cleanly.

**Picking a template:** pass `-m <filename>` (looked up in your own templates
folder, then in that bot's shipped one), or `-m <path>` to point anywhere. With no `-m`, the
bot uses `message.txt`.

**Character limits:** connection-request notes are capped by LinkedIn at **300
characters** (counted as UTF-16 code units, so emoji = 2). The connect bot
enforces this — it drops `{name}` first, then truncates without splitting an emoji.
Direct messages have no cap, so the message bot never truncates.

#### First-name handling

`{name}` is filled with the contact's first name via
[`names.py`](src/linkedin_bots/shared/domain/names.py), which is tuned for **Brazilian names**: it
keeps compound first names like *João Victor*, *Ana Júlia*, and
*Maria de Lourdes*, while dropping surnames such as *Silva* or *Santos*.

### Where data lives

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
│   ├── logs/week-YYYY-MM-DD.log
│   └── templates/           # your own templates (optional)
├── messaging/
│   ├── sent_history.json    # everyone already messaged
│   ├── logs/
│   └── templates/
└── withdrawing/
    └── logs/
```

Set `LINKEDIN_BOTS_HOME` to use another folder. Every run logs the path of its
log file when it starts and when it ends.

### Shared behavior & configuration

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

### Shell tab-completion (optional)

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

### Project layout

```
linkedin-bots/
├── pyproject.toml               # package, dependencies, console script, architecture contracts
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
inward (adapters → application → domain), contexts never import each other,
and `lint-imports` (run in CI) fails the build otherwise.

### Running the tests

```bash
python -m pytest     # the whole suite; tests never touch your real data directory
lint-imports         # the architecture contracts declared in pyproject.toml
```

Run them with pytest, not `unittest`: `tests/conftest.py` points every test at
a throwaway data directory, and only pytest loads it.

### License

[MIT](LICENSE) © Lucas Bueno Cesario.

## Português (Brasil)

Um pequeno conjunto de bots em Python + Selenium que automatizam a prospecção
no LinkedIn controlando **a sua própria sessão do Chrome, já logada**. Três
bots, um único comando:

| Bot | Comando | O que faz | Docs |
|-----|---------|-----------|------|
| **Connect** | `linkedin-bots connect` | Percorre os resultados da busca de pessoas e envia convites de conexão personalizados. | [docs/connecting.pt-BR.md](docs/connecting.pt-BR.md) |
| **Message** | `linkedin-bots message` | Percorre a caixa de entrada do Messaging e envia uma mensagem de acompanhamento personalizada para cada conversa. | [docs/messaging.pt-BR.md](docs/messaging.pt-BR.md) |
| **Withdraw** | `linkedin-bots withdraw` | Retira os convites enviados mais antigos que uma data de corte, do mais antigo para o mais novo, para liberar a lista limitada de pendentes. | [docs/withdrawing.pt-BR.md](docs/withdrawing.pt-BR.md) |

Cada bot tem seu próprio guia, com a referência completa de opções e notas de
implementação. Esta página cobre tudo o que eles têm em comum: instalação,
configuração, convenções e a arquitetura.

> **Atenção.** Automatizar o LinkedIn viola os Termos de Serviço e pode fazer
> sua conta ser restringida. Estas ferramentas se limitam com pausas parecidas
> com as de uma pessoa e respeitam os limites do LinkedIn, mas o uso é por sua
> conta e risco. Mantenha volumes moderados.

### Como funcionam (o modelo compartilhado)

Os três bots **se conectam a uma instância do Chrome já aberta** pelo protocolo
DevTools, em vez de abrir um navegador próprio. Isso significa que:

- você faz login no LinkedIn uma vez, numa sessão normal do navegador; e
- os bots agem como essa sessão — sem lidar com credenciais, sem login separado.

Você abre a página certa (resultados da busca de pessoas para `connect`, a
caixa de entrada do Messaging para `message`, o gerenciador de convites
enviados para `withdraw`), deixa essa aba aberta e roda o bot. Ele encontra a
aba correta entre as abas abertas e percorre a página enviando mensagens com
pausas aleatórias, mantendo o PC acordado até terminar.

### Requisitos e instalação

- **Python 3.10+** (desenvolvido no 3.14)
- **Google Chrome**

Instale o pacote num ambiente virtual — em modo editável, para que mudanças no
código e nos templates valham sem reinstalar:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
```

Isso coloca um comando `linkedin-bots` no PATH do ambiente. As dependências
ficam declaradas no [`pyproject.toml`](pyproject.toml).

O Selenium 4.33 traz o **Selenium Manager** embutido, então um ChromeDriver
compatível é baixado automaticamente na primeira vez que você roda um bot — sem
configurar driver manualmente.

#### Executável para Windows

No Windows dá para dispensar o Python: baixe
`linkedin-bots-<versão>-windows-x64.exe` da
[release mais recente](https://github.com/lucasbc92/linkedin-bots/releases/latest)
e rode-o no lugar de `linkedin-bots`
(ex.: `linkedin-bots-1.1.0-windows-x64.exe connect`). O Chrome continua
necessário.

- Ele traz um `message.txt` genérico em inglês por bot (o `message_english.txt`
  distribuído), embutido e não editável. Coloque seus próprios templates na sua
  pasta de dados (veja [Templates](#templates-1)) ou aponte o `-m` para um
  arquivo (`-m C:\caminho\para\mensagem.txt`).
- O executável não é assinado, então o SmartScreen mostra "O Windows protegeu
  o computador" na primeira vez: escolha **Mais informações → Executar assim
  mesmo**.

Ele é gerado a partir da tag da release pelo
[`.github/workflows/release.yml`](.github/workflows/release.yml).

### Configuração: conectar o Chrome aos bots

Os bots se conectam ao Chrome em `127.0.0.1:9222`, então o Chrome precisa ser
iniciado com a depuração remota ativada. **Feche o Chrome completamente
antes**, depois abra-o de novo com as flags abaixo.

> **Observação:** versões recentes do Chrome se recusam, sem avisar, a abrir a
> porta do DevTools quando se usa o user-data-dir **padrão** (uma proteção
> contra malwares que roubam cookies procurando portas 9222 abertas). Você
> também precisa passar `--user-data-dir` apontando para uma pasta de perfil
> separada e dedicada — e fazer login no LinkedIn uma vez nesse novo perfil.

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

Depois, nessa janela do Chrome:

1. Faça login no LinkedIn.
2. Abra a página de que o bot precisa:
   - **connect** → uma página de resultados da busca de pessoas (`linkedin.com/search/results/people/…`)
   - **message** → a caixa de entrada do Messaging (`linkedin.com/messaging`)
   - **withdraw** → o gerenciador de convites enviados (`linkedin.com/mynetwork/invitation-manager/sent/`; o bot abre a página se nenhuma aba a mostrar)
3. Rode o bot, de qualquer pasta.

Se nenhuma aba compatível for encontrada, cada bot usa a aba atual e avisa
você.

### Execução

```bash
linkedin-bots connect [opções]      # envia pedidos de conexão
linkedin-bots message [opções]      # envia mensagens de acompanhamento
linkedin-bots withdraw [opções]     # retira convites enviados antigos
linkedin-bots stats                 # convites enviados por semana
linkedin-bots                       # mostra a ajuda
linkedin-bots connect --help        # ajuda do comando + exemplos
python -m linkedin_bots …           # o mesmo, sem o comando de console
```

Veja o guia de cada bot para a lista completa de opções:
[connect](docs/connecting.pt-BR.md#opções) · [message](docs/messaging.pt-BR.md#opções) · [withdraw](docs/withdrawing.pt-BR.md#uso).

### Templates

Os bots connect e message leem o texto das mensagens de arquivos de template em texto puro,
então você pode mudar o texto sem mexer no código.

```
src/linkedin_bots/connecting/templates/   # usado por `linkedin-bots connect`
├── message.txt                           (padrão, português)
└── message_english.txt

src/linkedin_bots/messaging/templates/    # usado por `linkedin-bots message`
├── message.txt                           (padrão, português)
├── message_english.txt
├── reconnect.txt                         (reabordar contatos antigos)
└── reconnect_english.txt
```

Os templates distribuídos são genéricos. **Seus próprios templates** ficam na
sua pasta de dados (veja [Onde ficam os dados](#onde-ficam-os-dados)), em
`<contexto>/templates/`. Um arquivo ali tem prioridade sobre o distribuído de
mesmo nome, então um `message.txt` pessoal vira o seu padrão e os arquivos
distribuídos cobrem o resto. Eles ficam fora do repositório e também valem para
o executável do Windows.

**Formato** (tratado por [`messages.py`](src/linkedin_bots/shared/domain/messages.py)):

- Um arquivo pode ter **várias variações separadas por uma linha com três ou
  mais hifens** (`---`). O bot sorteia uma a cada envio, para que sua
  prospecção não pareça idêntica para todo mundo.
- `{name}` em qualquer ponto do texto é trocado pelo primeiro nome do contato.
- Se não for possível descobrir o nome do contato, `{name}` (e uma vírgula /
  espaço vizinhos) é removido, para que a saudação continue fluindo bem.

**Escolhendo um template:** passe `-m <arquivo>` (procurado na sua pasta de
templates e depois na distribuída daquele bot), ou `-m <caminho>` para apontar
para qualquer lugar.
Sem `-m`, o bot usa `message.txt`.

**Limites de caracteres:** as notas dos pedidos de conexão são limitadas pelo
LinkedIn a **300 caracteres** (contados em unidades UTF-16, então emoji = 2). O
bot connect respeita isso — primeiro remove `{name}`, depois corta o texto sem
partir um emoji ao meio. Mensagens diretas não têm limite, então o bot
message nunca corta nada.

#### Tratamento do primeiro nome

`{name}` é preenchido com o primeiro nome do contato por
[`names.py`](src/linkedin_bots/shared/domain/names.py), que é ajustado para **nomes
brasileiros**: mantém primeiros nomes compostos como *João Victor*, *Ana Júlia*
e *Maria de Lourdes*, e descarta sobrenomes como *Silva* ou *Santos*.

### Onde ficam os dados

Os logs e os registros de quem foi contatado são dados pessoais, então ficam
fora do repositório, na sua pasta de dados de usuário:

| SO | Pasta |
|---|---|
| Windows | `%LOCALAPPDATA%\linkedin-bots\` |
| macOS | `~/Library/Application Support/linkedin-bots/` |
| Linux | `~/.local/share/linkedin-bots/` |

```
linkedin-bots/
├── connecting/
│   ├── invites.jsonl        # todo convite confirmado
│   ├── logs/week-AAAA-MM-DD.log
│   └── templates/           # seus próprios templates (opcional)
├── messaging/
│   ├── sent_history.json    # todo mundo que já recebeu mensagem
│   ├── logs/
│   └── templates/
└── withdrawing/
    └── logs/
```

Defina `LINKEDIN_BOTS_HOME` para usar outra pasta. Toda execução registra no
log o caminho do arquivo de log quando começa e quando termina.

### Comportamento e configuração compartilhados

Valem para os três bots e são configurados a cada execução por flags (não há
arquivo de configuração):

- **Pausas parecidas com as de uma pessoa.** Pausas aleatórias entre ações e
  páginas, para não parecer um script.
- **Prevenção de suspensão.** No Windows, o PC é mantido acordado durante a
  execução e restaurado depois ([`sleep.py`](src/linkedin_bots/shared/infrastructure/sleep.py)). Não faz
  nada em outras plataformas.
- **Logs.** Toda execução é acrescentada ao arquivo de log semanal daquele bot,
  na pasta de dados (veja [Onde ficam os dados](#onde-ficam-os-dados); a semana
  começa domingo às 21:00, America/São_Paulo), e repetida no console. Controle
  o nível de detalhe com `-l / --log-level` (`INFO` por padrão, ou `DEBUG` /
  `WARN` / `ERROR`). Configurado em
  [`logging_setup.py`](src/linkedin_bots/shared/infrastructure/logging_setup.py).
- **Resumo da execução.** Cada bot termina mostrando a contagem
  `sent / failed / skipped` (enviados / com falha / pulados).
- **Cliques robustos.** O LinkedIn ignora alguns cliques sintéticos, então os
  três bots usam uma escada de cliques nativo → ActionChains → Chrome DevTools
  Protocol → JavaScript para produzir eventos confiáveis (inclusive dentro do
  Shadow DOM).
- **Parada limpa.** `Ctrl+C` encerra a execução de forma limpa e ainda restaura
  as configurações de energia.

### Autocompletar no shell (opcional)

O comando `linkedin-bots` traz ganchos do argcomplete, incluindo o autocompletar dos nomes de
template para `-m`. Configuração única:

**Bash / Git Bash** — adicione ao `~/.bashrc`:
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

### Estrutura do projeto

```
linkedin-bots/
├── pyproject.toml               # pacote, dependências, comando de console, contratos de arquitetura
├── src/linkedin_bots/
│   ├── cli/                     # raiz de composição: um módulo por comando
│   ├── connecting/              # bot Connect   → docs/connecting.pt-BR.md
│   ├── messaging/               # bot Message   → docs/messaging.pt-BR.md
│   ├── withdrawing/             # bot Withdraw  → docs/withdrawing.pt-BR.md
│   │   ├── domain/              #   regras puras: idade dos convites, o que retirar
│   │   ├── application/         #   caso de uso + as portas que ele usa
│   │   └── adapters/selenium/   #   Page Objects do LinkedIn
│   └── shared/
│       ├── domain/              # primeiros nomes, templates de mensagem
│       └── infrastructure/      # conexão ao Chrome, cliques, rolagem, logs, caminhos de dados
├── tests/                       # espelha o src/; fixtures/ guarda HTML salvo do LinkedIn
└── docs/                        # guias dos bots, design/ com specs, reference/
```

Os três contextos seguem o mesmo formato hexagonal. As dependências
apontam para dentro (adapters → application → domain), os contextos nunca
importam uns aos outros, e o `lint-imports` (rodado no CI) faz o build falhar
caso contrário.

### Rodando os testes

```bash
python -m pytest     # a suíte inteira; os testes nunca tocam na sua pasta de dados real
lint-imports         # os contratos de arquitetura declarados no pyproject.toml
```

Rode com o pytest, não com o `unittest`: o `tests/conftest.py` aponta cada teste
para uma pasta de dados descartável, e só o pytest o carrega.

### Licença

[MIT](LICENSE) © Lucas Bueno Cesario.
