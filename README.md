# Vibetram

Vibetram is an independent open-source graphical interface project built on top of [OpenAI Codex CLI](https://github.com/openai/codex). Codex and ChatGPT compatibility is under development; no connection to this conversation is established.

- **Vibetram Mobile**: experimental Android prototype.
- **Vibetram Desktop**: planned Electron-free desktop client, intended to reduce overhead and RAM usage. No desktop release or measured RAM comparison is available.

## Current 1.91 status

This repository now contains the expanded Android and pinned native Rust source used to prepare the offline 1.91 alpha, together with GitHub Actions preparation. The genuine local 1.91 APK passed host/package checks: 88 native test executions and Java suites with 24, 44 and 21 checks. These overlapping checks do not establish Android phone behavior, real-network enforcement or live service compatibility. **1.91 phone testing remains pending.**

The runtime uses synthetic process-only sign-in, fake enrollment and memory transport. Native code starts signed out; activation is explicit, status-only, and expires after a non-renewable 120 seconds. Stop, focus loss, cancellation and expiry revoke the local session. No real login, pairing, Internet permission, model/file/shell/capture access or persistent host registration is enabled. Local shutdown is not evidence of server-side host deletion.

## Source and CI

Source is expanded as ordinary files: `android/`, `codex-rs/`, and `ci/`. See [CI_STATUS.md](CI_STATUS.md), [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md), [LICENSING.md](LICENSING.md), and [GENERATED_INPUTS_REVIEW.json](GENERATED_INPUTS_REVIEW.json).

Push/PR checks validate source bindings and offline manifest policy with read-only permissions. Native/unsigned Android qualification is a separate manual trusted-main action and has **not run on a clean hosted runner**. Exact Rust, SDK, NDK, JDK, native build prerequisites and generated inputs still require qualification. The release job remains disabled pending an authorized signing and signed-artifact policy. Private signing material is not included.

The intended first public APK is `Vibetram-Alpha-1.91-Android.apk`. A genuine local artifact exists, but no GitHub Release has been published. The old repository ZIP is retained only as historical source evidence; it is not the current expanded tree or a complete build. Future release `source.zip` must come from the exact APK build commit, not this historical ZIP. Earlier APKs will not be relabelled as 1.91.

Whole-tree source provenance and scoped privacy/notices review are complete for this candidate, without legal/trademark clearance or a guarantee that no secrets exist. Eleven optional upstream sample/documentation images/icons are excluded; no replacement artwork was added. Third-party components retain their licences and notices.

## Upstream credit

Vibetram is built on top of [OpenAI Codex CLI](https://github.com/openai/codex), using adapted native Codex app-server and transport components as part of the project, rather than merely providing a link to a separate Codex app. The 1.91 checkpoint uses those components in offline host and local APK package checks; clean-runner builds, phone behavior and end-to-end compatibility remain unverified.

Credit to OpenAI and the upstream contributors for the Codex code on which the reviewed native components are based. Applicable Apache-2.0 and third-party notices are preserved in [LICENSE](LICENSE), [NOTICE](NOTICE) and [LICENSING.md](LICENSING.md); see [source provenance](SOURCE_PROVENANCE.md) for the exact base and modifications. This credit does not imply an official or supported integration, affiliation or endorsement.

## Branding and independence

Vibetram is an independent project, not affiliated with, endorsed by or owned by OpenAI. References to Codex, ChatGPT, Dots and AI models identify intended integrations; their names and rights remain with their respective rights holders. No legal, name-availability or trademark clearance is claimed.

The maintainer is willing to respond to explicit requests for changes or takedown. This is a statement of project intent, not an independent legal determination.

The selected icon direction is the project's own terminal-and-headphones concept, without obsolete name text or tagline. A verified clean asset has not been included in this snapshot. No OpenAI logo or other asset is included.

## Licence and OpenAI guidance

Vibetram’s code is available under Apache 2.0. For questions about OpenAI trademarks or services, consult [OpenAI’s terms](https://openai.com/policies/terms-of-use/) and [brand guidance](https://openai.com/brand/). Third-party components retain their applicable licences and notices.
