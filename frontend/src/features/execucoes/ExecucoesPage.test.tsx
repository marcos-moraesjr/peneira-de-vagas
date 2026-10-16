import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, makeRun, makeScanner, makeSource, mockApi, renderWithClient } from "../../test/mockApi";
import { ExecucoesPage } from "./ExecucoesPage";

describe("ExecucoesPage", () => {
  it("mostra o histórico descrito e não exibe o card de configuração em vigor", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [makeRun(1, "concluida", [makeSource("gupy")])] });
    renderWithClient(<ExecucoesPage />);
    await screen.findByRole("heading", { name: "Histórico de execuções" });
    expect(screen.queryByRole("heading", { name: "Configuração em vigor" })).not.toBeInTheDocument();
    expect(screen.getByText("Consulte as buscas já realizadas e abra uma execução para ver o resultado de cada fonte.")).toBeInTheDocument();
  });

  it("lista execuções e, ao clicar, abre o card com o resultado de cada fonte", async () => {
    const user = userEvent.setup();
    mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": [
        makeRun(2, "concluida", [
          makeSource("linkedin", { status: "falha", motivo: "login", novas: 0, lidas: 0, aprovadas: 0 }),
          makeSource("gupy", { lidas: 40, aprovadas: 7, novas: 5 }),
        ]),
      ],
    });
    renderWithClient(<ExecucoesPage />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Execução #2" }));
    const dialog = await screen.findByRole("dialog", { name: /execução #2/i });
    const rows = within(within(dialog).getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("LinkedIn");
    expect(rows[1]).toHaveTextContent(/sessão está deslogada/i);
    expect(rows[2]).toHaveTextContent("Gupy");
    expect(rows[2]).toHaveTextContent("40");
    expect(rows[2]).toHaveTextContent("5");
  });

  it("o histórico tem a coluna Conjunto com o nome usado na busca, e traço nas execuções antigas", async () => {
    mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": [makeRun(2, "concluida", [makeSource("gupy")], "Mecânica"), makeRun(1, "concluida", [makeSource("gupy")], "")],
    });
    renderWithClient(<ExecucoesPage />);
    const table = await screen.findByRole("table", { name: "Execuções" });
    expect(within(table).getByRole("button", { name: "Conjunto" })).toBeInTheDocument();
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Mecânica");
    expect(rows[2]).toHaveTextContent("—");
  });

  it("o card fecha no botão Fechar", async () => {
    const user = userEvent.setup();
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [makeRun(2, "concluida", [makeSource("gupy")])] });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Execução #2" }));
    await user.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sem execuções mostra estado vazio", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [] });
    renderWithClient(<ExecucoesPage />);
    expect(await screen.findByText(/nenhuma execução ainda/i)).toBeInTheDocument();
  });

  it("erro de API aparece em linguagem simples", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": { status: 500, json: {} } });
    renderWithClient(<ExecucoesPage />);
    expect(await screen.findByText(/não foi possível carregar as execuções/i)).toBeInTheDocument();
  });
});

describe("ExecucoesPage — lista ordenável", () => {
  const RUNS = [
    { ...makeRun(1, "concluida", [makeSource("gupy")]), inicio: "2026-10-14T12:00:00+00:00", fim: "2026-10-14T12:05:00+00:00" },
    {
      ...makeRun(2, "concluida", [makeSource("gupy", { status: "falha", motivo: "login" })]),
      inicio: "2026-10-14T13:00:00+00:00",
      fim: "2026-10-14T13:01:00+00:00",
    },
    { ...makeRun(3, "concluida", [makeSource("gupy")]), inicio: "2026-10-14T11:00:00+00:00", fim: "2026-10-14T11:03:00+00:00" },
  ];

  function ids() {
    const table = screen.getByRole("table", { name: "Execuções" });
    return within(table)
      .getAllByRole("row")
      .slice(1)
      .map((row) => (row as HTMLTableRowElement).cells[0].textContent?.replace("Execução #", ""));
  }

  it("mostra as execuções numa tabela com cabeçalho, da mais recente para a mais antiga", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": RUNS });
    renderWithClient(<ExecucoesPage />);
    await screen.findByRole("table", { name: "Execuções" });
    for (const name of ["Execução", "Início", "Duração", "Resultado"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    expect(ids()).toEqual(["3", "2", "1"]);
  });

  it("clicar no cabeçalho ordena e clicar de novo inverte", async () => {
    const user = userEvent.setup();
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": RUNS });
    renderWithClient(<ExecucoesPage />);
    await screen.findByRole("table", { name: "Execuções" });
    await user.click(screen.getByRole("button", { name: "Duração" }));
    expect(ids()).toEqual(["2", "3", "1"]);
    await user.click(screen.getByRole("button", { name: "Duração" }));
    expect(ids()).toEqual(["1", "3", "2"]);
    await user.click(screen.getByRole("button", { name: "Início" }));
    expect(ids()).toEqual(["3", "1", "2"]);
    expect(screen.getByRole("columnheader", { name: /início/i })).toHaveAttribute("aria-sort", "ascending");
  });

  it("ordena por resultado (com falhas primeiro ao inverter)", async () => {
    const user = userEvent.setup();
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": RUNS });
    renderWithClient(<ExecucoesPage />);
    await screen.findByRole("table", { name: "Execuções" });
    await user.click(screen.getByRole("button", { name: "Resultado" }));
    await user.click(screen.getByRole("button", { name: "Resultado" }));
    expect(ids()[0]).toBe("2");
  });
});

describe("ExecucoesPage — excluir uma execução", () => {
  const RUNS = [makeRun(2, "concluida", [makeSource("gupy")]), makeRun(1, "concluida", [makeSource("gupy")])];

  it("após confirmar, exclui só a linha escolhida e recarrega a lista", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let apagada = false;
    const { calls } = mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": () => (apagada ? [RUNS[1]] : RUNS),
      "DELETE /api/runs/2": () => {
        apagada = true;
        return { removidas: 1 };
      },
    });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Excluir execução #2" }));
    await waitFor(() => expect(screen.queryByText("Execução #2")).not.toBeInTheDocument());
    expect(screen.getByText("Execução #1")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/runs/2")).toBe(true);
  });

  it("se o usuário cancelar a confirmação, não exclui nada", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const { calls } = mockApi({ "GET /api/config": CONFIG, "GET /api/runs": RUNS });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Excluir execução #1" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("erro da API aparece em linguagem simples", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": RUNS,
      "DELETE /api/runs/1": { status: 409, json: { detail: "A execução está em andamento" } },
    });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Excluir execução #1" }));
    expect(await screen.findByText(/a execução está em andamento/i)).toBeInTheDocument();
  });
});

describe("ExecucoesPage — limpar histórico", () => {
  const RUNS = [makeRun(2, "concluida", [makeSource("gupy")]), makeRun(1, "concluida", [makeSource("gupy")])];

  it("após confirmar, apaga o histórico e recarrega a lista", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let apagado = false;
    const { calls } = mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": () => (apagado ? [] : RUNS),
      "DELETE /api/runs": () => {
        apagado = true;
        return { removidas: 2 };
      },
    });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Limpar execuções" }));
    expect(await screen.findByText(/nenhuma execução ainda/i)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/runs")).toBe(true);
  });

  it("se o usuário cancelar a confirmação, não apaga nada", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const { calls } = mockApi({ "GET /api/config": CONFIG, "GET /api/runs": RUNS });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Limpar execuções" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("sem execuções o botão fica desabilitado", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [] });
    renderWithClient(<ExecucoesPage />);
    expect(await screen.findByRole("button", { name: "Limpar execuções" })).toBeDisabled();
  });

  it("erro da API (ex.: execução em andamento) aparece em linguagem simples", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": RUNS,
      "DELETE /api/runs": { status: 409, json: { detail: "Há uma execução em andamento" } },
    });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Limpar execuções" }));
    expect(await screen.findByText(/há uma execução em andamento/i)).toBeInTheDocument();
  });
});

describe("ExecucoesPage — scanners", () => {
  it("lista versão, data da exploração, autor e estado de cada scanner", async () => {
    mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": [],
      "GET /api/scanners": [
        makeScanner("linkedin", { versao: "1.2.0", explorado_em: "2026-10-14" }),
        makeScanner("indeed", { status: "refazer", mensagem: "2 falhas seguidas", instrucao: "x" }),
        makeScanner("gupy", { status: "atencao", mensagem: "1 falha" }),
      ],
    });
    renderWithClient(<ExecucoesPage />);
    const table = await screen.findByRole("table", { name: "Scanners" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("LinkedIn");
    expect(rows[1]).toHaveTextContent("1.2.0");
    expect(rows[1]).toHaveTextContent("14/10/2026");
    expect(rows[1]).toHaveTextContent("Claude");
    expect(rows[1]).toHaveTextContent(/em dia/i);
    expect(rows[2]).toHaveTextContent(/refazer/i);
    expect(rows[3]).toHaveTextContent(/atenção/i);
  });

  it("mostra a versão do scanner usada em cada fonte da execução", async () => {
    const user = userEvent.setup();
    mockApi({
      "GET /api/config": CONFIG,
      "GET /api/runs": [makeRun(3, "concluida", [makeSource("gupy", { scanner_versao: "1.1.0" })])],
    });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Execução #3" }));
    expect(await within(await screen.findByRole("dialog")).findByRole("cell", { name: "v1.1.0" })).toBeInTheDocument();
  });
});

describe("ExecucoesPage — sem o painel de refazer a documentação", () => {
  it("não exibe o painel nem o botão de gerar instrução", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [] });
    renderWithClient(<ExecucoesPage />);
    await screen.findByRole("heading", { name: "Histórico de execuções" });
    expect(screen.queryByRole("heading", { name: "Refazer a documentação das plataformas" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gerar instrução para refazer a documentação" })).not.toBeInTheDocument();
  });
});
