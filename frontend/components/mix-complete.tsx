"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useMix, MixTrack } from "@/lib/mix-context";
import {
  Download,
  Play,
  Pause,
  RotateCcw,
  Music,
  Clock,
  Gauge,
  Copy,
  Check,
  SkipBack,
  SkipForward,
} from "lucide-react";

// Mini turntable component for the mix player
function MiniTurntable({ 
  isPlaying, 
  trackName, 
  artist,
  side 
}: { 
  isPlaying: boolean; 
  trackName: string; 
  artist: string;
  side: "left" | "right";
}) {
  return (
    <div className="flex flex-col items-center">
      {/* Turntable */}
      <div className="relative">
        <div className="w-40 h-40 rounded-full bg-secondary border-2 border-border shadow-lg relative overflow-hidden">
          {/* Vinyl Record */}
          <div
            className={`absolute inset-2 rounded-full bg-gradient-to-br from-gray-900 via-gray-800 to-black border border-gray-700 ${
              isPlaying ? "vinyl-spin" : ""
            }`}
          >
            {/* Record Label */}
            <div className="absolute inset-1/3 rounded-full bg-primary flex items-center justify-center">
              <div className="text-center">
                <div className="text-[8px] font-bold text-primary-foreground">DJ</div>
                <div className="w-2 h-2 rounded-full bg-background mx-auto mt-0.5"></div>
              </div>
            </div>
            {/* Vinyl Grooves */}
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="absolute rounded-full border border-gray-600 opacity-20"
                style={{
                  top: `${12 + i * 10}%`,
                  left: `${12 + i * 10}%`,
                  right: `${12 + i * 10}%`,
                  bottom: `${12 + i * 10}%`,
                }}
              />
            ))}
          </div>
          {/* Tonearm */}
          <div 
            className={`absolute top-4 ${side === "left" ? "right-4" : "left-4"} w-16 h-0.5 bg-muted-foreground rounded-full origin-right shadow transition-transform ${
              isPlaying ? "rotate-[30deg]" : "rotate-[45deg]"
            }`}
          >
            <div className="absolute right-0 w-2 h-2 bg-primary rounded-full -translate-y-0.5"></div>
          </div>
        </div>
      </div>
      {/* Track info */}
      <div className="mt-2 text-center max-w-40">
        <p className="text-xs font-medium truncate">{trackName}</p>
        <p className="text-xs text-muted-foreground truncate">{artist}</p>
      </div>
    </div>
  );
}

export function MixComplete() {
  const { result, resetMix } = useMix();
  const [isPlaying, setIsPlaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [currentTrackIndex, setCurrentTrackIndex] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  
  if (!result) return null;
  
  const { cdnUrl, durationSeconds, playlist, targetBpm } = result;
  
  // Estimate which track is playing based on current time
  // Assume ~60 seconds per track segment in the mix
  const estimatedTrackDuration = durationSeconds / playlist.length;
  
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    
    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
      // Estimate current track based on time
      const estimatedIndex = Math.min(
        Math.floor(audio.currentTime / estimatedTrackDuration),
        playlist.length - 1
      );
      setCurrentTrackIndex(estimatedIndex);
    };
    
    audio.addEventListener("timeupdate", handleTimeUpdate);
    return () => audio.removeEventListener("timeupdate", handleTimeUpdate);
  }, [estimatedTrackDuration, playlist.length]);
  
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };
  
  const handlePlayPause = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };
  
  const handleSkipBack = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 30);
  };
  
  const handleSkipForward = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = Math.min(durationSeconds, audioRef.current.currentTime + 30);
  };
  
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = Number(e.target.value);
  };
  
  const handleCopyLink = async () => {
    await navigator.clipboard.writeText(cdnUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const handleDownload = () => {
    const link = document.createElement("a");
    link.href = cdnUrl;
    link.download = `ai-dj-mix-${Date.now()}.mp3`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  
  // Get current and next tracks for turntable display
  const currentTrack = playlist[currentTrackIndex] || playlist[0];
  const nextTrack = playlist[Math.min(currentTrackIndex + 1, playlist.length - 1)] || currentTrack;
  
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary/20 to-purple-500/20 p-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-primary rounded-lg flex items-center justify-center">
            <Music className="w-8 h-8 text-primary-foreground" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold">Your AI Mix is Ready!</h3>
            <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {formatDuration(durationSeconds)}
              </span>
              <span className="flex items-center gap-1">
                <Gauge className="w-4 h-4" />
                {targetBpm} BPM
              </span>
              <span className="flex items-center gap-1">
                <Music className="w-4 h-4" />
                {playlist.length} tracks
              </span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Dual Turntables */}
      <div className="p-6 bg-gradient-to-b from-background to-muted/30 border-b border-border">
        <div className="flex justify-center items-start gap-8">
          {/* Left Turntable - Current Track */}
          <div className="flex flex-col items-center">
            <div className="text-xs text-muted-foreground mb-2 font-medium">DECK A</div>
            <MiniTurntable 
              isPlaying={isPlaying} 
              trackName={currentTrack?.title || "---"}
              artist={currentTrack?.artist || "---"}
              side="left"
            />
          </div>
          
          {/* Center Controls */}
          <div className="flex flex-col items-center justify-center gap-3 py-8">
            <div className="text-xs text-muted-foreground font-medium">MIXER</div>
            
            {/* BPM Display */}
            <div className="bg-background border border-border rounded px-3 py-1">
              <span className="text-lg font-mono font-bold text-primary">{targetBpm}</span>
              <span className="text-xs text-muted-foreground ml-1">BPM</span>
            </div>
            
            {/* Transport Controls */}
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="icon" 
                className="rounded-full w-10 h-10"
                onClick={handleSkipBack}
              >
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button 
                size="icon" 
                className="rounded-full w-14 h-14 bg-primary hover:bg-primary/90"
                onClick={handlePlayPause}
              >
                {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-0.5" />}
              </Button>
              <Button 
                variant="outline" 
                size="icon" 
                className="rounded-full w-10 h-10"
                onClick={handleSkipForward}
              >
                <SkipForward className="w-4 h-4" />
              </Button>
            </div>
            
            {/* Track counter */}
            <div className="text-xs text-muted-foreground">
              Track {currentTrackIndex + 1} / {playlist.length}
            </div>
          </div>
          
          {/* Right Turntable - Next Track */}
          <div className="flex flex-col items-center">
            <div className="text-xs text-muted-foreground mb-2 font-medium">DECK B</div>
            <MiniTurntable 
              isPlaying={isPlaying} 
              trackName={nextTrack?.title || "---"}
              artist={nextTrack?.artist || "---"}
              side="right"
            />
          </div>
        </div>
      </div>
      
      {/* Waveform & Seek */}
      <div className="p-6 border-b border-border">
        <audio
          ref={audioRef}
          src={cdnUrl}
          onEnded={() => setIsPlaying(false)}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          className="hidden"
        />
        
        <div className="space-y-3">
          {/* Waveform visualization */}
          <div className="h-16 bg-muted rounded-lg flex items-center justify-center overflow-hidden relative">
            {/* Progress overlay */}
            <div 
              className="absolute left-0 top-0 bottom-0 bg-primary/20 transition-all"
              style={{ width: `${(currentTime / durationSeconds) * 100}%` }}
            />
            {/* Waveform bars */}
            <div className="flex items-end gap-0.5 h-full py-2 relative z-10">
              {Array.from({ length: 80 }).map((_, i) => {
                const progress = (currentTime / durationSeconds) * 100;
                const barPosition = (i / 80) * 100;
                const isPlayed = barPosition < progress;
                return (
                  <div
                    key={i}
                    className={`w-1 rounded-full transition-all ${
                      isPlayed ? "bg-primary" : "bg-primary/30"
                    }`}
                    style={{
                      height: `${20 + Math.sin(i * 0.3) * 30 + Math.sin(i * 0.7) * 20}%`,
                    }}
                  />
                );
              })}
            </div>
          </div>
          
          {/* Seek slider */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono w-12">
              {formatDuration(currentTime)}
            </span>
            <input
              type="range"
              min="0"
              max={durationSeconds}
              value={currentTime}
              onChange={handleSeek}
              className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <span className="text-xs text-muted-foreground font-mono w-12 text-right">
              {formatDuration(durationSeconds)}
            </span>
          </div>
        </div>
        
        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 mt-4">
          <Button onClick={handleDownload}>
            <Download className="w-4 h-4 mr-2" />
            Download MP3
          </Button>
          <Button variant="outline" onClick={handleCopyLink}>
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copy Link
              </>
            )}
          </Button>
          <Button variant="outline" onClick={resetMix}>
            <RotateCcw className="w-4 h-4 mr-2" />
            New Mix
          </Button>
        </div>
      </div>
      
      {/* Tracklist */}
      <div className="p-6">
        <h4 className="font-medium mb-4">Tracklist</h4>
        <div className="space-y-2">
          {playlist.map((track, index) => (
            <TrackItem 
              key={track.spotify_id} 
              track={track} 
              index={index} 
              isLast={index === playlist.length - 1}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function TrackItem({ track, index, isLast }: { track: MixTrack; index: number; isLast: boolean }) {
  const transitionLabels: Record<string, string> = {
    crossfade: "Crossfade",
    echo_out: "Echo Out",
    filter_sweep: "Filter Sweep",
    backspin: "Backspin",
  };
  
  return (
    <div className="flex items-center gap-3 p-3 bg-background rounded-lg border border-border">
      <div className="w-8 h-8 bg-muted rounded flex items-center justify-center text-sm font-medium text-muted-foreground">
        {index + 1}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{track.title}</p>
        <p className="text-sm text-muted-foreground truncate">{track.artist}</p>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="px-2 py-0.5 bg-muted rounded">{Math.round(track.bpm)} BPM</span>
        <span className="px-2 py-0.5 bg-muted rounded">{track.key}</span>
        {!isLast && track.transition && (
          <span className="px-2 py-0.5 bg-primary/20 text-primary rounded">
            → {transitionLabels[track.transition.type] || track.transition.type}
          </span>
        )}
      </div>
    </div>
  );
}
