import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const API = import.meta.env.VITE_API_BASE || '/api'
export const API_BASE = API

export async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function apiDownload(path: string, opts?: RequestInit) {
  const res = await fetch(API + path, {
    headers: {
      ...(opts?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(opts?.headers || {}),
    },
    ...opts,
  })
  if (!res.ok) throw new Error(await res.text())
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/)
  const filename = decodeURIComponent(match?.[1] || match?.[2] || 'download')
  return { blob, filename }
}

export function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

// Server timestamps are stored as UTC but are serialized without timezone (e.g. "2026-03-25T09:17:31.230998").
// Treat them as UTC to avoid an 8-hour offset when users are in Asia/Shanghai.
export function parseServerDate(value: any): Date | null {
  if (value === null || value === undefined || value === '') return null
  const s = String(value)
  // If the string already contains timezone info, let Date parse it directly.
  if (/[zZ]$/.test(s) || /[+-]\d\d:\d\d$/.test(s)) return new Date(s)
  // SQLModel/SQLite often serializes as "YYYY-MM-DDTHH:MM:SS(.ffffff)" or "YYYY-MM-DD HH:MM:SS(.ffffff)".
  if (s.includes(' ')) return new Date(s.replace(' ', 'T') + 'Z')
  if (s.includes('T')) return new Date(s + 'Z')
  return new Date(s)
}

export function formatDateTime(value: any, locale = 'zh-CN'): string {
  const d = parseServerDate(value)
  return d ? d.toLocaleString(locale) : '-'
}

export function formatDate(value: any, locale = 'zh-CN'): string {
  const d = parseServerDate(value)
  return d ? d.toLocaleDateString(locale) : '-'
}
