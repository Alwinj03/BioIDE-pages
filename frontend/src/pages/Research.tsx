import React, { useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, Empty, ErrorBox, Icon, I, ProvenanceBadge, Section, Spinner, Stat } from '../components/ui'

type Paper = {
  title: string; authors: string[]; year: number | null; journal: string | null
  doi: string | null; pmid: string | null; pmcid: string | null; abstract: string | null
  citations: number | null; is_open_access: boolean | null; url: string | null
  article_type: string | null
  full_text_url: string | null; concepts: string[]; found_in: string[]; source: string
}

export function Research({ projectId, pending }: { projectId: string | null; pending?: any }) {
  const [query, setQuery] = useState('')
  const [providers, setProviders] = useState<string[]>(['europepmc', 'openalex'])
  const [yearMin, setYearMin] = useState<string>('')
  const [openAccess, setOpenAccess] = useState(false)
  const [articleType, setArticleType] = useState('')
  const [limit, setLimit] = useState(20)
  const [selected, setSelected] = useState<Paper | null>(null)
  const [saved, setSaved] = useState<Paper[]>([])

  const provs = useAsync<any>(() => api.get('/api/literature/providers'), true)
  const search = useAsync<any>((body: any) => api.post('/api/literature/search', body))
  const fulltext = useAsync<any>((pmcid: string) => api.get(`/api/literature/fulltext/${pmcid}`))

  React.useEffect(() => {
    if (pending?.body?.query) { setQuery(pending.body.query); void run(pending.body.query) }
  }, [pending])

  const run = (q?: string) => search.run({
    query: q ?? query, providers, limit,
    year_min: yearMin ? parseInt(yearMin) : null,
    open_access: openAccess, article_type: articleType || null,
    project_id: projectId,
  })

  const savePaper = async (p: Paper) => {
    setSaved(s => s.find(x => (x.doi ?? x.title) === (p.doi ?? p.title)) ? s : [...s, p])
    if (projectId) { try { await api.post(`/api/projects/${projectId}/literature`, p) } catch { /* local copy kept */ } }
  }

  const bibtex = useMemo(() => saved.length ? buildBibtex(saved) : '', [saved])

  return (
    <div className="flex h-full min-h-0">
      {/* left: query + saved */}
      <div className="w-[300px] shrink-0 space-y-3 overflow-y-auto border-r border-line p-3">
        <Section title="Search" className="!p-3">
          <textarea className="input h-20 resize-none" placeholder="Research question or keywords…"
                    value={query} onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void run() } }} />
          <button className="btn-primary mt-2 w-full justify-center" onClick={() => run()} disabled={!query.trim() || search.loading}>
            <Icon d={I.search} className="h-3.5 w-3.5" />{search.loading ? 'Querying…' : 'Search'}
          </button>

          <div className="mt-3 space-y-2 border-t border-line pt-3">
            <div>
              <label className="label">Providers</label>
              <div className="mt-1 space-y-1">
                {Object.entries(provs.data?.providers ?? {}).map(([k, desc]: any) => (
                  <label key={k} className="flex cursor-pointer items-start gap-2">
                    <input type="checkbox" checked={providers.includes(k)} className="mt-0.5 accent-accent"
                           onChange={e => setProviders(p => e.target.checked ? [...p, k] : p.filter(x => x !== k))} />
                    <span className="min-w-0">
                      <span className="text-[11.5px] text-ink">{k}</span>
                      <span className="block text-[10px] leading-snug text-muted">{desc}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="label">From year</label>
                <input className="input mt-1 mono" placeholder="2015" value={yearMin}
                       onChange={e => setYearMin(e.target.value.replace(/\D/g, ''))} />
              </div>
              <div>
                <label className="label">Max records</label>
                <input type="number" min="5" max="100" className="input mt-1 mono" value={limit}
                       onChange={e => setLimit(parseInt(e.target.value) || 20)} />
              </div>
            </div>
            <div>
              <label className="label">Article type</label>
              <select className="input mt-1" value={articleType} onChange={e => setArticleType(e.target.value)}>
                <option value="">any</option>
                {provs.data?.article_types?.map((t: string) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-2 text-[11.5px] text-muted">
              <input type="checkbox" checked={openAccess} onChange={e => setOpenAccess(e.target.checked)} className="accent-accent" />
              Open access only
            </label>
          </div>
        </Section>

        <Section title={`Saved papers (${saved.length})`} className="!p-3"
                 right={saved.length > 0 ? <button className="btn-ghost" onClick={() => setSaved([])}>clear</button> : undefined}>
          {saved.length === 0 ? (
            <p className="text-[11px] text-muted">Papers you save appear here and in the project's literature collection.</p>
          ) : (
            <div className="space-y-1.5">
              {saved.map((p, i) => (
                <button key={i} onClick={() => setSelected(p)}
                        className="w-full rounded border border-line bg-bg p-1.5 text-left hover:border-accent/50">
                  <div className="line-clamp-2 text-[10.5px] leading-snug text-ink">{p.title}</div>
                  <div className="mono mt-0.5 text-[9.5px] text-muted">{p.year} · {p.journal?.slice(0, 28)}</div>
                </button>
              ))}
              <details className="mt-2">
                <summary className="cursor-pointer text-[10.5px] text-accent">BibTeX</summary>
                <div className="mt-1"><Code code={bibtex} filename="references.bib" maxH="max-h-48" /></div>
              </details>
            </div>
          )}
        </Section>
      </div>

      {/* centre: results */}
      <div className="min-w-0 flex-1 overflow-y-auto p-4">
        {search.loading && <Spinner label="Querying literature APIs…" />}
        {search.error && (
          <ErrorBox error={search.error}
                    hint="BioIDE queries these APIs live and holds no local copy of any literature database. When a provider is unreachable you see this error — it will never fill the page with records it did not retrieve." />
        )}
        {!search.data && !search.loading && !search.error && (
          <Empty title="Search the literature" icon={I.book}
                 body="Europe PMC, OpenAlex, Crossref and PubMed are queried directly. Records are merged by DOI and PMID, and every field shown came back from a provider." />
        )}
        {search.data && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <ProvenanceBadge p={search.data.provenance} elapsed={search.elapsed} />
              <span className="chip">{search.data.count} records</span>
              {search.data.providers_queried.map((p: string) => (
                <span key={p} className={`chip ${search.data.provider_errors?.[p] ? 'border-rose-500/40 text-rose-300' : 'border-accent2/40 text-accent2'}`}>
                  {p} {search.data.provider_errors?.[p] ? 'failed' : 'ok'}
                </span>
              ))}
            </div>

            {Object.keys(search.data.provider_errors ?? {}).length > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/[0.05] p-2.5">
                <div className="text-[11px] font-semibold text-amber-200">Some providers failed</div>
                {Object.entries(search.data.provider_errors).map(([k, v]: any) => (
                  <div key={k} className="mono mt-0.5 break-words text-[10.5px] text-amber-100/80">{k}: {v}</div>
                ))}
                <div className="mt-1 text-[10.5px] text-muted">
                  Results below come only from the providers that answered.
                </div>
              </div>
            )}

            {search.data.results.map((p: Paper, i: number) => (
              <article key={i} onClick={() => setSelected(p)}
                       className={`panel card-hover cursor-pointer p-3 ${selected?.title === p.title ? 'border-accent/60' : ''}`}>
                <h4 className="text-[13px] font-semibold leading-snug text-ink">{p.title}</h4>
                <div className="mt-1 text-[11px] text-muted">
                  {(p.authors ?? []).slice(0, 4).join(', ')}{(p.authors?.length ?? 0) > 4 && ' et al.'}
                  {p.year && <span> · {p.year}</span>}
                  {p.journal && <span> · <span className="italic">{p.journal}</span></span>}
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {p.citations !== null && <span className="chip">{p.citations} citations</span>}
                  {p.is_open_access && <span className="chip border-accent2/40 text-accent2">open access</span>}
                  {p.article_type && <span className="chip">{p.article_type}</span>}
                  {p.found_in?.map(s => <span key={s} className="chip">{s}</span>)}
                  {p.doi && <a href={`https://doi.org/${p.doi}`} target="_blank" rel="noreferrer"
                               onClick={e => e.stopPropagation()} className="chip border-accent/40 text-accent hover:bg-accent/10">
                    <Icon d={I.link} className="h-2.5 w-2.5" />{p.doi}
                  </a>}
                  <button className="btn-ghost ml-auto" onClick={e => { e.stopPropagation(); void savePaper(p) }}>
                    <Icon d={I.down} className="h-3 w-3" />save
                  </button>
                </div>
                {p.abstract && <p className="mt-2 line-clamp-3 text-[11.5px] leading-relaxed text-muted">{p.abstract}</p>}
              </article>
            ))}
          </div>
        )}
      </div>

      {/* right: detail */}
      <div className="w-[380px] shrink-0 overflow-y-auto border-l border-line p-3">
        {!selected ? (
          <Empty title="Select a paper" icon={I.book}
                 body="Record details, concepts and open-access full text appear here. BioIDE shows only what the provider returned." />
        ) : (
          <div className="space-y-3">
            <h3 className="text-[13px] font-semibold leading-snug">{selected.title}</h3>
            <div className="text-[11px] leading-relaxed text-muted">{(selected.authors ?? []).join(', ')}</div>
            <dl className="space-y-1">
              {[
                ['Year', selected.year], ['Journal', selected.journal], ['Type', selected.article_type],
                ['DOI', selected.doi], ['PMID', selected.pmid], ['PMCID', selected.pmcid],
                ['Citations', selected.citations], ['Open access', selected.is_open_access === null ? 'unknown' : String(selected.is_open_access)],
              ].filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => (
                <div key={k as string} className="flex items-baseline justify-between gap-2 border-b border-line/50 py-1">
                  <dt className="text-[10.5px] uppercase tracking-wide text-muted">{k}</dt>
                  <dd className="mono min-w-0 break-all text-right text-[11px] text-ink">{String(v)}</dd>
                </div>
              ))}
            </dl>

            <div className="flex flex-wrap gap-1.5">
              {selected.url && <a className="btn px-2 py-1 text-[11px]" href={selected.url} target="_blank" rel="noreferrer">
                <Icon d={I.link} className="h-3 w-3" />publisher
              </a>}
              {selected.full_text_url && <a className="btn px-2 py-1 text-[11px]" href={selected.full_text_url} target="_blank" rel="noreferrer">
                <Icon d={I.docs} className="h-3 w-3" />full text
              </a>}
              {selected.pmcid && (
                <button className="btn px-2 py-1 text-[11px]" onClick={() => fulltext.run(selected.pmcid!)}>
                  <Icon d={I.down} className="h-3 w-3" />fetch OA text
                </button>
              )}
              <button className="btn px-2 py-1 text-[11px]" onClick={() => savePaper(selected)}>
                <Icon d={I.copy} className="h-3 w-3" />save
              </button>
            </div>

            {selected.concepts?.length > 0 && (
              <div>
                <div className="label">Concepts / MeSH, as returned</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {selected.concepts.map(c => <span key={c} className="chip">{c}</span>)}
                </div>
              </div>
            )}

            {selected.abstract && (
              <div>
                <div className="label">Abstract</div>
                <p className="mt-1 whitespace-pre-wrap text-[11.5px] leading-relaxed text-muted">{selected.abstract}</p>
              </div>
            )}

            {fulltext.loading && <Spinner label="Fetching open-access text…" />}
            {fulltext.error && <ErrorBox error={fulltext.error} />}
            {fulltext.data && (
              <div>
                <div className="label">Open-access full text · {fulltext.data.n_references} references</div>
                {fulltext.data.license && (
                  <div className="mt-1 text-[10px] leading-relaxed text-muted">{fulltext.data.license}</div>
                )}
                <div className="mt-2 max-h-96 space-y-2 overflow-y-auto">
                  {fulltext.data.sections.map((s: any, i: number) => (
                    <details key={i} className="panel-tight p-2">
                      <summary className="cursor-pointer text-[11px] font-medium text-ink">{s.title || `Section ${i + 1}`}</summary>
                      <p className="mt-1 text-[11px] leading-relaxed text-muted">{s.text}</p>
                    </details>
                  ))}
                </div>
              </div>
            )}

            <div className="rounded-lg border border-line bg-bg2 p-2 text-[10.5px] leading-relaxed text-muted">
              BioIDE does not summarise or synthesise this record unless you ask BioAgent to, and when it does it
              cites only records retrieved in that conversation.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function buildBibtex(papers: Paper[]): string {
  return papers.map(p => {
    const last = (p.authors?.[0] ?? 'anon').split(' ').pop() ?? 'anon'
    const key = (last + (p.year ?? '')).replace(/\W/g, '').toLowerCase() || 'ref'
    const fields: [string, any][] = [
      ['title', p.title], ['author', (p.authors ?? []).join(' and ')],
      ['journal', p.journal], ['year', p.year], ['doi', p.doi],
    ]
    const body = fields.filter(([, v]) => v).map(([k, v]) => `  ${k} = {${v}}`).join(',\n')
    return `@article{${key},\n${body}\n}`
  }).join('\n\n')
}
