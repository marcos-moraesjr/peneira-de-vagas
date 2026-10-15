import { useState } from "react";
import { buttonSecondary } from "./ui";

/** Copia um texto (ex.: instrução para o Claude) para a área de transferência e confirma. */
export function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
  }
  return (
    <div className="flex items-center gap-3">
      <button type="button" className={buttonSecondary} onClick={copy}>
        Copiar instrução para o Claude
      </button>
      {state === "copied" && <span className="text-xs text-sinal-fg">Copiado</span>}
      {state === "failed" && <span className="text-xs text-erro-fg">Não foi possível copiar: selecione o texto e copie à mão.</span>}
    </div>
  );
}
