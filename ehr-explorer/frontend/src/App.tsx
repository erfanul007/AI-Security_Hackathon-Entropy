import { useEffect, useState } from 'react'
import { type Meta, get, send } from './api'
import Dashboard from './Dashboard'
import PatientDetail from './PatientDetail'
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
  const [epoch, setEpoch] = useState(0) // bumped on env switch so every view refetches

  useEffect(() => {
    get<Meta>('/api/meta').then(setMeta, e => setError(e.message))
    get<{ env: string }>('/api/env').then(d => setEnv(d.env), () => {})
  }, [])

  async function switchEnv(next: string) {
    try {
      const d = await send<{ env: string }>('PUT', '/api/env', { env: next })
      setEnv(d.env)
      if (view.kind === 'patient') setView({ kind: 'dashboard' }) // that patient id may not exist in the other DB
      setEpoch(n => n + 1)
      setError('')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const current = view.kind === 'table' ? view.t : view.kind

  return (
    <div className="app">
      <header className="topbar">
        <strong>EHR Explorer</strong>
        {env && (
          <select className={`badge ${env}`} value={env} onChange={e => switchEnv(e.target.value)} aria-label="Database">
            <option value="demo">DEMO</option>
            <option value="prod">PROD</option>
          </select>
        )}
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
      <main key={epoch}>
        {error && <p className="error" role="alert">{error}</p>}
        {meta && view.kind === 'table' && (
          <TableView key={view.t + (view.editPk ?? '')} t={view.t} meta={meta} editPk={view.editPk}
            onPatient={id => setView({ kind: 'patient', id })} />
        )}
        {view.kind === 'dashboard' && <Dashboard />}
        {view.kind === 'patient' && (
          <PatientDetail key={view.id} id={view.id} onEdit={(t, editPk) => setView({ kind: 'table', t, editPk })} />
        )}
      </main>
    </div>
  )
}
