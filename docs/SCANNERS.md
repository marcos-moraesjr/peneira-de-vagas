# Scanners — versionamento e manutenção

Cada fonte de vagas (LinkedIn, Indeed, Gupy) tem um **scanner**: o adaptador em `backend/app/sources/<fonte>.py`
mais as amostras de teste, **gerado pelo Claude a partir de uma exploração da plataforma** (seletores e endpoint
observados no DOM real; ver [`EXPLORACAO_PLATAFORMAS.md`](EXPLORACAO_PLATAFORMAS.md)). Plataformas mudam sem
aviso, então todo scanner tem prazo de validade: este documento define como versioná-lo, como o app avisa que
ele quebrou e como refazê-lo.

## Manifesto

[`backend/scanners.toml`](../backend/scanners.toml) é a fonte de verdade da versão de cada scanner:

| Chave | Significado |
| --- | --- |
| `versao` | `MAJOR.MINOR.PATCH` do scanner |
| `explorado_em` | data (AAAA-MM-DD) da exploração da plataforma que originou esta versão |
| `gerado_por` | quem produziu a versão (hoje: `Claude`) |
| `referencia` | onde está a exploração (seção de `EXPLORACAO_PLATAFORMAS.md`) |

### Regra de versão

- **PATCH** — ajuste de seletor, texto de bloqueio ou parâmetro de URL sem mudar o que a fonte devolve.
- **MINOR** — novo dado lido (campo extra em `Job`), novo modo de paginação ou de leitura.
- **MAJOR** — scanner refeito do zero (nova exploração, fluxo diferente) ou troca de canal (ex.: navegador → API).

Toda mudança em `sources/<fonte>.py`, no JS de extração ou nas amostras **sobe a versão** e ganha uma linha no
changelog abaixo, na mesma alteração. O app grava a versão usada em cada fonte de cada execução
(`run_sources.scanner_versao`), então o histórico mostra qual versão produziu qual resultado.

## Quando o app avisa que é hora de refazer

O estado de cada scanner (`GET /api/scanners`, tela Vagas e tela Execuções) é calculado assim:

| Estado | Condição | O que o usuário vê |
| --- | --- | --- |
| **Refazer** | `falhas_consecutivas` (config: `[versionamento]`, padrão 2) falhas seguidas de **quebra**, só na versão atual | alerta vermelho na tela Vagas + **instrução pronta para colar no Claude**; aviso `refazer` no log |
| **Atenção** | 1 falha de quebra, **ou** scanner explorado há mais de `max_idade_dias` (padrão 90) | nota discreta |
| **Em dia** | nenhuma das anteriores | nada |

- **Falhas de quebra** (`motivos_de_quebra`): `seletor_nao_encontrado`, `zero_resultados`, `http_erro`.
- **Não contam** como quebra: `captcha`, `login`, `cloudflare`, `cdp_indisponivel` (pedem ação do usuário, não um
  scanner novo). Elas também **não interrompem** a contagem de falhas de quebra.
- Uma execução bem-sucedida da fonte zera a contagem.
- Subir a versão no manifesto zera a contagem (só contam falhas da versão atual).
- O app **não chama o Claude sozinho**: o aviso é a instrução, e quem dispara a refação é o usuário.

## Como refazer um scanner

1. Na tela Vagas, clique em **Copiar instrução para o Claude** (ou use o modelo abaixo) e cole numa sessão do
   Claude Code neste repositório, com o Chrome dedicado aberto e logado.
2. O Claude explora a plataforma de novo, atualiza a seção da fonte em `EXPLORACAO_PLATAFORMAS.md`, escreve os
   testes (vermelho), ajusta o adaptador (verde) e as amostras, sobe a versão em `backend/scanners.toml` e
   registra o changelog aqui.
3. Você valida com uma busca real (`Buscar agora`); o estado volta a **Em dia** quando uma execução da nova
   versão tiver sucesso.

Modelo da instrução (o app a preenche com fonte, versão, data, contagem e motivo):

```
O scanner da fonte "<Fonte>" (versão X.Y.Z, explorado em AAAA-MM-DD por Claude) precisa ser refeito.
Motivo: N falhas seguidas na versão atual (<motivo>: <detalhe>).
Faça, seguindo TDD (teste vermelho antes do código):
1. Explore a plataforma de novo no navegador e atualize a seção da fonte em docs/EXPLORACAO_PLATAFORMAS.md.
2. Ajuste o adaptador em backend/app/sources/<fonte>.py e as amostras em backend/tests/samples/.
3. Suba a versão de "<fonte>" em backend/scanners.toml (e a data da exploração) e registre a mudança no
   changelog de docs/SCANNERS.md.
4. Rode os testes do backend e do frontend e me diga o que ainda precisa de validação manual.
```

## Changelog

| Fonte | Versão | Data | Mudança |
| --- | --- | --- | --- |
| linkedin | 1.0.0 | 2026-10-14 | Primeira versão: leitura card a card (`li[data-occludable-job-id]`), título em `a[href*="/jobs/view/"] strong`, `f_TPR=r86400`, paginação por `start=`. Não verificado: paginação por `start=`, perfil sem login |
| indeed | 1.0.0 | 2026-10-14 | Primeira versão: `div.job_seen_beacon`, `a.jcs-JobTitle[data-jk]`, trecho pelos `li` do card, `fromage=1`. Não verificado: efeito de `fromage`, paginação por `start=` |
| gupy | 1.0.0 | 2026-10-14 | Primeira versão: `portal.gupy.io/api/job-search/jobs` (`jobName`, `limit`, `offset`). Não verificado: resposta a `httpx` fora do navegador |
