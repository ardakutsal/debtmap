'use client';

import Link from 'next/link';
import useSWR from 'swr';
import { apiUrl, gradeColor } from '@/lib/utils';

type Entry = {
  owner: string;
  repo: string;
  debt_score: number;
  grade: string;
  ai_generated_pct: number | null;
  files_analyzed: number;
  analysis_id: string;
  updated_at: string;
};

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function LeaderboardPage() {
  const { data, error } = useSWR<{ entries: Entry[] }>(apiUrl('/leaderboard'), fetcher);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="mb-8">
        <Link href="/" className="mono text-xs text-muted hover:text-accent">
          ← debtmap
        </Link>
        <h1 className="mt-2 text-3xl font-semibold">Leaderboard</h1>
        <p className="mt-1 text-sm text-muted">
          Latest scan per repository, best DebtScore first. Scan any public repo to put it here.
        </p>
      </header>

      {error && <p className="mono text-sm text-danger">Failed to load leaderboard.</p>}
      {!data && !error && <p className="mono text-sm text-muted">Loading…</p>}

      {data && data.entries.length === 0 && (
        <p className="text-sm text-muted">No scans yet — be the first.</p>
      )}

      {data && data.entries.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-panel text-left text-xs uppercase tracking-wider text-muted">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Repository</th>
                <th className="px-4 py-3 text-right">Score</th>
                <th className="px-4 py-3 text-right">Grade</th>
                <th className="px-4 py-3 text-right">AI commits</th>
                <th className="px-4 py-3 text-right">Files</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((e, i) => (
                <tr key={`${e.owner}/${e.repo}`} className="border-t border-border/60 hover:bg-panel">
                  <td className="mono px-4 py-3 text-muted">{i + 1}</td>
                  <td className="px-4 py-3">
                    <Link href={`/results/${e.analysis_id}`} className="mono hover:text-accent">
                      <span className="text-accent">{e.owner}</span>
                      <span className="text-muted">/</span>
                      {e.repo}
                    </Link>
                  </td>
                  <td className="mono px-4 py-3 text-right">{e.debt_score?.toFixed(1)}</td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className="mono inline-block w-8 rounded px-1.5 py-0.5 text-center text-xs font-bold"
                      style={{ background: gradeColor(e.debt_score), color: '#0f1117' }}
                    >
                      {e.grade}
                    </span>
                  </td>
                  <td className="mono px-4 py-3 text-right text-muted">
                    {e.ai_generated_pct != null ? `${e.ai_generated_pct}%` : '—'}
                  </td>
                  <td className="mono px-4 py-3 text-right text-muted">{e.files_analyzed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
