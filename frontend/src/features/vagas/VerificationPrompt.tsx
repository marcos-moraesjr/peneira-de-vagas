import { useConfirmVerification, useVerification } from "../../api/hooks";
import { ErrorBox } from "../../components/ErrorBox";
import { buttonPrimary } from "../../components/ui";
import { sourceLabel } from "../../lib/failures";

/** Fonte parada num CAPTCHA/Cloudflare: o usuário conclui a verificação no Chrome dedicado e confirma aqui. */
export function VerificationPrompt({ running }: { running: boolean }) {
  const verification = useVerification(running);
  const confirm = useConfirmVerification();
  const fontes = running ? (verification.data?.fontes ?? []) : [];
  if (fontes.length === 0) return null;
  return (
    <div className="space-y-2">
      {fontes.map((fonte) => (
        <div key={fonte} role="alert" className="flex flex-wrap items-center gap-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <span>
            {sourceLabel(fonte)} pediu uma verificação. Conclua-a à mão no Chrome dedicado e confirme: a busca segue de onde parou.
          </span>
          <button type="button" className={buttonPrimary} disabled={confirm.isPending} onClick={() => confirm.mutate(fonte)}>
            Já concluí a verificação
          </button>
        </div>
      ))}
      {confirm.error && <ErrorBox message={confirm.error.message} />}
    </div>
  );
}
