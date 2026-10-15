# LESSONS.md — Erros e Lições

Registro de erros reais, armadilhas e remoções de feature. Começa vazio: cada entrada nasce de algo que
aconteceu no projeto. Não registre refactors nem ajustes sem impacto lógico.

## Quando registrar

- Vaga duplicada, vaga relevante perdida ou vagas irrelevantes em massa.
- Mudança de comportamento de regra (filtro, pontuação, deduplicação, falha explícita).
- Mudança de seletor, de endpoint ou de resposta de uma fonte (LinkedIn, Indeed, Gupy).
- Bloqueio, CAPTCHA, restrição de conta ou limitação de taxa — o que disparou e o que mudou.
- Falha de dados: banco, migração, perda de histórico de execuções.
- Falha estrutural ou erro relevante de integração (CDP, execução em segundo plano, front × API).
- **Remoção de feature** — sempre.

## Formato

Uma entrada por problema, em ordem cronológica dentro de cada seção, com data (AAAA-MM-DD):

```
### <título curto> (AAAA-MM-DD)
- **Contexto**: onde e quando apareceu.
- **Causa raiz**: o que de fato estava errado.
- **Impacto**: o que quebrou ou distorceu (com números quando houver).
- **Correção**: o que foi feito (commit/versão).
- **Risco futuro**: como o erro pode voltar e o que checar.
```

**Remoção de feature** — use este formato no lugar:

```
### Remoção: <feature> (AAAA-MM-DD)
- **Como funcionava**: lógica suficiente para recriá-la.
- **Parâmetros removidos**: chaves de config, colunas, módulos.
- **Motivo**: por que saiu.
```

## Seções

Crie conforme a necessidade; sugestão inicial:

1. Filtro e deduplicação
2. Fontes (seletores, endpoints, bloqueios)
3. Dados e migrações
4. Remoções de feature
5. Armadilhas técnicas (CDP, execução em segundo plano, polling)

## Regras

- Se a entrada alterar o comportamento do sistema, atualize o `ARCHITECTURE.md` na mesma sessão.
- Se uma regra de prevenção ficar clara, ela vai para o `CODE_QUALITY.md`; aqui fica só o caso real que a
  originou.
- Não duplique o que o `ARCHITECTURE.md` já descreve: registre o erro, não o mecanismo atual.
- Nunca cole cookies ou dados pessoais em uma entrada.

---

## Entradas

### Indeed: cards-isca invisíveis quebravam a abertura do painel (2026-10-15)
- **Contexto**: execução real do Indeed falhou com "Não abriu o painel da vaga … após 3 tentativa(s)" (`seletor_nao_encontrado`), em vagas que existiam na listagem.
- **Causa raiz**: a listagem traz `div.job_seen_beacon` falsos (caixa 0×0, `data-jk` inventado, link `/viewjob`, título copiado de outra vaga; mudam a cada carga). O extrator os coletava; o clique neles navegava para `/viewjob`, os cards reais saíam do DOM e o painel da vaga seguinte nunca abria. Efeito colateral: abrir `/viewjob` é o que já havia gerado bloqueio Cloudflare. Além disso, `#jobDescriptionText` já não existe no painel (a descrição está em `.simple-job-description-html`).
- **Impacto**: a fonte encerrava a execução na primeira vaga depois de uma isca; a descrição completa não era lida.
- **Correção**: scanner `indeed` 1.10.2: só cards com área visível; `.simple-job-description-html` primeiro nos seletores do detalhe. Validado numa carga real (15 vagas abertas, 1 isca excluída). Lição: a contagem "16 no DOM, 15 no texto" da exploração já indicava a isca; divergência assim deve ser explicada antes de seguir.
- **Risco futuro**: o Indeed pode trocar a técnica da isca (por exemplo, posicionar fora da tela em vez de 0×0) ou renomear o contêiner da descrição; a falha explícita continua pedindo nova exploração.

### Indeed: descrição no painel, sem abrir a vaga individual (2026-10-15)
- **Antes:** o scanner abria `/viewjob?jk=…` para cada vaga nova, para ler a descrição e o JSON-LD `datePosted`.
- **Depois:** clica no título do card pelo `data-jk` e lê a descrição completa no painel `DESKTOP_EMBEDDED` da listagem. Se o painel não abrir, falha como mudança de seletor; não há fallback para a URL individual.
- **Motivo:** a captura real da listagem confirmou `autoOpenTwoPaneViewjobResponse.sanitizedJobDescription`. A resposta do painel tem `datePublished: null`, então `publicada_em` deixa de ser coletada; a recência permanece sob `fromage` e deduplicação.
- **Risco futuro:** o Indeed pode mudar o comportamento do título ou os seletores do painel; o teste cobre o clique por `data-jk`, e a falha explícita pede nova exploração em vez de navegar silenciosamente.

### `ERR_HTTP_RESPONSE_CODE_FAILURE` na paginação do LinkedIn (2026-10-15)
- **Contexto**: depois da primeira página, a abertura de `start=25` falhou com `net::ERR_HTTP_RESPONSE_CODE_FAILURE` e a fonte encerrou após uma única tentativa.
- **Causa raiz**: `ERR_HTTP_RESPONSE_CODE_FAILURE` é a forma como o Chromium informa que a navegação recebeu uma resposta HTTP malsucedida; o código anterior descartava o status (por exemplo, 403, 429 ou 5xx), que é a causa acionável.
- **Impacto**: o detalhe mostrava apenas um erro genérico e levava à tentativa equivocada de tratar qualquer resposta HTTP como transitória.
- **Correção**: a abertura captura o status da resposta principal e o inclui no detalhe da falha. A fonte não repete `ERR_HTTP_RESPONSE_CODE_FAILURE`, pois 4xx/429 podem ser login, bloqueio ou limitação de taxa; só `ERR_ABORTED` mantém as tentativas configuradas.
- **Risco futuro**: se o Chromium não emitir a resposta antes de falhar, o status continuará ausente; nesse caso o detalhe preserva o erro original e a execução real do usuário é necessária para diagnosticar a infraestrutura da plataforma.

### Primeiro erro de abertura encerrava a fonte inteira (2026-10-15)
- **Contexto**: no LinkedIn, a abertura de `start=25` do termo "Engenheiro Mecânico" recebeu HTTP 429 e a fonte falhou, perdendo os demais termos e os contadores do que já havia sido gravado.
- **Causa raiz**: qualquer `SourceUnavailable` subia direto até a execução, sem distinguir erro transitório de limitação de taxa; o parcial lido não era contado.
- **Impacto**: um timeout isolado cancelava os termos restantes; a linha da fonte mostrava 0 vagas mesmo com vagas já gravadas.
- **Correção**: erro transitório pula só o termo (até `max_falhas_termo_seguidas` seguidas); 401/403/429 vira `SourceRateLimited` e encerra a fonte sem retentativa, conforme a regra de não contornar limitação de taxa; os contadores parciais são gravados na falha.
- **Risco futuro**: o 429 em si só diminui com ritmo mais lento (`pausa_*`, `max_paginas_por_termo`), decisão do usuário; esperar e repetir seria insistir numa fonte que pediu para parar.

### Uma vaga com painel que não abre derrubava o Indeed inteiro (2026-10-15)
- **Contexto**: "Não abriu o painel da vaga 5d2a882098ab92fc em indeed após 3 tentativa(s)" encerrou a fonte, apesar de as demais vagas abrirem.
- **Causa raiz**: `SourceLayoutChanged` de uma única vaga subia direto; não havia distinção entre seletor quebrado (todas falham) e vaga isolada (removida, lenta, isca).
- **Correção**: a vaga é pulada e a próxima segue; `max_falhas_detalhe_seguidas` falhas seguidas, ou zero vagas detalhadas, mantêm a falha de seletor.
- **Risco futuro**: pular esconde vagas persistentemente problemáticas; o aviso fica no log e a vaga volta na próxima execução.

### `ERR_ABORTED` sem contexto suficiente no Indeed (2026-10-15)
- **Contexto**: a abertura de uma vaga do Indeed falhou em `page.goto` com `net::ERR_ABORTED`; a tela mostrava apenas uma mensagem técnica curta.
- **Causa raiz**: o Playwright interrompeu a navegação durante a espera por `domcontentloaded`; o erro original não trazia a etapa nem o limite de tentativas no detalhe apresentado ao usuário.
- **Impacto**: ficou difícil distinguir falha na busca de falha no detalhe e diagnosticar se o limite de tentativas havia sido atingido.
- **Correção**: o detalhe agora informa fonte, etapa, URL, tentativas realizadas/limite e erro original; o botão **Ver detalhes** continua exibindo a mensagem completa sem expor dados da sessão.
- **Risco futuro**: `ERR_ABORTED` pode continuar sendo causado por redirecionamento, login ou bloqueio externo; verificar o detalhe e o log antes de alterar seletores.

### Detalhes só depois de toda a paginação (2026-10-15)
- **Contexto**: execução real do LinkedIn e do Indeed; o navegador passava vários minutos rolando resultados sem abrir uma vaga.
- **Causa raiz**: `BrowserSource.search` precisava concluir todas as palavras-chave e páginas antes de o serviço chamar `enrich`.
- **Impacto**: a descrição completa só começava a ser coletada depois de toda a rolagem; execuções longas pareciam travadas e podiam ser interrompidas antes do detalhe.
- **Correção**: scanners LinkedIn `1.8.2` e Indeed `1.9.2` intercalam triagem, detalhe e paginação, mantendo uma aba por fonte e sem abrir detalhes rejeitados.
- **Risco futuro**: se o fluxo voltar a separar `search` e `enrich`, o sintoma reaparece; manter teste que verifica a ordem página → detalhe → próxima página.

### Remoção: copiar perfil do Chrome pessoal (2026-10-14)
- **Como funcionava**: botão "Copiar perfil" na aba Vagas (`GET /api/browser/profiles`, `POST /api/browser/profile/copy`).
  `chrome_profile.py` lia o `Local State` do Chrome pessoal, copiava a pasta do perfil escolhido (ignorando caches) para
  `chrome-profile.tmp`, trocava pelo `chrome-profile/` no fim (o antigo ia para `backups/`) e gravava o marcador
  `peneira-de-vagas-profile.json`; o Chrome dedicado abria com `--profile-directory=<pasta copiada>`. A tela mostrava um alerta
  enquanto nenhum perfil fora copiado.
- **Parâmetros removidos**: `[navegador] chrome_user_data_dirs` e `copy_ignore`; módulo `services/chrome_profile.py`;
  schemas `ProfileOut`, `ProfilesOut`, `CopyProfileIn`, `CopyProfileOut`; componente `ProfileCopy`, hooks `useProfiles`
  e `useCopyProfile`.
- **Motivo**: decisão do usuário, ao pensar em tornar o projeto comercial. A cópia podia não manter o login (cookies presos
  à instalação do Chrome) e levava cookies e sessões do perfil pessoal para outra pasta. O Chrome dedicado agora sempre
  nasce vazio e o login é à mão.

### "Limpar execuções" não removia nada (2026-10-14)
- **Contexto**: aba Execuções. O botão não tinha efeito visível.
- **Causa raiz**: `jobs.run_id` era `NOT NULL` com FK, então a limpeza preservava toda execução que originou vagas; com todas as execuções tendo originado vagas, `removidas=0`.
- **Impacto**: histórico impossível de limpar enquanto as vagas existissem (6 execuções no caso real).
- **Correção**: esquema v5 (`jobs.run_id` anulável, `ON DELETE SET NULL`, cópia do `.db` antes da migração); a limpeza apaga todas as execuções e as vagas ficam sem execução de origem. Regra anterior registrada no ARCHITECTURE.
- **Risco futuro**: vaga com `run_id` nulo perde o critério de ordenação por execução (`run_id DESC`); a ordem padrão cai para pontos e id.

### Regra alterada: bloqueio espera o usuário (2026-10-14)

- **Antes:** CAPTCHA/Cloudflare/login encerravam a fonte na hora (`SourceBlocked`) e a verificação só podia ser feita para a execução seguinte, recomeçando a busca.
- **Depois:** a fonte pausa com a aba aberta; o botão **Já concluí a verificação** (`POST /api/verificacao/{fonte}/confirmar`) a retoma na página que bloqueou. Prazo `[navegador] espera_verificacao_s`; esgotado, falha como antes. Decisão do usuário; a verificação continua sendo feita só à mão, sem resolver CAPTCHA nem disfarçar a automação.

### Regra alterada: abas em paralelo (2026-10-14)

- **Antes:** "sem abas em paralelo" — as fontes rodavam sempre em sequência.
- **Depois:** com `[navegador] abas_paralelas = true` (padrão `false`) as fontes rodam ao mesmo tempo, uma aba por plataforma, cada uma com as próprias pausas. Decisão do usuário; continua proibido abrir várias abas na mesma plataforma e rodar mais de uma execução por vez. Ligar/desligar pela aba Configurações (grupo Navegador, `PUT /api/config`); vale a partir da próxima busca.

### Remoção: consultas booleanas prontas do Google (2026-10-14)
- **Como funcionava**: `[google] consultas` guardava consultas completas (`site:… intitle:(…) -"US only" …`), enviadas inteiras em `q`; `GoogleSource` ignorava as palavras-chave, localidades e modalidade da tela e tinha `local_filter = False` (vagas com `pontos = 0`, sem exclusões).
- **Parâmetros removidos**: `[google] consultas`; `GoogleSource.local_filter`/`search`/`_localidades`. Entra `[google] modalidade_termos`. Uma versão intermediária restringia a `[google] sites` (lever, greenhouse…); removida a pedido do usuário, a consulta não restringe o site.
- **Motivo**: o exemplo de desenvolvimento da config era buscado de verdade, ignorando o que o usuário cadastrou; além disso passava de 32 palavras (limite do Google) e usava `intitle:(…)`, que o Google não agrupa, e voltava "não encontrou nenhum documento". Hoje a consulta nasce da tela.

### Remoção: fonte Google (2026-10-15)
- **Como funcionava**: quarta fonte (`GoogleSite` + `GoogleSource`, `sources/google.py`): uma busca em `google.com/search` por palavra-chave e localidade, com os termos da modalidade, lendo o resultado (título e trecho) sem abrir a página da vaga. Seletores nunca observados no DOM real; a fonte falhava com `zero_resultados` e pedia CAPTCHA.
- **Parâmetros removidos**: seção `[google]` (`base_url`, `page_size`, `modalidade_termos`) e a validação em `config.py`; scanner `google` do `scanners.toml`; `GoogleSource`/`GoogleSite`, amostras e testes; fonte no registro, na tela Vagas (checkbox), na cor do selo e nos rótulos. A exceção de verificação manual do Google pelo agente saiu do `AI_GUIDELINES.md`.
- **Motivo**: decisão do usuário. A fonte não trazia vagas úteis (zero resultados, bloqueio) e mantê-la custava um adaptador sem seletores verificados.

### Regra alterada: detalhe de todas as vagas novas, sem teto (2026-10-15)
- **Antes:** `[limites] max_paginas_detalhe = 15`: só as 15 primeiras vagas novas de cada fonte tinham o detalhe aberto; as demais entravam sem descrição (filtradas só por título e card) e sem data de publicação.
- **Depois:** o detalhe é aberto para **todas** as vagas novas aprovadas na lista; o limite passa a ser só `[limites] max_vagas_lista` (100 por fonte). Parâmetro `max_paginas_detalhe` removido (config, schema da API, tela Configurações e Execuções). As pausas variáveis e uma aba por plataforma continuam.
- **Motivo**: pedido explícito do usuário (ler a descrição completa de todas as vagas). **Risco registrado**: mais páginas por execução aumentam a chance de bloqueio (o Indeed já devolveu Cloudflare em `/viewjob`); o bloqueio continua encerrando a fonte, sem contorno.

### Regra alterada: localidade e modalidade filtradas nas vagas listadas, não na busca (2026-10-15)
- **Antes:** localidade e modalidade da config iam na busca de cada plataforma (`location`/`l`, `f_WT` no LinkedIn, `workplaceType` na Gupy), com uma busca por localidade (e, na Gupy, por modalidade). O Indeed não filtrava modalidade e a Gupy não filtrava localidade; o resultado dependia de como cada plataforma interpreta o filtro (o LinkedIn casa por região, o `l` do Indeed por área).
- **Depois:** a busca leva só palavra-chave, recência e página. `Job` ganha `modalidade` e um filtro local único (`services/localizacao.py`) decide sobre as vagas listadas, igual para todas as fontes. Vaga com dado desconhecido segue `[filtro] aceitar_desconhecido` (padrão `true`: passa).
- **Motivo:** decisão do usuário: os filtros de busca das plataformas não são padronizados. **Custo:** a lista traz vagas de qualquer lugar (mais cards lidos, e os detalhes só são abertos para as aprovadas). Limitação conhecida: a localidade é texto livre; "São Paulo" (cidade) casa também o estado.
- **Tela:** a aba Configurações deixou de editar localidades e modalidade (pedido do usuário); os valores ficam só no `config.toml`, e a tela preserva `busca.localidades`/`modalidade` ao salvar as demais opções. A aba Execuções segue exibindo os valores em vigor.

### Indeed: data de publicação procurada no lugar errado (2026-10-15)
- **Contexto**: execução real do Indeed; log "33 de 33 vagas abertas no detalhe ficaram sem data de publicação" mesmo após as versões 1.4.0 e 1.5.0.
- **Causa raiz**: as duas versões procuravam "Publicada há N dias" no texto do `body` sem nunca terem visto o HTML real. A página de detalhe não tem esse texto; a data exata está no JSON-LD (`<script type="application/ld+json">`, `JobPosting.datePosted`).
- **Impacto**: todas as vagas do Indeed ficavam sem `publicada_em` (coluna "Publicada" vazia; `max_dias` nunca as descartava).
- **Correção**: scanner `indeed` 1.7.0 lê `datePosted`; o texto do `body` ficou como reserva. Lição: seletor de fonte só entra com HTML real salvo como amostra de teste.


### Remoção: filtro único `localidade` da listagem (2026-10-15)
- **Como funcionava**: `GET /api/jobs?localidade=` e o corpo de `POST /api/jobs/mark-seen` filtravam pelo texto livre da localidade (contém, sem acento); a tela tinha um campo "Localidade".
- **Parâmetros removidos**: `localidade` na listagem e em marcar como vistas, e o campo da tela. A ordenação `ordenar=localidade` continua.
- **Motivo**: pedido do usuário. O filtro virou dois, `cidade` e `estado` (derivados do texto por `split_localidade`), mais o filtro `modalidade`, agora gravada na coluna `jobs.modalidade` (migração v6, não destrutiva).

### Remoção: filtros `cidade` e `estado` da listagem, unificados em `local` (2026-10-15)
- **Como funcionava**: `GET /api/jobs?cidade=&estado=` e o corpo de `POST /api/jobs/mark-seen` filtravam cidade e UF em campos separados; a tela tinha dois campos e uma lista de modalidade.
- **Parâmetros removidos**: `cidade` e `estado` na listagem e em marcar como vistas, e os campos "Cidade", "Estado" e o seletor "Modalidade" da tela. `modalidade` segue aceito pela API (a tela não o envia mais).
- **Motivo**: pedido do usuário. Um campo só (`local`) casa cidade, UF ou modalidade; o backend decide, o front só envia o texto.

### Remoção: botão Interromper e cancelamento da execução (2026-10-15)
- **Como funcionava**: `POST /api/runs/{id}/cancel` acendia um `threading.Event` por execução (`app.state.cancel`) e o `VerificationGate.cancel()`; `run_service` e `BrowserSource` checavam o evento entre etapas, páginas e vagas e levantavam `SourceInterrupted`; o front tinha o botão **Interromper** (`useCancelRun`).
- **Parâmetros removidos**: a rota `cancel`, `app.state.cancel`, o argumento `cancel` de `execute_run`/`start_run`, `SourceInterrupted`, `VerificationGate.cancel/check/reset`, `runs.ensure_running`. O motivo `interrompida` continua: é o que `db.close_stale_runs` grava quando o processo cai no meio de uma execução.
- **Motivo**: pedido do usuário. Agora a execução só termina sozinha (ou ao fechar o app); a espera de verificação manual acaba ao confirmar ou no prazo de `espera_verificacao_s`.

### Regra alterada: limite de páginas por palavra-chave e de termos de busca (2026-10-15)
- **Antes:** `[limites] max_vagas_lista = 300` valia para a fonte inteira: os primeiros termos podiam consumir o teto e os últimos nem eram pesquisados. `[busca] max_termos_busca = 10` só barrava a criação de termos novos; um conjunto já maior era buscado inteiro.
- **Depois:** `[limites] max_paginas_por_termo = 3` vale para cada palavra-chave em cada fonte: abre no máximo 3 páginas de resultados (o teto de vagas, antes `max_vagas_lista` e depois `max_vagas_por_termo`, foi trocado por páginas a pedido do usuário). `[busca] max_termos_busca = 6` também vale na execução: só os 6 primeiros termos do conjunto vão às fontes (o filtro local continua pontuando com todos). Os dois são controles deslizantes na tela Configurações. Parâmetro `max_vagas_lista` removido; entra `max_paginas_por_termo` (1–10 na tela).
- **Motivo**: pedido do usuário. **Risco registrado**: o máximo de páginas abertas por fonte passa a ser 6 × 3 = 18 (vagas lidas dependem do tamanho da página do site: LinkedIn 25, Indeed 10, Gupy 50), com mais chance de bloqueio quanto maior o valor; o bloqueio continua encerrando a fonte, sem contorno.

### Regra alterada: palavras-chave separadas em busca (query) e ranking (pontuação) (2026-10-15)
- **Antes:** uma lista de palavras `busca` por conjunto servia à query (uma busca por palavra, por fonte) e à pontuação das vagas.
- **Depois:** três grupos por conjunto: `busca` (só gera queries, limitada por `max_termos_busca`), `ranking` (só pontua, sem teto) e `exclusao`. A pontuação soma `busca` + `ranking` (termo nos dois grupos conta uma vez); `min_score` corta pelo total. Migração 8 do banco: `keywords.tipo` aceita `ranking` e **as palavras `busca` existentes foram apagadas** (a pedido do usuário, para recriar do zero); exclusões, conjuntos e vagas ficam, e o `.db` é copiado para `backups/` antes de migrar.
- **Motivo**: pedido do usuário. Palavras amplas servem para pontuar mas encareceriam a busca (cada palavra da query abre páginas em cada plataforma).

### Regra alterada: pontuação só depois do detalhe da vaga (2026-10-15)
- **Antes:** a lista (título e trecho do card) era avaliada por completo, inclusive a pontuação mínima; só as aprovadas tinham o detalhe aberto. No LinkedIn o card traz quase só título e legenda, então vagas cujas palavras estavam só na descrição (inclusive as palavras de ranking) eram descartadas sem nunca serem lidas.
- **Depois:** a lista só descarta por exclusão, localidade e modalidade. O detalhe é aberto para todas as vagas triadas e ainda desconhecidas; a pontuação (busca + ranking) e o limiar valem sobre o detalhe, e só as aprovadas são gravadas.
- **Motivo**: pedido do usuário (opção "pontuar depois do detalhe"). **Risco registrado**: mais páginas de detalhe por execução (limitadas por `max_paginas_por_termo`) e, como a vaga reprovada no detalhe não é gravada, a página dela é aberta de novo nas execuções seguintes enquanto estiver na janela de recência.

### Regra alterada: vagas pertencem a um conjunto (2026-10-15)
- **Antes:** as vagas eram globais: a mesma vaga (`fonte`, `id_da_vaga`) existia uma vez, a lista misturava as buscas de todos os conjuntos e a deduplicação ignorava qual conjunto a achou.
- **Depois:** cada vaga fica atrelada ao conjunto que estava **ativo quando a execução começou** (`jobs.conjunto_id`); a mesma vaga achada por dois conjuntos vira uma linha em cada, com pontuação e `visto` próprios, e a deduplicação (vaga já conhecida, sem reabrir o detalhe) vale por conjunto. A lista, "Marcar todas como vistas" e "Excluir todas as vagas" valem para o conjunto ativo ou o escolhido no seletor da página Vagas (`conjunto_id`). Excluir um conjunto exclui as vagas dele junto. Migração 9: as vagas já existentes foram atreladas ao primeiro conjunto (a informação de origem não existia) e o `.db` é copiado para `backups/` antes.
- **Motivo**: pedido do usuário. **Consequência**: trocar o conjunto ativo troca a lista de vagas, e uma vaga em dois conjuntos aparece (e é lida) duas vezes.

### Remoção: botão Copiar por linha nos conjuntos (2026-10-15)
- **Como funcionava**: cada linha da tabela tinha um botão **Copiar**, que abria a edição contextual para informar o nome da cópia.
- **Depois**: o botão foi removido das linhas. O formulário **Novo conjunto** ganhou a lista **Copiar palavras de**, com a opção **Começar vazio** e os conjuntos existentes; ao escolher uma origem, o nome digitado cria a cópia com todas as palavras.
- **Motivo**: pedido do usuário. A tabela fica focada em selecionar, editar e excluir, enquanto criação e cópia ficam reunidas no mesmo fluxo.

### Remoção: botões Salvar e Descartar da tela Configurações (2026-10-15)
- **Como funcionava**: a tela mantinha um rascunho e só enviava `PUT /api/config` ao clicar em **Salvar**; **Descartar** voltava aos valores em vigor.
- **Depois**: os botões foram removidos. O rascunho é enviado automaticamente quando o campo perde o foco (ou Enter), ao marcar/desmarcar uma opção e ao soltar ou usar o teclado num controle deslizante; nada é enviado se o valor não mudou. A tela mostra "Salvando…" e "Configuração salva. Vale a partir da próxima busca."; erro do backend (422) continua exibido, mantendo o que foi digitado.
- **Motivo**: pedido do usuário. Não há debounce por tempo (evitaria um parâmetro novo no `config.toml`); sem o botão Descartar, um valor errado já salvo é corrigido editando de novo.
