"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Volume2, Headphones } from "lucide-react"

export function DJMixer() {
  const [crossfader, setCrossfader] = useState(50)
  const [leftGain, setLeftGain] = useState(75)
  const [rightGain, setRightGain] = useState(75)
  const [leftEQHigh, setLeftEQHigh] = useState(50)
  const [leftEQMid, setLeftEQMid] = useState(50)
  const [leftEQLow, setLeftEQLow] = useState(50)
  const [rightEQHigh, setRightEQHigh] = useState(50)
  const [rightEQMid, setRightEQMid] = useState(50)
  const [rightEQLow, setRightEQLow] = useState(50)

  return (
    <div className="bg-card border border-border rounded-lg p-6 mx-8">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold text-primary">DJ MIXER</h2>
      </div>

      <div className="grid grid-cols-2 gap-8">
        {/* Left Channel */}
        <div className="space-y-4">
          <div className="text-center text-sm font-semibold text-muted-foreground">DECK A</div>

          {/* EQ Controls */}
          <div className="space-y-3">
            <div>
              <div className="text-xs text-muted-foreground mb-1">HIGH</div>
              <input
                type="range"
                min="0"
                max="100"
                value={leftEQHigh}
                onChange={(e) => setLeftEQHigh(Number.parseInt(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">MID</div>
              <input
                type="range"
                min="0"
                max="100"
                value={leftEQMid}
                onChange={(e) => setLeftEQMid(Number.parseInt(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">LOW</div>
              <input
                type="range"
                min="0"
                max="100"
                value={leftEQLow}
                onChange={(e) => setLeftEQLow(Number.parseInt(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>

          {/* Gain Control */}
          <div>
            <div className="text-xs text-muted-foreground mb-1">GAIN</div>
            <input
              type="range"
              min="0"
              max="100"
              value={leftGain}
              onChange={(e) => setLeftGain(Number.parseInt(e.target.value))}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Cue Button */}
          <Button variant="outline" size="sm" className="w-full bg-transparent">
            <Headphones className="h-4 w-4 mr-2" />
            CUE
          </Button>
        </div>

        {/* Right Channel */}
        <div className="space-y-4">
          <div className="text-center text-sm font-semibold text-muted-foreground">DECK B</div>

          {/* EQ Controls */}
          <div className="space-y-3">
            <div>
              <div className="text-xs text-muted-foreground mb-1">HIGH</div>
              <input
                type="range"
                min="0"
                max="100"
                value={rightEQHigh}
                onChange={(e) => setRightEQHigh(Number.parseInt(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">MID</div>
              <input
                type="range"
                min="0"
                max="100"
                value={rightEQMid}
                onChange={(e) => setRightEQMid(Number.parseInt(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">LOW</div>
              <input
                type="range"
                min="0"
                max="100"
                value={rightEQLow}
                onChange={(e) => setRightEQLow(Number.parseInt(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>

          {/* Gain Control */}
          <div>
            <div className="text-xs text-muted-foreground mb-1">GAIN</div>
            <input
              type="range"
              min="0"
              max="100"
              value={rightGain}
              onChange={(e) => setRightGain(Number.parseInt(e.target.value))}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Cue Button */}
          <Button variant="outline" size="sm" className="w-full bg-transparent">
            <Headphones className="h-4 w-4 mr-2" />
            CUE
          </Button>
        </div>
      </div>

      {/* Crossfader */}
      <div className="mt-8">
        <div className="text-center text-xs text-muted-foreground mb-2">CROSSFADER</div>
        <div className="relative">
          <input
            type="range"
            min="0"
            max="100"
            value={crossfader}
            onChange={(e) => setCrossfader(Number.parseInt(e.target.value))}
            className="w-full h-3 bg-secondary rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>A</span>
            <span>B</span>
          </div>
        </div>
      </div>

      {/* Master Volume */}
      <div className="mt-6">
        <div className="text-center text-xs text-muted-foreground mb-2">MASTER</div>
        <div className="flex items-center space-x-2">
          <Volume2 className="h-4 w-4 text-muted-foreground" />
          <input
            type="range"
            min="0"
            max="100"
            defaultValue="80"
            className="flex-1 h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>
    </div>
  )
}
