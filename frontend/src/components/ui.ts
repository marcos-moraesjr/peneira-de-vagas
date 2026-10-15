const foco = "focus-visible:shadow-foco";
export const buttonPrimary = `rounded-botao bg-grafite-900 px-5 py-2 text-corpo font-medium text-painel hover:opacity-90 ${foco} disabled:cursor-not-allowed disabled:bg-linha-2 disabled:text-grafite-400`;
export const buttonSecondary = `rounded-botao border border-linha bg-painel px-3.5 py-2 text-dado font-medium text-grafite-900 hover:bg-linha-2 ${foco} disabled:cursor-not-allowed disabled:opacity-50`;
export const buttonDark = `rounded-botao bg-grafite-900 px-3.5 py-2 text-dado font-medium text-painel hover:opacity-90 ${foco} disabled:cursor-not-allowed disabled:opacity-50`;
export const buttonDanger = `rounded-botao border border-erro/40 bg-erro-bg px-3.5 py-2 text-dado font-medium text-erro-fg hover:bg-erro/10 ${foco} disabled:cursor-not-allowed disabled:opacity-50`;
export const inputClass = `rounded-botao border border-linha bg-painel px-3 py-2 text-dado text-grafite-900 placeholder:text-grafite-400 ${foco}`;
export const card = "rounded-painel border border-linha bg-painel p-4";
export const label = "text-rotulo uppercase text-grafite-500";
export const sourceColors: Record<string, string> = {
  linkedin: "bg-fonte-linkedin-bg text-fonte-linkedin-fg",
  indeed: "bg-fonte-indeed-bg text-fonte-indeed-fg",
  gupy: "bg-fonte-gupy-bg text-fonte-gupy-fg",
};
