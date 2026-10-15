import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { CONFIG, mockApi, renderWithClient } from "../test/mockApi";
import { ConjuntosPanel } from "./ConjuntosPanel";

type Conjunto = { id: number; nome: string; ativo: boolean };

const mecanica: Conjunto = { id: 1, nome: "Mecânica", ativo: true };
const tecnologia: Conjunto = { id: 2, nome: "Tecnologia", ativo: false };

function setup(initial: Conjunto[], extra: Record<string, unknown> = {}) {
  let items = [...initial];
  const api = mockApi({
    "GET /api/config": CONFIG,
    "GET /api/conjuntos": () => items,
    "POST /api/conjuntos": (body: unknown) => {
      const created = { id: 10, nome: (body as { nome: string }).nome, ativo: true };
      items = [...items.map((c) => ({ ...c, ativo: false })), created];
      return { status: 201, json: created };
    },
    "POST /api/conjuntos/2/ativar": () => {
      items = items.map((c) => ({ ...c, ativo: c.id === 2 }));
      return { status: 204 };
    },
    "POST /api/conjuntos/1/copiar": (body: unknown) => {
      const copia = { id: 11, nome: (body as { nome: string }).nome, ativo: true };
      items = [...items.map((c) => ({ ...c, ativo: false })), copia];
      return { status: 201, json: copia };
    },
    "PATCH /api/conjuntos/1": (body: unknown) => {
      items = items.map((c) => (c.id === 1 ? { ...c, nome: (body as { nome: string }).nome } : c));
      return items[0];
    },
    ...extra,
    "DELETE /api/conjuntos/1": () => {
      items = items.filter((c) => c.id !== 1);
      return { status: 204 };
    },
  });
  renderWithClient(<ConjuntosPanel />);
  return api;
}

describe("ConjuntosPanel", () => {
  it("lista os conjuntos com o ativo selecionado", async () => {
    setup([mecanica, tecnologia]);
    const select = await screen.findByLabelText("Conjunto ativo");
    await waitFor(() => expect(select).toHaveValue("1"));
    expect(screen.getByRole("option", { name: "Tecnologia" })).toBeInTheDocument();
  });

  it("trocar o conjunto ativa o escolhido", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await screen.findByRole("option", { name: "Tecnologia" });
    await user.selectOptions(screen.getByLabelText("Conjunto ativo"), "Tecnologia");
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/conjuntos/2/ativar")).toBe(true));
    await waitFor(() => expect(screen.getByLabelText("Conjunto ativo")).toHaveValue("2"));
  });

  it("cria um conjunto novo e limpa o campo", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica]);
    const input = await screen.findByLabelText("Novo conjunto");
    await user.type(input, "Tecnologia{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/conjuntos")?.body).toEqual({ nome: "Tecnologia" }));
    await waitFor(() => expect(screen.getByLabelText("Conjunto ativo")).toHaveValue("10"));
    expect(input).toHaveValue("");
  });

  it("exclui o conjunto ativo depois de confirmar", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup([mecanica, tecnologia]);
    await user.click(await screen.findByRole("button", { name: "Excluir conjunto" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/conjuntos/1")).toBe(true));
  });

  it("com um só conjunto, não dá para excluir", async () => {
    setup([mecanica]);
    expect(await screen.findByRole("button", { name: "Excluir conjunto" })).toBeDisabled();
  });

  it("renomeia o conjunto ativo: abre com o nome atual, envia o novo e volta ao seletor", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await user.click(await screen.findByRole("button", { name: "Renomear conjunto" }));
    const input = screen.getByLabelText("Novo nome do conjunto");
    expect(input).toHaveValue("Mecânica");
    await user.clear(input);
    await user.type(input, "Engenharia mecânica{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/conjuntos/1")?.body).toEqual({ nome: "Engenharia mecânica" }));
    expect(await screen.findByRole("option", { name: "Engenharia mecânica" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Novo nome do conjunto")).not.toBeInTheDocument();
  });

  it("cancelar a renomeação não envia nada", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica]);
    await user.click(await screen.findByRole("button", { name: "Renomear conjunto" }));
    await user.type(screen.getByLabelText("Novo nome do conjunto"), "x");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByLabelText("Conjunto ativo")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("nome recusado pelo servidor aparece no aviso e mantém a edição aberta", async () => {
    const user = userEvent.setup();
    setup([mecanica, tecnologia], { "PATCH /api/conjuntos/1": { status: 422, json: { detail: "Esse conjunto já existe: 'Tecnologia'" } } });
    await user.click(await screen.findByRole("button", { name: "Renomear conjunto" }));
    const input = screen.getByLabelText("Novo nome do conjunto");
    await user.clear(input);
    await user.type(input, "Tecnologia{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Esse conjunto já existe");
    expect(screen.getByLabelText("Novo nome do conjunto")).toBeInTheDocument();
  });

  it("copia o conjunto ativo: sugere um nome, envia o escolhido e ativa a cópia", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await user.click(await screen.findByRole("button", { name: "Copiar conjunto" }));
    const input = screen.getByLabelText("Nome da cópia");
    expect(input).toHaveValue("Mecânica (cópia)");
    await user.clear(input);
    await user.type(input, "Mecânica júnior{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/conjuntos/1/copiar")?.body).toEqual({ nome: "Mecânica júnior" }));
    await waitFor(() => expect(screen.getByLabelText("Conjunto ativo")).toHaveValue("11"));
    expect(screen.getByRole("option", { name: "Mecânica júnior" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Nome da cópia")).not.toBeInTheDocument();
  });

  it("cancelar a cópia não envia nada", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica]);
    await user.click(await screen.findByRole("button", { name: "Copiar conjunto" }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByLabelText("Conjunto ativo")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/copiar"))).toBe(false);
  });

  it("nome da cópia recusado pelo servidor aparece no aviso e mantém a edição aberta", async () => {
    const user = userEvent.setup();
    setup([mecanica, tecnologia], { "POST /api/conjuntos/1/copiar": { status: 422, json: { detail: "Esse conjunto já existe: 'Mecânica (cópia)'" } } });
    await user.click(await screen.findByRole("button", { name: "Copiar conjunto" }));
    await user.click(screen.getByRole("button", { name: "Criar cópia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Esse conjunto já existe");
    expect(screen.getByLabelText("Nome da cópia")).toBeInTheDocument();
  });
});
