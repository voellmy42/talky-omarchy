# Talky desktop prototype

Talky is a native Python/GTK4 app, separate from the user's Voxtype service.

- `ui.py`: control window, preview, and language/vocabulary settings.
- `overlay.py`: independent service-owned GTK layer-shell HUD. It stays alive while
  hidden between recordings, works without the control window, and uses actual
  Voxtype audio frames for its waveform. The service restarts it after a crash.
  It requests status without dictated text and never takes keyboard focus.
  GTK layer-shell is loaded before GTK/Wayland, as required by its
  [Python linking instructions](https://github.com/wmww/gtk4-layer-shell/blob/main/linking.md).
- `service.py`: user-owned Unix control socket, session state machine, cancel
  generation checks, and in-memory latest transcript. CLI status excludes text.
- `engine.py`: a resident Voxtype Vulkan child with an explicit local Whisper
  model, disabled hotkeys/OSD/auto-submit/streaming insertion, and file output.
  Its runtime, data, cache, and config directories are inside Talky's runtime.
  PipeWire and Pulse still connect to the real user's audio server.
- `formatter.py`: resident llama.cpp Vulkan with Qwen2.5 1.5B Instruct Q4_K_M,
  loopback-only listener and per-process API key. Few-shot JSON editing prompt,
  conservative lexical/number/negation guards, and bounded raw fallback.
- `desktop.py`: copies final text then sends a paste shortcut only when the
  original Hyprland window still has focus. A changed/unknown window means
  clipboard-only delivery. Enter is never sent. Terminals use Ctrl+Shift+V.

Starting the app loads models but does not start microphone capture. Recording
starts only with the button, F8, or an explicit CLI `start`/`toggle`. The button
defaults to preview; paste mode gives three seconds to focus a destination.
F8 targets the current window and inserts the completed dictation. Shift+F8
cancels; a late cleanup response cannot insert a cancelled session.

Audio remains inside Voxtype's process. The temporary transcript file is in the
private user runtime directory and is removed when read or on shutdown/startup.
The latest raw/final transcript stays in memory for review until cleared, next
recording, or quit. The app does not save dictation history. The clipboard retains
copied text according to the user's desktop clipboard policy. Child logs are
discarded; no dictated text is logged by default. Downloads happen only through
the explicitly run setup script. Inference is local; no API backend is enabled.

## Current limits

The underlying Whisper base model is the pre-existing multilingual model. English,
German, and Swiss German are the requested languages. Whisper has no separate
Swiss German language code: `de` is used when German is selected. Recognition and
dialect fidelity need real recordings. The small formatter's narrow editing guard
can reject useful spelling changes and leave corrections untouched. It cannot
prove semantic equivalence. Raw transcription is inspectable in the UI.

Eager processing is implemented as an optional configuration setting but remains
off until cross-chunk corrections are evaluated. Context is app class plus a
personal vocabulary; there is no screen, cursor-text, or browser-domain capture.
Focus checks operate at window level, not individual text field level. A successful
paste command does not prove that the destination accepted text. The timing label
therefore says **finish to paste sent**, rather than claiming confirmed insertion.
App-specific paste handling and cancellation still need testing in the user's
actual applications.

The app launcher is installed without login autostart. Models remain resident
while Talky is running. Closing the window hides it; Quit Talky stops the app and
service. If launched cold via F8, the app opens first and waits for another deliberate
recording action once models are ready. Voxtype's own F9 and Super+Ctrl+X remain
separate. No private Wispr API is used.

## Overlay verification

`python scripts/smoke-overlay.py` renders the production HUD with synthetic
recording/processing/completed state in an isolated test runtime. It never opens
the control window, uses the microphone, or contacts the real dictation service.
The compositor check verified one overlay layer, an unchanged focused window,
visible processing state, and hiding on completion. A cropped waveform image was
inspected locally under `/tmp`. Unit tests cover lifecycle state, text-free status,
and supervision/restart throttling. `scripts/reload-service.py` activates service
updates while idle; it refuses if dictation is active at its initial check.
