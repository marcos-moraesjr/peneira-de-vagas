import { useState } from "react";
import type { Run } from "../../api/types";
import { buttonPrimary } from "../../components/ui";
import { sourceLabel } from "../../lib/failures";
import { timeAgo } from "../../lib/format";
import { ESTADOS_BRASILEIROS } from "../../lib/estados";
import { MODALIDADES } from "../../lib/format";

const STATUS_TEXT: Record<string, string> = {
  aguardando: "aguardando",
  buscando: "buscando",
  ok: "concluída",
  falha: "falhou",
};

const STATUS_CLASS: Record<string, string> = {
  aguardando: "text-atencao-fg",
  buscando: "text-atencao-fg",
  ok: "text-sinal-fg",
  falha: "text-erro-fg",
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
  estado: string;
  onEstadoChange: (estado: string) => void;
  modalidade: string;
  onModalidadeChange: (modalidade: string) => void;
  janelaDias: string;
  onJanelaDiasChange: (dias: string) => void;
  hint?: string;
};

export function RunStatus({ latest }: { latest: Run | undefined }) {
  if (latest?.status !== "executando") return null;
  return (
    <div className="inline-flex rounded-botao border border-linha bg-painel px-2 py-1">
      <ul role="status" className="flex flex-wrap items-center gap-3 text-sm text-grafite-500">
        {latest.fontes.map((source) => (
          <li key={source.fonte} className={STATUS_CLASS[source.status] ?? "text-grafite-500"}>
            {sourceLabel(source.fonte)}: {STATUS_TEXT[source.status] ?? source.status}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RunBar({
  latest,
  canSearch,
  starting,
  sources,
  onSearch,
  estado,
  onEstadoChange,
  modalidade,
  onModalidadeChange,
  janelaDias,
  onJanelaDiasChange,
  hint,
}: Props) {
  const [selected, setSelected] = useState<string[]>(sources);
  const chosen = sources.filter((name) => selected.includes(name));
  const running = latest?.status === "executando";

  function toggle(name: string) {
    setSelected((current) => (current.includes(name) ? current.filter((item) => item !== name) : [...current, name]));
  }
  return (
    <div role="region" aria-label="Controles da busca" className="space-y-1.5 rounded-painel border border-linha bg-painel px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={buttonPrimary}
          disabled={!canSearch || running || starting || chosen.length === 0}
          onClick={() => onSearch(chosen.length === sources.length ? null : chosen)}
        >
          {running ? "Buscando…" : "Buscar agora"}
        </button>
        <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-grafite-700" disabled={running}>
          <legend className="sr-only">Plataformas da busca</legend>
          {sources.map((name) => (
            <label key={name} className="flex items-center gap-2">
              <input type="checkbox" checked={selected.includes(name)} onChange={() => toggle(name)} />
              {sourceLabel(name)}
            </label>
          ))}
        </fieldset>
        <div className="ml-2 flex flex-wrap items-center gap-3 border-l border-linha pl-3">
          <label className="flex items-center gap-2 text-sm text-grafite-700">
            Estado
            <select aria-label="Estado da busca" value={estado} onChange={(event) => onEstadoChange(event.target.value)} className="rounded-botao border border-linha bg-painel px-3 py-2 text-dado text-grafite-900">
              <option value="">Todos os estados</option>
              {ESTADOS_BRASILEIROS.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-grafite-700">
            Modalidade
            <select aria-label="Modalidade da busca" value={modalidade} onChange={(event) => onModalidadeChange(event.target.value)} className="rounded-botao border border-linha bg-painel px-3 py-2 text-dado text-grafite-900">
              <option value="">Todas</option>
              {MODALIDADES.map((item) => <option key={item.valor} value={item.valor}>{item.rotulo}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-grafite-700">
            Janela de recência (dias)
            <input
              aria-label="Janela de recência (dias)"
              type="number"
              min={1}
              value={janelaDias}
              onChange={(event) => onJanelaDiasChange(event.target.value)}
              className="w-20 rounded-botao border border-linha bg-painel px-3 py-2 text-dado text-grafite-900"
            />
          </label>
        </div>
        {latest?.status === "concluida" && (
          <span className="text-legenda text-grafite-500">
            Última busca {timeAgo(latest.fim ?? latest.inicio)}:{" "}
            {newJobsText(latest)}
          </span>
        )}
        {hint && <span className="text-sm text-atencao-fg">{hint}</span>}
      </div>
    </div>
  );
}
