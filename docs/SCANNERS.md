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

## Como o usuário comum recebe um scanner corrigido

O usuário instalado pelo `install.ps1` não tem o repositório nem o Claude Code: o scanner corrigido chega **dentro de uma versão nova do app**.

1. Quem mantém o projeto refaz o scanner (seção abaixo), sobe a versão em `scanners.toml` e gera o pacote com `scripts/build-release.ps1 -Versao X.Y.Z` (grava `versao.txt`).
2. Publica com `gh release create vX.Y.Z release/peneira.zip`.
3. Na tela Vagas do usuário aparece o aviso **Há uma versão nova** (consulta à última Release do GitHub, só a versão; desligável em `[atualizacao] verificar`). Ele fecha o programa e roda `peneira atualizar`, que reinstala só o app; banco, config, logs e perfil do Chrome ficam.

O alerta **Refazer** (instrução para o Claude) continua sendo para quem mantém o projeto; o usuário comum só precisa atualizar. A versão do app (`versao.txt`) é distinta da versão de cada scanner (`scanners.toml`).

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
| linkedin | 1.0.1 | 2026-10-14 | Em bloqueio (CAPTCHA/login/Cloudflare) a aba fica aberta para o usuário concluir a verificação à mão (`playwright_session`); sem mudança no que a fonte lê |
| indeed | 1.0.1 | 2026-10-14 | Em bloqueio (CAPTCHA/login/Cloudflare) a aba fica aberta para o usuário concluir a verificação à mão (`playwright_session`); sem mudança no que a fonte lê |
| linkedin | 1.0.2 | 2026-10-14 | `modalidade` passa a ser lista: `f_WT` leva os códigos separados por vírgula (ex.: `2,3`). Não verificado: aceitação de vários valores em `f_WT` pelo LinkedIn |
| gupy | 1.1.0 | 2026-10-14 | `modalidade` passa a ser lista: uma busca por modalidade (`workplaceType` com um valor, como observado), vagas unidas sem repetir. Sem modalidade, uma busca sem filtro |
| google | 0.1.0 | 2026-10-14 | Primeira versão (0.x = **seletores não observados no DOM real**): `google.com/search` com `q` (consulta booleana inteira de `[google] consultas`), `tbs=qdr:d<N>` e `start=`; resultados `#search a` com `h3` e trecho em `[data-sncf]`/`.VwiC3b`; bloqueio por `/sorry`, "tráfego incomum", `consent.google.com` e `accounts.google.com`. Não verificado: todos os seletores, efeito de `tbs` e da paginação por `start=`, frequência de CAPTCHA. Rodar "Documentar plataforma" para o Google antes de subir para 1.0.0 |
| linkedin | 1.1.0 | 2026-10-14 | `Job` ganha `localidade` (legenda do card, já lida como trecho). O card não traz data de publicação: `publicada_em` fica vazio. Sem mudança nos seletores |
| indeed | 1.1.0 | 2026-10-14 | `Job` ganha `localidade` (`[data-testid="text-location"]`, seletor já observado) no JS de extração. O card não traz data: `publicada_em` fica vazio |
| gupy | 1.2.0 | 2026-10-14 | `Job` ganha `localidade` (`city, state`) e `publicada_em` (`publishedDate`), campos já presentes na resposta. Campo ausente deixa vazio, não é mudança de layout |
| linkedin | 1.2.0 | 2026-10-14 | `search_url(termo, start, localidade)`: `location` vem de uma das `[busca] localidades` (uma busca por palavra-chave e localidade), não mais de um texto único. Não verificado: `location` com estado ("Minas Gerais") |
| indeed | 1.2.0 | 2026-10-14 | `search_url(termo, start, localidade)`: `l` vem de uma das `[busca] localidades`. Não verificado: `l` com estado inteiro |
| google | 0.1.1 | 2026-10-14 | `search_url` aceita `localidade` e a ignora; `GoogleSource` não multiplica as consultas pelas localidades |
| linkedin | 1.3.0 | 2026-10-14 | Em bloqueio a fonte espera o usuário concluir a verificação (`VerificationGate`) e retoma reabrindo a página que bloqueou; sem confirmação no prazo, falha como antes. Sem mudança no que a fonte lê |
| indeed | 1.3.0 | 2026-10-14 | Idem LinkedIn: espera e retoma após a verificação manual |
| google | 0.2.0 | 2026-10-14 | Idem LinkedIn: espera e retoma após a verificação manual (`/sorry`, consentimento, login) |
| google | 0.3.0 | 2026-10-14 | `search_url(termo, start, localidade)` monta a consulta de palavra-chave + localidade + termos da modalidade, em vez de receber a consulta pronta (sem `site:`; os sites foram removidos a pedido do usuário); `GoogleSource` volta a usar as palavras-chave do painel e o filtro local. Seletores do DOM seguem não observados. Não verificado: aceitação da consulta pelo Google (limite de 32 palavras) |
| linkedin | 1.4.0 | 2026-10-14 | `publicada_em` passa a ser lida no detalhe da vaga (texto relativo "há N horas/dias/semanas/meses" → ISO), com o seletor já observado da descrição do topo. Só vagas cujo detalhe foi aberto ganham data. Não verificado: formato do texto em vagas sem "há" e com a interface em inglês |
| indeed | 1.4.0 | 2026-10-14 | `publicada_em` passa a ser lida no detalhe da vaga: busca "Publicada há N dias"/"Posted N days ago"/"hoje" no texto do `body` (conversão em `relative_date.py`, compartilhada com o LinkedIn). **Não verificado no DOM real**: texto exato e posição da data na página de detalhe; se não achar, a vaga fica sem data |
| linkedin | 1.6.0 | 2026-10-15 | `search_url(termo, start)`: `location` e `f_WT` saem da busca; `Job` ganha `modalidade`, lida da legenda do card ("(Presencial)"). Localidade e modalidade passam a ser filtradas localmente. **Não verificado no DOM real**: formato da legenda em todas as vagas |
| indeed | 1.6.0 | 2026-10-15 | `search_url(termo, start)`: `l` sai da busca; `Job` ganha `modalidade`, lida da localidade e dos itens do card por palavras ("Remoto", "Híbrido"…). Localidade e modalidade filtradas localmente. **Não verificado no DOM real**: o card quase não informa modalidade |
| gupy | 1.3.0 | 2026-10-15 | `workplaceType` sai da busca (uma busca por palavra-chave, não por modalidade); `Job` ganha `modalidade`, de `workplaceType` (`remote`/`hybrid`/`on-site`). Localidade e modalidade filtradas localmente |
| google | removido | 2026-10-15 | Fonte removida a pedido do usuário: `sources/google.py`, `[google]` da config, amostras e testes apagados; sai de `scanners.toml`, do registro de fontes e da tela. Execuções antigas com `fonte = google` seguem no banco |
| linkedin | 1.5.0 | 2026-10-15 | Data de publicação não vinha na prática: o seletor foi observado no painel lateral da busca, mas a fonte abre `/jobs/view/<id>/`. Agora cada seletor é tentado em ordem e, sem data em nenhum, procura no texto da página uma linha que seja inteira a data ("Há 3 dias", "Anunciada novamente há 8 horas"; `find_published_line`, sem depender de classe CSS). Sem mudança nos seletores. **Não verificado no DOM real** (execução é do usuário): se a página de detalhe não tiver a data em linha própria, a vaga segue sem data e o log avisa |
| indeed | 1.5.0 | 2026-10-15 | Idem LinkedIn para a busca da linha da data no texto da página; a leitura do `body` passa a aceitar também "Publicado"/"Postado" (masculino) além de "Publicada"/"Posted". "Ativa há…" e "há mais de 30 dias" seguem ignorados. Execução com vagas sem data passa a gravar no log "N de M vagas … sem data de publicação". **Não verificado no DOM real** |
| indeed | 1.7.0 | 2026-10-15 | `publicada_em` passou a vir do JSON-LD do detalhe (`JobPosting.datePosted`, ISO exato), observado em HTML real salvo pelo usuário. O texto "Publicada há…" não existe na página (só "Recém publicada" em JSON interno); o texto do `body` ficou como reserva. A amostra e essa leitura foram removidas no scanner 1.10.0, que lê apenas o painel da listagem. |
| linkedin | 1.7.0 | 2026-10-15 | Limite de leitura por palavra-chave, não mais por fonte: cada termo abre até `[limites] max_paginas_por_termo` páginas de resultados (`start` de 25 em 25; a paginação para antes se a página vier vazia ou só repetir vagas do próprio termo). Sem mudança nos seletores nem na URL |
| indeed | 1.8.0 | 2026-10-15 | Idem LinkedIn: páginas por palavra-chave (`start` de 10 em 10). Sem mudança nos seletores nem na URL |
| gupy | 1.4.0 | 2026-10-15 | Idem LinkedIn: páginas da API por palavra-chave (`offset` de `page_size` em `page_size`). Sem mudança na API |
| linkedin | 1.8.0 | 2026-10-15 | `Job` ganha `palavra_chave`: a primeira palavra-chave cuja busca devolveu a vaga (vaga repetida em outra busca fica com a primeira). Sem mudança nos seletores nem no que a fonte lê |
| indeed | 1.9.0 | 2026-10-15 | `Job` ganha `palavra_chave`: a primeira palavra-chave cuja busca devolveu a vaga (vaga repetida em outra busca fica com a primeira). Sem mudança nos seletores nem no que a fonte lê |
| gupy | 1.5.0 | 2026-10-15 | `Job` ganha `palavra_chave`: a primeira palavra-chave cuja busca devolveu a vaga (vaga repetida em outra busca fica com a primeira). Sem mudança nos seletores nem no que a fonte lê |
| linkedin | 1.8.1 | 2026-10-15 | Após a verificação manual, se a reabertura da página falha (`goto` abortado pelo redirecionamento do site), tenta mais uma vez após a pausa, em vez de encerrar a fonte com `http_erro`. Sem mudança nos seletores nem no que a fonte lê |
| indeed | 1.9.1 | 2026-10-15 | Idem LinkedIn: uma nova tentativa de reabrir a página após a verificação manual |
| linkedin | 1.8.2 | 2026-10-15 | Busca e detalhe passam a ocorrer por página: depois de rolar e triar uma página, abre imediatamente os detalhes elegíveis antes de continuar a paginação; mantém uma aba por fonte |
| indeed | 1.9.2 | 2026-10-15 | Idem LinkedIn: abre os detalhes elegíveis de cada página antes de continuar a paginação |
| linkedin | 1.8.3 | 2026-10-15 | A localidade canônica da execução é traduzida para o parâmetro `location` da busca |
| indeed | 1.9.3 | 2026-10-15 | A localidade canônica da execução é traduzida para o parâmetro `l` da busca |
| linkedin | 1.8.5 | 2026-10-15 | `goto` abortado (`ERR_ABORTED`) é repetido até `[navegador] max_tentativas_abertura`; depois a fonte falha como `http_erro` |
| indeed | 1.9.4 | 2026-10-15 | Idem LinkedIn: `goto` abortado (`ERR_ABORTED`) é repetido até `[navegador] max_tentativas_abertura`; depois a fonte falha como `http_erro` |
| gupy | 1.5.1 | 2026-10-15 | A camada de consulta explicita que a Gupy não suporta localidade na API observada; o filtro local permanece como fallback |
| linkedin | 1.8.4 | 2026-10-15 | A modalidade canônica é traduzida para `f_WT` (`1` remoto, `2` presencial, `3` híbrido) |
| gupy | 1.5.2 | 2026-10-15 | A modalidade canônica é traduzida para `workplaceType` (`remote`, `on-site` ou `hybrid`); localidade segue como filtro local |
| linkedin | 1.8.10 | 2026-10-15 | `goto` com `ERR_HTTP_RESPONSE_CODE_FAILURE` (observado ao abrir a segunda página) registra o status HTTP recebido e encerra a fonte, sem repetir uma possível resposta 4xx/429; `ERR_ABORTED` mantém as tentativas configuradas |
| indeed | 1.9.6 | 2026-10-15 | Idem LinkedIn: `ERR_HTTP_RESPONSE_CODE_FAILURE` registra o status HTTP e não é repetido |
| indeed | 1.10.0 | 2026-10-15 | A descrição completa passa a ser lida no painel `DESKTOP_EMBEDDED`: clica em `a.jcs-JobTitle[data-jk]` da listagem e extrai `#jobDescriptionText`/`.jobsearch-JobComponent-description`, sem abrir `/viewjob`. A data deixa de ser coletada, pois `datePublished` do painel capturado é nulo; se o painel não abrir, a fonte falha como seletor alterado, sem fallback de URL. |
| indeed | 1.10.1 | 2026-10-15 | Corrige a abertura do painel: usa `a[data-jk]`, o identificador estável da vaga, em vez da classe visual `jcs-JobTitle` removida pelo site. A abertura do painel é repetida até `[navegador] max_tentativas_painel` antes de registrar `seletor_nao_encontrado`. |
| indeed | 1.10.2 | 2026-10-15 | `EXTRACT_JS` ignora os cards-isca invisíveis da listagem (caixa 0×0, `data-jk` falso, link `/viewjob`): clicá-los tirava a página da listagem e o painel da vaga seguinte "não abria" (`seletor_nao_encontrado`). A descrição passa a ser lida em `.simple-job-description-html`, pois `#jobDescriptionText` não existe mais no painel. Observado no DOM real em 15/10/2026 (15 vagas abertas e lidas, 1 isca excluída). |
| gupy | 1.6.0 | 2026-10-15 | Aplica localmente `[busca] janela_dias` a `publishedDate` antes da deduplicação; vaga anterior ao corte não é devolvida. A API não oferece parâmetro de recência observado; vaga sem `publishedDate` permanece para não gerar falso negativo. |
| linkedin | 1.9.0 | 2026-10-15 | Termo que falha por erro transitório (timeout, 5xx, `ERR_ABORTED` esgotado) é pulado e a busca segue com o próximo, até `[navegador] max_falhas_termo_seguidas` falhas seguidas. HTTP 401/403/429 vira `SourceRateLimited`: encerra a fonte na hora, sem repetir nem pular termos; o que já foi lido e gravado continua contado na fonte. |
| indeed | 1.11.0 | 2026-10-15 | Idem LinkedIn: termos com falha transitória são pulados; HTTP 401/403/429 encerra a fonte preservando o parcial. |
| linkedin | 1.9.1 | 2026-10-15 | Vaga cujo painel/detalhe não abre é pulada (não gravada, tentada de novo na próxima execução); `[navegador] max_falhas_detalhe_seguidas` falhas seguidas, ou nenhuma vaga detalhada, encerram a fonte como `seletor_nao_encontrado`. |
| indeed | 1.11.1 | 2026-10-15 | Idem LinkedIn: um painel que não abre (`Não abriu o painel da vaga … após 3 tentativa(s)`) não derruba mais a fonte inteira. |
| linkedin | 1.9.2 | 2026-10-15 | Depois de abrir o painel de cada vaga a fonte espera `[ritmo] pausa_detalhe_min_s`–`pausa_detalhe_max_s` (3–6 s), em vez da pausa de rolagem (0,25–0,7 s): a rajada de cliques de detalhe antecedia o HTTP 429 na abertura da página 2. |
| indeed | 1.11.2 | 2026-10-15 | Idem LinkedIn: pausa de detalhe configurável depois de abrir cada painel (código de espera compartilhado). |

## Refazer só a documentação das plataformas

Para atualizar `EXPLORACAO_PLATAFORMAS.md` sem esperar um scanner quebrar (por exemplo, antes de uma validação ou
depois de um aviso de atenção), use a tela **Execuções → Refazer a documentação das plataformas**: escolha
todas as plataformas ou uma, clique em **Gerar instrução para refazer a documentação** e cole a instrução
copiada numa sessão do Claude Code neste repositório.

A instrução pede **apenas documentação**: o Claude repete a busca com as suas palavras-chave, registra URL,
seletores, paginação, filtro de data, formato da resposta e sinais de bloqueio (marcando o que foi verificado e
o que não foi), compara com o que os adaptadores usam hoje e **lista as divergências sem alterar o código**.
Se houver divergência, ele pergunta se deve atualizar os scanners; aí vale o procedimento da seção anterior
(TDD, nova versão em `scanners.toml`, changelog).

As regras de segurança vão junto na instrução: só o Chrome dedicado, sem abrir vagas para candidatura, sem
aceitar cookies nem digitar credenciais, sem resolver CAPTCHA nem contornar bloqueios.

O scanner LinkedIn 1.8.9 compara o atributo `data-occludable-job-id` de cada card diretamente, sem interpolar o ID em um seletor CSS. Isso evita erro de sintaxe quando o ID e serializado com aspas.

O LinkedIn compartilha a leitura progressiva com o Indeed. Cards que jÃ¡ chegam completos no DOM nÃ£o sÃ£o rolados novamente; somente cards lazy incompletos recebem a rolagem e a pausa configurada.

O scanner LinkedIn 1.8.8 lÃª a descriÃ§Ã£o completa de `data-testid="expandable-text-box"` pelo `textContent` do painel lateral, sem acionar “mais” e sem navegar para a URL individual da vaga. O tÃ­tulo do card ainda Ã© acionado para carregar o painel; se ele nÃ£o abrir, a URL individual continua como fallback.
