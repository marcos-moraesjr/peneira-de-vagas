# Diretrizes para Agentes de IA — JobScanner

Ponto de entrada (`CLAUDE.md`/`AGENTS.md` apontam para cá); prevalece sobre os demais docs. Aqui só
comportamento; especificações ficam nos docs abaixo.

## 1. Idioma

Responder sempre em PT-BR.

## 2. Antes de agir

1. Consultar `docs/ARCHITECTURE.md` (fonte de verdade: fluxo, contratos, módulos, config, convenções) e
   `docs/LESSONS.md` (erros conhecidos); mapear dependências cruzadas. Demais docs: `CODE_QUALITY.md`
   (testes, estilo, limites, git, pronto), `TECH_STACK.md` (libs permitidas e excluídas), `MVP.md` (escopo),
   `FASES.md` (ordem de construção), `SCANNERS.md` (versão e manutenção dos scanners), `README.md` (intro e execução local).
2. Nunca ler arquivo inteiro: grep → read do trecho.

## 3. Método de desenvolvimento: TDD

**Todo código de produção nasce de um teste que falha.** Não há exceção por pressa, por "ser simples" ou
por "testo depois".

1. **Red** — escrever primeiro o teste que descreve o comportamento; rodá-lo e **ver falhar pelo motivo
   certo** (não por erro de import ou de sintaxe).
2. **Green** — escrever o **mínimo** de código para passar; nada além do que o teste exige.
3. **Refactor** — melhorar com a suíte verde, sem mudar comportamento nem editar o teste junto.

- **Bug:** primeiro o teste que reproduz, depois a correção.
- **Um ciclo por vez:** um comportamento → um teste → o código; não escrever vários testes e a
  implementação inteira de uma vez.
- Escrever a implementação antes do teste é violação: apagar o código e recomeçar pelo teste.
- Relatar no fim a evidência do ciclo (teste vermelho e depois verde). Sem teste passando, a tarefa não está
  pronta.
- Únicas dispensas (lista fechada em `CODE_QUALITY.md` §1): `requirements.txt`/`package.json`,
  `config.toml` de exemplo, scaffolding sem lógica, ajuste puramente visual e texto fixo.
- Testes nunca acessam a rede nem os sites reais; usam amostras salvas e fontes simuladas.

## 4. Escopo

- Um pedido por vez; ao concluir, parar. Nada de "já que estou aqui".
- Fora do pedido aprovado: parar e perguntar, sem "versão simplificada".
- Sem abstração para um segundo caso inexistente (uma fonte nova não justifica uma classe base antes de existir).
- Biblioteca fora do `TECH_STACK.md`: parar e pedir aprovação.
- Sem parâmetro hardcoded: valor que ajusta comportamento (palavra-chave, limite, pausa, timeout, URL de
  busca) nasce no `config.toml` (`CODE_QUALITY.md` §5), nunca como constante de módulo ou literal; registrar
  o parâmetro no ARCHITECTURE.md na mesma sessão.

## 5. Acesso a sites, contas e segredos

- **Nunca contornar bloqueio**: CAPTCHA, verificação anti-bot (Cloudflare), tela de login inesperada ou
  limitação de taxa encerram a fonte na execução e geram alerta. Não resolver CAPTCHA, não trocar
  user-agent para disfarçar, não usar proxy, não instalar stealth (`TECH_STACK.md`, Excluídos).
- Chrome dedicado do projeto apenas (`--user-data-dir` próprio, porta de depuração só em `localhost`).
  Nunca conectar ao perfil pessoal do usuário nem abrir a porta de depuração além de `127.0.0.1`.
- Nunca ler, imprimir, logar ou commitar cookies, o perfil do Chrome (`chrome-profile/`),
  `*.db` ou o conteúdo de sessões logadas.
- Abrir a API além de `127.0.0.1` ou enviar dados a terceiros além das três fontes de vagas: decisão **exclusiva do usuário**.
- Frontend não repete regra de negócio nem validação: exibe e envia; quem decide é o backend.
- Ritmo humano é regra, não detalhe: sem abas em paralelo, sem remover as pausas variáveis, sem aumentar o
  teto de páginas por execução sem pedido explícito.
- Testes automatizados nunca acessam LinkedIn, Indeed ou Gupy; usam amostras salvas. A execução real
  (`integration`) é do usuário: não executar, automatizar nem agendar.
- Nunca apagar nem sobrescrever o `.db` do usuário; migração destrutiva só com pedido explícito e cópia prévia.
  Testes usam banco temporário.

## 6. Documentação

Após qualquer implementação, atualizar na mesma sessão, só o trecho afetado (grep → read → edit; nunca
reescrever o arquivo):

- **ARCHITECTURE.md** — fluxo, módulos, diretórios, contrato das fontes, rotas da API, modelo de dados, config, regras do
  filtro e da deduplicação; ao mudar regra documentada, registrar antes e depois.
- **README.md** — só intro e execução local (requisitos, instalação, comandos).
- **LESSONS.md** — casos dos critérios do próprio arquivo (toda remoção de feature inclusa), no formato dele.
- **TECH_STACK.md** — dependência que entra ou sai; decisão em aberto que for resolvida.
- **SCANNERS.md** e `backend/scanners.toml` — toda mudança em adaptador de fonte (`sources/<fonte>.py`, JS de extração, amostras) sobe a versão do scanner e registra o changelog, na mesma alteração.
- **FASES.md** — marcar a fase concluída e registrar desvios.

## 7. Prestação de contas

Relatar com honestidade: testes que falham (com a saída) e passos pulados. Só dar por concluído quando a
Definição de Pronto (`CODE_QUALITY.md` §7) valer por inteiro, com o ciclo TDD (§3) cumprido.
