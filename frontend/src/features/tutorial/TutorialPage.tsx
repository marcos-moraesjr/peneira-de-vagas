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

export function TutorialPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-display text-grafite-900">Como usar o Peneira</h2>
      <p className="text-sm text-grafite-500">
        O Peneira busca vagas no LinkedIn, no Indeed e na Gupy, filtra pelas suas palavras-chave e mostra só o que
        é novo. Tudo roda na sua máquina.
      </p>

      <ol aria-label="Passos" className="space-y-3">
        <Step title="Abra o Chrome dedicado">
          <p>
            LinkedIn e Indeed são lidos pelo Chrome real, num perfil só do Peneira (nunca o seu pessoal). Na aba
            Vagas, clique em <strong>Abrir Chrome dedicado</strong>: o aviso "Chrome dedicado aberto" aparece quando ele
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
            Nessa janela, faça login no LinkedIn e no Indeed <strong>à mão</strong>; o Peneira nunca digita
            credenciais. No Indeed, escolha uma opção no aviso de cookies. A sessão fica salva no perfil dedicado, então
            isso só se repete se os sites pedirem de novo.
          </p>
        </Step>

        <Step title="Cadastre as palavras-chave">
          <p>
            Na aba Busca, digite um termo em <strong>Palavras-chave</strong> e tecle Enter (já vem com "Engenheiro
            Mecânico"). Use <strong>Exclusões</strong> para descartar vagas com certos termos, como "estágio". O termo
            casa em qualquer ordem e ignora acento, maiúsculas, plural e gênero. As mudanças valem a partir da próxima
            busca.
          </p>
        </Step>

        <Step title="Busque">
          <p>
            Clique em <strong>Buscar agora</strong>. O andamento de cada fonte aparece ao lado do botão (aguardando,
            buscando, concluída, falhou). Uma busca por vez, em ritmo humano: com as três fontes, leva alguns minutos.
            O app não contorna CAPTCHA nem bloqueios; se uma fonte pedir verificação, ela é encerrada e avisada.
          </p>
        </Step>

        <Step title="Leia os resultados">
          <p>
            A aba <strong>Não lidas</strong> mostra o que você ainda não viu. Clique no título para abrir a vaga original
            (isso a marca como vista). Na primeira busca, a Gupy traz também vagas antigas;
            depois disso, o app só mostra o que ainda não tinha visto. A aba Execuções guarda o histórico e o resultado
            de cada fonte.
          </p>
        </Step>
      </ol>

      <section className={`${card} space-y-2`}>
        <h3 className="text-base font-semibold text-grafite-900">Se alguma fonte falhar</h3>
        <p className="text-sm text-grafite-500">
          Uma fonte que falha aparece em destaque na aba Busca, com a causa e o que fazer. As demais continuam. Falha
          nunca é a mesma coisa que "nenhuma vaga".
        </p>
        <ProblemsTable />
      </section>

      <section className={`${card} space-y-2 text-sm text-grafite-700`}>
        <h3 className="text-base font-semibold text-grafite-900">Quando o scanner quebra</h3>
        <p>
          Sites mudam sem aviso. Se uma fonte falhar por layout, zero resultados ou erro de HTTP várias vezes seguidas,
          a aba Busca mostra "o scanner precisa ser refeito". Clique em <strong>Copiar instrução para o Claude</strong>{" "}
          e cole numa sessão do Claude Code neste repositório: ele explora a plataforma de novo e gera a versão
          seguinte do scanner. A aba Execuções mostra a versão de cada scanner.
        </p>
      </section>
    </div>
  );
}
