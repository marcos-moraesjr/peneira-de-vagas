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
  kind: "number" | "text" | "slider" | "modalidade" | "localidades";
  step?: string;
  dica?: string;
};

const GROUPS: { titulo: string; fields: Field[] }[] = [
  {
    titulo: "Busca",
    fields: [
      {
        section: "busca",
        key: "localidades",
        label: "Localidades",
        kind: "localidades",
        dica: "Cidades ou estados (ex.: Campinas, SP · Minas Gerais). Uma busca por palavra-chave e localidade, no LinkedIn e no Indeed. Nenhuma = sem filtro de local.",
      },
      {
        section: "busca",
        key: "modalidade",
        label: "Modalidade",
        kind: "modalidade",
      },
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
        key: "max_paginas_detalhe",
        label: "Páginas de detalhe por execução",
        kind: "number",
      },
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
const MODALIDADES = [
  ["remoto", "Remoto"],
  ["hibrido", "Híbrido"],
  ["presencial", "Presencial"],
];

type Draft = Record<string, string>;
const SLIDER_MAX = 10;
const LOCALIDADE_SEP = "\n";
const id = (field: Field) => `${field.section}.${field.key}`;
const valueOf = (config: Config, field: Field) => {
  const value = (config[field.section] as Record<string, unknown>)[field.key];
  if (Array.isArray(value)) return value.join(field.kind === "localidades" ? LOCALIDADE_SEP : ",");
  return String(value);
};

function toDraft(config: Config): Draft {
  return Object.fromEntries(FIELDS.map((field) => [id(field), valueOf(config, field)]));
}

function toConfig(draft: Draft): Config {
  const config: Record<string, Record<string, unknown>> = {};
  for (const field of FIELDS) {
    const raw = draft[id(field)];
    config[field.section] ??= {};
    config[field.section][field.key] =
      field.kind === "modalidade"
        ? raw
          ? raw.split(",")
          : []
        : field.kind === "localidades"
          ? raw
            ? raw.split(LOCALIDADE_SEP)
            : []
          : field.kind === "text"
          ? raw
          : raw === ""
            ? null
            : Number(raw);
  }
  return config as unknown as Config;
}

function ConfigForm({ config }: { config: Config }) {
  const save = useSaveConfig();
  const [draft, setDraft] = useState<Draft>(() => toDraft(config));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [entry, setEntry] = useState("");
  const dirty = FIELDS.some((field) => draft[id(field)] !== valueOf(config, field));

  function change(field: Field, value: string) {
    setDraft({ ...draft, [id(field)]: value });
    setSaved(false);
  }

  function toggle(field: Field, value: string) {
    const current = draft[id(field)].split(",");
    const next = MODALIDADES.map(([name]) => name).filter((name) =>
      name === value ? !current.includes(name) : current.includes(name),
    );
    change(field, next.join(","));
  }

  function addLocalidade(field: Field) {
    const name = entry.trim();
    if (!name) return;
    const current = draft[id(field)];
    change(field, current ? `${current}${LOCALIDADE_SEP}${name}` : name);
    setEntry("");
  }

  function removeLocalidade(field: Field, name: string) {
    change(
      field,
      draft[id(field)]
        .split(LOCALIDADE_SEP)
        .filter((item) => item !== name)
        .join(LOCALIDADE_SEP),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    save.mutate(toConfig(draft), {
      onSuccess: (result) => {
        setDraft(toDraft(result));
        setSaved(true);
      },
      onError: (failure) => setError(failure.message),
    });
  }

  function discard() {
    setDraft(toDraft(config));
    setEntry("");
    setError(null);
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {GROUPS.map((group) => (
        <section key={group.titulo} className={card} aria-label={group.titulo}>
          <h2 className="mb-3 text-sm font-semibold text-slate-800">{group.titulo}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {group.fields.map((field) => (
              <div key={id(field)} className="flex flex-col gap-1">
                {field.kind === "localidades" ? (
                  <div className="flex flex-col gap-2 text-sm text-slate-700 sm:col-span-2">
                    <label htmlFor={id(field)}>{field.label}</label>
                    <div className="flex gap-2">
                      <input
                        id={id(field)}
                        className={`${inputClass} w-full`}
                        value={entry}
                        onChange={(e) => setEntry(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addLocalidade(field);
                          }
                        }}
                      />
                      <button type="button" className={buttonSecondary} onClick={() => addLocalidade(field)}>
                        Adicionar localidade
                      </button>
                    </div>
                    {draft[id(field)] && (
                      <ul className="flex flex-wrap gap-2">
                        {draft[id(field)].split(LOCALIDADE_SEP).map((name) => (
                          <li key={name} className="flex items-center gap-1 rounded-full bg-slate-100 py-1 pl-3 pr-1">
                            {name}
                            <button
                              type="button"
                              aria-label={`Remover ${name}`}
                              className="rounded-full px-2 text-slate-500 hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-sky-600"
                              onClick={() => removeLocalidade(field, name)}
                            >
                              ✕
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : field.kind === "modalidade" ? (
                  <fieldset className="flex flex-col gap-1 text-sm text-slate-700">
                    <legend className="mb-1">{field.label}</legend>
                    <div className="flex flex-wrap gap-4">
                      {MODALIDADES.map(([value, label]) => (
                        <label key={value} className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={draft[id(field)].split(",").includes(value)}
                            onChange={() => toggle(field, value)}
                          />
                          {label}
                        </label>
                      ))}
                    </div>
                    <span className="text-xs text-slate-500">Nenhuma marcada = todas as modalidades.</span>
                  </fieldset>
                ) : field.kind === "slider" ? (
                  <>
                    <label htmlFor={id(field)} className="text-sm text-slate-700">
                      {field.label}
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        id={id(field)}
                        type="range"
                        min={0}
                        max={Math.max(SLIDER_MAX, Number(valueOf(config, field)), Number(draft[id(field)]))}
                        step={1}
                        className="w-full accent-slate-900"
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
                  <label className="flex flex-col gap-1 text-sm text-slate-700">
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
                {field.dica && <span className="text-xs text-slate-500">{field.dica}</span>}
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
        {saved && <span className="text-sm text-emerald-700">Configuração salva. Vale a partir da próxima busca.</span>}
      </div>
    </form>
  );
}

export function ConfigPage() {
  const config = useConfig();
  if (config.isError) return <ErrorBox message="Não foi possível carregar a configuração." />;
  if (!config.data) return <p className="text-sm text-slate-500">Carregando…</p>;
  return <ConfigForm config={config.data} />;
}
