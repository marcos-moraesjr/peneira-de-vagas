# JobScanner

Aplicação **local** que busca vagas de emprego no **LinkedIn**, no **Indeed** e na **Gupy**. Você cadastra
as palavras-chave no front end (padrão de desenvolvimento: **Engenheiro Mecânico**), clica em **Buscar
agora**, e a API consulta as três fontes, filtra, remove duplicadas e mostra as vagas novas na tela.

- LinkedIn e Indeed: navegador Chrome real e dedicado, controlado via CDP (sem disfarce de automação).
- Gupy: API JSON do próprio portal.
- Front end: React + TypeScript. API: FastAPI. Banco: SQLite.

> **Estado atual:** Fases 0–4 implementadas e cobertas por testes automatizados; **falta a sua validação
> manual** contra os sites reais (`docs/FASES.md`). Endpoint e seletores seguem a exploração em DOM real de
> 14/10/2026 ([`docs/EXPLORACAO_PLATAFORMAS.md`](docs/EXPLORACAO_PLATAFORMAS.md) §2); o que ainda não foi verificado está em
> `docs/FASES.md` (Status). Confirme com uma execução real.

## Documentação

| Doc | Conteúdo |
| --- | --- |
| [`docs/MVP.md`](docs/MVP.md) | escopo, regras de negócio e critérios de aceite |
| [`docs/FASES.md`](docs/FASES.md) | ordem de construção |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | fluxo, API, módulos, dados e configuração |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | bibliotecas permitidas e excluídas |
| [`docs/DESIGN_BRIEF.md`](docs/DESIGN_BRIEF.md) | telas e estados da interface |
| [`docs/CODE_QUALITY.md`](docs/CODE_QUALITY.md) | testes, estilo, git e definição de pronto |
| [`docs/SCANNERS.md`](docs/SCANNERS.md) | versão de cada scanner, aviso de "refazer" e como refazer com o Claude |
| [`docs/EXPLORACAO_PLATAFORMAS.md`](docs/EXPLORACAO_PLATAFORMAS.md) | exploração das plataformas (endpoint e seletores observados) |
| [`docs/LESSONS.md`](docs/LESSONS.md) | erros e lições registrados |
| [`docs/AI_GUIDELINES.md`](docs/AI_GUIDELINES.md) | regras para agentes de IA |

## Requisitos

- Windows, macOS ou Linux (sistema da máquina de execução ainda em decisão: `docs/MVP.md` §11)
- **Python 3.12+**
- **Node.js 20+** e npm
- **Google Chrome** instalado (o projeto **não** baixa navegadores do Playwright)
- Conta logada no LinkedIn e no Indeed, **dentro do Chrome dedicado** (veja abaixo)

## Instalação

```bash
# backend (no Windows sem "python" no PATH, use: py -3 -m venv .venv)
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt

# frontend
cd frontend
npm install
```

## Chrome dedicado (LinkedIn e Indeed)

Usa um perfil próprio (`data/chrome-profile/`), nunca o seu pessoal; a porta de depuração fica só em `localhost`.

**Pelo app (recomendado):** na aba Busca, clique em **Abrir Chrome dedicado**. O indicador muda para "Chrome
dedicado aberto" quando ele estiver pronto. Se o Chrome não for achado, ajuste `chrome_paths` em
`backend/config.toml`.

**Pelo terminal (alternativa):** `powershell -File scripts\chrome-dedicado.ps1`.

Na primeira vez, faça login no LinkedIn e no Indeed **manualmente** nessa janela e deixe-a aberta durante a
busca. Se o Chrome estiver fechado, a busca nessas fontes falha com o aviso "Chrome dedicado não encontrado"
(a Gupy continua funcionando). O LinkedIn e o Indeed podem pedir verificação (CAPTCHA); nesse caso a fonte falha e a aba fica aberta para você resolver à mão.

> O uso de navegador logado em automação pode violar os termos de uso do LinkedIn e do Indeed; o risco de
> restrição da conta é aceito conscientemente. Se aparecer CAPTCHA ou verificação, resolva à mão: o
> projeto não contorna bloqueios.

## Execução

**Uso diário (um processo):** a API serve o front compilado.

```bash
cd frontend && npm run build && cd ..
.venv\Scripts\python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8100
```

Abra <http://127.0.0.1:8100>. (A porta 8000 foi evitada de propósito: costuma estar em uso por outros apps.)

**Desenvolvimento (dois processos):**

```bash
.venv\Scripts\python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8100
cd frontend && npm run dev          # http://127.0.0.1:5173, com proxy para a API
```

Não use `--reload` ao fazer buscas reais no Windows: o recarregador troca o laço de eventos e pode impedir
o Playwright de conectar ao Chrome.

Após mudar um schema da API: `python -m backend.scripts.export_openapi` e depois `cd frontend && npm run gen:api`.

Não exponha a API além de `127.0.0.1`: ela não tem autenticação.

## Uso

1. Abra o app e, no painel **Palavras-chave**, adicione os termos (já vem com "Engenheiro Mecânico"). Use
   **Exclusões** para descartar vagas indesejadas.
2. Clique em **Buscar agora** e acompanhe o andamento por fonte.
3. Veja as vagas **novas**, abra a original pelo link e marque como vistas.
4. A tela **Execuções** mostra o histórico e o motivo de qualquer fonte que tenha falhado.
5. A aba **Tutorial** do app traz esses passos (Chrome dedicado, login, palavras-chave, busca) e a tabela de problemas comuns.

Parâmetros fixos (localidade, pesos, limites, pausas; a localidade vem vazia, como na busca observada) ficam em `backend/config.toml`; referência completa em
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#configuração).

## Testes

```bash
pytest                               # backend, a partir da raiz (sem rede)
cd frontend && npm test              # Vitest
cd frontend && npm run typecheck     # tipos
```

Os testes marcados `browser` usam o Chrome local em modo headless sobre HTML salvo (sem rede) e são
pulados se o Chrome não estiver instalado.

Os testes de integração contra os sites reais (`pytest -m integration`) são rodados **só por você**,
manualmente, nunca em rotina.

## Dados e privacidade

Tudo fica na sua máquina: banco em `data/jobscanner.db`, perfil do Chrome em `data/chrome-profile/`, logs em
`logs/` (nenhum é versionado). A única comunicação externa são as requisições às três fontes de vagas.

## Quando um scanner quebra

Cada fonte tem um scanner versionado (`backend/scanners.toml`). Se ele falhar por quebra (layout mudou, zero
resultados, HTTP) em execuções seguidas, a tela **Vagas** mostra "O scanner do X precisa ser refeito" com um
botão **Copiar instrução para o Claude**: cole a instrução numa sessão do Claude Code neste repositório. O
procedimento completo e o changelog estão em [`docs/SCANNERS.md`](docs/SCANNERS.md).
