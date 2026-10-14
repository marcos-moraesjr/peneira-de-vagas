import { useScanners } from "../../api/hooks";
import type { Scanner } from "../../api/types";
import { CopyButton } from "../../components/CopyButton";
import { sourceLabel } from "../../lib/failures";

function CopyInstruction({ instruction }: { instruction: string }) {
  return (
    <div className="mt-2 space-y-2">
      <details className="text-xs">
        <summary className="cursor-pointer text-red-800">Ver instrução</summary>
        <pre className="mt-1 whitespace-pre-wrap rounded bg-white/70 p-2 text-slate-800">{instruction}</pre>
      </details>
      <CopyButton text={instruction} />
    </div>
  );
}

function RedoAlert({ scanner }: { scanner: Scanner }) {
  return (
    <div role="alert" className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
      <p>
        <strong>
          O scanner do {sourceLabel(scanner.fonte)} (v{scanner.versao}) precisa ser refeito.
        </strong>{" "}
        {scanner.mensagem} Peça ao Claude para explorar a plataforma de novo e gerar a próxima versão.
      </p>
      {scanner.instrucao && <CopyInstruction instruction={scanner.instrucao} />}
    </div>
  );
}

/** Aviso de que um scanner quebrou (refazer) ou está sob suspeita (atenção); sem nada a dizer, não aparece. */
export function ScannerBanner() {
  const scanners = useScanners().data ?? [];
  const toRedo = scanners.filter((scanner) => scanner.status === "refazer");
  const watch = scanners.filter((scanner) => scanner.status === "atencao");
  return (
    <>
      {toRedo.map((scanner) => (
        <RedoAlert key={scanner.fonte} scanner={scanner} />
      ))}
      {watch.map((scanner) => (
        <p key={scanner.fonte} role="note" className="rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-700">
          <strong>{sourceLabel(scanner.fonte)}</strong> (scanner v{scanner.versao}): {scanner.mensagem}
        </p>
      ))}
    </>
  );
}
