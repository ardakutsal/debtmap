'use client';

import { useState } from 'react';

export function BadgeSnippet({ owner, repo, apiBase }: { owner: string; repo: string; apiBase: string }) {
  const [copied, setCopied] = useState<string | null>(null);
  const url = `${apiBase}/badge/${owner}/${repo}`;
  const md = `[![debtmap](${url})](https://debtmap.dev/results/${owner}/${repo})`;
  const html = `<a href="https://debtmap.dev/results/${owner}/${repo}"><img src="${url}" alt="debtmap"/></a>`;

  function copy(label: string, text: string) {
    navigator.clipboard?.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1400);
  }

  return (
    <div className="space-y-3">
      <div>
        <img src={url} alt="debtmap badge" className="rounded border border-border" />
      </div>
      {[
        { label: 'Markdown', value: md },
        { label: 'HTML', value: html },
      ].map((s) => (
        <div key={s.label}>
          <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-wider text-muted">
            <span>{s.label}</span>
            <button onClick={() => copy(s.label, s.value)} className="text-accent">
              {copied === s.label ? 'copied!' : 'copy'}
            </button>
          </div>
          <code className="mono block overflow-x-auto whitespace-pre rounded-md bg-panel2 p-2 text-[11px]">
            {s.value}
          </code>
        </div>
      ))}
    </div>
  );
}
