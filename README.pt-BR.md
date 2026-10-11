[English](README.md) | [Português (Brasil)](README.pt-BR.md)

# linkedin-bots

[![CI](https://github.com/lucasbc92/linkedin-bots/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasbc92/linkedin-bots/actions/workflows/ci.yml)

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

## Como funcionam (o modelo compartilhado)

Os três bots **se conectam a uma instância do Chrome já aberta** pelo protocolo
DevTools, em vez de abrir um navegador próprio. Isso significa que:

- você faz login no LinkedIn uma vez, numa sessão normal do navegador; e
- os bots agem como essa sessão — sem lidar com credenciais, sem login separado.

Você abre a página certa (resultados da busca de pessoas para `connect`, a
caixa de entrada do Messaging para `message`, o gerenciador de convites
enviados para `withdraw`), deixa essa aba aberta e roda o bot. Ele encontra a
aba correta entre as abas abertas e percorre a página enviando mensagens com
pausas aleatórias, mantendo o PC acordado até terminar.

## Requisitos e instalação

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

## Configuração: conectar o Chrome aos bots

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

## Execução

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

## Templates

Os bots connect e message leem o texto das mensagens de arquivos de template em texto puro,
então você pode mudar o texto sem mexer no código.

```
src/linkedin_bots/connecting/templates/   # usado por `linkedin-bots connect`
├── message.txt                           (padrão, português)
└── message_english.txt

src/linkedin_bots/messaging/templates/    # usado por `linkedin-bots message`
├── message.txt                           (padrão, português)
├── message_english.txt
├── message_extended.txt                  (versão longa de cada um)
├── message_english_extended.txt
└── reconnect*.txt                        (reabordar contatos antigos)
```

**Formato** (tratado por [`messages.py`](src/linkedin_bots/shared/domain/messages.py)):

- Um arquivo pode ter **várias variações separadas por uma linha com três ou
  mais hifens** (`---`). O bot sorteia uma a cada envio, para que sua
  prospecção não pareça idêntica para todo mundo.
- `{name}` em qualquer ponto do texto é trocado pelo primeiro nome do contato.
- Se não for possível descobrir o nome do contato, `{name}` (e uma vírgula /
  espaço vizinhos) é removido, para que a saudação continue fluindo bem.

**Escolhendo um template:** passe `-m <arquivo>` (procurado dentro da pasta de
templates daquele bot), ou `-m <caminho>` para apontar para qualquer lugar.
Sem `-m`, o bot usa `message.txt`.

**Limites de caracteres:** as notas dos pedidos de conexão são limitadas pelo
LinkedIn a **300 caracteres** (contados em unidades UTF-16, então emoji = 2). O
bot connect respeita isso — primeiro remove `{name}`, depois corta o texto sem
partir um emoji ao meio. Mensagens diretas não têm limite, então o bot
message nunca corta nada.

### Tratamento do primeiro nome

`{name}` é preenchido com o primeiro nome do contato por
[`names.py`](src/linkedin_bots/shared/domain/names.py), que é ajustado para **nomes
brasileiros**: mantém primeiros nomes compostos como *João Victor*, *Ana Júlia*
e *Maria de Lourdes*, e descarta sobrenomes como *Silva* ou *Santos*.

## Onde ficam os dados

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
│   └── logs/week-AAAA-MM-DD.log
├── messaging/
│   ├── sent_history.json    # todo mundo que já recebeu mensagem
│   └── logs/
└── withdrawing/
    └── logs/
```

Defina `LINKEDIN_BOTS_HOME` para usar outra pasta. Toda execução registra no
log o caminho do arquivo de log quando começa e quando termina.

## Comportamento e configuração compartilhados

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

## Autocompletar no shell (opcional)

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

## Estrutura do projeto

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

## Rodando os testes

```bash
python -m pytest     # a suíte inteira; os testes nunca tocam na sua pasta de dados real
lint-imports         # os contratos de arquitetura declarados no pyproject.toml
```

Rode com o pytest, não com o `unittest`: o `tests/conftest.py` aponta cada teste
para uma pasta de dados descartável, e só o pytest o carrega.

## Licença

[MIT](LICENSE) © Lucas Bueno Cesario.
