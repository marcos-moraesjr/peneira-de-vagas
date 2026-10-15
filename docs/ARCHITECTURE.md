# JobScanner — Arquitetura

Fonte de verdade de fluxo, contratos, módulos, config e convenções. Stack e exclusões:
[`TECH_STACK.md`](TECH_STACK.md). Escopo: [`MVP.md`](MVP.md); ordem de construção: [`FASES.md`](FASES.md);
telas: [`DESIGN_BRIEF.md`](DESIGN_BRIEF.md).
Estado atual: **Fases 0–4 implementadas** (backend com 110+ testes e frontend com 41). Falta a validação do
usuário contra os sites reais (critérios 7 e 8 do MVP) e a Fase 5 (14 dias de uso). Endpoint da Gupy e
seletores do LinkedIn/Indeed seguem a exploração em DOM real de 14/10/2026 registrada em
[`EXPLORACAO_PLATAFORMAS.md`](EXPLORACAO_PLATAFORMAS.md) (§2); o código Python daquele documento foi **superado** por esta
arquitetura. Continua **não verificado**: a Gupy responder a `httpx` fora do navegador, o efeito real de
`fromage=1` no Indeed, a paginação por `start=` nos dois sites e o comportamento em perfil sem login.

## Visão geral

App **local** com front end (React) e API (FastAPI). O front dispara a busca; a API executa, em segundo
plano, as tarefas de cada fonte (LinkedIn, Indeed e Google via navegador real/CDP; Gupy via API JSON), filtra,
deduplica no SQLite e expõe os resultados, que o front exibe. Um usuário, nada sai da máquina além das
requisições às três fontes.

## Fluxo

```
Front (React/Vite) ──fetch + tipos OpenAPI──▶ API (FastAPI) ──sqlite3──▶ SQLite (.db)
        ▲                                         │
        │  polling do andamento (TanStack Query)  ▼
        └───────────────────────────── serviço de execução (thread)
                                                  │
                  para cada fonte (LinkedIn → Indeed → Google → Gupy), isolada
                  (em sequência; com `[navegador] abas_paralelas = true`, todas ao mesmo tempo, uma aba e uma conexão de banco por fonte):
                  sources/<fonte> ─▶ vagas (formato único) ─▶ filters ─▶ db (dedup)
                         └── falha explícita (SourceError) ─▶ run_sources
```

1. `POST /api/runs` cria a execução (`status=executando`) e dispara o serviço em segundo plano; devolve `202` com o id. Se já há execução em andamento: `409`.
2. O serviço percorre as fontes. Cada uma roda em `try/except` próprio: a falha de uma grava `run_sources` com `status=falha` e motivo, e **segue para a próxima**.
3. A fonte aplica a busca (palavra-chave + últimas 24h), lê a lista e devolve vagas no formato único.
4. `filters` pontua e descarta (exclusões, limiar). Só as aprovadas seguem.
5. Navegador: a página de **detalhe** é aberta apenas para vagas aprovadas, até o teto por execução.
6. `db` insere as aprovadas ainda desconhecidas `(fonte, id_da_vaga)`; essas são as **novas** (`visto=0`).
7. Ao fim, `run_sources` recebe lidas/aprovadas/novas e `runs` vira `concluida`.
8. O front consulta `GET /api/runs/{id}` em polling enquanto `executando`; ao concluir, invalida o cache e recarrega as vagas.
9. Cada execução grava a versão do scanner de cada fonte (`scanners.toml`); ao fim, se algum scanner atingiu o limite de falhas de quebra, registra aviso `refazer` no log (a tela mostra o alerta; ver `SCANNERS.md`).
10. Ao abrir (`lifespan`): cria/atualiza o esquema (cópia do `.db` antes de mudanças) e marca como `concluida` com falha `interrompida` qualquer execução que ficou `executando` (processo caiu).

Navegador: o Chrome dedicado é aberto **pelo usuário** (script de atalho), logado manualmente. A API só
conecta (`connect_over_cdp`); se a porta não responde, a fonte falha com `cdp_indisponivel`. Playwright usa
a API síncrona dentro da thread da execução.

## API

Tudo sob `/api`, JSON, só em `127.0.0.1`. Erros: `422` (entrada inválida), `404`, `409` (execução em andamento).

| Rota | Efeito |
| --- | --- |
| `GET /api/health` | `{status, db}` |
| `POST /api/runs` | inicia a busca; corpo opcional `{fontes}` (`null`/ausente = todas as plataformas; lista = só essas, rodam na ordem do registro; antes era `{fonte}` com um único nome); `202 {id}`; `409` se há outra em andamento; `422` se a lista for vazia ou tiver fonte inexistente (valor e esperado) |
| `POST /api/runs/{id}/cancel` | interrompe a execução em andamento (botão **Interromper**); `202 {id}`; `404` se não existe; `409` se já terminou. O cancelamento é cooperativo (um `threading.Event` por execução, em `app.state.cancel`): é checado antes de cada fonte e ao fim da busca e do detalhe, então a etapa em curso termina antes de parar. A fonte em andamento é descartada (nada é gravado) e as demais não começam: todas ficam `falha/interrompida`; a execução vira `concluida` |
| `GET /api/runs?limit=` | histórico (mais recentes primeiro), cada um com suas `fontes` |
| `DELETE /api/runs` | limpa o histórico: apaga **todas** as execuções (e seus `run_sources`); `200 {removidas}`; `409` se há execução em andamento. As vagas nunca são apagadas: ficam com `run_id` nulo (antes, execuções que originaram vagas eram preservadas e a limpeza não removia nada se todas tinham originado) |
| `GET /api/runs/{id}` | andamento: `status` e, por fonte, `status`, `motivo`, `lidas`, `aprovadas`, `novas` |
| `GET /api/jobs?visto=&fonte=&q=&max_dias=&ordenar=&direcao=&limit=&offset=` | vagas (cada uma com `localidade` e `publicada_em`). Sem `ordenar`: ordem padrão (execução mais recente, pontos, id). `ordenar` ∈ `titulo`, `empresa`, `localidade`, `publicada_em`, `encontrada_em`, `fonte`, `pontos` e `direcao` ∈ `asc` (padrão) / `desc`; texto compara sem acento nem maiúscula; vagas sem `publicada_em` ficam no fim nas duas direções; desempate por `id` decrescente; valor fora da lista → `422` com valor e esperado. A ordenação é no servidor porque a lista pagina; `visto=false` = novas. `max_dias=N` (inteiro ≥ 1, senão `422`) descarta da listagem as vagas com `publicada_em` anterior a *hoje − N dias* (comparação pela data, com o "agora" da API); **vagas sem `publicada_em` (LinkedIn, Indeed, Google) nunca são descartadas** por esse filtro. É filtro de exibição: nada é apagado |
| `PATCH /api/jobs/{id}` | `{visto: bool}` |
| `DELETE /api/jobs` | apaga todas as vagas (vistas e novas, sem filtro); `200 {removidas}`; `409` se há execução em andamento. Vaga excluída que reaparecer numa busca volta como nova (a deduplicação consulta a tabela `jobs`); "Limpar execuções" apaga o histórico independentemente das vagas |
| `POST /api/jobs/mark-seen` | marca como vistas todas as que casam com os filtros do corpo (`fonte`, `q`, `max_dias`) |
| `GET /api/keywords?tipo=` | lista palavras-chave (`busca`) e/ou exclusões (`exclusao`) **do conjunto ativo** |
| `POST /api/keywords` | `{termo, tipo}` → `201` (grava no conjunto ativo); `422` se vazio, maior que `keyword_max_length` ou duplicado **no conjunto** (sem acento/caixa) |
| `DELETE /api/keywords/{id}` | remove; `404` se não existe |
| `GET /api/conjuntos` | conjuntos de palavras-chave `[{id, nome, ativo}]`; exatamente um está ativo |
| `POST /api/conjuntos` | `{nome}` → `201`; cria um conjunto **vazio e já o ativa**; `422` se vazio, maior que `keyword_max_length` ou duplicado (sem acento/caixa) |
| `POST /api/conjuntos/{id}/ativar` | torna esse o conjunto ativo → `204`; `404` se não existe |
| `DELETE /api/conjuntos/{id}` | apaga o conjunto e suas palavras → `204`; se era o ativo, ativa o primeiro que sobrar; `404` se não existe; `422` se for o último |
| `GET /api/verificacao` | `{fontes}`: fontes de navegador paradas num bloqueio (CAPTCHA/Cloudflare/login), esperando o usuário concluir a verificação à mão |
| `POST /api/verificacao/{fonte}/confirmar` | botão **Já concluí a verificação**: libera a fonte, que reabre a página que bloqueou e segue a busca de onde parou; `204`; `409` se a fonte não está esperando. Cancelar a execução também libera a espera (a fonte vira `interrompida`) |
| `GET /api/browser` · `POST /api/browser/open` | se o Chrome dedicado está aberto (sonda CDP) · abre-o com perfil próprio e porta só local (`ja_aberto` se já estava); 422 se o Chrome não for achado em `chrome_paths` |
| `GET /api/scanners/instrucao?fonte=` | instrução pronta para o Claude Code **refazer só a documentação** das plataformas (todas ou uma), com versões atuais, palavras-chave cadastradas e regras de segurança; 422 se a fonte for desconhecida |
| `GET /api/scanners` | versão e estado (`ok`/`atencao`/`refazer`) de cada scanner; em `refazer`, traz a `instrucao` pronta para o Claude (`SCANNERS.md`) |
| `GET /api/config` | config em vigor: seções `busca`, `filtro`, `limites`, `ritmo`, `navegador` (só `abas_paralelas`), `api` (caminhos, `cdp_url`, `chrome_paths` e URLs das fontes ficam de fora) |
| `PUT /api/config` | corpo = o mesmo formato do `GET` (completo); valida, regrava só esses valores no `config.toml` (comentários e demais chaves intactos) e passa a valer na hora; `422` se inválido (arquivo intacto), `409` se há execução em andamento |

Motivos de falha de fonte (enum): `captcha`, `login`, `cloudflare`, `seletor_nao_encontrado`,
`zero_resultados`, `cdp_indisponivel`, `http_erro`, `interrompida`, `erro_interno`. Status por fonte durante
a execução: `aguardando`, `buscando`, `ok`, `falha` (a resposta também traz `detalhe`, texto técnico do erro).
Os `keywords` são semeados com `[padrao]` **uma única vez** (flag `seeded` na tabela `meta`): apagar tudo
depois não ressemeia.

## Estrutura e saídas

Ajustar aqui ao criar cada diretório.

| Caminho | Conteúdo |
| --- | --- |
| `backend/app/main.py` | `create_app()`: rotas sob `/api`, lifespan, tradução de erros, build estático em `/` |
| `backend/app/routes/` | rotas finas: `health`, `runs`, `jobs`, `keywords`, `conjuntos`, `config` |
| `backend/app/services/` | `run_service` (orquestra uma execução, trava de execução única), `jobs` (consulta e marcação), `keywords` (CRUD no conjunto ativo, normalização, seed), `conjuntos` (criar, ativar, remover), `filters` (normalização, pontuação, exclusões) |
| `backend/app/services/runs.py` | consulta de execuções e resultado por fonte |
| `backend/app/sources/` | `verification.py` (`VerificationGate`: espera/confirmação/cancelamento da verificação manual), `gupy.py` (httpx), `browser.py` (`BrowserSource`, `PlaywrightNavigator`, `playwright_session`: CDP, ritmo, bloqueio), `linkedin.py`, `indeed.py` e `google.py` (adaptadores de site; `GoogleSource` busca pelas palavras-chave e localidades do painel), `registry.py` (`build_sources`: LinkedIn → Indeed → Google → Gupy), `types.py` (`Job`), `errors.py` (`SourceBlocked`, `SourceLayoutChanged`, `SourceEmpty`, `SourceUnavailable`) |
| `backend/app/schemas.py` | contratos Pydantic de toda a API |
| `backend/app/errors.py` | `DomainError` (422), `NotFound` (404), `Conflict` (409) |
| `backend/app/db.py` | `sqlite3`: conexão, esquema versionado (`schema_version`), inserção com dedup, consultas |
| `backend/app/config.py` | carrega e valida `config.toml` em objeto tipado |
| `backend/app/deps.py` | dependências injetáveis: `get_settings`, `get_connection`, `get_now` |
| `backend/config.toml` | parâmetros de busca, filtro, limites e pausas (sem segredos) |
| `backend/scanners.toml` | manifesto de versões dos scanners (versão, data da exploração, autor, referência); regras em `SCANNERS.md` |
| `backend/app/services/scanners.py` · `routes/scanners.py` | `load_manifest`, `evaluate` (estado de cada scanner) e a rota `/api/scanners` |
| `backend/scripts/export_openapi.py` | grava o OpenAPI em `frontend/src/api/openapi.json`; `npm run gen:api` gera `schema.d.ts` |
| `scripts/chrome-dedicado.ps1` | alternativa manual ao botão: abre o Chrome dedicado (porta 9222 só em localhost, perfil `data/chrome-profile/`) |
| `backend/app/services/chrome.py` · `routes/browser.py` | `is_open`, `find_chrome`, `open_chrome`: sonda, descoberta e abertura do Chrome dedicado; `cdp_url` só aceita 127.0.0.1/localhost (validado na config) |
| `backend/tests/` | pytest, um `test_<módulo>.py` por módulo; `conftest.py`: SQLite temporário, `Settings` e "agora" injetados; `samples/` (JSON/HTML salvos, sem dados pessoais) |
| `frontend/src/api/` | `client.ts` (`apiGet` tipado + `apiSend`), `hooks.ts`; `schema.d.ts` e `openapi.json` gerados e versionados |
| `frontend/src/features/` | `vagas` (lista, filtros, busca, seletor de conjuntos e painéis de palavras-chave), `execucoes` (histórico e config) |
| `frontend/src/components/` | componentes comuns (`Tabs`, `ErrorBox`, `SourceBadge`, `ui.ts` com classes Tailwind compartilhadas) |
| `frontend/dist/` | build estático (gerado, não versionado) |
| `scripts/chrome-dedicado.*` | abre o Chrome dedicado (perfil e porta CDP) |
| `data/chrome-profile/` | perfil do Chrome dedicado (não versionado) |
| `data/jobscanner.db` | banco SQLite (não versionado) |
| `logs/` | log da execução (não versionado) |

## Contrato das fontes

Cada `sources/<fonte>.py` expõe `fetch(config, ...) -> list[Job]`. `Job`:

| Campo | Tipo | Observação |
| --- | --- | --- |
| `id` | `str` | identificador estável da vaga **na fonte** |
| `titulo` | `str` | |
| `empresa` | `str` | vazio permitido |
| `link` | `str` | URL canônica, sem parâmetros de rastreio |
| `trecho` | `str` | descrição ou resumo disponível (lista; detalhe, se aberto) |
| `fonte` | `str` | `linkedin`, `indeed`, `google` ou `gupy` |
| `localidade` | `str` | vazio permitido. Gupy: `city, state`; LinkedIn: legenda do card (local e modalidade); Indeed: `[data-testid="text-location"]` |
| `publicada_em` | `str \| None` | data de publicação em ISO 8601. Gupy: `publishedDate`. **LinkedIn: lida só na página de detalhe** (`.job-details-jobs-unified-top-card__tertiary-description-container`, texto relativo "há 8 horas" convertido para ISO por `parse_relative_date`; mês = 30 dias, ano = 365), portanto só nas vagas cujo detalhe foi aberto (teto `max_paginas_detalhe`); as demais ficam `None`. **Indeed: também só no detalhe**, procurando "Publicada há N dias"/"Posted N days ago"/"Publicada hoje" no texto da página (`body`; **seletor não observado**; "Ativa há…" e "mais de 30 dias" são ignorados). Google: `None`. `sources/relative_date.py` faz a conversão. Antes: LinkedIn e Indeed nunca preenchiam |

Cada fonte expõe também `name` e `enrich(jobs) -> list[Job]` (abre o detalhe; na Gupy e no Google é identidade).
Falhas são exceções de `sources/errors.py` (com `motivo` e `detalhe`), nunca lista vazia disfarçada. **Zero
resultados** é decidido pelo serviço de execução (`SourceEmpty`, MVP §6.8); a fonte de navegador devolve `[]`
quando a página traz o aviso de "nenhum resultado" e levanta `SourceLayoutChanged` quando não há cards **nem**
o aviso. Exceção inesperada vira `erro_interno` sem derrubar as demais fontes.

LinkedIn e Indeed compartilham `sources/browser.py` (`BrowserSource`: paginação, rolagem, pausas, detecção de
bloqueio, detalhe), extraído porque há dois casos reais; cada site fornece um adaptador (`LinkedInSite`,
`IndeedSite`: URL de busca, `classify`, JS de extração, seletores de detalhe, `to_job`). O navegador real é
isolado em `PlaywrightNavigator`, o que permite testar o fluxo com um navegador simulado.

### Google

- Fonte de navegador (`GoogleSite` + `GoogleSource`, subclasse de `BrowserSource`). **Mesma origem das demais fontes**: uma
  consulta por palavra-chave e por localidade do painel (`[busca] localidades`), montada como
  `"palavra-chave" ["localidade"] [("remote" OR "remoto" …)]` (sem restrição de site; os termos
  da modalidade escolhida em `[busca] modalidade`, de `[google] modalidade_termos`; aspas internas removidas). Enviada em `q`, com `tbs=qdr:d<N>` (dias, arredondando
  `janela_horas` para cima) e `start=` (passo `[google] page_size`).
- Resultado = link `#search a` com `h3` (título) e trecho em `[data-sncf]`/`.VwiC3b`. `id` e `link` = URL sem query e
  sem fragmento (`/url?q=` é desembrulhado; links do próprio Google são ignorados); `empresa` fica vazia.
- **Seletores não observados no DOM real** (scanner 0.x): frágeis até a plataforma ser documentada.
- Bloqueio: `/sorry`, "tráfego incomum"/"unusual traffic" → `captcha`; `consent.google.com` e `accounts.google.com`
  → `login`. Sem contorno; a aba fica aberta para o usuário resolver à mão (como no LinkedIn/Indeed).
- **Filtro local como nas demais fontes** (exclusões e pontuação sobre título e trecho do resultado; não há página de
  detalhe aberta). Antes (scanner 0.2.0): consulta booleana pronta em `[google] consultas` (um exemplo de
  desenvolvimento acabou sendo buscado), `local_filter = False` e `pontos = 0`. Depois (0.3.0): consulta montada da tela e
  filtro local aplicado. O Google limita a consulta a 32 palavras; as exclusões ficam só no filtro local, fora da consulta.

### Gupy

- `GET https://portal.gupy.io/api/job-search/jobs?jobName=&limit=&offset=` (+ `workplaceType` se a modalidade
  estiver na config), observado ao paginar o portal; **não documentado**, tratado como instável. `limit=50`
  funcionou (máximo não testado).
- Resposta: `data[]` (`id`, `name`, `description`, `careerPageName`, `city`, `state`, `workplaceType`,
  `publishedDate`, `jobUrl`…) e `pagination.total`. Campo ausente → `SourceLayoutChanged`; HTTP ≠ 200
  (inclusive 403) → `SourceUnavailable`/`http_erro`, **sem cabeçalhos para disfarçar o cliente**.
- A API devolve **tudo** que casa com o termo, inclusive vagas antigas (2022…) e sem filtro de recência:
  na primeira execução, quase tudo aparece como "nova"; a deduplicação cobre as seguintes.
- `jobUrl` leva um token em base64: usado como link, sem interpretar (a query string é removida).

### LinkedIn e Indeed

- URL de busca montada da config: `keywords`/`q`, recência (`f_TPR=r86400` / `fromage=1`), `start` para paginar
  e `location`/`l` **só se** houver localidade (a busca observada não envia local). **Uma busca por palavra-chave e por
  localidade** de `[busca] localidades` (sem nenhuma, uma única busca sem local); o teto `max_vagas_lista` vale para o conjunto.
  A Gupy não filtra por localidade; o Google a escreve na consulta (entre aspas), uma busca por localidade.
- **LinkedIn lê card a card** (`lazy_cards`): o `<li data-occludable-job-id>` já traz o ID, mas título e empresa
  só aparecem depois de rolar até ele (7–11 cards renderizados ao carregar, de 25). Card sem título é
  descartado e **nunca gravado**, para a vaga não deixar de ser avaliada depois. Indeed lê tudo de uma vez.
- Seletores observados: LinkedIn `a[href*="/jobs/view/"] strong` (título), `.artdeco-entity-lockup__subtitle`
  (empresa), `.artdeco-entity-lockup__caption` (local); Indeed `a.jcs-JobTitle[data-jk]` (ID e título em
  `span[title]`), `[data-testid="company-name"]`, `[data-testid="text-location"]` (local), itens `li` do card (trecho). Classes com hash não são usadas.
- "Anunciada novamente há N horas" no LinkedIn = vaga repostada; quem decide se é nova é o SQLite.
- O banner de cookies do Indeed não bloqueia a leitura; escolha uma opção uma vez, à mão, no Chrome dedicado.
- Pausas variáveis entre ações (e curtas ao rolar); uma aba por vez.
- Tela de login, CAPTCHA/verificação, página Cloudflare ou seletor ausente → exceção da fonte; **sem retentativa de contorno**.
- **Bloqueio: a fonte espera o usuário** (`VerificationGate`, `[navegador] espera_verificacao_s`). A aba fica aberta, a tela mostra o aviso com o botão **Já concluí a verificação** e, ao confirmar, a fonte reabre a página que bloqueou e segue de onde parou (o que já foi lido é mantido). Se o bloqueio persistir, volta a esperar; sem confirmação no prazo, ou sem portão, vale o comportamento abaixo. Antes: o bloqueio encerrava a fonte na hora. Nada é resolvido ou contornado pelo programa.
- **Bloqueio (`SourceBlocked`) sem confirmação mantém a aba aberta** no Chrome dedicado, para o usuário concluir a verificação à
  mão; a próxima execução abre uma aba nova (antes: a aba era sempre fechada). Outros erros e o sucesso continuam
  fechando a aba. A aba deixada aberta é responsabilidade do usuário fechar.

## Filtro

Palavras-chave e exclusões vêm da tabela `keywords`, **só do conjunto ativo** (tabela `conjuntos`; antes eram uma lista única global), lidas **no início de cada execução** (edição vale na
busca seguinte). Cada palavra-chave `busca` gera uma consulta por fonte (mais termos = mais páginas lidas,
limitadas por `max_vagas_lista`); a mesma lista pontua o filtro local.

1. **Normalização**: minúsculas, sem acento (`unicodedata`), espaços colapsados.
2. **Exclusões**: qualquer termo excluído em título ou trecho descarta a vaga.
3. **Pontuação**: `peso_titulo` por palavra-chave no título + `peso_descricao` no trecho (cada termo conta uma vez).
4. **Limiar**: aprovada se `pontos >= min_score`.

Casamento: um termo casa quando **todas as suas palavras** aparecem no texto, **em qualquer ordem e ignorando plural/gênero** (`engenheira`/`engenheiros` ≡ `engenheiro`, sem stemming além disso: `engenharia` não casa `engenheiro`)
(assim "Engenheiro Mecânico" casa "Engenheira Mecânica" e "Mecânico — Engenheiro de Projetos").
Qualquer exclusão (mesmo critério) em título **ou** trecho descarta.
Fluxo no serviço: filtra a lista → descarta as já conhecidas → abre detalhe das novas (até `max_paginas_detalhe`)
→ **reavalia com a descrição completa** (uma exclusão que só aparece no detalhe descarta a vaga) → grava.

## Dados

### Modelo

SQLite via `sqlite3`, `PRAGMA foreign_keys=ON`; esquema versionado em `schema_version`. Cópia do `.db`
antes de qualquer mudança de esquema.

| Tabela | Colunas | Restrições |
| --- | --- | --- |
| `jobs` | `id` PK, `fonte`, `id_da_vaga`, `titulo`, `empresa`, `link`, `trecho`, `pontos`, `run_id` FK (anulável, `ON DELETE SET NULL`; esquema v5), `encontrada_em`, `localidade` (`''` se a fonte não informa), `publicada_em` (NULL se não informa), `visto` (0/1) | `UNIQUE(fonte, id_da_vaga)` |
| `conjuntos` (esquema v4) | `id` PK, `nome`, `nome_normalizado` (único), `ativo` (0/1), `criada_em` | índice único parcial: no máximo um `ativo=1`; a migração cria o conjunto `Padrão` (ativo) |
| `keywords` | `id` PK, `termo`, `termo_normalizado`, `tipo` (`busca`/`exclusao`), `criada_em`, `conjunto_id` FK (`ON DELETE CASCADE`) | `UNIQUE(conjunto_id, termo_normalizado, tipo)` (antes `UNIQUE(termo_normalizado, tipo)`); a migração 4 move as palavras existentes para o `Padrão` |
| `runs` | `id` PK, `inicio`, `fim`, `status` (`executando`/`concluida`) | |
| `run_sources` | `run_id` FK, `fonte`, `status` (`aguardando`/`buscando`/`ok`/`falha`), `motivo`, `detalhe`, `lidas`, `aprovadas`, `novas`, `scanner_versao` (versão do scanner usada; esquema v2) | `PRIMARY KEY(run_id, fonte)` |

Datas em ISO 8601 (UTC); o front formata em pt-BR com `Intl`. "Agora" é injetado, não lido no meio da regra.

## Configuração

Todo valor que ajusta comportamento mora aqui, nunca como literal (`CODE_QUALITY.md` §5). `config.toml` lido
por `backend/app/config.py` (`tomllib`) e editável pela aba Configurações **só** nas seções `busca`, `filtro`, `limites`,
`ritmo`, `api` e, de `navegador`, apenas `abas_paralelas` (`PUT /api/config`; escrita em `services/config_edit.py`, sem biblioteca: troca só o valor da linha).
Antes: `janela_horas`, `trecho_max_chars`, pesos e `poll_interval_ms` não tinham limite; agora exigem `> 0` (pesos, `min_score` e pausas, `>= 0`); caminhos relativos partem da raiz do projeto. Host e porta são
argumentos do `uvicorn` (`127.0.0.1` por padrão; abrir para a rede é decisão registrada no TECH_STACK).

| Parâmetro | Default | Efeito |
| --- | --- | --- |
| `[geral] db_path` | `data/jobscanner.db` | arquivo SQLite (a pasta é criada se faltar) |
| `[geral] frontend_dist` | `frontend/dist` | build estático servido pela API em `/` |
| `[geral] log_dir` | `logs` | pasta do log |
| `[padrao] palavras_chave` | `["Engenheiro Mecânico"]` | seed da tabela `keywords` (tipo `busca`, conjunto ativo), aplicado **uma única vez** (flag `seeded`); depois disso, a lista vive no SQLite e é editada pelo front |
| `[padrao] exclusoes` | `[]` | seed das exclusões, mesma regra |
| `[busca] keyword_max_length` | `80` | tamanho máximo de um termo |
| `[busca] localidades` / `modalidade` | `[]` / `[]` | lista de cidades ou estados (`"Campinas, SP"`, `"Minas Gerais"`; textos não vazios, sem repetição ignorando caixa; vazia = não envia local, como na busca observada), editável na aba Configurações; e lista de `remoto`/`hibrido`/`presencial` (vazia = todas). Antes: `localidade`, um único texto (`""`) e `modalidade` um único texto (`"remoto"`…); LinkedIn envia `f_WT=2,3`, Gupy faz uma busca por modalidade |
| `[busca] janela_horas` | `24` | filtro de recência da própria busca (onde a fonte permite) |
| `[filtro] peso_titulo` / `peso_descricao` | `3` / `1` | pontos por termo no título e no trecho |
| `[filtro] min_score` | `3` | pontuação mínima para aprovar |
| `[limites] max_paginas_detalhe` | `15` | teto de páginas de detalhe abertas por execução |
| `[limites] max_vagas_lista` | `100` | teto de vagas lidas por fonte |
| `[filtro] trecho_max_chars` | `4000` | tamanho máximo do trecho/descrição guardado |
| `[ritmo] rolagem_min_s` / `rolagem_max_s` | `0.25` / `0.7` | pausa ao rolar a lista card a card (LinkedIn) |
| `[ritmo] pausa_min_s` / `pausa_max_s` | `2` / `6` | pausa aleatória entre ações no navegador |
| `[geral] backup_dir` | `backups` | cópia do `.db` antes de migrar o esquema |
| `[linkedin]` / `[indeed]` `base_url`, `page_size` | URL de busca e passo de paginação (`start`) | |
| `[navegador] cdp_url` | `http://127.0.0.1:9222` | endereço do Chrome dedicado (só `localhost`) |
| `[navegador] timeout_s` | `30` | espera máxima por página/elemento |
| `[navegador] espera_verificacao_s` | `600` | tempo que a fonte espera o usuário concluir a verificação e confirmar; esgotado (ou sem confirmar), falha como antes. Antes: o bloqueio encerrava a fonte na hora |
| `[navegador] abas_paralelas` | `false` | `true`: as fontes rodam ao mesmo tempo, uma aba por plataforma (cada aba mantém as próprias pausas). Antes: sempre em sequência, sem esta chave |
| `[navegador] probe_timeout_s` / `chrome_paths` | `1.5` / caminhos do Chrome (Windows, Linux, macOS) | espera ao sondar o CDP; onde procurar o Chrome para o botão "Abrir Chrome dedicado" (o primeiro que existir) |
| `[geral] chrome_profile_dir` | `data/chrome-profile` | perfil do Chrome dedicado (nunca o pessoal) |
| `[api] jobs_page_size` | `50` | tamanho padrão da página de vagas |
| `[api] runs_history_limit` | `30` | execuções devolvidas por padrão no histórico |
| `[api] poll_interval_ms` | `2000` | intervalo do polling do front (exposto em `GET /api/config`) |
| `[versionamento] falhas_consecutivas` / `max_idade_dias` | `2` / `90` | falhas de quebra seguidas (na versão atual) que mandam refazer o scanner; idade que pede atenção |
| `[versionamento] motivos_de_quebra` | `seletor_nao_encontrado`, `zero_resultados`, `http_erro` | motivos que contam como scanner quebrado (bloqueios não contam) |
| `[google] base_url`, `page_size` | `https://www.google.com/search`, `10` | URL de busca e passo de paginação (`start`) |
| `[google] modalidade_termos` | `remoto`, `hibrido`, `presencial` → termos em inglês e português | palavras que a consulta usa para cada modalidade de `[busca] modalidade`; as três chaves, cada uma com lista não vazia |
| `[gupy] base_url`, `page_size`, `timeout_s` | `portal.gupy.io/api/job-search/jobs`, `50`, `20` | endpoint (parâmetros `jobName`, `limit`, `offset`, `workplaceType`), página e timeout. A Gupy não tem filtro de recência (a deduplicação cobre) nem de localidade nesta versão |

Os valores `(a definir)` dependem das decisões em aberto de `MVP.md` §11. Parâmetro novo é registrado aqui
na mesma sessão.

## Regras de negócio

Vivem no `MVP.md` §6 (nova × vista, filtro em duas passadas, detalhe só se passar, falha explícita,
execução única). Alterar uma delas: registrar aqui o **antes e o depois** e abrir entrada em `LESSONS.md`
se for mudança de comportamento.

## Uso programático

Comandos de execução e testes: [README](../README.md).

## Convenções

- **Identidade da vaga**: sempre o par `(fonte, id_da_vaga)`; link nunca é chave.
- **Datas**: ISO 8601 em UTC no banco e na API; "agora" injetado, nunca lido no meio da regra.
- **Texto**: normalização só no `filters`; fontes devolvem o texto original.
- **Logging**: módulo `logging` da stdlib; sem cookies nem conteúdo de página nas mensagens.
- **Erros**: exceção própria por causa (`sources/errors.py`); a mensagem traz valor ofensor e esperado.
- **Camadas**: rota → serviço → fonte/banco (`CODE_QUALITY.md` §4); rota não contém regra; serviço não conhece HTTP.
- **Frontend** não repete regra de negócio: exibe e envia. Tipos gerados do OpenAPI. Estado do servidor no TanStack Query; UI local em `useState`.
- **Segurança**: API e porta CDP só em `127.0.0.1`; perfil do Chrome dedicado.

Testes e dependências: [CODE_QUALITY.md](CODE_QUALITY.md) §1 e [TECH_STACK.md](TECH_STACK.md).
