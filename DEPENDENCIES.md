# Dependency and notice review

Source-only candidate: no Cargo registry/Git dependency source archives, native libraries, executables, APKs, toolchains or third_party directories are shipped. The native package Cargo.toml files remain dependency declarations resolved through the pinned upstream workspace, not a claim that all external packages are Apache-2.0.

The upstream root licence is Apache-2.0. Its NOTICE includes OpenAI Codex and MIT-licensed Ratatui-derived attribution and is retained conservatively. Upstream's separate third_party directories (PowerShell, V8, voice, wezterm and Wine) are not copied into this candidate. This does not establish that none of their code would be transitively included in a later binary.

The historical Android build statically vendors OpenSSL through openssl-sys. The pinned lockfile records native-tls 0.2.14, openssl 0.10.75 and openssl-sys 0.9.111, among many other dependencies. No third-party archive is redistributed in this source snapshot. Before distributing an APK, resolve the actual Android feature/target closure from its final lockfile, identify bundled native dependencies and assets, and include their applicable licence/copyright/NOTICE texts. Do not substitute a workspace-wide package list or build success for that binary notice audit.

The existing metadata-only probe listed 155 workspace packages with licence metadata; it did not enumerate all external transitive dependencies and does not clear them. Public source preparation does not authorize downloads, account access, live pairing or credential reuse.
The historical Android Java reference includes earlier auth, network and local capture tools; it is not a zero-permission 1.91 application or a grant to activate those tools. Public source inspection is separate from execution. A future offline APK must select only its reviewed inputs and verify its manifest and permission boundary.


## Historical published checkpoint (superseded where noted above)

# Dependency and notice review

Source-only candidate: no Cargo registry/Git dependency source archives, native libraries, executables, APKs, toolchains or third_party directories are shipped. The native package Cargo.toml files remain dependency declarations resolved through the pinned upstream workspace, not a claim that all external packages are Apache-2.0.

The upstream root licence is Apache-2.0. Its NOTICE includes OpenAI Codex and MIT-licensed Ratatui-derived attribution and is retained conservatively. Upstream's separate third_party directories (PowerShell, V8, voice, wezterm and Wine) are not copied into this candidate. This does not establish that none of their code would be transitively included in a later binary.

The historical Android build statically vendors OpenSSL through openssl-sys. The pinned lockfile records native-tls 0.2.14, openssl 0.10.75 and openssl-sys 0.9.111, among many other dependencies. No third-party archive is redistributed in this source snapshot. Before distributing an APK, resolve the actual Android feature/target closure from its final lockfile, identify bundled native dependencies and assets, and include their applicable licence/copyright/NOTICE texts. Do not substitute a workspace-wide package list or build success for that binary notice audit.

The existing metadata-only probe listed 155 workspace packages with licence metadata; it did not enumerate all external transitive dependencies and does not clear them. Public source preparation does not authorize downloads, account access, live pairing or credential reuse.
The historical Android Java reference includes earlier auth, network and local capture tools; it is not a zero-permission 1.91 application or a grant to activate those tools. Public source inspection is separate from execution. A future offline APK must select only its reviewed inputs and verify its manifest and permission boundary.
