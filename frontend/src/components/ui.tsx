import React, { useEffect, useState } from 'react'
import type { Provenance } from '../lib/api'

export function Icon({ d, className = 'h-4 w-4' }: { d: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d={d} />
    </svg>
  )
}

export const I = {
  home: 'M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM21 21l-4.3-4.3',
  book: 'M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2V5ZM8 7h7M8 11h7',
  flow: 'M5 7h5M14 7h5M9.5 17h5M7.5 4.5v5M16.5 4.5v5M12 14.5v5M7.5 9.5 12 14.5M16.5 9.5 12 14.5',
  dna: 'M7 3c0 6 10 6 10 12M17 3c0 6-10 6-10 12M7 21c0-3 10-3 10-6M8 7h8M8 12h8M8 17h8',
  layers: 'M12 3 3 7.5l9 4.5 9-4.5L12 3ZM3 12.5 12 17l9-4.5M3 17 12 21.5 21 17',
  atom: 'M12 12a9 4.5 0 1 0 0-.01M12 12a4.5 9 0 1 0 .01 0M12 12a6.4 6.4 0 1 0 .01 0',
  code: 'M9 7 4 12l5 5M15 7l5 5-5 5',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z',
  docs: 'M7 3h7l5 5v13H7V3ZM14 3v5h5M10 13h7M10 17h7',
  gear: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-2.88 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 2.6 15H2.5a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 7a1.7 1.7 0 0 0-.34-1.87L4.2 5.07A2 2 0 1 1 7.03 2.24l.06.06A1.7 1.7 0 0 0 9 2.6V2.5a2 2 0 1 1 4 0v.1A1.7 1.7 0 0 0 17 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 21.4 9h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.9 2Z',
  check: 'M4 12.5 9 17.5 20 6.5',
  x: 'M6 6l12 12M18 6 6 18',
  warn: 'M12 3 2 20h20L12 3ZM12 9v5M12 17.5v.5',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v6M12 7.5v.5',
  play: 'M7 4.5 19 12 7 19.5v-15Z',
  spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18',
  down: 'M12 4v14M6 13l6 6 6-6',
  up: 'M12 20V6M6 11l6-6 6 6',
  copy: 'M9 9h10v10H9V9ZM5 15V5h10',
  chevron: 'M9 6l6 6-6 6',
  terminal: 'M4 5h16v14H4V5ZM7 10l2.5 2.5L7 15M12.5 15H17',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  link: 'M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1',
  refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <svg viewBox="0 0 24 24" className="h-4 w-4 animate-spin text-accent" fill="none">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeOpacity="0.2" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      {label ?? 'Running…'}
    </div>
  )
}

/** Error display. Shows the backend message verbatim — no softening, no retry theatre. */
export function ErrorBox({ error, hint }: { error: string; hint?: string }) {
  return (
    <div className="animate-fade rounded-lg border border-rose-500/40 bg-rose-500/[0.07] p-3">
      <div className="flex items-start gap-2">
        <Icon d={I.warn} className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold text-rose-300">This did not run</div>
          <pre className="mono mt-1 whitespace-pre-wrap break-words text-rose-200/90">{error}</pre>
          {hint && <div className="mt-2 text-[11px] text-muted">{hint}</div>}
        </div>
      </div>
    </div>
  )
}

/** The provenance badge. Rendered next to any number BioIDE displays, so a result
 *  with no recorded execution is visually impossible to mistake for one that ran. */
export function ProvenanceBadge({ p, elapsed }: { p?: Provenance | null; elapsed?: number | null }) {
  const [open, setOpen] = useState(false)
  if (!p) return null
  return (
    <div className="relative inline-block">
      <button onClick={() => setOpen(!open)}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent2/40 bg-accent2/10 px-2 py-0.5 text-[11px] font-medium text-accent2 hover:bg-accent2/20">
        <Icon d={I.check} className="h-3 w-3" />
        executed · {p.tool} {p.tool_version}
      </button>
      {open && (
        <div className="absolute left-0 top-7 z-30 w-72 animate-fade rounded-lg border border-line bg-bg2 p-3 shadow-2xl">
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">Provenance</div>
          <dl className="mono space-y-1 text-[11px]">
            {[
              ['run id', p.run_id],
              ['analysis', p.kind],
              ['tool', `${p.tool} ${p.tool_version}`],
              ['input hash', p.input_hash || '(n/a)'],
              ['executed at', p.executed_at],
              ...(elapsed ? [['round trip', `${elapsed.toFixed(2)} s`]] : []),
            ].map(([k, v]) => (
              <div key={k as string} className="flex gap-2">
                <dt className="w-20 shrink-0 text-muted">{k}</dt>
                <dd className="min-w-0 break-all text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 border-t border-line pt-2 text-[10px] leading-relaxed text-muted">
            These values came from the named library in this process. BioIDE does not generate numerical results
            with a language model.
          </p>
        </div>
      )}
    </div>
  )
}

export function Caveats({ items, title = 'How to read this' }: { items?: string[]; title?: string }) {
  const [open, setOpen] = useState(true)
  if (!items?.length) return null
  return (
    <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 text-left">
        <Icon d={I.info} className="h-3.5 w-3.5 shrink-0 text-amber-400" />
        <span className="text-xs font-semibold text-amber-200">{title}</span>
        <Icon d={I.chevron} className={`ml-auto h-3.5 w-3.5 text-amber-400/70 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5 pl-5">
          {items.map((c, i) => (
            <li key={i} className="list-disc text-[11.5px] leading-relaxed text-amber-100/80">{c}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function Section({ title, subtitle, right, children, className = '' }:
  { title: string; subtitle?: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel p-4 ${className}`}>
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted">{subtitle}</p>}
        </div>
        {right && <div className="flex shrink-0 items-center gap-2">{right}</div>}
      </header>
      {children}
    </section>
  )
}

export function Stat({ label, value, unit, tone = 'default' }:
  { label: string; value: React.ReactNode; unit?: string; tone?: 'default' | 'good' | 'warn' | 'bad' }) {
  const colour = { default: 'text-ink', good: 'text-accent2', warn: 'text-amber-300', bad: 'text-rose-300' }[tone]
  return (
    <div className="panel-tight px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-lg leading-tight ${colour}`}>
        {value}{unit && <span className="ml-1 text-xs text-muted">{unit}</span>}
      </div>
    </div>
  )
}

export function Table<T>({ rows, cols, maxH = 'max-h-80', empty = 'No rows', onRowClick }: {
  rows: T[]
  cols: { key: string; label: string; render?: (r: T) => React.ReactNode; className?: string; align?: 'right' }[]
  maxH?: string
  empty?: string
  onRowClick?: (r: T) => void
}) {
  if (!rows?.length) return <div className="py-6 text-center text-xs text-muted">{empty}</div>
  return (
    <div className={`${maxH} overflow-auto rounded-lg border border-line`}>
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr>{cols.map(c => (
            <th key={c.key} className={`th ${c.align === 'right' ? 'text-right' : ''}`}>{c.label}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}
                onClick={() => onRowClick?.(r)}
                className={`hover:bg-line/30 ${onRowClick ? 'cursor-pointer' : ''}`}>
              {cols.map(c => (
                <td key={c.key} className={`td ${c.align === 'right' ? 'text-right' : ''} ${c.className ?? ''}`}>
                  {c.render ? c.render(r) : String((r as any)[c.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Code({ code, language, filename, maxH = 'max-h-96' }:
  { code: string; language?: string; filename?: string; maxH?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }
  const download = () => {
    const url = URL.createObjectURL(new Blob([code], { type: 'text/plain' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'bioide-export.txt'
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-bg">
      <div className="flex items-center justify-between border-b border-line bg-bg2 px-3 py-1.5">
        <span className="mono text-muted">{filename || language || 'code'}</span>
        <div className="flex gap-1">
          <button className="btn-ghost" onClick={copy}>
            <Icon d={copied ? I.check : I.copy} className="h-3 w-3" />{copied ? 'copied' : 'copy'}
          </button>
          {filename && (
            <button className="btn-ghost" onClick={download}>
              <Icon d={I.down} className="h-3 w-3" />download
            </button>
          )}
        </div>
      </div>
      <pre className={`${maxH} overflow-auto p-3 mono leading-relaxed text-ink/90`}>{code}</pre>
    </div>
  )
}

export function Tabs({ tabs, active, onChange }:
  { tabs: { id: string; label: string; badge?: number | string }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-line">
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)}
                className={`-mb-px border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
                  active === t.id ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-ink'}`}>
          {t.label}
          {t.badge !== undefined && (
            <span className="ml-1.5 rounded-full bg-line px-1.5 py-0.5 text-[10px] text-muted">{t.badge}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export function ExecBadge({ kind }: { kind: string }) {
  const map: Record<string, { label: string; cls: string; title: string }> = {
    native: { label: 'runs here', cls: 'border-accent2/40 bg-accent2/10 text-accent2',
              title: 'Executes inside the BioIDE backend now, with a provenance record.' },
    local: { label: 'your machine', cls: 'border-accent/40 bg-accent/10 text-accent',
             title: 'BioIDE generates the command; it runs on your machine after you approve it.' },
    local_db: { label: 'machine + database', cls: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
                title: 'Needs the tool installed and a large reference database downloaded by you.' },
    external: { label: 'external service', cls: 'border-muted/40 bg-muted/10 text-muted',
                title: 'A hosted service, GPU job or desktop application. BioIDE does not run it.' },
    input: { label: 'input', cls: 'border-line bg-bg2 text-muted', title: 'A data input, not a computation.' },
    io: { label: 'input', cls: 'border-line bg-bg2 text-muted', title: 'A data input, not a computation.' },
    script: { label: 'script step', cls: 'border-line bg-bg2 text-muted', title: 'A short script you write or adapt.' },
  }
  const m = map[kind] ?? { label: kind, cls: 'border-line bg-bg2 text-muted', title: kind }
  return <span title={m.title} className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${m.cls}`}>{m.label}</span>
}

export function Empty({ icon = I.info, title, body, action }:
  { icon?: string; title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line px-6 py-10 text-center">
      <Icon d={icon} className="h-6 w-6 text-muted/60" />
      <div className="text-sm font-medium text-ink">{title}</div>
      {body && <p className="max-w-md text-[11.5px] leading-relaxed text-muted">{body}</p>}
      {action}
    </div>
  )
}

export function useRotating(items: string[], ms = 3600) {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (items.length < 2) return
    const t = setInterval(() => setI(x => (x + 1) % items.length), ms)
    return () => clearInterval(t)
  }, [items.length, ms])
  return items[i] ?? ''
}
