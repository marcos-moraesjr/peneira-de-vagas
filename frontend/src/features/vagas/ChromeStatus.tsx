import { useBrowser, useOpenBrowser } from "../../api/hooks";
import { ErrorBox } from "../../components/ErrorBox";
import { buttonSecondary } from "../../components/ui";

/** Estado do Chrome dedicado (necessário para LinkedIn, Indeed e Google) com botão para abri-lo. */
export function ChromeStatus() {
  const browser = useBrowser();
  const open = useOpenBrowser();
  if (!browser.data) return null;
  if (browser.data.aberto) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-600">
        <span aria-hidden className="h-2 w-2 rounded-full bg-emerald-500" />
        Chrome dedicado aberto
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
        <span className="flex items-center gap-2">
          <span aria-hidden className="h-2 w-2 rounded-full bg-amber-500" />
          Chrome dedicado fechado
        </span>
        <button type="button" className={buttonSecondary} disabled={open.isPending} onClick={() => open.mutate()}>
          {open.isPending ? "Abrindo…" : "Abrir Chrome dedicado"}
        </button>
        <span className="text-xs text-slate-500">Necessário para LinkedIn, Indeed e Google (a Gupy não precisa).</span>
      </div>
      {open.error && <ErrorBox message={open.error.message} />}
    </div>
  );
}
