# Talky for Omarchy

**Speak into any app. See when you’re recording. Keep inference local.**

Talky is a native GTK4 dictation app for Omarchy and Hyprland. It combines
Voxtype’s local speech recognition with resident LLM cleanup, a live waveform
overlay, and paste into the window where you started dictating.

![Talky recording overlay](assets/recording-overlay.png)

*Overlay preview using synthetic audio levels; the real waveform follows your microphone.*

## What it does

- **F8** to start/finish dictation; **Shift+F8** to cancel.
- A bottom-center overlay shows the live waveform, timer, and processing state,
  even with the control window closed. It keeps keyboard focus in your writing app.
- Local cleanup handles punctuation, fillers, and explicit spoken corrections,
  with conservative checks and raw-transcript fallback on timeout or rejected edits.
- A native window offers preview mode, language selection, vocabulary hints,
  and comparison with the original transcription.
- If you switch windows during processing, Talky copies the result for you to paste.
- Models stay loaded while Talky runs. No Enter keystroke is sent to submit text.

This is an early working prototype. It has been used for real dictation on an
Omarchy desktop; broader hardware, language, and application coverage still needs
testing. No general speed or quality advantage over other tools is claimed.

## Requirements

- Omarchy with Hyprland and **Lua** user bindings (`~/.config/hypr/bindings.lua`).
- Linux **x86_64**, Python **3.11+**, GTK4/PyGObject, and GTK4 layer shell.
- Voxtype **1.1.1**, including `/usr/lib/voxtype/voxtype-vulkan`, and a working
  Vulkan driver. The initial implementation has been exercised on NVIDIA;
  other GPUs and CPU-only operation need validation.
- `wtype`, `wl-clipboard`, and PipeWire/PulseAudio audio capture.
- An existing multilingual Whisper model at
  `~/.local/share/voxtype/models/ggml-base.bin` (or configure another local path).
- About **1.2 GB** of downloads for the local formatter runtime and model,
  plus the Whisper model. Model memory requirements depend on your choices.

Omarchy commonly provides several of these dependencies already. Check what is
installed before adding packages. For the default Whisper model, use Voxtype’s
`voxtype setup model` selector; do not change your working Voxtype configuration
just to try Talky.

## Get started

```bash
git clone https://github.com/voellmy42/talky-omarchy.git
cd talky-omarchy

# Explicit download: verified llama.cpp Vulkan runtime and official Qwen GGUF model.
python scripts/setup-local.py

# Try the native app before installing desktop integration.
./talky app
```

The app loads models without recording. Start in **preview mode**: click
**Start dictation**, speak, then **Finish dictation**. Inspect the result before
trying paste into another app.

Once that works, install the launcher and optional shortcuts:

```bash
python scripts/install-desktop.py          # app launcher only
python scripts/install-desktop.py --keys   # also add F8 / Shift+F8
```

The installer backs up the bindings file, checks for shortcut conflicts, and
validates Hyprland after changes. Your existing Voxtype service and shortcuts
remain available. The launcher references this checkout, so keep it at its
installed path. No login autostart is installed.

## Everyday use

Open **Talky** from the launcher once to warm the models. Focus the app where you
want to write, press **F8**, speak, then press **F8** again. The overlay also has
**Finish** and **Cancel** buttons. A cold F8 launch opens Talky first; start
recording again once it is ready.

In the control window, expand **Language, cleanup & vocabulary** to change
settings. Select Auto for English/German switching; German also covers Swiss
German recognition. Dialect fidelity and corrections need further evaluation.
The button’s paste mode gives you three seconds to focus a destination window.

Closing the control window hides it. **Quit Talky** stops the service and models.

```bash
./talky status       # status without dictated text
./talky cancel
./talky shutdown     # stop Talky’s service

# Remove Talky’s launcher and its marked shortcut block; keep project/models.
python scripts/install-desktop.py --remove --keys
```

## Privacy and limits

- Inference runs locally. No cloud inference backend or telemetry is enabled.
- The setup script downloads software/models; the app does not download them
  automatically or upload dictation.
- No audio recordings or dictation history are saved. A temporary transcript
  exists in a private runtime directory during processing; the latest raw/final
  text stays in memory for review until cleared, replaced, or quit.
- Final text is copied to the clipboard for paste. Your desktop clipboard manager
  may retain it according to its own settings.
- Context is limited to application class and your vocabulary. Talky does not
  collect screenshots, surrounding text, or browser contents.
- Cleanup is imperfect. Conservative guards can reject helpful edits or leave a
  correction unresolved. They cannot prove that every accepted edit preserves meaning.
- Focus protection is at window level, not text-field level. Paste shortcuts may
  need adaptation for particular applications. A successful paste command does
  not prove the application accepted the text.

Talky is an independent implementation. It does not use Wispr Flow’s private API,
models, branding, or client code. [Investigation status](docs/wispr-investigation.md).

## Development

Run the headless tests without downloading models or accessing a microphone:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Optional manual checks on a Wayland desktop:

```bash
python scripts/smoke-overlay.py     # synthetic HUD states; no microphone
python scripts/smoke-desktop.py     # paste test text into a scratch editor
python scripts/evaluate-formatter.py # synthetic text through the downloaded model
```

The desktop paste check changes the clipboard. The overlay check writes a cropped
preview to `/tmp`. Neither starts microphone capture. Keep personal evaluation
material in ignored `recordings/` and `benchmark-results/` directories.

See the [ten-item improvement roadmap](docs/review-and-roadmap.md),
[architecture](docs/architecture.md), [benchmarking](docs/benchmarking.md),
[implementation plan](PLAN.md), and [contributing](CONTRIBUTING.md).

## Credits and license

Talky builds on [Voxtype](https://github.com/peteonrails/voxtype),
[whisper.cpp](https://github.com/ggml-org/whisper.cpp),
[llama.cpp](https://github.com/ggml-org/llama.cpp),
[Qwen](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF), GTK4, and
[GTK4 Layer Shell](https://github.com/wmww/gtk4-layer-shell).
The earlier macOS experiment is [voellmy42/talky](https://github.com/voellmy42/talky).

Talky’s source is [MIT licensed](LICENSE). Downloaded runtimes and models keep
their own licenses; see [third-party components](THIRD_PARTY.md).
