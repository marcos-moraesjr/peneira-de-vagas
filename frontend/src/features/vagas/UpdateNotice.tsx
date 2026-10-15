import { useAtualizacao } from "../../api/hooks";

/** Aviso de versão nova do app (traz os scanners corrigidos). Só exibe o que a API decidiu; sem aviso, não aparece. */
export function UpdateNotice() {
  const update = useAtualizacao().data;
  if (update?.estado !== "disponivel") return null;
  return (
    <p role="note" className="rounded-painel border border-l-[3px] border-sinal bg-sinal-bg px-3 py-2 text-xs text-sinal-fg">
      <strong>Há uma versão nova da Peneira de Vagas ({update.disponivel}).</strong> Você usa a {update.instalada}; as versões
      novas trazem os scanners corrigidos quando uma plataforma muda. Para atualizar, feche este programa (Ctrl+C no terminal) e
      rode <code className="font-semibold">{update.comando}</code>. Seus dados são mantidos.
    </p>
  );
}
