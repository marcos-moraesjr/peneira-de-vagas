import { useState, type FormEvent } from "react";
import { useConfig, useSaveConfig } from "../../api/hooks";
import type { Config } from "../../api/types";
import { ErrorBox } from "../../components/ErrorBox";
import { buttonPrimary, buttonSecondary, card, inputClass } from "../../components/ui";

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
    titulo: "Ritmo de buscas",
    fields: [
      {
        section: "ritmo",
        key: "pausa_min_s",
        label: "Pausa mínima (s)",
        kind: "number",
        step: "any",
        dica: "Menor espera entre uma ação e outra no navegador.",
      },
      {
        section: "ritmo",
        key: "pausa_max_s",
        label: "Pausa máxima (s)",
        kind: "number",
        step: "any",
        dica: "Maior espera entre ações; o sistema sorteia uma pausa dentro deste intervalo.",
      },
      {
        section: "ritmo",
        key: "rolagem_min_s",
        label: "Rolagem mínima (s)",
        kind: "number",
        step: "any",
        dica: "Menor espera após rolar a lista para carregar o próximo card.",
      },
      {
        section: "ritmo",
        key: "rolagem_max_s",
        label: "Rolagem máxima (s)",
        kind: "number",
        step: "any",
        dica: "Maior espera após rolar a lista; mantém a navegação em ritmo humano.",
      },
    ],
  },
  {
    titulo: "Navegador",
    fields: [
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
  const [draft, setDraft] = useState<Draft>(() => toDraft(config));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const dirty = FIELDS.some((field) => draft[id(field)] !== valueOf(config, field));

  function change(field: Field, value: string) {
    setDraft({ ...draft, [id(field)]: value });
    setSaved(false);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    save.mutate(toConfig(draft, config), {
      onSuccess: (result) => {
        setDraft(toDraft(result));
        setSaved(true);
      },
      onError: (failure) => setError(failure.message),
    });
  }

  function discard() {
    setDraft(toDraft(config));
    setError(null);
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {GROUPS.map((group) => (
        <section key={group.titulo} className={card} aria-label={group.titulo}>
          <h2 className={`${group.intro ? "mb-1" : "mb-3"} text-sm font-semibold text-grafite-900`}>{group.titulo}</h2>
          {group.intro && <p className="mb-3 text-xs text-grafite-500">{group.intro}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {group.fields.map((field) => (
              <div key={id(field)} className="flex flex-col gap-1">
                {field.kind === "checkbox" ? (
                  <label className="flex items-center gap-2 text-sm text-grafite-700">
                    <input
                      type="checkbox"
                      checked={draft[id(field)] === "true"}
                      onChange={(e) => change(field, String(e.target.checked))}
                    />
                    {field.label}
                  </label>
                ) : field.kind === "slider" ? (
                  <>
                    <label htmlFor={id(field)} className="text-sm text-grafite-700">
                      {field.label}
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        id={id(field)}
                        type="range"
                        min={Math.min(field.min ?? 0, Number(valueOf(config, field)), Number(draft[id(field)]))}
                        max={Math.max(field.max ?? SLIDER_MAX, Number(valueOf(config, field)), Number(draft[id(field)]))}
                        step={field.step ?? 1}
                        className="w-full accent-[var(--pn-grafite-900)]"
                        value={draft[id(field)]}
                        onChange={(e) => change(field, e.target.value)}
                      />
                      <output
                        data-testid={`valor-${id(field)}`}
                        className="w-10 text-right text-sm font-medium tabular-nums"
                      >
                        {draft[id(field)]}
                      </output>
                    </div>
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
      {error && <ErrorBox message={error} />}
      <div className="flex items-center gap-3">
        <button type="submit" className={buttonPrimary} disabled={!dirty || save.isPending}>
          Salvar
        </button>
        <button type="button" className={buttonSecondary} disabled={!dirty} onClick={discard}>
          Descartar
        </button>
        {saved && <span className="text-sm text-sinal-fg">Configuração salva. Vale a partir da próxima busca.</span>}
      </div>
    </form>
  );
}

export function ConfigPage() {
  const config = useConfig();
  if (config.isError) return <ErrorBox message="Não foi possível carregar a configuração." />;
  if (!config.data) return <p className="text-sm text-grafite-500">Carregando…</p>;
  return <ConfigForm config={config.data} />;
}
