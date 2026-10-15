import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { Atualizacao, BrowserStatus, Config, Conjunto, Health, Job, JobsPage, Keyword, KeywordType, Run, Scanner } from "./types";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => apiGet<Health>("/api/health") });
}

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => apiGet<Config>("/api/config"), staleTime: Infinity });
}

export function useConjuntos() {
  return useQuery({ queryKey: ["conjuntos"], queryFn: () => apiGet<Conjunto[]>("/api/conjuntos") });
}

/** Criar, renomear, ativar ou excluir um conjunto muda quais palavras valem e quais vagas aparecem: recarrega conjuntos, palavras e vagas. */
function useConjuntoMutation<T>(mutationFn: (value: T) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["conjuntos"] }),
        client.invalidateQueries({ queryKey: ["keywords"] }),
        client.invalidateQueries({ queryKey: ["jobs"] }),
      ]),
  });
}

export function useAddConjunto() {
  return useConjuntoMutation((nome: string) => apiSend<Conjunto>("POST", "/api/conjuntos", { nome }));
}

export function useRenameConjunto() {
  return useConjuntoMutation(({ id, nome }: { id: number; nome: string }) => apiSend<Conjunto>("PATCH", `/api/conjuntos/${id}`, { nome }));
}

export function useCopyConjunto() {
  return useConjuntoMutation(({ id, nome }: { id: number; nome: string }) => apiSend<Conjunto>("POST", `/api/conjuntos/${id}/copiar`, { nome }));
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
    mutationFn: (input: { fontes: string[] | null; localidade?: string; modalidade?: string; janela_dias?: number }) => apiSend<{ id: number }>("POST", "/api/runs", input),
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

export function useDeleteRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiSend<{ removidas: number }>("DELETE", `/api/runs/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export type JobFilters = {
  visto?: boolean;
  fonte?: string;
  q?: string;
  local?: string;
  conjuntoId?: number;
  todosConjuntos?: boolean;
  excluidas?: boolean;
  candidatadas?: boolean;
  ordenar?: string;
  direcao?: "asc" | "desc";
  maxDias?: number;
};

/** `live`: com uma execução rodando, recarrega no intervalo da config para as vagas aparecerem conforme são gravadas. */
export function useJobs(filters: JobFilters, page: number, live = false) {
  const config = useConfig().data;
  const pageSize = config?.api.jobs_page_size;
  const pollMs = config?.api.poll_interval_ms;
  const params = new URLSearchParams();
  if (filters.visto !== undefined) params.set("visto", String(filters.visto));
  if (filters.fonte) params.set("fonte", filters.fonte);
  if (filters.q) params.set("q", filters.q);
  if (filters.local) params.set("local", filters.local);
  if (filters.conjuntoId !== undefined) params.set("conjunto_id", String(filters.conjuntoId));
  if (filters.todosConjuntos) params.set("todos_conjuntos", "true");
  if (filters.excluidas) params.set("excluidas", "true");
  if (filters.candidatadas) params.set("candidatadas", "true");
  if (filters.maxDias !== undefined) params.set("max_dias", String(filters.maxDias));
  if (filters.ordenar) params.set("ordenar", filters.ordenar);
  if (filters.ordenar && filters.direcao) params.set("direcao", filters.direcao);
  if (pageSize) params.set("limit", String(pageSize));
  if (pageSize && page > 1) params.set("offset", String(pageSize * (page - 1)));
  return useQuery({
    queryKey: ["jobs", filters, page, pageSize],
    queryFn: () => apiGet<JobsPage>(`/api/jobs?${params}`),
    enabled: pageSize !== undefined,
    placeholderData: keepPreviousData,
    refetchInterval: live && pollMs ? pollMs : false,
  });
}

export function useSetSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, visto }: { id: number; visto: boolean }) => apiSend<Job>("PATCH", `/api/jobs/${id}`, { visto }),
    // Atualização otimista: a linha muda na hora; a recarga (onSettled) confirma ou desfaz conforme o servidor.
    onMutate: async ({ id, visto }) => {
      await client.cancelQueries({ queryKey: ["jobs"] });
      client.setQueriesData<JobsPage>({ queryKey: ["jobs"] }, (page) =>
        page && { ...page, items: page.items.map((job) => (job.id === id ? { ...job, visto } : job)) },
      );
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useSetExcluida() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, excluida }: { id: number; excluida: boolean }) => apiSend<Job>("PATCH", `/api/jobs/${id}`, { excluida }),
    onSettled: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useSetCandidatada() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, candidatada }: { id: number; candidatada: boolean }) => apiSend<Job>("PATCH", `/api/jobs/${id}`, { candidatada }),
    onSettled: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useMarkAllSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filters: { fonte?: string; q?: string; local?: string; max_dias?: number; conjunto_id?: number; todos_conjuntos?: boolean }) =>
      apiSend<{ atualizadas: number }>("POST", "/api/jobs/mark-seen", filters),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useClearJobs() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (conjuntoId?: number) =>
      apiSend<{ removidas: number }>("DELETE", conjuntoId === undefined ? "/api/jobs" : `/api/jobs?conjunto_id=${conjuntoId}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

/** Há versão nova do app? Consulta uma vez por sessão (a API fala com o GitHub); falha vira "sem aviso". */
export function useAtualizacao() {
  return useQuery({
    queryKey: ["atualizacao"],
    queryFn: () => apiGet<Atualizacao>("/api/atualizacao"),
    staleTime: Infinity,
    retry: false,
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

/** Fontes esperando o usuário concluir uma verificação à mão; só consulta (em polling) durante uma execução. */
export function useVerification(enabled: boolean) {
  const pollMs = useConfig().data?.api.poll_interval_ms;
  return useQuery({
    queryKey: ["verificacao"],
    queryFn: () => apiGet<{ fontes: string[] }>("/api/verificacao"),
    enabled: enabled && pollMs !== undefined,
    refetchInterval: pollMs ?? false,
  });
}

export function useConfirmVerification() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (fonte: string) => apiSend<void>("POST", `/api/verificacao/${fonte}/confirmar`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["verificacao"] }),
  });
}
