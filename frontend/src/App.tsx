import React, { useEffect, useState } from 'react'
import { api } from './lib/api'
import { Icon, I } from './components/ui'
import { Assistant } from './components/Assistant'
import { Home } from './pages/Home'
const Research = React.lazy(() => import('./pages/Research').then(m => ({ default: m.Research })))
const Workflows = React.lazy(() => import('./pages/Workflows').then(m => ({ default: m.Workflows })))
const Bioinformatics = React.lazy(() => import('./pages/Bioinformatics').then(m => ({ default: m.Bioinformatics })))
const Omics = React.lazy(() => import('./pages/Omics').then(m => ({ default: m.Omics })))
const Modelling = React.lazy(() => import('./pages/Modelling').then(m => ({ default: m.Modelling })))
const Editor = React.lazy(() => import('./pages/Editor').then(m => ({ default: m.Editor })))
const Projects = React.lazy(() => import('./pages/Projects').then(m => ({ default: m.Projects })))
const Docs = React.lazy(() => import('./pages/Docs').then(m => ({ default: m.Docs })))
const Settings = React.lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })))
const Tools = React.lazy(() => import('./pages/Tools').then(m => ({ default: m.Tools })))

const NAV = [
  { id: 'home', label: 'Home', icon: I.home },
  { id: 'research', label: 'Research', icon: I.book },
  { id: 'workflows', label: 'Workflows', icon: I.flow },
  { id: 'bioinformatics', label: 'Bioinformatics', icon: I.dna },
  { id: 'omics', label: 'Omics', icon: I.layers },
  { id: 'modelling', label: 'Modelling', icon: I.atom },
  { id: 'tools', label: 'Tools', icon: I.gear },
  { id: 'editor', label: 'Code editor', icon: I.code },
  { id: 'projects', label: 'Projects', icon: I.folder },
  { id: 'docs', label: 'Documentation', icon: I.docs },
  { id: 'settings', label: 'Settings', icon: I.chart },
]

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden>
        <defs>
          <linearGradient id="bg1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="100%" stopColor="#34D399" />
          </linearGradient>
        </defs>
        <rect x="1.5" y="1.5" width="25" height="25" rx="7" fill="none" stroke="url(#bg1)" strokeWidth="1.6" />
        <path d="M9 7c0 7 10 7 10 14M19 7c0 7-10 7-10 14" stroke="url(#bg1)" strokeWidth="1.7"
              fill="none" strokeLinecap="round" />
        <path d="M10.2 10.5h7.6M10.2 14h7.6M10.2 17.5h7.6" stroke="#94A3B8" strokeWidth="1.1"
              strokeLinecap="round" opacity="0.65" />
      </svg>
      <div className="leading-none">
        <div className="text-[15px] font-bold tracking-tight">BioIDE</div>
        <div className="mt-0.5 text-[9px] uppercase tracking-[0.14em] text-muted">biological engineering</div>
      </div>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState('home')
  const [pending, setPending] = useState<any>(null)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [seed, setSeed] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [projects, setProjects] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [profile, setProfile] = useState({ role: 'Biotechnology student', level: 'Intermediate' })
  const [onboarding, setOnboarding] = useState(false)
  const [apiDown, setApiDown] = useState<string | null>(null)

  useEffect(() => {
    try {
      const saved = localStorage.getItem('bioide.profile')
      if (saved) setProfile(JSON.parse(saved))
      else setOnboarding(true)
      const p = localStorage.getItem('bioide.project')
      if (p) setProjectId(p)
    } catch { setOnboarding(true) }
  }, [])

  useEffect(() => {
    try { localStorage.setItem('bioide.profile', JSON.stringify(profile)) } catch { /* private mode */ }
  }, [profile])
  useEffect(() => {
    try {
      if (projectId) localStorage.setItem('bioide.project', projectId)
      else localStorage.removeItem('bioide.project')
    } catch { /* private mode */ }
  }, [projectId])

  const loadProjects = () => api.get('/api/projects')
    .then(r => { setProjects(r.projects ?? []); setApiDown(null) })
    .catch(e => setApiDown(e?.detail ?? String(e)))
  useEffect(() => { void loadProjects() }, [page])

  const navigate = (workspace: string, payload?: any) => {
    setPage(workspace)
    setPending(payload ?? null)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setAssistantOpen(true) }
      if (e.key === 'Escape') setAssistantOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const common = { projectId, pending }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-bg2 px-4">
        <button onClick={() => navigate('home')} className="shrink-0"><Logo /></button>

        <div className="relative hidden min-w-0 max-w-md flex-1 md:block">
          <Icon d={I.search} className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted" />
          <input
            className="input !py-1.5 !pl-8 text-[12px]"
            placeholder="Search or describe an objective…  ⌘K for BioAgent"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && search.trim()) {
                api.post('/api/agent/route', { q: search.trim() })
                  .then(r => navigate(r.workspace, r.suggested_actions?.[0]))
                  .catch(() => navigate('home'))
              }
            }} />
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <select className="input !w-auto !py-1 text-[11px]" value={projectId ?? ''}
                  onChange={e => setProjectId(e.target.value || null)}>
            <option value="">no project (runs unlinked)</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <a className="btn-ghost hidden lg:inline-flex" href="/docs" target="_blank" rel="noreferrer">
            <Icon d={I.docs} className="h-3.5 w-3.5" />API
          </a>
          <button className="btn-ghost hidden lg:inline-flex" onClick={() => navigate('docs')}>
            <Icon d={I.info} className="h-3.5 w-3.5" />Docs
          </button>
          <button className={`btn ${assistantOpen ? 'border-accent text-accent' : ''}`}
                  onClick={() => setAssistantOpen(!assistantOpen)}>
            <Icon d={I.spark} className="h-3.5 w-3.5" />BioAgent
          </button>
          <div className="hidden h-8 w-8 items-center justify-center rounded-full border border-line bg-panel text-[11px] font-semibold text-muted sm:flex"
               title={`${profile.role} · ${profile.level}`}>
            {profile.role.split(' ').map(w => w[0]).slice(0, 2).join('')}
          </div>
        </div>
      </header>

      {apiDown && (
        <div className="border-b border-rose-500/40 bg-rose-500/[0.08] px-4 py-2 text-[11.5px] text-rose-200">
          <Icon d={I.warn} className="mr-1.5 inline h-3.5 w-3.5" />
          The backend is not reachable: <span className="mono">{apiDown}</span>. Start it with{' '}
          <span className="mono">uvicorn app.main:app --port 8000</span>.
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <nav className="flex w-[196px] shrink-0 flex-col border-r border-line bg-bg2 py-2">
          {NAV.map(n => (
            <button key={n.id} onClick={() => navigate(n.id)}
                    className={`mx-2 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[12.5px] transition-colors ${
                      page === n.id ? 'bg-accent/[0.12] text-accent' : 'text-muted hover:bg-line/40 hover:text-ink'}`}>
              <Icon d={n.icon} className="h-4 w-4 shrink-0" />
              {n.label}
            </button>
          ))}
          <div className="mt-auto px-4 py-3 text-[9.5px] leading-relaxed text-muted/60">
            Results shown in BioIDE come from real library calls and carry a provenance record.
          </div>
        </nav>

        <main className="min-w-0 flex-1 overflow-hidden">
          <React.Suspense fallback={<div className="p-6 text-xs text-muted">loading workspace…</div>}>
          {page === 'home' && <Home onNavigate={navigate} onAsk={q => { setSeed(q); setAssistantOpen(true) }} />}
          {page === 'research' && <Research {...common} />}
          {page === 'workflows' && <Workflows {...common} />}
          {page === 'bioinformatics' && <Bioinformatics {...common} />}
          {page === 'omics' && <Omics {...common} />}
          {page === 'modelling' && <Modelling {...common} />}
          {page === 'tools' && <Tools {...common} />}
          {page === 'editor' && <Editor projectId={projectId} />}
          {page === 'projects' && <Projects projectId={projectId} setProjectId={setProjectId}
                                            pending={pending} onNavigate={navigate} />}
          {page === 'docs' && <Docs />}
          {page === 'settings' && <Settings profile={profile} setProfile={setProfile} />}
          </React.Suspense>
        </main>

        <Assistant open={assistantOpen} onClose={() => setAssistantOpen(false)}
                   projectId={projectId} onNavigate={navigate} seed={seed} />
      </div>

      {onboarding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg/85 p-4 backdrop-blur-sm">
          <div className="panel w-full max-w-lg animate-fade p-6">
            <Logo />
            <h2 className="mt-4 text-lg font-semibold">Welcome to BioIDE</h2>
            <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
              Two questions, so explanations land at the right level. Neither restricts what you can do.
            </p>
            <div className="mt-4 space-y-3">
              <div>
                <label className="label">What describes you best?</label>
                <div className="mt-1.5 grid grid-cols-2 gap-1.5">
                  {['Biotechnology student', 'Bioinformatics student', 'Computational biologist',
                    'Research scholar', 'Industry professional', 'Independent developer'].map(r => (
                    <button key={r} onClick={() => setProfile(p => ({ ...p, role: r }))}
                            className={`rounded-lg border px-2 py-1.5 text-[11.5px] transition-colors ${
                              profile.role === r ? 'border-accent bg-accent/10 text-ink' : 'border-line text-muted hover:text-ink'}`}>
                      {r}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label">Experience with computational biology</label>
                <div className="mt-1.5 flex gap-1.5">
                  {['Beginner', 'Intermediate', 'Advanced'].map(l => (
                    <button key={l} onClick={() => setProfile(p => ({ ...p, level: l }))}
                            className={`flex-1 rounded-lg border px-2 py-1.5 text-[11.5px] transition-colors ${
                              profile.level === l ? 'border-accent bg-accent/10 text-ink' : 'border-line text-muted hover:text-ink'}`}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-5 rounded-lg border border-line bg-bg2 p-3 text-[11px] leading-relaxed text-muted">
              One thing worth knowing up front: BioIDE will not show you a number it did not compute. Results carry
              a provenance badge naming the library and version that produced them, and steps it cannot run are
              labelled rather than simulated.
            </div>
            <button className="btn-primary mt-4 w-full justify-center" onClick={() => setOnboarding(false)}>
              Start
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
