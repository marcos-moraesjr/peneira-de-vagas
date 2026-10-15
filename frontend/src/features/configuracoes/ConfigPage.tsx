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
};

const GROUPS: { titulo: string; fields: Field[] }[] = [
  {
    titulo: "Busca",
    fields: [
      {
        section: "busca",
        key: "janela_horas",
        label: "Janela de recência (horas)",
        kind: "number",
      },
      {
        section: "busca",
        key: "keyword_max_length",
        label: "Tamanho máximo da palavra-chave",
        kind: "number",
      },
    ],
  },
  {
    titulo: "Filtro",
    fields: [
      {
        section: "filtro",
        key: "peso_titulo",
        label: "Peso no título",
        kind: "slider",
      },
      {
        section: "filtro",
        key: "peso_descricao",
        label: "Peso na descrição",
        kind: "slider",
      },
      {
        section: "filtro",
        key: "min_score",
        label: "Pontuação mínima",
        kind: "slider",
      },
      {
        section: "filtro",
        key: "trecho_max_chars",
        label: "Tamanho máximo do trecho",
        kind: "number",
      },
    ],
  },
  {
    titulo: "Limites",
    fields: [
      {
        section: "limites",
        key: "max_vagas_lista",
        label: "Vagas lidas por fonte",
        kind: "number",
      },
    ],
  },
  {
    titulo: "Ritmo",
    fields: [
      {
        section: "ritmo",
        key: "pausa_min_s",
        label: "Pausa mínima (s)",
        kind: "number",
        step: "any",
      },
      {
        section: "ritmo",
        key: "pausa_max_s",
        label: "Pausa máxima (s)",
        kind: "number",
        step: "any",
      },
      {
        section: "ritmo",
        key: "rolagem_min_s",
        label: "Rolagem mínima (s)",
        kind: "number",
        step: "any",
      },
      {
        section: "ritmo",
        key: "rolagem_max_s",
        label: "Rolagem máxima (s)",
        kind: "number",
        step: "any",
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
      },
      {
        section: "api",
        key: "poll_interval_ms",
        label: "Intervalo de atualização (ms)",
        kind: "number",
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
          <h2 className="mb-3 text-sm font-semibold text-grafite-900">{group.titulo}</h2>
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
                        min={0}
                        max={Math.max(SLIDER_MAX, Number(valueOf(config, field)), Number(draft[id(field)]))}
                        step={1}
                        className="w-full accent-[var(--pn-grafite-900)]"
                        value={draft[id(field)]}
                        onChange={(e) => change(field, e.target.value)}
                      />
                      <output
                        data-testid={`valor-${id(field)}`}
                        className="w-8 text-right text-sm font-medium tabular-nums"
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
