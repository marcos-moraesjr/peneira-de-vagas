import { FAILURE_REASONS, describeFailure, sourceLabel } from "./failures";

describe("describeFailure", () => {
  it("traduz o motivo em frase simples e ação", () => {
    const captcha = describeFailure("linkedin", "captcha");
    expect(captcha.message).toContain("verificação de segurança");
    expect(captcha.action).toContain("Chrome dedicado");
  });

  it("cobre todos os motivos padronizados", () => {
    const motivos = [
      "captcha", "login", "cloudflare", "seletor_nao_encontrado", "zero_resultados",
      "cdp_indisponivel", "http_erro", "interrompida", "erro_interno",
    ];
    for (const motivo of motivos) {
      const text = describeFailure("indeed", motivo);
      expect(text.message.length).toBeGreaterThan(5);
      expect(text.action.length).toBeGreaterThan(5);
    }
  });

  it("motivo desconhecido não quebra e mostra o valor", () => {
    expect(describeFailure("gupy", "novo_motivo").message).toContain("novo_motivo");
  });

  it("nunca apresenta zero resultados como sucesso", () => {
    expect(describeFailure("gupy", "zero_resultados").message).toMatch(/nenhuma vaga/i);
  });
});

describe("sourceLabel", () => {
  it("usa o nome de exibição de cada fonte", () => {
    expect(sourceLabel("linkedin")).toBe("LinkedIn");
    expect(sourceLabel("indeed")).toBe("Indeed");
    expect(sourceLabel("gupy")).toBe("Gupy");
    expect(sourceLabel("outra")).toBe("outra");
  });
});

describe("FAILURE_REASONS", () => {
  it("lista todos os motivos padronizados, cada um com texto", () => {
    expect(FAILURE_REASONS).toHaveLength(9);
    for (const reason of FAILURE_REASONS) expect(describeFailure("gupy", reason).message).not.toMatch(/^falhou \(/);
  });
});
