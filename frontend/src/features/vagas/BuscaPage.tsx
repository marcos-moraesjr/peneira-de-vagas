import { useKeywords, useRuns, useStartRun } from "../../api/hooks";
import { ConjuntosPanel } from "../../components/ConjuntosPanel";
import { ErrorBox } from "../../components/ErrorBox";
import { KeywordsPanel } from "../../components/KeywordsPanel";
import { SOURCES } from "../../lib/failures";
import { ChromeStatus } from "./ChromeStatus";
import { FailureBanner } from "./FailureBanner";
import { RunBar } from "./RunBar";
import { ScannerBanner } from "./ScannerBanner";
import { VerificationPrompt } from "./VerificationPrompt";

export function BuscaPage() {
  const runs = useRuns();
  const latest = runs.data?.[0];
  const keywords = useKeywords("busca");
  const startRun = useStartRun();
  const hasKeywords = (keywords.data?.length ?? 0) > 0;

  return (
    <div className="space-y-3">
      <RunBar
        latest={latest}
        canSearch={hasKeywords}
        starting={startRun.isPending}
        sources={SOURCES}
        onSearch={(sources) => startRun.mutate(sources)}
        hint={hasKeywords || !keywords.isSuccess ? undefined : "Adicione ao menos uma palavra-chave para buscar."}
      />
      {startRun.error && <ErrorBox message={startRun.error.message} />}
      <VerificationPrompt running={latest?.status === "executando"} />
      <ChromeStatus />
      <FailureBanner run={latest} onRestart={(fontes) => startRun.mutate(fontes)} restarting={startRun.isPending} />
      <ScannerBanner />

      <ConjuntosPanel />
      <div className="grid gap-4 md:grid-cols-2">
        <KeywordsPanel tipo="busca" />
        <KeywordsPanel tipo="exclusao" />
      </div>
    </div>
  );
}
