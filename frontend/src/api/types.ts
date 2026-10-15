import type { components } from "./schema";

type Schemas = components["schemas"];

export type Job = Schemas["JobOut"];
export type JobsPage = Schemas["JobsPage"];
export type Run = Schemas["RunOut"];
export type RunSource = Schemas["RunSourceOut"];
export type Keyword = Schemas["KeywordOut"];
export type Conjunto = Schemas["ConjuntoOut"];
export type Config = Schemas["ConfigOut"];
export type Health = Schemas["HealthOut"];

export type KeywordType = "busca" | "ranking" | "exclusao";
export type SeenFilter = "novas" | "todas";
export type Scanner = Schemas["ScannerOut"];
export type BrowserStatus = Schemas["BrowserOut"];
