# Post-publication review: ten improvements

Reviewed the first public upload, commit `2995654`, after publication to
[voellmy42/talky-omarchy](https://github.com/voellmy42/talky-omarchy).
The initial CI run passed on Python 3.11 and 3.14. This is a source review plus
small synthetic checks, not a new speech-quality or performance benchmark.
The items below are proposed work; they have not been implemented by this review.

## 1. Strengthen meaning-preserving cleanup — highest priority

**Finding:** [`safe_candidate`](../src/talky/formatter.py#L26) compares token sets,
counts, numeric multisets, and total negation counts. It does not preserve the
order or relationships of those tokens. Direct synthetic calls currently accept:

- `Alice owes Bob 20 euros.` → `Bob owes Alice 20 euros.`
- `I do not want coffee. I want tea.` → `I want coffee. I do not want tea.`

They reject `Use port 8080, actually 9090.` → `Use port 9090.`, even though that
is an explicit numeric correction. These checks demonstrate guard limitations;
they do not show that the model generated those outputs in real dictation.

**Proposal:** Align edits against the source, limit changes to explicit spans,
preserve unaffected word order and negation scope, and handle clearly spoken
numeric corrections deliberately. Preserve raw fallback and reviewable diffs.
Add adversarial and multilingual regression cases before widening edit permissions.

**Done when:** Role/negation reversals are rejected, intended corrections have
explicit tests, and actual-model evaluations report accepted errors separately
from rejected useful edits. No heuristic should be described as proving meaning.

## 2. Recover from failures and explain them

**Finding:** The service restarts the overlay but not failed speech/formatter
processes. [`Controller.poll`](../src/talky/service.py#L137) enters an error state
when speech exits; some command exceptions can propagate from polling into the
service loop. The formatter can retain a `ready` label after its process dies.
Child diagnostics are discarded, and the UI silently ignores failed status polls.

**Proposal:** Add supervised child recovery, explicit disconnected/degraded states,
a Retry action, and bounded diagnostic error codes without dictated text. Move
blocking child commands and delivery outside the session lock so cancellation and
status stay responsive. Handle startup/shutdown races explicitly.

**Done when:** Injected engine/formatter/socket failures recover without duplicate
models, stale ready labels, unexpected insertion, or orphaned microphone capture.

## 3. Make setup work on a fresh machine

**Finding:** [`Settings`](../src/talky/settings.py#L13) assumes an installed
Voxtype Vulkan binary and an existing Whisper model. The setup script downloads
only the formatter, and runtime/model locations depend on the checkout. The
Python package metadata exposes an installable CLI while subprocess launchers
still assume a repository-root `talky` executable.

**Proposal:** Add `talky doctor` and a guided setup that checks architecture,
Python/GTK, audio, paste tools, model paths, and actual GPU support. Offer a tested
CPU path and compatible local model choices. Choose a clear supported installation
layout, then package it for Omarchy/Arch with versioned releases.

**Done when:** A clean supported desktop can install, diagnose missing components,
run preview dictation, update, and uninstall without undocumented manual edits.

## 4. Add microphone selection and input health

**Finding:** [`Engine.start`](../src/talky/engine.py#L34) always writes
`device = "default"`. There is no device picker, explicit muted/disconnected
status, or distinction between capture failure and an empty recognition result.

**Proposal:** Offer a device selector and an explicitly started input-level test.
Detect missing/muted input and device changes; explain whether the problem is
capture, silence, or recognition. Keep recording a deliberate action.

**Done when:** Switching between built-in, USB, and headset microphones is visible,
persistent, and recoverable without editing TOML or restarting the whole app.

## 5. Make insertion and clipboard behavior configurable per app

**Finding:** [`deliver`](../src/talky/desktop.py#L21) chooses a terminal paste
shortcut using class-name substrings, copies text before output, and checks focus
only at window level. The previous clipboard is not restored; multiple fields
inside one window are indistinguishable.

**Proposal:** Add explicit per-app paste profiles, a last-moment focus recheck,
optional clipboard restoration that respects intervening user copies, and better
fallback feedback. Investigate text-field identity only through supported opt-in
interfaces. Keep Enter/auto-submit disabled.

**Done when:** A documented app matrix covers editors, terminals, browsers, and
chat apps, with focus changes, clipboard ownership changes, and failed paste tests.

## 6. Build a multilingual speech evaluation suite and model picker

**Finding:** The default is the pre-existing Whisper base model. English, German,
and Swiss German matter to this project, but the model script currently evaluates
six synthetic text inputs and does not assert expected outcomes. Vocabulary hints
exist, but the lexical cleanup guard rejects any newly introduced spelling.

**Proposal:** Create an explicitly shareable speech corpus covering dialect,
code-switching, names, technical terms, numbers, negations, and self-corrections.
Compare ASR/cleanup choices and quantizations on the same clips. Expose model
selection with measured memory/latency/accuracy tradeoffs and controlled vocabulary
corrections. Never silently translate dialect into another language/style.

**Done when:** Model changes have reproducible quality and correction-effort
reports, including Swiss German failures, rather than a few favorable examples.

## 7. Reduce finish-to-text latency with measurements

**Finding:** [`Settings.eager`](../src/talky/settings.py#L23) defaults off; cleanup
starts after final transcription. The offline benchmark launches fresh processes
and does not exercise the resident formatter or full interactive path.

**Proposal:** Add a resident-path benchmark with stage timing and p50/p95 reports.
Compare eager recognition and safe preparation during recording, retaining
whole-utterance correction semantics. Tune thread/model/GPU memory use against
measured data. Keep partial results internal until final output is safe.

**Done when:** Real recordings show a documented improvement in finish-to-paste-sent
latency without increased meaning errors. Destination acceptance remains distinct
from dispatching the paste shortcut.

## 8. Offer configurable shortcuts and smoother background use

**Finding:** The installer hardcodes F8/Shift+F8. Cold launch opens the window and
requires another recording action. There is no push-to-talk choice or optional
login startup. The button countdown is local UI state; closing the window does
not cancel a pending countdown.

**Proposal:** Add shortcut selection with conflict checks, toggle/push-to-talk
modes, optional idle login startup, and a consistent cancellable countdown visible
in the overlay. Ensure modifier release before inserting when custom combinations
are used. Keep microphone capture off at login and during warmup.

**Done when:** Everyday dictation works from a chosen shortcut with clear readiness,
consistent cancellation, and no need to manage the control window manually.

## 9. Finish the overlay interaction

**Finding:** The HUD has fixed styling/placement and no monitor selector.
[`presentation`](../src/talky/overlay.py#L25) hides it for completed, clipboard,
and error states, so users with the main window hidden can miss delivery fallback
or failure information.

**Proposal:** Offer active-monitor placement, size/contrast controls, optional
start/stop sounds, and short explicit outcomes such as “Copied: focus changed” or
“Microphone unavailable.” Expose actual readiness/failure, not just recording.
Avoid adding focus-taking windows or persistent visual clutter.

**Done when:** Multi-monitor/fullscreen use and clipboard/error outcomes remain
clear with the main window closed; feedback is accessible and configurable.

## 10. Extend automated tests across real process and desktop boundaries

**Finding:** The 18 tests cover important logic, but the compositor checks are
manual scripts. There are no automated installer/rollback, child-crash, model
reload, real Unix-socket lifecycle, or long-session integration tests. The
formatter evaluation script prints results instead of grading them.

**Proposal:** Add deterministic subprocess/IPC tests with fake local engines,
installer tests against temporary home directories, and a virtual Wayland job for
HUD/focus behavior where feasible. Test paths containing spaces, repeated reloads,
crash recovery, cancellation during output, and optional cleanup being enabled
when it was disabled at startup. Keep model/speech evaluation opt-in and local.

**Done when:** CI catches lifecycle/install/focus regressions before release and
reports separate logic, desktop integration, and actual-model evaluation results.

## Suggested sequence

Start with **1–3**: meaning preservation, failure recovery, and setup for new users.
Then improve input/output reliability (**4–5**), establish speech evaluations before
latency tuning (**6–7**), and polish daily use and regression coverage (**8–10**).
