"use client";

import { useEffect, useState } from "react";
import { useMix, MixResult } from "@/lib/mix-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, Clock, Music, Download, Save, ExternalLink } from "lucide-react";

export function MixHistory() {
  const { listMixes, loadMix, downloadTrack, saveMixToLocalStorage, getSavedMixes } = useMix();
  const [mixes, setMixes] = useState<MixResult[]>([]);
  const [savedMixes, setSavedMixes] = useState<MixResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMixHistory = async () => {
      try {
        const mixList = await listMixes();
        setMixes(mixList);
        setSavedMixes(getSavedMixes());
      } catch (error) {
        console.error("Failed to load mix history:", error);
      } finally {
        setLoading(false);
      }
    };

    loadMixHistory();
  }, [listMixes, getSavedMixes]);

  const handleLoadMix = async (sessionId: string) => {
    await loadMix(sessionId);
  };

  const handleSaveMix = (mix: MixResult) => {
    saveMixToLocalStorage(mix);
    setSavedMixes(getSavedMixes()); // Refresh the saved mixes list
  };

  const handleDownloadTrack = (track: any) => {
    downloadTrack(track);
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Music className="w-5 h-5" />
            Mix History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Loading your mixes...</p>
        </CardContent>
      </Card>
    );
  }

  if (mixes.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Music className="w-5 h-5" />
            Mix History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No mixes found. Create your first mix above!</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Server Mixes */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Music className="w-5 h-5" />
            Your Mixes ({mixes.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {mixes.length === 0 ? (
            <p className="text-muted-foreground">No mixes found. Create your first mix above!</p>
          ) : (
            <div className="space-y-3">
              {mixes.map((mix) => (
                <MixCard 
                  key={mix.sessionId} 
                  mix={mix} 
                  onLoad={handleLoadMix}
                  onSave={handleSaveMix}
                  onDownloadTrack={handleDownloadTrack}
                  showSaveButton={true}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Saved Mixes */}
      {savedMixes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Save className="w-5 h-5" />
              Saved Mixes ({savedMixes.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {savedMixes.map((mix) => (
                <MixCard 
                  key={mix.sessionId} 
                  mix={mix} 
                  onLoad={handleLoadMix}
                  onSave={handleSaveMix}
                  onDownloadTrack={handleDownloadTrack}
                  showSaveButton={false}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Helper component for mix cards
function MixCard({ 
  mix, 
  onLoad, 
  onSave, 
  onDownloadTrack, 
  showSaveButton 
}: { 
  mix: MixResult; 
  onLoad: (sessionId: string) => void;
  onSave: (mix: MixResult) => void;
  onDownloadTrack: (track: any) => void;
  showSaveButton: boolean;
}) {
  return (
    <div className="border rounded-lg p-3 hover:bg-muted/50 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Music className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium text-sm">
            {mix.playlist.length} tracks
          </span>
          <Clock className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {Math.round(mix.durationSeconds / 60)} min
          </span>
        </div>
        <div className="flex gap-2">
          {mix.cdnUrl && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => window.open(mix.cdnUrl, '_blank')}
            >
              <Play className="w-4 h-4 mr-1" />
              Play
            </Button>
          )}
          {showSaveButton && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onSave(mix)}
            >
              <Save className="w-4 h-4 mr-1" />
              Save
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => onLoad(mix.sessionId)}
          >
            Load
          </Button>
        </div>
      </div>
      
      <p className="text-xs text-muted-foreground truncate mb-2">
        {mix.playlist.slice(0, 3).map(track => track.title).join(", ")}
        {mix.playlist.length > 3 && ` + ${mix.playlist.length - 3} more`}
      </p>
      
      {/* Track list with download buttons */}
      <div className="space-y-1">
        {mix.playlist.slice(0, 3).map((track, index) => (
          <div key={index} className="flex items-center justify-between text-xs bg-muted/30 rounded px-2 py-1">
            <span className="truncate flex-1">
              {track.title} - {track.artist}
            </span>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0 ml-2"
              onClick={() => onDownloadTrack(track)}
            >
              <ExternalLink className="w-3 h-3" />
            </Button>
          </div>
        ))}
        {mix.playlist.length > 3 && (
          <p className="text-xs text-muted-foreground text-center">
            + {mix.playlist.length - 3} more tracks...
          </p>
        )}
      </div>
    </div>
  );
}