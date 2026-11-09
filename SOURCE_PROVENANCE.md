# Expanded 1.91 source provenance

Public base: openai/codex rust-v0.156.0, commit fe74a774532af67b5a4a3dec03ce9469e17f89af, codex-rs tree 4d801c92b75f358678e87c2ac6e84b245713c8eb. All 7827 upstream Rust-workspace paths are present. Comparison found 7802 content matches (raw bytes first, UTF-8 CRLF-to-LF fallback only), 25 recorded Android/status-only integration modifications, and 11 original native additions. MODIFICATIONS.json records the actual pre-notice hashes. Candidate modifications carry prominent comments; original engineering inputs are preserved elsewhere and are not edited by this review.

android/src is the actual nine-file Android 1.91 port, android/AndroidManifest.xml is its zero-permission manifest, and android/host-tests contains synthetic checks. Required dependency notices are in android/assets. This folder is expanded source, not a release ZIP. The older published source ZIP is not substituted for it. Future source.zip must come from the exact CI build commit.

The local upstream comparison verifies content provenance, not legal/trademark clearance or a clean-runner build. The vendored bubblewrap LICENSE entry was an upstream symlink to COPYING; the Windows extracted tree represents that entry as the regular text COPYING. Its full COPYING remains alongside it. Publication-mode restoration and build compatibility must not be assumed from blob hashes alone.

Whole-tree source review found public upstream marker/test fixtures, not owner credentials, at the twelve previously flagged paths. They match the exact upstream Git blob identities. No private signing files, browser credentials, runtime account data or private logs were copied. Pattern checks are not a guarantee of absence. Upstream image assets remain a separate owner-scope issue: they have not been approved as Vibetram artwork or publication assets. Publication stays blocked until that inclusion/build-input decision is resolved.


## Review checkpoint 04 — current disposition

The earlier upstream-artwork blocker is resolved by omitting 11 optional sample/documentation images/icons and removing their six reference locations. Exact backups remain outside this expanded publication folder. No substitute branding was added. ASSET_EXCLUSIONS.json identifies every omitted file. The bubblewrap LICENSE is now a regular file containing the exact unmodified COPYING licence text, preserving its original upstream symlink-to-COPYING provenance in this record and protected backup. This is a portable source representation, not a changed licence grant.

Whole-tree source provenance and scoped privacy/notices review is complete for this candidate; this is not legal/trademark clearance or a guarantee that no secrets exist. Source publication readiness is separate from build validation. GENERATED_INPUTS_REVIEW.json records dynamic/toolchain inputs that remain unexecuted. Clean-runner, Android compile and phone tests remain unverified; CI signing is not authorized and the release job remains disabled. No source ZIP belongs in the repository: future release source.zip must be generated from the exact APK build commit.


## Historical published checkpoint (superseded where noted above)

# Source provenance



Public base: https://github.com/openai/codex/tree/fe74a774532af67b5a4a3dec03ce9469e17f89af (annotated tag rust-v0.156.0 resolves to this commit through the official GitHub API).



The historical 5606b6c0ac6554bab2c049f1d07be79d8af2b90e identifier is a local android-openssl-probe commit, not an absent public upstream commit. Its recorded change enables the Android arm64 openssl-sys vendored feature in codex-rs/core/Cargo.toml. The recorded local compatibility files are app-server-transport/src/transport/unix_socket.rs, arg0/Cargo.toml, arg0/src/lib.rs, core/src/installation_id.rs and network-proxy/src/credential_broker/replacement.rs. This component snapshot does not claim to contain all compatibility/build inputs.



The native overlay contains the reviewed app-server and app-server-transport source checkpoint, including project status-only gate/session/auth-pairing changes. It derives through the preserved 1.85 native candidate, corrected activation-time gate, 1.90 offline session and 1.91 final host revision. Native originals changed relative to the accessible local baseline carry a prominent provenance/modification notice in this copy. Source and copied-byte SHA-256 values are listed in SOURCE_MANIFEST.json. Public connection_auth.rs and remote_control/protocol.rs at the base match recorded baseline SHA-256 values after LF-to-CRLF conversion.



integration-java contains the five final 1.91 host integration files. legacy-android-java contains 92 historical 1.83 Android Java files for source reference, not a complete 1.91 Android application; the generated private BuildEvidence.java stamp is excluded. The legacy tree is not newly validated against 1.91. No live credentials, runtime state, private notes, logs, local build paths or original signing configuration accompany this snapshot.



This snapshot adds notices and documentation only; it does not alter the preserved engineering inputs or prove a reproducible Android release. The maintainer must qualify complete public build inputs and required notices before a release claim.