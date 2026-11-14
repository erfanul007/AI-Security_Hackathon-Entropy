export type Col = {
  name: string; type: string; required: boolean; pk: boolean
  fk: string | null; strict: string[] | null; suggest: string[] | null
}
export type TableMeta = { pk: string; columns: Col[]; group: string }
export type Meta = { tables: Record<string, TableMeta>; groups: Record<string, string[]> }
export type Row = Record<string, unknown>
export type Rows = { rows: Row[]; total: number }

export async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`)
  return data as T
}

export const get = <T,>(path: string) => send<T>('GET', path)

/** Mirrors backend kind(): which input a column gets. */
export function kind(type: string): 'INT' | 'NUMERIC' | 'BOOLEAN' | 'TIMESTAMP' | 'DATE' | 'TEXT' | 'STRING' {
  const t = type.toUpperCase()
  for (const k of ['INT', 'NUMERIC', 'BOOLEAN', 'TIMESTAMP', 'DATE', 'TEXT'] as const) if (t.includes(k)) return k
  return 'STRING'
}

export const show = (v: unknown) => (v === null || v === undefined ? '' : String(v))
