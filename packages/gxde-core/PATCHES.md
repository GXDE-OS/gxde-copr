# GXDE core 源码补丁登记

当前新增源码补丁：**0 项**。

## 拆分结构（2026-10-20 起）

历史单包 bundle 已按用途拆分为 **17 个功能包 + 1 个元包**，
全部在 COPR 单项目 `charofstring/gxde-core` 下以多 package 形式构建（用户只需 enable 一个 repo）。

- 生成器：`scripts/gxde-core-sources.py` 内的 `GROUPS` 清单驱动；`update` 解析全部模块写入共享
  `packages/gxde-core/upstream-lock.json`（v2：`components` + 每组 `version`/`release`/`commits`），
  `prepare --group <name>|all` 生成 `build/<group>-rpmbuild/` 树。
- 每组版本来自其主模块 tag（`version_from`），release 在该组模块 commit 集变化时自动 +1；
  元包 gxde-core 版本跟随 control-center，任一组成员变化即 bump。
- 模板：`packages/gxde-core/group.spec.in`（全部组共用，占位符由生成器填充）；
  `gxde-core.spec.in` 为元包（noarch，仅 Requires/Recommends）。
- 共享构建前置：`packages/gxde-core/common.sh`（stage/导出/toolbin shim/sed 清扫/`_cmake`/`_qmake`/
  `normalize_stage`），各组脚本在 `packages/gxde-core/groups/<group>.sh`，经 `%build` 第三参数 source。
- `split-files.py`：devel 清单为空时不再报错（无 devel 面的组不声明 devel 子包）；
  有 devel 面的组：libs、dock、top-panel、launcher、polkit-agent、file-manager、search、
  compressor（rofd.h/FFI）、app-management（deepin-qdbus-service，被 search 消费）、
  wallpaper-chooser（libgxde-wallpicker 静态库与头文件）。
- 包间构建依赖（波次）：W1 artwork/libs/daemon/polkit-agent/installer/screensaver/terminal/
  compressor/launcher/session-ui/app-management → W2 dock/control-center →
  W3 top-panel/file-manager → W4 search/wallpaper-chooser → W5 元包。
  search 在 W4：grand-search 除 `deepin-qdbus-service`（app-management devel）外还
  `find_package(dfm6-search)`，该 cmake 配置由 util-dfm 安装（file-manager 组 devel）。
  file-manager（W3）除 dock-devel/libs-devel/Bernese-devel 外还需 `gxde-compressor-devel`
  （rofd.h/librofd_ffi，OFD 缩略图与预览插件用）——compressor 在 W1，波次序不变。
- `gxde-shell-tools` 已从模块清单剔除：上游仓库只含 Arch 打包元数据（无源码），bundle 也从未构建它。

## 构建适配（非源码补丁）

以下调整均通过构建参数或环境变量实现，不修改上游源码：

- **rofd (Rust)**：`qttypes` proc-macro 的 cpp crate 在 LTO-thin 对象中读不到结构体元数据，`--remap-path-prefix` 会破坏其基于路径的宏匹配。构建时从 `RUSTFLAGS` 去除 `--remap-path-prefix`，从 `CFLAGS`/`CXXFLAGS` 去除 `-flto` 和 `-ffat-lto-objects`，与 AUR 一致。
- **rofd**：使用 `cargo build --offline --locked`，要求 SRPM 中包含完整的 vendor 依赖。Fedora COPR 构建环境无网络。
- **gxde-top-panel**：上游 CMakeLists 用 `apt --version` 判断是否走 `deb.cmake` 安装规则；另一分支仍用旧文件名 `dde-top-panel`。构建时提供一个 `apt` 桩（输出 `apt 0 (build stub)`）让它走 `deb.cmake`，与 AUR 一致。
- **gxde-top-panel lrelease**：上游 `find_program(QT_LRELEASE_EXECUTABLE /usr/lib/qt6/bin/lrelease)` 把 Debian 路径当程序名找，Fedora 上 NOTFOUND，ninja 执行 `QT_LRELEASE_EXECUTABLE-NOTFOUND` 直接 127。构建时传 `-DQT_LRELEASE_EXECUTABLE=$toolbin/lrelease` 预置缓存变量绕过搜索。file-manager 的 `GXDECommon.cmake` 用 `NAMES lrelease-qt6 lrelease6 lrelease` 按名搜索，PATH shim 可命中，无需处理。
- **translation-generate.cmake 的 /lib/qtN/bin 回退**：deepin 系模块（deepin-screensaver、gxde-file-manager、gxde-top-panel）共用的 cmake 翻译模块在 `Qt${QT_VERSION_MAJOR}_LRELEASE_EXECUTABLE` 未定义时回退到硬编码 `/lib/qt${QT_VERSION_MAJOR}/bin/lrelease`（ninja 运行期 127）。`common.sh` 的 `_cmake` 统一预置 `-DQt5_LRELEASE_EXECUTABLE=/usr/bin/lrelease-qt5 -DQt6_LRELEASE_EXECUTABLE=$toolbin/lrelease`，回退分支永不触发。
- **qdbusxml2cpp 后缀**：Fedora 只有 `qdbusxml2cpp-qt5`/`qdbusxml2cpp-qt6`，session-ui 的 `find_program(QDBUSXML2CPP qdbusxml2cpp)` 按名搜索 NOTFOUND（ninja 执行 `QDBUSXML2CPP-NOTFOUND` → 127）。`common.sh` 在 toolbin 建 `qdbusxml2cpp` 软链（默认 qt6），session-ui（Qt5 主工程）在自己的组脚本里翻转到 qt5 版。
- **man 页与 brp-compress 竞态**：`split-files.py` 的清单在 `%install` 期生成，而 `brp-compress` 其后把 man 页改名 `.gz`，会导致 `%files` 清单失配；模板统一 `%global __brp_compress %{nil}`，让清单与 buildroot 保持一致。
- **deepin-daemon 图标**：`install-icons` 目标用 Python 调 `rsvg-convert`，Fedora 由 `librsvg2-tools` 提供（不是 `librsvg-tools`），已加入 daemon 组 BuildRequires。
- **gxde-terminal devel 面**：terminal 安装 `gxde-terminalwidget6` 的头文件、cmake 配置、pc 与 `.so` 开发符号链接，组清单须开 `devel=True`，否则 unpackaged files 报错。
- **gxde-wallpapers image-blur**：blur 目标硬编码调用 `/usr/lib/deepin-api/image-blur`（deepin-api，Fedora 未打包；VM 曾装有该工具所以本地验证通过、干净 chroot Error 127）。artwork 组脚本在 `toolbin/` 放一个 ImageMagick stub（`magick IN -blur 0xSIGMA OUT`，参数签名与 deepin-api 一致）并 sed 改写 Makefile 硬编码路径走 PATH。BuildRequires 增加 `ImageMagick`。
- **干净 chroot 的 BR 全量审计**（COPR 第二至五轮失败后）：VM 环境累积了 bundle 时代全部 builddep + 桌面工具，会掩盖组 BR 缺失；COPR 干净 chroot 逐层暴露。逐组把依赖面一次挖全：daemon ← gocode-gxde 全部 cgo pc（补 `gdk-pixbuf2-xlib-devel`、`pkgconfig(libcanberra)`）+ sni-server/garma 的 `pkg_check_modules(libcjson)`（补 `cjson-devel`）+ deepin-menu include `<LayerShellQt/Shell>`（补 `layer-shell-qt-devel`）+ globalmenu-service 的 `find_package(KF5Config/KF5CoreAddons/KF5WindowSystem)`（补三个 kf5 devel）+ sni-server 的 `find_package(KF6 COMPONENTS CoreAddons Crash DBusAddons StatusNotifierItem)`（补四个 kf6 devel）+ globalmenu-service include `<xcb/xcb_atom.h>`（X11 公共集补 `xcb-util-devel`——xcb-util-wm/image/ewmh 都不带这个头）；terminal ← terminalwidget 全部 pkg_check_modules（补 chardet/utf8proc/atspi-2/kf6-kwindowsystem/glib2/zlib/gtest + QT5 保险）+ `detectcode.h` 直接 include `<uchardet/uchardet.h>`（补 `uchardet-devel`）；compressor ← rofd vendored `-sys` crate 全集（补 GLIB 集 + `pkgconfig(cairo-gobject)`）+ 第一方 `rofd-render` build.rs 探测的 `jbig2dec`（补 `jbig2dec-devel`；image/png/tiff/zlib 均走 vendored 纯 Rust crate，无需系统库）；file-manager ← 三模块全部 .pro/CMake 硬依赖枚举（补 `polkit-qt5-1-devel polkit-qt6-1-devel openssl-devel git lucene++-devel layer-shell-qt-devel kf5-kcodecs-devel pkgconfig(udisks2) pkgconfig(mount) qt6-qtwebengine-devel`（webview 子项目 `QT += webenginewidgets`）+ 此前的 `boost-devel libsecret-devel`；`libgxmr`/`deepin-anything`/`Qt5Xdg`/`udisks2-qt5` 等为 packagesExist 可选探测或 Qt5 分支，VM 构建同为 false，无需 BR）；search ← grand-search 全部 REQUIRED pkg_check_modules 枚举（补 `gxde-dock-devel gsettings-qt-devel libicu-devel taglib-devel ffmpegthumbnailer-devel pkgconfig(libavformat)`——含此前遗漏的 search→dock pc 依赖边；`deepin-pdfium` 为组内 staged）。
- **util-dfm 的 .pc 泄漏 CMake target 名**：`dfm6-search.pc` 的 `Requires:` 混入 `Boostsystem`、`Threads`（CMake target 名，非 pkg-config 模块），rpm 的 pkgconfig 依赖生成器将其转成 devel 包上无法满足的 `pkgconfig(…)` 自动依赖（dnf 报 nothing provides），且这类 .pc 也会让 `pkg-config --exists dfm6-search` 失败。**rpm 6.0.2 无视 `%global __requires_exclude`**（spec 过滤路线实测无效），故 file-manager 组脚本在 `_cmake util-dfm` 后直接 sed 剥离 staged `.pc` 中这两个 token（顺带规整空白/重复逗号），根因数据修好，rpm 依赖与 pkg-config 消费者同时恢复正常。
- **rpm6 构建成功后自动清理 BUILD 树**：rpm 6.0 在 `rpmbuild -ba` 成功后删除 BUILD 下的构建树（失败时保留）。调试成功构建的中间产物（stage、.pc、flags.make 等）须在构建期内抓取，或从产物 RPM 反查（`rpm2cpio | cpio -idm`）。
- **F45 OpenSSL 无 EVP_sm3（跨版本）**：file-manager 在 F44 双架构通过、F45 双架构失败——`util-dfm/src/dfm-burn/.../dsm3hash.cpp` 无条件调用 `EVP_sm3()`（SM3 国密哈希），F45 的 OpenSSL 头不再声明它。上游无开关宏，且代码本身对 `md == nullptr` 优雅降级（返回空串）。修法：fm 组脚本在 `_cmake util-dfm` 前用 gcc 编译探测 `EVP_sm3` 可用性，仅在不可编译时向该文件 evp.h include 后注入 `static const EVP_MD *EVP_sm3() { return nullptr; }` 回退——F44/VM 零改动，F45 上 SM3 功能优雅缺失（可选特性）。构建期探测而非 `%if fedora` 版本号硬编码，未来 OpenSSL 行为变化自适应。
- **跨包文件冲突（拆分后显形的 bundle 隐性 bug，共 3 处）**：
  - `/var/lib/polkit-1{,/localauthority,/localauthority/10-vendor.d}` 目录归 `polkit-pkla-compat`（daemon 组已 Requires）；split-files.py 的 common 目录集合收录这三层，daemon 只打包目录内的 `.pkla` 文件。
  - `com.deepin.dde.Dock.service`：top-panel 装的版本 `Exec=/usr/bin/dde-dock`——该二进制任何包都不提供（上游改名前 deb 布局的残留），bundle 时代按安装顺序 last-writer-wins 一直在发行这个坏文件。拆分后保留 dock 包的可用版本（`Exec=/usr/bin/gxde-dock`），top-panel 组脚本删除自己的副本。
  - `/usr/share/applications/mimeapps.list`：Fedora 归 `shared-mime-info` 所有（发行版管理的默认关联），artwork 组脚本按配置筛选先例从 stage 删除己方副本。
- **_qmake 多词命令**：`_qmake "qmake6 -r" …`（file-manager 需要 `-r` 递归传参）曾因 `"$qm"` 加引号整串当命令名执行而报 `qmake6 -r: command not found`——bundle 时代从未构建到 file-manager 所以未暴露。common.sh 改为 `read -r -a qmcmd <<< "$qm"` 数组执行。
- **split-files.py 插件 .so 误分类**：`category()` 曾把 libdir 下**任意深度**的 `.so` 判为 devel，导致 `/usr/lib64/gtk-3.0/modules/libappmenu-gtk-module-wayland.so`（daemon 组，运行期 GTK 模块）落入 devel.files——daemon 无 devel 子包 → unpackaged 报错；bundle 时代则把 Qt/dock 插件 `.so` 错装进 devel 包（运行包缺插件的隐性 bug）。修复：仅 libdir **根目录**的 `.so` 符号链接算 devel，子目录插件归 runtime（新增单测覆盖）。修复后全部组需重打 SRPM 重验（split-files.py 是每组的 Source102）。
- **gxde-session-ui**：主工程为 Qt5，但 dde-osd / dde-shutdown 为 Qt6 目标。早前的全局 `-DCMAKE_CXX_FLAGS=… -I/usr/include/qt5`（为 `<QGSettings/QGSettings>` include 形式服务）会把 Qt5 的 QtCore 等头文件暴露给 Qt6 目标——dde-osd 被 Qt 6.11 moc 生成的 `qt_staticMetaObjectStaticContent` 等新宏在 Qt5 头下不存在，编译失败；dde-shutdown（Qt6）也会错拿 Qt5 版 QGSettings 头。修法：构建前把 `<QGSettings/QGSettings>` 重写为 `<QGSettings>`（2 处），各子工程经 `gsettings-qt`/`gsettings-qt6` 的 pc 拿到版本正确的 `-I/usr/include/qt{5,6}/QGSettings`，随后移除全局 include。同为构建树就地修改。
- **gxde-file-manager**：KF6 头文件（KCodecs）要求 C++20；`qmake6 -r` 让参数传到子项目，`CONFIG+=c++20`。
- **deepin-daemon**：Go GOPATH 模式，依赖 `gxde-infra` 提供的 `/usr/share/gocode-gxde`。`GO111MODULE=off`，`CGO_CFLAGS` 加 `-std=gnu17`。
- **deepin-policy-ts-convert**：deepin-daemon 的 Makefile `ts_to_policy` 目标调用该工具生成翻译后的 polkit policy。Fedora 未打包 `deepin-gettext-tools`，故将其 `src/policy_ts_convert.py`（tag 1.0.11，GPL-2.0-or-later，sha256 `bfbd90b8…68515d`）作为 Source105 随 gxde-daemon 组 SRPM 携带，`%prep` 复制到构建树，`common.sh` 装入 `toolbin/` 加入 PATH。仅构建期使用，不随二进制包分发。
- **deepin-desktop-ts-convert**：同源工具（`src/desktop_ts_convert.pl`，Perl，tag 1.0.11，sha256 `3a57994c…77fce`），session-ui 的 `translate_desktop.sh` 和 file-manager 多个 `translate_ts2desktop.sh`/`translate_desktop2ts.sh` 以绝对路径 `/usr/bin/deepin-desktop-ts-convert` 调用（部分带 `[ -x … ]` 守卫）。作为 Source106 随 session-ui/file-manager 两组 SRPM 携带，`common.sh` 装入 `toolbin/` 并把构建树内所有 `.sh` 的该绝对路径 sed 到 `$toolbin/…`（保留守卫语义）。Perl 依赖 `XML::LibXML`/`Config::Tiny` 以 `perl-interpreter perl-XML-LibXML perl-Config-Tiny` 加入两组 BuildRequires。
- **Qt linguist 工具后缀**：上游 `translate_generation.sh` 调用不带后缀的 `lrelease`，Fedora 只有 `lrelease-qt5`/`lrelease-qt6`。`build.sh` 建 `toolbin/` shim 并随模块 Qt 版本切换软链目标。
- **硬编码 Qt 工具路径**：多个模块的翻译脚本硬编码 Debian/Arch 路径（`/usr/lib/qt6/bin/lrelease`、`/usr/lib/x86_64-linux-gnu/qt6/bin/…` 等），Fedora 上不存在。`build.sh` 在构建前将所有 `.sh` 中的这些绝对路径统一 sed 到 `toolbin/` shim——脚本内 `[ -f … ]` 探测依然成立，且跟随模块 Qt 版本切换。这是对构建树内源码的就地修改（无独立补丁文件）。
- **CMAKE_CXX_FLAGS 无条件覆盖**：gxde-dock、gxde-top-panel(-plugins)、gxde-launcher、gxde-control-center（dialogs/frame）在 CMakeLists 顶部 `set(CMAKE_CXX_FLAGS "-g -Wall")`，把 `%set_build_flags` 注入的 Fedora 硬化 flags（redhat-hardened-cc1 的 PIE、FORTIFY、annobin）全部清掉，导致对象文件非 PIC，PIE 链接报 `R_X86_64_32 ... recompile with -fPIE`（dock 的 mocs_compilation 首当其冲）。`build.sh` 构建前将此类无条件 `set` 统一 sed 为追加式 `set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} …")`；已是追加式的行（含 `$`）与注释行不受影响。同为构建树就地修改。
- **gxde-network-utils-qt6（第 44 模块）**：gxde-dock / gxde-control-center / gxde-top-panel-plugins 通过 `pkg_check_modules(… REQUIRED gxde-network-utils-qt6)` 依赖该库；Arch 上是独立包（gxde/gxde-network-utils-qt6-git），Fedora 侧并入 bundle。上游 `.pro` 硬编码 `target.path = $$PREFIX/lib` 且 pc 的 libdir 在解析期展开，构建时传 `-after target.path=$libdir QMAKE_PKGCONFIG_LIBDIR=$libdir` 双双覆盖到 `/usr/lib64`。`libdframeworkdbus-qt6` 依赖由 `gxde-infra-devel` 提供（头文件路径 `/usr/include/libdframeworkdbus-qt6-6.0` 与 `.pro` 默认值一致）。
- **gxde-bernese 迁出 Core（2026-11-07）**：Bernese 与 GXTK7 现在由独立的
  `charofstring/gxde-gxtk7` 项目提供；Core 不再捆绑其源码。top-panel、control-center、
  file-manager 显式 BuildRequires `gxde-bernese-devel`，Core COPR 将新项目作为外部仓库。
- **gxde-wallpaper-chooser（2026-11-07）**：以独立 `gxde-wallpaper-chooser` 功能包加入
  Core，运行包依赖 file-manager/control-center，静态 `libgxde-wallpicker.a` 与头文件进入
  `-devel` 子包。上游把该静态库安装到写死的 `/usr/lib`，组脚本在 x86_64/aarch64
  将它移到 `%{_libdir}`；仅做安装树布局适配，没有源码补丁。
- **file-manager Qt6 分支依赖**：`gxde-file-manager-lib` 的 `.pro` 在 Qt6 下用 `gsettings-qt6 / udisks2-qt6 / disomaster-qt6`（前两者及 disomaster-qt6 由 `gxde-infra-devel` 和 gsettings-qt6 COPR 包提供），Qt5-only 的 `Qt5Xdg / udisks2-qt5 / disomaster` 分支不会走到，无需打包 libqtxdg。`poppler-cpp`（pdf 预览插件）与 `polkit-agent-1`（file-manager-daemon）在 Fedora 由 `poppler-cpp-devel`、`polkit-devel` 提供，已用 `pkgconfig(…)` 形式加入 BuildRequires。
- **CGo alsa 头**：vendored Go 绑定以 `<asoundlib.h>` 裸名引用，Fedora 头文件在 `/usr/include/alsa/` 下，`CGO_CPPFLAGS` 加 `-I/usr/include/alsa`（与 gxde-infra 修法一致）。
- **zlib**：F44 运行时可能是 `zlib-ng-compat`，此时 `zlib-devel` 的 `libz.so` 软链悬空导致 `-lz` 链接失败；BuildRequires 改用 `pkgconfig(zlib)` 让 dnf 选择与运行时匹配的 devel 包。
- **Debian→Fedora 布局**：`/lib` 合并到 `/usr/lib`，`/usr/sbin` 合并到 `/usr/bin`，`usr/lib/*-linux-gnu` 展平到 `usr/lib`。与 AUR 的 Debian→Arch 布局转换对应。
- **配置筛选**：删除会改变系统行为的 `/etc` 配置（`sudoers.d`、`modprobe.d`、`systemd`、`udisks2`、`acpi`、`grub.d`、`gimp`、`X11/xinit/xinitrc.d/50-systemd-user.sh` 等），这些由对应 Fedora 包拥有。
- **权限修复**：部分模块用 `install(FILES)` 安装可执行文件但未给执行权限；Debian 靠 `dh_fixperms` 补。RPM 构建中对 `usr/bin` 下文件统一 `chmod 755`，对 `usr/libexec` 下带 shebang 的文件补执行权限。
- **qmake nostrip**：`CONFIG+=nostrip` 防止 qmake 提前 strip 导致 RPM debugsource 为空（与 gxde-dtk2 的处理一致）。
- **libtool 归档**：安装阶段删除 `*.la` 文件，避免 Fedora `brp-ldconfig` 问题，并在生成文件清单前匹配最终 buildroot。
- **Search 构建依赖**：`deepin-pdfium` 的 CMake 必需 `pkgconfig(chardet)`；Fedora 由 `libchardet-devel` 提供。仅补 `gxde-search` 的 BuildRequires，无需修改上游源码（COPR 11177321 暴露）。
- **gxde-wayland-gtk-menu**：通过 RPM `%post`/`%preun` 脚本在 `/etc/gtk-3.0/settings.ini` 的 `gtk-modules` 中添加/移除 `appmenu-gtk-module-wayland`，对应 AUR 的 `.install` 钩子。

若未来必须回补源码修复，先列出组件/tag、补丁内容、原因和移除条件，并向用户报告。
