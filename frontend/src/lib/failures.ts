const LABELS: Record<string, string> = { linkedin: "LinkedIn", indeed: "Indeed", gupy: "Gupy" };

/** Plataformas de busca, na ordem em que aparecem na tela. */
export const SOURCES = ["linkedin", "indeed", "gupy"];

export function sourceLabel(fonte: string): string {
  return LABELS[fonte] ?? fonte;
}

const TEXTS: Record<string, { message: string; action: string }> = {
  captcha: {
    message: "pediu uma verificação de segurança (CAPTCHA).",
    action: "Abra o Chrome dedicado, resolva a verificação à mão e busque de novo.",
  },
  login: {
    message: "a sessão está deslogada.",
    action: "Faça login no Chrome dedicado e busque de novo.",
  },
  cloudflare: {
    message: "bloqueou com verificação anti-bot (Cloudflare).",
    action: "Abra o Chrome dedicado, conclua a verificação à mão e tente mais tarde.",
  },
  seletor_nao_encontrado: {
    message: "o layout do site mudou e as vagas não foram encontradas na página.",
    action: "Os seletores precisam ser atualizados no código.",
  },
  zero_resultados: {
    message: "nenhuma vaga retornada pela fonte.",
    action: "Pode ser falta de vagas, bloqueio silencioso ou mudança no site; confira abrindo a busca à mão.",
  },
  cdp_indisponivel: {
    message: "o Chrome dedicado não foi encontrado.",
    action: "Abra-o com scripts/chrome-dedicado.ps1 e busque de novo.",
  },
  http_erro: {
    message: "a fonte não respondeu como esperado.",
    action: "Tente novamente em alguns minutos.",
  },
  interrompida: {
    message: "a busca foi interrompida (o aplicativo foi fechado).",
    action: "Busque de novo.",
  },
  erro_interno: {
    message: "erro inesperado ao ler a fonte.",
    action: "Veja o detalhe e o log em logs/peneira-de-vagas.log.",
  },
};

/** Motivo padronizado da API → frase simples + ação para o usuário. */
export function describeFailure(_fonte: string, motivo: string): { message: string; action: string } {
  return TEXTS[motivo] ?? { message: `falhou (${motivo}).`, action: "Veja o log em logs/peneira-de-vagas.log." };
}

/** Todos os motivos padronizados de falha de fonte, na ordem em que a página Como usar os explica. */
export const FAILURE_REASONS = Object.keys(TEXTS);
