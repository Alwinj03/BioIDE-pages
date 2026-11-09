import React, { useEffect, useRef, useState } from 'react'

/** 3Dmol.js viewer. Loaded lazily so the main bundle stays small, and it reports
 *  a load failure rather than showing an empty box. */
export function StructureViewer({ pdb, style = 'cartoon', colour = 'spectrum', height = 400 }: {
  pdb: string
  style?: 'cartoon' | 'stick' | 'sphere'
  colour?: 'spectrum' | 'bfactor' | 'chain'
  height?: number
}) {
  const host = useRef<HTMLDivElement>(null)
  const viewer = useRef<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const mod: any = await import('3dmol/build/3Dmol.js')
        const $3Dmol = mod.default ?? mod ?? (window as any).$3Dmol
        if (cancelled || !host.current) return
        host.current.innerHTML = ''
        viewer.current = $3Dmol.createViewer(host.current, { backgroundColor: '#0B1020', antialias: true })
        setReady(true)
      } catch (e: any) {
        setError(`The 3D viewer could not load: ${e?.message ?? e}. The parsed numbers above are unaffected.`)
      }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const v = viewer.current
    if (!v || !ready || !pdb) return
    try {
      v.clear()
      v.addModel(pdb, 'pdb')
      const spec: any =
        colour === 'bfactor'
          ? { colorscheme: { prop: 'b', gradient: 'roygb', min: 0, max: 80 } }
          : colour === 'chain' ? { colorscheme: 'chain' } : { color: 'spectrum' }
      if (style === 'cartoon') v.setStyle({}, { cartoon: spec, stick: { radius: 0.08, ...spec } })
      else if (style === 'stick') v.setStyle({}, { stick: { radius: 0.16, ...spec } })
      else v.setStyle({}, { sphere: { scale: 0.32, ...spec } })
      // Ligands and modified residues in green; waters hidden, since they obscure the fold.
      v.setStyle({ hetflag: true, resn: ['HOH', 'WAT', 'DOD'], invert: true },
                 { stick: { radius: 0.2, colorscheme: 'greenCarbon' },
                   sphere: { scale: 0.22, colorscheme: 'greenCarbon' } })
      v.setStyle({ resn: ['HOH', 'WAT', 'DOD'] }, {})
      v.zoomTo()
      v.render()
    } catch (e: any) {
      setError(`Rendering failed: ${e?.message ?? e}`)
    }
  }, [pdb, style, colour, ready])

  if (error) {
    return (
      <div className="rounded-lg border border-amber-500/40 bg-amber-500/[0.06] p-3 text-[11.5px] leading-relaxed text-amber-100/80">
        {error}
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-lg border border-line bg-bg" style={{ height }}>
      <div ref={host} className="absolute inset-0" />
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">
          loading the 3D viewer…
        </div>
      )}
    </div>
  )
}
