"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useMix } from "@/lib/mix-context";
import { Sparkles, Loader2 } from "lucide-react";

interface PromptInputProps {
  onGenerate?: () => void;
}

export function PromptInput({ onGenerate }: PromptInputProps) {
  const { generateMix, isGenerating, isSpotifyConnected } = useMix();
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(30);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    
    await generateMix(prompt.trim(), duration);
    onGenerate?.();
  };
  
  const isReady = isSpotifyConnected;
  
  const examplePrompts = [
    "30 minute afrobeats party mix, high energy",
    "Chill lo-fi hip hop for studying",
    "2000s R&B throwback vibes",
    "Amapiano sunrise set, build from chill to energetic",
    "EDM festival bangers, peak time energy",
  ];
  
  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="w-5 h-5 text-primary" />
        <h2 className="text-lg font-semibold">AI Mix Generator</h2>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="prompt" className="block text-sm font-medium text-muted-foreground mb-2">
            Describe your perfect mix
          </label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g., 30 minute afrobeats party mix with high energy, featuring Burna Boy and Wizkid vibes..."
            className="w-full h-24 px-4 py-3 bg-background border border-border rounded-lg 
                       text-foreground placeholder:text-muted-foreground
                       focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent
                       resize-none"
            disabled={isGenerating}
          />
        </div>
        
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label htmlFor="duration" className="text-sm text-muted-foreground whitespace-nowrap">
              Duration:
            </label>
            <select
              id="duration"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="px-3 py-2 bg-background border border-border rounded-lg
                         text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={isGenerating}
            >
              <option value={15}>15 min</option>
              <option value={30}>30 min</option>
              <option value={45}>45 min</option>
              <option value={60}>60 min</option>
              <option value={90}>90 min</option>
            </select>
          </div>
          
          <div className="flex-1" />
          
          <Button
            type="submit"
            disabled={!isReady || isGenerating || !prompt.trim()}
            className="min-w-[140px]"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Generate Mix
              </>
            )}
          </Button>
        </div>
        
        {!isReady && (
          <p className="text-sm text-yellow-500">
            ⚠️ Connect Spotify in settings to generate mixes
          </p>
        )}
      </form>
      
      {/* Example prompts */}
      <div className="mt-6 pt-4 border-t border-border">
        <p className="text-sm text-muted-foreground mb-2">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {examplePrompts.map((example, i) => (
            <button
              key={i}
              onClick={() => setPrompt(example)}
              disabled={isGenerating}
              className="text-xs px-3 py-1.5 bg-background border border-border rounded-full
                         text-muted-foreground hover:text-foreground hover:border-primary
                         transition-colors disabled:opacity-50"
            >
              {example.length > 35 ? example.slice(0, 35) + "..." : example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
