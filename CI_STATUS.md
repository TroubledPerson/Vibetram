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
