# Changelog

## 1.91 expanded source / Actions preparation (2026-11-09)

- Published expanded Android and pinned native source instead of introducing another source archive.
- Added source-binding/offline-manifest checks and a manual unsigned build qualification candidate; release/signing remains disabled.
- Preserved upstream credit, Apache-2.0 and third-party notices; documented local modifications and excluded eleven optional upstream sample/documentation images/icons.
- Represented the bubblewrap licence portably using its exact COPYING text and recorded original link provenance.
- Current local alpha remains offline-only synthetic authentication/enrollment/transport with explicit activation, a non-renewable 120-second session and cancellation guards.
- Existing local host/package checks passed. Clean hosted-runner compilation and new 1.91 phone tests are pending; no live connection or public APK release is claimed.

## Historical changelog

# Changelog

## 1.91 alpha — planned first public Android build, not released

The source/host-test checkpoint is complete; the Android APK, owner-phone testing and GitHub release upload are pending. Intended release asset: `Vibetram-Alpha-1.91-Android.apk`. No existing 1.90 APK represents this version.

### Implemented and host-validated

- Added an offline-only continuation from the existing managed sign-in parser into native status-only enable/pairing/status/disable components, using synthetic authentication/backend/transport.
- Fixed inactive signed-out session retirement cancelling the session created after first sign-in.
- Preserved revocation after prior Stop, activation or authenticated owner change; added exact installation/environment binding and stale-result rejection.
- Added generic device naming and remote serialization minimization for personal paths/user-agent text.
- Tested cancellation during enrollment, queued completion rejection, expiry, strict schemas, metadata persistence and child/reader cleanup.
- Final host results: 86 native test executions and 44 Java/native checks. These overlap functionality and do not establish live or Android compatibility.

### Published

- Published the reviewed source snapshot as `Vibetram-Alpha-1.91-Source.zip` with licence, required notices and documentation in commit `fa3bafbb29fee843410513b24cafd73cc51453e0`. Public upstream provenance and required notices are verified, and Apache-2.0 for original Vibetram code is approved. This source publication is not an Android APK release.

### Pending

- Android native rebuild from final 1.91 source, Android-safe Activity/process adapter and explicit Stop/focus-loss controls; normal and canceled/expired runs on a phone.
- Compile/manifest/permission, payload identity, uncompressed aligned resources.arsc, native alignment, ZIP integrity and existing-certificate signature verification.
- Actual GitHub release asset upload and remote hash/size verification.
- Official host withdrawal and this-conversation compatibility. Live authentication/pairing remains separately restricted.

### Product direction

Vibetram Mobile is the Android prototype. Vibetram Desktop is planned as an Electron-free client intended to reduce overhead and RAM usage; no desktop release or comparative RAM benchmark exists. The project is independent and unaffiliated with OpenAI. No logo asset is included until the owner's clean terminal-and-headphones artwork, without old text/tagline, is available and cleared for use.

## Unreleased CI and source maintenance

- Separate 250 ms target resource supervision from a 30-second census worker, with at most two full walks and bounded fail-closed teardown. Retained-space samples are non-atomic, not a hard write quota.
- Replace two static AWS-shaped redaction test fixtures with new deterministic constructions; preserve upstream notices and production redaction behavior. Historical copies and the open alert are not erased or resolved.
- Python/synthetic qualification is recorded separately from unrun native clean-build, Rust CLI test and phone validation.
