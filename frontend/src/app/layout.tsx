import type { Metadata } from 'next';
import './globals.css';

const TITLE = 'DebtMap — Find technical debt in AI-generated codebases';
const DESCRIPTION = 'A one-number score, treemap, and action plan for any GitHub repository.';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'https://debtmap.up.railway.app'),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: { title: TITLE, description: DESCRIPTION, siteName: 'DebtMap', type: 'website' },
  twitter: { card: 'summary', title: TITLE, description: DESCRIPTION },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg text-text">
        {children}
      </body>
    </html>
  );
}
