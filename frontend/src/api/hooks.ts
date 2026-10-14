import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { BrowserStatus, Config, Conjunto, Health, Job, JobsPage, Keyword, KeywordType, Run, Scanner } from "./types";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => apiGet<Health>("/api/health") });
}

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => apiGet<Config>("/api/config"), staleTime: Infinity });
}

export function useConjuntos() {
  return useQuery({ queryKey: ["conjuntos"], queryFn: () => apiGet<Conjunto[]>("/api/conjuntos") });
}

/** Criar, ativar ou excluir um conjunto muda quais palavras valem: recarrega conjuntos e palavras. */
function useConjuntoMutation<T>(mutationFn: (value: T) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: ["conjuntos"] }), client.invalidateQueries({ queryKey: ["keywords"] })]),
  });
}

export function useAddConjunto() {
  return useConjuntoMutation((nome: string) => apiSend<Conjunto>("POST", "/api/conjuntos", { nome }));
}

export function useActivateConjunto() {
  return useConjuntoMutation((id: number) => apiSend<void>("POST", `/api/conjuntos/${id}/ativar`));
}

export function useDeleteConjunto() {
  return useConjuntoMutation((id: number) => apiSend<void>("DELETE", `/api/conjuntos/${id}`));
}

export function useKeywords(tipo: KeywordType) {
  return useQuery({ queryKey: ["keywords", tipo], queryFn: () => apiGet<Keyword[]>(`/api/keywords?tipo=${tipo}`) });
}

export function useAddKeyword(tipo: KeywordType) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (termo: string) => apiSend<Keyword>("POST", "/api/keywords", { termo, tipo }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["keywords"] }),
  });
}

export function useDeleteKeyword() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiSend<void>("DELETE", `/api/keywords/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["keywords"] }),
  });
}

/** Histórico; enquanto a execução mais recente está rodando, atualiza no intervalo da config (polling). */
export function useRuns() {
  const pollMs = useConfig().data?.api.poll_interval_ms;
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => apiGet<Run[]>("/api/runs"),
    refetchInterval: (query) => (query.state.data?.[0]?.status === "executando" && pollMs ? pollMs : false),
  });
}

export function useStartRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (fontes: string[] | null) => apiSend<{ id: number }>("POST", "/api/runs", { fontes }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useCancelRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiSend<{ id: number }>("POST", `/api/runs/${id}/cancel`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useClearRuns() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiSend<{ removidas: number }>("DELETE", "/api/runs"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export type JobFilters = { visto?: boolean; fonte?: string; q?: string; ordenar?: string; direcao?: "asc" | "desc" };

export function useJobs(filters: JobFilters, pages: number) {
  const pageSize = useConfig().data?.api.jobs_page_size;
  const params = new URLSearchParams();
  if (filters.visto !== undefined) params.set("visto", String(filters.visto));
  if (filters.fonte) params.set("fonte", filters.fonte);
  if (filters.q) params.set("q", filters.q);
  if (filters.ordenar) params.set("ordenar", filters.ordenar);
  if (filters.ordenar && filters.direcao) params.set("direcao", filters.direcao);
  if (pageSize) params.set("limit", String(pageSize * pages));
  return useQuery({
    queryKey: ["jobs", filters, pages, pageSize],
    queryFn: () => apiGet<JobsPage>(`/api/jobs?${params}`),
    enabled: pageSize !== undefined,
    placeholderData: keepPreviousData,
  });
}

export function useSetSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, visto }: { id: number; visto: boolean }) => apiSend<Job>("PATCH", `/api/jobs/${id}`, { visto }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useMarkAllSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filters: { fonte?: string; q?: string }) =>
      apiSend<{ atualizadas: number }>("POST", "/api/jobs/mark-seen", filters),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useClearJobs() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiSend<{ removidas: number }>("DELETE", "/api/jobs"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useScanners() {
  return useQuery({ queryKey: ["scanners"], queryFn: () => apiGet<Scanner[]>("/api/scanners") });
}

/** Chrome dedicado aberto/fechado; enquanto fechado, confere de novo no intervalo da config. */
export function useBrowser() {
  const pollMs = useConfig().data?.api.poll_interval_ms;
  return useQuery({
    queryKey: ["browser"],
    queryFn: () => apiGet<BrowserStatus>("/api/browser"),
    refetchInterval: (query) => (query.state.data?.aberto === false && pollMs ? pollMs : false),
  });
}

export function useOpenBrowser() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiSend<{ estado: string }>("POST", "/api/browser/open"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["browser"] }),
  });
}

/** Instrução para o Claude Code refazer a documentação das plataformas (todas, ou só a `fonte`). */
export function useDocumentationInstruction() {
  return useMutation({
    mutationFn: (fonte: string) =>
      apiGet<{ instrucao: string }>(`/api/scanners/instrucao${fonte ? `?fonte=${fonte}` : ""}`),
  });
}


/** Grava a configuração editável; a resposta (valores em vigor) vira o cache de `useConfig`. */
export function useSaveConfig() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (config: Config) => apiSend<Config>("PUT", "/api/config", config),
    onSuccess: (config) => client.setQueryData(["config"], config),
  });
}
