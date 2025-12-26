"use client";

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";

// Types
export interface MixTrack {
  spotify_id: string;
  title: string;
  artist: string;
  duration_ms: number;
  bpm: number;
  key: string;
  energy: number;
  danceability: number;
  transition: {
    type: string;
    bars: number;
    direction?: string;
  };
}

export interface MixProgress {
  stage: "idle" | "interpreting" | "fetching" | "downloading" | "analyzing" | "rendering" | "uploading" | "complete" | "error";
  progress: number;
  detail: string;
  source?: string;
  currentTrack?: string;
}

export interface MixResult {
  sessionId: string;
  cdnUrl: string;
  durationSeconds: number;
  playlist: MixTrack[];
  targetBpm: number;
}

interface MixContextType {
  // Spotify auth
  isSpotifyConnected: boolean;
  spotifyAccessToken: string | null;
  connectSpotify: () => void;
  disconnectSpotify: () => void;
  
  // Mix generation
  isGenerating: boolean;
  progress: MixProgress;
  result: MixResult | null;
  error: string | null;
  generateMix: (prompt: string, durationMinutes?: number) => Promise<void>;
  cancelMix: () => void;
  resetMix: () => void;
}

const MixContext = createContext<MixContextType | null>(null);

export function useMix() {
  const context = useContext(MixContext);
  if (!context) {
    throw new Error("useMix must be used within a MixProvider");
  }
  return context;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function MixProvider({ children }: { children: React.ReactNode }) {
  // Spotify auth state
  const [isSpotifyConnected, setIsSpotifyConnected] = useState(false);
  const [spotifyAccessToken, setSpotifyAccessToken] = useState<string | null>(null);
  
  // Mix generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<MixProgress>({
    stage: "idle",
    progress: 0,
    detail: "",
  });
  const [result, setResult] = useState<MixResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // WebSocket ref
  const wsRef = useRef<WebSocket | null>(null);
  
  // Fetch token from backend using session ID
  const fetchTokenFromSession = async (sessionId: string): Promise<string | null> => {
    try {
      const response = await fetch(`${BACKEND_URL}/spotify/token?session_id=${sessionId}`);
      if (!response.ok) return null;
      const data = await response.json();
      return data.access_token || null;
    } catch {
      return null;
    }
  };
  
  // Load saved tokens on mount and auto-connect
  useEffect(() => {
    const initAuth = async () => {
      if (typeof window === "undefined") return;
      
      const params = new URLSearchParams(window.location.search);
      const spotifySession = params.get("spotify_session");
      
      // If we have a session from OAuth redirect, fetch the token securely
      if (spotifySession) {
        const token = await fetchTokenFromSession(spotifySession);
        if (token) {
          setSpotifyAccessToken(token);
          setIsSpotifyConnected(true);
          localStorage.setItem("spotify_access_token", token);
          localStorage.setItem("spotify_session", spotifySession);
        }
        // Clean URL (remove session from URL bar)
        window.history.replaceState({}, "", window.location.pathname);
      } else {
        // Try to load from localStorage first
        const savedToken = localStorage.getItem("spotify_access_token");
        if (savedToken) {
          setSpotifyAccessToken(savedToken);
          setIsSpotifyConnected(true);
        } else {
          // Auto-connect using Client Credentials (no user action needed)
          try {
            const response = await fetch(`${BACKEND_URL}/spotify/auto-auth`);
            if (response.ok) {
              const data = await response.json();
              if (data.access_token) {
                setSpotifyAccessToken(data.access_token);
                setIsSpotifyConnected(true);
                localStorage.setItem("spotify_access_token", data.access_token);
                if (data.session_id) {
                  localStorage.setItem("spotify_session", data.session_id);
                }
              }
            }
          } catch (err) {
            console.log("Auto-connect failed, user will need to connect manually");
          }
        }
      }
    };
    
    initAuth();
  }, []);
  
  const connectSpotify = useCallback(async () => {
    // Use auto-auth (Client Credentials flow) - no user login needed
    try {
      const response = await fetch(`${BACKEND_URL}/spotify/auto-auth`);
      if (!response.ok) {
        throw new Error("Failed to connect to Spotify");
      }
      const data = await response.json();
      
      if (data.access_token) {
        setSpotifyAccessToken(data.access_token);
        setIsSpotifyConnected(true);
        localStorage.setItem("spotify_access_token", data.access_token);
        if (data.session_id) {
          localStorage.setItem("spotify_session", data.session_id);
        }
      }
    } catch (err) {
      console.error("Auto-auth failed, falling back to OAuth:", err);
      // Fallback to full OAuth if auto-auth fails
      window.location.href = `${BACKEND_URL}/spotify/auth`;
    }
  }, []);
  
  const disconnectSpotify = useCallback(() => {
    setSpotifyAccessToken(null);
    setIsSpotifyConnected(false);
    localStorage.removeItem("spotify_access_token");
    localStorage.removeItem("spotify_session");
  }, []);
  
  const cancelMix = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsGenerating(false);
    setProgress({ stage: "idle", progress: 0, detail: "" });
  }, []);
  
  const resetMix = useCallback(() => {
    setResult(null);
    setError(null);
    setProgress({ stage: "idle", progress: 0, detail: "" });
  }, []);
  
  // SSE fallback - defined before generateMix since it's used there
  const fallbackToSSE = useCallback((sessionId: string, playlist: MixTrack[], targetBpm: number) => {
    const eventSource = new EventSource(`${BACKEND_URL}/sse/mix/${sessionId}`);
    
    eventSource.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.type === "progress") {
          const progressData = message.data;
          setProgress({
            stage: progressData.stage || "fetching",
            progress: progressData.progress || 0,
            detail: progressData.detail || "",
            source: progressData.source,
          });
        } else if (message.type === "complete") {
          const completeData = message.data;
          setResult({
            sessionId,
            cdnUrl: completeData.cdn_url,
            durationSeconds: completeData.duration_seconds || 0,
            playlist,
            targetBpm,
          });
          setProgress({
            stage: "complete",
            progress: 100,
            detail: "Mix complete!",
          });
          setIsGenerating(false);
          eventSource.close();
        } else if (message.type === "error") {
          setError(message.data.error || "An error occurred");
          setIsGenerating(false);
          eventSource.close();
        }
      } catch (e) {
        console.error("Failed to parse SSE message:", e);
      }
    };
    
    eventSource.onerror = () => {
      setError("Lost connection to progress stream");
      setIsGenerating(false);
      eventSource.close();
    };
  }, []);
  
  const generateMix = useCallback(async (prompt: string, durationMinutes?: number) => {
    if (!spotifyAccessToken) {
      setError("Please connect your Spotify account first");
      return;
    }
    
    setIsGenerating(true);
    setError(null);
    setResult(null);
    setProgress({ stage: "interpreting", progress: 0, detail: "Starting..." });
    
    try {
      // Call the generate-mix endpoint
      const response = await fetch(`${BACKEND_URL}/mix/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${spotifyAccessToken}`,
        },
        body: JSON.stringify({
          prompt,
          duration_minutes: durationMinutes,
          spotify_access_token: spotifyAccessToken,
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to start mix generation");
      }
      
      const data = await response.json();
      const sessionId = data.session_id;
      
      // Store initial playlist data
      const playlist = data.playlist as MixTrack[];
      const targetBpm = data.target_bpm;
      
      // Connect to WebSocket for progress updates
      const wsUrl = `${BACKEND_URL.replace("http", "ws")}/ws/mix/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log("WebSocket connected for session:", sessionId);
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === "connected") {
            setProgress({
              stage: "fetching",
              progress: 0,
              detail: "Connected to progress stream",
            });
          } else if (message.type === "progress") {
            const progressData = message.data;
            setProgress({
              stage: progressData.stage || "fetching",
              progress: progressData.progress || 0,
              detail: progressData.detail || "",
              source: progressData.source,
              currentTrack: progressData.current_track,
            });
          } else if (message.type === "complete") {
            const completeData = message.data;
            setResult({
              sessionId,
              cdnUrl: completeData.cdn_url,
              durationSeconds: completeData.duration_seconds || 0,
              playlist,
              targetBpm,
            });
            setProgress({
              stage: "complete",
              progress: 100,
              detail: "Mix complete!",
            });
            setIsGenerating(false);
            ws.close();
          } else if (message.type === "error") {
            setError(message.data.error || "An error occurred");
            setProgress({
              stage: "error",
              progress: 0,
              detail: message.data.error || "An error occurred",
            });
            setIsGenerating(false);
            ws.close();
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };
      
      ws.onerror = (e) => {
        console.error("WebSocket error:", e);
        // Try SSE fallback
        fallbackToSSE(sessionId, playlist, targetBpm);
      };
      
      ws.onclose = () => {
        console.log("WebSocket closed");
        wsRef.current = null;
      };
      
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Failed to generate mix";
      setError(errorMessage);
      setProgress({ stage: "error", progress: 0, detail: errorMessage });
      setIsGenerating(false);
    }
  }, [spotifyAccessToken, fallbackToSSE]);
  
  return (
    <MixContext.Provider
      value={{
        isSpotifyConnected,
        spotifyAccessToken,
        connectSpotify,
        disconnectSpotify,
        isGenerating,
        progress,
        result,
        error,
        generateMix,
        cancelMix,
        resetMix,
      }}
    >
      {children}
    </MixContext.Provider>
  );
}
