import { useState } from "react";
import type { Run } from "../../api/types";
import { buttonPrimary, buttonSecondary } from "../../components/ui";
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

type Props = {
  latest: Run | undefined;
  canSearch: boolean;
  starting: boolean;
  sources: string[];
  /** `null` = todas as plataformas. */
  onSearch: (sources: string[] | null) => void;
  cancelling: boolean;
  onCancel: (runId: number) => void;
  hint?: string;
};

export function RunBar({
  latest,
  canSearch,
  starting,
  sources,
  onSearch,
  cancelling,
  onCancel,
  hint,
}: Props) {
  const [selected, setSelected] = useState<string[]>(sources);
  const chosen = sources.filter((name) => selected.includes(name));
  const running = latest?.status === "executando";

  function toggle(name: string) {
    setSelected((current) => (current.includes(name) ? current.filter((item) => item !== name) : [...current, name]));
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={buttonPrimary}
          disabled={!canSearch || running || starting || chosen.length === 0}
          onClick={() => onSearch(chosen.length === sources.length ? null : chosen)}
        >
          {running ? "Buscando…" : "Buscar agora"}
        </button>
        {running && (
          <button type="button" className={buttonSecondary} disabled={cancelling} onClick={() => onCancel(latest.id)}>
            {cancelling ? "Interrompendo…" : "Interromper"}
          </button>
        )}
        <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-700" disabled={running}>
          <legend className="sr-only">Plataformas da busca</legend>
          {sources.map((name) => (
            <label key={name} className="flex items-center gap-2">
              <input type="checkbox" checked={selected.includes(name)} onChange={() => toggle(name)} />
              {sourceLabel(name)}
            </label>
          ))}
        </fieldset>
        {latest?.status === "concluida" && (
          <span className="text-sm text-slate-600">
            Última busca {timeAgo(latest.fim ?? latest.inicio)}:{" "}
            {newJobsText(latest)}
          </span>
        )}
        {hint && <span className="text-sm text-amber-700">{hint}</span>}
      </div>
      {running && (
        <ul
          role="status"
          className="flex flex-wrap gap-3 text-sm text-slate-600"
        >
          {latest.fontes.map((source) => (
            <li key={source.fonte}>
              {sourceLabel(source.fonte)}:{" "}
              {STATUS_TEXT[source.status] ?? source.status}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
