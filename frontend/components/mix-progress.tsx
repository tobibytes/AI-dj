"use client";

import { useMix } from "@/lib/mix-context";
import { Loader2, Music, Download, Disc3, Wand2, Search, AudioLines, Upload, CheckCircle, XCircle } from "lucide-react";

const STAGE_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  idle: { icon: Disc3, label: "Ready", color: "text-muted-foreground" },
  interpreting: { icon: Wand2, label: "Understanding your request", color: "text-purple-500" },
  fetching: { icon: Search, label: "Finding tracks on Spotify", color: "text-green-500" },
  downloading: { icon: Download, label: "Downloading audio", color: "text-blue-500" },
  analyzing: { icon: AudioLines, label: "Analyzing tracks", color: "text-orange-500" },
  rendering: { icon: Music, label: "Rendering mix", color: "text-pink-500" },
  uploading: { icon: Upload, label: "Uploading to CDN", color: "text-cyan-500" },
  complete: { icon: CheckCircle, label: "Complete!", color: "text-green-500" },
  error: { icon: XCircle, label: "Error", color: "text-red-500" },
};

const STAGE_ORDER = [
  "interpreting",
  "fetching",
  "downloading",
  "analyzing",
  "rendering",
  "uploading",
  "complete",
];

export function MixProgress() {
  const { isGenerating, progress } = useMix();
  
  if (!isGenerating && progress.stage === "idle") {
    return null;
  }
  
  const currentStageIndex = STAGE_ORDER.indexOf(progress.stage);
  const config = STAGE_CONFIG[progress.stage] || STAGE_CONFIG.idle;
  const Icon = config.icon;
  
  return (
    <div className="bg-card border border-border rounded-lg p-6 space-y-4">
      <div className="flex items-center gap-3">
        <div className={`${config.color}`}>
          {progress.stage !== "complete" && progress.stage !== "error" ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : (
            <Icon className="w-6 h-6" />
          )}
        </div>
        <div className="flex-1">
          <h3 className="font-medium">{config.label}</h3>
          {progress.detail && (
            <p className="text-sm text-muted-foreground">{progress.detail}</p>
          )}
        </div>
        {progress.source && (
          <span className={`text-xs px-2 py-1 rounded-full ${
            progress.source === "librespot" 
              ? "bg-green-500/20 text-green-400"
              : "bg-red-500/20 text-red-400"
          }`}>
            {progress.source === "librespot" ? "Spotify" : "YouTube"}
          </span>
        )}
      </div>
      
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ease-out ${
              progress.stage === "error" ? "bg-red-500" : "bg-primary"
            }`}
            style={{ width: `${progress.progress}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{progress.progress}%</span>
          <span>{progress.currentTrack}</span>
        </div>
      </div>
      
      {/* Stage indicators */}
      <div className="flex items-center justify-between pt-2">
        {STAGE_ORDER.slice(0, -1).map((stage, index) => {
          const stageConfig = STAGE_CONFIG[stage];
          const StageIcon = stageConfig.icon;
          const isActive = stage === progress.stage;
          const isComplete = currentStageIndex > index;
          
          return (
            <div
              key={stage}
              className="flex flex-col items-center gap-1"
              title={stageConfig.label}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : isComplete
                    ? "bg-primary/20 text-primary"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {isComplete ? (
                  <CheckCircle className="w-4 h-4" />
                ) : isActive ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <StageIcon className="w-4 h-4" />
                )}
              </div>
              <span
                className={`text-[10px] ${
                  isActive ? "text-primary font-medium" : "text-muted-foreground"
                }`}
              >
                {stage.charAt(0).toUpperCase() + stage.slice(1)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
