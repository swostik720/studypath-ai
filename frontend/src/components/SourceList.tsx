import type { Source } from "@/lib/api";

export function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50 text-sm dark:border-slate-700 dark:bg-slate-800/50">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-slate-700 dark:text-slate-200">
        Sources ({sources.length})
      </summary>
      <ol className="space-y-3 px-3 pb-3">
        {sources.map((s, i) => (
          <li key={`${s.url}-${i}`}>
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-blue-700 underline-offset-2 hover:underline dark:text-blue-400"
            >
              [{i + 1}] {s.title}
            </a>
            <span className="ml-2 text-xs text-slate-500">relevance {s.score.toFixed(2)}</span>
            <p className="mt-1 line-clamp-3 text-slate-600 dark:text-slate-300">{s.text}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}
