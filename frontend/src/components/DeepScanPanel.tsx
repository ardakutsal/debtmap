'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/lib/utils';

type Risk = { title: string; severity: 'high' | 'medium' | 'low'; files: string[]; why: string; fix: string };
type Memo = { headline: string; overall_assessment: string; risks: Risk[]; quick_wins: string[] };
type FileFinding = { title: string; severity: string; evidence: string; fix: string };
type FileReview = { path: string; verdict: string; static_signal_correct: boolean; findings: FileFinding[] };

type DeepScanState = {
  status: 'none' | 'queued' | 'running' | 'completed' | 'failed' | 'error';
  memo?: Memo;
  file_reviews?: FileReview[];
  error?: string | null;
  detail?: string;
};

const SEVERITY_COLOR: Record<string, string> = {
  high: '#ff6b6b',
  medium: '#ffd06b',
  low: '#8fa3ff',
};

export function DeepScanPanel({ analysisId }: { analysisId: string }) {
  const [state, setState] = useState<DeepScanState>({ status: 'none' });
  const [starting, setStarting] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl(`/results/${analysisId}/deep-scan`));
      if (resp.status === 404) {
        setState({ status: 'none' });
        return 'none';
      }
      const data = await resp.json();
      setState({ ...data, status: data.status });
      return data.status as string;
    } catch {
      return 'none';
    }
  }, [analysisId]);

  useEffect(() => {
    fetchStatus();
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [fetchStatus]);

  useEffect(() => {
    if (state.status === 'queued' || state.status === 'running') {
      if (!timer.current) {
        timer.current = setInterval(async () => {
          const s = await fetchStatus();
          if (s !== 'queued' && s !== 'running' && timer.current) {
            clearInterval(timer.current);
            timer.current = null;
          }
        }, 4000);
      }
    }
  }, [state.status, fetchStatus]);

  async function start() {
    setStarting(true);
    try {
      const resp = await fetch(apiUrl(`/results/${analysisId}/deep-scan`), { method: 'POST' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setState({ status: 'error', detail: data.detail || `Error ${resp.status}` });
        return;
      }
      setState({ status: data.status ?? 'queued' });
    } finally {
      setStarting(false);
    }
  }

  return (
    <section className="rounded-2xl border border-accent/30 bg-panel p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-wider text-muted">
          Deep Scan · AI architect review
        </h2>
        <span className="mono rounded-full border border-border bg-panel2 px-2 py-0.5 text-[10px] text-muted">
          Claude
        </span>
      </div>

      {state.status === 'none' && (
        <div>
          <p className="mb-3 text-sm text-muted">
            A principal-engineer-style review of the worst files: which static flags are real,
            which are noise, and the systemic risks behind them.
          </p>
          <button
            onClick={start}
            disabled={starting}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-bg transition hover:brightness-110 disabled:opacity-60"
          >
            {starting ? 'Starting…' : 'Run Deep Scan (~1 min)'}
          </button>
        </div>
      )}

      {(state.status === 'queued' || state.status === 'running') && (
        <div className="flex items-center gap-3 text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
          Reviewing the top debt files with Claude — this takes about a minute…
        </div>
      )}

      {state.status === 'error' && (
        <p className="mono text-sm text-danger">{state.detail}</p>
      )}

      {state.status === 'failed' && (
        <p className="mono text-sm text-danger">Deep scan failed: {state.error || 'unknown error'}</p>
      )}

      {state.status === 'completed' && state.memo && (
        <div className="space-y-4">
          <p className="text-lg font-semibold leading-snug">“{state.memo.headline}”</p>
          <p className="text-sm leading-relaxed text-muted">{state.memo.overall_assessment}</p>

          <div className="space-y-3">
            {state.memo.risks.map((r) => (
              <div key={r.title} className="rounded-xl border border-border bg-panel2 p-4">
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: SEVERITY_COLOR[r.severity] ?? '#5c6773' }}
                  />
                  <span className="text-sm font-semibold">{r.title}</span>
                  <span className="mono ml-auto text-[10px] uppercase text-muted">{r.severity}</span>
                </div>
                <p className="text-xs leading-relaxed text-muted">{r.why}</p>
                <p className="mt-1 text-xs leading-relaxed">
                  <span className="text-accent">Fix:</span> {r.fix}
                </p>
                {r.files.length > 0 && (
                  <p className="mono mt-2 text-[10px] text-muted">{r.files.join(' · ')}</p>
                )}
              </div>
            ))}
          </div>

          {state.memo.quick_wins.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs uppercase tracking-wider text-muted">Quick wins</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-muted">
                {state.memo.quick_wins.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {state.file_reviews && state.file_reviews.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted hover:text-text">
                Per-file reviews ({state.file_reviews.length})
              </summary>
              <div className="mt-2 space-y-2">
                {state.file_reviews.map((fr) => (
                  <div key={fr.path} className="rounded-lg border border-border/60 bg-panel2 p-3">
                    <p className="mono text-xs text-accent">{fr.path}</p>
                    <p className="mt-1 text-xs text-muted">
                      {fr.verdict}
                      {!fr.static_signal_correct && (
                        <span className="ml-2 rounded bg-panel px-1.5 py-0.5 text-[10px] uppercase">
                          static flag judged noise
                        </span>
                      )}
                    </p>
                    {fr.findings.map((f) => (
                      <p key={f.title} className="mt-1 text-xs">
                        <span style={{ color: SEVERITY_COLOR[f.severity] ?? '#9aa3b5' }}>{f.title}:</span>{' '}
                        <span className="text-muted">{f.fix}</span>
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
