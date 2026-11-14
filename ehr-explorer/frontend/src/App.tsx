import { useEffect, useState } from 'react'
import { type Meta, get } from './api'
import TableView from './TableView'

export type View =
  | { kind: 'dashboard' }
  | { kind: 'table'; t: string; editPk?: string }
  | { kind: 'patient'; id: number }

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [env, setEnv] = useState('')
  const [view, setView] = useState<View>({ kind: 'dashboard' })
  const [error, setError] = useState('')

  useEffect(() => {
    get<Meta>('/api/meta').then(setMeta, e => setError(e.message))
    get<{ env: string }>('/api/env').then(d => setEnv(d.env), () => {})
  }, [])

  const current = view.kind === 'table' ? view.t : view.kind

  return (
    <div className="app">
      <header className="topbar">
        <strong>EHR Explorer</strong>
        {env && <span className={`badge ${env}`}>{env.toUpperCase()}</span>}
      </header>
      <nav className="sidebar" aria-label="Tables">
        <button className={current === 'dashboard' ? 'active' : ''} onClick={() => setView({ kind: 'dashboard' })}>Dashboard</button>
        {meta && Object.entries(meta.groups).map(([group, tables]) => (
          <div key={group}>
            <h3>{group}</h3>
            {tables.map(t => (
              <button key={t} className={current === t ? 'active' : ''} onClick={() => setView({ kind: 'table', t })}>{t}</button>
            ))}
          </div>
        ))}
      </nav>
      <main>
        {error && <p className="error" role="alert">{error}</p>}
        {meta && view.kind === 'table' && (
          <TableView key={view.t + (view.editPk ?? '')} t={view.t} meta={meta} editPk={view.editPk}
            onPatient={id => setView({ kind: 'patient', id })} />
        )}
        {view.kind === 'dashboard' && <p className="muted">Dashboard</p>}
        {view.kind === 'patient' && <p className="muted">Patient #{view.id}</p>}
      </main>
    </div>
  )
}
