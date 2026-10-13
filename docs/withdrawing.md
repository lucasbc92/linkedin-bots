# Withdraw bot

[English](#english) | [Português (Brasil)](#português-brasil)

## English

Loads the **sent-invitation manager** back to a cutoff date and withdraws every
invitation older than it, oldest first — the pending-invite list is capped, and
months-old invitations that were never accepted are what fills it.

> See the [root README](../README.md) for the one-time setup (attaching Chrome,
> installing dependencies) and the conventions shared by the bots.

### What it does

Starting from `linkedin.com/mynetwork/invitation-manager/sent/` (it navigates
there if you're elsewhere), the bot:

0. **Finds the tab.** Attaching to a running Chrome lands on an arbitrary tab,
   so the bot switches to the invitation-manager tab (or navigates there)
   before touching anything — the same thing `connect` and `message` do.
1. **Expands the list to the very end.** The page is a LazyColumn: scrolling
   loads nothing, and every page after the first is appended by a **"Load
   more"** button. The bot clicks it repeatedly — through an in-page
   JavaScript loop by default, falling back to the trusted-click ladder in
   `src/linkedin_bots/shared/infrastructure/clicking.py` if that stalls — until the button is gone and the
   oldest invitation is in the DOM. `--stop-early` stops at the cutoff
   instead, which is cheaper but never reaches the oldest.
2. **Picks every card past the cutoff.** The list is only *roughly*
   newest-first — LinkedIn sometimes shows an invitation from hours ago
   below ones from a month ago — so no position in it is trusted as a
   boundary. With the whole list loaded, `targets_older_than` checks every
   card and keeps each one past `--until`, sorted oldest first.

   Cards show relative ages (`Sent 3 months ago`), never dates. LinkedIn
   rounds down, so that label means *at least* three months: the parsed date
   is the **newest** the invitation can be. A card is withdrawn only when
   that newest-possible date is already past `--until`, so ambiguous cards —
   and any card whose age can't be parsed — are left alone.
3. **Withdraws, oldest first.** Each withdrawal opens a confirmation dialog
   whose confirm button repeats the invitee's name
   (`aria-label="Withdraw invitation sent to Camilla Souza"`). The bot checks
   that name against the card it clicked and **dismisses the dialog instead
   of confirming** when they disagree — withdrawing the wrong person can't be
   undone, a skipped card can. It then waits for the card to leave the list
   before moving on, with a randomized 1.5–3 s gap between withdrawals. A
   dialog left open after a failure is cancelled, since a modal `<dialog>`
   blocks every click beneath it.

### Two ways down the list

The default is **expand, then withdraw**: load every page, then withdraw every
card past the cutoff, oldest first. It is the thorough one — it always reaches
the true bottom of the list — but a thousand expanded cards make the page
heavy, and nothing is withdrawn until the loading finishes.

`--rolling` is the other way round: withdraw whatever is **already loaded** and
past `--until`, load two more pages, withdraw again, repeat until the list
ends. Withdrawn cards leave the DOM as new ones arrive, so the page stays about
the size it started at, and the run starts working immediately. It also starts
from whatever is on screen — scroll down to the first invitation past the
cutoff by hand, then run it, and it picks up from there.

Either way a card is withdrawn only when its own age proves it is past the
cutoff, and a failed withdrawal is never retried inside the same run.

### Usage

```bash
linkedin-bots withdraw                              # same as --until 1m, after a y/N confirmation
linkedin-bots withdraw --until 2026/05/01 --dry-run # preview — nothing is clicked
linkedin-bots withdraw --until 2026/05/01           # withdraw, after a y/N confirmation
linkedin-bots withdraw --until 1m --max 200 -y      # load 200 cards, withdraw the old ones among them
linkedin-bots withdraw --until 1m --rolling         # withdraw as it loads, down to the oldest
```

| Flag | Meaning |
|---|---|
| `--until YYYY/MM/DD` | Withdraw invitations sent **on or before** this date, or this far back (`2m`, `3w`). Default `1m`. |
| `--max N` | Load at most N invitations, then withdraw the ones among them older than `--until`. Keeps the page light. |
| `--rolling` | Withdraw what is loaded and past `--until`, load two more pages, repeat down to the oldest — instead of expanding the list first. |
| `--dry-run` | Log what would be withdrawn; click nothing. |
| `-y`, `--yes` | Skip the confirmation prompt. |
| `--max-pages N` | Cap the pages loaded — the same bound as `--max`, counted in page loads rather than cards. A page counts whether it came from clicking "Load more" or from the list paging on scroll. With `--rolling`, the pages loaded per top-up (default 2). `--max-clicks` is accepted as an alias. |
| `--no-js` | Drive every page with trusted clicks instead of the in-page loop. |
| `--stop-early` | Stop loading at the cutoff instead of expanding to the end. No effect with `--rolling`, which never expands up front. |
| `--probe` | Print which tab, selectors and buttons the bot can see, then exit. |
| `-l LEVEL` | Log verbosity (default `INFO`). |

Withdrawal is irreversible and the run is unattended once started, so there is
always a cutoff (`--until`, `1m` when omitted) — there is no "withdraw
everything" mode — and the first run asks for confirmation unless `-y` is
passed. Start with `--dry-run`.

### Notes

- **Withdrawing blocks re-inviting that person for up to 3 weeks** — LinkedIn
  says so in the confirmation dialog. Worth remembering before clearing
  invitations to recruiters you may want to reach again.
- **Withdrawing does not refund the weekly invitation limit.** It frees space in
  the *pending* list; the weekly counter the connect bot tracks is unaffected.
- `tests/fixtures/withdrawing/withdraw-dialog.html` is the captured confirmation dialog
  the selectors key off; keep it in sync when LinkedIn's markup shifts.
- **The whole list is heavy.** ~1000 invitations is ~100 pages; the fully
  expanded DOM slows the browser down, and the default expands to the end
  because old invitations can sit anywhere in it. `--stop-early` skips that
  cost when the oldest invitations aren't the ones you're after.
- Age parsing and target selection are pure functions (`parse_sent_age`,
  `targets_older_than`) in `src/linkedin_bots/withdrawing/domain/`, covered
  by `tests/withdrawing/`.
- **When a run finds nothing, run `--probe` first.** It prints the open tabs,
  how many cards each candidate selector matches, whether the withdraw links
  and the "Load more" button are visible, and the last few button labels on
  the page — which separates "wrong tab" from "markup changed" from "list
  never mounted" without guessing.

## Português (Brasil)

Carrega o **gerenciador de convites enviados** até uma data de corte e retira
todo convite mais antigo que ela, do mais antigo para o mais novo — a lista de
convites pendentes tem limite, e são os convites de meses atrás, nunca aceitos,
que a enchem.

> Veja o [README principal](../README.md#português-brasil) para a configuração única
> (conectar o Chrome, instalar as dependências) e as convenções comuns aos
> bots.

### O que ele faz

A partir de `linkedin.com/mynetwork/invitation-manager/sent/` (ele navega até
lá se você estiver em outra página), o bot:

0. **Encontra a aba.** Conectar a um Chrome aberto cai numa aba qualquer, então
   o bot muda para a aba do gerenciador de convites (ou navega até ela) antes
   de mexer em qualquer coisa — o mesmo que `connect` e `message` fazem.
1. **Expande a lista até o fim.** A página é uma LazyColumn: rolar não carrega
   nada, e cada página depois da primeira é acrescentada por um botão **"Load
   more"**. O bot clica nele repetidamente — por um loop em JavaScript dentro
   da página por padrão, recorrendo à escada de cliques confiáveis de
   `src/linkedin_bots/shared/infrastructure/clicking.py` se ele travar — até o botão sumir e o convite mais
   antigo estar no DOM. `--stop-early` para na data de corte, o que é mais
   barato mas nunca chega ao mais antigo.
2. **Escolhe todo card além da data de corte.** A lista só está *mais ou menos*
   do mais novo para o mais antigo — às vezes o LinkedIn mostra um convite de
   horas atrás abaixo de outros de um mês atrás — então nenhuma posição nela é
   confiável como fronteira. Com a lista inteira carregada,
   `targets_older_than` confere cada card e fica com todos os que passaram de
   `--until`, ordenados do mais antigo para o mais novo.

   Os cards mostram idades relativas (`Sent 3 months ago`), nunca datas. O
   LinkedIn arredonda para baixo, então esse rótulo significa *pelo menos* três
   meses: a data interpretada é a **mais recente** que o convite pode ter. Um
   card só é retirado quando essa data mais recente possível já passou de
   `--until`, então cards ambíguos — e qualquer card cuja idade não dê para
   interpretar — ficam como estão.
3. **Retira, do mais antigo para o mais novo.** Cada retirada abre um diálogo
   de confirmação cujo botão de confirmar repete o nome do convidado
   (`aria-label="Withdraw invitation sent to Camilla Souza"`). O bot compara
   esse nome com o do card que clicou e **fecha o diálogo em vez de confirmar**
   quando eles não batem — retirar o convite da pessoa errada não tem volta, um
   card pulado tem. Depois espera o card sair da lista antes de seguir, com um
   intervalo aleatório de 1,5–3 s entre retiradas. Um diálogo que fica aberto
   depois de uma falha é cancelado, já que um `<dialog>` modal bloqueia todo
   clique por baixo dele.

### Dois jeitos de descer a lista

O padrão é **expandir, depois retirar**: carregar todas as páginas e então
retirar todo card além da data de corte, do mais antigo para o mais novo. É o
jeito completo — sempre chega ao verdadeiro fim da lista —, mas mil cards
expandidos deixam a página pesada, e nada é retirado até o carregamento
terminar.

`--rolling` é o contrário: retira o que **já está carregado** e passou de
`--until`, carrega mais duas páginas, retira de novo, e repete até a lista
acabar. Cards retirados saem do DOM enquanto novos chegam, então a página fica
mais ou menos do tamanho em que começou, e a execução começa a trabalhar na
hora. Ele também começa do que estiver na tela — role à mão até o primeiro
convite além da data de corte, depois rode, e ele continua dali.

Nos dois casos, um card só é retirado quando a própria idade prova que ele
passou da data de corte, e uma retirada que falhou nunca é tentada de novo na
mesma execução.

### Uso

```bash
linkedin-bots withdraw                              # igual a --until 1m, depois de uma confirmação y/N
linkedin-bots withdraw --until 2026/05/01 --dry-run # prévia — nada é clicado
linkedin-bots withdraw --until 2026/05/01           # retira, depois de uma confirmação y/N
linkedin-bots withdraw --until 1m --max 200 -y      # carrega 200 cards e retira os antigos entre eles
linkedin-bots withdraw --until 1m --rolling         # retira enquanto carrega, até o mais antigo
```

| Flag | Significado |
|---|---|
| `--until AAAA/MM/DD` | Retira os convites enviados **nesta data ou antes**, ou de até esse tempo atrás (`2m`, `3w`). Padrão `1m`. |
| `--max N` | Carrega no máximo N convites e retira os que, entre eles, são mais antigos que `--until`. Mantém a página leve. |
| `--rolling` | Retira o que está carregado e passou de `--until`, carrega mais duas páginas e repete até o mais antigo — em vez de expandir a lista primeiro. |
| `--dry-run` | Registra no log o que seria retirado; não clica em nada. |
| `-y`, `--yes` | Pula a pergunta de confirmação. |
| `--max-pages N` | Limita as páginas carregadas — o mesmo limite de `--max`, contado em carregamentos de página em vez de cards. Uma página conta tanto se veio de clicar em "Load more" quanto da lista paginando ao rolar. Com `--rolling`, são as páginas carregadas a cada reabastecimento (padrão 2). `--max-clicks` é aceito como sinônimo. |
| `--no-js` | Move cada página com cliques confiáveis em vez do loop dentro da página. |
| `--stop-early` | Para de carregar na data de corte em vez de expandir até o fim. Não tem efeito com `--rolling`, que nunca expande de antemão. |
| `--probe` | Mostra qual aba, quais seletores e quais botões o bot consegue ver, e sai. |
| `-l NÍVEL` | Nível de detalhe do log (padrão `INFO`). |

A retirada é irreversível e a execução segue sozinha depois de iniciada, então
sempre existe uma data de corte (`--until`, `1m` quando omitido) — não há modo
"retirar tudo" — e a primeira execução pede confirmação, a menos que `-y` seja
passado. Comece com `--dry-run`.

### Observações

- **Retirar um convite impede convidar a mesma pessoa de novo por até 3
  semanas** — o LinkedIn avisa isso no diálogo de confirmação. Vale lembrar
  antes de limpar convites para recrutadores que você talvez queira abordar de
  novo.
- **Retirar não devolve o limite semanal de convites.** Libera espaço na lista
  de *pendentes*; o contador semanal que o bot connect acompanha não muda.
- `tests/fixtures/withdrawing/withdraw-dialog.html` é o diálogo de confirmação capturado
  em que os seletores se baseiam; mantenha-o atualizado quando o markup do
  LinkedIn mudar.
- **A lista inteira é pesada.** ~1000 convites são ~100 páginas; o DOM
  totalmente expandido deixa o navegador lento, e o padrão expande até o fim
  porque convites antigos podem estar em qualquer ponto dela. `--stop-early`
  evita esse custo quando os convites mais antigos não são os que você quer.
- A interpretação das idades e a escolha dos alvos são funções puras
  (`parse_sent_age`, `targets_older_than`), em
  `src/linkedin_bots/withdrawing/domain/`, cobertas por `tests/withdrawing/`.
- **Quando uma execução não encontrar nada, rode `--probe` primeiro.** Ele
  mostra as abas abertas, quantos cards cada seletor candidato encontra, se os
  links de retirada e o botão "Load more" estão visíveis, e os últimos rótulos
  de botão da página — o que separa "aba errada" de "markup mudou" de "lista
  nunca montou" sem precisar adivinhar.
