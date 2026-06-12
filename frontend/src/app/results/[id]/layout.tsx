import type { Metadata } from 'next';
import { apiUrl } from '@/lib/utils';

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const fallback: Metadata = {
    title: 'DebtMap report',
    description: 'Technical-debt report for a GitHub repository.',
  };
  try {
    const resp = await fetch(apiUrl(`/results/${params.id}`), { cache: 'no-store' });
    if (!resp.ok) return fallback;
    const data = await resp.json();
    if (data.status !== 'completed') return fallback;

    const title = `${data.owner}/${data.repo} — DebtScore ${Math.round(data.debt_score)} · Grade ${data.grade}`;
    const aiPct = data.ai_generated_pct ?? 0;
    const description = `${data.files_analyzed} files analyzed · AI-signed commits ${aiPct}% · DebtMap technical-debt report.`;
    return {
      title,
      description,
      openGraph: { title, description, siteName: 'DebtMap', type: 'website' },
      // og/twitter images come from the segment's opengraph-image.tsx route.
      twitter: { card: 'summary_large_image', title, description },
    };
  } catch {
    return fallback;
  }
}

export default function ResultsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
