"use client";

import { useState } from "react";
import { PromptInput } from "@/components/prompt-input";
import { MixProgress } from "@/components/mix-progress";
import { MixComplete } from "@/components/mix-complete";
import { useMix } from "@/lib/mix-context";
import { Disc3, Sparkles } from "lucide-react";

export default function Home() {
  const { progress, result, error, isGenerating, cancelMix } = useMix();
  
  return (
    <main className="container mx-auto px-4 py-8">
      {/* Hero section */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4">
          <Disc3 className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold mb-2">Create Your Perfect Mix</h2>
        <p className="text-muted-foreground max-w-lg mx-auto">
          Describe the vibe you&apos;re looking for, and our AI DJ will craft a seamless mix
          with professional transitions, matched BPM, and harmonic key mixing.
        </p>
      </div>
      
      {/* Main content area */}
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Prompt input - always visible */}
        <PromptInput />
        
        {/* Error display */}
        {error && (
          <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
            <p className="text-destructive text-sm">{error}</p>
          </div>
        )}
        
        {/* Progress display */}
        {isGenerating && <MixProgress />}
        
        {/* Cancel button while generating */}
        {isGenerating && (
          <div className="flex justify-center">
            <button
              onClick={cancelMix}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel generation
            </button>
          </div>
        )}
        
        {/* Completed mix display */}
        {result && progress.stage === "complete" && <MixComplete />}
        
        {/* Feature highlights */}
        {!isGenerating && !result && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
            <FeatureCard
              icon={<Sparkles className="w-5 h-5" />}
              title="AI-Powered"
              description="GPT understands your mood and genre preferences"
            />
            <FeatureCard
              icon={<Disc3 className="w-5 h-5" />}
              title="Pro Transitions"
              description="Crossfades, echo outs, filter sweeps & backspins"
            />
            <FeatureCard
              icon={
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              }
              title="Harmonic Mixing"
              description="Tracks matched by key using the Camelot wheel"
            />
          </div>
        )}
      </div>
    </main>
  );
}

function FeatureCard({ 
  icon, 
  title, 
  description 
}: { 
  icon: React.ReactNode; 
  title: string; 
  description: string;
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-4 text-center">
      <div className="inline-flex items-center justify-center w-10 h-10 bg-primary/10 text-primary rounded-full mb-3">
        {icon}
      </div>
      <h3 className="font-medium mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
