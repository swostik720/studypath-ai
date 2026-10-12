export interface Config {
  port: number;
  mongoUrl: string;
  ragUrl: string;
  ragTimeoutMs: number;
  corsOrigin: string;
  rateLimitPerMinute: number;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  return {
    port: Number(env.PORT ?? 4000),
    mongoUrl: env.MONGO_URL ?? "mongodb://localhost:27017/studypath",
    ragUrl: env.RAG_URL ?? "http://localhost:8000",
    // Local LLMs on CPU can be slow; keep this generous but bounded.
    ragTimeoutMs: Number(env.RAG_TIMEOUT_MS ?? 120_000),
    corsOrigin: env.CORS_ORIGIN ?? "http://localhost:3000",
    rateLimitPerMinute: Number(env.RATE_LIMIT_PER_MINUTE ?? 30),
  };
}
