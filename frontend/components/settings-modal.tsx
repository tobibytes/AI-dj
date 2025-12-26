"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useMix } from "@/lib/mix-context";
import { Settings, X, Check, AlertCircle, Music2 } from "lucide-react";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const {
    isSpotifyConnected,
    connectSpotify,
    disconnectSpotify,
  } = useMix();
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-card border border-border rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Spotify Connection */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Music2 className="w-4 h-4 text-green-500" />
              <h3 className="font-medium">Spotify Account</h3>
            </div>
            
            <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
              <div className="flex items-center gap-3">
                {isSpotifyConnected ? (
                  <>
                    <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                      <Check className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Connected</p>
                      <p className="text-xs text-muted-foreground">Spotify Premium</p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-8 h-8 bg-muted rounded-full flex items-center justify-center">
                      <AlertCircle className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Not Connected</p>
                      <p className="text-xs text-muted-foreground">Connect to search tracks</p>
                    </div>
                  </>
                )}
              </div>
              
              {isSpotifyConnected ? (
                <Button variant="outline" size="sm" onClick={disconnectSpotify}>
                  Disconnect
                </Button>
              ) : (
                <Button size="sm" onClick={connectSpotify} className="bg-green-500 hover:bg-green-600">
                  Connect
                </Button>
              )}
            </div>
          </div>
          
          {/* Info */}
          <div className="p-3 bg-muted/50 rounded-lg">
            <p className="text-xs text-muted-foreground">
              🔒 Your Spotify credentials are handled via OAuth (we never see your password).
              AI features are powered by our backend - no API keys needed!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Settings button component for the header
export function SettingsButton() {
  const [isOpen, setIsOpen] = useState(false);
  const { isSpotifyConnected } = useMix();
  
  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="relative p-2 rounded-lg hover:bg-muted transition-colors"
        title="Settings"
      >
        <Settings className="w-5 h-5" />
        {!isSpotifyConnected && (
          <span className="absolute top-1 right-1 w-2 h-2 bg-yellow-500 rounded-full" />
        )}
      </button>
      
      <SettingsModal isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}
