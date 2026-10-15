# Peneira de Vagas — Briefing para o design da interface

App web **pessoal e local** de busca de vagas (um usuário, sem login, pt-BR). A API executa a busca no
LinkedIn, Indeed e Gupy; a interface dispara a busca e exibe os resultados. Escopo em [`MVP.md`](MVP.md);
contratos em [`ARCHITECTURE.md`](ARCHITECTURE.md) (seção API).

## Princípio de design

O maior risco é o **ruído** e o **silêncio enganoso**. Toda decisão visual serve a:

1. **Ver as vagas novas em segundos**: abrir → ver o que é novo → clicar para a vaga original.
2. **Nunca confundir falha com "sem vagas"**: fonte que falhou aparece destacada, com causa e ação.

Uso principal em **desktop**; layout responsivo é desejável, mas o celular não é requisito do MVP.

## Navegação

Barra superior com 2 telas: **Vagas** (inicial) e **Execuções**. No canto, indicador discreto de status da
API ("API: ok · banco: ok" / "API indisponível").

## Conceitos do domínio

- **Fonte**: LinkedIn, Indeed, Gupy — cada uma com selo/cor próprios e consistentes em todo o app.
- **Nova × vista**: nova = ainda não marcada pelo usuário; precisa ser visualmente distinta (ponto/realce).
- **Pontuação**: quão bem a vaga casa com as palavras-chave; exibida discretamente (ex.: "5 pts").
- **Execução**: uma busca; tem estado (executando, concluída) e resultado por fonte (ok ou falha com motivo).
- **Falha de fonte**: motivo padronizado (`captcha`, `login`, `cloudflare`, `seletor_nao_encontrado`,
  `zero_resultados`, `cdp_indisponivel`, `http_erro`, `interrompida`) traduzido em frase simples + ação.

## Telas

### 1. Vagas (`/`) — a mais importante

De cima para baixo:

- **Chrome dedicado**: indicador "Chrome dedicado aberto/fechado"; fechado, mostra o botão **Abrir Chrome dedicado** (abre pelo app, sem terminal) e a nota de que só LinkedIn e Indeed precisam dele.
- **Abas (barra lateral)**: **Busca** (barra de ação, Chrome dedicado, avisos de falha e scanner, conjuntos, palavras-chave e exclusões) e **Vagas** (filtros e lista), além de Execuções, Configurações e Como usar.
- **Barra de ação**: botão **Buscar agora** e, ao lado, checkboxes de plataforma (LinkedIn · Indeed · Gupy; todas marcadas por padrão, escolha de uma ou mais; sem nenhuma marcada o botão fica desabilitado; desabilitados durante a execução). Antes era uma lista "Plataforma da busca" com uma só opção por vez. Durante a execução vira "Buscando…" (desabilitado) e mostra o andamento por fonte (cada fonte: aguardando · buscando · ok · falha).
- **Faixa de falhas** (só se a última execução teve falha; âmbar/vermelho): uma linha por fonte com motivo e ação. Exemplos: "LinkedIn: verificação de segurança. Abra o Chrome dedicado e resolva manualmente." · "Chrome dedicado não encontrado. Abra-o com o atalho do projeto."
- **Aviso de scanner** (abaixo da faixa de falhas): scanner em estado `refazer` aparece como alerta vermelho "O scanner do X (vN) precisa ser refeito" com a mensagem, a instrução pronta (recolhível) e o botão **Copiar instrução para o Claude**; estado `atencao` aparece como nota discreta; em dia, nada. Detalhes em `SCANNERS.md`.
- **Painel de palavras-chave** (recolhível, aberto na primeira visita): campo de texto + **Adicionar** (Enter também; foco volta ao campo), lista de termos como "chips" com ✕ para remover; seção irmã **Exclusões** igual. Sem termos: orientação "Adicione ao menos uma palavra-chave para buscar" e **Buscar agora** desabilitado. Erros inline ("Esse termo já existe", "Informe um termo"). Nota: "Vale a partir da próxima busca." Padrão de desenvolvimento: chip "Engenheiro Mecânico".
- **Filtros**: abas/segmentos **Todas** (padrão) | **Não lidas**, select de fonte ("Todas as fontes"), busca por texto (título/empresa). **Marcar todas como vistas** (com confirmação leve) e **Excluir todas as vagas** (confirmação explícita; apaga vistas e novas, sem respeitar os filtros; irreversível).
- **Lista de vagas** (tabela; antes eram linhas de lista; rolagem horizontal em telas estreitas): colunas **Vaga** (ponto de "nova" + título, link que abre a vaga em nova aba) · Empresa · Localidade · Publicada (DD/MM/AAAA; "—" quando a fonte não informa: LinkedIn e Indeed) · "Encontrada há X" · Plataforma (selo) · Pontos (sem coluna Ações; a linha não lida tem fundo destacado). **Ordenação:** todos os cabeçalhos de dado são botões (▲/▼/↕ e `aria-sort`); o 1º clique ordena (texto A→Z; pontos e datas do maior/mais recente), o 2º inverte, o 3º volta à ordem padrão. Abrir o link de uma vaga nova a marca como vista (implementado; a confirmar com o usuário). Paginação numerada (Anterior, 1 2 3 …, Próxima) abaixo da tabela, no lugar do botão "Carregar mais".
- **Estados**: carregando · vazio com orientação ("Nenhuma vaga nova. Última busca: {data}.") · vazio antes da primeira busca ("Clique em Buscar agora") · erro de API.

### 2. Execuções (`/execucoes`)

- **Histórico**: uma linha por execução — início, duração, status; expandida mostra uma linha por fonte: status (ok/falha), motivo, lidas, aprovadas, novas.
- **Refazer a documentação das plataformas**: select "Plataforma" (todas ou uma) + botão **Gerar instrução para refazer a documentação**; mostra a instrução e o botão **Copiar instrução para o Claude**.
- **Scanners**: tabela com fonte, versão, data da exploração, autor (Claude) e estado (Em dia / Atenção / Refazer); a expansão de cada execução mostra a versão do scanner usada em cada fonte.
- **Configuração em vigor** (somente leitura): localidades, pesos, limites. Nota: "Para alterar, edite `config.toml`. Palavras-chave e exclusões são editadas na aba Busca."
- **Estados**: carregando, vazio ("Nenhuma execução ainda"), erro.

## Estados e feedback a desenhar

Carregando · vazio (cada lista) · erro de API (frase simples, vermelho) · execução em andamento (progresso por fonte) · falha de fonte (âmbar/vermelho, com ação) · sucesso discreto (toast "N vagas novas") · vaga nova × vista · foco de teclado visível.

## Restrições técnicas

- Stack: **React + TypeScript + Tailwind CSS**, TanStack Query. **Sem biblioteca de componentes** (MUI, Ant, shadcn, Chakra excluídas) e **sem roteador** (abas em estado). Ícones só SVG inline ou emoji.
- Datas formatadas via `Intl` (pt-BR), sem libs de data.
- Tudo local, sem fontes/CDNs externos (fonte do sistema ou empacotada).
- Andamento da execução por **polling** (`poll_interval_ms`); sem WebSocket.
- Componentes em `frontend/src/features/*` (uma pasta por tela) e comuns em `frontend/src/components/`.

## O que entregar do design

Tokens (cores por fonte, estados nova/vista, alerta/erro, tipografia, espaçamento, raio), as 2 telas em
desktop (e, se possível, tablet/mobile) e os estados listados. Tema claro obrigatório; escuro opcional.

## O que NÃO mudar sem decisão do usuário

A separação entre "novas" e "vistas", o destaque de falha de fonte (nunca esconder como lista vazia) e as
mensagens de motivo padronizadas.

## Referências

- Escopo e critérios: [`MVP.md`](MVP.md) · fases: [`FASES.md`](FASES.md)
- Arquitetura e API: [`ARCHITECTURE.md`](ARCHITECTURE.md) · stack: [`TECH_STACK.md`](TECH_STACK.md)
