[English](connecting.md) | [Português (Brasil)](connecting.pt-BR.md)

# Bot connect

Percorre os **resultados da busca de pessoas** do LinkedIn e envia convites de
conexão personalizados, página por página, até acabarem os resultados ou
atingir o limite semanal de convites do LinkedIn.

> Veja o [README principal](../README.md#português-brasil) para a configuração única
> (conectar o Chrome, instalar as dependências) e as convenções comuns aos dois
> bots.

## O que ele faz

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

## Uso

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

### Opções

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

## Ritmo

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

## Alcançando quem só oferece Follow

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

## Filtro de recrutador tech

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

## Limites de convites de conexão

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

## Contagem de convites

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

## Como funciona (notas de implementação)

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

### HTML de referência

[`tests/fixtures/connecting/`](../tests/fixtures/connecting/) guarda trechos de HTML do LinkedIn salvos (o
modal de convite, o modal de nota, a tela de e-mail, o card de quem só oferece
Follow, uma página de perfil completa, o menu **More** aberto desse perfil, os
contêineres antigo/novo dos resultados de busca) usados como fixtures ao
atualizar seletores. `tests/connecting/adapters/test_saved_markup.py` roda os
seletores de Follow, More e Connect contra esses arquivos (o lxml, no extra de
desenvolvimento, faz com que rodem em vez de serem pulados), então uma mudança no markup do
LinkedIn aparece como um teste falhando, e não como uma execução silenciosa que
não convida ninguém.
