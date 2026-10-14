import type { Run } from "../../api/types";
import { describeFailure, sourceLabel } from "../../lib/failures";

/** Falha de fonte nunca vira lista vazia: aparece aqui com a causa e o que fazer. */
export function FailureBanner({ run }: { run: Run | undefined }) {
  const failures = run?.fontes.filter((source) => source.status === "falha") ?? [];
  if (failures.length === 0) return null;
  return (
    <div role="alert" className="space-y-1 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      {failures.map((source) => {
        const { message, action } = describeFailure(source.fonte, source.motivo ?? "erro_interno");
        return (
          <p key={source.fonte}>
            <strong>{sourceLabel(source.fonte)}</strong> {message} {action}
          </p>
        );
      })}
    </div>
  );
}
