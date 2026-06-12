import { ImageResponse } from 'next/og';
import { apiUrl } from '@/lib/utils';

export const alt = 'DebtMap score card';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

const GRADE_COLORS: Record<string, string> = {
  A: '#2ea44f',
  B: '#7ec93f',
  C: '#e3b341',
  D: '#e86a2b',
  F: '#d1242f',
};

async function fetchResult(id: string) {
  try {
    const resp = await fetch(apiUrl(`/results/${id}`), { cache: 'no-store' });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data.status === 'completed' ? data : null;
  } catch {
    return null;
  }
}

export default async function Image({ params }: { params: { id: string } }) {
  const data = await fetchResult(params.id);

  if (!data) {
    return new ImageResponse(
      (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0f1117',
            color: '#e7ebf3',
            fontSize: 72,
            fontFamily: 'monospace',
          }}
        >
          <span style={{ color: '#7cffb7' }}>debt</span>map
        </div>
      ),
      size,
    );
  }

  const grade = data.grade ?? '?';
  const gradeColor = GRADE_COLORS[grade] ?? '#5c6773';
  const score = Math.round(data.debt_score ?? 0);
  const aiPct = data.ai_generated_pct ?? 0;
  const topAgent = data.provenance?.agents?.[0]?.name;

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          background: '#0f1117',
          color: '#e7ebf3',
          padding: 64,
          fontFamily: 'monospace',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', fontSize: 36 }}>
            <span style={{ color: '#7cffb7', fontWeight: 700 }}>debt</span>
            <span style={{ fontWeight: 700 }}>map</span>
          </div>
          <div
            style={{
              display: 'flex',
              fontSize: 26,
              color: '#9aa3b5',
              border: '2px solid #262c3a',
              borderRadius: 999,
              padding: '10px 28px',
              background: '#161a22',
            }}
          >
            {aiPct > 0 ? `AI commits ${aiPct}%${topAgent ? ` · ${topAgent}` : ''}` : 'No AI signatures found'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 56 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 260,
              height: 260,
              borderRadius: 999,
              border: `14px solid ${gradeColor}`,
              background: '#161a22',
              fontSize: 110,
              fontWeight: 700,
            }}
          >
            {score}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ display: 'flex', fontSize: 56, fontWeight: 700 }}>
              <span style={{ color: '#7cffb7' }}>{data.owner}</span>
              <span style={{ color: '#5c6773' }}>/</span>
              <span>{data.repo}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <div
                style={{
                  display: 'flex',
                  background: gradeColor,
                  color: '#0f1117',
                  fontSize: 44,
                  fontWeight: 700,
                  borderRadius: 14,
                  padding: '6px 30px',
                }}
              >
                Grade {grade}
              </div>
              <div style={{ display: 'flex', fontSize: 30, color: '#9aa3b5' }}>
                {data.files_analyzed} files analyzed
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', fontSize: 24, color: '#5c6773' }}>
          Technical-debt report · DebtScore 0–100, lower is better
        </div>
      </div>
    ),
    size,
  );
}
