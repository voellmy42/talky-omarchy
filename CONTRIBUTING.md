# Contributing

Talky is an early local-first dictation app for Omarchy/Hyprland. Focus on reliable
capture, meaning preservation, visible recording state, and measured latency.

1. Describe the problem, affected desktop/app, and expected behavior in an issue.
2. Keep changes focused and retain raw-text fallback and cancellation behavior.
3. Run `PYTHONPATH=src python -m unittest discover -s tests -v`.
4. For desktop changes, manually verify focus, recording state, cancellation,
   and clipboard fallback. Never start the microphone without a deliberate action.

Do not attach personal recordings/transcripts, credentials, or unredacted logs.
Use synthetic text or explicitly shareable samples. Include Python, Voxtype,
GTK, Hyprland/Omarchy, and GPU/driver versions when reporting compatibility issues.
Do not claim speed/quality improvements without documenting how they were measured.

Contributions are submitted under this project's MIT license. Please keep model
weights, downloaded runtimes, local settings, and benchmark output out of commits.
