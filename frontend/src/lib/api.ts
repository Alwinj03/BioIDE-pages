export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

const base = ''

async function handle(r: Response) {
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`
    try {
      const j = await r.json()
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      try { detail = (await r.text()).slice(0, 400) || detail } catch { /* keep */ }
    }
    throw new ApiError(r.status, detail)
  }
  const ct = r.headers.get('content-type') || ''
  return ct.includes('application/json') ? r.json() : r.text()
}

export const api = {
  get: (p: string) => fetch(base + p).then(handle),
  post: (p: string, body?: unknown) =>
    fetch(base + p, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    }).then(handle),
  del: (p: string) => fetch(base + p, { method: 'DELETE' }).then(handle),
  upload: (p: string, files: Record<string, File>, fields?: Record<string, string>) => {
    const fd = new FormData()
    for (const [k, v] of Object.entries(files)) fd.append(k, v)
    for (const [k, v] of Object.entries(fields ?? {})) fd.append(k, v)
    return fetch(base + p, { method: 'POST', body: fd }).then(handle)
  },
}

export type Provenance = {
  run_id: string
  tool: string
  tool_version: string
  kind: string
  input_hash: string
  executed: boolean
  executed_at: string
}
