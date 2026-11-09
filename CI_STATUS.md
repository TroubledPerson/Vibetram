# Published source; source-policy CI passed; native build unrun

The expanded 1.91 source and Actions preparation are published at privacy-corrected commit `5393963cbb3f8fcd36347122fc890b017b1307e4`. [Actions run 42623028634](https://github.com/TroubledPerson/Vibetram/actions/runs/42623028634) completed successfully: the hosted `source-checks` job ran the 13 policy tests and source-binding verification. The native `unsigned-qualification` and `release` jobs were both skipped. This was a real cloud source check, not a cloud native/Android build.

The expanded tree retains the pinned Codex Rust workspace and 1.91 Android/native inputs. Apache-2.0, upstream NOTICE and third-party notices remain applicable. Whole-tree provenance and scoped privacy/notices review are complete for this candidate, without legal/trademark clearance or a guarantee that no secrets exist. Eleven optional sample/documentation images/icons were excluded without substitute branding. Bubblewrap LICENSE contains the exact COPYING text, preserving the original symlink provenance. Originals, historical source archive and previous APKs remain preserved.

PR/push source checks are read-only. Native qualification is manual, trusted-main only, and currently assumes preinstalled exact tools and at least 40 GiB free. Those prerequisites are NOT established by the successful source job. See [CI_RUNNER_PLAN.md](CI_RUNNER_PLAN.md) for verified image metadata, implementation gaps and the proposed unsigned trial. No native compiler, SDK installation, credential transfer or signing ran in this documentation phase.

The local genuine 1.91 APK has its recorded host/package checks, but new 1.91 phone testing is PENDING. The current runtime remains offline-only synthetic authentication, fake enrollment and memory transport, with explicit activation, status-only boundaries, Stop/focus-loss cancellation and a non-renewable 120-second lifetime. No real sign-in/pairing, Internet permission, file/shell/model/capture access or persistent host registration is enabled.

CI signing is not authorized. The release job stays explicitly disabled. Future build output must be labelled unsigned until an approved signer is used, and future release source.zip must come from the exact APK build commit. The old repository ZIP is historical evidence, not the new build input. No new source ZIP or APK release was published in this stage.

Publication used the already authenticated GitHub Desktop session. The separate connector's write denial remains binding, and no credential or TLS workaround was used. Source-check success does not establish native build reproducibility or live ChatGPT compatibility.

## Read-only hosted preflight implemented

A standard-free Windows runner now inventories disk/RAM, exact installed toolchains and required paths after source checks. It performs no installs, native compilation, cleanup or signing. Its JSON artifact/summary explicitly reports qualification separately from successful inventory execution. The existing40GiB guard and pinned versions are unchanged; native qualification also requires the preflight output to be true and an explicit manual compile request. The first exact preflight result is pending this commit's hosted run.

## Explicit pinned Rust provisioning trial

A trusted main push whose commit message includes `[provision-rust195]` may explicitly install1.95.0, clippy/rustfmt/rust-src and the Android ARM64 standard library from the official Rust distribution, in fresh job-private storage. It uses the existing runner rustup, no self-update, no credentials, a600-second process limit, two IO/download workers and512MiB unpacking hint. Monitored output is8GiB with a4MiB log threshold; this is not a kernel or cumulative-write quota. At least48GiB must be free before setup, retaining the40GiB guard throughout. No manual cleanup or native compilation occurs. Later preflight in the SAME job must verify exact inputs. Another build job gets a new VM and must prepare/recheck its own tools; it cannot reuse this job's qualification by assumption. Native qualification is temporarily disabled even if the preflight succeeds, pending review of its result. Signing/release remain disabled.

Official references: [Rust1.95 release](https://blog.rust-lang.org/2026/04/16/Rust-1.95.0/), [rustup environment controls](https://rust-lang.github.io/rustup/environment-variables.html), [profiles](https://rust-lang.github.io/rustup/concepts/profiles.html). No installer or compiler was run locally.

## One bounded unsigned clean-build trial

A trusted main push explicitly marked [unsigned-trial-191] launches one standard-free Windows build job. It provisions exact Rust1.95.0 and components/Android target IN THAT VM, then requires that VM's preflight. Previous-job qualification is not reused. Other pushes/PRs cannot start this native trial. The release job stays disabled.

The native trial retains a40GiB workspace floor, requires104GiB initially for its64GiB monitored retained-output threshold, uses two Cargo/CMake workers, a90-minute overall deadline and64MiB per-command log threshold. These are monitored guards, not a kernel/cumulative-write quota. Fresh Cargo/Rustup caches, output and fixture profiles are job-private. No credential environment is passed to build/test children; sources remain locked without version changes or private accounts.

Android compilation explicitly uses NDK30 clang/clang++/llvm-ar, API29 and16KiB LOAD alignment, with static C++ runtime selection. Host tests must be collected and actually pass nonempty production filters. Java controller/auth/native tests include real monotonic expiry, followed by exact tested-class-to-D8-JAR verification. The package must preserve stored/aligned resources.arsc, native ZIP/ELF alignment, package/version/zero permissions, locked-source hashes and compiled dependency notice coverage. A fixed unused offline-only resource guarantees an actual resource table without changing the visible app label. The source ZIP comes from the exact build commit.

Only a successful trial uploads an explicitly UNSIGNED APK and measured provenance as short-lived workflow artifacts, not GitHub Releases. Missing notice coverage or unpackaged runtime dependencies fail closed. A failed trial retains bounded public-safe JSON diagnostics, not an unvalidated APK. Phone testing and signing remain pending. No local native compiler, SDK install, key upload or actual login/pairing occurs.

## First trial and pinned licence-link accounting correction

Run42634616898 stopped in dependency preparation when the monitor rejected a filesystem link; no test or APK success is claimed. The initial diagnostic did not retain the offending path. Static metadata of locked nucleo commit4253de9faabb4e5c6d81d946a5e35a90f87347ee independently establishes matcher/LICENSE is the exact link ../LICENSE (Git blob ea5b60640b01f74e295037aa8a6b7d4ea278a739). Its regular root LICENSE is16725bytes, Git blob a612ad9813b006ce81d1ee438dd784da99a54007.

The monitor now handles only that pinned Cargo-checkout licence link, checking relative checkout identity, exact target text, regular target/ancestors and full Git-blob identity. It counts at least4KiB for link metadata; the regular target is counted by the ordinary walk. It does not follow arbitrary links. Unknown file links, directory links/junctions, wrong targets or mismatched contents remain fatal with a relative-path diagnostic. No dependency/link content, lockfile, disk floor, output/time/CPU threshold or permissions changed. This corrects a concrete overly broad link rejection while preserving containment/accounting. One bounded repair trial follows; prior failure evidence remains retained.

The licence identity check permits only UTF-8 CRLF-to-LF checkout normalization, consistent with the upstream source review; all other text changes still fail the exact public Git-blob identity. Windows separator and Git-blob known-vector fixtures cover the monitor implementation before the repair trial.

## Bounded no-compile lock/link diagnosis

A trusted [lock-diagnostic-191] commit triggers metadata work only, not the unsigned compile job. Exact Rust1.95/target/components are prepared and rechecked on its own standard-free temporary Windows VM. A10-minute process budget,8GiB monitored retained-output threshold,32MiB command-log threshold and unchanged40GiB floor apply; no cleanup or compiler invocation is permitted.

The diagnostic fetches the seven already-locked public Git commits into bare object stores and qualifies licence links by exact tracked link blobs, internal Git-tree target resolution and regular licence-text blob identity. It never follows unknown filesystem targets. This also covers renamed upstream Git repositories through normal authorized Git transport; no rejected connector/API endpoint is retried or bypassed.

It copies the Rust workspace into disposable storage, probes cargo metadata --locked, and permits only an offline workspace lock proposal there. The committed lockfile is checked unchanged. The proposal is never used to compile, copied back or adopted automatically. Reports compare every package version/source/checksum and dependency edge, with a clearly labelled proposed-not-adopted lockfile/diff if generated. An incomplete offline resolution is reported rather than fetching unapproved new packages or substituting versions. Native compilation, signing, Releases and device actions do not run in this stage.

## Reviewed exact lock and five-link repair

No-compile run42640665926 succeeded on exact Rust1.95.0. Its disposable proposal a52305dae660c260e5b33a6dd4b3d0cecb9bf4ef56836dfc0dbf9e587754ff0d changes155 local workspace entries from0.0.0 to the already-declared0.156.0 and adds the existing Android libc declaration to codex-arg0's dependency list. All external package entries, versions, sources and checksums are unchanged. This exact reviewed proposal is now adopted, without changing manifests or dependency pins.

The same run audited all seven pinned Git trees. The only five licence links were nucleo matcher/LICENSE and h3's h3, h3-datagram, h3-quinn, h3-webtransport LICENSE links, all ../LICENSE. h3's regular root licence is1054bytes, Git blob97d180d899ac03e8db023a2aec14f3d223e7df39 at locked commite07e69412876f7e26f026bd75a48b2704d8c8283. Their unchanged text, exact target and tracked identities are now covered by the same fail-closed monitor rules; every unknown link remains fatal.

One dual-marked repair trial first requires a fresh no-compile locked metadata success and an offline workspace update producing zero lock delta on its own VM. Only after that diagnostic succeeds can the separate unsigned build job start, with its own fresh toolchain/preflight and all existing guards. Source-policy tests include the exact reviewed lock and external-entry fingerprint. No signed output or public Release is enabled; no phone success is claimed.

## Installed Microsoft x64 linker qualification

The reviewed lock/link trial42642356032 passed locked metadata with zero delta and all five exact licence links, then stopped at the first host dependency build scripts: link.exe returned GNU-style extra-operand errors for MSVC arguments. No native test binary or APK completed.

The next single bounded trial uses Microsoft's installed vswhere and VsDevCmd.bat -arch=x64 -host_arch=x64. It verifies Microsoft Authenticode/company/version/SHA256 for vswhere, cl, link and lib, exact Hostx64/x64 paths, the discovered VC/SDK libraries and headers, and resolved link.exe. Only selected developer environment fields enter the sanitized child process; no machine/global settings change. Rust's Windows host linker and C/C++ tools are explicit, while the pinned Android NDK selection is retained.

Before Cargo compilation, tiny C/Windows-SDK and exact-Rust1.95 x64 programs must compile/link and validate as PE x64. These test executables are not run. Each command has a bounded deadline and the qualification has a180-second checked budget under the existing disk/output monitor. Failure preserves a small msvc-qualification report and stops before the full build. Only if it passes does the existing unsigned trial continue. No tool installation, dependency/version change, signing or Release is added.

Official setup references: https://github.com/microsoft/vswhere/wiki/Find-VC and https://learn.microsoft.com/en-us/cpp/build/building-on-the-command-line?view=msvc-170

## Discovery-only environment correction and tiny probe

Run42644436451 confirmed the initial PATH points to Git usr/bin/link.exe. Microsoft-signed vswhere3.1.7.39155 passed provenance checks, but returned no installation under the private sanitized environment; no C/Rust fixture or Cargo compilation ran. That qualification remains failed, not a successful MSVC setup.

A separate [msvc-probe-191] run now compares the same installed vswhere command before/after adding only the known public ProgramData and ALLUSERSPROFILE registration locations to the discovery/setup subprocess. No account environment or credentials are imported; compiler children still receive only the selected VC fields. Empty/ambiguous discovery stops with a precise category. Only tiny compile/link fixtures may run in this probe, never Cargo or application compilation. A further full unsigned trial remains blocked pending actual tiny-probe success.

The tiny-only probe42645570825 established the discovery cause: sanitized baseline found0 installations; adding the two public registration locations found1. The official setup then emitted identical LIBPATH entries because Windows set LIB includes prefix matches. No fixture or Cargo compile ran. The parser now treats only identical repeated known-key values as idempotent and still rejects every conflicting duplicate. A bounded tiny-only probe verifies the correction before any full trial.

Tiny probe42646138226 verified Microsoft Authenticode and versions for cl19.51.36260.0 and link/lib14.51.36260.0. It then stopped before fixture compilation because the input check incorrectly expected stdio.h under MSVC. The UCRT header is now checked under the selected Windows SDK Include/version/ucrt; vcruntime.h remains a VC-toolset input. Every required input's presence is recorded before failure. This corrects the check without installing or substituting tools. See https://learn.microsoft.com/en-us/cpp/c-runtime-library/crt-library-features?view=msvc-170

Tiny probe42646712950 established installed VS18 Enterprise, VC14.51.36231 and SDK10.0.26100.0 with all six required inputs present and valid Microsoft tool signatures. It stopped on a raw LIB-path substring check before compilation. LIB directories are now compared as absolute normalized Windows path entries, preserving case-insensitive/separator semantics and rejecting relative/traversing entries. The selected entries are recorded so any remaining mismatch is explicit; exact executable and input identity checks remain in place.

Tiny probe42647268189 passed exact Microsoft executable signatures, required input files and normalized VC/SDK LIB directories. It stopped because Microsoft link.exe /? returned1100 while printing its normal help banner. The redundant help invocation is removed; valid signatures/file versions and the two actual tiny C/Rust link checks provide qualification. Zero-exit enforcement for compile/link commands remains unchanged. No dependency/native-application compilation has run in these tiny probes.

## No-traversal reparse metadata instrumentation

The monitor still fails immediately on every unknown directory link. After its active child tree is stopped, it may record only that link object's own metadata using Windows open-reparse-point/back-up-semantics handles, then FSCTL_GET_REPARSE_POINT. It holds each verified regular ancestor without share-write/delete, rejects reparse ancestors, checks handle/file identities and repeated raw reparse data, and never opens or enumerates the target. A sharing/access failure remains fatal; no alternate access or ACL change is attempted.

Records are bounded to16KiB of reparse data and64KiB public-safe JSON, with a checked5-second metadata budget. Unknown tags, malformed data, target escapes, self/ancestor cycles and races remain unqualified. Internal-looking targets are lexical candidates only, never permission to traverse or exclude them. External target strings are minimized to class/volume/hash. File timestamps and the active phase/PID establish correlation, not proven creator attribution.

One instrumented tiny-only hosted probe may run. The full Cargo/native-application job and Release remain disabled for its commit. No accounting exception is introduced; all existing dependencies, floors, time/output guards and failure evidence are retained.

## Independent physical IE directory qualification

Instrumented probe42650152605 captured Content.IE5 as mount-point tag0xa0000003 with stored target IE inside the same job work root, without traversing it. This proves target text, not target-directory regularity or creator attribution.

A next tiny-only probe adds independently constructed physical-path metadata opens for precisely the observed INetCache/IE location. Every component must be a regular directory, same volume, with stable unique file identities; any reparse ancestor, conflicting alias identity, access/sharing failure, race or different mapping stays fatal. Link metadata is rechecked after the physical query. No target contents are read or enumerated and no accounting exception is added. Successful target metadata would support designing a future exact alias rule, not silently enable compilation or establish whole-profile write confinement. Security-alert inspection is outside this work and unresolved publication concerns still bar release.

## Exact job-owned Content.IE5 accounting rule

Physical metadata probe42651622182 verified the independently named IE directory and all12 ancestors as stable same-volume regular directories, distinct from the junction. The monitor now permits only this exact already-observed mapping, revalidating it on every accounting pass while holding source/target/ancestor metadata handles across the independent scan. It charges32KiB alias metadata, prunes Content.IE5 from traversal, and requires exactly one IE-root enumeration. No global link exclusion is introduced.

Alias and target identities/raw record are pinned within each job and checked before/after scans. A newly appearing alias requires a fresh leased snapshot; an already qualified alias disappearing/replacing, any metadata/access/sharing ambiguity, root overlap, unknown link, target file snapshot race or inaccessible walk is fatal. Fatal accounting errors latch, preventing automatic retries in finalizers. Existing40GiB floor,64GiB monitored output, deadlines, CPU limits, dependency pins and five exact licence links remain unchanged.

One tiny-only compiler/link probe follows synthetic policy/count tests. No full Cargo/native-app compile, signing, Release or security-alert investigation is included; unresolved publication concerns remain a release blocker.

## Tiny qualification passed; one unsigned full-build trial

Run42654399508 at79f2649 passed the real tiny C/Windows-SDK and Rust1.95 x64 compile/link checks in32.641seconds. Both PE files were validated and neither executed. The actual guarded scan qualified the exact alias, charged32KiB metadata and pruned it, with a distinct regular same-volume target and12 verified ancestors. All146 preparation tests passed.

The next full trial calls the same Guard and qualify_msvc implementation; no duplicate accounting/controller path is introduced. Fresh VM provisioning, locked metadata with zero lock delta, fresh strict preflight and tiny link qualification remain required. Public qualified-msvc.json pins the passing Microsoft toolset/SDK, executable versions and SHA256s, setup script and six SDK/VC inputs; changes fail before application Cargo compilation. Exact Rust build identity is checked as well.

This trusted dual-marked push authorizes one existing bounded unsigned full build only:40GiB free floor,64GiB monitored retained-output threshold,104GiB initial headroom, two workers and90-minute process deadline remain unchanged. Signing, Release and security-alert inspection remain disabled/out of scope; pending separate security review still bars release. Cloud native/Android/package success and phone testing are not inferred from the tiny probe.

## Verified scratch-handle snapshots; bounded incomplete rescans

Run42655744075 passed exact tool pins, locked resolution and67 alias-accounting passes, then the namespace walker failed on a disappearing target/ci-test/deps/rmeta scratch directory. Cargo dependency compilation had started; no host test binary, Android compile or APK completed. No dependency/security diagnosis is inferred from this monitor stop.

The repair is limited to six-character rmeta scratch names directly in the pinned host/Android ci-test deps locations. It opens each leaf without following reparses, verifies regular type/identity and same-volume regular ancestors, and enumerates all bounded file metadata through that same handle instead of descending by a replaceable path. Unknown children/directories/reparses, rename/replacement, missing-before-verification, permissions and ambiguity remain fatal. Parent identities and leaf identity/creation metadata are pinned; share-delete on the leaf permits normal cleanup without changing ACLs.

Only a verified regular handle with Windows DeletePending confirmation may interrupt a snapshot. Such a pass produces no total: handles close, prior observed peak and known partial/allocation bytes remain retained, and a whole fresh snapshot is attempted, at most3 times/check and256 interruptions/job. Resource/free-space/log/time checks run before and between attempts, without resetting clocks or reservations. Exhaustion latches failure. Unverified file disappearance is fatal rather than silently counted as zero. Alias/IE identity rules are unchanged and remain fatal on their races.

This remains monitored, non-atomic retained-space accounting, not an exact historical maximum or hard cumulative-write quota. Incomplete residual sizes are reported unknown, never zero; a rescan does not reconstruct bytes created/deleted between observations. The original full64GiB reservation and40GiB physical free-space floor remain held independently; no allowance is released because data disappeared.

Official metadata contracts: https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info and https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_both_dir_info . One bounded unsigned retry is authorized after synthetic policy/privacy review. Signing/Release and pending-alert inspection remain excluded.

## Fresh ordinary-entry metadata and bounded enumeration telemetry

Run42661462853 stopped after33 qualified alias passes on ALIAS_VALIDATED_SCAN_DEADLINE while Cargo compilation was active. Its last completed sampled retained total was2172553126bytes. There were no confirmed scratch-disappearance rescans. It did not produce an Android APK or native test result.

The monitor now uses one fresh os.lstat metadata record for each ordinary directory/file entry, checks type and Windows reparse attributes/tag, and counts regular sizes from that fresh record. It does not use cached DirEntry sizes. Existing exact alias leases, held-handle scratch enumeration, pinned licence bytes and fatal missing/access/unknown-type rules remain active. The five-second alias-validation-plus-scan deadline is unchanged.

Enumeration checks physical free space, retained partial/previous peak and the global trial time/log budget at every root boundary and at most256 entries or0.25seconds between metadata operations. This cannot interrupt a blocking filesystem operation or guarantee a hard write cap. Root-index telemetry reports duration, ordinary file entries, directory entries, scratch leaves and confirmed partial bytes; a failed root has no completed total. These measurements exclude scratch child-entry counts enumerated inside the specialised handle policy. Full trees are still rescanned; sustainability at clean-build scale remains unverified.

Local synthetic equivalence/failure tests and a bounded regular-tree benchmark precede one unsigned hosted trial. No security alert inspection, signing, Release, permission or tool-pin changes are included.

## Whole-snapshot invalidation for exact compiler object churn

Run42664118196 completed62 validated alias scans with periodic resource checks, then fresh metadata of an ordinary compiler rcgu.o file returned Windows error2. The partial scan was rejected; no Android APK or native test result completed.

The new accommodation applies only to direct rcgu.o entries of the job-owned host/Android ci-test deps roots and exact FileNotFoundError with winerror2 from the fresh entry metadata call. It is not proof that a vanished object was harmless. Its whole snapshot is invalidated, never accepted with a skipped entry or zero size. All roots must be fully rescanned, at most3 attempts within ONE nonrenewable five-second window, with independent periodic physical free/output/log/global-time checks. The full reservation and prior accepted/observed peaks remain held; unknown residual bytes stay unknown. Repeated churn, expiry or256 invalidations/job fail closed.

Before descending into either compiler scratch root, no-follow handles verify and hold that root and every regular same-volume ancestor without share-delete/write. Identity/creation baselines persist across scans, so root/ancestor replacement, links, denial and unexpected IO remain fatal. All leaf reparses, including replacements on a later complete pass, still go through existing fail-closed link policies. Special held-handle rmeta and pinned licence/alias rules are retained. The alias metadata collector's five-second limit is unchanged, and the outer snapshot window can only be stricter.

Last completed per-root telemetry is now preserved separately from a discarded/failed current scan. This remains non-atomic retained-space monitoring, not exact cumulative writes or a hard quota; ephemeral bytes between observations are not reconstructed. No signing, Release, credentials or security-alert inspection is included.
