import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useJobs, useKeywords, useMarkAllSeen, useRuns, useSetSeen, useStartRun } from "../../api/hooks";
import type { SeenFilter } from "../../api/types";
import { ErrorBox } from "../../components/ErrorBox";
import { KeywordsPanel } from "../../components/KeywordsPanel";
import { buttonSecondary, inputClass } from "../../components/ui";
import { sourceLabel } from "../../lib/failures";
import { FailureBanner } from "./FailureBanner";
import { ScannerBanner } from "./ScannerBanner";
import { JobsList } from "./JobsList";
import { RunBar } from "./RunBar";

const SOURCES = ["linkedin", "indeed", "gupy"];
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

export function VagasPage() {
  const [seen, setSeen] = useState<SeenFilter>("novas");
  const [fonte, setFonte] = useState("");
  const [q, setQ] = useState("");
  const [pages, setPages] = useState(1);

  const runs = useRuns();
  const latest = runs.data?.[0];
  const keywords = useKeywords("busca");
  const jobs = useJobs({ visto: seen === "novas" ? false : undefined, fonte, q }, pages);
  const startRun = useStartRun();
  const setSeenMutation = useSetSeen();
  const markAll = useMarkAllSeen();
  useReloadJobsWhenRunFinishes(latest?.status);

  const hasKeywords = (keywords.data?.length ?? 0) > 0;
  const items = jobs.data?.items ?? [];

  function markAllSeen() {
    if (window.confirm("Marcar todas as vagas filtradas como vistas?")) {
      markAll.mutate({ fonte: fonte || undefined, q: q || undefined });
    }
  }

  return (
    <div className="space-y-4">
      <RunBar
        latest={latest}
        canSearch={hasKeywords}
        starting={startRun.isPending}
        onSearch={() => startRun.mutate()}
        hint={hasKeywords || !keywords.isSuccess ? undefined : "Adicione ao menos uma palavra-chave para buscar."}
      />
      {startRun.error && <ErrorBox message={startRun.error.message} />}
      <FailureBanner run={latest} />
      <ScannerBanner />

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
        <JobsList jobs={items} onSeen={(job, visto) => setSeenMutation.mutate({ id: job.id, visto })} />
      )}
      {jobs.data && jobs.data.total > items.length && (
        <button type="button" className={buttonSecondary} onClick={() => setPages((count) => count + 1)}>
          Carregar mais ({items.length} de {jobs.data.total})
        </button>
      )}
    </div>
  );
}
