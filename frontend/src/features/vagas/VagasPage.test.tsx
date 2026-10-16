import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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

  it("abre na aba Todas (sem visto), com Todas antes de Não lidas; Não lidas envia visto=false", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Todas", "Não lidas", "Candidaturas", "Excluídas"]);
    expect(screen.getByRole("tab", { name: "Todas" })).toHaveAttribute("aria-selected", "true");
    expect(calls.some((c) => c.path.startsWith("/api/jobs") && c.path.includes("visto"))).toBe(false);
    await user.click(screen.getByRole("tab", { name: "Não lidas" }));
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs"));
      expect(last?.path).toContain("visto=false");
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

  it("ordena pelo servidor: texto começa crescente, números e datas decrescentes, terceiro clique limpa", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    const ultima = () => [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"))?.path ?? "";
    await user.click(screen.getByRole("button", { name: /^Empresa/ }));
    await waitFor(() => expect(ultima()).toContain("ordenar=empresa&direcao=asc"));
    await user.click(screen.getByRole("button", { name: /^Empresa/ }));
    await waitFor(() => expect(ultima()).toContain("ordenar=empresa&direcao=desc"));
    await user.click(screen.getByRole("button", { name: /^Empresa/ }));
    await waitFor(() => expect(ultima()).not.toContain("ordenar"));
    await user.click(screen.getByRole("button", { name: /^Pontos/ }));
    await waitFor(() => expect(ultima()).toContain("ordenar=pontos&direcao=desc"));
  });

  it("abrir o link de uma vaga nova também a marca como vista", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    const link = await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    link.addEventListener("click", (event) => event.preventDefault());
    await user.click(link);
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
  });

  it("ao abrir o link a linha muda para lida na hora, sem esperar a resposta do servidor", async () => {
    const user = userEvent.setup();
    let liberar: () => void = () => {};
    const segura = new Promise<void>((resolve) => (liberar = resolve));
    setup({ jobs: [makeJob(1)], extra: { "PATCH /api/jobs/1": async () => { await segura; return { ...makeJob(1), visto: true }; } } });
    const link = await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    link.addEventListener("click", (event) => event.preventDefault());
    expect(screen.getAllByLabelText("Vaga nova")).toHaveLength(1);
    await user.click(link);
    await waitFor(() => expect(screen.queryAllByLabelText("Vaga nova")).toHaveLength(0));
    liberar();
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

  it("filtra por pontuação mínima: envia min_pontos na listagem e em marcar como vistas; vazio remove", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    const campo = screen.getByLabelText("Pontuação mínima");
    await user.type(campo, "5");
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).toContain("min_pontos=5");
    });
    await user.click(screen.getByRole("button", { name: "Marcar todas como vistas" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/api/jobs/mark-seen")?.body).toEqual({ min_pontos: 5 }));
    await user.clear(campo);
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).not.toContain("min_pontos");
    });
  });

  it("filtra por idade: \"Publicadas há no máximo\" envia max_dias na listagem e em marcar como vistas; vazio remove", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    const campo = screen.getByLabelText("Publicadas há no máximo (dias)");
    await user.type(campo, "7");
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs"));
      expect(last?.path).toContain("max_dias=7");
    });
    await user.click(screen.getByRole("button", { name: "Marcar todas como vistas" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/api/jobs/mark-seen")?.body).toEqual({ max_dias: 7 }));
    await user.clear(campo);
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).not.toContain("max_dias");
    });
  });

  it("filtra por local (cidade, estado ou modalidade): envia na listagem e em marcar como vistas; vazio remove", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    const local = screen.getByLabelText("Filtrar por cidade, estado ou modalidade");
    await user.type(local, "campinas");
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).toContain("local=campinas");
      expect(last?.path).not.toMatch(/cidade|estado|modalidade/);
    });
    await user.click(screen.getByRole("button", { name: "Marcar todas como vistas" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/api/jobs/mark-seen")?.body).toEqual({ local: "campinas" }));
    await user.clear(local);
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).not.toContain("local");
    });
  });

  it("envia a modalidade escolhida na barra de busca", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [] });
    const select = await screen.findByRole("combobox", { name: "Modalidade da busca" });
    await user.selectOptions(select, "remoto");
    await user.click(screen.getByRole("button", { name: "Buscar agora" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null, modalidade: "remoto" }));
  });

  it("envia a janela de recência em dias na busca", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [] });
    const input = await screen.findByLabelText("Janela de recência (dias)");
    await user.clear(input);
    await user.type(input, "7");
    await user.click(screen.getByRole("button", { name: "Buscar agora" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null, janela_dias: 7 }));
  });

  it("aplica o estado da busca também à lista para não exibir vagas antigas de outras UFs", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.selectOptions(await screen.findByRole("combobox", { name: "Estado da busca" }), "São Paulo");
    await user.click(screen.getByRole("button", { name: "Buscar agora" }));

    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).toContain("local=S%C3%A3o+Paulo");
    });
    expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null, localidade: "São Paulo" });
  });

  it("a busca por título ou empresa vem antes do filtro de local e ocupa a largura da coluna", async () => {
    setup({ jobs: [makeJob(1)] });
    await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
    const campos = screen.getAllByRole("textbox").map((campo) => campo.getAttribute("aria-label"));
    expect(campos.indexOf("Buscar vagas")).toBeLessThan(campos.indexOf("Filtrar por cidade, estado ou modalidade"));
    expect(screen.getByLabelText("Buscar vagas").className).toContain("w-full");
    expect(screen.queryByLabelText("Modalidade da lista")).not.toBeInTheDocument();
  });


  it("excluir todas as vagas pede confirmação e chama DELETE /api/jobs", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Excluir todas as vagas" }));
    expect(confirm).toHaveBeenCalled();
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/jobs")).toBe(true));
  });

  it("cancelar a exclusão não envia nada", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Excluir todas as vagas" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
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
    expect(await screen.findByText(/use os controles acima/i)).toBeInTheDocument();
  });

  it("depois de uma busca sem vagas novas mostra que não há vagas novas (aba Não lidas)", async () => {
    setup({ jobs: [], runs: [makeRun(1, "concluida", [makeSource("gupy", { novas: 0 })])] });
    await userEvent.setup().click(await screen.findByRole("tab", { name: "Não lidas" }));
    expect(await screen.findByText(/nenhuma vaga nova/i)).toBeInTheDocument();
  });

  it("acompanha a execução por polling e recarrega as vagas ao concluir", async () => {
    let ciclo = 0;
    const { calls } = setup({
      jobs: [makeJob(1)],
      runs: () => (ciclo++ < 1 ? [makeRun(5, "executando", [makeSource("gupy", { status: "buscando" })])] : [makeRun(5, "concluida", [makeSource("gupy", { novas: 3 })])]),
    });
    await waitFor(() => expect(calls.filter((c) => c.path.startsWith("/api/jobs")).length).toBeGreaterThan(1));
  });

  it("enquanto a execução roda, recarrega a lista de vagas a cada polling (vagas aparecem conforme são encontradas)", async () => {
    const { calls } = setup({
      jobs: [makeJob(1)],
      runs: [makeRun(5, "executando", [makeSource("linkedin", { status: "buscando" })])],
    });
    await waitFor(() => expect(calls.filter((c) => c.path.startsWith("/api/jobs?")).length).toBeGreaterThan(2));
  });

  it("mostra o erro de API em linguagem simples", async () => {
    setup({ extra: { "GET /api/jobs": { status: 500, json: { detail: "falhou" } } } });
    expect(await screen.findByText(/não foi possível carregar as vagas/i)).toBeInTheDocument();
  });

  describe("paginação", () => {
    const paginado = { "GET /api/jobs": () => ({ items: [makeJob(1)], total: 120 }) };
    const ultima = (calls: { path: string }[]) => [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"))?.path;

    it("mostra páginas numeradas em vez de Carregar mais e pede só a página escolhida", async () => {
      const user = userEvent.setup();
      const { calls } = setup({ jobs: [makeJob(1)], extra: paginado });
      await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
      expect(screen.queryByRole("button", { name: /Carregar mais/ })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Página 1" })).toHaveAttribute("aria-current", "page");
      expect(screen.getByRole("button", { name: "Página 3" })).toBeInTheDocument();
      expect(ultima(calls)).toContain("limit=50");
      expect(ultima(calls)).not.toContain("offset");
      await user.click(screen.getByRole("button", { name: "Página 2" }));
      await waitFor(() => expect(ultima(calls)).toContain("offset=50"));
      expect(ultima(calls)).toContain("limit=50");
      expect(screen.getByRole("button", { name: "Página 2" })).toHaveAttribute("aria-current", "page");
    });

    it("Anterior e Próxima andam uma página e ficam desabilitados nas pontas", async () => {
      const user = userEvent.setup();
      const { calls } = setup({ jobs: [makeJob(1)], extra: paginado });
      await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
      expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
      await user.click(screen.getByRole("button", { name: "Próxima" }));
      await waitFor(() => expect(ultima(calls)).toContain("offset=50"));
      await user.click(screen.getByRole("button", { name: "Página 3" }));
      await waitFor(() => expect(ultima(calls)).toContain("offset=100"));
      expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
    });

    it("mudar um filtro volta para a página 1", async () => {
      const user = userEvent.setup();
      const { calls } = setup({ jobs: [makeJob(1)], extra: paginado });
      await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
      await user.click(screen.getByRole("button", { name: "Página 2" }));
      await waitFor(() => expect(ultima(calls)).toContain("offset=50"));
      await user.type(screen.getByLabelText("Filtrar por cidade, estado ou modalidade"), "c");
      await waitFor(() => expect(ultima(calls)).toContain("local=c"));
      expect(ultima(calls)).not.toContain("offset");
    });

    it("sem mais que uma página não mostra a paginação", async () => {
      setup({ jobs: [makeJob(1)] });
      await screen.findByRole("link", { name: "Engenheiro Mecânico 1" });
      expect(screen.queryByRole("navigation", { name: "Paginação" })).not.toBeInTheDocument();
    });
  });
});

describe("VagasPage — excluir vaga da lista", () => {
  it("o botão da linha envia excluida=true", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Excluir vaga Engenheiro Mecânico 1" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/jobs/1")?.body).toEqual({ excluida: true }));
  });

  it("a aba Excluídas pede excluidas=true e o botão da linha restaura a vaga", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1, { excluida: true })] });
    await user.click(await screen.findByRole("tab", { name: "Excluídas" }));
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).toContain("excluidas=true");
    });
    await user.click(await screen.findByRole("button", { name: "Restaurar vaga Engenheiro Mecânico 1" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/jobs/1")?.body).toEqual({ excluida: false }));
  });
});

describe("VagasPage — vagas candidatadas", () => {
  it("o botão da linha, ao lado do ✕, envia candidatada=true", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)] });
    await user.click(await screen.findByRole("button", { name: "Marcar candidatura na vaga Engenheiro Mecânico 1" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/jobs/1")?.body).toEqual({ candidatada: true }));
  });

  it("a aba Candidaturas pede candidatadas=true e o botão da linha desfaz a candidatura", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1, { candidatada: true })] });
    await user.click(await screen.findByRole("tab", { name: "Candidaturas" }));
    await waitFor(() => {
      const last = [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"));
      expect(last?.path).toContain("candidatadas=true");
    });
    await user.click(await screen.findByRole("button", { name: "Desfazer candidatura na vaga Engenheiro Mecânico 1" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/jobs/1")?.body).toEqual({ candidatada: false }));
  });

  it("na aba Candidaturas não há botão de excluir", async () => {
    const user = userEvent.setup();
    setup({ jobs: [makeJob(1, { candidatada: true })] });
    await user.click(await screen.findByRole("tab", { name: "Candidaturas" }));
    await screen.findByRole("button", { name: "Desfazer candidatura na vaga Engenheiro Mecânico 1" });
    expect(screen.queryByRole("button", { name: /^Excluir vaga/ })).not.toBeInTheDocument();
  });
});

describe("VagasPage — seletor de conjunto", () => {
  const conjuntos = [
    { id: 1, nome: "Mecânica", ativo: true },
    { id: 2, nome: "Tecnologia", ativo: false },
  ];
  const ultimaListagem = (calls: { path: string }[]) => [...calls].reverse().find((c) => c.path.startsWith("/api/jobs?"))?.path ?? "";

  it("começa no conjunto ativo (sem enviar conjunto_id) e lista os conjuntos para escolher", async () => {
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    const seletor = await screen.findByLabelText("Conjunto");
    expect(seletor).toHaveValue("1");
    expect(within(seletor).getByRole("option", { name: "Mecânica (ativo)" })).toBeInTheDocument();
    expect(within(seletor).getByRole("option", { name: "Tecnologia" })).toBeInTheDocument();
    expect(ultimaListagem(calls)).not.toContain("conjunto_id");
  });

  it("escolher outro conjunto lista as vagas dele, volta à página 1 e vale em marcar como vistas e excluir", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup({
      jobs: [makeJob(1)],
      extra: { "GET /api/conjuntos": conjuntos, "DELETE /api/jobs": { removidas: 1 } },
    });
    await user.selectOptions(await screen.findByLabelText("Conjunto"), "2");
    await waitFor(() => expect(ultimaListagem(calls)).toContain("conjunto_id=2"));
    await user.click(screen.getByRole("button", { name: "Marcar todas como vistas" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/api/jobs/mark-seen")?.body).toEqual({ conjunto_id: 2 }));
    await user.click(screen.getByRole("button", { name: "Excluir todas as vagas" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/jobs?conjunto_id=2")).toBe(true));
  });

  it("a opção Todos tira o filtro de conjunto da lista e do marcar como vistas, e bloqueia excluir", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    await user.selectOptions(await screen.findByLabelText("Conjunto"), "todos");
    await waitFor(() => expect(ultimaListagem(calls)).toContain("todos_conjuntos=true"));
    expect(ultimaListagem(calls)).not.toContain("conjunto_id");
    await user.click(screen.getByRole("button", { name: "Marcar todas como vistas" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/api/jobs/mark-seen")?.body).toEqual({ todos_conjuntos: true }));
    expect(screen.getByRole("button", { name: "Excluir todas as vagas" })).toBeDisabled();
  });

  it("a confirmação de excluir nomeia o conjunto", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    await user.selectOptions(await screen.findByLabelText("Conjunto"), "2");
    await user.click(screen.getByRole("button", { name: "Excluir todas as vagas" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Tecnologia"));
  });
});

describe("VagasPage — conjunto da busca", () => {
  const conjuntos = [
    { id: 1, nome: "Mecânica", ativo: true },
    { id: 2, nome: "Tecnologia", ativo: false },
  ];

  it("a barra de busca não tem seletor de conjunto único; o conjunto ativo se troca no filtro da lista", async () => {
    setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
    await barra.findByRole("combobox", { name: "Adicionar à sequência" });
    expect(barra.queryByRole("combobox", { name: /Conjunto da busca/ })).not.toBeInTheDocument();
  });

  it("monta uma sequência de conjuntos, reordena e envia a ordem na busca", async () => {
    const user = userEvent.setup();
    const tres = [...conjuntos, { id: 3, nome: "Soldagem", ativo: false }];
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": tres } });
    const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
    const adicionar = await barra.findByRole("combobox", { name: "Adicionar à sequência" });
    await user.selectOptions(adicionar, "1");
    await user.selectOptions(barra.getByRole("combobox", { name: "Adicionar à sequência" }), "3");
    await user.click(barra.getByRole("button", { name: "Subir Soldagem" }));
    const itens = barra.getAllByRole("listitem").filter((item) => item.textContent?.match(/Mecânica|Soldagem/) && item.closest("ol"));
    expect(itens.map((item) => item.textContent)).toEqual([expect.stringContaining("Soldagem"), expect.stringContaining("Mecânica")]);
    await user.click(barra.getByRole("button", { name: "Buscar agora" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null, conjunto_ids: [3, 1] }));
  });

  it("remover da sequência a esvazia e a busca volta a usar só o conjunto ativo", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
    await user.selectOptions(await barra.findByRole("combobox", { name: "Adicionar à sequência" }), "2");
    await user.click(barra.getByRole("button", { name: "Remover Tecnologia" }));
    await user.click(barra.getByRole("button", { name: "Buscar agora" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null }));
  });

  it("arrastar um item da sequência para outra posição reordena a lista", async () => {
    const user = userEvent.setup();
    const tres = [...conjuntos, { id: 3, nome: "Soldagem", ativo: false }];
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": tres } });
    const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
    for (const id of ["1", "2", "3"]) await user.selectOptions(await barra.findByRole("combobox", { name: "Adicionar à sequência" }), id);
    const item = (nome: string) => within(barra.getByRole("list")).getByText(nome).closest("li") as HTMLElement;
    expect(item("Soldagem")).toHaveAttribute("draggable", "true");
    fireEvent.dragStart(item("Soldagem"));
    fireEvent.dragOver(item("Mecânica"));
    fireEvent.drop(item("Mecânica"));
    fireEvent.dragEnd(item("Soldagem"));
    await user.click(barra.getByRole("button", { name: "Buscar agora" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null, conjunto_ids: [3, 1, 2] }));
  });

  it("carrega a sequência salva no servidor e a usa na busca", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos, "GET /api/conjuntos/sequencia": { conjunto_ids: [2, 1] } } });
    const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
    const lista = within(await barra.findByRole("list"));
    expect(lista.getAllByRole("listitem").map((item) => item.textContent)).toEqual([expect.stringContaining("Tecnologia"), expect.stringContaining("Mecânica")]);
    await user.click(barra.getByRole("button", { name: "Buscar agora" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ fontes: null, conjunto_ids: [2, 1] }));
  });

  it("salva a ordem no servidor a cada mudança da sequência", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
    await user.selectOptions(await barra.findByRole("combobox", { name: "Adicionar à sequência" }), "1");
    await user.selectOptions(barra.getByRole("combobox", { name: "Adicionar à sequência" }), "2");
    await user.click(barra.getByRole("button", { name: "Subir Tecnologia" }));
    await waitFor(() => {
      const puts = calls.filter((c) => c.method === "PUT" && c.path === "/api/conjuntos/sequencia").map((c) => c.body);
      expect(puts).toEqual([{ conjunto_ids: [1] }, { conjunto_ids: [1, 2] }, { conjunto_ids: [2, 1] }]);
    });
  });
});

