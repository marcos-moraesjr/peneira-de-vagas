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
                  para cada fonte (LinkedIn → Indeed → Gupy), isolada
                  (em sequência; com `[navegador] abas_paralelas = true`, todas ao mesmo tempo, uma aba e uma conexão de banco por fonte):
                  sources/<fonte> ─▶ vagas (formato único) ─▶ filters ─▶ db (dedup)
                         └── falha explícita (SourceError) ─▶ run_sources
```

1. `POST /api/runs` cria a execução (`status=executando`) e dispara o serviço em segundo plano; devolve `202` com o id. Se já há execução em andamento: `409`.
2. O serviço percorre as fontes. Cada uma roda em `try/except` próprio: a falha de uma grava `run_sources` com `status=falha` e motivo, e **segue para a próxima**.
3. A fonte aplica a busca (palavra-chave + últimas 24h), lê a lista e devolve vagas no formato único.
4. **Triagem pela lista** (título e trecho do card): só exclusões, localidade e modalidade descartam. A pontuação **não** corta aqui.
5. Navegador: a página de **detalhe** é aberta para todas as vagas que passaram na triagem e ainda são desconhecidas `(fonte, id_da_vaga)`.
6. `filters` pontua com o detalhe (exclusões, `busca` + `ranking`, limiar) e `db` insere as aprovadas; essas são as **novas** (`visto=0`). Vaga reprovada só no detalhe não é gravada (e, por isso, tem a página aberta de novo na próxima execução).
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
| `GET /api/runs?limit=` | histórico (mais recentes primeiro), cada um com suas `fontes` |
| `DELETE /api/runs/{id}` | exclui uma execução (botão **Excluir** da linha, com confirmação) e seus `run_sources`; `200 {removidas: 1}`; `404` se não existe; `409` se ela está em andamento. As vagas são mantidas (`run_id` nulo) |
| `DELETE /api/runs` | limpa o histórico: apaga **todas** as execuções (e seus `run_sources`); `200 {removidas}`; `409` se há execução em andamento. As vagas nunca são apagadas: ficam com `run_id` nulo (antes, execuções que originaram vagas eram preservadas e a limpeza não removia nada se todas tinham originado) |
| `GET /api/runs/{id}` | andamento: `status` e, por fonte, `status`, `motivo`, `lidas`, `aprovadas`, `novas` |
| `GET /api/jobs?conjunto_id=&visto=&fonte=&q=&cidade=&estado=&modalidade=&max_dias=&ordenar=&direcao=&limit=&offset=` | vagas **de um conjunto**: `conjunto_id` escolhe o conjunto (inexistente → `404`); omitido, vale o conjunto ativo. Cada vaga (cada uma com `localidade`, `cidade`, `estado`, `modalidade`, `palavra_chave` e `publicada_em`; `cidade` e `estado` (sigla UF) são derivados do texto livre da `localidade` por `split_localidade` em `services/localizacao.py`, não são colunas do banco; vazio quando a fonte não informa). `cidade` e `estado`: filtram as já encontradas pela cidade (contém, sem acento nem maiúscula) e pela sigla da UF (contém, sem diferenciar caixa); `modalidade` ∈ `remoto`, `hibrido`, `presencial` (outro valor → `422` com valor e esperado); vazio = sem filtro. `POST /api/jobs/mark-seen` aceita os mesmos três. Sem `ordenar`: ordem padrão (execução mais recente, pontos, id). `ordenar` ∈ `titulo`, `empresa`, `localidade`, `cidade`, `estado`, `modalidade`, `palavra_chave`, `publicada_em`, `encontrada_em`, `fonte`, `pontos` e `direcao` ∈ `asc` (padrão) / `desc`; texto compara sem acento nem maiúscula; vagas sem `publicada_em` ficam no fim nas duas direções; desempate por `id` decrescente; valor fora da lista → `422` com valor e esperado. A ordenação é no servidor porque a lista pagina; `visto=false` = novas. `max_dias=N` (inteiro ≥ 1, senão `422`) descarta da listagem as vagas com `publicada_em` anterior a *hoje − N dias* (comparação pela data, com o "agora" da API); **vagas sem `publicada_em` (LinkedIn, Indeed) nunca são descartadas** por esse filtro. É filtro de exibição: nada é apagado |
| `PATCH /api/jobs/{id}` | `{visto: bool}` |
| `DELETE /api/jobs?conjunto_id=` | apaga todas as vagas **do conjunto** (padrão: o ativo; vistas e novas, sem filtro); `200 {removidas}`; `409` se há execução em andamento. Vaga excluída que reaparecer numa busca volta como nova (a deduplicação consulta a tabela `jobs`); "Limpar execuções" apaga o histórico independentemente das vagas |
| `POST /api/jobs/mark-seen` | marca como vistas todas as que casam com os filtros do corpo (`fonte`, `q`, `cidade`, `estado`, `modalidade`, `max_dias`) **no conjunto** de `conjunto_id` (padrão: o ativo) |
| `GET /api/keywords?tipo=` | lista palavras-chave da busca (`busca`, viram queries), de ranking (`ranking`, só pontuam) e/ou exclusões (`exclusao`) **do conjunto ativo** |
| `POST /api/keywords` | `{termo, tipo}` → `201` (grava no conjunto ativo); `422` se vazio, maior que `keyword_max_length`, acima de `max_termos_busca` (só `busca`; `ranking` não tem teto) ou duplicado **no mesmo grupo do conjunto** (sem acento/caixa; o mesmo termo pode estar em `busca` e em `ranking`) |
| `DELETE /api/keywords/{id}` | remove; `404` se não existe |
| `GET /api/conjuntos` | conjuntos de palavras-chave `[{id, nome, ativo}]`; exatamente um está ativo |
| `POST /api/conjuntos` | `{nome}` → `201`; cria um conjunto **vazio e já o ativa**; `422` se vazio, maior que `keyword_max_length` ou duplicado (sem acento/caixa) |
| `PATCH /api/conjuntos/{id}` | `{nome}` → `200` com `{id, nome, ativo}`; troca o nome mantendo palavras e estado ativo; `404` se não existe; `422` se vazio, maior que `keyword_max_length` ou igual (sem acento/caixa) ao nome de **outro** conjunto (mudar só a caixa/acento do próprio nome é permitido) |
| `POST /api/conjuntos/{id}/copiar` | `{nome}` → `201` com `{id, nome, ativo}`; cria um conjunto com **todas as palavras** do original (`busca`, `ranking` e `exclusao`) e já o ativa; o original não muda; `404` se o original não existe; `422` nas mesmas condições de `POST /api/conjuntos` (nome vazio, longo ou repetido) |
| `POST /api/conjuntos/{id}/ativar` | torna esse o conjunto ativo → `204`; `404` se não existe |
| `DELETE /api/conjuntos/{id}` | apaga o conjunto e suas palavras → `204`; se era o ativo, ativa o primeiro que sobrar; `404` se não existe; `422` se for o último |
| `GET /api/verificacao` | `{fontes}`: fontes de navegador paradas num bloqueio (CAPTCHA/Cloudflare/login), esperando o usuário concluir a verificação à mão |
| `POST /api/verificacao/{fonte}/confirmar` | botão **Já concluí a verificação**: libera a fonte, que reabre a página que bloqueou e segue a busca de onde parou; `204`; `409` se a fonte não está esperando. |
| `GET /api/browser` · `POST /api/browser/open` | se o Chrome dedicado está aberto (sonda CDP) · abre-o com perfil próprio e porta só local (`ja_aberto` se já estava); 422 se o Chrome não for achado em `chrome_paths` |
| `GET /api/scanners/instrucao?fonte=` | instrução pronta para o Claude Code **refazer só a documentação** das plataformas (todas ou uma), com versões atuais, palavras-chave cadastradas e regras de segurança; 422 se a fonte for desconhecida |
| `GET /api/scanners` | versão e estado (`ok`/`atencao`/`refazer`) de cada scanner; em `refazer`, traz a `instrucao` pronta para o Claude (`SCANNERS.md`) |
| `GET /api/config` | config em vigor: seções `busca` (inclui `max_termos_busca`), `filtro`, `limites` (`max_paginas_por_termo`), `ritmo`, `navegador` (só `abas_paralelas`), `api` (caminhos, `cdp_url`, `chrome_paths` e URLs das fontes ficam de fora) |
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
| `backend/app/services/` | `run_service` (orquestra uma execução, trava de execução única), `jobs` (consulta e marcação), `keywords` (CRUD no conjunto ativo, normalização, seed), `conjuntos` (criar, copiar, renomear, ativar, remover), `filters` (normalização, pontuação, exclusões) |
| `backend/app/services/runs.py` | consulta de execuções e resultado por fonte |
| `backend/app/sources/` | `verification.py` (`VerificationGate`: espera/confirmação da verificação manual), `gupy.py` (httpx), `browser.py` (`BrowserSource`, `PlaywrightNavigator`, `playwright_session`: CDP, ritmo, bloqueio), `linkedin.py` e `indeed.py` (adaptadores de site), `registry.py` (`build_sources`: LinkedIn → Indeed → Gupy), `types.py` (`Job`), `errors.py` (`SourceBlocked`, `SourceLayoutChanged`, `SourceEmpty`, `SourceUnavailable`) |
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
| `frontend/src/features/` | `vagas` (lista paginada por números de página (`Pagination`: `limit` e `offset` da API), filtros, busca, seletor de conjuntos e painéis de palavras-chave), `execucoes` (histórico em tabela ordenável pelo cabeçalho, detalhe por fonte em card ao clicar, botão de excluir na linha, e config) |
| `frontend/src/components/` | componentes comuns (`Tabs`, `ErrorBox`, `SourceBadge`, `ui.ts` com classes Tailwind compartilhadas) |
| `frontend/public/`, `frontend/src/index.css` | ícone da marca Peneira e tokens de identidade (variáveis `--pn-*`, temas claro e escuro via `data-theme`, escolhido pelo botão da barra (`ThemeToggle`, salvo em `localStorage` `peneira-tema`) ou, sem escolha, pelo `prefers-color-scheme` em `index.html`; mapeadas no `@theme` do Tailwind; fonte única Noto Sans empacotada (`@fontsource/noto-sans`, pesos 400–700; a do Indeed), com a pilha do sistema como reserva) |
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
| `fonte` | `str` | `linkedin`, `indeed` ou `gupy` |
| `palavra_chave` | `str` | primeira palavra-chave do conjunto ativo cuja busca devolveu a vaga (`BrowserSource`/`GupySource` a gravam ao juntar os termos; vaga achada por vários termos fica com o primeiro); `""` em vagas gravadas antes do esquema v7 |
| `localidade` | `str` | vazio permitido. Gupy: `city, state`; LinkedIn: legenda do card (local e modalidade); Indeed: `[data-testid="text-location"]` |
| `publicada_em` | `str \| None` | data de publicação em ISO 8601. Gupy: `publishedDate`. **LinkedIn: lida só na página de detalhe** (`.job-details-jobs-unified-top-card__tertiary-description-container`, texto relativo "há 8 horas" convertido para ISO por `parse_relative_date`; mês = 30 dias, ano = 365), e o detalhe agora é aberto para todas as vagas novas (sem teto; antes só as primeiras `max_paginas_detalhe` = 15 tinham data); só vaga cujo detalhe não trouxe a data fica `None`. **Indeed: também só no detalhe**, primeiro `datePosted` do JSON-LD (`script[type="application/ld+json"]`, ISO exato, observado no HTML real) e, na reserva, procurando "Publicada há N dias"/"Posted N days ago"/"Publicada hoje" no texto da página (`body`; **seletor não observado**; "Ativa há…" e "mais de 30 dias" são ignorados; aceita "Publicada/Publicado/Postado/Posted"). **Fallback comum (LinkedIn e Indeed):** sem data em nenhum seletor, `find_published_line` procura no texto da página uma linha (separada por quebra de linha, "·" ou "|") que seja inteira a data, sem depender de classe CSS. Vagas abertas no detalhe sem data geram aviso no log da fonte. `sources/relative_date.py` faz a conversão. Antes: só o seletor do LinkedIn e o regex "Publicada/Posted" do Indeed, sem fallback |

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

- URL de busca montada da config: `keywords`/`q`, recência (`f_TPR=r86400` / `fromage=1`) e `start` para paginar.
  **Localidade e modalidade não vão na busca** (nem `location`/`l`, nem `f_WT`, nem `workplaceType` da Gupy): as
  plataformas as tratam de formas diferentes (ou nem filtram). Uma busca por palavra-chave; o limite `max_paginas_por_termo` vale
  para **cada palavra-chave** em cada fonte: abre no máximo N páginas de resultados (a quantidade de vagas por página é a do site; a paginação também para antes se a página vier vazia ou só repetir vagas que o próprio termo já viu; vaga achada por dois termos fica com o primeiro). Antes: teto de vagas (`max_vagas_lista`, da fonte inteira; depois `max_vagas_por_termo`, por termo), substituído por páginas. Antes ainda: uma busca por palavra-chave **e por localidade**, `f_WT` no LinkedIn e uma busca por modalidade na Gupy.
- **Filtro local de localidade e modalidade** (`services/localizacao.py`, igual para todas as fontes, aplicado na lista e de
  novo após o detalhe): `Job.localidade` e `Job.modalidade` (`remoto`/`hibrido`/`presencial`, ou `""`) vêm do card: LinkedIn
  da legenda ("(Presencial)"), Indeed da localidade e dos itens do card, Gupy de `workplaceType`. Localidade: a vaga passa se
  casar com alguma entrada de `[busca] localidades`: entrada de cidade (`"Campinas, SP"`) casa a cidade (e a UF, se a vaga a
  informar); entrada só de estado (`"Minas Gerais"` ou `"MG"`) casa pela UF da vaga (nome do estado ou sigla). Modalidade:
  precisa estar em `[busca] modalidade`. **Desconhecido** (localidade vazia, só "Brasil", vaga remota, vaga de estado sem UF
  no texto, modalidade não informada) segue `[filtro] aceitar_desconhecido`. Limitações: o texto da localidade é livre
  (cidade chamada como o estado, como "São Paulo", casa também o estado) e a modalidade do Indeed é só por palavras do card.
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
- **Bloqueio: a fonte espera o usuário** (`VerificationGate`, `[navegador] espera_verificacao_s`). A aba fica aberta, a tela mostra o aviso com o botão **Já concluí a verificação** e, ao confirmar, a fonte reabre a página que bloqueou e segue de onde parou (o que já foi lido é mantido). Se a reabertura falhar (o site ainda redireciona após a verificação e o `goto` é abortado), tenta uma vez mais após a pausa; falhando de novo, `http_erro`. Antes: a primeira falha na reabertura encerrava a fonte. Se o bloqueio persistir, volta a esperar; sem confirmação no prazo, ou sem portão, vale o comportamento abaixo. Antes: o bloqueio encerrava a fonte na hora. Nada é resolvido ou contornado pelo programa.
- **Bloqueio (`SourceBlocked`) sem confirmação mantém a aba aberta** no Chrome dedicado, para o usuário concluir a verificação à
  mão; a próxima execução abre uma aba nova (antes: a aba era sempre fechada). Outros erros e o sucesso continuam
  fechando a aba. A aba deixada aberta é responsabilidade do usuário fechar.

## Filtro

Palavras-chave e exclusões vêm da tabela `keywords`, **só do conjunto ativo** (tabela `conjuntos`; antes eram uma lista única global), lidas **no início de cada execução** (edição vale na
busca seguinte). Há três grupos: `busca` (query), `ranking` (só pontua; não gera consulta) e `exclusao`. Cada palavra-chave `busca` gera uma consulta por fonte (mais termos = mais páginas lidas,
limitadas por `max_paginas_por_termo` em cada termo); só os primeiros `max_termos_busca` termos do conjunto vão às fontes (conjunto maior que o teto é cortado na execução); o filtro local pontua com `busca` **+** `ranking` (um termo nos dois grupos conta uma vez). Antes: uma lista só (`busca`) servia à query e à pontuação.

1. **Normalização**: minúsculas, sem acento (`unicodedata`), espaços colapsados.
2. **Exclusões**: qualquer termo excluído em título ou trecho descarta a vaga.
3. **Pontuação**: `peso_titulo` por palavra-chave no título + `peso_descricao` no trecho (cada termo conta uma vez).
4. **Limiar**: aprovada se `pontos >= min_score`.

Casamento: um termo casa quando **todas as suas palavras** aparecem no texto, **em qualquer ordem e ignorando plural/gênero** (`engenheira`/`engenheiros` ≡ `engenheiro`, sem stemming além disso: `engenharia` não casa `engenheiro`)
(assim "Engenheiro Mecânico" casa "Engenheira Mecânica" e "Mecânico — Engenheiro de Projetos").
Qualquer exclusão (mesmo critério) em título **ou** trecho descarta.
Fluxo no serviço: tria a lista (exclusões, localidade, modalidade; sem pontuação; antes a pontuação também cortava aqui, e palavras só presentes na descrição eram perdidas) → descarta as já conhecidas → abre o detalhe de **todas** as novas triadas, avalia com a pontuação completa e grava só as aprovadas; `aprovadas` em `run_sources` = já gravadas + aprovadas no detalhe (sem teto; o limite é `max_paginas_por_termo` por palavra-chave e por fonte. Antes: até `max_paginas_detalhe` = 15, e as demais ficavam sem descrição e sem data)
→ **reavalia com a descrição completa** (uma exclusão que só aparece no detalhe descarta a vaga) → grava.

## Dados

### Modelo

SQLite via `sqlite3`, `PRAGMA foreign_keys=ON`; esquema versionado em `schema_version`. Cópia do `.db`
antes de qualquer mudança de esquema.

| Tabela | Colunas | Restrições |
| --- | --- | --- |
| `jobs` | `id` PK, `fonte`, `id_da_vaga`, `titulo`, `empresa`, `link`, `trecho`, `pontos`, `run_id` FK (anulável, `ON DELETE SET NULL`; esquema v5), `encontrada_em`, `localidade` (`''` se a fonte não informa), `publicada_em` (NULL se não informa), `modalidade` (`remoto`/`hibrido`/`presencial` ou `''` se a fonte não informa; esquema v6), `palavra_chave` (`''` se desconhecida; esquema v7), `visto` (0/1), `conjunto_id` FK (`ON DELETE CASCADE`; esquema v9) | `UNIQUE(conjunto_id, fonte, id_da_vaga)` (antes `UNIQUE(fonte, id_da_vaga)`): **uma linha por conjunto**, com pontuação e `visto` próprios; a migração 9 atrela as vagas existentes ao primeiro conjunto; excluir o conjunto exclui as vagas dele |
| `conjuntos` (esquema v4) | `id` PK, `nome`, `nome_normalizado` (único), `ativo` (0/1), `criada_em` | índice único parcial: no máximo um `ativo=1`; a migração cria o conjunto `Padrão` (ativo) |
| `keywords` | `id` PK, `termo`, `termo_normalizado`, `tipo` (`busca`/`ranking`/`exclusao`), `criada_em`, `conjunto_id` FK (`ON DELETE CASCADE`) | `UNIQUE(conjunto_id, termo_normalizado, tipo)` (antes `UNIQUE(termo_normalizado, tipo)`); a migração 4 move as palavras existentes para o `Padrão`; a migração 8 adiciona `ranking` e **apaga as palavras `busca` existentes** (exclusões e vagas ficam; cópia do `.db` em `backups/` antes) |
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
| `[busca] max_termos_busca` | `6` | máximo de palavras-chave `busca` por conjunto (cada termo gera uma consulta por fonte; consultas demais levam a bloqueio); `422` ao exceder, exclusões não contam; na execução só os primeiros `max_termos_busca` termos vão às fontes. Editável na tela Configurações (controle deslizante, 1–10; antes: `10`, e só barrava termos novos) |
| `[busca] localidades` / `modalidade` | `[]` / `[]` | lista de cidades ou estados (`"Campinas, SP"`, `"Minas Gerais"`; textos não vazios, sem repetição ignorando caixa; vazia = sem filtro de local), **só no `config.toml`: a aba Configurações não os edita mais** (o `PUT /api/config` os preserva como vieram; antes eram editáveis na tela); e lista de `remoto`/`hibrido`/`presencial` (vazia = todas). **Filtram as vagas listadas (filtro local), não vão na busca da plataforma.** Antes: iam na busca (`location`/`l`, `f_WT`, `workplaceType`, uma busca por localidade/modalidade) |
| `[filtro] aceitar_desconhecido` | `true` | vaga sem localidade/modalidade informada (ou só "Brasil", ou remota) passa pelo filtro de local e modalidade; `false` descarta. Só no `config.toml` (não aparece na tela) |
| `[busca] janela_horas` | `24` | filtro de recência da própria busca (onde a fonte permite) |
| `[filtro] peso_titulo` / `peso_descricao` | `3` / `1` | pontos por termo no título e no trecho |
| `[filtro] min_score` | `3` | pontuação mínima para aprovar |
| `[limites] max_paginas_por_termo` | `3` | páginas de resultados abertas por palavra-chave e por fonte (LinkedIn 25 vagas/página, Indeed 10, Gupy 50; máximo de páginas por fonte = `max_termos_busca` × este valor); editável na tela Configurações (controle deslizante, 1–10). Antes: `max_vagas_lista` (teto de vagas da fonte inteira, 300) |
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
