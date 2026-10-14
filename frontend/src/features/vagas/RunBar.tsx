import type { Run } from "../../api/types";
import { buttonPrimary } from "../../components/ui";
import { sourceLabel } from "../../lib/failures";
import { timeAgo } from "../../lib/format";

const STATUS_TEXT: Record<string, string> = {
  aguardando: "aguardando",
  buscando: "buscando",
  ok: "concluída",
  falha: "falhou",
};

function newJobsText(run: Run): string {
  const total = run.fontes.reduce((sum, source) => sum + source.novas, 0);
  return `${total} ${total === 1 ? "vaga nova" : "vagas novas"}`;
}

type Props = { latest: Run | undefined; canSearch: boolean; starting: boolean; onSearch: () => void; hint?: string };

export function RunBar({ latest, canSearch, starting, onSearch, hint }: Props) {
  const running = latest?.status === "executando";
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className={buttonPrimary} disabled={!canSearch || running || starting} onClick={onSearch}>
          {running ? "Buscando…" : "Buscar agora"}
        </button>
        {latest?.status === "concluida" && (
          <span className="text-sm text-slate-600">
            Última busca {timeAgo(latest.fim ?? latest.inicio)}: {newJobsText(latest)}
          </span>
        )}
        {hint && <span className="text-sm text-amber-700">{hint}</span>}
      </div>
      {running && (
        <ul role="status" className="flex flex-wrap gap-3 text-sm text-slate-600">
          {latest.fontes.map((source) => (
            <li key={source.fonte}>
              {sourceLabel(source.fonte)}: {STATUS_TEXT[source.status] ?? source.status}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
