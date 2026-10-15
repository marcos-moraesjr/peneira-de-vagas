import { screen, waitFor } from "@testing-library/react";
import { mockApi, renderWithClient } from "../../test/mockApi";
import { UpdateNotice } from "./UpdateNotice";

function setup(resposta: unknown) {
  const { calls } = mockApi({ "GET /api/atualizacao": resposta });
  renderWithClient(<UpdateNotice />);
  return calls;
}

describe("UpdateNotice", () => {
  it("avisa que há versão nova e mostra o comando para atualizar", async () => {
    setup({ estado: "disponivel", instalada: "0.1.0", disponivel: "0.2.0", comando: "peneira atualizar" });
    const aviso = await screen.findByRole("note");
    expect(aviso).toHaveTextContent("0.2.0");
    expect(aviso).toHaveTextContent("0.1.0");
    expect(aviso).toHaveTextContent("peneira atualizar");
    expect(aviso).toHaveTextContent(/scanners/i);
  });

  it.each(["atualizado", "desenvolvimento", "indisponivel", "desligado"])("não mostra nada quando o estado é %s", async (estado) => {
    const calls = setup({ estado });
    await waitFor(() => expect(calls.some((call) => call.path === "/api/atualizacao")).toBe(true));
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
