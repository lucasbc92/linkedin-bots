[English](messaging.md) | [Português (Brasil)](messaging.pt-BR.md)

# Bot message

Percorre a caixa de entrada do **Messaging** do LinkedIn (`linkedin.com/messaging`)
da mais recente para a mais antiga e envia uma mensagem de acompanhamento
personalizada para cada conversa existente.

> Veja o [README principal](../README.pt-BR.md) para a configuração única
> (conectar o Chrome, instalar as dependências) e as convenções comuns aos dois
> bots.

## O que ele faz

A partir de uma aba aberta do **Messaging**, o bot:

1. Encontra a aba do Messaging entre as abas abertas do Chrome (ou usa a aba
   atual).
2. Decide por onde começar (veja [Onde ele começa](#onde-ele-começa) abaixo).
3. Percorre a lista de conversas **estritamente numa direção, um card por
   vez** — para baixo (mais nova→mais antiga) por padrão, ou para cima (mais
   antiga→mais nova) com `-i`/`--inv`. O próximo contato é sempre o card
   vizinho naquela direção, nunca uma nova varredura a partir do topo. Para
   cada card, ele:
   - pula cards **Sponsored**, **InMail** e **LinkedIn Offer** (identificados
     pela etiqueta, o "pill");
   - pula quem já está registrado no histórico de envios;
   - opcionalmente para quando uma conversa ultrapassa `--date-limit` (mais
     antiga que ele indo para baixo, mais nova indo para cima com `-i`);
   - abre a conversa, digita uma mensagem personalizada na caixa de texto e a
     envia.
4. Carrega mais conversas (focando o último card) até chegar ao fim da lista
   (ou atingir `--max`). Indo para cima com `-i` não é preciso carregar mais —
   todo card acima do ponto de partida já está carregado.

Enviar uma mensagem faz aquela conversa pular para o topo da lista, então o bot
guarda o *próximo* card **antes** de enviar. É isso que mantém a caminhada
ancorada: nada depois do envio é calculado em relação ao topo da lista, então
os contatos que já receberam mensagem e estão lá em cima nunca voltam a ser
alvo.

O texto da mensagem vem de um template em [`src/linkedin_bots/messaging/templates/`](../src/linkedin_bots/messaging/templates/).
`{name}` é trocado pelo primeiro nome do contato. Diferente do bot connect,
mensagens diretas **não têm limite de 300 caracteres**, então os templates
nunca são cortados. Veja [Templates](../README.pt-BR.md#templates) no README
principal para o formato.

Os templates distribuídos são genéricos: um de acompanhamento e um de
reabordagem por idioma. Seus próprios templates têm prioridade sobre eles pelo
nome (veja [Templates](../README.pt-BR.md#templates)).

| Template | Idioma | Uso |
|----------|--------|-----|
| `message.txt` (padrão) | português | acompanhamento depois de um convite aceito |
| `message_english.txt` | inglês | acompanhamento |
| `reconnect.txt` | português | reabordar um contato antigo |
| `reconnect_english.txt` | inglês | reabordagem |

## Uso

```bash
linkedin-bots message                        # template padrão, caixa de entrada inteira
linkedin-bots message --dry-run              # mostra quem/o quê — não envia nada
linkedin-bots message --max 10               # para depois de 10 mensagens
linkedin-bots message --date-limit 2025/12/31  # para nas conversas mais antigas que esta data
linkedin-bots message --start-date 2025/07/30  # rola até esta data e começa por ali
linkedin-bots message -m reconnect.txt --max 5 --dry-run
linkedin-bots message -i -m reconnect_english.txt --date-limit 2024/10/20
    # clique antes numa conversa antiga, depois caminhe para cima (mais antiga→mais nova),
    # parando quando uma conversa for mais nova que a data limite
linkedin-bots message --last-message-regex ".*há 7.*" \
    --last-message-regex-custom ".*for 7.*" message_english.txt
    # prévias em português recebem message.txt, as em inglês message_english.txt
```

### Opções

| Flag | Padrão | Significado |
|------|--------|-------------|
| `-m`, `--message ARQUIVO` | `message.txt` | Arquivo de template. Um nome de arquivo sozinho é procurado na sua pasta de templates e depois em `src/linkedin_bots/messaging/templates/`; um caminho é usado como está. Um arquivo que não existe interrompe a execução. |
| `--date-limit AAAA/MM/DD` | nenhum | Para quando uma conversa for mais antiga que esta data (ou, com `-i`/`--inv`, mais nova que esta data). |
| `--start-date AAAA/MM/DD` | nenhum | Rola a lista para baixo (carregando mais conforme preciso), clica na **primeira conversa com data igual ou anterior** a esta e começa a enviar a partir dela, inclusive. Se não existir conversa assim, a execução termina sem enviar. |
| `-i`, `--inv` | desligado | Percorre a lista **para cima** (mais antiga → mais nova) em vez de para baixo. Também inverte `--date-limit`, que passa a significar "parar quando uma conversa for mais nova que esta data". Útil para trabalhar contatos muito antigos, do fim da caixa de entrada para cima. |
| `--dry-run` | desligado | Registra no log quem receberia mensagem e a primeira linha do texto, sem abrir conversas nem enviar nada. |
| `--max N` | ilimitado | Para depois de enviar `N` mensagens (um teto para limitar estragos). |
| `--last-message-regex REGEX` | nenhum | Só manda mensagem para conversas cuja prévia da última mensagem bate com `REGEX`; elas recebem o template de `-m`. Veja [Roteamento pela última mensagem](#roteamento-pela-última-mensagem). |
| `--last-message-regex-custom REGEX ARQUIVO` | nenhum | Envia `ARQUIVO` em vez do template de `-m` para as conversas que batem com `REGEX`. Pode ser repetido. |
| `-l`, `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARN` ou `ERROR`. |

## Roteamento pela última mensagem

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

## Onde ele começa

- **Nenhuma conversa aberta** → começa do topo da lista (a mais recente), ou do
  fim (a mais antiga) quando `-i`/`--inv` é passado.
- **Uma conversa já aberta** (você clicou numa antes de iniciar) → começa
  **por essa conversa, inclusive**, e segue na direção da caminhada (para baixo
  por padrão, para cima com `-i`). Todo card do outro lado da conversa ativa é
  pulado. Isso permite retomar de um ponto conhecido, por exemplo: clicar na
  conversa mais antiga da caixa de entrada e rodar com `-i` para subir pelos
  contatos antigos.
- **`--start-date` passado** → o próprio bot rola a lista (focando o último
  card para disparar o carregamento, já que rolar simplesmente não carrega mais
  de forma confiável) até encontrar a primeira conversa com data igual ou
  anterior àquela, clica nela e começa dali — igual a ter clicado nela à mão.
  Funciona do mesmo jeito com ou sem `-i`, porque só afeta onde a caminhada
  *começa*, não a direção que ela segue depois.

Todo contato para quem uma mensagem foi enviada com confirmação também é
registrado em `messaging/sent_history.json`, na pasta de dados (veja
[Onde ficam os dados](../README.pt-BR.md#onde-ficam-os-dados)). A lista de
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

## Interpretação de datas

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

## Como funciona (notas de implementação)

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

## Documentos de design

- [`design/messaging-bot.spec.pt-BR.md`](design/messaging-bot.spec.pt-BR.md) — a spec
  original (HTML de partida e comportamento desejado).
