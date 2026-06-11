'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiUrl } from '@/lib/utils';

export default function LandingPage() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/github\.com\/[^\/]+\/[^\/]+/.test(url)) {
      setError('Enter a GitHub repository URL (e.g. https://github.com/facebook/react)');
      return;
    }
    setSubmitting(true);
    try {
      let resp: Response;
      try {
        resp = await fetch(apiUrl('/analyze'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repo_url: url, branch: 'main' }),
        });
      } catch {
        throw new Error('API unreachable — is the backend running on port 8000?');
      }
      if (resp.status === 429) throw new Error('Rate limit hit — try again in an hour.');
      if (!resp.ok) {
        const payload = await resp.json().catch(() => ({}));
        throw new Error(payload.detail || `API error (${resp.status})`);
      }
      const data = await resp.json();
      router.push(`/results/${data.analysis_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setSubmitting(false);
    }
  }

  return (
    <main className="relative mx-auto flex max-w-6xl flex-col gap-24 px-6 py-16 md:py-24">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="mono text-xl font-bold">
            <span className="text-accent">debt</span>map
          </div>
          <span className="rounded-full border border-border bg-panel px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted">
            v0.1 · MIT
          </span>
        </div>
        <nav className="flex items-center gap-6 text-sm text-muted">
          <a href="https://github.com/ardakutsal/debtmap" className="hover:text-text">GitHub</a>
          <a href="#how" className="hover:text-text">How it works</a>
          <a href="#badge" className="hover:text-text">Badge</a>
        </nav>
      </header>

      <section className="flex flex-col items-center text-center">
        <p className="mono mb-5 rounded-full border border-border bg-panel px-3 py-1 text-xs text-accent">
          for vibe-coded and AI-generated repos
        </p>
        <h1 className="max-w-3xl text-5xl font-semibold leading-tight tracking-tight md:text-6xl">
          Your AI-generated code <br />
          <span className="text-accent">has debt.</span> Find it.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-muted">
          DebtMap scans a GitHub repo for the telltale patterns of AI-era sprawl
          — duplication, silent error swallowing, missing tests, god files — plus
          git-evidence AI provenance, and returns a single score, a file-level
          heatmap, and a prioritized fix list.
        </p>

        <form onSubmit={onSubmit} className="mt-10 w-full max-w-2xl">
          <div className="glow flex items-center gap-2 rounded-xl border border-border bg-panel2 p-2">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="mono flex-1 bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted"
              disabled={submitting}
            />
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-bg transition hover:brightness-110 disabled:opacity-60"
            >
              {submitting ? 'Queuing…' : 'Analyze →'}
            </button>
          </div>
          {error && <p className="mono mt-3 text-sm text-danger">{error}</p>}
          <p className="mt-3 text-xs text-muted">
            Free · No auth required · Up to 500 files per repo · Analysis ~30–60s
          </p>
        </form>

        <div id="badge" className="mono mt-12 flex items-center gap-3 rounded-lg border border-border bg-panel px-4 py-3 text-xs text-muted">
          <span>Example badge:</span>
          <img
            alt="debtmap B · 34"
            src="data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22130%22 height=%2220%22%3E%3Crect width=%2260%22 height=%2220%22 fill=%22%2324292f%22/%3E%3Crect x=%2260%22 width=%2270%22 height=%2220%22 fill=%22%237ec93f%22/%3E%3Ctext x=%2230%22 y=%2214%22 fill=%22%23fff%22 font-family=%22Verdana%22 font-size=%2211%22 text-anchor=%22middle%22%3Edebtmap%3C/text%3E%3Ctext x=%2295%22 y=%2214%22 fill=%22%23fff%22 font-family=%22Verdana%22 font-size=%2211%22 text-anchor=%22middle%22%3EB · 34%3C/text%3E%3C/svg%3E"
          />
          <span>paste the markdown snippet from your results page into your README</span>
        </div>
      </section>

      <section id="how" className="grid gap-4 md:grid-cols-3">
        {[
          {
            n: '01',
            title: 'Paste a GitHub URL',
            body: 'Public repo or your own with a token. We clone shallow, extract AST, never execute code.',
          },
          {
            n: '02',
            title: 'Eight analyzers run',
            body: 'Error handling, duplication, contracts, tests, comments, imports, churn — plus git-metadata AI provenance.',
          },
          {
            n: '03',
            title: 'Get your DebtScore',
            body: 'One number A–F, file treemap, action plan, and a README badge you can embed in minutes.',
          },
        ].map((step) => (
          <div key={step.n} className="rounded-2xl border border-border bg-panel p-6 transition hover:border-accent/40">
            <div className="mono text-xs text-accent">{step.n}</div>
            <div className="mt-2 text-lg font-semibold">{step.title}</div>
            <p className="mt-2 text-sm text-muted">{step.body}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        {[
          ['Error Handling', '25%'],
          ['Duplication', '20%'],
          ['Arch. Contracts', '20%'],
          ['Test Coverage', '10%'],
          ['Comment Patterns', '10%'],
          ['Dependency Graph', '10%'],
          ['Code Churn', '5%'],
          ['AI Provenance', 'git evidence'],
        ].map(([label, w]) => (
          <div key={label} className="rounded-xl border border-border bg-panel2 p-4">
            <div className="text-sm font-medium">{label}</div>
            <div className="mono mt-1 text-xs text-muted">weight {w}</div>
          </div>
        ))}
      </section>

      <footer className="mt-8 border-t border-border pt-6 text-xs text-muted">
        MIT-licensed · self-hostable · built for AI-era debt.
      </footer>
    </main>
  );
}
