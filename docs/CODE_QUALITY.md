# Regras de Qualidade de Código — JobScanner

Para humanos e agentes. Convenções de módulos, config e logging:
[`ARCHITECTURE.md`](ARCHITECTURE.md#convenções). Processo do agente: [`AI_GUIDELINES.md`](AI_GUIDELINES.md).

## 1. Testes

**TDD** (filtro, deduplicação, parsing, regras de falha por fonte): **Red** — teste que falha pelo motivo
certo → **Green** — o mínimo para passar → **Refactor** com a suíte verde. **Bug:** teste que reproduz,
depois a correção.
**Sem teste:** `requirements.txt`, `config.toml` de exemplo, textos de mensagem, scaffolding.

- Comandos: README.md → Testes. Backend em `backend/tests/test_<módulo>.py` (espelha cada módulo);
  frontend com Vitest ao lado do componente (`@testing-library/react`, API simulada).
- **Sem rede** na suíte padrão. Gupy: parsing testado com amostra salva em `tests/samples/` (JSON; hoje
  **sintética**, a substituir por captura real). LinkedIn/Indeed: URLs, detecção de bloqueio e fluxo (paginação,
  pausas, falhas) testados com navegador simulado; a extração dos cards é testada sobre HTML salvo com o
  **Chrome local em headless** (marker `browser`, sem rede, pulado se o Chrome faltar).
- **Filtro**: acento e caixa (`estágio` = `ESTAGIO`), peso título × descrição, exclusão que vence a
  pontuação, texto vazio, limiar na borda.
- **Deduplicação**: mesma vaga em duas execuções; mesmo `id` em fontes diferentes não colide; vaga já gravada
  não gera nova linha nem volta a `visto=0`.
- **Isolamento de falhas**: fonte simulada que levanta erro não impede as demais e gera alerta.
- Cada teste usa SQLite temporário (fixture em `conftest.py`); a suíte nunca toca o `.db` real.
- API testada com `TestClient` do FastAPI; o serviço de execução é testado com fontes simuladas, chamado
  direto (síncrono). Segunda chamada a `POST /api/runs` durante uma execução devolve 409.
- Sem `sleep` nem relógio real: pausas e "agora" são injetados (a pausa humana é função passada como parâmetro).
- Testes `integration` (marker): contra os sites reais, rodados **só pelo usuário**, nunca em rotina nem por agente; pelo
  agente, nos termos de `AI_GUIDELINES.md` §5.
- Nome de teste descreve comportamento: `test_vaga_com_termo_excluido_e_descartada`.

## 2. Estilo

- **Funções: 4–40 linhas**; mais longa faz mais de uma coisa.
- **Arquivos: até 600 linhas**, por responsabilidade (SRP).
- **Código acima do limite é dívida**: ao tocá-lo, não aumentar o excesso; extrair a parte alterada.
- **Refatoração não muda comportamento**: suíte verde antes e depois, sem alterar teste junto, um módulo
  por vez.
- **Nomes específicos**; proibidos `data`, `handler`, `manager`, `helpers`, `info`, `process`, `item`.
- **Sem duplicação**: na 2ª ocorrência, extrair.
- **Imports todos no início do módulo** (stdlib, terceiros, projeto).
- **Retorno antecipado**; no máximo 2 níveis de indentação.
- **Validar nas fronteiras** (config, resposta da Gupy, DOM lido); o interior confia nos contratos. Erro traz
  valor ofensor e esperado: `Config inválida: max_detail_pages=-1 (esperado >= 0)`.
- **Type hints** nas assinaturas públicas; vaga é `TypedDict` ou `dataclass` único, nunca dict solto.
- **Falha explícita**: exceção própria por causa (`SourceBlocked`, `SourceLayoutChanged`, `SourceEmpty`);
  nada de `except Exception: pass`.

## 3. Comentários

- Remover código legado, morto ou comentado ao substituir implementação.
- Função nova: docstring de 2–4 linhas (intenção e contrato).
- Comentar o **porquê**, não o quê; preservar comentários que carregam intenção. Seletor frágil e campo da
  Gupy não documentado ganham um comentário dizendo de onde vieram e quando foram capturados.
- Sem IDs de ticket em comentários; explicar o problema ou citar o SHA.

## 4. Dependências e fronteiras

- Camadas do backend: rota → serviço (regra de negócio) → fontes/banco. Rota não contém regra; serviço não
  conhece HTTP; fonte não conhece filtro nem banco; filtro não conhece fonte.
- Só `sources/linkedin.py` e `sources/indeed.py` usam Playwright; só `sources/gupy.py` usa `httpx`.
- Frontend não repete regra de negócio nem validação: exibe e envia. Tipos vêm do OpenAPI gerado; `strict`, sem `any`.
- Biblioteca nova: processo do [`TECH_STACK.md`](TECH_STACK.md).

## 5. Config e constantes

- Nada hardcoded (onde cada parâmetro mora: `ARCHITECTURE.md`, Configuração).
- Todo valor que ajusta comportamento (palavra-chave, exclusão, URL de busca, teto de páginas, pausa
  mínima/máxima, timeout, atraso inicial, limiar de pontuação) é parâmetro do `config.toml`, nunca constante
  de módulo nem literal no código. Antes de escrever um número que não seja autoevidente, definir onde ele
  mora na config; módulo só lê.
- **Constante nomeada** se o valor repete em 2+ pontos ou se erro de digitação falharia em silêncio (nome de
  fonte, status de execução). Literal para valor único autoevidente e asserções de teste.

## 6. Git

- Sem `git add -A`/`.`/diretório puro: só caminhos explícitos.
- Antes de commitar, `git diff --cached --name-only`: só o que pertence à mudança; documentação
  (`docs/`, `README.md`) vai no mesmo commit do código que a motivou.
- Nunca commitar `*.db`, `data/` (inclui `data/chrome-profile/`), `.venv`, `node_modules`, `frontend/dist`, logs, nem amostras com dados pessoais (limpar
  antes de salvar em `tests/samples/`).
- Mensagem curta, no imperativo, em PT-BR: `adiciona filtro de exclusões por título`.
- Sem `--no-verify` nem contorno de assinatura.

## 7. Definição de pronto

- [ ] Teste escrito antes e passando.
- [ ] `pytest` verde no backend e `npm test` + `tsc --noEmit` verdes no frontend, quando tocados (exceto os
      casos "sem teste" do §1); `integration` não é rodado por agente.
- [ ] Funções ≤ 40 linhas, arquivos ≤ 600, docstring nas novas, sem código morto.
- [ ] Nada hardcoded; config no lugar certo.
- [ ] Nenhuma tentativa de contornar bloqueio; falhas de fonte geram alerta.
- [ ] Documentação atualizada conforme `AI_GUIDELINES.md` §6.
- [ ] Se mexeu em adaptador de fonte: versão do scanner subida em `scanners.toml` e changelog de `SCANNERS.md` atualizado.
- [ ] Usuário conferiu uma execução real antes de confiar na fonte.
