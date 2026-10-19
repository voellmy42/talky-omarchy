# Talky implementation plan

Build a smooth local-first dictation app for Omarchy/Hyprland, with visible
recording state, reliable cancellation, and meaning-preserving text output.

## Current implementation

- Native GTK4 control window with preview, language/vocabulary settings, and raw
  transcription comparison.
- Independent service-owned layer-shell overlay with waveform, timer, and controls.
- Separate resident Voxtype Vulkan speech engine and llama.cpp/Qwen cleanup model.
- Clipboard/paste delivery with window-focus protection and no auto-submit.
- Bounded cleanup with conservative guards and original-text fallback.
- Reversible app launcher and optional F8/Shift+F8 bindings; no login autostart.
- Headless regression tests, desktop smoke checks, and offline benchmarking tools.

## Working constraints

- Local inference is the default. Network inference requires explicit opt-in;
  no cloud inference backend is implemented yet.
- Never start microphone capture without a deliberate user action.
- Keep recordings, transcripts, credentials, downloaded models, and local benchmark
  results out of Git. Do not log dictation by default.
- Keep the user's existing Voxtype setup separate.
- Measure latency and quality; do not infer them from model size or synthetic tests.
- Dictated questions and instructions remain text; cleanup must not answer/execute them.
- Use the Omarchy skill before agent-driven desktop/user configuration changes.
- No sub-agent delegation was requested for this project.

## Validation priorities

1. Evaluate deliberate real speech across English, German, Swiss German, silence,
   corrections, technical vocabulary, long utterances, and actual target apps.
2. Compare ASR/cleanup model choices on repeatable samples and available hardware.
3. Separate cold startup, resident inference, final transcription, cleanup, and
   finish-to-paste-sent timing; distinguish paste dispatch from app acceptance.
4. Evaluate eager processing (currently off) with cross-chunk corrections and
   GPU memory contention before enabling it by default.
5. Improve diagnostics, startup/recovery, installation, and hardware portability.
6. Investigate specific Wispr client behavior with REA when an authorized artifact
   becomes available. Client analysis cannot establish hidden server models.

## Publishing

The user explicitly authorized creating a new public GitHub repository named
`voellmy42/talky-omarchy` and selected the MIT license. Publish the initial version,
then review the project and propose ten improvements. This authorization does not
include announcing it on other services or sending messages to others.

See [architecture](docs/architecture.md), [findings](docs/initial-findings.md),
[benchmarking](docs/benchmarking.md), and [Wispr investigation](docs/wispr-investigation.md).
