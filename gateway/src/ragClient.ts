import { z } from "zod";

export const ragResponseSchema = z.object({
  answer: z.string(),
  answered: z.boolean(),
  top_score: z.number().optional(),
  sources: z.array(
    z.object({ title: z.string(), url: z.string(), text: z.string(), score: z.number() }),
  ),
});
export type RagResponse = z.infer<typeof ragResponseSchema>;

export interface RagClient {
  ask(question: string): Promise<RagResponse>;
}

export class RagUnavailableError extends Error {}

export class HttpRagClient implements RagClient {
  constructor(
    private readonly baseUrl: string,
    private readonly timeoutMs: number,
  ) {}

  async ask(question: string): Promise<RagResponse> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (err) {
      throw new RagUnavailableError(`RAG service unreachable: ${(err as Error).message}`);
    }
    if (!res.ok) throw new RagUnavailableError(`RAG service returned HTTP ${res.status}`);
    const parsed = ragResponseSchema.safeParse(await res.json());
    if (!parsed.success) throw new RagUnavailableError("RAG service returned an unexpected payload");
    return parsed.data;
  }
}
