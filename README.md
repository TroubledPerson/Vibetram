# Vibetram

Vibetram is an open-source graphical interface project built on top of [OpenAI Codex CLI](https://github.com/openai/codex), currently a work in progress. Codex and ChatGPT integration compatibility is under development. Planned Electron-free desktop client, intended to reduce overhead and RAM usage.

- **Vibetram Mobile**: experimental Android prototype.
- **Vibetram Desktop**: planned; no desktop release is available.

## Current status

The latest source checkpoint tests a bounded status-only native session using synthetic authentication, enrollment and memory transport. The final host revision passed 86 native test executions and 44 Java/native checks. These are overlapping host checks, not proof of live service compatibility, Android behavior for that revision or a connection to this conversation.

Earlier Android prototypes demonstrated owner-observed ChatGPT sign-in/model replies and offline native cancellation/expiry. They do not establish current remote pairing or end-to-end ChatGPT connectivity. Live pairing and completed client enrollment have not been demonstrated.

The intended pilot defaults off, requires explicit activation and expires after a non-renewable 120 seconds. Remote file, shell, model and capture operations are outside its status-only contract. Local shutdown does not establish deletion of a server-side host registration.

## Source and builds

The reviewed source archive contains the reviewed native components, five 1.91 host integration Java files and historical Android Java reference source. The public upstream identity and Apache-2.0/NOTICE are verified; the owner has approved Apache-2.0 for original Vibetram code. It is not a complete portable Android build. No release APK, binary, signing key, private log or user account/session data is included. See LICENSING.md, SOURCE_PROVENANCE.md, DEPENDENCIES.md and BUILD_STATUS.md.

## Upstream credit

Vibetram is built on top of [OpenAI Codex CLI](https://github.com/openai/codex), using adapted native Codex app-server and transport components as part of the project, rather than merely providing a link to a separate Codex app. The published 1.91 checkpoint runs those components in offline host tests; this is not yet a validated 1.91 Android APK or a verified full end-to-end Codex GUI.

Credit to OpenAI and the upstream contributors for the Codex code on which the reviewed native components are based. Applicable Apache-2.0 and third-party notices are preserved in [LICENSE](LICENSE), [NOTICE](NOTICE) and [LICENSING.md](LICENSING.md); see [source provenance](SOURCE_PROVENANCE.md) for the exact base and modifications. This credit does not imply an official or supported integration, affiliation or endorsement.

## Branding and independence

Vibetram is an independent project, not affiliated with, endorsed by or owned by OpenAI. References to Codex, ChatGPT, Dots and AI models identify intended integrations; their names and rights remain with their respective rights holders. No legal, name-availability or trademark clearance is claimed.

The maintainer is willing to respond to explicit requests for changes or takedown. This is a statement of project intent, not an independent legal determination.

The selected icon direction is the project's own terminal-and-headphones concept, without obsolete name text or tagline. A verified clean asset has not been included in this snapshot. No OpenAI logo or other asset is included.

## First public Android release (pending)

The intended first public build is **1.91**, with release asset name `Vibetram-Alpha-1.91-Android.apk`. The genuine Android APK has not been built or validated yet. Earlier 1.90 artifacts will not be relabelled, substituted or published as this release. Source publication, APK construction, phone testing and GitHub release upload are separate milestones; none is implied by the source archive. See CHANGELOG.md.

Lower desktop overhead/RAM usage is a design goal, not a measured benchmark or guarantee.

## Download source

[Reviewed 1.91 source archive](Vibetram-Alpha-1.91-Source.zip) (1,711,655 bytes). This is source, not an installable APK or a complete portable Android build. The archive preserves the reviewed directory structure, per-file provenance and package manifest.

SHA-256: `c87e1942428e40af12b195f4e4a6091a90f66dba271c2d81193a658c5b9f4373`.

## Licence and OpenAI guidance

Vibetram’s code is available under Apache 2.0. For questions about OpenAI trademarks or services, consult [OpenAI’s terms](https://openai.com/policies/terms-of-use/) and [brand guidance](https://openai.com/brand/). Third-party components retain their applicable licences and notices.
