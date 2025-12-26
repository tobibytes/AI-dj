"use client"

import { RefObject, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Play, Pause, SkipForward, SkipBack } from "lucide-react"

interface TurntableProps {
  side: "left" | "right"
  trackName?: string
  artist?: string
  track: string;
  togglePlay: () => void;
  audioRef: RefObject<HTMLAudioElement | null>
  onSkipForward?: () => void
  onSkipBack?: () => void
}

export function Turntable({ side, trackName = "Track Name", artist = "Artist Name", track, togglePlay, audioRef, onSkipBack, onSkipForward }: TurntableProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [bpm, setBpm] = useState(128)

  return (
    <div className="flex flex-col items-center space-y-6 p-8">
      {/* Turntable Platter */}
      <div className="relative">
        {/* Outer Ring */}
        <div className="w-80 h-80 rounded-full bg-secondary border-4 border-border shadow-2xl relative overflow-hidden">
          {/* Vinyl Record */}
          <div
            className={`absolute inset-4 rounded-full bg-gradient-to-br from-gray-900 via-gray-800 to-black border-2 border-gray-700 ${
              isPlaying ? "vinyl-spin" : ""
            }`}
          >
            {/* Record Label */}
            <div className="absolute inset-1/3 rounded-full bg-primary flex items-center justify-center">
              <div className="text-center">
                <div className="text-xs font-bold text-primary-foreground mb-1">DJ SET</div>
                <div className="w-4 h-4 rounded-full bg-background mx-auto"></div>
              </div>
            </div>

            {/* Vinyl Grooves */}
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="absolute rounded-full border border-gray-600 opacity-30"
                style={{
                  top: `${10 + i * 8}%`,
                  left: `${10 + i * 8}%`,
                  right: `${10 + i * 8}%`,
                  bottom: `${10 + i * 8}%`,
                }}
              />
            ))}
          </div>

          {/* Tonearm */}
          <div className="absolute top-8 right-8 w-32 h-1 bg-muted-foreground rounded-full origin-right transform rotate-45 shadow-lg">
            <div className="absolute right-0 w-3 h-3 bg-primary rounded-full -translate-y-1"></div>
          </div>
        </div>
      </div>

      {/* Track Info Display */}
      <div className="bg-card border border-border rounded-lg p-4 w-80 text-center">
        <div className="text-sm text-muted-foreground mb-1">NOW PLAYING</div>
        <div className="font-bold text-lg text-foreground truncate">{trackName}</div>
        <div className="text-muted-foreground truncate">{artist}</div>
        <div className="text-xs text-primary mt-2">{bpm} BPM</div>
      </div>

      {/* Transport Controls */}
      <div className="flex items-center space-x-4">
        <Button variant="outline" size="icon" className="rounded-full bg-transparent" onClick={onSkipBack}>
          <SkipBack className="h-4 w-4" />
        </Button>

        <Button onClick={togglePlay} size="icon" className="rounded-full w-12 h-12 bg-primary hover:bg-primary/90">
          {isPlaying ? <Pause className="h-6 w-6" /> : <Play className="h-6 w-6 ml-1" />}
        </Button>
        <Button variant="outline" size="icon" className="rounded-full bg-transparent" onClick={onSkipForward}>
          <SkipForward className="h-4 w-4" />
        </Button>
      </div>
      
        <audio 
            className="hidden" 
            ref={audioRef}
            src={track} 
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)} 
            onEnded={() => setIsPlaying(false)}
            />
     
    </div>
  )
}
