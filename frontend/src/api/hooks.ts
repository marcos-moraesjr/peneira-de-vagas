import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { Config, Health, Job, JobsPage, Keyword, KeywordType, Run, Scanner } from "./types";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => apiGet<Health>("/api/health") });
}

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => apiGet<Config>("/api/config"), staleTime: Infinity });
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
    mutationFn: () => apiSend<{ id: number }>("POST", "/api/runs"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export type JobFilters = { visto?: boolean; fonte?: string; q?: string };

export function useJobs(filters: JobFilters, pages: number) {
  const pageSize = useConfig().data?.api.jobs_page_size;
  const params = new URLSearchParams();
  if (filters.visto !== undefined) params.set("visto", String(filters.visto));
  if (filters.fonte) params.set("fonte", filters.fonte);
  if (filters.q) params.set("q", filters.q);
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

export function useScanners() {
  return useQuery({ queryKey: ["scanners"], queryFn: () => apiGet<Scanner[]>("/api/scanners") });
}
