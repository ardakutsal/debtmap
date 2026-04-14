'use client';

import { gradeColor } from '@/lib/utils';

const LABELS: Record<string, string> = {
  style_homogeneity: 'Style Homogeneity',
  duplication: 'Duplication',
  comment_patterns: 'Comment Patterns',
  error_handling: 'Error Handling',
  architectural_contracts: 'Architectural Contracts',
  dependency_graph: 'Dependency Graph',
  code_churn: 'Code Churn',
};

export function AnalyzerBars({ analyzers }: { analyzers: Record<string, { score: number; weight: number; skipped?: boolean }> }) {
  return (
    <div className="space-y-3">
      {Object.entries(analyzers).map(([name, v]) => {
        const score = v.skipped ? 0 : v.score;
        return (
          <div key={name}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-muted">{LABELS[name] ?? name}</span>
              <span className="mono">
                {v.skipped ? 'skipped' : score.toFixed(0)}
                <span className="ml-2 text-muted">· {Math.round(v.weight * 100)}%</span>
              </span>
            </div>
            <div className="h-2 rounded-full bg-panel2">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${score}%`, backgroundColor: v.skipped ? '#3a4054' : gradeColor(score) }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
