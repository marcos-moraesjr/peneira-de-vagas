import type { Run } from "../../api/types";
import { describeFailure, sourceLabel } from "../../lib/failures";
import { buttonSecondary } from "../../components/ui";

/** Falha de fonte nunca vira lista vazia: aparece aqui com a causa, o que fazer e como reiniciar. */
export function FailureBanner({ run, onRestart, restarting }: { run: Run | undefined; onRestart: (fontes: string[]) => void; restarting: boolean }) {
  const failures = run?.fontes.filter((source) => source.status === "falha") ?? [];
  if (failures.length === 0) return null;
  const running = run?.status === "executando";
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-painel border border-l-[3px] border-falha-bg border-l-falha bg-falha-bg px-[18px] py-3.5 text-[13px] font-medium text-falha-fg">
      <div className="space-y-1">
        {failures.map((source) => {
          const { message, action } = describeFailure(source.fonte, source.motivo ?? "erro_interno");
          return (
            <p key={source.fonte}>
              <strong>{sourceLabel(source.fonte)}</strong> {message} {action}
            </p>
          );
        })}
      </div>
      {!running && (
        <button type="button" className={buttonSecondary} disabled={restarting} onClick={() => onRestart(failures.map((source) => source.fonte))}>
          Reiniciar
        </button>
      )}
    </div>
  );
}
