import { ConjuntosPanel } from "../../components/ConjuntosPanel";
import { KeywordsPanel } from "../../components/KeywordsPanel";

export function BuscaPage() {
  return (
    <div className="space-y-3">
      <ConjuntosPanel />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <KeywordsPanel tipo="busca" />
          <p className="text-xs text-grafite-500">Máximo de 6 palavras-chave de busca por conjunto.</p>
        </div>
        <KeywordsPanel tipo="ranking" />
      </div>
      <KeywordsPanel tipo="exclusao" />
    </div>
  );
}
