import type { ReactNode } from "react";
import { card } from "../../components/ui";
import { FAILURE_REASONS, describeFailure } from "../../lib/failures";

function Step({ title, children }: { title: string; children: ReactNode }) {
  return (
    <li className={`${card} space-y-2 text-sm text-grafite-700`}>
      <h3 className="text-base font-semibold text-grafite-900">{title}</h3>
      {children}
    </li>
  );
}

function Command({ children }: { children: string }) {
  return <pre className="overflow-x-auto rounded bg-grafite-900 px-3 py-2 text-xs text-painel">{children}</pre>;
}

function ProblemsTable() {
  return (
    <table aria-label="Problemas comuns" className="w-full text-left text-sm">
      <thead>
        <tr className="text-xs uppercase text-grafite-500">
          <th className="py-1">Motivo</th>
          <th>O que aconteceu</th>
          <th>O que fazer</th>
        </tr>
      </thead>
      <tbody>
        {FAILURE_REASONS.map((reason) => {
          const { message, action } = describeFailure("", reason);
          return (
            <tr key={reason} className="border-t border-linha-2 align-top">
              <td className="py-1 pr-2 text-xs">{reason}</td>
              <td className="pr-2">A fonte {message}</td>
              <td>{action}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function ComoUsarPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-display text-grafite-900">Como usar o Peneira de Vagas</h2>
      <p className="text-sm text-grafite-500">
        O Peneira de Vagas busca vagas no LinkedIn, no Indeed e na Gupy, filtra pelas suas palavras-chave e mostra só o que
        é novo. Tudo roda na sua máquina.
      </p>

      <ol aria-label="Passos" className="space-y-3">
        <Step title="Abra o Chrome dedicado">
          <p>
            LinkedIn e Indeed são lidos pelo Chrome real, num perfil só do Peneira de Vagas (nunca o seu pessoal). Na aba
            Buscar vagas, clique em <strong>Abrir Chrome dedicado</strong>: o aviso "Chrome dedicado aberto" aparece quando ele
            estiver pronto. Deixe a janela aberta durante a busca.
          </p>
          <p>
            O app conversa com ela pela porta de depuração 9222, que só responde dentro do seu computador. Com ela
            fechada, só a Gupy funciona; as outras fontes avisam que o Chrome não foi encontrado.
          </p>
          <details className="text-xs text-grafite-500">
            <summary className="cursor-pointer">O botão não funcionou? Abra pelo terminal</summary>
            <p className="mt-1">Na pasta do projeto:</p>
            <Command>{"powershell -File scripts\\chrome-dedicado.ps1"}</Command>
          </details>
        </Step>

        <Step title="Entre nos sites (uma vez)">
          <p>
            Nessa janela, faça login no LinkedIn e no Indeed <strong>à mão</strong>; o Peneira de Vagas nunca digita
            credenciais. No Indeed, escolha uma opção no aviso de cookies. A sessão fica salva no perfil dedicado, então
            isso só se repete se os sites pedirem de novo.
          </p>
        </Step>

        <Step title="Cadastre as palavras-chave">
          <p>
            Na aba Parâmetros de busca, digite um termo em <strong>Palavras-chave da busca</strong> e tecle Enter: cada uma vira uma
            busca nas plataformas (até 6 palavras-chave de busca por conjunto, porque consultas demais levam a bloqueio).
            Em <strong>Palavras-chave de ranking</strong> ficam os termos que não fazem busca,
            só pontuam as vagas encontradas. Use <strong>Exclusões</strong> para descartar vagas com certos termos,
            como "estágio". O termo
            casa em qualquer ordem e ignora acento, maiúsculas, plural e gênero. As mudanças valem a partir da próxima
            busca.
          </p>
        </Step>

        <Step title="Organize em conjuntos">
          <p>
            As palavras-chave vivem em <strong>Conjuntos de busca</strong> (no topo da aba Parâmetros de busca), por exemplo
            um por área ou cargo. Só o conjunto ativo é editado e buscado. Crie um conjunto vazio ou copie as palavras de
            outro, ative, renomeie ou exclua pela tabela. Cada conjunto guarda as próprias vagas e a própria pontuação.
          </p>
          <p>
            Na aba Buscar vagas, a <strong>Sequência de conjuntos</strong> busca vários conjuntos de uma vez, na ordem
            escolhida (arraste os itens ou use as setas). Cada conjunto vira uma execução no histórico. Vazia, a busca
            usa só o conjunto ativo. A sequência para se uma fonte for bloqueada por CAPTCHA, login ou erro de HTTP.
          </p>
        </Step>

        <Step title="Busque">
          <p>
            Em Buscar vagas, marque as plataformas e, se quiser, restrinja o <strong>Estado</strong>, a{" "}
            <strong>Modalidade</strong> (remoto, híbrido ou presencial) e a <strong>Janela de recência</strong> (em dias;
            vale só para aquela busca). Depois clique em <strong>Buscar agora</strong>. O andamento de cada fonte e o
            conjunto em busca aparecem na tela (aguardando, buscando, concluída, falhou). Uma busca por vez, em ritmo
            humano: com as três fontes, leva alguns minutos.
            Por padrão as plataformas buscam ao mesmo tempo, cada uma na sua aba (isso muda em Configurações).
            O app não contorna CAPTCHA nem bloqueios: se uma fonte pedir verificação, ela espera na aba aberta. Conclua
            a verificação à mão no Chrome dedicado e clique em <strong>Já concluí a verificação</strong> para a busca
            seguir de onde parou; se o tempo de espera acabar, a fonte falha e é avisada.
          </p>
        </Step>

        <Step title="Leia os resultados">
          <p>
            A aba <strong>Não lidas</strong> mostra o que você ainda não viu. Clique no título para abrir a vaga original
            (isso a marca como vista). A aba Todas inclui também as já vistas.
          </p>
          <p>
            Em cada linha, o botão ✓ marca que você se candidatou: a vaga vai para <strong>Candidaturas</strong> e não volta
            como nova. O botão de excluir manda a vaga para <strong>Excluídas</strong>, de onde dá para restaurá-la. Nos dois
            casos a vaga continua no banco, então não reaparece como nova nas próximas buscas.
          </p>
          <p>
            Acima da lista, filtre por conjunto, fonte, dias desde a publicação, pontuação mínima, título, empresa ou
            local, e ordene clicando no cabeçalho das colunas. Esses filtros só mexem na lista; não fazem nova busca.
            Use <strong>Marcar todas como vistas</strong> para zerar as novas. A Gupy informa a data de publicação e o LinkedIn
            também; o Indeed não, e por isso suas vagas nunca saem pelo filtro de dias.
          </p>
        </Step>

        <Step title="Ajuste e acompanhe">
          <p>
            Em Configurações ficam os pontos por palavra-chave no título e na descrição, a pontuação mínima, as páginas
            abertas por palavra-chave, as pausas e a opção de rodar as plataformas em paralelo. Tudo é salvo ao sair
            do campo. Ao mudar pesos ou palavras, use <strong>Recalcular pontuação</strong> para reaplicá-los às vagas já
            encontradas (nenhuma é apagada).
          </p>
          <p>
            A aba Execuções guarda o histórico, o conjunto, o resultado de cada fonte e a versão de cada scanner; dá para
            excluir uma execução (as vagas ficam) ou limpar o histórico.
          </p>
        </Step>

        <Step title="Mantenha atualizado">
          <p>
            Quando sai uma versão nova, a aba Buscar vagas avisa. Feche o programa (Ctrl+C no terminal) e rode, num terminal:
          </p>
          <Command>peneira atualizar</Command>
          <p>
            Seu banco, suas palavras-chave, o config e o perfil do Chrome ficam na sua pasta de dados e não são tocados.
          </p>
        </Step>
      </ol>

      <section className={`${card} space-y-2`}>
        <h3 className="text-base font-semibold text-grafite-900">Se alguma fonte falhar</h3>
        <p className="text-sm text-grafite-500">
            Uma fonte que falha aparece em destaque na aba Buscar vagas, com a causa e o que fazer. As demais continuam. Falha
          nunca é a mesma coisa que "nenhuma vaga".
        </p>
        <ProblemsTable />
      </section>

      <section className={`${card} space-y-2 text-sm text-grafite-700`}>
        <h3 className="text-base font-semibold text-grafite-900">Quando o scanner quebra</h3>
        <p>
          Sites mudam sem aviso. Se uma fonte falhar por layout, zero resultados ou erro de HTTP várias vezes seguidas,
          a aba Buscar vagas mostra "o scanner precisa ser refeito". Clique em <strong>Copiar instrução para o Claude</strong>{" "}
          e cole numa sessão do Claude Code neste repositório: ele explora a plataforma de novo e gera a versão
          seguinte do scanner. A aba Execuções mostra a versão de cada scanner.
        </p>
      </section>
    </div>
  );
}
