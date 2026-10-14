import { useState } from "react";
import { useHealth } from "./api/hooks";
import { ConfigPage } from "./features/configuracoes/ConfigPage";
import { ExecucoesPage } from "./features/execucoes/ExecucoesPage";
import { TutorialPage } from "./features/tutorial/TutorialPage";
import { VagasPage } from "./features/vagas/VagasPage";

const TABS = [
  { id: "vagas", label: "Vagas" },
  { id: "execucoes", label: "Execuções" },
  { id: "config", label: "Configurações" },
  { id: "tutorial", label: "Tutorial" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function HealthBadge() {
  const health = useHealth();
  if (health.isError) return <span className="text-xs text-red-700">API indisponível</span>;
  if (!health.data) return <span className="text-xs text-slate-400">verificando…</span>;
  return (
    <span className="text-xs text-slate-500">
      API: {health.data.status} · banco: {health.data.db}
    </span>
  );
}

export default function App() {
  const [tab, setTab] = useState<TabId>("vagas");
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
          <h1 className="text-lg font-bold">JobScanner</h1>
          <nav role="tablist" className="flex gap-1">
            {TABS.map((item) => (
              <button
                key={item.id}
                role="tab"
                type="button"
                aria-selected={tab === item.id}
                onClick={() => setTab(item.id)}
                className={`rounded-md px-3 py-1.5 text-sm ${tab === item.id ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="ml-auto">
            <HealthBadge />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        {tab === "vagas" && <VagasPage />}
        {tab === "execucoes" && <ExecucoesPage />}
        {tab === "config" && <ConfigPage />}
        {tab === "tutorial" && <TutorialPage />}
      </main>
    </div>
  );
}
