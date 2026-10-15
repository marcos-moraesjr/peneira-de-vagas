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

### Remoção: copiar perfil do Chrome pessoal (2026-10-14)
- **Como funcionava**: botão "Copiar perfil" na aba Vagas (`GET /api/browser/profiles`, `POST /api/browser/profile/copy`).
  `chrome_profile.py` lia o `Local State` do Chrome pessoal, copiava a pasta do perfil escolhido (ignorando caches) para
  `chrome-profile.tmp`, trocava pelo `chrome-profile/` no fim (o antigo ia para `backups/`) e gravava o marcador
  `jobscanner-profile.json`; o Chrome dedicado abria com `--profile-directory=<pasta copiada>`. A tela mostrava um alerta
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