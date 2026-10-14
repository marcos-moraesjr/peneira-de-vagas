import { formatDate, formatDateTime, formatDuration, timeAgo } from "./format";

describe("timeAgo", () => {
  const now = new Date("2026-10-14T12:00:00Z");

  it("descreve minutos, horas e dias em pt-BR", () => {
    expect(timeAgo("2026-10-14T11:55:00Z", now)).toBe("há 5 minutos");
    expect(timeAgo("2026-10-14T09:00:00Z", now)).toBe("há 3 horas");
    expect(timeAgo("2026-10-12T12:00:00Z", now)).toBe("há 2 dias");
  });

  it("menos de um minuto vira 'agora'", () => {
    expect(timeAgo("2026-10-14T11:59:40Z", now)).toBe("agora");
  });
});

describe("formatDuration", () => {
  it("formata segundos e minutos", () => {
    expect(formatDuration("2026-10-14T12:00:00Z", "2026-10-14T12:00:42Z")).toBe("42 s");
    expect(formatDuration("2026-10-14T12:00:00Z", "2026-10-14T12:03:05Z")).toBe("3 min 5 s");
  });

  it("sem fim (em andamento) devolve traço", () => {
    expect(formatDuration("2026-10-14T12:00:00Z", null)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("usa dia/mês/ano em pt-BR", () => {
    expect(formatDateTime("2026-10-14T15:30:00Z")).toMatch(/14\/10\/2026/);
  });
});

describe("formatDate", () => {
  it("formata AAAA-MM-DD como dia/mês/ano sem deslocar por fuso horário", () => {
    expect(formatDate("2026-10-14")).toBe("14/10/2026");
    expect(formatDate("2026-01-01")).toBe("01/01/2026");
  });
});
