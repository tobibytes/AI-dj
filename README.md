# AI DJ

An experimental AI‑assisted DJ app with dual decks, smooth crossfades, and a queue panel. The vision is a microservice architecture that enables “fire” transitions, automatic mix curation, and instant testing of suggested transition points.

## Features (current)

- Dual decks UI
  - Play/Pause per deck with hidden HTMLAudioElement
- Crossfade
  - Equal‑power curve for perceived constant loudness
  - Controlled via CROSSFADER slider or explicit action buttons:
    - Fade to Deck A (2s) — `data-action="fade-to-a"`
    - Fade to Deck B (2s) — `data-action="fade-to-b"`
    - Cut to Deck A — `data-action="cut-to-a"`
    - Cut to Deck B — `data-action="cut-to-b"`
- Queue Panel
  - Tabs: “Next” and “Recently Played”
  - Renders track name and artist
  - “Next” seeded from `frontend/public/tracks.json`
- Code policy: “avoid useEffect unless necessary”
  - Effects only for genuine external system sync. See `docs/memory/react-effects.md`.

## Roadmap (near‑term)

- “Fire” transitions
  - Provide tracks and transition points (beat/phrase aligned)
  - Test transitions instantly in the UI
- AI mixes
  - AI suggests transitions, ordering, and blend durations
  - One‑click audition of suggestions
- Persistence and playback
  - Persist Next/Recently Played, basic library management
  - Safer audio sourcing via a backend proxy instead of raw direct links
- Audio intelligence
  - Analyze BPM, key, and waveform/peaks to enable beatmatching and key‑aware transitions

## Architecture (vision: microservices)

- Frontend (Next.js, React)
  - Real‑time UI, action buttons for AI/control systems (via `data-action` selectors)
- API Gateway / Orchestrator (future)
  - Single entrypoint for clients, auth, rate limits
- Track Ingest Service (future, Rust)
  - Resolve playable audio URLs (e.g., via yt‑dlp), fetch metadata
- Audio Analysis Service (future, Rust/WASM)
  - BPM, key detection, peak map, cue points
- Mix Engine Service (future, Rust)
  - Transition curves, beatmatching, rendering/previews
- Recommendation/LLM Service (future)
  - Generate transitions/mixes, accept feedback to refine
- Storage (future)
  - Postgres for catalog/metadata, S3 for assets, Redis for queues
- Messaging (optional future)
  - Kafka/NATS for async jobs and events

## Tech stack

- Frontend
  - Next.js 15 (App Router), React 19, TypeScript 5
  - Tailwind CSS 4, `lucide-react`
  - Event‑driven UI: `requestAnimationFrame` for fades; equal‑power crossfade math
- Backend (prototype)
  - Rust + `anyhow`
  - Uses system tool `yt-dlp` to resolve direct audio stream URLs (demo code in `backend/src/main.rs`)

## Project structure

- `frontend/` — Next.js app
  - `app/page.tsx` — Decks, mixer, crossfader, action buttons, queue panel
  - `components/` — `Turntable`, `DJMixer`, `QueuePanel`, UI `Button`
  - `public/tracks.json` — Seed tracks (artist, name, url)
- `backend/` — Rust prototype demonstrating stream URL resolution via `yt-dlp`
- `docs/` — Guidelines and memory notes (e.g., `react-effects.md`)

## Getting started

### Prerequisites

- Node.js (LTS recommended; Node 18+)
- npm (or pnpm)
- Rust (stable) + Cargo
- Optional (for backend demo): `yt-dlp` available on PATH
  - macOS: `brew install yt-dlp`
  - Windows: `choco install yt-dlp` (or `winget install yt-dlp`)
  - Python: `pip install -U yt-dlp`

### Frontend (Next.js)

- In one terminal:
  - `cd frontend`
  - `npm install`
  - `npm run dev`
  - Open `http://localhost:3000`

### Usage

- Click Play on a deck to start audio
- Crossfade:
  - Use the CROSSFADER slider (A—B)
  - Or click action buttons: Fade to A/B, Cut to A/B
- Queue:
  - Switch between “Next” and “Recently Played”
  - Edit `frontend/public/tracks.json` to change the “Next” list

Programmatic action triggers (e.g., from an automation/agent):
- `document.querySelector('[data-action="fade-to-b"]')?.click()`
- `document.querySelector('[data-action="fade-to-a"]')?.click()`
- `document.querySelector('[data-action="cut-to-a"]')?.click()`
- `document.querySelector('[data-action="cut-to-b"]')?.click()`

### Backend (demo)

- In another terminal:
  - `cd backend`
  - `cargo run`
- Prints a direct audio stream URL resolved by yt‑dlp for a demo YouTube link
- Note: This is not yet a server; it’s a utility for future ingest/microservice work

## Notes and disclaimers

- Streaming direct URLs from third parties can expire and may be subject to terms of service. The future backend will proxy/ingest safely and cache metadata rather than shipping raw links.

## Contributing

- Coding policy: minimize `useEffect`; prefer event‑driven patterns and server capabilities
- Commit small, focused PRs; include acceptance criteria and tests where applicable
- Roadmap issues welcome (transitions, analysis, mix engine, persistence)

## License

- TBD
