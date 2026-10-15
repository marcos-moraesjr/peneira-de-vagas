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
    expect(screen.getByLabelText("Localidades")).toHaveValue("");
    expect(screen.getByText("Brasil")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remover Brasil" })).toBeInTheDocument();
    expect(screen.getByLabelText("Pausa máxima (s)")).toHaveValue(6);
    for (const nome of ["Remoto", "Híbrido", "Presencial"]) expect(screen.getByRole("checkbox", { name: nome })).not.toBeChecked();
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
    const user = userEvent.setup();
    setup();
    const salvar = await screen.findByRole("button", { name: "Salvar" });
    expect(salvar).toBeDisabled();
    await user.type(screen.getByLabelText("Localidades"), "Campinas{Enter}");
    expect(salvar).toBeEnabled();
  });

  it("envia a configuração completa, com números, e confirma", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    fireEvent.change(await screen.findByRole("slider", { name: "Pontuação mínima" }), { target: { value: "5" } });
    expect(screen.getByTestId("valor-filtro.min_score")).toHaveTextContent("5");
    await user.click(screen.getByRole("checkbox", { name: "Híbrido" }));
    await user.click(screen.getByRole("checkbox", { name: "Remoto" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toEqual({
      ...CONFIG,
      filtro: { ...CONFIG.filtro, min_score: 5 },
      busca: { ...CONFIG.busca, modalidade: ["remoto", "hibrido"] },
    });
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

  it("desmarcar todas as modalidades envia lista vazia (todas)", async () => {
    const user = userEvent.setup();
    const { calls } = mockApi({
      "GET /api/config": { ...CONFIG, busca: { ...CONFIG.busca, modalidade: ["remoto"] } },
      "PUT /api/config": (body: unknown) => body,
    });
    renderWithClient(<ConfigPage />);
    const remoto = await screen.findByRole("checkbox", { name: "Remoto" });
    expect(remoto).toBeChecked();
    await user.click(remoto);
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await screen.findByText(/configuração salva/i);
    expect((calls.find((c) => c.method === "PUT")?.body as typeof CONFIG).busca.modalidade).toEqual([]);
  });

  it("Descartar volta aos valores em vigor", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(await screen.findByLabelText("Localidades"), "xyz{Enter}");
    await user.click(screen.getByRole("button", { name: "Remover Brasil" }));
    await user.click(screen.getByRole("button", { name: "Descartar" }));
    expect(screen.getByText("Brasil")).toBeInTheDocument();
    expect(screen.queryByText("xyz")).not.toBeInTheDocument();
  });

  it("cadastra várias localidades (cidades e estados) com Enter ou Adicionar e envia a lista", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const campo = await screen.findByLabelText("Localidades");
    await user.type(campo, "Campinas, SP{Enter}");
    expect(campo).toHaveValue("");
    await user.type(campo, "  Minas Gerais ");
    await user.click(screen.getByRole("button", { name: "Adicionar localidade" }));
    await user.click(screen.getByRole("button", { name: "Adicionar localidade" })); // campo vazio: ignora
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    expect((calls.find((c) => c.method === "PUT")?.body as typeof CONFIG).busca.localidades).toEqual([
      "Brasil",
      "Campinas, SP",
      "Minas Gerais",
    ]);
  });

  it("remover todas as localidades envia lista vazia (sem filtro de local)", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "Remover Brasil" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await screen.findByText(/configuração salva/i);
    expect((calls.find((c) => c.method === "PUT")?.body as typeof CONFIG).busca.localidades).toEqual([]);
  });

  it("Enter no campo de localidade não envia o formulário", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.type(await screen.findByLabelText("Localidades"), "Recife{Enter}");
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });
});
