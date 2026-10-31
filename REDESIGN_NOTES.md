# ERA — UI/UX Redesign (final drop)

Complete frontend, ready to drop into your existing repository. Copy the `src/`
folder and `index.html` to your repo root — same paths as before, nothing renamed,
moved or deleted. Review the diff in GitHub Desktop, commit, push.

**No dependencies were added or removed.** `package.json` is untouched: the orb and
the transcript panel are plain React + canvas + Tailwind.

---

## Files in this drop

| File | Status |
|---|---|
| `index.html` | changed — title, meta description, theme-color |
| `src/index.css` | changed — new design system (tokens, fonts, component classes) |
| `src/App.tsx` | changed — restyled, orb replaced, transcript panel wired in |
| `src/components/VoiceOrb.tsx` | **new** — 3D canvas orb (idle / listening / processing / speaking) |
| `src/components/LiveTranscript.tsx` | **new** — live transcript side panel |
| `src/components/AutonomyDashboard.tsx` | changed — restyled |
| `src/components/BluetoothMusicManager.tsx` | changed — restyled |
| `src/main.tsx` | unchanged (included for completeness) |
| `src/types.ts` | unchanged |
| `src/lib/*.ts` | unchanged |
| `src/db/*.ts` | unchanged |
| `src/middleware/auth.ts` | unchanged |
| `src/era-voice-assistant.code-workspace` | unchanged |

---

## 1. The design language

| Token | Value | Used for |
|---|---|---|
| `#0a0b0d` | ink-950 | app background |
| `#101215` | ink-900 | cards, bars |
| `#15181c` | ink-800 | inputs, chips |
| `#e6a94a` | accent | primary action, active tab, orb |
| `#ef5a60` | live | microphone recording, destructive |
| `#4ec98a` | ok | connected |
| `rgba(255,255,255,.07)` | line | every border |
| Plus Jakarta Sans | UI text | |
| Azeret Mono | metadata | timestamps, labels, status |

One accent colour; rose only for "live / destructive"; borders at 7% white instead of
coloured glow; every neon box-shadow removed; 11px minimum type size; one focus ring;
radii normalised to 8 / 10 / 12 / 14px.

## 2. VoiceOrb (`src/components/VoiceOrb.tsx`)

A 3D point cloud on a canvas — no WebGL, no libraries. Shape *and* motion change with
the session state, so you can tell from across the room who is talking:

| state | shape | motion | colour |
|---|---|---|---|
| `idle` | dotted globe | slow Y rotation | warm gold |
| `listening` | globe breathing outward + ripples | fast, mic-like | rose |
| `processing` | half-formed gyroscope | fast spin | gold |
| `speaking` | three intersecting rings | slow counter-rotation | warm gold |

Purely presentational: it takes `state` and calls `onClick` — in `App.tsx` that is the
same `toggleSession` handler as before.

## 3. LiveTranscript (`src/components/LiveTranscript.tsx`)

The side panel that mirrors the voice conversation as chat messages.

* **Messages are never translated or normalised** — a Hindi turn stays in Hindi, an
  English turn stays in English. Only the panel chrome is English.
* Speaker filter (All / You / ERA), in-session search, auto-scroll with a "Latest"
  jump button when you scroll up, per-message copy, `VOICE` tag for turns that came
  from the live audio stream, and a "Listening…" row while the mic is open.
* The language chip is derived from the transcript itself (Devanagari → Hindi, Arabic
  → Urdu, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Punjabi, else English).
  It is a label only — no translation is performed.
* Data comes from props that already existed (`dashboardChats`, `transcriptions`,
  `state`). It owns no data and makes no network calls. ERA replies still pass through
  the app's existing `cleanUrlsAndLinks` formatter, so link cleaning behaves exactly
  as before.

Wiring in `App.tsx`:

```tsx
<LiveTranscript
  messages={dashboardChats}
  voiceIds={transcriptions.map((t) => t.id)}
  state={state}
  formatModelText={cleanUrlsAndLinks}
  className="mb-4 min-h-0 flex-1"
/>
```

Layout: on `lg` and up the voice stage sits on the left and the transcript panel on the
right (`lg:order-1` / `lg:order-2`); below `lg` they stack. The text input under the
panel is unchanged — typing still sends the same `{ type: 'text' }` websocket message.

## 4. How the restyle was done (and why logic is untouched)

1. Design tokens live in `src/index.css` (`:root` variables + Tailwind `@theme` for the
   fonts) plus plain component classes: `.card`, `.card-quiet`, `.card-inset`, `.btn`,
   `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.chip`, `.field`, `.label`, `.pill`,
   `.modal-card`, `.section-label`, `.kbd`.
2. Palette migration across every screen: `slate → neutral`, `cyan → amber`,
   `pink → rose`, `purple/indigo → orange`, `blue → stone`, including the hard-coded
   `rgba()` / hex colours inside the canvas drawing code. Dashboard, session
   transcripts, text chat + YouTube inspector, workspace (VS Code / browser
   simulations), settings, contacts, WhatsApp linker, every modal, the
   shutdown/lock/sleep overlays and the error banners all inherit from the same tokens.
3. Structural restyle of the app shell only: header, dashboard split view, cloud-sync
   banner, bottom controller.

### Verified, not assumed

| marker | original | final |
|---|---|---|
| `onClick=` | 73 | 73 |
| `onChange=` | 15 | 15 |
| `useState` | 79 | 79 |
| `useEffect` | 19 | 19 |
| `fetch(` | 17 | 17 |
| `/api/...` paths | 17 | 17 |
| `localStorage` | 25 | 25 |
| `setX(...)` setters | 300 | 300 |

Every handler, state hook, API call, Firebase call and validation is byte-identical.
The only JSX removed is the old orb markup and the old hand-rolled message list — both
replaced by components that receive the same props.

## 5. Checks performed

* `esbuild` transform of every TSX file — passes (syntax + JSX).
* `esbuild` bundle of `src/main.tsx` with node_modules externalised — all imports
  resolve, passes.
* `postcss` parse of the new `index.css` — passes.
* Server-side render of `LiveTranscript` with sample data — renders, detects Hindi from
  Devanagari, keeps the Devanagari text verbatim, shows the VOICE tag and the live
  "Listening…" row.
* Tailwind-compiled screenshot of the panel — layout, spacing and typography checked.
* Line diff of `App.tsx` with class names stripped — only colour literals and the
  restyled blocks differ.

**Not verified here:** a full `vite build`. The sandbox this was prepared in cannot
allocate WebAssembly memory (Vite/Tailwind need it) and `npm install` of the full
dependency tree exceeds its 2 GB RAM. Run `npm install && npm run build` once locally;
nothing in this drop adds a dependency or changes a build input.

## 6. Responsive behaviour

* Header wraps instead of overflowing; navigation stays on one row.
* Dashboard split view stacks below `lg`; the transcript panel goes full width and the
  voice stage keeps its height.
* Panes use `min-w-0` so long transcripts never blow out the grid.
* Touch targets on the controller are ≥ 44px; the orb scales with its container.

## 7. Suggested follow-ups (not done on purpose)

1. Per-message audio replay (needs the audio buffers to be persisted first).
2. Optional translation toggle (needs a translate call — would be new network traffic).
3. Splitting the remaining 4,518-line `App.tsx` into components + hooks.
4. Virtualising the transcript list for very long sessions.
