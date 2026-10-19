# Wispr Flow investigation: evidence and limits

Reviewed 2026-10-19. No Wispr app, installer, account, or capture was available
locally for this investigation. No REA client analysis
has been performed, and Talky is not yet a reverse-engineered replica.

The official download URL currently redirects to an account sign-in/onboarding
page. No account was created, and no private endpoint was contacted.

Sources reviewed:

- [Wispr Context Awareness](https://docs.wisprflow.ai/articles/4678293671-Context-Awareness)
  describes active-app/website identity, context near the cursor, dictionary/name
  hints, and local casing/spacing adjustments. This documents observable behavior;
  it does not establish the implementation or server prompts. Talky currently
  implements only application class and vocabulary hints.
- [Official download flow](https://wisprflow.ai/get-started) requires onboarding.
- [REA README](https://github.com/morluto/rea/blob/main/README.md) and
  [static JavaScript artifact workflow](https://github.com/morluto/rea/blob/main/docs/javascript-artifact-reconstruction.md)
  describe local ASAR/directory analysis and evidence records. Setup is not needed
  merely to build Talky, and was not run without an analyzable target.

When an authorized artifact becomes available, record its source/version/hash,
then inspect context collection, audio chunk boundaries, request scheduling,
finalization, cancellation, and insertion. Separate static call paths from
runtime observations. Do not infer hidden model identities from client strings
or make Talky depend on a private Wispr endpoint.
