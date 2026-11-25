import { CONFIG, mockApi, renderWithClient } from "../../test/mockApi";
import { VagasPage } from "./VagasPage";

export const keyword = { id: 1, termo: "Engenheiro Mecânico", tipo: "busca", criada_em: "2026-10-14T12:00:00+00:00" };

export function setup(opts: { jobs?: unknown[]; runs?: unknown[] | (() => unknown[]); keywords?: unknown[]; extra?: Record<string, unknown> } = {}) {
  const jobs = opts.jobs ?? [];
  const api = mockApi({
    "GET /api/config": CONFIG,
    "GET /api/keywords": opts.keywords ?? [keyword],
    "GET /api/jobs": () => ({ items: jobs, total: jobs.length }),
    "GET /api/runs": () => (typeof opts.runs === "function" ? opts.runs() : (opts.runs ?? [])),
    "POST /api/runs": { status: 202, json: { id: 5 } },
    "PATCH /api/jobs/1": () => ({ ...(jobs[0] as object), visto: true }),
    "POST /api/jobs/mark-seen": { atualizadas: 2 },
    ...opts.extra,
  });
  renderWithClient(<VagasPage />);
  return api;
}
