import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, makeRun, makeSource, mockApi, renderWithClient } from "../../test/mockApi";
import { BuscaPage } from "./BuscaPage";

const keyword = { id: 1, termo: "Engenheiro Mecânico", tipo: "busca", criada_em: "2026-10-14T12:00:00+00:00" };

function setup(opts: { jobs?: unknown[]; runs?: unknown[] | (() => unknown[]); keywords?: unknown[]; extra?: Record<string, unknown> } = {}) {
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
  renderWithClient(<BuscaPage />);
  return api;
}

describe("BuscaPage", () => {
  it("depois de uma busca mostra a data da última busca", async () => {
    setup({ runs: [makeRun(1, "concluida", [makeSource("gupy", { novas: 0 })])] });
    expect(await screen.findByText(/última busca/i)).toBeInTheDocument();
  });

  it("sem palavra-chave desabilita Buscar agora e explica", async () => {
    setup({ keywords: [] });
    expect(await screen.findByRole("button", { name: "Buscar agora" })).toBeDisabled();
    expect((await screen.findAllByText(/adicione ao menos uma palavra-chave/i)).length).toBeGreaterThan(0);
  });

  it("Buscar agora dispara POST /api/runs", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [] });
    const button = await screen.findByRole("button", { name: "Buscar agora" });
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(button);
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/runs")).toBe(true));
  });

  it("vem com todas as plataformas marcadas e Buscar agora busca em todas", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [] });
    const button = await screen.findByRole("button", { name: "Buscar agora" });
    await waitFor(() => expect(button).toBeEnabled());
    for (const nome of ["LinkedIn", "Indeed", "Gupy"]) expect(screen.getByRole("checkbox", { name: nome })).toBeChecked();
    await user.click(button);
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null }));
  });

  it("desmarcar plataformas busca só nas marcadas (mais de uma)", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [] });
    const button = await screen.findByRole("button", { name: "Buscar agora" });
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(screen.getByRole("checkbox", { name: "Indeed" }));
    await user.click(button);
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: ["linkedin", "gupy"] }));
  });

  it("sem nenhuma plataforma marcada o botão fica desabilitado", async () => {
    const user = userEvent.setup();
    setup({ jobs: [] });
    const button = await screen.findByRole("button", { name: "Buscar agora" });
    await waitFor(() => expect(button).toBeEnabled());
    for (const nome of ["LinkedIn", "Indeed", "Gupy"]) await user.click(screen.getByRole("checkbox", { name: nome }));
    expect(button).toBeDisabled();
  });

  it("durante a execução mostra o andamento por fonte e bloqueia novo clique", async () => {
    setup({
      runs: [
        makeRun(5, "executando", [
          makeSource("linkedin", { status: "ok" }),
          makeSource("indeed", { status: "buscando" }),
          makeSource("gupy", { status: "aguardando" }),
        ]),
      ],
    });
    const button = await screen.findByRole("button", { name: "Buscando…" });
    expect(button).toBeDisabled();
    const progress = screen.getByRole("status");
    expect(within(progress).getByText(/LinkedIn/)).toBeInTheDocument();
    expect(within(progress).getByText(/buscando/i)).toBeInTheDocument();
    expect(within(progress).getByText(/aguardando/i)).toBeInTheDocument();
  });

  it("sem execução em andamento não há botão Interromper", async () => {
    setup({ runs: [makeRun(5, "executando", [makeSource("linkedin", { status: "buscando" })])] });
    await screen.findByRole("button", { name: "Buscando…" });
    expect(screen.queryByRole("button", { name: /interromp/i })).not.toBeInTheDocument();
  });

  it("falha de fonte aparece em destaque com motivo e ação, não como lista vazia", async () => {
    setup({
      jobs: [],
      runs: [makeRun(5, "concluida", [makeSource("linkedin", { status: "falha", motivo: "captcha", novas: 0 }), makeSource("gupy")])],
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("LinkedIn");
    expect(alert).toHaveTextContent(/verificação de segurança/i);
    expect(alert).toHaveTextContent(/Chrome dedicado/);
    expect(alert).not.toHaveTextContent("Gupy");
  });

  it("falha de fonte oferece Reiniciar, que busca de novo só nas fontes que falharam", async () => {
    const user = userEvent.setup();
    const { calls } = setup({
      runs: [
        makeRun(5, "concluida", [
          makeSource("linkedin", { status: "falha", motivo: "interrompida", novas: 0 }),
          makeSource("indeed", { status: "falha", motivo: "interrompida", novas: 0 }),
          makeSource("gupy"),
        ]),
      ],
    });
    await user.click(await screen.findByRole("button", { name: "Reiniciar" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: ["linkedin", "indeed"] }));
  });

  it("sem falha ou com busca em andamento não há botão Reiniciar", async () => {
    setup({ runs: [makeRun(5, "concluida", [makeSource("gupy")])] });
    await screen.findByRole("button", { name: "Buscar agora" });
    expect(screen.queryByRole("button", { name: "Reiniciar" })).not.toBeInTheDocument();
  });

  it("exibe os painéis de palavras-chave e de exclusões", async () => {
    setup({});
    expect(await screen.findByLabelText("Nova palavra-chave")).toBeInTheDocument();
    expect(screen.getByLabelText("Nova exclusão")).toBeInTheDocument();
  });

  it("separa as palavras da busca (query) das de ranking (pontuação) e das exclusões", async () => {
    setup({});
    expect(await screen.findByRole("region", { name: "Palavras-chave da busca" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Palavras-chave de ranking" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Exclusões" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nova palavra de ranking")).toBeInTheDocument();
  });

  it("separa as palavras da busca (query) das de ranking (pontuação) e das exclusões", async () => {
    setup({});
    expect(await screen.findByRole("region", { name: "Palavras-chave da busca" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Palavras-chave de ranking" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Exclusões" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nova palavra de ranking")).toBeInTheDocument();
  });
});
