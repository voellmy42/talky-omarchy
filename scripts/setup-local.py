#!/usr/bin/env python3
"""Download a pinned, verified runtime and official local formatting model.

Downloads assets only. Does not install services, change desktop settings, or
send recordings/transcripts anywhere. Run deliberately, with internet access.
"""
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_URL = 'https://github.com/ggml-org/llama.cpp/releases/download/b11739/llama-b11739-bin-ubuntu-vulkan-x64.tar.gz'
RUNTIME_SHA256 = 'a6b1062ecded87c1e2b67f99c7a7106530b95b40e703b570690b046a2c98f21a'
MODEL_REPO = 'Qwen/Qwen2.5-1.5B-Instruct-GGUF'
MODEL_FILE = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'


def download(url, destination, digest):
    if destination.exists() and hashlib.file_digest(destination.open('rb'), 'sha256').hexdigest() == digest:
        print(f'Already verified: {destination.name}', flush=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + '.partial')
    print(f'Downloading {destination.name}', flush=True)
    with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    with partial.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest:
        raise RuntimeError('Download checksum mismatch')
    partial.replace(destination)


def main():
    archive = ROOT / 'vendor' / 'llama-b11739-vulkan.tar.gz'
    download(RUNTIME_URL, archive, RUNTIME_SHA256)
    runtime = ROOT / 'vendor' / 'llama'
    runtime.mkdir(exist_ok=True)
    with tarfile.open(archive) as package:
        package.extractall(runtime, filter='data')
    # Resolve a commit and LFS SHA-256 from the official repository, then pin the
    # download to that commit. Record provenance beside the ignored model.
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{MODEL_REPO}?blobs=true', timeout=30) as response:
        metadata = json.load(response)
    entry = next(x for x in metadata['siblings'] if x['rfilename'] == MODEL_FILE)
    digest = entry['lfs']['sha256']
    commit = metadata['sha']
    model = ROOT / 'models' / MODEL_FILE
    download(f'https://huggingface.co/{MODEL_REPO}/resolve/{commit}/{MODEL_FILE}', model, digest)
    (model.parent / 'formatter-provenance.json').write_text(json.dumps(dict(
        repository=MODEL_REPO, revision=commit, file=MODEL_FILE, sha256=digest,
        runtime=RUNTIME_URL, runtime_sha256=RUNTIME_SHA256), indent=2) + '\n')
    print('Local formatter assets ready. No desktop configuration changed.', flush=True)


if __name__ == '__main__':
    main()
