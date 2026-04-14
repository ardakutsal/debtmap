import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function gradeColor(score: number): string {
  if (score <= 20) return '#2ea44f';
  if (score <= 40) return '#7ec93f';
  if (score <= 60) return '#e3b341';
  if (score <= 75) return '#e86a2b';
  return '#d1242f';
}

export function gradeFor(score: number): string {
  if (score <= 20) return 'A';
  if (score <= 40) return 'B';
  if (score <= 60) return 'C';
  if (score <= 75) return 'D';
  return 'F';
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';

export function apiUrl(path: string) {
  return path.startsWith('http') ? path : `${API_BASE}${path}`;
}
