# Third-party components

Talky's MIT license covers this repository's original source and assets. It does
not replace the licenses of external software or model weights.

| Component | Use | Upstream license/source |
| --- | --- | --- |
| Voxtype | Separate local capture/transcription process | [MIT](https://github.com/peteonrails/voxtype/blob/main/LICENSE) |
| whisper.cpp | Speech engine inside Voxtype | [MIT](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE) |
| llama.cpp | Downloaded local formatter runtime | [MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |
| Qwen2.5-1.5B-Instruct-GGUF | Downloaded cleanup model | [Apache-2.0](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/LICENSE) |
| GTK4 / PyGObject | Native interface | [GTK](https://www.gtk.org/) / [PyGObject](https://pygobject.gnome.org/) |
| GTK4 Layer Shell | Recording overlay | [MIT](https://github.com/wmww/gtk4-layer-shell/blob/main/LICENSE) |

Runtime/model downloads are excluded from Git. The setup script verifies their
SHA-256 digests and stores download provenance locally beside the model. Preserve
upstream license files if redistributing those components yourself.
