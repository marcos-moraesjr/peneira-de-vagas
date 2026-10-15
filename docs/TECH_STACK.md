# Stack Técnica — Peneira de Vagas

Decisões, justificativas e **exclusões explícitas**. Se uma biblioteca não está
nesta página, ela não está no projeto. **Adicionar uma exige aprovação explícita
do usuário** e, uma vez aprovada, uma linha aqui e a entrada em
`requirements.txt` / `package.json` na mesma alteração.

## Princípio norteador

**Construir apenas o que o pipeline exige.** Toda dependência precisa justificar
seu lugar removendo mais código do que adiciona. Na dúvida, escreva as 30 linhas
você mesmo.

## Arquitetura em uma linha

Front end (React) → API (FastAPI) → tarefas de busca (Playwright/httpx) → SQLite. O front dispara a
busca pela API e exibe os resultados; **não há Telegram nem agendador externo** (decisão do usuário).

## Fontes de dados

| Fonte | Canal | Observação |
| --- | --- | --- |
| **LinkedIn** | Navegador real (Chrome dedicado, controlado via CDP) | Navegador logado em automação viola os termos de uso; risco de restrição da conta aceito conscientemente. |
| **Indeed** | Navegador real (mesmo Chrome dedicado) | Protegido por Cloudflare. Verificação anti-bot é esperada e tratada como falha, nunca contornada. |
| **Gupy** | API JSON do portal (`portal.gupy.io`) via HTTP | Endpoint não documentado: capturado pelo DevTools (aba Network) e tratado como instável. |

## Backend

| Preocupação | Escolha | Por quê |
| --- | --- | --- |
| Linguagem / runtime | **Python 3.12+** | Ecossistema maduro para automação de navegador e HTTP. |
| API | **FastAPI** + **uvicorn** | Contrato tipado (Pydantic), OpenAPI gerado para o front, tarefas em segundo plano. |
| Validação / schemas | **Pydantic** (vem com FastAPI) | Contratos da API; sem biblioteca de validação adicional. |
| Automação de navegador | **Playwright** (`connect_over_cdp`) | Conecta ao Chrome real já aberto, com logins persistentes e a impressão digital de um navegador comum. |
| Cliente HTTP | **httpx** | Gupy (API JSON). Um único cliente HTTP no projeto; também base do `TestClient` do FastAPI. |
| Extração de HTML | Locators do próprio Playwright | Sem biblioteca de parsing separada; o DOM é lido onde ele já está. |
| Armazenamento | **SQLite** (módulo `sqlite3` da stdlib) | Deduplicação por chave única `(fonte, id_da_vaga)`, vagas e histórico de execuções. Sem ORM. |
| Filtro de palavras-chave | `re` + `unicodedata` (stdlib) | Normalização (caixa, acentos) e regex. Peso maior para título que para descrição, com lista de exclusões. |
| Configuração | **TOML** (`tomllib` da stdlib) | Localidade, pesos, limites e pausas ficam em `config.toml`, fora do código. Leitura com `tomllib`; a aba Configurações regrava só o valor da linha (`services/config_edit.py`, sem lib de escrita, comentários preservados). |
| Palavras-chave e exclusões | **SQLite** (tabela `keywords`) | Editáveis pelo front; `config.toml` só traz o valor inicial (seed). Evita biblioteca de escrita de TOML. |
| Execução da busca | `threading` (stdlib) | Uma execução por vez, em segundo plano; a API responde na hora e o front consulta o andamento. |
| Logging | Módulo `logging` da stdlib | Sem biblioteca de logging externa. |

## Frontend

| Preocupação | Escolha | Por quê |
| --- | --- | --- |
| Framework | **React 18 + TypeScript** (`strict`) | |
| Build / dev | **Vite** | Dev com proxy para a API; build estático servido pelo FastAPI em uso diário. |
| Estilo | **Tailwind CSS** | Sem biblioteca de componentes. |
| Fonte | **Noto Sans** via `@fontsource/noto-sans` (pesos 400, 500, 600, 700; a mesma do Indeed), com a pilha do sistema como reserva | Fonte única em todo o front; empacotada localmente (sem CDN nem requisição a terceiros). |
| Dados do servidor | **TanStack Query** | Cache, polling do andamento da execução e invalidação após mutações. |
| Tipos da API | **openapi-typescript** | Tipos gerados do OpenAPI do backend; nunca escritos à mão. |
| Navegação | `useState` (abas) | São duas telas (Vagas, Execuções); sem roteador. |
| Formatação | `Intl` | Datas e textos em pt-BR, sem biblioteca de datas. |
| Gráficos | — | Fora do MVP. |

### Versões

`backend/requirements.txt` fixa `fastapi`, `uvicorn`, `playwright`, `httpx` e `pytest`. `frontend/package.json`
fixa as versões do frontend (React 18.3, Vite 6.0.5 com `overrides` para ter uma só cópia, Tailwind 4.1.11 —
a 4.0.0 falhou no build —, TanStack Query 5, Vitest 2, openapi-typescript 7). Dependências de teste do front:
`jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`. Python
desenvolvido e testado em 3.14; o mínimo suportado segue 3.12. Como o projeto conecta ao Chrome existente, **não** rodamos `playwright install`
para baixar navegadores próprios.

## Estrutura do projeto

```
peneira-de-vagas/
├── backend/
│   ├── app/
│   │   ├── main.py        # create_app(): rotas, lifespan, build estático
│   │   ├── routes/        # rotas finas
│   │   ├── services/      # execução da busca, vagas, filtro
│   │   ├── sources/       # linkedin.py, indeed.py (Playwright/CDP) e gupy.py (httpx)
│   │   ├── db.py          # SQLite e deduplicação
│   │   └── config.py      # config.toml tipado
│   ├── config.toml
│   └── tests/
├── frontend/
│   ├── src/               # api/, components/, features/ (vagas, execucoes)
│   └── e2e/               # (somente se aprovado, ver Pendências)
├── scripts/               # atalho do Chrome dedicado
└── docs/
```

Todas as fontes devolvem o mesmo formato: `id`, `título`, `empresa`, `link`, `trecho`, `fonte`.

## Regras de projeto

- **Chrome dedicado:** perfil próprio (`--user-data-dir`) e `--remote-debugging-port=9222` ligado só em `localhost`. Nunca conectar ao perfil pessoal em uso (versões recentes do Chrome ignoram a porta de depuração nele). O login nos sites é feito à mão pelo usuário nesse perfil (fica em `data/chrome-profile/`, fora do Git).
- **API só em `127.0.0.1`:** sem autenticação, portanto sem exposição à rede. Abrir além disso é decisão do usuário.
- **Deduplicação, não janela de tempo:** vaga nova é a que não está no SQLite.
- **Filtro da própria busca primeiro:** URL com palavra-chave e filtro de últimas 24h; o filtro local é a segunda passada.
- **Limite de páginas por execução:** lista lida inteira; página de detalhe aberta só para vagas que passam no filtro, com teto por execução (valor inicial: 15).
- **Falha explícita:** CAPTCHA, tela de login inesperada, mudança de seletor ou zero resultados em uma fonte **encerram aquela fonte na execução** e aparecem no front como falha daquela fonte. As demais continuam.
- **Sem contorno de bloqueio:** o projeto não resolve CAPTCHA nem disfarça automação.
- **Ritmo humano:** pausas variáveis entre ações, uma aba por plataforma (opção `navegador.abas_paralelas` roda as plataformas ao mesmo tempo; nunca várias abas na mesma) e **uma execução por vez** (nova solicitação durante uma execução responde 409).

## Testes

| Camada | Escolha |
| --- | --- |
| Backend, unitário e API | **pytest** + `TestClient` do FastAPI — filtro, deduplicação, parsing da Gupy (amostras salvas), rotas, execução com fontes simuladas |
| Backend, integração | **pytest** com marker `integration` — execução real contra os sites, rodada pelo usuário (agente só com autorização prévia, em LinkedIn/Indeed) |
| Frontend | **Vitest** + `@testing-library/react` — componentes e fluxos com a API simulada |

## Ferramentas

- **venv** local (`.venv`) + `pip install -r requirements.txt`; `npm` para o frontend.
- **Distribuição (usuário comum, sem instalador `.exe`):** `scripts/build-release.ps1` empacota o **Python embeddable** oficial (artefato de build, não biblioteca do projeto) com as dependências de `requirements.txt` (menos `pytest`) num `.zip` publicado em GitHub Release; `scripts/install.ps1` instala e `peneira.cmd` é o comando. PyInstaller e Inno Setup **não** entram (antivírus e instalador fora do desejado). Não há `playwright install`: o projeto só conecta ao Chrome do usuário por CDP.
- **Git** — `.gitignore` cobre `__pycache__`, `.venv`, `*.db`, `data/` (inclui `data/chrome-profile/`), `node_modules`, `frontend/dist`, `logs/`, `/release/`.

Sem formatador/linter/CI configurados hoje. Adotar um (ex.: ruff, ESLint) é uma decisão a registrar aqui antes de entrar.

## Excluídos explicitamente

Não introduza nenhum destes sem uma decisão explícita registrada neste arquivo:

- **Telegram, e-mail e qualquer notificação externa** — a saída é o front end. _(Antes: Telegram era a saída; removido por decisão do usuário.)_
- **python-dotenv / `.env`** — sem segredos no projeto agora que o Telegram saiu. Se surgir um segredo, reavaliar.
- **Selenium / undetected-chromedriver / playwright-stealth** — o projeto resolve detecção usando o navegador real, não disfarçando um automatizado.
- **Serviços de resolução de CAPTCHA e proxies rotativos** — contornar bloqueio acelera o banimento.
- **Scrapy** — framework de crawling em larga escala.
- **BeautifulSoup / lxml** — os locators do Playwright cobrem a extração, e a Gupy devolve JSON.
- **requests / aiohttp** — um único cliente HTTP (`httpx`).
- **SQLAlchemy / Alembic / qualquer ORM / PostgreSQL** — poucas tabelas em SQLite não justificam abstração; o esquema evolui por script SQL versionado.
- **pandas / numpy** — são listas de dicionários.
- **rapidfuzz / embeddings / modelos de linguagem para classificar vagas** — fora do escopo inicial. Reavaliar só com falsos positivos medidos em uso real.
- **APScheduler / Celery / Redis / filas** — uma execução por vez em `threading`; agendamento automático é decisão em aberto (ver Pendências).
- **Flask, Django, Streamlit** — a API é FastAPI.
- **Bibliotecas de componentes (MUI, Ant, shadcn, Chakra), Redux/Zustand, TanStack Router, bibliotecas de datas** — Tailwind + componentes próprios, estado do servidor no TanStack Query.
- **WebSocket / SSE** — o andamento da execução é lido por polling (TanStack Query).
- **Docker** — o Chrome com sessão logada e IP residencial é o que o projeto precisa, e isso vive na máquina do usuário.
- **APIs de agregadores (Adzuna, JSearch, SerpApi) e leitura de alertas por e-mail** — alternativas avaliadas e descartadas (LinkedIn e Indeed 100% navegador).

## Pendências de decisão

- **Agendamento automático:** hoje a busca é disparada por botão no front. Agendar exige um agendador interno (sai das exclusões só com aprovação) ou o agendador do SO chamando `POST /api/runs`. Decidir depois da Fase 5.
- **Local de execução:** PC próprio (IP residencial, precisa estar ligado e com o Chrome aberto) ou VPS (IP de datacenter é bloqueado mais rápido). Ponto de partida: PC próprio.
- **Exclusões iniciais, localidade e modalidade** (`config.toml`). Palavra-chave de desenvolvimento: "Engenheiro Mecânico".
- **Editar os demais parâmetros pela interface** (pesos, limites): exigiria mover a config para o SQLite. Fora do MVP.
- **E2E (Playwright no front):** só se aprovado; por ora, Vitest.
