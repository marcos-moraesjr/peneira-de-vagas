import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useClearJobs, useConfig, useConjuntos, useJobs, useKeywords, useMarkAllSeen, useRuns, useSetCandidatada, useSetExcluida, useSetSeen, useStartRun } from "../../api/hooks";
import type { SeenFilter } from "../../api/types";
import { buttonSecondary, inputClass } from "../../components/ui";
import { SOURCES, sourceLabel } from "../../lib/failures";
import { ErrorBox } from "../../components/ErrorBox";
import { ChromeStatus } from "./ChromeStatus";
import { FailureBanner } from "./FailureBanner";
import { RunBar, RunStatus } from "./RunBar";
import { ScannerBanner } from "./ScannerBanner";
import { UpdateNotice } from "./UpdateNotice";
import { VerificationPrompt } from "./VerificationPrompt";
import { Pagination } from "./Pagination";
import { JobsList, type Sort, type SortColumn } from "./JobsList";

const TABS: { id: SeenFilter; label: string }[] = [
  { id: "todas", label: "Todas" },
  { id: "novas", label: "Não lidas" },
  { id: "candidatadas", label: "Candidaturas" },
  { id: "excluidas", label: "Excluídas" },
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
  palavra_chave: "asc",
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

const TODOS = "todos";

export function VagasPage() {
  const [seen, setSeen] = useState<SeenFilter>("todas");
  const [fonte, setFonte] = useState("");
  const [q, setQ] = useState("");
  const [local, setLocal] = useState("");
  const [maxDias, setMaxDias] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<Sort>(null);
  const [conjuntoEscolhido, setConjuntoEscolhido] = useState<number | typeof TODOS | null>(null);
  const [localidade, setLocalidade] = useState("");
  const [modalidadeBusca, setModalidadeBusca] = useState("");
  const [janelaDias, setJanelaDias] = useState<string | undefined>();

  const conjuntos = useConjuntos().data ?? [];
  // Sem escolha (ou com o conjunto escolhido já excluído), a lista acompanha o conjunto ativo (o servidor decide).
  const todosConjuntos = conjuntoEscolhido === TODOS;
  const conjuntoId = todosConjuntos ? undefined : conjuntos.some((item) => item.id === conjuntoEscolhido) ? (conjuntoEscolhido ?? undefined) : undefined;
  const conjuntoMostrado = todosConjuntos ? undefined : conjuntos.find((item) => item.id === (conjuntoId ?? conjuntos.find((c) => c.ativo)?.id));
  const maxDiasValue = maxDias === "" ? undefined : Number(maxDias);
  const runs = useRuns();
  const latest = runs.data?.[0];
  const keywords = useKeywords("busca");
  const startRun = useStartRun();
  const jobs = useJobs({ visto: seen === "novas" ? false : undefined, fonte, q, local, conjuntoId, todosConjuntos, excluidas: seen === "excluidas", candidatadas: seen === "candidatadas", ordenar: sort?.column, direcao: sort?.direction, maxDias: maxDiasValue }, page, latest?.status === "executando");
  const setSeenMutation = useSetSeen();
  const setExcluida = useSetExcluida();
  const setCandidatada = useSetCandidatada();
  const markAll = useMarkAllSeen();
  const clearJobs = useClearJobs();
  useReloadJobsWhenRunFinishes(latest?.status);

  const items = jobs.data?.items ?? [];
  const config = useConfig().data;
  const pageSize = config?.api.jobs_page_size;
  const janelaDiasBusca = janelaDias ?? String(config?.busca.janela_dias ?? 3);
  const totalPages = pageSize && jobs.data ? Math.max(1, Math.ceil(jobs.data.total / pageSize)) : 1;
  // Se a lista encolher (vagas marcadas como vistas, filtro), não fica numa página que deixou de existir.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  function markAllSeen() {
    if (window.confirm("Marcar todas as vagas filtradas como vistas?")) {
      markAll.mutate({ fonte: fonte || undefined, q: q || undefined, local: local || undefined, max_dias: maxDiasValue, conjunto_id: conjuntoId, ...(todosConjuntos ? { todos_conjuntos: true } : {}) });
    }
  }

  function deleteAll() {
    const nome = conjuntoMostrado ? ` do conjunto "${conjuntoMostrado.nome}"` : "";
    if (window.confirm(`Excluir TODAS as vagas${nome} (vistas e novas)? Não dá para desfazer; se reaparecerem numa busca, voltam como novas.`)) {
      clearJobs.mutate(conjuntoId);
    }
  }

  function runSearch(sources: string[] | null) {
    // O estado escolhido na busca também define o recorte inicial da lista.
    // Sem isso, vagas antigas do conjunto continuam visíveis e parecem ter
    // ignorado o filtro, especialmente quando a Gupy não traz novas vagas.
    setLocal(localidade);
    setPage(1);
    startRun.mutate({ fontes: sources, ...(localidade ? { localidade } : {}), ...(modalidadeBusca ? { modalidade: modalidadeBusca } : {}), ...(janelaDias ? { janela_dias: Number(janelaDias) } : {}) });
  }

  return (
    <div className="space-y-3">
      <RunBar
        latest={latest}
        canSearch={(keywords.data?.length ?? 0) > 0}
        starting={startRun.isPending}
        sources={SOURCES}
        onSearch={runSearch}
        estado={localidade}
        onEstadoChange={setLocalidade}
        modalidade={modalidadeBusca}
        onModalidadeChange={setModalidadeBusca}
        janelaDias={janelaDiasBusca}
        onJanelaDiasChange={setJanelaDias}
        hint={keywords.data?.length || !keywords.isSuccess ? undefined : "Adicione ao menos uma palavra-chave na aba Parâmetros de busca."}
      />
      {startRun.error && <ErrorBox message={startRun.error.message} />}
      <VerificationPrompt running={latest?.status === "executando"} />
      <ChromeStatus>
        <RunStatus latest={latest} />
      </ChromeStatus>
      <FailureBanner run={latest} onRestart={runSearch} restarting={startRun.isPending} />
      <ScannerBanner />
      <UpdateNotice />
      <section aria-label="Filtros da lista" className="space-y-2 rounded-painel border border-linha bg-painel px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="text-sm font-semibold text-grafite-900">Filtrar vagas encontradas</h2>
        <p className="text-xs text-grafite-500">Só filtra o que já está na lista abaixo; não faz uma nova busca.</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {conjuntos.length > 0 && (
          <label className="flex items-center gap-2 text-sm text-grafite-700">
            Conjunto
            <select
              value={todosConjuntos ? TODOS : (conjuntoMostrado?.id ?? "")}
              onChange={(event) => {
                setConjuntoEscolhido(event.target.value === TODOS ? TODOS : Number(event.target.value));
                setPage(1);
              }}
              className={inputClass}
            >
              <option value={TODOS}>Todos</option>
              {conjuntos.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.ativo ? `${item.nome} (ativo)` : item.nome}
                </option>
              ))}
            </select>
          </label>
        )}
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
          className={`${inputClass} w-96`}
        />
        <input
          aria-label="Filtrar por cidade, estado ou modalidade"
          placeholder="Cidade, estado ou modalidade"
          value={local}
          onChange={(event) => {
            setLocal(event.target.value);
            setPage(1);
          }}
          className={`${inputClass} w-72`}
        />
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <button type="button" className={buttonSecondary} onClick={markAllSeen}>
            Marcar todas como vistas
          </button>
          <button type="button" className={buttonSecondary} disabled={clearJobs.isPending || todosConjuntos} title={todosConjuntos ? "Escolha um conjunto para excluir as vagas dele" : undefined} onClick={deleteAll}>
            Excluir todas as vagas
          </button>
        </div>
      </div>
      </section>

      {jobs.isError && <ErrorBox message="Não foi possível carregar as vagas. Verifique se a API está rodando." />}
      {jobs.isLoading && <p className="text-sm text-grafite-500">Carregando vagas…</p>}
      {jobs.isSuccess && items.length === 0 && (
        <p className="rounded-painel border border-dashed border-linha px-4 py-8 text-center text-sm text-grafite-500">
          {runs.data?.length === 0
            ? "Nenhuma busca feita ainda. Use os controles acima ou a aba Parâmetros de busca."
            : seen === "novas"
              ? "Nenhuma vaga nova."
              : seen === "excluidas"
                ? "Nenhuma vaga excluída."
                : seen === "candidatadas"
                  ? "Nenhuma candidatura marcada."
                  : "Nenhuma vaga encontrada."}
        </p>
      )}
      {items.length > 0 && (
        <JobsList
          jobs={items}
          onSeen={(job, visto) => setSeenMutation.mutate({ id: job.id, visto })}
          onExcluir={(job, excluida) => setExcluida.mutate({ id: job.id, excluida })}
          onCandidatar={(job, candidatada) => setCandidatada.mutate({ id: job.id, candidatada })}
          sort={sort}
          onSort={(column) => setSort((current) => nextSort(current, column))}
        />
      )}
      <Pagination page={page} totalPages={totalPages} onPage={setPage} />
    </div>
  );
}
