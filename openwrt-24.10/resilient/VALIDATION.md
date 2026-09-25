# v2rayA Resilient rename validation

Validated on 2026-09-25 in the existing OpenWrt 24.10.4 ARM64 VM.

- The signed public Resilient source was added with `add-resilient-feed.sh`.
  The previous personal source entry and cached package list were removed.
- Installed `luci-app-v2raya-resilient` through LuCI System > Software,
  leaving force-overwrite unchecked. LuCI pulled the exact matching service
  and core from the public HTTPS feed and replaced all three previous packages.
- All three Resilient packages showed Installed. The menu and configuration
  page displayed **v2rayA Resilient**, with status **RUNNING**.
- The modified UCI configuration remained byte-for-byte identical, SHA256
  `3d41e77675922cb491edf5e30243c9afbbfd32d6c178f47e33c6114ac4f46a15`.
  opkg retained the existing config and placed its template at `v2raya-opkg`.
- Existing test-account login and its one subscription were preserved.
- Service and core reported `2.5.7-recovery.2`, with coreVersionValid=true.
- Compared the packaged service/core bytes with the previously tested binaries:
  both are identical. The rename changes packaging, labels and migration
  metadata, not application behavior. The earlier six VPN traffic tests and
  fifteen policy tests were not rerun for this rename.

Package versions: service/core `2.5.7-recovery.2-r8.resilient1`,
LuCI `26.268.0-r8.resilient1`. Application source is
`b3c6789330daf3c25f4aaa5464ad2385a7e3c35a`; packaging code is `23efd75`,
with installation documentation updated in `453b249`.

The VM uses a test-only Cortex-A53 package architecture alias on generic ARM64.
Physical router hardware and other OpenWrt versions are not covered.
