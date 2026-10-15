import { useState } from "react";
import type { Run } from "../../api/types";
import { describeFailure, sourceLabel } from "../../lib/failures";
import { buttonSecondary, card } from "../../components/ui";

/** Falha de fonte nunca vira lista vazia: aparece aqui com a causa e permite retomá-la. */
export function FailureBanner({ run, onRestart, restarting }: { run: Run | undefined; onRestart: (fontes: string[]) => void; restarting: boolean }) {
  const failures = run?.fontes.filter((source) => source.status === "falha") ?? [];
  const [selectedFonte, setSelectedFonte] = useState<string | null>(null);
  if (failures.length === 0) return null;
  const running = run?.status === "executando";
  const selected = failures.find((source) => source.fonte === selectedFonte);
  const selectedDescription = selected ? describeFailure(selected.fonte, selected.motivo ?? "erro_interno") : null;
  return (
    <>
      <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-painel border border-l-[3px] border-falha-bg border-l-falha bg-falha-bg px-[18px] py-3.5 text-[13px] font-medium text-falha-fg">
        <div className="space-y-2">
          {failures.map((source) => {
            const { message, action } = describeFailure(source.fonte, source.motivo ?? "erro_interno");
            return (
              <div key={source.fonte} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <p>
                  <strong>{sourceLabel(source.fonte)}</strong> {message} {action}
                </p>
                <button type="button" className={buttonSecondary} aria-label={`Ver detalhes do ${sourceLabel(source.fonte)}`} onClick={() => setSelectedFonte(source.fonte)}>
                  Ver detalhes
                </button>
              </div>
            );
          })}
        </div>
        {!running && (
          <button type="button" className={buttonSecondary} disabled={restarting} onClick={() => onRestart(failures.map((source) => source.fonte))}>
            Retomar de onde parou
          </button>
        )}
      </div>
      {selected && selectedDescription && (
        <section role="dialog" aria-modal="false" aria-labelledby="failure-detail-title" className={`${card} mt-3 space-y-3`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 id="failure-detail-title" className="text-titulo text-grafite-900">
                Erro no {sourceLabel(selected.fonte)}
              </h2>
              <p className="mt-1 text-sm text-grafite-700">{selectedDescription.message} {selectedDescription.action}</p>
            </div>
            <button type="button" className={buttonSecondary} onClick={() => setSelectedFonte(null)}>
              Fechar
            </button>
          </div>
          <pre className="overflow-auto whitespace-pre-wrap rounded-botao bg-grafite-900 p-3 text-xs text-painel">
            {selected.detalhe ?? "A fonte não forneceu uma mensagem técnica adicional."}
          </pre>
        </section>
      )}
    </>
  );
}
