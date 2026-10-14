import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, mockApi, renderWithClient } from "../test/mockApi";
import { KeywordsPanel } from "./KeywordsPanel";

type Kw = { id: number; termo: string; tipo: string; criada_em: string };

function setup(initial: Kw[] = [], overrides: Record<string, unknown> = {}) {
  let items = [...initial];
  const api = mockApi({
    "GET /api/config": CONFIG,
    "GET /api/keywords": () => items,
    "POST /api/keywords": (body: unknown) => {
      const { termo, tipo } = body as { termo: string; tipo: string };
      const created = { id: items.length + 10, termo, tipo, criada_em: "2026-10-14T12:00:00+00:00" };
      items = [...items, created];
      return { status: 201, json: created };
    },
    "DELETE /api/keywords/1": () => {
      items = items.filter((k) => k.id !== 1);
      return { status: 204 };
    },
    ...overrides,
  });
  renderWithClient(<KeywordsPanel tipo="busca" titulo="Palavras-chave" />);
  return api;
}

const padrao: Kw = { id: 1, termo: "Engenheiro Mecânico", tipo: "busca", criada_em: "2026-10-14T12:00:00+00:00" };

describe("KeywordsPanel", () => {
  it("lista as palavras-chave salvas como chips", async () => {
    setup([padrao]);
    expect(await screen.findByText("Engenheiro Mecânico")).toBeInTheDocument();
  });

  it("sem termos mostra orientação", async () => {
    setup([]);
    expect(await screen.findByText(/nenhuma palavra-chave/i)).toBeInTheDocument();
  });

  it("adiciona com Enter, limpa o campo e mantém o foco", async () => {
    const user = userEvent.setup();
    const { calls } = setup([padrao]);
    const input = await screen.findByLabelText("Nova palavra-chave");
    await user.type(input, "Projetista Mecânico{Enter}");
    expect(await screen.findByText("Projetista Mecânico")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ termo: "Projetista Mecânico", tipo: "busca" });
    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
  });

  it("adiciona pelo botão Adicionar", async () => {
    const user = userEvent.setup();
    setup([]);
    await user.type(await screen.findByLabelText("Nova palavra-chave"), "Mecatrônica");
    await user.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(await screen.findByText("Mecatrônica")).toBeInTheDocument();
  });

  it("mostra o erro da API sem perder o que foi digitado", async () => {
    const user = userEvent.setup();
    setup([padrao], { "POST /api/keywords": { status: 422, json: { detail: "Esse termo já existe: 'x'" } } });
    const input = await screen.findByLabelText("Nova palavra-chave");
    await user.type(input, "x{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("já existe");
    expect(input).toHaveValue("x");
  });

  it("termo vazio é recusado pelo backend e a mensagem dele é exibida", async () => {
    const user = userEvent.setup();
    setup([padrao], { "POST /api/keywords": { status: 422, json: { detail: "Informe um termo" } } });
    await user.type(await screen.findByLabelText("Nova palavra-chave"), "   {Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Informe um termo");
  });

  it("remove um termo pelo ✕", async () => {
    const user = userEvent.setup();
    setup([padrao]);
    await user.click(await screen.findByRole("button", { name: "Remover Engenheiro Mecânico" }));
    await waitFor(() => expect(screen.queryByText("Engenheiro Mecânico")).not.toBeInTheDocument());
  });
});
