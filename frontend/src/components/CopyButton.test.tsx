import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CopyButton } from "./CopyButton";

function stubClipboard(writeText: () => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

describe("CopyButton", () => {
  it("copia o texto e confirma", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    render(<CopyButton text="instrução completa" />);
    await user.click(screen.getByRole("button", { name: "Copiar instrução para o Claude" }));
    expect(writeText).toHaveBeenCalledWith("instrução completa");
    expect(await screen.findByText("Copiado")).toBeInTheDocument();
  });

  it("se o navegador recusar a cópia, orienta a selecionar o texto à mão", async () => {
    const user = userEvent.setup();
    stubClipboard(vi.fn().mockRejectedValue(new Error("negado")));
    render(<CopyButton text="x" />);
    await user.click(screen.getByRole("button", { name: "Copiar instrução para o Claude" }));
    expect(await screen.findByText(/selecione o texto/i)).toBeInTheDocument();
    expect(screen.queryByText("Copiado")).not.toBeInTheDocument();
  });
});
