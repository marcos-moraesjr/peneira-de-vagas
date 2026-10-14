import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeScanner, mockApi, renderWithClient, CONFIG } from "../../test/mockApi";
import { ScannerBanner } from "./ScannerBanner";

const INSTRUCAO = 'O scanner da fonte "LinkedIn" (versão 1.0.0) precisa ser refeito.\nFaça, seguindo TDD...';

function setup(scanners: unknown[]) {
  mockApi({ "GET /api/config": CONFIG, "GET /api/scanners": scanners });
  renderWithClient(<ScannerBanner />);
}

describe("ScannerBanner", () => {
  it("não mostra nada quando todos os scanners estão em dia", async () => {
    setup([makeScanner("linkedin"), makeScanner("gupy")]);
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("scanner que precisa ser refeito aparece como alerta com fonte, versão e motivo", async () => {
    setup([
      makeScanner("linkedin", {
        status: "refazer",
        falhas_consecutivas: 2,
        ultimo_motivo: "seletor_nao_encontrado",
        mensagem: "2 falhas seguidas (seletor_nao_encontrado): o scanner provavelmente quebrou e precisa ser refeito.",
        instrucao: INSTRUCAO,
      }),
    ]);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("LinkedIn");
    expect(alert).toHaveTextContent("v1.0.0");
    expect(alert).toHaveTextContent(/precisa ser refeito/i);
    expect(alert).toHaveTextContent(/Claude/);
  });

  it("copia a instrução pronta para o Claude", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    setup([makeScanner("linkedin", { status: "refazer", instrucao: INSTRUCAO, mensagem: "x" })]);
    await user.click(await screen.findByRole("button", { name: "Copiar instrução para o Claude" }));
    expect(writeText).toHaveBeenCalledWith(INSTRUCAO);
    expect(await screen.findByText("Copiado")).toBeInTheDocument();
  });

  it("deixa ver a instrução antes de copiar", async () => {
    setup([makeScanner("indeed", { status: "refazer", instrucao: INSTRUCAO, mensagem: "x" })]);
    expect(await screen.findByText(/seguindo TDD/)).toBeInTheDocument();
  });

  it("scanner em atenção aparece como nota discreta, não como alerta", async () => {
    setup([makeScanner("gupy", { status: "atencao", mensagem: "1 falha(s) seguida(s) (http_erro). Se repetir, o scanner precisa ser refeito." })]);
    const note = await screen.findByRole("note");
    expect(note).toHaveTextContent("Gupy");
    expect(note).toHaveTextContent(/1 falha/);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("vários scanners a refazer geram um aviso para cada fonte", async () => {
    setup([
      makeScanner("linkedin", { status: "refazer", instrucao: INSTRUCAO, mensagem: "x" }),
      makeScanner("indeed", { status: "refazer", instrucao: INSTRUCAO, mensagem: "y" }),
    ]);
    expect(await screen.findAllByRole("alert")).toHaveLength(2);
  });
});
