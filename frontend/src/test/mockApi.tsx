import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";

type Handler = (body: unknown, url: URL) => { status?: number; json?: unknown } | unknown;

/** Substitui o fetch global; as rotas são "MÉTODO /caminho" → resposta (ou função). */
export function makeScanner(fonte: string, overrides: Record<string, unknown> = {}) {
  return {
    fonte,
    versao: "1.0.0",
    explorado_em: "2026-10-14",
    gerado_por: "Claude",
    referencia: "docs/EXPLORACAO_PLATAFORMAS.md",
    status: "ok",
    falhas_consecutivas: 0,
    ultimo_motivo: null,
    mensagem: "Scanner em dia.",
    instrucao: null,
    ...overrides,
  };
}

export function mockApi(userRoutes: Record<string, Handler | unknown>) {
  const routes: Record<string, Handler | unknown> = { "GET /api/scanners": [], ...userRoutes };
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path: url.pathname + url.search, body });
    const route = routes[`${method} ${url.pathname}`];
    if (route === undefined) return new Response(JSON.stringify({ detail: `sem rota ${method} ${url.pathname}` }), { status: 404 });
    const result = await (typeof route === "function" ? (route as Handler)(body, url) : route);
    const reply = result as { status?: number; json?: unknown };
    if (reply && typeof reply === "object" && typeof reply.status === "number") {
      return new Response(reply.status === 204 ? null : JSON.stringify(reply.json ?? {}), { status: reply.status });
    }
    return new Response(JSON.stringify(result), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export const CONFIG = {
  busca: { localidades: ["Brasil"], modalidade: [], janela_horas: 24, keyword_max_length: 80 },
  filtro: { peso_titulo: 3, peso_descricao: 1, min_score: 3, trecho_max_chars: 4000 },
  limites: { max_vagas_lista: 100 },
  ritmo: { pausa_min_s: 2, pausa_max_s: 6, rolagem_min_s: 0.25, rolagem_max_s: 0.7 },
  navegador: { abas_paralelas: false },
  api: { jobs_page_size: 50, poll_interval_ms: 50 },
};

export function makeJob(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    fonte: "gupy",
    id_da_vaga: String(id),
    titulo: `Engenheiro Mecânico ${id}`,
    empresa: "ACME",
    link: `https://vagas.example/${id}`,
    trecho: "",
    pontos: 3,
    run_id: 1,
    encontrada_em: "2026-10-14T12:00:00+00:00",
    localidade: "",
    cidade: "",
    estado: "",
    modalidade: "",
    publicada_em: null,
    visto: false,
    ...overrides,
  };
}

export function makeRun(id: number, status: "executando" | "concluida", fontes: Record<string, unknown>[] = []) {
  return { id, inicio: "2026-10-14T12:00:00+00:00", fim: status === "concluida" ? "2026-10-14T12:01:00+00:00" : null, status, fontes };
}

export function makeSource(fonte: string, overrides: Record<string, unknown> = {}) {
  return { fonte, status: "ok", motivo: null, detalhe: null, lidas: 10, aprovadas: 4, novas: 2, scanner_versao: "1.0.0", ...overrides };
}
