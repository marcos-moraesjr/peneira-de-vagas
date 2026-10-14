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
plano, as tarefas de cada fonte (LinkedIn e Indeed via navegador real/CDP; Gupy via API JSON), filtra,
deduplica no SQLite e expõe os resultados, que o front exibe. Um usuário, nada sai da máquina além das
requisições às três fontes.

## Fluxo

```
Front (React/Vite) ──fetch + tipos OpenAPI──▶ API (FastAPI) ──sqlite3──▶ SQLite (.db)
        ▲                                         │
        │  polling do andamento (TanStack Query)  ▼
        └───────────────────────────── serviço de execução (thread)
                                                  │
                  para cada fonte (LinkedIn → Indeed → Gupy), isolada:
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
| `POST /api/runs` | inicia a busca; `202 {id}`; `409` se há outra em andamento |
| `GET /api/runs?limit=` | histórico (mais recentes primeiro), cada um com suas `fontes` |
| `GET /api/runs/{id}` | andamento: `status` e, por fonte, `status`, `motivo`, `lidas`, `aprovadas`, `novas` |
| `GET /api/jobs?visto=&fonte=&q=&limit=&offset=` | vagas, mais recentes primeiro; `visto=false` = novas |
| `PATCH /api/jobs/{id}` | `{visto: bool}` |
| `POST /api/jobs/mark-seen` | marca como vistas todas as que casam com os filtros do corpo |
| `GET /api/keywords?tipo=` | lista palavras-chave (`busca`) e/ou exclusões (`exclusao`) |
| `POST /api/keywords` | `{termo, tipo}` → `201`; `422` se vazio, maior que `keyword_max_length` ou duplicado (sem acento/caixa) |
| `DELETE /api/keywords/{id}` | remove; `404` se não existe |
| `GET /api/scanners` | versão e estado (`ok`/`atencao`/`refazer`) de cada scanner; em `refazer`, traz a `instrucao` pronta para o Claude (`SCANNERS.md`) |
| `GET /api/config` | config em vigor (somente leitura): localidade, pesos, limites |

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
| `backend/app/routes/` | rotas finas: `health`, `runs`, `jobs`, `keywords`, `config` |
| `backend/app/services/` | `run_service` (orquestra uma execução, trava de execução única), `jobs` (consulta e marcação), `keywords` (CRUD, normalização, seed), `filters` (normalização, pontuação, exclusões) |
| `backend/app/services/runs.py` | consulta de execuções e resultado por fonte |
| `backend/app/sources/` | `gupy.py` (httpx), `browser.py` (`BrowserSource`, `PlaywrightNavigator`, `playwright_session`: CDP, ritmo, bloqueio), `linkedin.py` e `indeed.py` (adaptadores de site), `registry.py` (`build_sources`: LinkedIn → Indeed → Gupy), `types.py` (`Job`), `errors.py` (`SourceBlocked`, `SourceLayoutChanged`, `SourceEmpty`, `SourceUnavailable`) |
| `backend/app/schemas.py` | contratos Pydantic de toda a API |
| `backend/app/errors.py` | `DomainError` (422), `NotFound` (404), `Conflict` (409) |
| `backend/app/db.py` | `sqlite3`: conexão, esquema versionado (`schema_version`), inserção com dedup, consultas |
| `backend/app/config.py` | carrega e valida `config.toml` em objeto tipado |
| `backend/app/deps.py` | dependências injetáveis: `get_settings`, `get_connection`, `get_now` |
| `backend/config.toml` | parâmetros de busca, filtro, limites e pausas (sem segredos) |
| `backend/scanners.toml` | manifesto de versões dos scanners (versão, data da exploração, autor, referência); regras em `SCANNERS.md` |
| `backend/app/services/scanners.py` · `routes/scanners.py` | `load_manifest`, `evaluate` (estado de cada scanner) e a rota `/api/scanners` |
| `backend/scripts/export_openapi.py` | grava o OpenAPI em `frontend/src/api/openapi.json`; `npm run gen:api` gera `schema.d.ts` |
| `scripts/chrome-dedicado.ps1` | abre o Chrome dedicado (porta 9222 só em localhost, perfil `chrome-profile/`) |
| `backend/tests/` | pytest, um `test_<módulo>.py` por módulo; `conftest.py`: SQLite temporário, `Settings` e "agora" injetados; `samples/` (JSON/HTML salvos, sem dados pessoais) |
| `frontend/src/api/` | `client.ts` (`apiGet` tipado + `apiSend`), `hooks.ts`; `schema.d.ts` e `openapi.json` gerados e versionados |
| `frontend/src/features/` | `vagas` (lista, filtros, busca, painel de palavras-chave), `execucoes` (histórico e config) |
| `frontend/src/components/` | componentes comuns (`Tabs`, `ErrorBox`, `SourceBadge`, `ui.ts` com classes Tailwind compartilhadas) |
| `frontend/dist/` | build estático (gerado, não versionado) |
| `scripts/chrome-dedicado.*` | abre o Chrome dedicado (perfil e porta CDP) |
| `chrome-profile/` | perfil do Chrome dedicado (não versionado) |
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
| `fonte` | `str` | `linkedin`, `indeed` ou `gupy` |

Cada fonte expõe também `name` e `enrich(jobs) -> list[Job]` (abre o detalhe; na Gupy é identidade).
Falhas são exceções de `sources/errors.py` (com `motivo` e `detalhe`), nunca lista vazia disfarçada. **Zero
resultados** é decidido pelo serviço de execução (`SourceEmpty`, MVP §6.8); a fonte de navegador devolve `[]`
quando a página traz o aviso de "nenhum resultado" e levanta `SourceLayoutChanged` quando não há cards **nem**
o aviso. Exceção inesperada vira `erro_interno` sem derrubar as demais fontes.

LinkedIn e Indeed compartilham `sources/browser.py` (`BrowserSource`: paginação, rolagem, pausas, detecção de
bloqueio, detalhe), extraído porque há dois casos reais; cada site fornece um adaptador (`LinkedInSite`,
`IndeedSite`: URL de busca, `classify`, JS de extração, seletores de detalhe, `to_job`). O navegador real é
isolado em `PlaywrightNavigator`, o que permite testar o fluxo com um navegador simulado.

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
  e `location`/`l` **só se** a localidade estiver preenchida (a busca observada não envia local).
- **LinkedIn lê card a card** (`lazy_cards`): o `<li data-occludable-job-id>` já traz o ID, mas título e empresa
  só aparecem depois de rolar até ele (7–11 cards renderizados ao carregar, de 25). Card sem título é
  descartado e **nunca gravado**, para a vaga não deixar de ser avaliada depois. Indeed lê tudo de uma vez.
- Seletores observados: LinkedIn `a[href*="/jobs/view/"] strong` (título), `.artdeco-entity-lockup__subtitle`
  (empresa), `.artdeco-entity-lockup__caption` (local); Indeed `a.jcs-JobTitle[data-jk]` (ID e título em
  `span[title]`), `[data-testid="company-name"]`, itens `li` do card (trecho). Classes com hash não são usadas.
- "Anunciada novamente há N horas" no LinkedIn = vaga repostada; quem decide se é nova é o SQLite.
- O banner de cookies do Indeed não bloqueia a leitura; escolha uma opção uma vez, à mão, no Chrome dedicado.
- Pausas variáveis entre ações (e curtas ao rolar); uma aba por vez.
- Tela de login, CAPTCHA/verificação, página Cloudflare ou seletor ausente → exceção da fonte; **sem retentativa de contorno**.

## Filtro

Palavras-chave e exclusões vêm da tabela `keywords`, lidas **no início de cada execução** (edição vale na
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
| `jobs` | `id` PK, `fonte`, `id_da_vaga`, `titulo`, `empresa`, `link`, `trecho`, `pontos`, `run_id` FK, `encontrada_em`, `visto` (0/1) | `UNIQUE(fonte, id_da_vaga)` |
| `keywords` | `id` PK, `termo`, `termo_normalizado`, `tipo` (`busca`/`exclusao`), `criada_em` | `UNIQUE(termo_normalizado, tipo)` |
| `runs` | `id` PK, `inicio`, `fim`, `status` (`executando`/`concluida`) | |
| `run_sources` | `run_id` FK, `fonte`, `status` (`aguardando`/`buscando`/`ok`/`falha`), `motivo`, `detalhe`, `lidas`, `aprovadas`, `novas`, `scanner_versao` (versão do scanner usada; esquema v2) | `PRIMARY KEY(run_id, fonte)` |

Datas em ISO 8601 (UTC); o front formata em pt-BR com `Intl`. "Agora" é injetado, não lido no meio da regra.

## Configuração

Todo valor que ajusta comportamento mora aqui, nunca como literal (`CODE_QUALITY.md` §5). `config.toml` lido
por `backend/app/config.py` (`tomllib`); caminhos relativos partem da raiz do projeto. Host e porta são
argumentos do `uvicorn` (`127.0.0.1` por padrão; abrir para a rede é decisão registrada no TECH_STACK).

| Parâmetro | Default | Efeito |
| --- | --- | --- |
| `[geral] db_path` | `data/jobscanner.db` | arquivo SQLite (a pasta é criada se faltar) |
| `[geral] frontend_dist` | `frontend/dist` | build estático servido pela API em `/` |
| `[geral] log_dir` | `logs` | pasta do log |
| `[padrao] palavras_chave` | `["Engenheiro Mecânico"]` | seed da tabela `keywords` (tipo `busca`), aplicado **uma única vez** (flag `seeded`); depois disso, a lista vive no SQLite e é editada pelo front |
| `[padrao] exclusoes` | `[]` | seed das exclusões, mesma regra |
| `[busca] keyword_max_length` | `80` | tamanho máximo de um termo |
| `[busca] localidade` / `modalidade` | `""` / `""` | local (vazio = não envia, como na busca observada) e remoto/híbrido/presencial |
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
| `[api] jobs_page_size` | `50` | tamanho padrão da página de vagas |
| `[api] runs_history_limit` | `30` | execuções devolvidas por padrão no histórico |
| `[api] poll_interval_ms` | `2000` | intervalo do polling do front (exposto em `GET /api/config`) |
| `[versionamento] falhas_consecutivas` / `max_idade_dias` | `2` / `90` | falhas de quebra seguidas (na versão atual) que mandam refazer o scanner; idade que pede atenção |
| `[versionamento] motivos_de_quebra` | `seletor_nao_encontrado`, `zero_resultados`, `http_erro` | motivos que contam como scanner quebrado (bloqueios não contam) |
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
