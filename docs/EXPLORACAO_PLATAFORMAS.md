# Peneira de Vagas — Exploração das plataformas (14/10/2026)

> **Status:** documento de pesquisa. **Valem** as seções 2 (exploração das plataformas), 3.1 (Chrome dedicado)
> e 8 (riscos). **Superadas** pela arquitetura FastAPI + React (`ARCHITECTURE.md`): o Telegram, o
> `main.py`, o agendador (§5) e o código de referência da §4. Os achados da §2 já foram aplicados no código.

Base: exploração feita em **14/10/2026, ~19h (Brasília)**, com a busca
**"engenheiro mecânico"**, no Chrome do usuário (Chrome 155, Windows pelo
cabeçalho do navegador). Nenhuma vaga foi aberta para candidatura, nenhum banner
de cookies foi aceito e nenhum CAPTCHA apareceu.

Este documento segue o [`TECH_STACK.md`](TECH_STACK.md): Python, Playwright via
CDP, httpx, SQLite da stdlib, TOML, Telegram. Nenhuma dependência nova.

## 1. O que foi verificado e o que não foi

| Item | Status |
| --- | --- |
| LinkedIn: parâmetros de URL, seletores dos cards, ID da vaga, paginação, contagem de resultados | **Observado** no DOM real |
| LinkedIn: data da vaga | **Observado**, mas só no painel de detalhe e em texto relativo |
| Indeed: parâmetros de URL, seletores dos cards, `data-jk`, paginação | **Observado** no DOM real |
| Indeed: efeito real do filtro `fromage=1` | **Não confirmado**: o botão "Data do anúncio" mostra o número `1`, mas não vi o rótulo do filtro |
| Gupy: endpoint JSON, parâmetros, formato da resposta | **Observado**, chamado de dentro da página (mesma origem) |
| Gupy: o endpoint funcionar com `httpx` fora do navegador | **Não verificado** (pode exigir cabeçalhos ou devolver 403) |
| Código Python deste documento | **Não executado**. Os seletores foram validados com JavaScript no DOM; o fluxo Python é um esqueleto a testar |
| Comportamento sem login (perfil dedicado novo) | **Não verificado**. A exploração usou o perfil pessoal do Chrome |
| Padrões de bloqueio (authwall do LinkedIn, texto do Cloudflare) | **Conhecidos de memória, não observados** |

## 2. Resultado da exploração

### 2.1 Resumo

| | LinkedIn | Indeed | Gupy |
| --- | --- | --- | --- |
| Canal | Navegador (CDP) | Navegador (CDP) | HTTP (`httpx`) |
| Resultado em 14/10 | 53 resultados em 24h (3 páginas) | 15–16 cards por página, 5 páginas visíveis | 20 vagas no total |
| ID estável | `data-occludable-job-id` no `<li>` | `data-jk` no link do título | `id` numérico no JSON |
| Data da vaga | Texto relativo, só no detalhe | Não aparece no card | `publishedDate` ISO exato |
| Filtro de 24h | `f_TPR=r86400` (confirmado) | `fromage=1` (não confirmado) | Não existe; dedup resolve |
| Paginação | Botões "Página N" | Links `pagination-page-N` | `limit` + `offset` |

### 2.2 LinkedIn

**URL de busca**

```
https://www.linkedin.com/jobs/search/?keywords=<termo>&f_TPR=r86400
```

O LinkedIn acrescenta `currentJobId` sozinho. O chip "Últimas 24 horas" ficou
ativo e a contagem foi de 53 resultados. `f_TPR=r86400` funciona hoje, mas pode
mudar.

**Cards**

- 25 itens `li[data-occludable-job-id]` por página, com **25 IDs únicos já presentes no DOM mesmo antes de renderizar**. Isso permite deduplicar pelo ID antes de gastar tempo lendo o card.
- A renderização é **incremental**: entre 7 e 11 cards completos ao carregar, 16 depois de rolar até o fim. Não testei rolar card a card até chegar nos 25. O código abaixo lê enquanto rola, para não depender de os cards ficarem renderizados.
- Seletores dentro de um card renderizado:

| Dado | Seletor |
| --- | --- |
| ID | atributo `data-occludable-job-id` do `<li>` |
| Link | `a[href*="/jobs/view/"]` (caminho `/jobs/view/<id>/`) |
| Título | `a[href*="/jobs/view/"] strong` |
| Empresa | `.artdeco-entity-lockup__subtitle` |
| Local | `.artdeco-entity-lockup__caption` |

- O card **não tem `<time>`**. Marcadores como "Promovida", "Visualizado" e "Candidatura simplificada" aparecem no texto.
- Os contêineres usam **classes com hash aleatório** (a `ul`, as `div` de rolagem, parte das classes do link). Não use essas classes.

**Contagem e paginação**

- Contagem: `.jobs-search-results-list__title-heading` (texto: "engenheiro mecânico em: Brasil" e "53 resultados").
- Paginação: `.jobs-search-pagination` com `li.jobs-search-pagination__indicator`; botões `Página 1`, `Página 2`, `Página 3` e `Ver próxima página` (rótulos por `aria-label`).

**Painel de detalhe (lado direito)**

- `.job-details-jobs-unified-top-card__tertiary-description-container` devolveu: "Santana de Parnaíba, São Paulo, Brasil · Anunciada novamente há 8 horas · 95 candidaturas Promovida por recrutador · Avaliando candidaturas".
- **"Anunciada novamente" significa vaga repostada.** Uma vaga antiga pode voltar a aparecer na janela de 24h. Quem decide se é nova é o SQLite, não o texto.
- A descrição fica dentro de `<article>`.
- O link do card selecionado tem a classe `disabled`; para abrir o detalhe, clique no título (`strong`), não no `<a>`.

### 2.3 Indeed

**URL de busca**

```
https://br.indeed.com/jobs?q=<termo>&fromage=1
```

Ao carregar, o Indeed acrescenta `vjk=<jk>` sozinho. A ordenação padrão é
"relevância - data". Para forçar por data existe um parâmetro `sort=date`, que
**não testei**.

**Cards**

- `div.job_seen_beacon`: 16 no DOM, 15 no texto da página. O card a mais é uma **isca invisível** (caixa 0×0, `data-jk` falso como `f1e2d3c4b5a67890`, link `/viewjob?jk=…`, título copiado de outra vaga; muda a cada carga). Só cards com área visível são vagas; clicar na isca tira a página da listagem (observado em 15/10/2026).
- `a.jcs-JobTitle[data-jk]`: `data-jk` com 16 caracteres hexadecimais, único por card.
- Seletores:

| Dado | Seletor |
| --- | --- |
| ID | `a.jcs-JobTitle` → atributo `data-jk` |
| Título | `a.jcs-JobTitle span[title]` (atributo `title`) ou o texto do link |
| Empresa | `[data-testid="company-name"]` |
| Local | `[data-testid="text-location"]` |
| Atributos e trecho | itens `li` dentro do card ("Tempo integral", salário, trecho da descrição) |

- **Painel de detalhe:** a captura real de 15/10/2026 usa `DESKTOP_EMBEDDED`; cada título é `a.jcs-JobTitle[data-jk]` com `role="button"` e o clique carrega `autoOpenTwoPaneViewjobResponse`, que contém `sanitizedJobDescription`. A descrição é lida no painel (`.jobsearch-RightPane`, `[data-testid="viewjob-job-content"]`) por `.simple-job-description-html`, sem abrir `/viewjob`; `#jobDescriptionText` e `.jobsearch-JobComponent-description` não existem mais nesse painel (verificado em 15/10/2026) e ficam só como reserva.
- **Não há data de publicação confiável no painel:** a resposta capturada tem `datePublished: null`. `fromage=1` e a deduplicação são o filtro de recência; o scanner não abre a URL individual só para preencher data.

**Paginação:** `nav[role="navigation"]` com `a[data-testid="pagination-page-current"]`, `pagination-page-2` até `pagination-page-5` e `pagination-page-next`.

**Banner de cookies:** `#onetrust-banner-sdk`. Ele não bloqueia a leitura do DOM. Escolha uma vez, manualmente, no Chrome dedicado: a escolha fica gravada no perfil e o script não precisa clicar em nada.

**Ruído da busca:** a página 1 trouxe vagas fora do tema (instrutor de equipamento de mina, professor-autor de conteúdo, gestão de qualidade técnica). **Apenas 2 dos 15 títulos continham "mecânic"** ("Engenheiro Mecânico de Projetos" e "Projetista / Desenhista Mecânico Industrial"). O filtro local por título é obrigatório e, sozinho, será restritivo.

**Anti-bot:** nesta sessão não houve verificação. Uma única visita não prova que as execuções recorrentes passarão.

### 2.4 Gupy

**Endpoint** (capturado ao clicar em "Próxima página" no portal; a primeira carga vem renderizada pelo servidor e não faz chamada JSON):

```
GET https://portal.gupy.io/api/job-search/jobs?jobName=<termo>&limit=<n>&offset=<n>
```

- A interface usa `limit=12`. Com `limit=50` a API respondeu 200 com todas as 20 vagas. O limite máximo não foi testado.
- Resposta:

```json
{
  "data": [
    {
      "id": 12657029,
      "name": "Engenheiro(a) de Manutenção Mecânica I",
      "description": "...",
      "careerPageName": "AXIA Energia",
      "city": "Rio de Janeiro",
      "state": "Rio de Janeiro",
      "workplaceType": "on-site",
      "type": "vacancy_type_effective",
      "publishedDate": "2026-10-08T11:04:27.057Z",
      "applicationDeadline": "2026-11-30T00:00:00.000Z",
      "jobUrl": "https://axiaenergia.gupy.io/job/<token>",
      "badges": { "friendlyBadge": true, "isPWD": false }
    }
  ],
  "pagination": { "total": 20, "limit": 50, "offset": 0 }
}
```

- `workplaceType` apareceu como `on-site`, `hybrid` e `remote`. `type` como `vacancy_type_effective` e `vacancy_legal_entity`.
- Ordenado por `publishedDate` decrescente. A vaga mais nova era de 08/10/2026 (**zero nas últimas 24h, uma nos últimos 7 dias**) e a mais antiga de 2022. A API devolve **tudo que combina com o termo**, inclusive vaga antiga, então a deduplicação pelo ID é indispensável.
- `jobUrl` leva um token em base64. Use-o como link; não tente interpretá-lo.
- O portal tem banner de cookies (não interagi).

## 3. Setup

### 3.1 Chrome dedicado (Windows)

Versões recentes do Chrome ignoram `--remote-debugging-port` no perfil padrão,
então o perfil dedicado é obrigatório. Crie `iniciar_chrome.bat`:

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir=C:\peneira-de-vagas\data\chrome-profile
```

Passos únicos, **manuais**, nesse Chrome:

1. Faça login no LinkedIn. O script nunca digita credenciais.
2. Abra a busca do Indeed e escolha uma opção no banner de cookies.
3. Confirme se o Indeed e o LinkedIn exibem resultados normalmente.

Para subir o Chrome no logon, coloque um atalho do `.bat` na pasta Inicializar
(`shell:startup`). A porta 9222 fica em `localhost`; não exponha para a rede.

### 3.2 Projeto

```
peneira-de-vagas/
├── main.py
├── config.toml
├── .env                  # TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (nunca versionado)
├── requirements.txt
├── sources/
│   ├── __init__.py
│   ├── linkedin.py
│   ├── indeed.py
│   └── gupy.py
├── filters.py
├── db.py
├── notify.py
└── tests/
    └── fixtures/
```

```
python -m venv .venv
.venv\Scripts\pip install playwright httpx python-dotenv pytest
```

Não rode `playwright install`: o projeto conecta ao Chrome existente.

**Telegram:** crie o bot com o `@BotFather`, copie o token e descubra o
`chat_id` mandando uma mensagem ao bot e abrindo `getUpdates` no navegador.
Esse passo é seu.

`requirements.txt`: fixe as versões instaladas (`pip freeze`).

### 3.3 `config.toml`

Os termos de exclusão abaixo vêm do ruído observado no Indeed. Ajuste.

```toml
[busca]
palavras = ["engenheiro mecânico"]

[filtro]
titulo  = ["engenheiro mecanico", "engenheira mecanica", "projetista mecanico"]
corpo   = ["engenheiro mecanico", "engenharia mecanica"]
excluir = ["instrutor", "professor"]

[limites]
paginas_por_fonte     = 3
detalhes_por_execucao = 15
```

A comparação é feita sem acento e sem diferença de maiúsculas. Um falso negativo
já visível: a vaga da GE Vernova exige "Engenharia Elétrica, Mecânica ou
Automação", e nenhum dos termos acima casaria. Isso é o que o filtro por regex
(ou palavras-chave mais soltas) resolveria; meça antes de decidir.

## 4. Código de referência

### 4.1 `sources/__init__.py`

```python
from dataclasses import dataclass


@dataclass
class Vaga:
    fonte: str
    id: str
    titulo: str
    empresa: str = ""
    local: str = ""
    link: str = ""
    trecho: str = ""
    publicada_em: str = ""  # ISO (Gupy) ou texto relativo (LinkedIn)


class FonteBloqueada(Exception):
    """CAPTCHA, login inesperado ou verificação anti-bot: encerra a fonte."""


class FonteQuebrada(Exception):
    """Seletor mudou ou zero resultados: encerra a fonte e alerta."""
```

### 4.2 `db.py`

```python
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS vagas (
  fonte TEXT NOT NULL, id TEXT NOT NULL, titulo TEXT, empresa TEXT,
  local TEXT, link TEXT, trecho TEXT, publicada_em TEXT,
  vista_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (fonte, id)
);
CREATE TABLE IF NOT EXISTS execucoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fonte TEXT NOT NULL,
  em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT, lidas INTEGER, novas INTEGER, erro TEXT
);
"""


def conectar(caminho="peneira-de-vagas.db"):
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def conhecidos(con, fonte):
    return {r["id"] for r in con.execute("SELECT id FROM vagas WHERE fonte = ?", (fonte,))}


def registrar(con, v):
    """Insere a vaga. Devolve True se era nova (não estava no banco)."""
    cur = con.execute(
        "INSERT OR IGNORE INTO vagas (fonte, id, titulo, empresa, local, link, trecho, publicada_em)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (v.fonte, v.id, v.titulo, v.empresa, v.local, v.link, v.trecho, v.publicada_em),
    )
    con.commit()
    return cur.rowcount == 1


def log(con, fonte, status, lidas=0, novas=0, erro=""):
    con.execute(
        "INSERT INTO execucoes (fonte, status, lidas, novas, erro) VALUES (?, ?, ?, ?, ?)",
        (fonte, status, lidas, novas, erro[:500]),
    )
    con.commit()
```

**Regra:** só registre vaga cujo título foi lido. No LinkedIn, um card não
renderizado tem ID mas não tem título; registrá-lo faria a vaga nunca mais ser
avaliada.

### 4.3 `filters.py`

```python
import unicodedata


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def contem(texto, termos):
    t = norm(texto)
    return any(norm(x) in t for x in termos)


def excluida(v, cfg):
    return contem(f"{v.titulo} {v.trecho}", cfg["filtro"]["excluir"])


def casa(v, cfg):
    f = cfg["filtro"]
    if excluida(v, cfg):
        return False
    return contem(v.titulo, f["titulo"]) or contem(v.trecho, f["corpo"])
```

### 4.4 `notify.py`

```python
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def enviar(texto):
    r = httpx.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage",
        json={
            "chat_id": os.environ["TELEGRAM_CHAT_ID"],
            "text": texto[:4000],
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    r.raise_for_status()


def vaga(v):
    enviar(f"{v.fonte.upper()} · {v.titulo}\n{v.empresa} — {v.local}\n{v.link}")


def alerta(msg):
    enviar(f"⚠️ Peneira de Vagas: {msg}")
```

A URL do Telegram carrega o token. Em `main.py`, silencie o log INFO do `httpx`,
senão o token vai para o `peneira-de-vagas.log`.

### 4.5 `sources/gupy.py`

```python
import httpx

from . import FonteQuebrada, Vaga

API = "https://portal.gupy.io/api/job-search/jobs"


def coletar(_page, cfg, conhecidos):
    vagas = []
    for palavra in cfg["busca"]["palavras"]:
        offset = 0
        while True:
            r = httpx.get(API, params={"jobName": palavra, "limit": 50, "offset": offset}, timeout=20)
            if r.status_code != 200:
                raise FonteQuebrada(f"Gupy respondeu HTTP {r.status_code}")
            corpo = r.json()
            itens = corpo["data"]
            for x in itens:
                vagas.append(Vaga(
                    fonte="gupy",
                    id=str(x["id"]),
                    titulo=x["name"],
                    empresa=x.get("careerPageName") or "",
                    local=f'{x.get("city") or ""}/{x.get("state") or ""}',
                    link=x.get("jobUrl") or "",
                    trecho=x.get("description") or "",
                    publicada_em=x.get("publishedDate") or "",
                ))
            offset += len(itens)
            if not itens or offset >= corpo["pagination"]["total"]:
                break
    return vagas
```

Se a Gupy devolver 403 ou um desafio, trate como falha. Não adicione
cabeçalhos para disfarçar o cliente (regra de projeto do `TECH_STACK.md`).
`publishedDate` permite ignorar vagas com mais de N dias, se quiser.

### 4.6 `sources/linkedin.py`

Esqueleto: seletores observados, fluxo Python não executado.

```python
import random
import time
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PWTimeout

import filters

from . import FonteBloqueada, FonteQuebrada, Vaga

URL = "https://www.linkedin.com/jobs/search/?keywords={kw}&f_TPR=r86400"
CARD = "li[data-occludable-job-id]"
TOPO = ".job-details-jobs-unified-top-card__tertiary-description-container"
BLOQUEIO_URL = ("/authwall", "/login", "/checkpoint", "/uas/")  # padrões conhecidos, não observados

LER_CARDS = """els => els.map(li => {
  const a = li.querySelector('a[href*="/jobs/view/"]');
  const t = (s) => (li.querySelector(s)?.innerText || '').trim();
  return {
    id: li.dataset.occludableJobId,
    renderizado: !!a,
    titulo: a ? (a.querySelector('strong')?.innerText || '').trim() : '',
    empresa: t('.artdeco-entity-lockup__subtitle'),
    local: t('.artdeco-entity-lockup__caption'),
  };
})"""


def _pausa(a=0.8, b=2.2):
    time.sleep(random.uniform(a, b))


def _checar(page):
    if any(p in page.url for p in BLOQUEIO_URL):
        raise FonteBloqueada(f"LinkedIn redirecionou para {page.url.split('?')[0]}")


def _ler_pagina(page):
    """Rola card a card e lê enquanto renderiza (não depende de o card continuar renderizado)."""
    achados = {}
    cards = page.locator(CARD)
    for i in range(cards.count()):
        cards.nth(i).scroll_into_view_if_needed()
        _pausa(0.25, 0.7)
        for d in page.locator(CARD).evaluate_all(LER_CARDS):
            if d["renderizado"] or d["id"] not in achados:
                achados[d["id"]] = d
    return achados.values()


def _detalhar(page, v):
    """Abre a vaga no painel direito: preenche data (texto relativo) e descrição."""
    page.locator(f'li[data-occludable-job-id="{v.id}"] a[href*="/jobs/view/"] strong').first.click()
    topo = page.locator(TOPO).first
    topo.wait_for(timeout=10000)
    v.publicada_em = topo.inner_text().strip()
    v.trecho = page.locator("article").first.inner_text()[:3000]
    _pausa(1, 2.5)


def coletar(page, cfg, conhecidos):
    vagas = []
    orcamento = cfg["limites"]["detalhes_por_execucao"]
    try:
        for palavra in cfg["busca"]["palavras"]:
            page.goto(URL.format(kw=quote(palavra)), wait_until="domcontentloaded")
            _pausa(2, 4)
            _checar(page)
            page.wait_for_selector(CARD, timeout=15000)
            for n in range(1, cfg["limites"]["paginas_por_fonte"] + 1):
                if n > 1:
                    botao = page.get_by_role("button", name=f"Página {n}", exact=True)
                    if botao.count() == 0:
                        break
                    primeiro = page.locator(CARD).first.get_attribute("data-occludable-job-id")
                    botao.click()
                    page.wait_for_function(
                        "old => document.querySelector('li[data-occludable-job-id]')"
                        "?.dataset.occludableJobId !== old",
                        arg=primeiro, timeout=15000,
                    )
                    _pausa(1.5, 3)
                    _checar(page)
                for d in _ler_pagina(page):
                    if not d["renderizado"] or not d["titulo"]:
                        continue
                    v = Vaga(fonte="linkedin", id=d["id"], titulo=d["titulo"], empresa=d["empresa"],
                             local=d["local"], link=f'https://www.linkedin.com/jobs/view/{d["id"]}/')
                    if v.id not in conhecidos and orcamento > 0 and not filters.excluida(v, cfg):
                        _detalhar(page, v)
                        orcamento -= 1
                    vagas.append(v)
    except PWTimeout as e:
        raise FonteQuebrada(f"LinkedIn: timeout esperando elemento ({e.__class__.__name__})")
    return vagas
```

O detalhe só pode ser aberto enquanto a página da lista que contém o card está
na tela, por isso `_detalhar` roda dentro do laço de páginas. Vagas novas além do
orçamento de 15 detalhes entram sem descrição (o filtro as avalia só pelo título).

### 4.7 `sources/indeed.py`

Esqueleto: seletores observados, fluxo Python não executado.

```python
import random
import re
import time
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PWTimeout

from . import FonteBloqueada, FonteQuebrada, Vaga

URL = "https://br.indeed.com/jobs?q={kw}&fromage=1"
CARD = "div.job_seen_beacon"
PROXIMO = 'a[data-testid="pagination-page-next"]'
SINAIS = re.compile(r"captcha|verifique que você é humano|just a moment|checking your browser", re.I)

LER = """els => els.map(b => {
  const a = b.querySelector('a.jcs-JobTitle[data-jk]');
  const t = (s) => (b.querySelector(s)?.innerText || '').trim();
  return {
    id: a?.dataset.jk || '',
    titulo: (a?.querySelector('span[title]')?.getAttribute('title') || a?.innerText || '').trim(),
    empresa: t('[data-testid="company-name"]'),
    local: t('[data-testid="text-location"]'),
    trecho: Array.from(b.querySelectorAll('li')).map(x => x.innerText.trim()).join(' | '),
  };
})"""


def _pausa(a=1.5, b=3.5):
    time.sleep(random.uniform(a, b))


def _checar(page):
    if SINAIS.search(page.locator("body").inner_text(timeout=5000)):
        raise FonteBloqueada("Indeed pediu verificação anti-bot")


def _primeiro_jk(page):
    return page.locator(CARD).first.locator("a.jcs-JobTitle").get_attribute("data-jk")


def coletar(page, cfg, conhecidos):
    vagas = []
    try:
        for palavra in cfg["busca"]["palavras"]:
            page.goto(URL.format(kw=quote(palavra)), wait_until="domcontentloaded")
            _pausa(2, 4)
            _checar(page)
            for n in range(1, cfg["limites"]["paginas_por_fonte"] + 1):
                page.wait_for_selector(CARD, timeout=15000)
                for d in page.locator(CARD).evaluate_all(LER):
                    if d["id"] and d["titulo"]:
                        vagas.append(Vaga(fonte="indeed", id=d["id"], titulo=d["titulo"],
                                          empresa=d["empresa"], local=d["local"], trecho=d["trecho"],
                                          link=f'https://br.indeed.com/viewjob?jk={d["id"]}'))
                if n == cfg["limites"]["paginas_por_fonte"] or page.locator(PROXIMO).count() == 0:
                    break
                antigo = _primeiro_jk(page)
                page.locator(PROXIMO).click()
                page.wait_for_function(
                    "old => document.querySelector('div.job_seen_beacon a.jcs-JobTitle')"
                    "?.dataset.jk !== old",
                    arg=antigo, timeout=15000,
                )
                _pausa()
                _checar(page)
    except PWTimeout as e:
        raise FonteQuebrada(f"Indeed: timeout esperando elemento ({e.__class__.__name__})")
    return vagas
```

O Indeed não tem data no card nem descrição completa; o filtro avalia título e
os itens `li` do card. Abrir o detalhe de cada vaga aumenta o tráfego e o risco
de verificação; só faça se medir que o trecho não basta.

### 4.8 `main.py`

```python
import argparse
import logging
import random
import time
import tomllib
import traceback

from playwright.sync_api import sync_playwright

import db
import filters
import notify
from sources import FonteBloqueada, FonteQuebrada, gupy, indeed, linkedin

logging.basicConfig(level=logging.INFO, filename="peneira-de-vagas.log",
                    format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # a URL do Telegram contém o token

FONTES = {"gupy": gupy, "linkedin": linkedin, "indeed": indeed}


def rodar_fonte(nome, modulo, page, con, cfg):
    conhecidos = db.conhecidos(con, nome)
    primeira_vez = not conhecidos
    vagas = modulo.coletar(page, cfg, conhecidos)
    if not vagas:
        raise FonteQuebrada("zero vagas lidas")
    novas = [v for v in vagas if db.registrar(con, v)]
    if primeira_vez:  # baseline: grava tudo, não notifica
        notify.alerta(f"{nome}: baseline com {len(novas)} vagas gravadas, sem notificações")
        return len(vagas), 0
    enviadas = 0
    for v in novas:
        if filters.casa(v, cfg):
            notify.vaga(v)
            enviadas += 1
    return len(vagas), enviadas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-atraso", action="store_true", help="pula o atraso aleatório (testes manuais)")
    ap.add_argument("--fontes", default="gupy,linkedin,indeed")
    args = ap.parse_args()
    escolhidas = args.fontes.split(",")

    with open("config.toml", "rb") as f:
        cfg = tomllib.load(f)
    if not args.sem_atraso:
        time.sleep(random.uniform(0, 300))
    con = db.conectar()

    with sync_playwright() as p:
        browser = None
        if {"linkedin", "indeed"} & set(escolhidas):
            try:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
            except Exception as e:
                notify.alerta(f"Chrome dedicado inacessível na porta 9222 ({type(e).__name__}); "
                              "LinkedIn e Indeed ignorados")

        for nome, modulo in FONTES.items():
            if nome not in escolhidas:
                continue
            usa_navegador = modulo is not gupy
            if usa_navegador and browser is None:
                continue
            page = browser.contexts[0].new_page() if usa_navegador else None
            try:
                lidas, enviadas = rodar_fonte(nome, modulo, page, con, cfg)
                db.log(con, nome, "ok", lidas, enviadas)
                logging.info("%s: %d lidas, %d notificadas", nome, lidas, enviadas)
            except (FonteBloqueada, FonteQuebrada) as e:
                db.log(con, nome, "falha", erro=str(e))
                logging.warning("%s: %s", nome, e)
                notify.alerta(f"{nome}: {e}")
            except Exception as e:
                db.log(con, nome, "erro", erro=traceback.format_exc())
                logging.exception("%s: erro inesperado", nome)
                notify.alerta(f"{nome}: erro inesperado ({type(e).__name__})")
            finally:
                if page:
                    page.close()


if __name__ == "__main__":
    main()
```

Cada fonte falha isolada: um bloqueio no Indeed não impede o LinkedIn e a Gupy.

## 5. Agendamento

Execuções às 8h, 10h, 12h, 14h, 16h e 18h. O atraso aleatório de 0 a 5 minutos
já está no `main.py`.

**Windows (Agendador de Tarefas):**

```
schtasks /Create /TN "Peneira de Vagas" /SC DAILY /ST 08:00 /RI 120 /DU 10:01 ^
  /TR "cmd /c cd /d C:\peneira-de-vagas && .venv\Scripts\python.exe main.py"
```

- `/RI 120` repete a cada 120 min e `/DU 10:01` mantém a repetição até as 18:01. **Confirme na interface do Agendador que a última execução prevista é a das 18:00.**
- A tarefa precisa rodar **com o usuário conectado** (o Chrome é uma janela), e o computador não pode hibernar entre 8h e 18h.
- Linux/Mac: `0 8-18/2 * * *`.

## 6. Testes

**Unitários (`pytest`):**
- `filters.py`: acentos, maiúsculas, exclusões, título versus corpo (inclua o caso GE Vernova).
- `db.py`: `registrar` devolve `True` na primeira vez e `False` na segunda.
- `gupy.py`: parse de uma resposta salva em `tests/fixtures/gupy.json` (salve uma resposta real).
- Seletores: salve o HTML de um card de cada fonte em `tests/fixtures/` e teste a extração com `page.set_content`.

**Integração (marker `integration`, manual; agente só com autorização prévia do usuário em LinkedIn/Indeed):** execução real contra os sites.

## 7. Ordem de implementação e critérios de aceite

Valores de referência de **14/10/2026**; mudam com o tempo.

1. **Banco, filtro e Telegram.** Teste: uma mensagem de teste chega no celular.
2. **Gupy.** `python main.py --fontes gupy --sem-atraso`. Esperado: 20 vagas lidas, baseline sem notificações; uma segunda execução devolve 0 novas. **Se der 403, pare e reavalie antes de seguir.**
3. **Indeed.** `--fontes indeed`. Esperado: 15–16 cards por página, IDs únicos. Confirme visualmente que o filtro de data está em "último dia".
4. **LinkedIn.** `--fontes linkedin`. Esperado: até 25 IDs por página; compare o total com "N resultados" do cabeçalho.
5. **Os três juntos**, uma execução com atraso e uma cheia pelo agendador.
6. **Alerta de falha.** Force o erro (feche o Chrome dedicado, ou quebre um seletor) e confirme o aviso no Telegram.

## 8. Riscos e pontos de atenção

- **LinkedIn logado em automação viola os termos de uso.** O risco de restrição da conta existe mesmo com volume baixo, e não sei dizer qual é o limite seguro hoje. Ao primeiro sinal de verificação ou aviso na conta, desligue a fonte.
- **Indeed:** a exploração não encontrou bloqueio, mas foi uma visita. Verificação recorrente é o cenário provável; o script encerra a fonte e avisa, nunca tenta resolver.
- **Seletores quebram.** Os `data-*`, `data-testid` e classes `artdeco-*` são mais estáveis que as classes com hash, mas nenhum é garantido. O alerta de "zero vagas lidas" é a defesa; mantenha-o.
- **Janela de tempo é a deduplicação.** A execução das 8h captura a noite sem lógica especial, e uma execução perdida é compensada na seguinte. "Anunciada novamente" no LinkedIn não é vaga nova; o SQLite decide.
- **Baseline na primeira execução** evita uma enxurrada de notificações com vagas antigas (a Gupy devolveria 20, de 2022 a 2026).
- **Filtro restritivo:** só 2 de 15 títulos do Indeed continham "mecânic". Comece com título **ou** corpo e meça os falsos positivos e negativos antes de apertar.
- **Conta e dados:** nunca versione `.env`, `peneira-de-vagas.db`, `peneira-de-vagas.log` nem `data/chrome-profile/`.

## 9. Pendências de decisão

- **SO:** assumido **Windows** pelo cabeçalho do navegador; confirme.
- **Palavras-chave e exclusões** definitivas (`config.toml`).
- **Local de execução:** PC próprio (assumido) ou VPS.
- **Indeed sem login e LinkedIn deslogado:** testar no perfil dedicado antes de depender deles.
