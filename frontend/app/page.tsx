"use client"
import { Turntable } from "@/components/turn-table";
import { DJMixer } from "@/components/dj-mixer";
import { Button } from "@/components/ui/button";
import { useRef, useState } from "react";
import { QueuePanel, type Track } from "@/components/queue-panel";
import nextTracksJson from "@/public/tracks.json";

export default function Home() {
  const track1Ref = useRef<HTMLAudioElement | null>(null);
  const track2Ref = useRef<HTMLAudioElement | null>(null);

  const [crossfader, setCrossfader] = useState(50);

  // Queue data (static for now)
  const nextTracks = nextTracksJson as Track[];
  const recentTracks: Track[] = [];

  // Equal-power volume mapping for both decks from crossfader position t [0..1]
  const updateVolumes = (t: number) => {
    const a = track1Ref.current;
    const b = track2Ref.current;
    if (!a && !b) return;
    const left = Math.cos((t * Math.PI) / 2);  // Deck A
    const right = Math.sin((t * Math.PI) / 2); // Deck B
    if (a) a.volume = left;
    if (b) b.volume = right;
  };

  const handleCrossfaderChange = (value: number) => {
    setCrossfader(value);
    updateVolumes(value / 100);
  };

  // Crossfade actions (no useEffect) -----------------------------------------
  const fadeRAF = useRef<number | null>(null);

  const cancelFade = () => {
    if (fadeRAF.current != null) {
      cancelAnimationFrame(fadeRAF.current);
      fadeRAF.current = null;
    }
  };

  // target: 0 (Deck A) or 1 (Deck B)
  const fadeTo = (target: 0 | 1, durationMs = 2000) => {
    cancelFade();
    const start = crossfader / 100;
    const end = target;
    const startTime = performance.now();
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      const value = start + (end - start) * progress;
      setCrossfader(Math.round(value * 100));
      updateVolumes(value);
      if (progress < 1) {
        fadeRAF.current = requestAnimationFrame(step);
      } else {
        fadeRAF.current = null;
      }
    };
    fadeRAF.current = requestAnimationFrame(step);
  };

  const fadeToA = () => fadeTo(0);
  const fadeToB = () => fadeTo(1);
  const cutToA = () => {
    cancelFade();
    setCrossfader(0);
    updateVolumes(0);
  };
  const cutToB = () => {
    cancelFade();
    setCrossfader(1);
    updateVolumes(1);
  };

  // Existing deck play/pause controls ----------------------------------------
  const toggleTrack1 = () => {
    const audio = track1Ref.current;
    updateVolumes(crossfader / 100);
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {
        /* autoplay blocked or error */
      });
    } else {
      audio.pause();
      console.log(audio.currentTime);
    }
  };

  const toggleTrack2 = () => {
    const audio = track2Ref.current;
    updateVolumes(crossfader / 100);
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {
        /* autoplay blocked or error */
      });
    } else {
      audio.pause();
      console.log(audio.currentTime);
    }
  };

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="flex flex-col lg:flex-row items-start justify-center gap-8">
        {/* Left Turntable */}
        <div className="flex-1 max-w-md">
          <Turntable
            side="left"
            trackName={nextTracks[0].name}
            artist={nextTracks[0].artist}
            togglePlay={toggleTrack1}
            audioRef={track1Ref}
            track={nextTracks[0].url}
          />
        </div>
        {/* Right Turntable */}
        <div className="flex-1 max-w-md">
          <Turntable
            side="right"
            trackName={nextTracks[1].name}
            artist={nextTracks[1].artist}
            togglePlay={toggleTrack2}
            audioRef={track2Ref}
            track={nextTracks[1].url}
          />
        </div>
      </div>

      <div className="mt-8 space-y-4">
        <DJMixer crossfader={crossfader} onCrossfaderChange={handleCrossfaderChange} />
        <div className="flex flex-wrap gap-2 justify-center" aria-label="AI Actions">
          <Button data-action="fade-to-a" variant="outline" onClick={fadeToA}>
            Fade to Deck A (2s)
          </Button>
          <Button data-action="fade-to-b" variant="outline" onClick={fadeToB}>
            Fade to Deck B (2s)
          </Button>
          <Button data-action="cut-to-a" variant="secondary" onClick={cutToA}>
            Cut to Deck A
          </Button>
          <Button data-action="cut-to-b" variant="secondary" onClick={cutToB}>
            Cut to Deck B
          </Button>
        </div>
      </div>

      <div className="mt-8">
        <QueuePanel nextTracks={nextTracks} recentTracks={recentTracks} />
      </div>
      
    </main>
  );
}
