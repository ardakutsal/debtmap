'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { apiUrl, gradeColor } from '@/lib/utils';

type Side = {
  input: string;
  status: 'idle' | 'loading' | 'done' | 'error';
  error?: string;
  data?: any;
};

const ANALYZER_LABELS: Record<string, string> = {
  error_handling: 'Errors',
  duplication: 'Duplication',
  architectural_contracts: 'Contracts',
  test_coverage: 'Tests',
  comment_patterns: 'Comments',
  dependency_graph: 'Imports',
  code_churn: 'Churn',
  style_homogeneity: 'Style (info)',
};

async function runScan(repoInput: string): Promise<any> {
  const url = repoInput.includes('github.com') ? repoInput : `https://github.com/${repoInput}`;
  const resp = await fetch(apiUrl('/analyze'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: url, branch: 'main' }),
  });
  if (!resp.ok) {
    const payload = await resp.json().catch(() => ({}));
    throw new Error(payload.detail || `API error (${resp.status})`);
  }
  const { analysis_id } = await resp.json();
  for (let i = 0; i < 60; i++) {
    const r = await fetch(apiUrl(`/results/${analysis_id}`));
    const data = await r.json();
    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error(data.error || 'Analysis failed');
    await new Promise((res) => setTimeout(res, 3000));
  }
  throw new Error('Timed out waiting for analysis');
}

function ComparePageInner() {
  const params = useSearchParams();
  const [a, setA] = useState<Side>({ input: params?.get('a') ?? '', status: 'idle' });
  const [b, setB] = useState<Side>({ input: params?.get('b') ?? '', status: 'idle' });

  const run = useCallback(async () => {
    for (const [side, set] of [
      [a, setA],
      [b, setB],
    ] as const) {
      if (!side.input.trim()) continue;
      set((s) => ({ ...s, status: 'loading', error: undefined }));
      runScan(side.input.trim())
        .then((data) => set((s) => ({ ...s, status: 'done', data })))
        .catch((err) => set((s) => ({ ...s, status: 'error', error: String(err.message || err) })));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a.input, b.input]);

  useEffect(() => {
    if (params?.get('a') && params?.get('b')) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8">
        <Link href="/" className="mono text-xs text-muted hover:text-accent">
          ← debtmap
        </Link>
        <h1 className="mt-2 text-3xl font-semibold">Compare two repositories</h1>
        <p className="mt-1 text-sm text-muted">
          Side-by-side DebtScore, AI provenance, and category breakdown. Recently scanned repos
          return instantly from cache.
        </p>
      </header>

      <div className="mb-8 grid gap-4 md:grid-cols-[1fr_1fr_auto]">
        {(
          [
            [a, setA, 'owner/repo or GitHub URL'],
            [b, setB, 'owner/repo or GitHub URL'],
          ] as const
        ).map(([side, set, placeholder], i) => (
          <input
            key={i}
            value={side.input}
            onChange={(e) => set((s) => ({ ...s, input: e.target.value }))}
            placeholder={placeholder}
            className="mono rounded-xl border border-border bg-panel2 px-4 py-3 text-sm outline-none placeholder:text-muted"
          />
        ))}
        <button
          onClick={run}
          disabled={a.status === 'loading' || b.status === 'loading' || !a.input || !b.input}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-bg transition hover:brightness-110 disabled:opacity-60"
        >
          Compare
        </button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {[a, b].map((side, i) => (
          <CompareCard key={i} side={side} />
        ))}
      </div>
    </main>
  );
}

function CompareCard({ side }: { side: Side }) {
  if (side.status === 'idle')
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-dashed border-border text-sm text-muted">
        Enter a repository above
      </div>
    );
  if (side.status === 'loading')
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-border bg-panel text-sm text-muted">
        <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-accent" /> Scanning…
      </div>
    );
  if (side.status === 'error')
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-danger/40 bg-panel p-6 text-center text-sm text-danger">
        {side.error}
      </div>
    );

  const d = side.data;
  const color = gradeColor(d.debt_score);
  return (
    <div className="rounded-2xl border border-border bg-panel p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="mono text-lg font-semibold">
          <span className="text-accent">{d.owner}</span>
          <span className="text-muted">/</span>
          {d.repo}
        </div>
        <span
          className="rounded-lg px-3 py-1 text-sm font-bold"
          style={{ background: color, color: '#0f1117' }}
        >
          {d.grade} · {Math.round(d.debt_score)}
        </span>
      </div>
      <p className="mono mb-4 text-xs text-muted">
        {d.files_analyzed} files · AI commits {d.ai_generated_pct ?? 0}%
        {d.provenance?.agents?.[0] ? ` (${d.provenance.agents[0].name})` : ''}
      </p>
      <div className="space-y-2">
        {Object.entries(ANALYZER_LABELS).map(([key, label]) => {
          const v = d.analyzers?.[key];
          if (!v || v.skipped) return null;
          return (
            <div key={key}>
              <div className="mb-0.5 flex justify-between text-xs">
                <span className="text-muted">{label}</span>
                <span className="mono">{Math.round(v.score)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-panel2">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.min(100, v.score)}%`, background: gradeColor(v.score) }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <Link
        href={`/results/${d.analysis_id}`}
        className="mono mt-4 inline-block text-xs text-accent hover:underline"
      >
        full report →
      </Link>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={null}>
      <ComparePageInner />
    </Suspense>
  );
}
