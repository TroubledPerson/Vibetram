# Unsigned runner qualification plan (2026-11-09)

## Established versus unverified

The source-only workflow passed on GitHub. `ci/cloud_build.py` has not run on a clean runner. Its preparation logic requires Windows, 40 GiB free before setup/build, Rust 1.95.0, Android ARM64 target, JDK17, SDK platform35/build-tools35.0.0 and NDK30.0.16248370/API29. No native or signed-release success is claimed.

The [official Windows2025 image inventory](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md) currently lists SDK35/build-tools35.0.0, NDK30.0.16248370, JDK17, Perl, CMake and Ninja, but its default Rust differs from1.95.0 and default NDK variables may point to27. These are image-documentation facts, not observations of a particular future runner; record ImageVersion and actual paths/versions in a preflight.

[GitHub's standard public runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) lists Windows x64 with4 CPUs,16GB RAM and14GB SSD, and standard public-repository usage as free. That specification does not establish the project's40GiB free-space requirement. Measure actual free bytes first; if below42949672960, stop before installation/compilation. Do not lower the guard, delete preinstalled runner contents or select a paid/larger runner as an implicit workaround.

## Routine setup still to implement and qualify

1. Keep a standard free Windows runner with no secrets and contents:read. Capture available disk and exact installed tool metadata before expensive work. Fail closed on missing/unexpected tools.
2. Explicitly prepare pinned Rust1.95.0 and components clippy/rustfmt/rust-src plus `aarch64-linux-android` in the ephemeral job. A matching `rustc` onPATH does not establish the Android target. Use rustup's official distribution, record versions, never silently upgrade. The existing rust-toolchain.toml can trigger implicit installation: replace that assumption with an explicit setup stage. See [rustup overrides](https://rust-lang.github.io/rustup/overrides.html) and [cross-compilation](https://rust-lang.github.io/rustup/cross-compilation.html).
3. Verify exact SDK/JDK/NDK source.properties and executables. Prefer the listed preinstalled versions. If absent, stop with the exact missing package; any installation/licence acceptance must be separately qualified. [Android SDK package documentation](https://developer.android.com/tools/sdkmanager).
4. Set the exact NDK30 compiler/linker and archiver for both Rust and native C/C++ dependencies. The current script sets the Cargo linker but not the target-specific CC/AR or all CMake/NDK discovery variables; default NDK27 must not be selected accidentally. Verify Perl/CMake/Ninja/MSVC availability. [Official NDK external-build guidance](https://developer.android.com/ndk/guides/other_build_systems).
5. Fetch only public locked Cargo registry dependencies and pinned Git revisions; no accounts, tokens or version/lockfile changes. Clean dependency availability and build scripts/OUT_DIR generation remain untested. A target install does not supply all third-party native build requirements.
6. Validate each selected host test filter matches expected tests rather than accepting an empty successful filter. Rerun affected Java fixtures against generated BuildPins and compiled/D8 inputs. Check the compiled APK manifest, native/package identities, notice closure and native/ZIP alignment. Existing preparation assertions are not a substitute for these observed results.

## Proposed bounded unsigned trial

First add a read-only manual runner preflight with no install/compiler, recording disk and tool versions. If it cannot meet40GiB, return that measurement and propose a smaller qualified build strategy; no guard changes are automatic. If eligible, the next separately admitted trial explicitly sets up pinned Rust/target and exact native build environment, then runs the locked selected host/Android build and existing packaging checks. Keep two Cargo jobs, no incremental build, the120-minute job limit and read-only permissions. Monitor output/headroom; a timeout or partial result is failure, not a release. No local native compilation is required by this plan.

Only an actually successful trial may upload the clearly labelled unsigned APK, same-GITHUB_SHA source.zip and measured provenance as short-lived workflow artifacts. No signing, install, phone execution, runtime network access or live enrollment is implied. A successful unsigned trial is not an installable signed public release or phone pass.

## Essential owner choice: release signer

- Existing signer in CI: preserves update compatibility, but requires explicit approval to transfer the private key/password to protected Actions secrets or an external signing service. No such transfer is authorized or implemented.
- Separate CI alpha signer: requires explicit approval of a new signing identity and secure persistence/rotation plan. Existing installs signed by the old certificate cannot receive it as an ordinary update.
- Keep the existing key local: CI builds unsigned artifacts and local signing remains a separate step. This keeps the key off GitHub but retains a desktop dependency, contrary to the desired fully cloud-built release workflow.

Do not generate a key, upload any private key, grant persistent access or enable the release job until that choice is made. Ordinary pinned tool setup and read-only checks can be handled within an admitted unsigned trial; the key custody/update-identity decision belongs to the owner. No paid resource is needed or authorized for the proposed preflight, and no paid fallback is automatic.
