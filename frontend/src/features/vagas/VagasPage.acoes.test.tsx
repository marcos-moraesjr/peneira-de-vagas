import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeJob, makeRun, makeSource } from "../../test/mockApi";
import { setup } from "./vagasPageSetup";

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

  it("começa em Todos (todos_conjuntos, sem conjunto_id) e lista os conjuntos para escolher", async () => {
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "GET /api/conjuntos": conjuntos } });
    const seletor = await screen.findByLabelText("Conjunto");
    expect(seletor).toHaveValue("todos");
    expect(within(seletor).getByRole("option", { name: "Mecânica (ativo)" })).toBeInTheDocument();
    expect(within(seletor).getByRole("option", { name: "Tecnologia" })).toBeInTheDocument();
    await waitFor(() => expect(ultimaListagem(calls)).toContain("todos_conjuntos=true"));
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

describe("VagasPage — botão Buscar condicionado ao navegador e às fontes", () => {
  const abrir = (aberto: boolean) => ({ "GET /api/browser": { aberto } });
  const buscar = () => screen.getByRole("button", { name: "Buscar agora" });

  it("com o Chrome fechado e LinkedIn/Indeed marcados, o botão fica bloqueado e explica o motivo", async () => {
    setup({ jobs: [makeJob(1)], extra: abrir(false) });
    await screen.findByText("Chrome dedicado fechado");
    expect(buscar()).toBeDisabled();
    expect(screen.getByText(/Abra o Chrome dedicado para buscar no LinkedIn ou no Indeed/)).toBeInTheDocument();
  });

  it("com o Chrome fechado, só a Gupy marcada libera o botão", async () => {
    const user = userEvent.setup();
    setup({ jobs: [makeJob(1)], extra: abrir(false) });
    await screen.findByText("Chrome dedicado fechado");
    await user.click(screen.getByRole("checkbox", { name: "LinkedIn" }));
    await user.click(screen.getByRole("checkbox", { name: "Indeed" }));
    expect(buscar()).toBeEnabled();
    expect(screen.queryByText(/Abra o Chrome dedicado para buscar/)).not.toBeInTheDocument();
  });

  it("com o Chrome aberto o botão fica liberado", async () => {
    setup({ jobs: [makeJob(1)], extra: abrir(true) });
    await screen.findByText("Chrome dedicado aberto");
    expect(buscar()).toBeEnabled();
  });
});

describe("VagasPage — recalcular pontuação", () => {
  it("o botão fica ao lado de marcar/excluir, recalcula e informa quantas vagas mudaram", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ jobs: [makeJob(1)], extra: { "POST /api/jobs/recalcular": { atualizadas: 2, total: 5 } } });
    const botao = await screen.findByRole("button", { name: "Recalcular pontuação" });
    expect(botao.parentElement).toContainElement(screen.getByRole("button", { name: "Marcar todas como vistas" }));
    expect(botao.parentElement).toContainElement(screen.getByRole("button", { name: "Excluir todas as vagas" }));
    await user.click(botao);
    expect(await screen.findByText("2 de 5 vagas tiveram a pontuação atualizada.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.path === "/api/jobs/recalcular")).toBe(true);
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

  describe("andamento da sequência", () => {
    const tres = [...conjuntos, { id: 3, nome: "Soldagem", ativo: false }];
    const sequencia = { conjunto_ids: [1, 2, 3] };
    const estados = async () => {
      const barra = within(await screen.findByRole("region", { name: "Controles da busca" }));
      const lista = within(await barra.findByRole("list"));
      return { barra, itens: lista.getAllByRole("listitem").map((item) => item.getAttribute("data-estado")) };
    };

    it("marca concluído, em andamento e pendente e informa o conjunto em andamento", async () => {
      const runs = [makeRun(11, "executando", [makeSource("gupy", { status: "buscando" })], "Tecnologia"), makeRun(10, "concluida", [makeSource("gupy")], "Mecânica")];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia } });
      const { barra, itens } = await estados();
      expect(itens).toEqual(["sucesso", "andamento", "pendente"]);
      const agora = screen.getByText("Buscando agora: Tecnologia (2 de 3)");
      expect(barra.queryByText("Buscando agora: Tecnologia (2 de 3)")).not.toBeInTheDocument();
      expect(agora.parentElement).toContainElement(screen.getByRole("status"));
    });

    it("sem sequência, informa o conjunto em andamento sem a contagem", async () => {
      const runs = [makeRun(11, "executando", [makeSource("gupy", { status: "buscando" })], "Tecnologia")];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres } });
      expect(await screen.findByText("Buscando agora: Tecnologia")).toBeInTheDocument();
    });

    it("marca em vermelho o conjunto cuja execução teve fonte com falha", async () => {
      const runs = [makeRun(11, "concluida", [makeSource("gupy")], "Tecnologia"), makeRun(10, "concluida", [makeSource("gupy", { status: "falha", motivo: "captcha" })], "Mecânica")];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia } });
      const { barra, itens } = await estados();
      expect(itens).toEqual(["falha", "sucesso", "pendente"]);
      expect(barra.queryByText(/Buscando agora/)).not.toBeInTheDocument();
    });

    it("ignora execuções antigas de outra sequência (nomes fora da ordem)", async () => {
      const runs = [makeRun(11, "concluida", [makeSource("gupy")], "Soldagem"), makeRun(10, "concluida", [makeSource("gupy")], "Mecânica")];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia } });
      const { itens } = await estados();
      expect(itens).toEqual(["pendente", "pendente", "sucesso"]);
    });

    it("ao clicar no conjunto, mostra o status de cada fonte da execução dele e esconde ao clicar de novo", async () => {
      const user = userEvent.setup();
      const runs = [
        makeRun(11, "executando", [makeSource("linkedin", { status: "buscando" }), makeSource("gupy", { status: "aguardando" })], "Tecnologia"),
        makeRun(10, "concluida", [makeSource("linkedin", { status: "falha", motivo: "captcha" }), makeSource("gupy")], "Mecânica"),
      ];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia } });
      const { barra } = await estados();
      expect(barra.queryByRole("group", { name: "Fontes de Mecânica" })).not.toBeInTheDocument();
      await user.click(barra.getByRole("button", { name: "Mecânica" }));
      const painel = within(barra.getByRole("group", { name: "Fontes de Mecânica" }));
      expect(painel.getByText("LinkedIn: falhou")).toBeInTheDocument();
      expect(painel.getByText("Gupy: concluída")).toBeInTheDocument();
      await user.click(barra.getByRole("button", { name: "Tecnologia" }));
      expect(within(barra.getByRole("group", { name: "Fontes de Tecnologia" })).getByText("LinkedIn: buscando")).toBeInTheDocument();
      expect(barra.queryByRole("group", { name: "Fontes de Mecânica" })).not.toBeInTheDocument();
      await user.click(barra.getByRole("button", { name: "Tecnologia" }));
      expect(barra.queryByRole("group", { name: "Fontes de Tecnologia" })).not.toBeInTheDocument();
    });

    it("fonte que falhou no painel do conjunto tem botão para retomar só ela, da execução desse conjunto", async () => {
      const user = userEvent.setup();
      const runs = [
        makeRun(11, "concluida", [makeSource("gupy")], "Tecnologia"),
        makeRun(10, "concluida", [makeSource("linkedin", { status: "falha", motivo: "interrompida" }), makeSource("gupy")], "Mecânica"),
      ];
      const { calls } = setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia } });
      const { barra } = await estados();
      await user.click(barra.getByRole("button", { name: "Mecânica" }));
      const painel = within(barra.getByRole("group", { name: "Fontes de Mecânica" }));
      expect(painel.queryByRole("button", { name: /Retomar Gupy/ })).not.toBeInTheDocument();
      await user.click(painel.getByRole("button", { name: "Retomar LinkedIn de onde parou" }));
      await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/runs")?.body).toEqual({ retomar_run_id: 10, fontes: ["linkedin"] }));
    });

    it("com o Chrome dedicado fechado, retomar o LinkedIn fica desabilitado", async () => {
      const user = userEvent.setup();
      const runs = [makeRun(10, "concluida", [makeSource("linkedin", { status: "falha", motivo: "cdp_indisponivel" })], "Mecânica")];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia, "GET /api/browser": { aberto: false } } });
      const { barra } = await estados();
      await user.click(barra.getByRole("button", { name: "Mecânica" }));
      expect(await barra.findByRole("button", { name: "Retomar LinkedIn de onde parou" })).toBeDisabled();
    });

    it("conjunto ainda sem execução informa que não foi buscado", async () => {
      const user = userEvent.setup();
      const runs = [makeRun(10, "concluida", [makeSource("gupy")], "Mecânica")];
      setup({ jobs: [makeJob(1)], runs, extra: { "GET /api/conjuntos": tres, "GET /api/conjuntos/sequencia": sequencia } });
      const { barra } = await estados();
      await user.click(barra.getByRole("button", { name: "Soldagem" }));
      expect(within(barra.getByRole("group", { name: "Fontes de Soldagem" })).getByText("Ainda não buscado nesta sequência.")).toBeInTheDocument();
    });
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
