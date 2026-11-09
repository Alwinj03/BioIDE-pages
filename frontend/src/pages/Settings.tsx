import React from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Code, ErrorBox, Icon, I, Section, Spinner, Stat, Table } from '../components/ui'

export function Settings({ profile, setProfile }: {
  profile: { role: string; level: string }
  setProfile: (p: { role: string; level: string }) => void
}) {
  const health = useAsync<any>(() => api.get('/api/health'), true)
  const caps = useAsync<any>(() => api.get('/api/capabilities'), true)
  const runs = useAsync<any>(() => api.get('/api/runs?limit=60'), true)

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <Section title="Your profile"
               subtitle="This tailors how much explanation BioIDE and BioAgent give. It never restricts functionality.">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Role</label>
            <select className="input mt-1" value={profile.role}
                    onChange={e => setProfile({ ...profile, role: e.target.value })}>
              {['Biotechnology student', 'Bioinformatics student', 'Computational biologist',
                'Research scholar', 'Industry professional', 'Independent developer'].map(r =>
                <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Experience level</label>
            <select className="input mt-1" value={profile.level}
                    onChange={e => setProfile({ ...profile, level: e.target.value })}>
              {['Beginner', 'Intermediate', 'Advanced'].map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-muted">
          Stored in this browser only. There is no account system and nothing is sent anywhere.
        </p>
      </Section>

      <Section title="Backend configuration"
               subtitle="Read live from the backend. Change these with environment variables and restart.">
        {health.loading && <Spinner />}
        {health.error && <ErrorBox error={health.error} hint="The frontend cannot reach the API. Is uvicorn running?" />}
        {health.data && (
          <>
            <div className="grid gap-2 sm:grid-cols-4">
              <Stat label="LLM provider" value={health.data.config.llm_provider}
                    tone={health.data.config.llm_enabled ? 'good' : 'warn'} />
              <Stat label="Code execution" value={health.data.config.allow_code_exec ? 'enabled' : 'disabled'}
                    tone={health.data.config.allow_code_exec ? 'good' : 'default'} />
              <Stat label="Install execution" value={health.data.config.allow_local_install ? 'enabled' : 'disabled'}
                    tone={health.data.config.allow_local_install ? 'warn' : 'good'} />
              <Stat label="Exec timeout" value={health.data.config.exec_timeout_s} unit="s" />
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {Object.entries(health.data.versions).map(([k, v]: any) => (
                <span key={k} className="chip mono">{k} {v}</span>
              ))}
            </div>
            <div className="mono mt-2 text-[10.5px] text-muted">data directory: {health.data.config.data_dir}</div>
          </>
        )}
      </Section>

      <Section title="Enable the conversational agent"
               subtitle="Every analysis endpoint works without a key. The key only enables orchestration and explanation.">
        <Code language="shell" code={`# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export BIOIDE_LLM_MODEL=claude-sonnet-4-5

# or any OpenAI-compatible endpoint, including a local model
export OPENAI_API_KEY=sk-...
export BIOIDE_LLM_BASE_URL=http://localhost:11434/v1   # Ollama
export BIOIDE_LLM_MODEL=qwen2.5:14b

# then restart the backend
uvicorn app.main:app --port 8000`} />
        <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
          BioIDE sends the model your prompt, the tool schemas and the tool results. It does not send your
          uploaded data unless a tool you invoked returned part of it.
        </p>
      </Section>

      <Section title="Recent activity, across all projects"
               subtitle="The provenance log. Every library call BioIDE has made in this installation."
               right={<button className="btn-ghost" onClick={() => runs.run()}>
                 <Icon d={I.refresh} className="h-3 w-3" />refresh</button>}>
        <Table maxH="max-h-96" rows={runs.data?.runs ?? []} empty="Nothing has run yet."
               cols={[
                 { key: 'started', label: 'When',
                   render: (r: any) => <span className="mono text-[10px] text-muted">{new Date(r.started * 1000).toLocaleString()}</span> },
                 { key: 'kind', label: 'Analysis', className: 'mono text-accent' },
                 { key: 'tool', label: 'Tool', render: (r: any) => <span className="mono">{r.tool} {r.tool_version}</span> },
                 { key: 'status', label: 'Status',
                   render: (r: any) => <span className={`chip ${r.status === 'succeeded' ? 'border-accent2/40 text-accent2'
                     : r.status === 'failed' ? 'border-rose-500/40 text-rose-300' : 'border-line'}`}>{r.status}</span> },
                 { key: 'duration_s', label: 'Seconds', align: 'right',
                   render: (r: any) => <span className="mono">{r.duration_s ?? '—'}</span> },
               ]} />
      </Section>

      <Section title="Data and deletion">
        <p className="text-[12px] leading-relaxed text-muted">
          Projects, provenance runs, artifacts and notebook sessions are stored in a SQLite database and files
          under the data directory above. Deleting a project removes its rows and its directory. Nothing is sent
          to a third party except the literature API queries you make and, if you configure a key, the agent
          conversation.
        </p>
        {caps.data?.host && (
          <p className="mt-2 text-[11px] leading-relaxed text-accent/80">{caps.data.host.note}</p>
        )}
      </Section>
    </div>
  )
}
