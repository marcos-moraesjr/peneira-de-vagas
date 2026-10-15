# MVP — Peneira de Vagas

Documento de escopo da primeira versão. Stack em [`TECH_STACK.md`](TECH_STACK.md);
ordem de construção em [`FASES.md`](FASES.md); telas em [`DESIGN_BRIEF.md`](DESIGN_BRIEF.md).

## 1. Objetivo

Aplicação **local** com front end e API. O usuário aciona uma busca no front; a API consulta o **LinkedIn**,
o **Indeed** (navegador real do usuário) e a **Gupy** (API JSON do portal), filtra por palavras-chave e
grava no SQLite. O front exibe as vagas encontradas. Responde a uma pergunta:

**Saiu alguma vaga relevante desde a última vez que olhei?**

## 2. Riscos centrais: bloqueio e ruído

1. **Bloqueio das fontes.** LinkedIn e Indeed detectam automação. A estratégia é usar o navegador real
   do usuário (Chrome dedicado, via CDP) em ritmo humano e **falhar explicitamente** quando algo bloquear
   (CAPTCHA, login, Cloudflare), nunca contornar.
2. **Ruído.** Lista cheia de vagas irrelevantes é ignorada. Toda decisão de escopo é julgada por: **isso
   reduz vaga irrelevante ou evita perder vaga relevante?** Se não, fica fora.

Consequências práticas:

- O filtro (palavras-chave, exclusões, peso do título) é a peça mais importante do produto.
- A tela de vagas mostra o que é **novo** logo de cara; o resto é consulta.
- Falha de fonte aparece com destaque, para o silêncio nunca ser confundido com "sem vagas".

## 3. Usuário e contexto

- Um único usuário, na própria máquina, com Chrome dedicado logado no LinkedIn e no Indeed.
- Sem login no app, sem multiusuário, sem nuvem. Dados ficam no SQLite local.
- Idioma: pt-BR; vagas no Brasil (localidade e modalidade ficam na `config.toml`).
- Uso em **desktop**; a API escuta só em `127.0.0.1`.

## 4. Escopo do MVP

### Dentro

| # | Funcionalidade | Resumo |
| --- | --- | --- |
| 1 | Fonte Gupy | Chamada HTTP à API JSON do portal, com termo de busca e filtros da config. |
| 2 | Fonte LinkedIn | Chrome dedicado via CDP; URL de busca com palavra-chave e últimas 24h; detalhe só das vagas que passam no filtro. |
| 3 | Fonte Indeed | Mesmo modelo do LinkedIn; Cloudflare tratado como falha. |
| 4 | Filtro | Normalização (caixa, acentos), palavras-chave com peso maior no título, lista de exclusões. |
| 5 | Deduplicação | SQLite, chave única `(fonte, id_da_vaga)`; vaga nova é a que não está no banco. |
| 6 | API | Iniciar execução, consultar andamento, listar vagas e execuções, marcar vaga como vista. |
| 7 | Front end | Tela **Vagas** (lista com filtros e "novas") e tela **Execuções** (histórico e falhas por fonte). |
| 8 | Palavras-chave | Campo no front para **adicionar, listar e remover** palavras-chave (e exclusões), salvas no SQLite. Padrão de desenvolvimento: **"Engenheiro Mecânico"**. |
| 9 | Configuração | `config.toml` (localidade, pesos, limites, pausas), somente leitura; exibida na tela Execuções. |
| 10 | Versionamento dos scanners | Cada fonte tem versão em `scanners.toml`; a execução grava a versão usada; falhas de quebra seguidas geram aviso de **refazer o scanner** (com instrução pronta para o Claude). Ver `docs/SCANNERS.md`. |

### Fora (explicitamente)

Telegram e qualquer notificação externa, agendamento automático (decisão em aberto), editar pela interface
os demais parâmetros da config (só palavras-chave e exclusões são editáveis), login e multiusuário, candidatura automática, resolução de CAPTCHA, proxies, classificação por
IA/embeddings, outras fontes (Catho, InfoJobs, Glassdoor…), APIs de agregadores, leitura de alertas por
e-mail, execução em nuvem/Docker, gráficos.

## 5. Telas

Detalhe em [`DESIGN_BRIEF.md`](DESIGN_BRIEF.md).

### 5.1 Vagas
- Botão **Buscar agora**, com andamento por fonte enquanto executa.
- Lista de vagas: título, empresa, fonte, pontuação, data em que foi vista, link para a vaga original.
- Filtros: **Não lidas** (não vistas), fonte, busca por texto. Marcar como vista (ao abrir o link da vaga e em lote).
- Faixa de alerta por fonte com falha na última execução.
- **Painel de palavras-chave**: campo de texto + botão Adicionar (Enter também), lista com remover; mesma interface para **exclusões**. Valem a partir da próxima busca.

### 5.2 Execuções
- Histórico: início, duração, por fonte (status, motivo, lidas, aprovadas, novas).
- Config em vigor (localidade, pesos, limites), somente leitura.

## 6. Regras de negócio

1. **Vaga nova = ausente do SQLite**, não "publicada nas últimas X horas". Execução perdida é compensada na seguinte.
2. **Vista × não vista:** vaga nasce `visto=0` ("nova" na tela) e só muda por ação do usuário.
3. **Formato único das fontes:** `id`, `título`, `empresa`, `link`, `trecho`, `fonte`. O filtro e o banco não conhecem a origem.
4. **Filtro em duas passadas:** primeiro a própria busca da fonte (palavra-chave + 24h); depois o filtro local sobre título e trecho.
5. **Pontuação:** acerto no título pesa mais que na descrição; qualquer termo de exclusão descarta a vaga, mesmo com pontuação alta. Pesos e limiar ficam na config.
6. **Só vagas aprovadas são gravadas** em `jobs`; as descartadas só contam em `runs.lidas`.
7. **Detalhe só se passar:** a página da vaga é aberta apenas quando título/trecho passa no filtro, até o teto por execução (padrão 15).
8. **Falha explícita por fonte:** CAPTCHA, login inesperado, seletor quebrado, **zero resultados** ou Chrome inacessível encerram *aquela fonte*, ficam registrados em `runs` e não interrompem as demais.
9. **Uma execução por vez:** pedir outra durante uma em andamento é rejeitado (409).
10. **Sem contorno de bloqueio e ritmo humano:** pausas variáveis, uma aba por vez.

## 7. Modelo de dados

| Tabela | Campos principais |
| --- | --- |
| `jobs` | id, fonte, id_da_vaga, título, empresa, link, trecho, pontos, run_id, visto_em_primeira_vez, `visto` (0/1) — chave única `(fonte, id_da_vaga)` |
| `keywords` | id, termo, `tipo` (`busca`/`exclusao`), criada_em — único por `(termo normalizado, tipo)` |
| `runs` | id, início, fim, status (`executando`, `concluida`) |
| `run_sources` | run_id, fonte, status, motivo, detalhe, lidas, aprovadas, novas, scanner_versao |

Sem ORM; `sqlite3` da stdlib. Evolução do esquema por script SQL versionado, com cópia do `.db` antes.

## 8. Critérios de aceite do MVP

| # | Critério | Como verificar |
| --- | --- | --- |
| 1 | Vaga já vista pela busca nunca é gravada duas vezes | Teste automatizado de deduplicação |
| 2 | O filtro respeita pesos e exclusões, com e sem acento | Testes automatizados com casos de borda |
| 3 | A resposta da Gupy é convertida ao formato único | Teste com amostra salva da API |
| 4 | Falha de uma fonte é registrada e não impede as outras | Teste com fonte simulada que levanta erro |
| 5 | Segunda execução simultânea é rejeitada (409) | Teste de API |
| 5b | Palavras-chave: adicionar, listar, remover; duplicata (sem acento/caixa) e vazio rejeitados; padrão "Engenheiro Mecânico" criado só se a tabela estiver vazia | Testes de API e do serviço |
| 9 | Scanner com falhas de quebra seguidas na versão atual vira "refazer" e traz a instrução; bloqueios não contam; subir a versão zera a contagem | Testes automatizados do serviço e da API |
| 6 | O front inicia a busca, mostra o andamento e lista as vagas novas | Teste de componente + verificação manual |
| 7 | Uma execução real nas três fontes retorna vagas | Verificação manual do usuário (`integration`) |
| 8 | O app abre com um único comando e os dados persistem | Verificação manual |

## 9. Critério de sucesso do produto

Usar por **14 dias seguidos**, abrindo o app e buscando ao menos uma vez por dia útil, com: nenhuma vaga
duplicada, nenhuma falha silenciosa, e vagas relevantes aparecendo antes de o usuário as achar sozinho.
O resultado decide a v2 (incluindo se vale agendar a busca).

## 10. Riscos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Restrição da conta no LinkedIn por automação | Alto | Risco aceito conscientemente; ritmo humano, volume baixo, perfil dedicado, parar ao primeiro aviso. |
| Cloudflare/CAPTCHA no Indeed | Médio | Falha da fonte, visível no front; sem contorno. |
| Mudança de seletor ou de endpoint (Gupy não documentada) | Alto | Falha explícita; amostras salvas nos testes para localizar a quebra. |
| Chrome dedicado fechado na hora da busca | Médio | Falha `cdp_indisponivel` com instrução na tela. |
| Filtro gera falso positivo/negativo | Médio | Ajuste de palavras-chave/exclusões na tela e dos pesos na `config.toml`; registrar casos reais em `LESSONS.md`. |
| Sem agendamento, o usuário esquece de buscar | Médio | Medir no uso real (Fase 5); agendar vira candidata da v2. |
| API exposta na rede sem autenticação | Médio | Escutar só em `127.0.0.1`; abrir exige decisão registrada. |

## 11. Decisões em aberto

1. **Agendamento automático** (hoje só por botão).
2. **Local de execução:** PC próprio (ponto de partida) ou VPS.
3. **Exclusões iniciais, localidade e modalidade** (`config.toml`). Palavra-chave inicial de desenvolvimento: "Engenheiro Mecânico".
4. **Zero resultados:** tratado como falha; reavaliar com o uso.
5. **Editar os demais parâmetros pela tela** (pesos, limites, localidade): exigiria mover a config para o SQLite.
