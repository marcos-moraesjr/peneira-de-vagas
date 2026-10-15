import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, mockApi, renderWithClient } from "../../test/mockApi";
import { ConfigPage } from "./ConfigPage";

function setup(put: unknown = (body: unknown) => body) {
  const api = mockApi({ "GET /api/config": CONFIG, "PUT /api/config": put });
  renderWithClient(<ConfigPage />);
  return api;
}

describe("ConfigPage", () => {
  it("mostra a configuração em vigor nos campos", async () => {
    setup();
    expect(await screen.findByLabelText("Pontuação mínima")).toHaveValue("3");
    expect(screen.getByLabelText("Pausa máxima (s)")).toHaveValue(6);
  });

  it("não oferece localidade nem modalidade (o filtro fica só no config.toml)", async () => {
    setup();
    await screen.findByLabelText("Pontuação mínima");
    expect(screen.queryByLabelText("Localidades")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Adicionar localidade" })).not.toBeInTheDocument();
    for (const nome of ["Remoto", "Híbrido", "Presencial"]) expect(screen.queryByRole("checkbox", { name: nome })).not.toBeInTheDocument();
  });

  it("pesos e pontuação mínima são controles deslizantes com o valor à vista", async () => {
    setup();
    for (const nome of ["Peso no título", "Peso na descrição", "Pontuação mínima"]) {
      expect(await screen.findByRole("slider", { name: nome })).toBeInTheDocument();
    }
    expect(screen.getByRole("slider", { name: "Peso no título" })).toHaveValue("3");
    expect(screen.getByTestId("valor-filtro.peso_titulo")).toHaveTextContent("3");
  });

  it("só habilita Salvar depois de alterar algo", async () => {
    setup();
    const salvar = await screen.findByRole("button", { name: "Salvar" });
    expect(salvar).toBeDisabled();
    fireEvent.change(screen.getByRole("slider", { name: "Pontuação mínima" }), { target: { value: "4" } });
    expect(salvar).toBeEnabled();
  });

  it("envia a configuração completa, com números, e confirma", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    fireEvent.change(await screen.findByRole("slider", { name: "Pontuação mínima" }), { target: { value: "5" } });
    expect(screen.getByTestId("valor-filtro.min_score")).toHaveTextContent("5");
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    // busca.localidades e busca.modalidade não estão na tela, mas seguem no corpo, como o servidor devolveu
    expect(put?.body).toEqual({ ...CONFIG, filtro: { ...CONFIG.filtro, min_score: 5 } });
    expect(screen.getByRole("button", { name: "Salvar" })).toBeDisabled();
  });

  it("ativa a busca em paralelo por plataforma e envia navegador.abas_paralelas", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const opcao = await screen.findByRole("checkbox", { name: /buscar as plataformas ao mesmo tempo/i });
    expect(opcao).not.toBeChecked();
    await user.click(opcao);
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ ...CONFIG, navegador: { abas_paralelas: true } });
  });

  it("mostra o erro do backend e mantém o que foi digitado", async () => {
    const user = userEvent.setup();
    setup({ status: 422, json: { detail: "Config inválida: pausa_min_s=9.0 (esperado <= pausa_max_s=6.0)" } });
    const campo = await screen.findByLabelText("Pausa mínima (s)");
    await user.clear(campo);
    await user.type(campo, "9");
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText(/pausa_min_s=9.0/)).toBeInTheDocument();
    expect(campo).toHaveValue(9);
  });

  it("Descartar volta aos valores em vigor", async () => {
    const user = userEvent.setup();
    setup();
    const slider = await screen.findByRole("slider", { name: "Pontuação mínima" });
    fireEvent.change(slider, { target: { value: "7" } });
    expect(slider).toHaveValue("7");
    await user.click(screen.getByRole("button", { name: "Descartar" }));
    expect(slider).toHaveValue("3");
  });
});
