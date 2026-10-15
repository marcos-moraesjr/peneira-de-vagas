import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { CONFIG, mockApi, renderWithClient } from "./test/mockApi";

const routes = {
  "GET /api/health": { status: "ok", db: "ok" },
  "GET /api/config": CONFIG,
  "GET /api/keywords": [],
  "GET /api/jobs": { items: [], total: 0 },
  "GET /api/runs": [],
};

describe("App", () => {
  it("abre na tela Buscar vagas e alterna para Execuções", async () => {
    const user = userEvent.setup();
    mockApi(routes);
    renderWithClient(<App />);
    expect(await screen.findByRole("tab", { name: "Buscar vagas", selected: true })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Execuções" }));
    expect(await screen.findByText(/nenhuma execução ainda/i)).toBeInTheDocument();
  });

  it("tem a aba Busca com o botão Buscar agora e os painéis de palavras-chave", async () => {
    const user = userEvent.setup();
    mockApi(routes);
    renderWithClient(<App />);
    await user.click(await screen.findByRole("tab", { name: "Parâmetros de busca" }));
    expect(screen.getByLabelText("Nova palavra-chave")).toBeInTheDocument();
  });

  it("mostra os controles da busca na aba Buscar vagas", async () => {
    mockApi(routes);
    renderWithClient(<App />);
    expect(await screen.findByRole("button", { name: "Buscar agora" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Estado da busca" })).toBeInTheDocument();
  });

  it("indica API e banco ok", async () => {
    mockApi(routes);
    renderWithClient(<App />);
    expect(await screen.findByText(/API: ok · banco: ok/)).toBeInTheDocument();
  });

  it("indica API indisponível", async () => {
    mockApi({ ...routes, "GET /api/health": { status: 500, json: {} } });
    renderWithClient(<App />);
    expect(await screen.findByText(/API indisponível/)).toBeInTheDocument();
  });
});

describe("App — como usar", () => {
  it("tem a aba Como usar", async () => {
    const user = userEvent.setup();
    mockApi(routes);
    renderWithClient(<App />);
    await user.click(await screen.findByRole("tab", { name: "Como usar" }));
    expect(await screen.findByRole("heading", { name: "Como usar o Peneira de Vagas" })).toBeInTheDocument();
  });
});

describe("App — configurações", () => {
  it("tem a aba Configurações", async () => {
    const user = userEvent.setup();
    mockApi(routes);
    renderWithClient(<App />);
    await user.click(await screen.findByRole("tab", { name: "Configurações" }));
    expect(await screen.findByRole("slider", { name: "Pontuação mínima para aparecer" })).toBeInTheDocument();
  });
});

describe("App — tema", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("alterna entre claro e escuro pelo botão da barra e lembra a escolha", async () => {
    const user = userEvent.setup();
    mockApi(routes);
    renderWithClient(<App />);
    const toggle = await screen.findByRole("button", { name: /tema escuro/i });
    expect(document.documentElement.dataset.theme).toBe("light");
    await user.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("peneira-de-vagas-tema")).toBe("dark");
    await user.click(screen.getByRole("button", { name: /tema claro/i }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("começa no tema salvo", async () => {
    localStorage.setItem("peneira-de-vagas-tema", "dark");
    mockApi(routes);
    renderWithClient(<App />);
    expect(await screen.findByRole("button", { name: /tema claro/i })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
