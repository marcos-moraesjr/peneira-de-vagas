import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useCancelRun, useClearJobs, useJobs, useKeywords, useMarkAllSeen, useRuns, useSetSeen, useStartRun } from "../../api/hooks";
import type { SeenFilter } from "../../api/types";
import { ErrorBox } from "../../components/ErrorBox";
import { ConjuntosPanel } from "../../components/ConjuntosPanel";
import { KeywordsPanel } from "../../components/KeywordsPanel";
import { buttonSecondary, inputClass } from "../../components/ui";
import { sourceLabel } from "../../lib/failures";
import { ChromeStatus } from "./ChromeStatus";
import { VerificationPrompt } from "./VerificationPrompt";
import { FailureBanner } from "./FailureBanner";
import { ScannerBanner } from "./ScannerBanner";
import { JobsList, type Sort, type SortColumn } from "./JobsList";
import { RunBar } from "./RunBar";

const SOURCES = ["linkedin", "indeed", "google", "gupy"];
const TABS: { id: SeenFilter; label: string }[] = [
  { id: "novas", label: "Novas" },
  { id: "todas", label: "Todas" },
];

/** Quando a execução mais recente passa de 'executando' para 'concluida', recarrega as vagas. */
function useReloadJobsWhenRunFinishes(status: string | undefined) {
  const client = useQueryClient();
  const previous = useRef(status);
  useEffect(() => {
    if (previous.current === "executando" && status === "concluida") {
      client.invalidateQueries({ queryKey: ["jobs"] });
      client.invalidateQueries({ queryKey: ["scanners"] });
    }
    previous.current = status;
  }, [status, client]);
}

/** Números e datas começam do maior/mais recente; texto, de A a Z. */
const FIRST_DIRECTION: Record<SortColumn, "asc" | "desc"> = {
  titulo: "asc",
  empresa: "asc",
  localidade: "asc",
  fonte: "asc",
  publicada_em: "desc",
  encontrada_em: "desc",
  pontos: "desc",
};

/** Clique na mesma coluna: direção inicial → inversa → sem ordenação (volta à ordem padrão). */
function nextSort(current: Sort, column: SortColumn): Sort {
  const first = FIRST_DIRECTION[column];
  if (current?.column !== column) return { column, direction: first };
  return current.direction === first ? { column, direction: first === "asc" ? "desc" : "asc" } : null;
}

export function VagasPage() {
  const [seen, setSeen] = useState<SeenFilter>("novas");
  const [fonte, setFonte] = useState("");
  const [q, setQ] = useState("");
  const [maxDias, setMaxDias] = useState("");
  const [pages, setPages] = useState(1);
  const [sort, setSort] = useState<Sort>(null);

  const maxDiasValue = maxDias === "" ? undefined : Number(maxDias);
  const runs = useRuns();
  const latest = runs.data?.[0];
  const keywords = useKeywords("busca");
  const jobs = useJobs({ visto: seen === "novas" ? false : undefined, fonte, q, ordenar: sort?.column, direcao: sort?.direction, maxDias: maxDiasValue }, pages);
  const startRun = useStartRun();
  const cancelRun = useCancelRun();
  const setSeenMutation = useSetSeen();
  const markAll = useMarkAllSeen();
  const clearJobs = useClearJobs();
  useReloadJobsWhenRunFinishes(latest?.status);

  const hasKeywords = (keywords.data?.length ?? 0) > 0;
  const items = jobs.data?.items ?? [];

  function markAllSeen() {
    if (window.confirm("Marcar todas as vagas filtradas como vistas?")) {
      markAll.mutate({ fonte: fonte || undefined, q: q || undefined, max_dias: maxDiasValue });
    }
  }

  function deleteAll() {
    if (window.confirm("Excluir TODAS as vagas encontradas (vistas e novas)? Não dá para desfazer; se reaparecerem numa busca, voltam como novas.")) {
      clearJobs.mutate();
    }
  }

  return (
    <div className="space-y-4">
      <RunBar
        latest={latest}
        canSearch={hasKeywords}
        starting={startRun.isPending}
        sources={SOURCES}
        onSearch={(sources) => startRun.mutate(sources)}
        cancelling={cancelRun.isPending}
        onCancel={(id) => cancelRun.mutate(id)}
        hint={hasKeywords || !keywords.isSuccess ? undefined : "Adicione ao menos uma palavra-chave para buscar."}
      />
      {startRun.error && <ErrorBox message={startRun.error.message} />}
      {cancelRun.error && <ErrorBox message={cancelRun.error.message} />}
      {clearJobs.error && <ErrorBox message={clearJobs.error.message} />}
      <VerificationPrompt running={latest?.status === "executando"} />
      <ChromeStatus />
      <FailureBanner run={latest} onRestart={(fontes) => startRun.mutate(fontes)} restarting={startRun.isPending} />
      <ScannerBanner />

      <ConjuntosPanel />
      <div className="grid gap-4 md:grid-cols-2">
        <KeywordsPanel tipo="busca" />
        <KeywordsPanel tipo="exclusao" />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" className="flex overflow-hidden rounded-md border border-slate-300">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={seen === tab.id}
              onClick={() => {
                setSeen(tab.id);
                setPages(1);
              }}
              className={`px-4 py-1.5 text-sm ${seen === tab.id ? "bg-slate-900 text-white" : "bg-white text-slate-700"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Fonte
          <select value={fonte} onChange={(event) => setFonte(event.target.value)} className={inputClass}>
            <option value="">Todas as fontes</option>
            {SOURCES.map((source) => (
              <option key={source} value={source}>
                {sourceLabel(source)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Publicadas há no máximo (dias)
          <input
            type="number"
            min={1}
            value={maxDias}
            onChange={(event) => {
              setMaxDias(event.target.value);
              setPages(1);
            }}
            className={`${inputClass} w-20`}
          />
        </label>
        <input
          aria-label="Buscar vagas"
          placeholder="Título ou empresa"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button type="button" className={buttonSecondary} onClick={markAllSeen}>
          Marcar todas como vistas
        </button>
        <button type="button" className={buttonSecondary} disabled={clearJobs.isPending} onClick={deleteAll}>
          Excluir todas as vagas
        </button>
      </div>

      {jobs.isError && <ErrorBox message="Não foi possível carregar as vagas. Verifique se a API está rodando." />}
      {jobs.isLoading && <p className="text-sm text-slate-500">Carregando vagas…</p>}
      {jobs.isSuccess && items.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
          {runs.data?.length === 0
            ? "Nenhuma busca feita ainda. Clique em Buscar agora."
            : seen === "novas"
              ? "Nenhuma vaga nova."
              : "Nenhuma vaga encontrada."}
        </p>
      )}
      {items.length > 0 && (
        <JobsList
          jobs={items}
          onSeen={(job, visto) => setSeenMutation.mutate({ id: job.id, visto })}
          sort={sort}
          onSort={(column) => setSort((current) => nextSort(current, column))}
        />
      )}
      {jobs.data && jobs.data.total > items.length && (
        <button type="button" className={buttonSecondary} onClick={() => setPages((count) => count + 1)}>
          Carregar mais ({items.length} de {jobs.data.total})
        </button>
      )}
    </div>
  );
}
