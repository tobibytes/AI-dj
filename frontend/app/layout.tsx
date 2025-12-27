import type { Metadata } from "next";
import "./globals.css";
import { MixProvider } from "@/lib/mix-context";
import { SettingsButton } from "@/components/settings-modal";

export const metadata: Metadata = {
  title: "AI DJ Studio",
  description: "AI-powered DJ that creates personalized mixes from your prompts",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="">
        <MixProvider>
          <div className="min-h-screen bg-background">
            {/* Header */}
            <header className="border-b border-border bg-card">
              <div className="container mx-auto px-4 py-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1" />
                  <div className="text-center">
                    <h1 className="text-3xl font-bold text-primary tracking-wider">AI DJ STUDIO</h1>
                    <p className="text-muted-foreground mt-2">AI-Powered Music Mix Generator</p>
                  </div>
                  <div className="flex-1 flex justify-end">
                    <SettingsButton />
                  </div>
                </div>
              </div>
            </header>
            
            {children}
            
            {/* Status Bar */}
            <footer className="container mx-auto px-4 pb-8">
              <div className="mt-12 bg-card border border-border rounded-lg p-4">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-primary rounded-full animate-pulse"></div>
                      <span className="text-muted-foreground">READY</span>
                    </div>
                  </div>
                  <div className="text-muted-foreground"></div>
                </div>
              </div>
            </footer>
          </div>
        </MixProvider>
      </body>
    </html>
  );
}
