# Fedora 45 bootstrap dependency

DTK5 requires `pkgconfig(gsettings-qt)`. Fedora 45 no longer ships this
dependency: Fedora dist-git's `dead.package` records retirement under
https://pagure.io/fesco/issue/3409.

Rebuild Fedora's last maintained packaging in the same COPR before building DTK5:

```bash
copr-cli build-distgit --name gsettings-qt --distgit fedora \
  --commit fd25bedfa7006845cc7791767a2c4dc82d464f75 \
  --chroot fedora-45-x86_64 --chroot fedora-45-aarch64 \
  charofstring/gxde-dtk5
```

Recipe: https://src.fedoraproject.org/rpms/gsettings-qt

The pinned recipe uses upstream commit
`d5e002d7e0bce46c315bcc99a44a8bd51f49f488` from
https://gitlab.com/ubports/development/core/gsettings-qt,
with a SHA512-verified source in Fedora's lookaside cache.
It produces `gsettings-qt` and `gsettings-qt-devel`; do not remove DTK's
BuildRequires or disable dependency checks to work around the missing package.

Initial bootstrap build:
https://copr.fedorainfracloud.org/coprs/build/11170154

The Fedora 45 CI container enables this COPR so the same dependency is
available for build and installation checks. The scheduled DTK tag workflow
does not update this bootstrap dependency automatically.
