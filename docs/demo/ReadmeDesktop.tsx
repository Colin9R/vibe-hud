import { useEffect } from 'react'
import AgentWindows from './demo/AgentWindows'
import DemoDock from './demo/DemoDock'
import { createDemoSessions } from '../config/demo'
import { useTimeStore } from '../stores/time'

// Static scenery only. The original GIF supplies every HUD frame and transition.
const agents = new Set<'claude' | 'codex'>(['claude'])
const openApps = new Set<'finder' | 'terminal' | 'vibehud'>(['finder', 'terminal', 'vibehud'])
const sessions = createDemoSessions().filter(({ source }) => source === 'claude')
const ignore = () => {}

export default function ReadmeDesktop() {
  useEffect(() => {
    useTimeStore.setState({ now: new Date(2026, 9, 23, 9, 41) })
  }, [])

  return (
    <main className="readme-stage" aria-label="README desktop scenery">
      <div className="readme-device macbook-frame border border-zinc-600 bg-zinc-800 shadow-mac-frame">
        <div className="macbook-bezel bg-black">
          <div className="macbook-screen relative isolate overflow-hidden bg-stone-900">
            <img className="pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover" src="/background.svg" alt="" draggable={false} />
            <div className="mac-desktop absolute inset-0">
              <AgentWindows openAgents={agents} activeAgent="claude" sessions={sessions}
                terminalExpanded={false} codexExpanded={false} terminalDraft="" onDraftChange={ignore}
                onExpandTerminal={ignore} onExpandCodex={ignore} onClose={ignore} onActivate={ignore} />
              <DemoDock isReady activeApp="terminal" openApps={openApps} launch={null} onOpen={ignore} />
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
