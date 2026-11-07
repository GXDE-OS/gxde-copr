#!/usr/bin/env python3
"""Lock GXDE core desktop components to release tags and generate the split
gxde-core-* package SRPM trees.

Branch-pinned modules (matching AUR's _branch map) use git describe on the
pinned branch to find the latest reachable tag — the same semantics as AUR's
prepare().  Other modules use the highest numeric tag across all refs.

The historical single gxde-core bundle was split (2026-10-20) into 17
purpose-based packages plus a metapackage, all built under the single COPR
project charofstring/gxde-core.  One shared upstream-lock.json pins every
module; each group derives its own version (from its primary module's tag)
and release (bumped when that group's module commits change).
"""
import argparse
import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('dtk_sources', Path(__file__).with_name('dtk5-sources.py'))
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)

ROOT = sources.ROOT
PACKAGE = ROOT / 'packages/gxde-core'

# AUR _branch map — these modules are cloned from a non-default branch and
# the latest tag *reachable from that branch* is used, not the global max.
BRANCH = {
    'gxde-sni-server': 'main',
    'gxde-top-panel-plugins': 'd20',
    'gxde-file-manager': 'char/qt6_migration',
    'gxde-terminal': 'dtk6',
    'rofd': 'main',
}

TAG = re.compile(r'v?(\d+(?:\.\d+)*(?:\+\d+(?:\.\d+)*)?)(?:(?:-?gxde(\d+))|(?:-arch(\d+))|(?:-(\d+)))?$')


def tag_key(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f'Unsupported release tag: {tag}')
    numbers = tuple(map(int, re.findall(r'\d+', match[1])))
    kind = 3 if match[3] else 2 if match[2] else 1 if match[4] else 0
    return numbers + (0,) * (10 - len(numbers)), kind, int(match[3] or match[2] or match[4] or 0)


def latest_tag(refs):
    tags, peeled = {}, {}
    for line in refs.splitlines():
        sha, ref = line.split()
        if not ref.startswith('refs/tags/'):
            continue
        name = ref.removeprefix('refs/tags/')
        if name.endswith('^{}'):
            peeled[name[:-3]] = sha
        elif TAG.fullmatch(name):
            tags[name] = sha
    if not tags:
        raise ValueError('No stable numeric release tags found; refusing a HEAD fallback')
    tag = max(tags, key=lambda value: (tag_key(value), value))
    return tag, peeled.get(tag, tags[tag])


def rpm_version(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f'Unsupported release tag: {tag}')
    suffix = match[2] or match[3] or match[4]
    return match[1].replace('+', '.') + (f'.gxde{suffix}' if match[2] else f'.{suffix}' if suffix else '')


def describe_branch_tag(repo_url, branch):
    """Clone (blobless) and return the latest tag reachable from the branch tip.

    Mirrors AUR's ``git describe --tags --abbrev=0`` on the checked-out branch.
    """
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['git', 'clone', '--filter=blob:none', '--bare', repo_url, tmp],
                       check=True, timeout=600)
        branch_tip = subprocess.check_output(
            ['git', '-C', tmp, 'rev-parse', f'refs/heads/{branch}'],
            text=True).strip()
        result = subprocess.run(
            ['git', '-C', tmp, 'describe', '--tags', '--abbrev=0', branch_tip],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f'{repo_url}: no tag reachable from branch {branch}')
        tag = result.stdout.strip()
        if not TAG.fullmatch(tag):
            raise ValueError(f'{repo_url}: branch {branch} describe returned non-numeric tag: {tag}')
        commit = subprocess.check_output(
            ['git', '-C', tmp, 'rev-parse', f'refs/tags/{tag}^{{}}'],
            text=True, stderr=subprocess.DEVNULL).strip()
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            commit = subprocess.check_output(
                ['git', '-C', tmp, 'rev-parse', f'refs/tags/{tag}'],
                text=True).strip()
        return tag, commit

# ---- BuildRequires building blocks (Fedora 45 names) ----
BASE = [
    'gcc gcc-c++ make cmake ninja-build pkgconf-pkg-config',
    'python3 gettext jq',
    'extra-cmake-modules lxqt-build-tools',
]
QT5 = [
    'qt5-qtbase-devel qt5-qttools-devel qt5-linguist qt5-qtsvg-devel',
    'qt5-qtx11extras-devel qt5-qtdeclarative-devel qt5-qtmultimedia-devel',
]
QT6 = [
    'qt6-qtbase-devel qt6-qtbase-private-devel qt6-qttools-devel qt6-linguist',
    'qt6-qtdeclarative-devel qt6-qtsvg-devel qt6-qt5compat-devel qt6-qtwayland-devel',
]
DTK = [
    'gxde-dtk5-devel gxde-dtk2-devel gxde-dtk2-widget-devel',
    'gxde-dtk6-devel gxde-dtk2-qt6-devel',
    'gxde-infra gxde-infra-devel',
]
X11 = [
    'pkgconfig(x11) pkgconfig(xext) pkgconfig(xtst) pkgconfig(xcb)',
    'xcb-util-devel xcb-util-wm-devel pkgconfig(xcb-image) pkgconfig(xcb-ewmh)',
    'pkgconfig(xcursor) pkgconfig(xfixes) pkgconfig(xi)',
    'pkgconfig(xrandr) pkgconfig(xscrnsaver) pkgconfig(xkbcommon)',
    'wayland-devel',
]
GLIB = [
    'glib2-devel pkgconfig(gio-unix-2.0) gtk3-devel',
    'pkgconfig(cairo) pkgconfig(librsvg-2.0) pkgconfig(gdk-pixbuf-2.0)',
    'pkgconfig(fontconfig) pkgconfig(freetype2)',
]
SYS = [
    'dbus-devel systemd-rpm-macros pam-devel openssl-devel libxcrypt-devel',
    'pkgconfig(alsa) pkgconfig(libpulse) pkgconfig(libpulse-simple)',
    'libgudev-devel gsettings-qt-devel gsettings-qt6-devel',
    'polkit-qt5-1-devel polkit-qt6-1-devel pkgconfig(zlib)',
]

GTK_MENU_SCRIPTLETS = '''
# gxde-wayland-gtk-menu: register/unregister the appmenu GTK module in
# /etc/gtk-3.0/settings.ini (mirrors AUR gxde-core-git.install).
%post
/usr/lib/gxde-wayland-gtk-menu/update-gtk-settings enable 2>/dev/null || \\
    echo "warning: could not enable appmenu GTK module" >&2

%preun
if [ "$1" -eq 0 ]; then
    /usr/lib/gxde-wayland-gtk-menu/update-gtk-settings disable 2>/dev/null || \\
        echo "warning: could not disable appmenu GTK module" >&2
fi'''

# ---- group manifest (order = build/submit waves are derived separately) ----
GROUPS = {
    'gxde-artwork': {
        'modules': ('gxde-account-faces', 'gxde-icon-theme', 'deepin-gtk-theme',
                    'gxde-artwork', 'gxde-wallpapers', 'gxde-sound-theme',
                    'gxde-default-settings'),
        'version_from': 'gxde-artwork',
        'summary': 'GXDE themes, icons, wallpapers, sounds and default settings',
        'description': 'GXDE desktop artwork: icon themes (gxde, deepin, dark, Sea),\n'
                       'GTK theme, wallpapers and blur caches, sound theme, account faces\n'
                       'and default desktop settings including tuning assets.',
        'br': ['make gettext xcursorgen gtk-update-icon-cache python3',
               'glib2-devel ImageMagick'],
        'devel': False, 'tools': (), 'debug_package': False,
        'requires': [], 'provides': [],
        'conflicts': ['deepin-gtk-theme deepin-sound-theme deepin-wallpapers'],
        'scriptlets': '',
    },
    'gxde-libs': {
        'modules': ('gxde-network-utils-qt6',),
        'version_from': 'gxde-network-utils-qt6',
        'summary': 'GXDE internal network utility library',
        'description': 'The gxde-network-utils-qt6 network device, model and worker\n'
                       'library used by the dock, panels and control center. GXDE\n'
                       'Bernese is packaged separately in charofstring/gxde-gxtk7.',
        'br': BASE + QT6 + DTK + X11 + ['gsettings-qt6-devel'],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-daemon': {
        'modules': ('deepin-daemon', 'gxde-daemon', 'startgxde', 'deepin-menu',
                    'gxde-sni-server', 'gxde-globalmenu-service',
                    'gxde-wayland-gtk-menu', 'transhell', 'garma'),
        'version_from': 'deepin-daemon',
        'summary': 'GXDE session daemons and base services',
        'description': 'GXDE session base services: deepin-daemon and gxde-daemon (with\n'
                       'dock, daemon-manager and gtk-theme-inject plugins), the startgxde\n'
                       'session starter, deepin-menu, the status-notifier-item server, the\n'
                       'globalmenu service, the wayland GTK menu bridge, garma and\n'
                       'transhell assets.',
        'br': BASE + QT5 + QT6 + DTK + X11 + GLIB + SYS + [
            'golang librsvg2-tools libnl3-devel',
            'libinput-devel mtdev-devel libsecret-devel',
            # Full cgo pkg-config set of the vendored gocode-gxde bindings:
            # alsa gdk-3.0 gdk-pixbuf-2.0 gdk-pixbuf-xlib-2.0 gdk-x11-3.0
            # glib-2.0 libcanberra libpulse libpulse-simple x11.
            'gdk-pixbuf2-xlib-devel pkgconfig(libcanberra)',
            # sni-server/garma pkg_check_modules needs libcjson.
            'cjson-devel',
            # deepin-menu (qmake6) includes <LayerShellQt/Shell>;
            # globalmenu-service is Qt5-based: KF5Config/KF5CoreAddons/
            # KF5WindowSystem + Qt5X11Extras (QT5 set covers the Qt side).
            'layer-shell-qt-devel kf5-kconfig-devel kf5-kcoreaddons-devel',
            'kf5-kwindowsystem-devel',
            # gxde-sni-server: find_package(KF6 COMPONENTS CoreAddons Crash
            # DBusAddons StatusNotifierItem) ≥ 6.10.
            'kf6-kcoreaddons-devel kf6-kcrash-devel kf6-kdbusaddons-devel',
            'kf6-kstatusnotifieritem-devel',
        ],
        'devel': False, 'tools': ('policy',), 'debug_package': True,
        'requires': ['python3 python3-pydbus python3-gobject',
                     'xdg-desktop-portal'],
        'provides': [], 'conflicts': ['deepin-daemon deepin-menu deepin-session'],
        'scriptlets': GTK_MENU_SCRIPTLETS,
    },
    'gxde-polkit-agent': {
        'modules': ('gxde-polkit-agent', 'dpa-ext-gnomekeyring'),
        'version_from': 'gxde-polkit-agent',
        'summary': 'GXDE polkit authentication agent',
        'description': 'The GXDE polkit authentication agent (Qt5/dtkwidget) and the\n'
                       'GNOME keyring agent extension.',
        'br': BASE + QT5 + DTK + X11 + ['polkit-qt5-1-devel gsettings-qt-devel'],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': ['polkit-pkla-compat'], 'provides': [],
        'conflicts': ['deepin-polkit-agent'], 'scriptlets': '',
    },
    'gxde-dock': {
        'modules': ('gxde-dock',),
        'version_from': 'gxde-dock',
        'summary': 'GXDE dock',
        'description': 'The GXDE dock (Qt6): taskbar, tray and the dock plugin\n'
                       'interface consumed by panel and file-manager plugins.',
        'br': BASE + QT6 + DTK + X11 + [
            'gsettings-qt6-devel layer-shell-qt-devel',
            'libdbusmenu-lxqt-devel kf6-kwindowsystem-devel',
            'qt6-qtmultimedia-devel gxde-libs-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-top-panel': {
        'modules': ('gxde-top-panel', 'gxde-top-panel-plugins'),
        'version_from': 'gxde-top-panel',
        'summary': 'GXDE top panel and plugins',
        'description': 'The GXDE top panel and its plugin set (Qt6): appmenu, tray,\n'
                       'keyboard layout, onboard, trash, notify, overlay warning, show\n'
                       'desktop and disk mount plugins.',
        'br': BASE + QT6 + DTK + X11 + [
            'gsettings-qt6-devel layer-shell-qt-devel libdbusmenu-lxqt-devel',
            'kf6-kwindowsystem-devel libxdo-devel',
            'gxde-libs-devel gxde-dock-devel gxde-bernese-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-control-center': {
        'modules': ('gxde-control-center',),
        'version_from': 'gxde-control-center',
        'summary': 'GXDE control center',
        'description': 'The GXDE control center (Qt6/dtk6): system settings modules\n'
                       'for appearance, desktop, sound, network, power, accounts and\n'
                       'more.',
        'br': BASE + QT6 + DTK + X11 + GLIB + SYS + [
            'qt6-qtmultimedia-devel qt6-qtwebengine-devel qt6-qtscxml-devel',
            'kf6-kcoreaddons-devel kf6-kcrash-devel kf6-kdbusaddons-devel',
            'kf6-kwindowsystem-devel kf6-kglobalaccel-devel',
            'kf6-kstatusnotifieritem-devel kf6-kcodecs-devel',
            'kf6-networkmanager-qt-devel libdbusmenu-lxqt-devel layer-shell-qt-devel',
            'lightdm-qt5-devel lightdm-qt6-devel gtest-devel',
            'gxde-libs-devel gxde-bernese-devel libudisks2-devel libwebp-devel file-devel',
        ],
        'devel': False, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-wallpaper-chooser': {
        'modules': ('gxde-wallpaper-chooser',),
        'version_from': 'gxde-wallpaper-chooser',
        'summary': 'GXDE wallpaper and screensaver chooser',
        'description': 'The GXDE wallpaper, lock-screen wallpaper and screensaver\n'
                       'chooser, including the embeddable wallpicker development library.',
        'br': BASE + QT6 + DTK + [
            'qt6-qtmultimedia-devel gsettings-qt6-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': ['gxde-file-manager gxde-control-center'],
        'provides': ['gxde-wallpaper'], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-launcher': {
        'modules': ('gxde-launcher',),
        'version_from': 'gxde-launcher',
        'summary': 'GXDE launcher',
        'description': 'The GXDE launcher (Qt6/dtk6): application grid, search and\n'
                       'category views.',
        'br': BASE + QT6 + DTK + X11 + [
            'gsettings-qt6-devel kf6-kwindowsystem-devel layer-shell-qt-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-session-ui': {
        'modules': ('gxde-session-ui',),
        'version_from': 'gxde-session-ui',
        'summary': 'GXDE session UI components',
        'description': 'GXDE session UI: lock screen, OSD, shutdown/suspend dialogs,\n'
                       'greeter, welcome, WM chooser and related session shell\n'
                       'components. Qt5 main project with Qt6 targets (dde-osd,\n'
                       'dde-shutdown).',
        'br': BASE + QT5 + QT6 + DTK + X11 + SYS + [
            'lightdm-qt5-devel lightdm-qt6-devel',
            'kf6-kwindowsystem-devel layer-shell-qt-devel',
            'perl-interpreter perl-XML-LibXML perl-Config-Tiny',
        ],
        'devel': False, 'tools': ('desktop',), 'debug_package': True,
        'requires': [], 'provides': [],
        'conflicts': ['deepin-session-ui deepin-session-shell'], 'scriptlets': '',
    },
    'gxde-file-manager': {
        'modules': ('gxde-file-manager', 'gxde-file-manager-integration', 'util-dfm'),
        'version_from': 'gxde-file-manager',
        'summary': 'GXDE file manager',
        'description': 'The GXDE file manager (Qt6), its dock/desktop integrations and\n'
                       'the util-dfm libraries (dfm-io, dfm-mount).',
        'br': BASE + QT6 + DTK + X11 + GLIB + [
            'kf6-kcodecs-devel gsettings-qt6-devel',
            'poppler-cpp-devel polkit-devel ffmpegthumbnailer-devel',
            'taglib-devel libmediainfo-devel libchardet-devel uchardet-devel',
            'cjson-devel libicu-devel qt6-qtmultimedia-devel',
            # Full hard-dep enumeration across the three fm modules' .pro and
            # CMakeLists (optional packagesExist probes like libgxmr/Qt5Xdg/
            # deepin-anything are false on VM too and need no BR); the webview
            # subproject needs QT += webenginewidgets.
            'polkit-qt5-1-devel polkit-qt6-1-devel openssl-devel git',
            'lucene++-devel layer-shell-qt-devel kf5-kcodecs-devel',
            'pkgconfig(udisks2) pkgconfig(mount) qt6-qtwebengine-devel',
            # Bundle-era BRs verified needed by fm subprojects: libav for the
            # video thumbnailer, libisoburn for dfm6-burn (its .pc Requires
            # libisoburn-1), file/utf8proc for mime & chinese2pinyin.
            'pkgconfig(libavformat) pkgconfig(libavcodec) pkgconfig(libavutil)',
            'libisoburn-devel file-devel utf8proc-devel libwebp-devel pkgconfig(zlib)',
            # dfm6-search.pc Requires Boost; dfm6-mount.pc Requires libsecret-1.
            'boost-devel libsecret-devel',
            'gxde-dock-devel gxde-libs-devel gxde-bernese-devel',
            # rofd.h / librofd_ffi for the OFD thumbnail and preview plugins.
            'gxde-compressor-devel',
            'perl-interpreter perl-XML-LibXML perl-Config-Tiny',
        ],
        'devel': True, 'tools': ('desktop',), 'debug_package': True,
        'requires': [], 'provides': ['deepin-util-dfm'],
        'conflicts': ['deepin-file-manager deepin-util-dfm'], 'scriptlets': '',
    },
    'gxde-terminal': {
        'modules': ('gxde-terminal',),
        'version_from': 'gxde-terminal',
        'summary': 'GXDE terminal',
        'description': 'The GXDE terminal emulator (Qt6/dtk6).',
        'br': BASE + QT5 + QT6 + DTK + X11 + [
            'gsettings-qt6-devel libicu-devel libsecret-devel',
            # Full pkg dep set of gxde-terminal/3rdparty/terminalwidget:
            # chardet Utf8Proc atspi-2 ICU libsecret-1 KF6WindowSystem GTest
            # gio/gobject ZLIB x11 xcb-ewmh; detectcode.h also includes
            # <uchardet/uchardet.h> directly.
            'libchardet-devel uchardet-devel utf8proc-devel at-spi2-core-devel',
            'gtest-devel kf6-kwindowsystem-devel glib2-devel pkgconfig(zlib)',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-search': {
        'modules': ('dde-grand-search', 'deepin-pdfium'),
        'version_from': 'dde-grand-search',
        'summary': 'GXDE grand search and pdfium backend',
        'description': 'GXDE global search (dde-grand-search) with the deepin-pdfium\n'
                       'document rendering backend for search previews.',
        'br': BASE + QT6 + DTK + X11 + [
            'lucene++-devel boost-devel lcms2-devel openjpeg2-devel',
            'libjpeg-turbo-devel jbig2dec-devel libchardet-devel pkgconfig(zlib)',
            'pkgconfig(freetype2) pkgconfig(fontconfig)',
            # Full REQUIRED pkg_check_modules enumeration of grand-search:
            # gxde-dock pc, gsettings-qt, icu-i18n, libavformat,
            # libffmpegthumbnailer, taglib (deepin-pdfium is staged in-group).
            'gxde-dock-devel gsettings-qt-devel libicu-devel taglib-devel',
            'ffmpegthumbnailer-devel pkgconfig(libavformat)',
            # deepin-qdbus-service headers (app-management) and the dfm6-search
            # cmake config (util-dfm in the file-manager group).
            'gxde-app-management-devel gxde-file-manager-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': ['deepin-pdfium'],
        'conflicts': ['deepin-grand-search deepin-pdfium'], 'scriptlets': '',
    },
    'gxde-screensaver': {
        'modules': ('deepin-screensaver', 'gxde-time-screensaver'),
        'version_from': 'deepin-screensaver',
        'summary': 'GXDE screensavers',
        'description': 'GXDE screensavers: deepin-screensaver (Qt6) and the time\n'
                       'screensaver (Qt5).',
        'br': BASE + QT5 + QT6 + DTK + X11 + [
            'gsettings-qt-devel gsettings-qt6-devel qt6-qtmultimedia-devel',
        ],
        'devel': False, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': ['deepin-screensaver'],
        'scriptlets': '',
    },
    'gxde-compressor': {
        'modules': ('gxde-compressor', 'gxde-shell-compressor', 'zipu', 'rofd'),
        'version_from': 'gxde-compressor',
        'summary': 'GXDE archive and compressor tools',
        'description': 'GXDE archive tools: rofd (Rust archive backend with a C FFI\n'
                       'library), gxde-compressor, the shell compressor and zipu\n'
                       'assets.',
        'br': BASE + QT6 + DTK + X11 + GLIB + [
            'rust cargo libarchive-devel',
            # System libs for rofd's vendored -sys crates: freetype-sys,
            # cairo-sys-rs, gio-sys, glib-sys, gobject-sys (GLIB set covers
            # glib/gio/gobject/cairo/freetype/fontconfig; cairo-gobject extra),
            # plus jbig2dec probed by the first-party rofd-render build.rs.
            'pkgconfig(freetype2) pkgconfig(fontconfig) pkgconfig(cairo-gobject)',
            'jbig2dec-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-installer': {
        'modules': ('deepin-installer-reborn',),
        'version_from': 'deepin-installer-reborn',
        'summary': 'GXDE installer timezone translations',
        'description': 'Timezone message catalogs from deepin-installer-reborn, shipped\n'
                       'as locale data (mirrors what the Arch gxde-core-git bundle\n'
                       'provides from this module).',
        'br': ['make gettext python3'],
        'devel': False, 'tools': (), 'debug_package': False,
        'requires': [], 'provides': [], 'conflicts': [], 'scriptlets': '',
    },
    'gxde-app-management': {
        'modules': ('gxde-app-installer', 'gxde-app-upgrader', 'gxde-app-uninstaller',
                    'deepin-service-manager', 'gxde-requ'),
        'version_from': 'deepin-service-manager',
        'summary': 'GXDE app store components and service manager',
        'description': 'GXDE app management: app installer/upgrader/uninstaller assets,\n'
                       'gxde-requ and deepin-service-manager (ships libqdbusservice,\n'
                       'consumed by gxde-search).',
        'br': BASE + QT6 + DTK + X11 + [
            'dbus-devel polkit-qt6-1-devel gsettings-qt6-devel',
        ],
        'devel': True, 'tools': (), 'debug_package': True,
        'requires': [], 'provides': ['deepin-service-manager'],
        'conflicts': ['deepin-service-manager'], 'scriptlets': '',
    },
}

META_NAME = 'gxde-core'
META_VERSION_FROM = 'gxde-control-center'

# gxde-shell-tools is intentionally absent: the upstream repo only carries
# Arch packaging metadata (no sources) and the historical bundle never built
# or shipped anything from it.
MODULES = tuple(m for g in GROUPS.values() for m in g['modules'])

TOOL_SOURCES = {
    'policy': ('Source105:      deepin-policy-ts-convert',
               'cp %{SOURCE105} deepin-policy-ts-convert',
               'deepin-policy-ts-convert'),
    'desktop': ('Source106:      deepin-desktop-ts-convert',
                'cp %{SOURCE106} deepin-desktop-ts-convert',
                'deepin-desktop-ts-convert'),
}


def resolve(old, cache):
    components = {}
    for name in MODULES:
        repo = f'https://github.com/GXDE-OS/{name}.git'
        if name in BRANCH:
            branch = BRANCH[name]
            tag, commit = describe_branch_tag(repo, branch)
            print(f'{name}: {tag} ({commit[:12]}) [branch={branch}]', flush=True)
        else:
            refs = subprocess.check_output(['git', 'ls-remote', '--tags', repo], text=True, timeout=120)
            tag, commit = latest_tag(refs)
            print(f'{name}: {tag} ({commit[:12]})', flush=True)
        previous = old.get('components', {}).get(name)
        if previous and name not in BRANCH:
            if tag_key(tag) < tag_key(previous['tag']):
                raise ValueError(f'{name}: upstream tag rollback requires manual review')
            if previous['tag'] == tag and previous['commit'] != commit:
                raise ValueError(f'{name}: released tag moved; refusing automatic update')
        url = f'https://codeload.github.com/GXDE-OS/{name}/tar.gz/{commit}'
        item = {'tag': tag, 'commit': commit, 'url': url}
        if name in BRANCH:
            item['branch'] = BRANCH[name]
        item['sha256'] = sources.download(url, cache / f'{name}-{commit}.tar.gz',
                                          previous['sha256'] if previous and previous['commit'] == commit else None)
        components[name] = item

    old_groups = old.get('groups', {})
    groups = {}
    for name, group in GROUPS.items():
        version = rpm_version(components[group['version_from']]['tag'])
        commits = {m: components[m]['commit'] for m in group['modules']}
        previous = old_groups.get(name)
        if previous is None or previous.get('version') != version:
            release = 1
        elif previous.get('commits') != commits:
            release = previous.get('release', 1) + 1
        else:
            release = previous.get('release', 1)
        groups[name] = {'version': version, 'release': release, 'commits': commits}
        print(f'== {name}: {version}-{release}', flush=True)

    meta_version = rpm_version(components[META_VERSION_FROM]['tag'])
    previous_meta = old_groups.get(META_NAME)
    if previous_meta is None or previous_meta.get('version') != meta_version:
        meta_release = 1
    elif any(groups[g] != old_groups.get(g) for g in GROUPS):
        meta_release = previous_meta.get('release', 1) + 1
    else:
        meta_release = previous_meta.get('release', 1)
    groups[META_NAME] = {'version': meta_version, 'release': meta_release, 'commits': {}}
    print(f'== {META_NAME} (meta): {meta_version}-{meta_release}', flush=True)
    return {'components': components, 'groups': groups}


def _module_sources(group_modules, components, destination):
    """Download/verify module tarballs and return spec fragment lists."""
    import hashlib
    import shutil
    import tarfile

    definitions, sources_list, checks, setup_flags, rename_cmds = [], [], [], [], []
    for index, name in enumerate(group_modules):
        component = components[name]
        commit = component['commit']
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError(f'Invalid commit for {name}')
        filename = f'{name}-{commit}.tar.gz'
        cached = ROOT / 'build/source-cache' / filename
        if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == component['sha256']:
            shutil.copyfile(cached, destination / 'SOURCES' / filename)
        sources.download(component['url'], destination / 'SOURCES' / filename, component['sha256'])
        # codeload names the tarball's top directory after the *current* repo
        # name, which may differ from the module name if upstream renamed the
        # repo (e.g. deepin-installer-reborn -> deepin-installer-reborn-old).
        with tarfile.open(destination / 'SOURCES' / filename, 'r:gz') as tar:
            top = next(iter(tar)).name.split('/')[0]
        definitions.append(f'%global commit{index} {commit}')
        sources_list.append(f'Source{index}: {component["url"]}#/{filename}')
        checks.append(f'{component["sha256"]}  {filename}')
        setup_flags.append(f'-a {index}')
        rename_cmds.append(f'mv {top} {name}')
    return definitions, sources_list, checks, setup_flags, rename_cmds


def _fill(template, replacements):
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def _mk_tree(destination):
    import shutil
    for directory in ('SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'RPMS', 'SRPMS'):
        (destination / directory).mkdir(parents=True, exist_ok=True)
    return shutil


def prepare_group(name, lock, destination):
    group = GROUPS[name]
    glock = lock['groups'][name]
    components = lock['components']
    shutil = _mk_tree(destination)

    definitions, sources_list, checks, setup_flags, rename_cmds = _module_sources(
        group['modules'], components, destination)

    tool_sources, tool_prep, tool_files = [], [], []
    for tool in group['tools']:
        src_line, prep_line, filename = TOOL_SOURCES[tool]
        tool_sources.append(src_line)
        tool_prep.append(prep_line)
        tool_files.append(filename)

    devel_package, devel_files = '', ''
    if group['devel']:
        # %{version}-%{release} macros (not the raw lock values) so the
        # dependency carries %{?dist} and matches the main package exactly.
        devel_package = (
            '\n%package devel\n'
            f'Summary:        Development files for {name}\n'
            f'Requires:       {name}%{{?_isa}} = %{{version}}-%{{release}}\n'
            '\n%description devel\n'
            f'Headers, pkg-config and CMake files for {name}.\n')
        devel_files = '\n%files devel -f devel.files'

    def _lines(prefix, items):
        return '\n'.join(f'{prefix}{item}' for item in items)

    template = (PACKAGE / 'group.spec.in').read_text()
    spec_text = _fill(template, {
        '@GROUP@': name,
        '@DEBUG_PACKAGE@': '' if group['debug_package'] else '%global debug_package %{nil}',
        '@COMMITS@': '\n'.join(definitions),
        '@NAME@': name,
        '@VERSION@': glock['version'],
        '@RELEASE@': str(glock['release']),
        '@SUMMARY@': group['summary'],
        '@SOURCES@': '\n'.join(sources_list),
        '@TOOL_SOURCES@': '\n'.join(tool_sources),
        '@BUILDREQS@': _lines('BuildRequires:  ', group['br']),
        '@REQUIRES@': _lines('Requires:       ', group['requires']),
        '@PROVIDES@': _lines('Provides:       ', group['provides']),
        '@CONFLICTS@': _lines('Conflicts:      ', group['conflicts']),
        '@DESCRIPTION@': group['description'],
        '@DEVEL_PACKAGE@': devel_package,
        '@SETUP@': ' '.join(setup_flags),
        '@RENAME@': '\n'.join(rename_cmds),
        '@LICENSES@': '\n'.join(
            f'cp {m}/LICENSE licenses/{m}.LICENSE 2>/dev/null || :' for m in group['modules']),
        '@TOOL_PREP@': '\n'.join(tool_prep),
        '@SCRIPTLETS@': group['scriptlets'],
        '@DEVEL_FILES@': devel_files,
    })
    (destination / f'SPECS/{name}.spec').write_text(spec_text)
    (destination / 'SOURCES/sources.sha256').write_text('\n'.join(checks) + '\n')
    shutil.copyfile(PACKAGE / 'groups' / f'{name}.sh', destination / 'SOURCES/build.sh')
    for shared in ('common.sh', 'split-files.py', 'upstream-lock.json'):
        shutil.copyfile(PACKAGE / shared, destination / 'SOURCES' / shared)
    for filename in tool_files:
        shutil.copyfile(PACKAGE / filename, destination / 'SOURCES' / filename)


def prepare_meta(lock, destination):
    shutil = _mk_tree(destination)
    glock = lock['groups'][META_NAME]
    template = (PACKAGE / f'{META_NAME}.spec.in').read_text()
    spec_text = _fill(template, {
        '@VERSION@': glock['version'],
        '@RELEASE@': str(glock['release']),
    })
    (destination / f'SPECS/{META_NAME}.spec').write_text(spec_text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('update', 'prepare'))
    parser.add_argument('--group', default='all',
                        help='group name or "all" (prepare only; always includes the metapackage)')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'build')
    args = parser.parse_args()

    path = PACKAGE / 'upstream-lock.json'
    lock = json.loads(path.read_text()) if path.exists() else {}
    if args.command == 'update':
        cache = ROOT / 'build/source-cache'
        cache.mkdir(parents=True, exist_ok=True)
        updated = resolve(lock, cache)
        path.write_text(json.dumps(updated, indent=2) + '\n')
        return

    if not lock.get('groups'):
        raise SystemExit('lock has no group metadata; run "update" first')
    names = list(GROUPS) if args.group == 'all' else [args.group]
    if args.group != 'all' and args.group not in GROUPS and args.group != META_NAME:
        raise SystemExit(f'unknown group: {args.group}')
    if args.group == META_NAME:
        names = []
    for name in names:
        destination = args.output_root.resolve() / f'{name}-rpmbuild'
        prepare_group(name, lock, destination)
        print(f'prepared {name} -> {destination}', flush=True)
    if args.group in ('all', META_NAME):
        destination = args.output_root.resolve() / f'{META_NAME}-rpmbuild'
        prepare_meta(lock, destination)
        print(f'prepared {META_NAME} (meta) -> {destination}', flush=True)


if __name__ == '__main__':
    main()
