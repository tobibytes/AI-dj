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
  
  // Mix persistence
  loadMix: (sessionId: string) => Promise<void>;
  listMixes: () => Promise<MixResult[]>;
  
  // New functionality
  downloadTrack: (track: MixTrack) => void;
  saveMixToLocalStorage: (mix: MixResult) => void;
  loadMixFromLocalStorage: (sessionId: string) => MixResult | null;
  getSavedMixes: () => MixResult[];
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
            // Fetch complete mix data from database
            const fetchMixData = async () => {
              try {
                const mixResponse = await fetch(`${BACKEND_URL}/api/mixes/${sessionId}`);
                if (mixResponse.ok) {
                  const mixData = await mixResponse.json();
                  const tracks = mixData.tracks.map((track: any) => ({
                    spotify_id: track.spotify_id,
                    title: track.title,
                    artist: track.artist,
                    duration_ms: track.duration_ms,
                    bpm: 120, // Default BPM, could be enhanced later
                    key: track.key,
                    energy: track.energy,
                    danceability: track.danceability,
                    transition: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1)?.transition_type
                      ? {
                          type: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1).transition_type,
                          bars: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1).transition_bars,
                          direction: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1).transition_direction,
                        }
                      : { type: "crossfade", bars: 8 }
                  }));

                  setResult({
                    sessionId,
                    cdnUrl: mixData.session.cdn_url || "",
                    durationSeconds: mixData.session.estimated_duration_minutes ? mixData.session.estimated_duration_minutes * 60 : 0,
                    playlist: tracks,
                    targetBpm: 120, // Default BPM
                  });
                } else {
                  // Fallback to websocket data if database fetch fails
                  setResult({
                    sessionId,
                    cdnUrl: message.data.cdn_url || "",
                    durationSeconds: message.data.duration_seconds || 0,
                    playlist,
                    targetBpm,
                  });
                }
              } catch (fetchError) {
                console.error("Failed to fetch mix data from database:", fetchError);
                // Fallback to websocket data
                setResult({
                  sessionId,
                  cdnUrl: message.data.cdn_url || "",
                  durationSeconds: message.data.duration_seconds || 0,
                  playlist,
                  targetBpm,
                });
              }

              setProgress({
                stage: "complete",
                progress: 100,
                detail: "Mix complete!",
              });
              setIsGenerating(false);
              ws.close();
            };

            fetchMixData();
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
  
  const loadMix = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/mixes/${sessionId}`);
      if (!response.ok) {
        throw new Error("Failed to load mix");
      }
      
      const mixData = await response.json();
      const tracks = mixData.tracks.map((track: any) => ({
        spotify_id: track.spotify_id,
        title: track.title,
        artist: track.artist,
        duration_ms: track.duration_ms,
        bpm: 120, // Default BPM
        key: track.key,
        energy: track.energy,
        danceability: track.danceability,
        transition: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1)?.transition_type
          ? {
              type: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1).transition_type,
              bars: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1).transition_bars,
              direction: mixData.transitions.find((t: any) => t.from_track_order === track.track_order - 1).transition_direction,
            }
          : { type: "crossfade", bars: 8 }
      }));

      setResult({
        sessionId,
        cdnUrl: mixData.session.cdn_url || "",
        durationSeconds: mixData.session.estimated_duration_minutes ? mixData.session.estimated_duration_minutes * 60 : 0,
        playlist: tracks,
        targetBpm: 120, // Default BPM
      });
    } catch (e) {
      console.error("Failed to load mix:", e);
      setError("Failed to load mix from database");
    }
  }, []);
  
  const listMixes = useCallback(async (): Promise<MixResult[]> => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/mixes`);
      if (!response.ok) {
        throw new Error("Failed to list mixes");
      }
      
      const sessions = await response.json();
      const mixes: MixResult[] = [];
      
      for (const session of sessions) {
        try {
          const mixResponse = await fetch(`${BACKEND_URL}/api/mixes/${session.id}`);
          if (mixResponse.ok) {
            const mixData = await mixResponse.json();
            const tracks = mixData.tracks.map((track: any) => ({
              spotify_id: track.spotify_id,
              title: track.title,
              artist: track.artist,
              duration_ms: track.duration_ms,
              bpm: 120,
              key: track.key,
              energy: track.energy,
              danceability: track.danceability,
              transition: { type: "crossfade", bars: 8 }
            }));
            
            mixes.push({
              sessionId: session.id,
              cdnUrl: mixData.session.cdn_url || "",
              durationSeconds: mixData.session.estimated_duration_minutes ? mixData.session.estimated_duration_minutes * 60 : 0,
              playlist: tracks,
              targetBpm: 120,
            });
          }
        } catch (e) {
          console.error(`Failed to load mix ${session.id}:`, e);
        }
      }
      
      return mixes;
    } catch (e) {
      console.error("Failed to list mixes:", e);
      return [];
    }
  }, []);
  
  // Download individual track
  const downloadTrack = useCallback((track: MixTrack) => {
    // Try to open Spotify track in browser
    if (track.spotify_id) {
      window.open(`https://open.spotify.com/track/${track.spotify_id}`, '_blank');
    } else {
      // Fallback: search for the track on Spotify
      const searchQuery = encodeURIComponent(`${track.title} ${track.artist}`);
      window.open(`https://open.spotify.com/search/${searchQuery}`, '_blank');
    }
  }, []);
  
  // Save mix to localStorage
  const saveMixToLocalStorage = useCallback((mix: MixResult) => {
    try {
      const savedMixes = JSON.parse(localStorage.getItem('savedMixes') || '[]');
      const existingIndex = savedMixes.findIndex((m: MixResult) => m.sessionId === mix.sessionId);
      
      if (existingIndex >= 0) {
        savedMixes[existingIndex] = mix;
      } else {
        savedMixes.push(mix);
      }
      
      localStorage.setItem('savedMixes', JSON.stringify(savedMixes));
    } catch (e) {
      console.error('Failed to save mix to localStorage:', e);
    }
  }, []);
  
  // Load mix from localStorage
  const loadMixFromLocalStorage = useCallback((sessionId: string): MixResult | null => {
    try {
      const savedMixes = JSON.parse(localStorage.getItem('savedMixes') || '[]');
      return savedMixes.find((mix: MixResult) => mix.sessionId === sessionId) || null;
    } catch (e) {
      console.error('Failed to load mix from localStorage:', e);
      return null;
    }
  }, []);
  
  // Get all saved mixes from localStorage
  const getSavedMixes = useCallback((): MixResult[] => {
    try {
      return JSON.parse(localStorage.getItem('savedMixes') || '[]');
    } catch (e) {
      console.error('Failed to get saved mixes from localStorage:', e);
      return [];
    }
  }, []);
  
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
        loadMix,
        listMixes,
        downloadTrack,
        saveMixToLocalStorage,
        loadMixFromLocalStorage,
        getSavedMixes,
      }}
    >
      {children}
    </MixContext.Provider>
  );
}
