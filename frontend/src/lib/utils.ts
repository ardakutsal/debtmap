import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Bands must mirror backend grade_for in app/analysis/scoring.py.
export function gradeColor(score: number): string {
  if (score <= 22) return '#2ea44f';
  if (score <= 42) return '#7ec93f';
  if (score <= 62) return '#e3b341';
  if (score <= 77) return '#e86a2b';
  return '#d1242f';
}

export function gradeFor(score: number): string {
  if (score <= 22) return 'A';
  if (score <= 42) return 'B';
  if (score <= 62) return 'C';
  if (score <= 77) return 'D';
  return 'F';
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';

export function apiUrl(path: string) {
  return path.startsWith('http') ? path : `${API_BASE}${path}`;
}
