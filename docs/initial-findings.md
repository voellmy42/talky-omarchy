# Initial findings and integration constraints

Talky began as an isolated Linux prototype alongside an existing Voxtype setup.
The original macOS Talky used Apple-specific MLX Whisper and Ollama cleanup;
those runtime assumptions do not carry over to Linux.

## Integration

- Voxtype 1.1.1 provides local Whisper, external start/stop/cancel controls,
  file output, vocabulary hints, and optional eager processing.
- Talky uses a separate runtime/config/data directory and resident process.
  Existing user Voxtype settings, service, and shortcuts are not replaced.
- The Voxtype CLI prints metadata before file-transcription text; the benchmark
  must separate that metadata from the actual transcript.
- GPU detection inside a restricted sandbox can differ from the real desktop.
  Verify Vulkan inference before diagnosing a driver failure or selecting models.
- GTK4 Layer Shell must load before GTK/Wayland in Python. The recording overlay
  runs as a separately supervised process, independent of the control window.

## Validation scope

The prototype has been exercised on one Omarchy/NVIDIA desktop. Headless tests
cover fallback, cancellation races, focus protection, preview behavior, conservative
cleanup guards, and overlay lifecycle. Desktop smoke checks cover scratch-editor
paste and synthetic-state overlay rendering without microphone capture.

The user has reported successful real dictation. This is not a controlled quality
or latency benchmark. English, German, and Swiss German are the initial language
interests; dialect fidelity and cross-application compatibility need broader tests.

No personal recordings, transcripts, model weights, machine-specific benchmark
results, or credentials belong in this repository. Keep evaluation material local.
