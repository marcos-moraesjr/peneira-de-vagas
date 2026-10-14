# JobScanner — Briefing para o design da interface

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

- **Barra de ação**: botão **Buscar agora**. Durante a execução vira "Buscando…" (desabilitado) e mostra o andamento por fonte (cada fonte: aguardando · buscando · ok · falha).
- **Faixa de falhas** (só se a última execução teve falha; âmbar/vermelho): uma linha por fonte com motivo e ação. Exemplos: "LinkedIn: verificação de segurança. Abra o Chrome dedicado e resolva manualmente." · "Chrome dedicado não encontrado. Abra-o com o atalho do projeto."
- **Aviso de scanner** (abaixo da faixa de falhas): scanner em estado `refazer` aparece como alerta vermelho "O scanner do X (vN) precisa ser refeito" com a mensagem, a instrução pronta (recolhível) e o botão **Copiar instrução para o Claude**; estado `atencao` aparece como nota discreta; em dia, nada. Detalhes em `SCANNERS.md`.
- **Painel de palavras-chave** (recolhível, aberto na primeira visita): campo de texto + **Adicionar** (Enter também; foco volta ao campo), lista de termos como "chips" com ✕ para remover; seção irmã **Exclusões** igual. Sem termos: orientação "Adicione ao menos uma palavra-chave para buscar" e **Buscar agora** desabilitado. Erros inline ("Esse termo já existe", "Informe um termo"). Nota: "Vale a partir da próxima busca." Padrão de desenvolvimento: chip "Engenheiro Mecânico".
- **Filtros**: abas/segmentos **Novas** | **Todas**, select de fonte ("Todas as fontes"), busca por texto (título/empresa). **Marcar todas como vistas** (com confirmação leve).
- **Lista de vagas** (tabela ou cartões): ponto de "nova" · **Título** (link que abre a vaga em nova aba) · Empresa · Fonte (selo) · Pontuação · "Encontrada há X" · ação **Marcar como vista**. Abrir o link de uma vaga nova a marca como vista (implementado; a confirmar com o usuário). Botão "Carregar mais (N de M)".
- **Estados**: carregando · vazio com orientação ("Nenhuma vaga nova. Última busca: {data}.") · vazio antes da primeira busca ("Clique em Buscar agora") · erro de API.

### 2. Execuções (`/execucoes`)

- **Histórico**: uma linha por execução — início, duração, status; expandida mostra uma linha por fonte: status (ok/falha), motivo, lidas, aprovadas, novas.
- **Scanners**: tabela com fonte, versão, data da exploração, autor (Claude) e estado (Em dia / Atenção / Refazer); a expansão de cada execução mostra a versão do scanner usada em cada fonte.
- **Configuração em vigor** (somente leitura): localidade, pesos, limites. Nota: "Para alterar, edite `config.toml`. Palavras-chave e exclusões são editadas na tela Vagas."
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
