# Fases de Desenvolvimento — JobScanner

Ordem de construção do MVP descrito em [`MVP.md`](MVP.md), com a stack de
[`TECH_STACK.md`](TECH_STACK.md). Cada fase termina com algo **utilizável** e
com critério de pronto verificável. Não se avança de fase com a anterior
quebrada.

**Tamanhos** (P/M/G) são estimativas relativas de esforço, não prazos. Calibre
depois da Fase 1.

## Status

**Fases 0–4: implementadas e verdes nos testes automatizados; aguardando a validação do usuário.** O que só o
usuário pode confirmar (execução real, fora dos testes): a Gupy responder a `httpx` fora do navegador (se
der 403, parar e reavaliar), o efeito de `fromage=1` no Indeed, a paginação por `start=`, Chrome dedicado
logado e a falha provocada (Chrome fechado). Endpoint e seletores vêm da exploração em DOM real de 14/10/2026
(`EXPLORACAO_PLATAFORMAS.md` §2); as amostras de teste são fictícias com a estrutura observada. Fase 5 não iniciada.

Extra pedido pelo usuário depois da Fase 4: **versionamento dos scanners** (`backend/scanners.toml`, esquema v2 do banco, `GET /api/scanners`, aviso "refazer" na tela e no log; ver `SCANNERS.md`).

Desvios registrados: o `README` e a API usam a porta **8100** (a 8000 estava em uso pelo FinApp); `Python 3.14`
no ambiente de desenvolvimento; Tailwind 4.1.11 no lugar da 4.0.0 (falha de build); `BackgroundTasks` não foi
usado (apenas `threading`); a Gupy não recebe filtro de localidade/recência nesta versão.

## Visão geral

| Fase | Nome | Tamanho | Resultado utilizável |
| --- | --- | --- | --- |
| 0 | Fundação | P | API + front + banco rodam de ponta a ponta com uma fonte falsa |
| 1 | Gupy, filtro e tela de vagas | M | Busca na Gupy pelo front e vagas reais listadas |
| 2 | Chrome dedicado e LinkedIn | G | LinkedIn lido via CDP, com falha explícita |
| 3 | Indeed | M | Terceira fonte, com tratamento de Cloudflare |
| 4 | Execuções e acabamento | P | Histórico, falhas por fonte e config visíveis |
| 5 | Uso real e estabilização | — | 14 dias de uso; decide a v2 |
| v2 | Evolução | — | Definida pelo uso real |

---

## Fase 0 — Fundação

**Objetivo:** esqueleto funcional, sem fonte real.

**Entregas**
- Repositório com `backend/` (FastAPI) e `frontend/` (Vite + React + TypeScript + Tailwind) e `.gitignore`.
- `config.toml` com as chaves iniciais e leitura tipada via `tomllib`.
- `db.py`: criação das tabelas `jobs`, `runs` e `run_sources`.
- `POST /api/runs`, `GET /api/runs/{id}`, `GET /api/jobs` com uma fonte falsa (fixture) no formato único; execução em segundo plano, uma por vez.
- Geração dos tipos do frontend a partir do OpenAPI (`openapi-typescript`) e wrapper mínimo de `fetch`.
- Um endpoint de saúde consumido pelo frontend.
- Execução em dev (dois processos) e em modo único (FastAPI servindo `frontend/dist`).
- pytest e Vitest rodando com um teste de exemplo cada.

**Pronto quando**
- Um comando sobe o app; o botão "Buscar agora" cria uma execução com a fonte falsa e a tela lista as vagas.
- Rodar duas vezes não duplica registros; pedir outra execução durante uma em andamento devolve 409.

**Atenção:** qualquer desvio de stack é registrado em `TECH_STACK.md` aqui. Nada fora da lista sem aprovação.

---

## Fase 1 — Gupy, filtro e tela de vagas

**Objetivo:** primeiro valor real, na fonte mais estável (API JSON, sem navegador).

**Entregas**
- `sources/gupy.py`: chamada httpx ao portal, parsing para o formato único, amostras reais salvas em `tests/samples/`.
- `keywords`: tabela, rotas `GET/POST/DELETE /api/keywords`, seed "Engenheiro Mecânico" e painel de palavras-chave/exclusões no front.
- `filters.py`: normalização, palavras-chave (do banco) com peso título × descrição, exclusões, limiar.
- Tela **Vagas**: lista, filtros (novas, fonte, texto), marcar como vista, link para a vaga, andamento da busca por polling.
- Faixa de falha por fonte.

**Pronto quando**
- Critérios 1, 2, 3, 4 e 5 do MVP (testes automatizados).
- Busca real na Gupy lista vagas e a segunda busca não repete nenhuma.

**Marco de uso:** com a Gupy funcionando, **ajuste o filtro com vagas reais**. É o ponto onde palavras-chave e exclusões deixam de ser chute.

---

## Fase 2 — Chrome dedicado e LinkedIn

**Objetivo:** ler o LinkedIn sem disfarçar automação.

**Entregas**
- Script/atalho que abre o Chrome dedicado (`--user-data-dir`, `--remote-debugging-port=9222`, só `localhost`); login manual do usuário.
- `sources/linkedin.py`: `connect_over_cdp`, URL de busca com palavra-chave e 24h, leitura da lista, detalhe só das vagas aprovadas (teto por execução), pausas variáveis.
- Detecção e falha explícita: login, CAPTCHA/verificação, seletor ausente, zero resultados, CDP indisponível — cada uma com mensagem e ação na tela.

**Pronto quando**
- Critério 4 do MVP com a fonte real simulada em teste.
- O usuário confirma uma execução real (`integration`) e uma falha provocada (Chrome fechado) exibida corretamente.

**Atenção:** é a fase de maior risco de restrição de conta. Volume baixo; parar ao primeiro aviso do LinkedIn.

---

## Fase 3 — Indeed

**Objetivo:** terceira fonte, reaproveitando o que a Fase 2 mostrou.

**Entregas**
- `sources/indeed.py` no mesmo modelo do LinkedIn.
- Cloudflare/verificação detectados e tratados como falha da fonte, sem tentativa de contorno.

**Pronto quando**
- Execução real devolve vagas do Indeed, ou falha de forma clara quando bloqueada.
- Código comum às duas fontes de navegador só é extraído porque **existem dois casos reais** (`AI_GUIDELINES.md` §4).

---

## Fase 4 — Execuções e acabamento

**Objetivo:** transparência sobre o que a busca fez.

**Entregas**
- Tela **Execuções**: histórico por fonte (status, motivo, lidas, aprovadas, novas, duração) e config em vigor (somente leitura).
- Log em arquivo; marcar todas como vistas.
- Estados de carregando, vazio e erro em todas as telas.

**Pronto quando**
- Critério 6 do MVP; o usuário entende, só olhando a tela, por que uma fonte falhou.

---

## Fase 5 — Uso real e estabilização

**Objetivo:** validar o produto, não adicionar funcionalidade.

**Atividades**
- Usar por **14 dias seguidos**.
- Registrar cada atrito: vaga irrelevante, vaga relevante perdida, falha silenciosa, falha recorrente de fonte, esquecer de buscar.
- Ajustar palavras-chave (tela) e `config.toml` e corrigir bugs; registrar em `LESSONS.md` o que for erro real.

**Pronto quando**
- Critério de sucesso do produto (`MVP.md` §9).
- Lista priorizada de atritos escrita, para decidir a v2.

**Se o critério falhar:** o problema costuma ser o filtro ou a fragilidade de uma fonte, ou o esquecimento de buscar. A v2 começa por aí.

---

## v2 — Evolução (só após a Fase 5)

Candidatas, **ordenadas pelo que o uso real indicar** (hipótese, não compromisso):

1. **Agendamento automático** da busca (agendador interno ou do SO chamando `POST /api/runs`; exige aprovação de stack).
2. Editar pela tela os demais parâmetros (pesos, limites, localidade).
3. Ajuste fino do filtro (sinônimos, pesos por campo); fuzzy/embeddings só com falso positivo **medido**.
4. Status de candidatura por vaga (interessado, aplicado, descartado).
5. Notificação (por exemplo, Telegram ou notificação do sistema), se o agendamento entrar.
6. Execução em VPS (avaliar bloqueio por IP de datacenter).

Fora de cogitação sem motivo forte: candidatura automática, multiusuário, contorno de bloqueio.

---

## Regras de condução

1. **Uma fase por vez.** Não começar a seguinte sem critério de pronto atingido.
2. **Testes junto com o código**, principalmente no filtro, na deduplicação, no parsing (amostras salvas) e nas rotas.
3. **Nenhuma dependência nova sem aprovação** e sem linha em `TECH_STACK.md`.
4. **Cópia do `.db` antes de qualquer mudança de esquema.**
5. **Escopo congelado até a Fase 5.** Ideias novas vão para uma lista, não para o código.
6. **Execução real contra os sites é do usuário**; testes automatizados usam amostras.
