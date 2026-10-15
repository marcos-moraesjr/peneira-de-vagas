import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useClearJobs, useConfig, useJobs, useMarkAllSeen, useRuns, useSetSeen } from "../../api/hooks";
import type { SeenFilter } from "../../api/types";
import { ErrorBox } from "../../components/ErrorBox";
import { buttonSecondary, inputClass } from "../../components/ui";
import { SOURCES, sourceLabel } from "../../lib/failures";
import { MODALIDADES } from "../../lib/format";
import { Pagination } from "./Pagination";
import { JobsList, type Sort, type SortColumn } from "./JobsList";

const TABS: { id: SeenFilter; label: string }[] = [
  { id: "novas", label: "Não lidas" },
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
  cidade: "asc",
  estado: "asc",
  modalidade: "asc",
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
  const [cidade, setCidade] = useState("");
  const [estado, setEstado] = useState("");
  const [modalidade, setModalidade] = useState("");
  const [maxDias, setMaxDias] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<Sort>(null);

  const maxDiasValue = maxDias === "" ? undefined : Number(maxDias);
  const runs = useRuns();
  const latest = runs.data?.[0];
  const jobs = useJobs({ visto: seen === "novas" ? false : undefined, fonte, q, cidade, estado, modalidade, ordenar: sort?.column, direcao: sort?.direction, maxDias: maxDiasValue }, page, latest?.status === "executando");
  const setSeenMutation = useSetSeen();
  const markAll = useMarkAllSeen();
  const clearJobs = useClearJobs();
  useReloadJobsWhenRunFinishes(latest?.status);

  const items = jobs.data?.items ?? [];
  const pageSize = useConfig().data?.api.jobs_page_size;
  const totalPages = pageSize && jobs.data ? Math.max(1, Math.ceil(jobs.data.total / pageSize)) : 1;
  // Se a lista encolher (vagas marcadas como vistas, filtro), não fica numa página que deixou de existir.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  function markAllSeen() {
    if (window.confirm("Marcar todas as vagas filtradas como vistas?")) {
      markAll.mutate({ fonte: fonte || undefined, q: q || undefined, cidade: cidade || undefined, estado: estado || undefined, modalidade: modalidade || undefined, max_dias: maxDiasValue });
    }
  }

  function deleteAll() {
    if (window.confirm("Excluir TODAS as vagas encontradas (vistas e novas)? Não dá para desfazer; se reaparecerem numa busca, voltam como novas.")) {
      clearJobs.mutate();
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" className="flex overflow-hidden rounded-botao border border-linha bg-painel">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={seen === tab.id}
              onClick={() => {
                setSeen(tab.id);
                setPage(1);
              }}
              className={`px-3.5 py-1.5 text-dado font-semibold ${seen === tab.id ? "bg-grafite-900 text-painel" : "text-grafite-500"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-grafite-700">
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
        <label className="flex items-center gap-2 text-sm text-grafite-700">
          Modalidade
          <select
            value={modalidade}
            onChange={(event) => {
              setModalidade(event.target.value);
              setPage(1);
            }}
            className={inputClass}
          >
            <option value="">Todas</option>
            {MODALIDADES.map((item) => (
              <option key={item.valor} value={item.valor}>
                {item.rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-grafite-700">
          Publicadas há no máximo (dias)
          <input
            type="number"
            min={1}
            value={maxDias}
            onChange={(event) => {
              setMaxDias(event.target.value);
              setPage(1);
            }}
            className={`${inputClass} w-20`}
          />
        </label>
        <div className="ml-auto flex flex-wrap gap-3">
          <button type="button" className={buttonSecondary} onClick={markAllSeen}>
            Marcar todas como vistas
          </button>
          <button type="button" className={buttonSecondary} disabled={clearJobs.isPending} onClick={deleteAll}>
            Excluir todas as vagas
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label="Buscar vagas"
          placeholder="Título ou empresa"
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          className={`${inputClass} min-w-0 flex-1`}
        />
        <input
          aria-label="Filtrar por cidade"
          placeholder="Cidade"
          value={cidade}
          onChange={(event) => {
            setCidade(event.target.value);
            setPage(1);
          }}
          className={`${inputClass} w-44`}
        />
        <input
          aria-label="Filtrar por estado"
          placeholder="Estado"
          value={estado}
          onChange={(event) => {
            setEstado(event.target.value);
            setPage(1);
          }}
          className={`${inputClass} w-24`}
        />
      </div>

      {jobs.isError && <ErrorBox message="Não foi possível carregar as vagas. Verifique se a API está rodando." />}
      {jobs.isLoading && <p className="text-sm text-grafite-500">Carregando vagas…</p>}
      {jobs.isSuccess && items.length === 0 && (
        <p className="rounded-painel border border-dashed border-linha px-4 py-8 text-center text-sm text-grafite-500">
          {runs.data?.length === 0
            ? "Nenhuma busca feita ainda. Vá à aba Busca e clique em Buscar agora."
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
      <Pagination page={page} totalPages={totalPages} onPage={setPage} />
    </div>
  );
}
