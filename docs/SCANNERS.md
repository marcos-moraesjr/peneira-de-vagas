# Scanners — versionamento, plataformas e manutenção

Cada fonte (LinkedIn, Indeed, Gupy) tem um **scanner**: o adaptador `backend/app/sources/<fonte>.py` mais as
amostras de teste, gerado pelo Claude a partir de uma exploração da plataforma (DOM e rede reais, registrada na
seção [Plataformas](#plataformas)). Plataformas mudam sem aviso: todo scanner tem prazo de validade.

## Manifesto e versão

[`backend/scanners.toml`](../backend/scanners.toml) é a fonte de verdade: `versao` (`MAJOR.MINOR.PATCH`),
`explorado_em` (AAAA-MM-DD), `gerado_por` (hoje `Claude`) e `referencia` (a seção da fonte neste arquivo).

- **PATCH:** ajuste de seletor, texto de bloqueio, parâmetro de URL ou comentário, sem mudar o que a fonte devolve.
- **MINOR:** novo dado lido (campo extra em `Job`), nova paginação ou novo modo de leitura.
- **MAJOR:** scanner refeito do zero ou troca de canal (ex.: navegador → API).

Toda mudança em `sources/<fonte>.py`, no JS de extração ou nas amostras **sobe a versão** e ganha uma linha no
[changelog](#changelog), na mesma alteração. Cada execução grava a versão usada (`run_sources.scanner_versao`).

## Quando o app avisa que é hora de refazer

Estado por scanner (`GET /api/scanners`, telas Vagas e Execuções):

| Estado | Condição | O que o usuário vê |
| --- | --- | --- |
| **Refazer** | `[versionamento] falhas_consecutivas` (padrão 2) falhas de **quebra** seguidas, só na versão atual | alerta vermelho na tela Vagas com **instrução pronta para o Claude**; aviso `refazer` no log |
| **Atenção** | 1 falha de quebra, **ou** explorado há mais de `max_idade_dias` (padrão 90) | nota discreta |
| **Em dia** | nenhuma das anteriores | nada |

- **Quebra** (`motivos_de_quebra`): `seletor_nao_encontrado`, `zero_resultados`, `http_erro`.
- `captcha`, `login`, `cloudflare` e `cdp_indisponivel` pedem ação do usuário, não scanner novo: não contam como
  quebra e também não zeram a contagem.
- Execução bem-sucedida da fonte ou subir a versão no manifesto zera a contagem.
- O app **não chama o Claude sozinho**: quem dispara a refação é o usuário.

## Como refazer um scanner

1. Na tela Vagas, **Copiar instrução para o Claude** e cole numa sessão do Claude Code neste repositório, com o
   Chrome dedicado aberto e logado.
2. O Claude explora a plataforma de novo, atualiza a seção da fonte aqui, escreve os testes (vermelho), ajusta o
   adaptador (verde) e as amostras, sobe a versão em `scanners.toml` e registra o changelog.
3. Você valida com uma busca real (`Buscar agora`); o estado volta a **Em dia** quando uma execução da nova
   versão tiver sucesso.

## Como o usuário comum recebe um scanner corrigido

O usuário do `install.ps1` não tem o repositório: o scanner corrigido chega **numa versão nova do app**.

1. Quem mantém refaz o scanner, sobe a versão em `scanners.toml` e gera o pacote com
   `scripts/build-release.ps1 -Versao X.Y.Z`.
2. Publica com `gh release create vX.Y.Z release/peneira.zip`.
3. A tela Vagas mostra **Há uma versão nova** (consulta só a versão da última Release; desligável em
   `[atualizacao] verificar`). O usuário fecha o programa e roda `peneira atualizar`; banco, config, logs e perfil
   do Chrome ficam.

A versão do app (`versao.txt`) é distinta da de cada scanner.

## Plataformas

Exploração de **14/10/2026** (busca "engenheiro mecânico", Chrome 155, Windows), complementada em 15/10/2026 para o
Indeed. Nenhuma vaga foi aberta para candidatura, nenhum cookie aceito, nenhum CAPTCHA apareceu. Os seletores
abaixo foram observados no DOM real; **frágeis**: `data-*`, `data-testid` e `artdeco-*` duram mais que as classes
com hash aleatório, mas nenhum é garantido. O alerta "zero vagas lidas" é a defesa.

| | LinkedIn | Indeed | Gupy |
| --- | --- | --- | --- |
| Canal | Navegador (CDP) | Navegador (CDP) | HTTP (`httpx`) |
| Volume observado | 53 resultados em 24h (3 páginas, 25 por página) | 15–16 cards por página, 5 páginas | 20 vagas no total |
| ID estável | `data-occludable-job-id` no `<li>` | `data-jk` no link do título | `id` numérico |
| Data da vaga | texto relativo, só no detalhe | não há no card nem no painel | `publishedDate` ISO |
| Filtro de recência | `f_TPR=r86400` (confirmado) | `fromage=1` (**não confirmado**) | não existe; filtro local (`janela_dias`) |
| Paginação | `start=` (25 em 25) | `start=` (10 em 10) | `limit` + `offset` |

Em todas, a recência e a deduplicação pelo ID (SQLite) decidem o que é vaga nova; as palavras-chave trazem ruído
(no Indeed, só 2 de 15 títulos continham "mecânic"), por isso o filtro local por título é obrigatório. Chrome
dedicado, login manual e porta de depuração: ver `ARCHITECTURE.md` e `TECH_STACK.md`.

### LinkedIn

- **Busca:** `https://www.linkedin.com/jobs/search/?keywords=<termo>&f_TPR=r86400` (o site acrescenta
  `currentJobId`). A localidade vai em `location` e a modalidade em `f_WT` (`1` remoto, `2` presencial, `3` híbrido).
- **Cards:** 25 `li[data-occludable-job-id]` por página, com os 25 IDs já no DOM antes de renderizar (dá para
  deduplicar antes de ler o card). A renderização é **incremental** (7–11 completos ao carregar, ~16 após rolar):
  a leitura acontece enquanto rola. Não há `<time>` no card; "Promovida", "Visualizado" e "Candidatura simplificada"
  aparecem só no texto.

  | Dado | Seletor |
  | --- | --- |
  | ID | `data-occludable-job-id` do `<li>` (comparado direto, sem interpolar em seletor CSS) |
  | Link | `a[href*="/jobs/view/"]` |
  | Título | `a[href*="/jobs/view/"] strong` |
  | Empresa | `.artdeco-entity-lockup__subtitle` |
  | Local/modalidade | `.artdeco-entity-lockup__caption` |

- **Contagem:** `.jobs-search-results-list__title-heading`. **Paginação:** `.jobs-search-pagination`, botões por
  `aria-label` ("Página N", "Ver próxima página").
- **Detalhe (painel lateral):** abre-se clicando no título (`strong`), não no `<a>` (o link do card selecionado
  fica `disabled`). Descrição em `data-testid="expandable-text-box"` (`textContent`, sem clicar em "mais"). A data
  está em `.job-details-jobs-unified-top-card__tertiary-description-container` ("Santana de Parnaíba, São Paulo ·
  Anunciada novamente há 8 horas · 95 candidaturas"); a fonte tenta cada seletor em ordem e, sem data, procura no
  texto da página uma linha que seja inteira a data. "Anunciada novamente" é repostagem, não vaga nova.
- **Não verificado:** perfil sem login, `f_WT` com vários valores, `location` com estado inteiro, formato da data
  com a interface em inglês ou sem "há".

### Indeed

- **Busca:** `https://br.indeed.com/jobs?q=<termo>&fromage=1` (o site acrescenta `vjk=`); localidade em `l`.
  `sort=date` existe e não foi testado.
- **Cards:** `div.job_seen_beacon`. Há uma **isca invisível** (caixa 0×0, `data-jk` falso, link `/viewjob`, título
  copiado de outra vaga, muda a cada carga): só cards com área visível são vagas, e clicar na isca tira a página da
  listagem.

  | Dado | Seletor |
  | --- | --- |
  | ID | `a[data-jk]` (`data-jk` com 16 hex; a classe `jcs-JobTitle` foi removida pelo site) |
  | Título | `span[title]` do link |
  | Empresa | `[data-testid="company-name"]` |
  | Local | `[data-testid="text-location"]` |
  | Trecho e atributos | itens `li` do card |

- **Painel:** layout `DESKTOP_EMBEDDED`; o clique no título carrega a descrição, lida em
  `.simple-job-description-html` (`#jobDescriptionText` não existe mais), sem abrir `/viewjob`. `datePublished` é
  nulo e o texto "Publicada há…" não existe: **não há data**; recência = `fromage=1` + deduplicação.
- **Paginação:** `a[data-testid="pagination-page-N"]` e `pagination-page-next`. **Cookies:** `#onetrust-banner-sdk`
  não bloqueia a leitura; escolha uma vez, à mão, no Chrome dedicado.
- **Não verificado:** efeito real de `fromage`, `l` com estado inteiro, anti-bot em uso recorrente (a exploração
  foi uma visita só).

### Gupy

- **Endpoint** (capturado ao clicar em "Próxima página"; a primeira carga é renderizada no servidor):
  `GET https://portal.gupy.io/api/job-search/jobs?jobName=<termo>&limit=<n>&offset=<n>`. O portal usa `limit=12`;
  `limit=50` respondeu 200 com todas as 20 vagas (máximo não testado).
- **Resposta:** `data[]` com `id`, `name`, `description`, `careerPageName` (empresa), `city`, `state`,
  `workplaceType` (`on-site`/`hybrid`/`remote`), `type`, `publishedDate` (ISO), `applicationDeadline`, `jobUrl`
  (token em base64: usar como link, não interpretar) e `badges`; mais `pagination` (`total`, `limit`, `offset`).
- A API devolve **tudo que combina com o termo**, de `publishedDate` decrescente (a mais nova tinha 6 dias, a mais
  antiga era de 2022): a recência é filtro local por `janela_dias`. A API não filtra localidade.
- **Não verificado:** resposta a `httpx` fora do navegador (pode exigir cabeçalhos ou dar 403).

### Riscos

- **LinkedIn logado em automação viola os termos de uso**; o risco de restrição da conta existe mesmo com volume
  baixo e o limite seguro é desconhecido. Ao primeiro sinal de verificação ou aviso na conta, desligue a fonte.
- **Bloqueio recorrente** (Indeed, LinkedIn) é o cenário provável: a fonte encerra e avisa, nunca tenta resolver.
- **Seletores quebram:** é para isso que existem o estado "Refazer" e o changelog abaixo.

## Changelog

Linhas por versão, da mais antiga à mais nova. Convenção: **não verificado** = depende de execução real do usuário.

### LinkedIn

| Versão | Data | Mudança |
| --- | --- | --- |
| 1.0.0 | 2026-10-14 | Primeira versão: leitura card a card, `f_TPR=r86400`, paginação por `start=` |
| 1.0.1–1.3.0 | 2026-10-14 | Em bloqueio (CAPTCHA/login/Cloudflare) a aba fica aberta e a fonte espera a verificação manual (`VerificationGate`), retomando a página que bloqueou; sem confirmação no prazo, falha como antes |
| 1.0.2, 1.2.0 | 2026-10-14 | `modalidade` e `localidade` em lista: uma busca por palavra-chave e localidade |
| 1.1.0 | 2026-10-14 | `Job` ganha `localidade` (legenda do card); o card não traz data |
| 1.4.0, 1.5.0 | 2026-10-14/15 | `publicada_em` lida no detalhe (texto relativo "há N…" → ISO); a 1.5.0 corrige: o seletor valia só no painel lateral, e agora cada seletor é tentado em ordem e, sem data, procura-se a linha da data no texto (`find_published_line`) |
| 1.6.0 | 2026-10-15 | `location` e `f_WT` saem da URL; `Job` ganha `modalidade` (legenda do card). Localidade e modalidade filtradas localmente |
| 1.7.0 | 2026-10-15 | Limite de leitura por palavra-chave: até `[limites] max_paginas_por_termo` páginas, parando se vier vazia ou repetida |
| 1.8.0 | 2026-10-15 | `Job` ganha `palavra_chave` (a primeira que devolveu a vaga) |
| 1.8.1, 1.8.5 | 2026-10-15 | `goto` abortado (`ERR_ABORTED`) é repetido até `[navegador] max_tentativas_abertura`; depois, `http_erro` |
| 1.8.2 | 2026-10-15 | Detalhe por página: rola e tria a página, abre os detalhes elegíveis e só então pagina; uma aba por fonte |
| 1.8.3, 1.8.4 | 2026-10-15 | Localidade e modalidade canônicas da execução traduzidas para `location` e `f_WT` |
| 1.8.8–1.8.9 | 2026-10-15 | Descrição completa lida de `expandable-text-box` no painel (sem "mais" nem URL individual; URL só como reserva); `data-occludable-job-id` comparado direto, sem interpolar no seletor; cards já completos não são rolados de novo |
| 1.8.10 | 2026-10-15 | `ERR_HTTP_RESPONSE_CODE_FAILURE` registra o status HTTP e encerra a fonte, sem repetir 4xx/429 |
| 1.9.0 | 2026-10-15 | Termo com falha transitória é pulado (até `max_falhas_termo_seguidas` seguidas); HTTP 401/403/429 encerra a fonte na hora (`SourceRateLimited`), preservando o já lido |
| 1.9.1 | 2026-10-15 | Vaga cujo painel não abre é pulada e tentada na próxima execução; `max_falhas_detalhe_seguidas` falhas seguidas (ou nenhuma vaga detalhada) encerram como `seletor_nao_encontrado` |
| 1.9.2, 1.9.3 | 2026-10-15 | Pausa de detalhe `[ritmo] pausa_detalhe_min_s`–`max_s` (3–6 s) após abrir cada painel (a rajada de cliques antecedia o HTTP 429) e `intervalo_tentativa_painel_s` (15 s) entre tentativas |
| 1.9.4 | 2026-10-15 | Referência da documentação migrada para este arquivo; sem mudança de comportamento |

### Indeed

| Versão | Data | Mudança |
| --- | --- | --- |
| 1.0.0 | 2026-10-14 | Primeira versão: `div.job_seen_beacon`, `fromage=1`, paginação por `start=` |
| 1.0.1–1.3.0 | 2026-10-14 | Espera e retoma após a verificação manual (igual ao LinkedIn) |
| 1.1.0, 1.2.0, 1.6.0 | 2026-10-14/15 | `Job` ganha `localidade` e `modalidade` (por palavras: "Remoto", "Híbrido"…); `l` sai da URL e localidade e modalidade passam a ser filtradas localmente |
| 1.4.0, 1.5.0, 1.7.0 | 2026-10-14/15 | Tentativas de ler `publicada_em` (texto "Publicada há…", depois JSON-LD `datePosted`); removidas na 1.10.0 |
| 1.8.0 | 2026-10-15 | Páginas por palavra-chave (`start` de 10 em 10) |
| 1.9.0 | 2026-10-15 | `Job` ganha `palavra_chave` |
| 1.9.1–1.9.4, 1.9.6 | 2026-10-15 | Uma nova tentativa após a verificação manual; detalhes de cada página antes de paginar; `l` traduzido da localidade canônica; `ERR_ABORTED` repetido e `ERR_HTTP_RESPONSE_CODE_FAILURE` registrado sem repetição |
| 1.10.0–1.10.2 | 2026-10-15 | Descrição lida no painel `DESKTOP_EMBEDDED` (clique em `a[data-jk]`, `.simple-job-description-html`), sem `/viewjob`; data deixa de ser coletada; abertura do painel repetida até `max_tentativas_painel`; `EXTRACT_JS` ignora as iscas invisíveis. Observado no DOM real (15 vagas lidas, 1 isca excluída) |
| 1.11.0–1.11.3 | 2026-10-15 | Igual ao LinkedIn: termos com falha transitória pulados, 401/403/429 encerram a fonte preservando o parcial, painel que não abre não derruba a fonte, pausa de detalhe e 15 s entre tentativas |
| 1.11.4 | 2026-10-15 | Referência da documentação migrada para este arquivo; sem mudança de comportamento |

### Gupy

| Versão | Data | Mudança |
| --- | --- | --- |
| 1.0.0 | 2026-10-14 | Primeira versão: `portal.gupy.io/api/job-search/jobs` (`jobName`, `limit`, `offset`) |
| 1.1.0 | 2026-10-14 | `modalidade` em lista: uma busca por modalidade, vagas unidas sem repetir |
| 1.2.0 | 2026-10-14 | `Job` ganha `localidade` (`city, state`) e `publicada_em` (`publishedDate`) |
| 1.3.0 | 2026-10-15 | `workplaceType` sai da busca (uma por palavra-chave); `Job` ganha `modalidade`; localidade e modalidade filtradas localmente |
| 1.4.0, 1.5.0 | 2026-10-15 | Páginas da API por palavra-chave; `Job` ganha `palavra_chave` |
| 1.5.1, 1.5.2 | 2026-10-15 | Explicita que a API não suporta localidade (filtro local); modalidade canônica traduzida para `workplaceType` |
| 1.6.0 | 2026-10-15 | Aplica `[busca] janela_dias` a `publishedDate` antes da deduplicação; vaga sem `publishedDate` permanece, para não gerar falso negativo |
| 1.6.1 | 2026-10-15 | Referência da documentação migrada para este arquivo; sem mudança de comportamento |

A fonte **Google** (0.1.0–0.3.0, seletores nunca observados) foi removida em 15/10/2026 a pedido do usuário:
código, `[google]` da config, amostras e testes apagados; execuções antigas com `fonte = google` seguem no banco.
