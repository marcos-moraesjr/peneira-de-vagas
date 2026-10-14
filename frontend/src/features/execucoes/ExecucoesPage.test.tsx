import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, makeRun, makeScanner, makeSource, mockApi, renderWithClient } from "../../test/mockApi";
import { ExecucoesPage } from "./ExecucoesPage";

describe("ExecucoesPage", () => {
  it("lista execuções e, ao expandir, o resultado de cada fonte", async () => {
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
    await user.click(await screen.findByRole("button", { name: /execução #2/i }));
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("LinkedIn");
    expect(rows[1]).toHaveTextContent(/sessão está deslogada/i);
    expect(rows[2]).toHaveTextContent("Gupy");
    expect(rows[2]).toHaveTextContent("40");
    expect(rows[2]).toHaveTextContent("5");
  });

  it("sem execuções mostra estado vazio", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [] });
    renderWithClient(<ExecucoesPage />);
    expect(await screen.findByText(/nenhuma execução ainda/i)).toBeInTheDocument();
  });

  it("mostra a configuração em vigor somente leitura e aponta onde editar", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [] });
    renderWithClient(<ExecucoesPage />);
    expect(await screen.findByText("Brasil")).toBeInTheDocument();
    expect(screen.getByText(/config\.toml/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("erro de API aparece em linguagem simples", async () => {
    mockApi({ "GET /api/config": CONFIG, "GET /api/runs": { status: 500, json: {} } });
    renderWithClient(<ExecucoesPage />);
    expect(await screen.findByText(/não foi possível carregar as execuções/i)).toBeInTheDocument();
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
    await user.click(await screen.findByRole("button", { name: /execução #3/i }));
    expect(await screen.findByRole("cell", { name: "v1.1.0" })).toBeInTheDocument();
  });
});

describe("ExecucoesPage — refazer a documentação das plataformas", () => {
  const INSTRUCAO = "Refaça a documentação das plataformas de vagas: LinkedIn, Indeed, Gupy.\nO que fazer...";

  function setup(reply: unknown = { instrucao: INSTRUCAO }) {
    return mockApi({ "GET /api/config": CONFIG, "GET /api/runs": [], "GET /api/scanners/instrucao": reply });
  }

  it("o botão gera a instrução para todas as plataformas e mostra o texto", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Gerar instrução para refazer a documentação" }));
    expect(await screen.findByText(/Refaça a documentação das plataformas/)).toBeInTheDocument();
    expect(calls.find((c) => c.path.startsWith("/api/scanners/instrucao"))?.path).toBe("/api/scanners/instrucao");
  });

  it("permite escolher uma plataforma só", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    renderWithClient(<ExecucoesPage />);
    await user.selectOptions(await screen.findByLabelText("Plataforma"), "gupy");
    await user.click(screen.getByRole("button", { name: "Gerar instrução para refazer a documentação" }));
    await screen.findByText(/Refaça a documentação/);
    expect(calls.find((c) => c.path.startsWith("/api/scanners/instrucao"))?.path).toBe("/api/scanners/instrucao?fonte=gupy");
  });

  it("copia a instrução gerada para colar no Claude Code", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    setup();
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Gerar instrução para refazer a documentação" }));
    await user.click(await screen.findByRole("button", { name: "Copiar instrução para o Claude" }));
    expect(writeText).toHaveBeenCalledWith(INSTRUCAO);
  });

  it("antes de gerar não mostra instrução nem botão de copiar", async () => {
    setup();
    renderWithClient(<ExecucoesPage />);
    await screen.findByRole("button", { name: "Gerar instrução para refazer a documentação" });
    expect(screen.queryByRole("button", { name: "Copiar instrução para o Claude" })).not.toBeInTheDocument();
  });

  it("erro da API aparece em linguagem simples", async () => {
    const user = userEvent.setup();
    setup({ status: 422, json: { detail: "Valor inválido: fonte='x'" } });
    renderWithClient(<ExecucoesPage />);
    await user.click(await screen.findByRole("button", { name: "Gerar instrução para refazer a documentação" }));
    expect(await screen.findByText(/Valor inválido: fonte/)).toBeInTheDocument();
  });
});
