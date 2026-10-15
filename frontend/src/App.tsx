import { useState } from "react";
import { ThemeToggle } from "./components/ThemeToggle";
import { useHealth } from "./api/hooks";
import { ConfigPage } from "./features/configuracoes/ConfigPage";
import { ExecucoesPage } from "./features/execucoes/ExecucoesPage";
import { ComoUsarPage } from "./features/como-usar/ComoUsarPage";
import { BuscaPage } from "./features/vagas/BuscaPage";
import { VagasPage } from "./features/vagas/VagasPage";

const TABS = [
  { id: "como-usar", label: "Como usar" },
  { id: "busca", label: "Parâmetros de busca" },
  { id: "vagas", label: "Buscar vagas" },
  { id: "execucoes", label: "Execuções" },
  { id: "config", label: "Configurações" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function HealthBadge() {
  const health = useHealth();
  const text = "flex items-center gap-2 text-legenda text-grafite-500";
  if (health.isError) return <span className={text}>API indisponível</span>;
  if (!health.data) return <span className={text}>verificando…</span>;
  return (
    <span className={text}>
      <span aria-hidden className="h-[7px] w-[7px] rounded-full bg-sinal" />
      API: {health.data.status} · banco: {health.data.db}
    </span>
  );
}

function Logo() {
  return (
    <h1 className="flex items-center gap-2 text-[17px] font-semibold tracking-[-0.03em]">
      <img src="/peneira-icon.svg" alt="" className="h-[22px] w-[22px]" />
      <span>Peneira de Vagas</span>
    </h1>
  );
}

export default function App() {
  const [tab, setTab] = useState<TabId>("vagas");
  return (
    <div className="min-h-screen bg-papel text-grafite-900">
      <header className="fixed inset-y-0 left-0 z-10 flex w-56 flex-col gap-6 border-r border-linha bg-painel px-4 py-5">
        <Logo />
        <nav role="tablist" aria-orientation="vertical" className="flex flex-col gap-1">
          {TABS.map((item) => (
            <button
              key={item.id}
              role="tab"
              type="button"
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
              className={`rounded-botao border-l-2 px-3 py-2 text-left text-corpo font-medium ${tab === item.id ? "border-grafite-900 bg-linha-2 text-grafite-900" : "border-transparent text-grafite-500 hover:text-grafite-900"}`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="mt-auto flex flex-col items-start gap-3">
          <HealthBadge />
          <ThemeToggle />
        </div>
      </header>
      <main className="ml-56 px-6 py-4">
        <div className="mx-auto max-w-7xl">
          {tab === "vagas" && <VagasPage />}
          {tab === "busca" && <BuscaPage />}
          {tab === "execucoes" && <ExecucoesPage />}
          {tab === "config" && <ConfigPage />}
          {tab === "como-usar" && <ComoUsarPage />}
        </div>
      </main>
    </div>
  );
}
