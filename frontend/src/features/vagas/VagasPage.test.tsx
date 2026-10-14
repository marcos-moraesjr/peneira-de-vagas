import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, makeJob, makeRun, makeSource, mockApi, renderWithClient } from "../../test/mockApi";
import { VagasPage } from "./VagasPage";

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
  renderWithClient(<VagasPage />);
  return api;
}

describe("VagasPage", () => {
  it("lista vagas com título como link para a vaga original em nova aba", async () => {
    setup({ jobs: [makeJob(1), makeJob(2, { fonte: "linkedin", empresa: "Beta" })] });
    const link = await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    expect(link).toHaveAttribute("href", "https://vagas.example/1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(screen.getByText(/Beta/)).toBeInTheDocument();
  });

  it("abre na aba Novas (visto=false) e Todas remove o filtro", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    expect(calls.some((c) => c.path.startsWith("/api/jobs") && c.path.includes("visto=false"))).toBe(true);
    await user.click(screen.getByRole("tab", { name: "Todas" }));
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs"));
      expect(last?.path).not.toContain("visto");
    });
  });

  it("filtra por fonte e por texto", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    await user.selectOptions(screen.getByLabelText("Fonte"), "linkedin");
    await user.type(screen.getByLabelText("Buscar vagas"), "ACME");
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs"));
      expect(last?.path).toContain("fonte=linkedin");
      expect(last?.path).toContain("q=ACME");
    });
  });

  it("marca como vista pelo botão", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Marcar como vista" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ visto: true }));
  });

  it("abrir o link de uma vaga nova também a marca como vista", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    const link = await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    link.addEventListener("click", (event) => event.preventDefault());
    await user.click(link);
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
  });

  it("vaga nova é destacada e vista não", async () => {
    setup({ jobs: [makeJob(1), makeJob(2, { visto: true })] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    expect(screen.getAllByLabelText("Vaga nova")).toHaveLength(1);
  });

  it("marcar todas como vistas pede confirmação e usa os filtros atuais", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Marcar todas como vistas" }));
    expect(confirm).toHaveBeenCalled();
    await waitFor(() => expect(calls.find((c) => c.path === "/api/jobs/mark-seen")?.body).toEqual({}));
  });

  it("cancelar a confirmação não envia nada", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Marcar todas como vistas" }));
    expect(calls.some((c) => c.path === "/api/jobs/mark-seen")).toBe(false);
  });

  it("antes da primeira busca orienta a clicar em Buscar agora", async () => {
    setup({ jobs: [], runs: [] });
    expect(await screen.findByText(/clique em buscar agora/i)).toBeInTheDocument();
  });

  it("depois de uma busca sem vagas novas mostra a data da última busca", async () => {
    setup({ jobs: [], runs: [makeRun(1, "concluida", [makeSource("gupy", { novas: 0 })])] });
    expect(await screen.findByText(/nenhuma vaga nova/i)).toBeInTheDocument();
    expect(screen.getByText(/última busca/i)).toBeInTheDocument();
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

  it("acompanha a execução por polling e recarrega as vagas ao concluir", async () => {
    let ciclo = 0;
    const { calls } = setup({
      jobs: [makeJob(1)],
      runs: () => (ciclo++ < 1 ? [makeRun(5, "executando", [makeSource("gupy", { status: "buscando" })])] : [makeRun(5, "concluida", [makeSource("gupy", { novas: 3 })])]),
    });
    expect(await screen.findByRole("button", { name: "Buscando…" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Buscar agora" })).toBeInTheDocument();
    expect(await screen.findByText(/3 vagas novas/i)).toBeInTheDocument();
    expect(calls.filter((c) => c.path.startsWith("/api/jobs")).length).toBeGreaterThan(1);
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

  it("mostra o erro de API em linguagem simples", async () => {
    setup({ extra: { "GET /api/jobs": { status: 500, json: { detail: "falhou" } } } });
    expect(await screen.findByText(/não foi possível carregar as vagas/i)).toBeInTheDocument();
  });

  it("exibe os painéis de palavras-chave e de exclusões", async () => {
    setup({});
    expect(await screen.findByLabelText("Nova palavra-chave")).toBeInTheDocument();
    expect(screen.getByLabelText("Nova exclusão")).toBeInTheDocument();
  });
});
