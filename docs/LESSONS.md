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

_(vazio)_
