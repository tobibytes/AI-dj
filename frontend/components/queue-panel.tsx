"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"

export type Track = {
  artist: string
  name: string
  url: string
}

interface QueuePanelProps {
  nextTracks: Track[]
  recentTracks: Track[]
}

export function QueuePanel({ nextTracks, recentTracks }: QueuePanelProps) {
  const [tab, setTab] = useState<"next" | "recent">("next")
  const tracks = tab === "next" ? nextTracks : recentTracks

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-primary">QUEUE</h3>
        <div className="flex gap-2">
          <Button
            data-action="queue-tab-next"
            variant={tab === "next" ? "secondary" : "outline"}
            size="sm"
            className="bg-transparent"
            onClick={() => setTab("next")}
          >
            Next
          </Button>
          <Button
            data-action="queue-tab-recent"
            variant={tab === "recent" ? "secondary" : "outline"}
            size="sm"
            className="bg-transparent"
            onClick={() => setTab("recent")}
          >
            Recently Played
          </Button>
        </div>
      </div>

      <ul className="divide-y divide-border">
        {tracks.length === 0 ? (
          <li className="py-3 text-sm text-muted-foreground">No tracks</li>
        ) : (
          tracks.map((t, i) => (
            <li key={`${tab}-${i}`} className="py-3">
              <div className="flex flex-col">
                <span className="font-medium text-foreground truncate">{t.name}</span>
                <span className="text-xs text-muted-foreground truncate">{t.artist}</span>
              </div>
            </li>
          ))
        )}
      </ul>
    </div>
  )
}
