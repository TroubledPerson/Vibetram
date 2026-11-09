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
