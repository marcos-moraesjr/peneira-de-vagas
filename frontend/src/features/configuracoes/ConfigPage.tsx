import { useState, type FormEvent } from "react";
import { useConfig, useRestaurarPadroes, useSaveConfig } from "../../api/hooks";
import type { Config } from "../../api/types";
import { ErrorBox } from "../../components/ErrorBox";
import { buttonSecondary, card, inputClass } from "../../components/ui";

type Section = keyof Config;
type Field = {
  section: Section;
  key: string;
  label: string;
  kind: "number" | "text" | "slider" | "checkbox";
  step?: string;
  dica?: string;
  /** Faixa do controle deslizante; a faixa cresce para caber um valor já gravado fora dela. */
  min?: number;
  max?: number;
};

const GROUPS: { titulo: string; intro?: string; fields: Field[] }[] = [
  {
    titulo: "Rankeamento de vagas",
    intro:
      "Cada vaga soma pontos pelas palavras-chave do conjunto ativo (da busca e de ranking) que aparecem no texto dela (cada palavra conta uma vez). Só entra na lista a vaga que atinge a pontuação mínima.",
    fields: [
      {
        section: "filtro",
        key: "peso_titulo",
        label: "Pontos por palavra-chave no título",
        kind: "slider",
        dica: "Quanto cada palavra-chave encontrada no título da vaga soma à pontuação.",
      },
      {
        section: "filtro",
        key: "peso_descricao",
        label: "Pontos por palavra-chave na descrição",
        kind: "slider",
        dica: "Quanto cada palavra-chave encontrada na descrição da vaga soma à pontuação.",
      },
      {
        section: "filtro",
        key: "min_score",
        label: "Pontuação mínima para aparecer",
        kind: "slider",
        dica: "Vagas com menos pontos que isso são descartadas. 0 aceita qualquer vaga sem palavra excluída.",
      },
      {
        section: "filtro",
        key: "trecho_max_chars",
        label: "Tamanho máximo da descrição lida (caracteres)",
        kind: "number",
        dica: "Só esse começo da descrição é guardado e usado para pontuar.",
      },
    ],
  },
  {
    titulo: "Limites de busca",
    fields: [
      {
        section: "limites",
        key: "max_paginas_por_termo",
        label: "Páginas abertas por palavra-chave (em cada fonte)",
        kind: "slider",
        min: 1,
        max: 10,
        dica: "Quantas páginas de resultados são abertas para cada palavra-chave em cada plataforma. Mais páginas trazem mais vagas, mas aumentam o tempo e o risco de bloqueio.",
      },
    ],
  },
  {
    titulo: "Ritmo e navegador",
    fields: [
      {
        section: "ritmo",
        key: "pausa_min_s",
        label: "Pausa mínima (s)",
        kind: "slider",
        min: 0,
        max: 15,
        step: "0.25",
        dica: "Menor espera entre uma ação e outra no navegador.",
      },
      {
        section: "ritmo",
        key: "pausa_max_s",
        label: "Pausa máxima (s)",
        kind: "slider",
        min: 0,
        max: 15,
        step: "0.25",
        dica: "Maior espera entre ações; o sistema sorteia uma pausa dentro deste intervalo.",
      },
      {
        section: "ritmo",
        key: "rolagem_min_s",
        label: "Rolagem mínima (s)",
        kind: "slider",
        min: 0,
        max: 3,
        step: "0.05",
        dica: "Menor espera após rolar a lista para carregar o próximo card.",
      },
      {
        section: "ritmo",
        key: "rolagem_max_s",
        label: "Rolagem máxima (s)",
        kind: "slider",
        min: 0,
        max: 3,
        step: "0.05",
        dica: "Maior espera após rolar a lista; mantém a navegação em ritmo humano.",
      },
      {
        section: "navegador",
        key: "max_tentativas_painel",
        label: "Tentativas para abrir o painel da vaga",
        kind: "slider",
        min: 1,
        max: 10,
        dica: "Quantas vezes o sistema tenta abrir o painel de uma vaga antes de pular a vaga e seguir para a próxima.",
      },
      {
        section: "navegador",
        key: "intervalo_tentativa_painel_s",
        label: "Intervalo entre tentativas (s)",
        kind: "slider",
        min: 1,
        max: 60,
        dica: "Espera depois de um erro ao abrir o painel, antes de tentar de novo. Dá tempo de a página do site se estabilizar.",
      },
      {
        section: "navegador",
        key: "abas_paralelas",
        label: "Buscar as plataformas ao mesmo tempo",
        kind: "checkbox",
        dica: "Uma aba por plataforma, cada uma com as próprias pausas. Desligado: uma plataforma por vez.",
      },
    ],
  },
  {
    titulo: "Interface",
    fields: [
      {
        section: "api",
        key: "jobs_page_size",
        label: "Vagas por página",
        kind: "number",
        dica: "Quantidade de vagas exibidas por página na lista.",
      },
      {
        section: "api",
        key: "poll_interval_ms",
        label: "Intervalo de atualização (ms)",
        kind: "number",
        dica: "Frequência com que a tela atualiza o andamento enquanto uma busca está em execução.",
      },
    ],
  },
];

const FIELDS = GROUPS.flatMap((group) => group.fields);
type Draft = Record<string, string>;
const SLIDER_MAX = 10;
const id = (field: Field) => `${field.section}.${field.key}`;
const valueOf = (config: Config, field: Field) => {
  return String((config[field.section] as Record<string, unknown>)[field.key]);
};

function toDraft(config: Config): Draft {
  return Object.fromEntries(FIELDS.map((field) => [id(field), valueOf(config, field)]));
}

/** Parte da config devolvida pelo servidor e troca só os campos da tela (o resto, como busca.localidades, segue como veio). */
function toConfig(draft: Draft, base: Config): Config {
  const config = structuredClone(base) as unknown as Record<string, Record<string, unknown>>;
  for (const field of FIELDS) {
    const raw = draft[id(field)];
    config[field.section][field.key] =
      field.kind === "checkbox" ? raw === "true" : field.kind === "text" ? raw : raw === "" ? null : Number(raw);
  }
  return config as unknown as Config;
}

function ConfigForm({ config }: { config: Config }) {
  const save = useSaveConfig();
  const restaurar = useRestaurarPadroes();
  const [draft, setDraft] = useState<Draft>(() => toDraft(config));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function change(field: Field, value: string) {
    setDraft({ ...draft, [id(field)]: value });
    setSaved(false);
  }

  /** Salva o rascunho (ou `next`, quando o estado ainda não renderizou) se difere do que está em vigor. */
  function commit(next: Draft = draft) {
    if (!FIELDS.some((field) => next[id(field)] !== valueOf(config, field))) return;
    setError(null);
    setSaved(false);
    save.mutate(toConfig(next, config), {
      onSuccess: (result) => {
        setDraft((current) => (current === next ? toDraft(result) : current));
        setSaved(true);
      },
      onError: (failure) => setError(failure.message),
    });
  }

  function restaurarPadroes() {
    if (!window.confirm("Restaurar todos os parâmetros desta tela para os padrões iniciais? Os valores atuais serão perdidos.")) return;
    setError(null);
    restaurar.mutate(undefined, {
      onSuccess: (result) => {
        setDraft(toDraft(result));
        setSaved(true);
      },
      onError: (failure) => setError(failure.message),
    });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    commit();
  }

  function toggle(field: Field, checked: boolean) {
    const next = { ...draft, [id(field)]: String(checked) };
    setDraft(next);
    commit(next);
  }

  return (
    <form onSubmit={submit} onBlur={() => commit()} className="space-y-4">
      {GROUPS.map((group) => (
        <section key={group.titulo} className={card} aria-label={group.titulo}>
          <h2 className={`${group.intro ? "mb-1" : "mb-3"} text-sm font-semibold text-grafite-900`}>{group.titulo}</h2>
          {group.intro && <p className="mb-3 text-xs text-grafite-500">{group.intro}</p>}
          <div className="grid gap-x-10 gap-y-3 sm:grid-cols-2">
            {group.fields.map((field) => (
              <div key={id(field)} className="flex flex-col gap-1">
                {field.kind === "checkbox" ? (
                  <label className="flex items-center gap-2 text-sm text-grafite-700">
                    <input
                      type="checkbox"
                      checked={draft[id(field)] === "true"}
                      onChange={(e) => toggle(field, e.target.checked)}
                    />
                    {field.label}
                  </label>
                ) : field.kind === "slider" ? (
                  <>
                    <div className="flex items-baseline justify-between gap-3">
                      <label htmlFor={id(field)} className="text-sm text-grafite-700">
                        {field.label}
                      </label>
                      <output data-testid={`valor-${id(field)}`} className="text-sm font-semibold tabular-nums text-grafite-900">
                        {draft[id(field)]}
                      </output>
                    </div>
                    <input
                      id={id(field)}
                      type="range"
                      min={Math.min(field.min ?? 0, Number(valueOf(config, field)), Number(draft[id(field)]))}
                      max={Math.max(field.max ?? SLIDER_MAX, Number(valueOf(config, field)), Number(draft[id(field)]))}
                      step={field.step ?? 1}
                      className="w-full accent-[var(--pn-grafite-900)]"
                      value={draft[id(field)]}
                      onChange={(e) => change(field, e.target.value)}
                      onPointerUp={() => commit()}
                      onKeyUp={() => commit()}
                    />
                  </>
                ) : (
                  <label className="flex flex-col gap-1 text-sm text-grafite-700">
                    {field.label}
                    <input
                      className={inputClass}
                      type={field.kind}
                      step={field.step}
                      value={draft[id(field)]}
                      onChange={(e) => change(field, e.target.value)}
                    />
                  </label>
                )}
                {field.dica && <span className="text-xs text-grafite-500">{field.dica}</span>}
              </div>
            ))}
          </div>
        </section>
      ))}
      <section className={card} aria-label="Padrões iniciais">
        <h2 className="mb-1 text-sm font-semibold text-grafite-900">Padrões iniciais</h2>
        <p className="mb-3 text-xs text-grafite-500">
          Devolve todos os parâmetros desta tela aos valores que vêm com o app. Palavras-chave, conjuntos e vagas não mudam.
        </p>
        <button type="button" className={buttonSecondary} disabled={restaurar.isPending} onClick={restaurarPadroes}>
          Restaurar padrões iniciais
        </button>
      </section>
      {error && <ErrorBox message={error} />}
      <p role="status" className="min-h-5 text-sm text-sinal-fg">
        {save.isPending ? <span className="text-grafite-500">Salvando…</span> : saved ? "Configuração salva. Vale a partir da próxima busca." : null}
      </p>
    </form>
  );
}

export function ConfigPage() {
  const config = useConfig();
  if (config.isError) return <ErrorBox message="Não foi possível carregar a configuração." />;
  if (!config.data) return <p className="text-sm text-grafite-500">Carregando…</p>;
  return <ConfigForm config={config.data} />;
}
