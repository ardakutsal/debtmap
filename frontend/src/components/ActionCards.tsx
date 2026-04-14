'use client';

type Action = {
  priority: number;
  category: string;
  title: string;
  why: string;
  effort: string;
  score: number;
  files: { path: string; score: number }[];
};

const EFFORT_LABEL: Record<string, string> = { S: 'small', M: 'medium', L: 'large' };

export function ActionCards({ plan }: { plan: Action[] }) {
  if (!plan.length) {
    return (
      <div className="rounded-xl border border-border bg-panel p-6 text-sm text-muted">
        No urgent action items — nice work.
      </div>
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {plan.map((a) => (
        <div key={a.priority} className="rounded-xl border border-border bg-panel p-5 transition hover:border-accent/40">
          <div className="mb-1 flex items-center gap-2">
            <span className="mono rounded-full border border-accent/50 px-2 py-0.5 text-[10px] text-accent">
              #{a.priority}
            </span>
            <span className="mono text-[10px] text-muted">{a.category}</span>
            <span className="ml-auto mono text-xs text-warn">effort · {EFFORT_LABEL[a.effort] ?? a.effort}</span>
          </div>
          <h3 className="text-base font-semibold">{a.title}</h3>
          <p className="mt-2 text-sm text-muted">{a.why}</p>
          <div className="mt-3 space-y-1">
            {a.files.map((f) => (
              <div key={f.path} className="flex items-center justify-between rounded-md bg-panel2 px-2 py-1 text-xs">
                <span className="mono truncate text-muted">{f.path}</span>
                <span className="mono text-accent">{f.score.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
