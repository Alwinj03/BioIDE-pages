import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'

export type AsyncState<T> = {
  data: T | null
  error: string | null
  loading: boolean
  run: (...args: any[]) => Promise<T | null>
  reset: () => void
  elapsed: number | null
}

/** Wraps an async call so every caller renders loading, error and timing the same way.
 *  Errors are shown verbatim: the backend's message is the honest explanation. */
export function useAsync<T>(fn: (...args: any[]) => Promise<T>, immediate = false, deps: any[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState<number | null>(null)
  const alive = useRef(true)
  const latest = useRef(0)

  useEffect(() => () => { alive.current = false }, [])

  const run = useCallback(async (...args: any[]) => {
    const token = ++latest.current
    setLoading(true)
    setError(null)
    const t0 = performance.now()
    try {
      const out = await fn(...args)
      if (!alive.current || token !== latest.current) return null
      setData(out)
      setElapsed((performance.now() - t0) / 1000)
      return out
    } catch (e) {
      if (!alive.current || token !== latest.current) return null
      setError(e instanceof ApiError ? e.detail : e instanceof Error ? e.message : String(e))
      setElapsed((performance.now() - t0) / 1000)
      return null
    } finally {
      if (alive.current && token === latest.current) setLoading(false)
    }
  }, deps)

  useEffect(() => { if (immediate) void run() }, [immediate, run])

  const reset = useCallback(() => { setData(null); setError(null); setElapsed(null) }, [])
  return { data, error, loading, run, reset, elapsed }
}
