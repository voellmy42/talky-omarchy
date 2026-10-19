# Benchmarking

Use a deliberately supplied mono 16 kHz PCM16 WAV. This command does not record
or insert text:

```bash
mkdir -p benchmark-results
./talky benchmark recordings/example.wav \
  --model ~/.local/share/voxtype/models/ggml-base.bin \
  --voxtype /usr/lib/voxtype/voxtype-vulkan \
  --runs 3 --output benchmark-results/example.jsonl
```

Reports are new owner-only JSONL files; transcripts are omitted unless
`--include-text` is explicitly supplied. Keep input/output in the ignored folders.

Each run starts a fresh Voxtype process and includes process/model startup.
Later runs can benefit from the OS file cache; this is not resident warm inference.
Transcription, formatting, and offline total are reported separately. Interactive
release-to-insertion is null in this tool. The app reports finish-to-paste-sent:
sending a paste shortcut is observable, destination acceptance is not confirmed.

For a generic stdin/stdout formatter command, configure an argv array using
`config/example.toml`, then pass `--config` to the benchmark or hook:

```bash
printf 'Do not deploy this yet.\n' | ./talky format --config config/example.toml
```

This generic hook defaults to exact passthrough and is separate from the desktop
app's resident Qwen formatter. Only configure trusted local commands. Commands
must emit only dictation on stdout; stderr is discarded, and timeout/failure
preserves the input. A configured executable can itself access networks, so local
inference remains the responsibility of the selected command.

Evaluate fillers, questions/instructions dictated as text, spoken corrections
across pauses, technical names/numbers/negations, silence, long utterances, and
required languages. Compare raw and cleaned text for meaning changes and manual
correction effort. Synthetic wrapper tests do not establish speech quality.
