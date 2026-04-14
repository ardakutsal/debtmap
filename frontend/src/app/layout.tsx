import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'DebtMap — Find technical debt in AI-generated codebases',
  description: 'A one-number score, treemap, and action plan for any GitHub repository.',
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
