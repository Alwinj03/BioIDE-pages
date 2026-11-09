import React from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
// @ts-ignore - plotly.js-dist-min has no bundled types
import Plotly from 'plotly.js-dist-min'

const Core = createPlotlyComponent(Plotly)

const FONT = { family: 'Inter, system-ui, sans-serif', size: 11, color: '#94A3B8' }

export const PALETTE = ['#38BDF8', '#34D399', '#A78BFA', '#FBBF24', '#F472B6', '#2DD4BF', '#FB923C', '#818CF8']

export const baseLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: FONT,
  margin: { l: 56, r: 18, t: 28, b: 46 },
  xaxis: { gridcolor: '#1c2941', zerolinecolor: '#263449', linecolor: '#263449', tickfont: FONT, automargin: true },
  yaxis: { gridcolor: '#1c2941', zerolinecolor: '#263449', linecolor: '#263449', tickfont: FONT, automargin: true },
  legend: { font: FONT, bgcolor: 'rgba(0,0,0,0)', orientation: 'h' as const, y: -0.22 },
  hoverlabel: { bgcolor: '#172033', bordercolor: '#263449', font: { ...FONT, color: '#F8FAFC' } },
  colorway: PALETTE,
}

export function Plot({ data, layout, height = 320, config }: {
  data: any[]
  layout?: Record<string, any>
  height?: number
  config?: Record<string, any>
}) {
  return (
    <Core
      data={data}
      layout={{ ...baseLayout, ...layout, height,
                xaxis: { ...baseLayout.xaxis, ...(layout?.xaxis ?? {}) },
                yaxis: { ...baseLayout.yaxis, ...(layout?.yaxis ?? {}) } }}
      config={{ displaylogo: false, responsive: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'], ...config }}
      style={{ width: '100%' }}
      useResizeHandler
    />
  )
}
