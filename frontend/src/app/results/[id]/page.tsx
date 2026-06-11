'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import useSWR from 'swr';
import { API_BASE, apiUrl } from '@/lib/utils';
import { ScoreGauge } from '@/components/ScoreGauge';
import { CategoryPie } from '@/components/CategoryPie';
import { FileTreemap } from '@/components/FileTreemap';
import { ActionCards } from '@/components/ActionCards';
import { FileTable } from '@/components/FileTable';
import { AnalyzerBars } from '@/components/AnalyzerBars';
import { BadgeSnippet } from '@/components/BadgeSnippet';

const fetcher = async (url: string) => {
  let resp: Response;
  try {
    resp = await fetch(url);
  } catch (err) {
    throw new Error('API unreachable — is the backend running on port 8000?');
  }
  if (resp.status === 404) throw new Error('Analysis not found. It may have expired or the ID is wrong.');
  if (!resp.ok) throw new Error(`API error (${resp.status})`);
  return resp.json();
};

export default function ResultsPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const { data, error } = useSWR(id ? apiUrl(`/results/${id}`) : null, fetcher, {
    refreshInterval: (d) => (d?.status === 'completed' || d?.status === 'failed' ? 0 : 2000),
    shouldRetryOnError: (err) => !String(err?.message || '').includes('not found'),
    errorRetryInterval: 3000,
  });

  if (error) return <ErrorState message={error instanceof Error ? error.message : String(error)} />;
  if (!data) return <Running message="Loading…" pct={0} />;
  if (data.status === 'failed') return <ErrorState message={data.error || 'Analysis failed'} />;
  if (data.status !== 'completed') return <Running message={data.current_step} pct={data.progress_pct ?? 0} />;

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="mb-8 flex items-start justify-between">
        <div>
          <Link href="/" className="mono text-xs text-muted hover:text-accent">
            ← new scan
          </Link>
          <h1 className="mt-2 text-3xl font-semibold">
            <span className="mono text-accent">{data.owner}</span>
            <span className="text-muted">/</span>
            <span className="mono">{data.repo}</span>
          </h1>
          <p className="mono mt-1 text-xs text-muted">
            branch · {data.branch} · {data.files_analyzed} files · {data.elapsed_seconds}s
          </p>
        </div>
        <ProvenanceChip provenance={data.provenance} />
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Panel title="DebtScore">
              <ScoreGauge score={data.debt_score} grade={data.grade} />
            </Panel>
            <Panel title="Category breakdown">
              <CategoryPie analyzers={data.analyzers} />
            </Panel>
          </div>

          <Panel title="File heatmap · box size = LOC · color = debt">
            <FileTreemap files={data.file_summary || []} />
          </Panel>

          <Panel title="Top debt-heavy files">
            <FileTable rows={data.file_summary || []} />
          </Panel>

          <div>
            <h2 className="mb-3 text-lg font-semibold">Action plan</h2>
            {(data.action_plan?.length ?? 0) > 0 ? (
              <ActionCards plan={data.action_plan} />
            ) : (
              <div className="rounded-2xl border border-border bg-panel p-5 text-sm text-muted">
                No category crossed the action threshold — debt is evenly low across the repo.
                Check the file table above for local hotspots.
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-6">
          <Panel title="Analyzer scores">
            <AnalyzerBars analyzers={data.analyzers} />
          </Panel>
          <Panel title="Repo stats">
            <dl className="space-y-2 text-sm">
              <Stat k="Files analyzed" v={data.files_analyzed} />
              <Stat k="Skipped (too large)" v={data.files_skipped_too_large ?? 0} />
              <Stat k="Elapsed" v={`${data.elapsed_seconds}s`} />
            </dl>
          </Panel>
          {data.provenance && <ProvenancePanel provenance={data.provenance} />}
          <Panel title="Embed badge">
            <BadgeSnippet owner={data.owner} repo={data.repo} apiBase={API_BASE} analysisId={id ?? ''} />
          </Panel>
        </aside>
      </div>
    </main>
  );
}

type Provenance = {
  commits_sampled: number;
  history_truncated?: boolean;
  ai_commits: number;
  ai_commit_pct: number;
  automation_commits: number;
  agents: { name: string; commits: number }[];
  human_authors: number;
  velocity: { peak_commits_24h: number; flag: string };
  likely_ai_assisted: boolean;
  confidence: string;
  assessment: string;
};

function ProvenanceChip({ provenance }: { provenance?: Provenance | null }) {
  if (!provenance) {
    return (
      <div className="mono rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
        AI provenance · no data
      </div>
    );
  }
  let label: React.ReactNode;
  if (provenance.ai_commit_pct > 0) {
    label = (
      <>
        AI commits · <span className="text-accent">{provenance.ai_commit_pct}%</span>
        {provenance.agents[0] ? <span className="text-muted"> · {provenance.agents[0].name}</span> : null}
      </>
    );
  } else if (provenance.likely_ai_assisted) {
    label = <>AI-likely velocity · <span className="text-accent">no signatures</span></>;
  } else {
    label = <>No AI signatures found</>;
  }
  return (
    <div
      className="mono rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted"
      title={provenance.assessment}
    >
      {label}
    </div>
  );
}

function ProvenancePanel({ provenance }: { provenance: Provenance }) {
  return (
    <Panel title="AI provenance · git evidence">
      <dl className="space-y-2 text-sm">
        <Stat k="Commits sampled" v={`${provenance.commits_sampled}${provenance.history_truncated ? '+' : ''}`} />
        <Stat k="AI-signed commits" v={`${provenance.ai_commit_pct}%`} />
        {provenance.agents.slice(0, 3).map((a) => (
          <Stat key={a.name} k={a.name} v={a.commits} />
        ))}
        {provenance.automation_commits > 0 && <Stat k="Automation bots" v={provenance.automation_commits} />}
        <Stat k="Human authors" v={provenance.human_authors} />
        <Stat k="Peak commits / 24h" v={provenance.velocity.peak_commits_24h} />
      </dl>
      <p className="mt-3 text-xs leading-relaxed text-muted">{provenance.assessment}</p>
    </Panel>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-panel p-5">
      <h2 className="mb-4 text-xs uppercase tracking-wider text-muted">{title}</h2>
      {children}
    </section>
  );
}

function Stat({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 py-1 last:border-0">
      <dt className="text-muted">{k}</dt>
      <dd className="mono">{v}</dd>
    </div>
  );
}

function Running({ message, pct }: { message: string; pct: number }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-6 text-center">
      <div className="mono mb-2 text-xs text-accent">Analyzing…</div>
      <h1 className="text-2xl font-semibold">{message || 'Starting analysis'}</h1>
      <div className="mt-6 h-2 w-full max-w-sm rounded-full bg-panel2">
        <div
          className="h-full rounded-full bg-accent transition-all duration-700"
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
      <div className="mono mt-2 text-xs text-muted">{pct}%</div>
    </main>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-6 text-center">
      <div className="mono mb-2 text-xs text-danger">Analysis failed</div>
      <pre className="mono max-w-full overflow-auto rounded-lg border border-danger/40 bg-panel p-4 text-left text-xs text-danger/90">
        {message}
      </pre>
      <Link href="/" className="mono mt-6 text-sm text-accent hover:underline">
        ← try another repo
      </Link>
    </main>
  );
}
