# gxde-extra 源码修改登记

不使用 tag 之后的 Git 提交。当前有一个针对正式 tag 缺失文件的独立补丁：

- `gxde-music` 4.0.2：`gxde-music-4.0.2-add-missing-ui-theme-token.patch`
  补入上游提交 `e88aaac3` 引用、但没有加入仓库的
  `src/music-player/view/uithemetoken.h`。该标签内十个源文件使用
  `UiToken::*`，导致 COPR 11270762 在首个包含点直接编译失败。补丁只定义
  已被调用的尺寸常量和基于当前 Qt palette 的前景、背景、强调色函数，
  不引入 tag 之后的代码。上游正式标签包含等价头文件或移除这些引用后，
  应删除此补丁。

## 构建树内修改

`build.sh` 在 RPM `%build` 中仅修改解包后的构建树，不回写上游仓库：

- 对 `upstream/**/*.sh` 与 `upstream/**/*.py` 内硬编码的 `/usr/lib/qt6/bin/`、
  `/usr/lib/qt5/bin/`、`/usr/lib/x86_64-linux-gnu/qt6/bin/`、
  `/usr/lib/x86_64-linux-gnu/qt5/bin/` 和 `/usr/bin/deepin-desktop-ts-convert`
  路径进行字符串替换，改为当前构建目录的 `toolbin/`。Fedora 的 Qt6 工具以
  `lrelease-qt6`（Qt5 为 `lrelease-qt5`）等名称安装，不提供这些 Arch/Debian
  路径。Boot Maker 的 `src/tools/translate_generation.py` 是必须覆盖的 Python
  脚本（COPR 11177680 暴露）；
  `deepin-desktop-ts-convert` 则从 `gxde-infra` 锁定的
  `deepin-gettext-tools` 正式 tag 中提取，作为 SRPM Source105 携带。
  同源的 `deepin-policy-ts-convert` 作为 Source104 携带。
  当上游改用可配置的工具路径或 Fedora 提供相同路径时，可移除此替换。

其余 Fedora 路径、依赖和构建选项适配在 spec 与 `build.sh` 中实现；
Picker 首轮 COPR 构建 11177678 缺少 `Qt6GuiPrivateConfig.cmake`，Release 2
仅补 `qt6-qtbase-private-devel` 构建依赖，没有修改上游源码。
Clipboard 首轮 11177679 同样缺 Qt6GuiPrivate，Release 2 加相同依赖。
Clone 首轮 11177684 缺 Qt5 私有头 `private/qiodevice_p.h`，且翻译阶段缺
`lrelease` 和 Perl XML 模块；Release 2 增加 `qt5-qtbase-private-devel`、
`perl-XML-LibXML`、`perl-Config-Tiny`，Qt5 构建时将 toolbin 指向
`lrelease-qt5`。这些均不修改上游 C++ 源码。
如后续必须增添其他源码修改，需在这里记下涉及的包、tag、修改原因与移除条件，
并向用户报告。

- `gxde-calendar` 6.0.3：在构建树的根 `CMakeLists.txt`，将
  `set(CMAKE_CXX_FLAGS "-g -Wall")` 改为追加 `-g -Wall`。原写法丢弃 Fedora
  `%set_build_flags` 中的 PIC/PIE 参数，COPR 11177681 的 aarch64 链接失败。
  上游保留调用者 CMake flags 后可移除。
- `gxde-ocr` 2.0.1：在构建树的 `src/CMakeLists.txt`，将捆绑 OpenCV 和
  ncnn 静态库路径中的 `build/install/lib/` 改为 `build/install/lib64/`。
  Fedora 45 的 `GNUInstallDirs` 将它们安装到 `lib64`，COPR 11177694
  因此找不到 `libopencv_world.a`。上游使用 `CMAKE_INSTALL_LIBDIR` 而非
  写死 `lib` 后可移除。
- `dde-clipboard` 6.6.2：在构建树的根 `CMakeLists.txt` 将
  `/usr/lib/qt6/bin/qdbusxml2cpp` 改为 `/usr/bin/qdbusxml2cpp-qt6`。
  Fedora 45 的 `qt6-qtbase-devel` 提供后者；COPR 11177954 因前者
  不存在，未生成 `clipboard_adaptor.h`。上游使用 Qt CMake 工具变量后可移除。
- `gxde-log-viewer` 6.5.42：在构建树的
  `3rdparty/DocxFactory/include/DocxFactory/zip/FileInfo.h`、
  `3rdparty/DocxFactory/src/opc/OpcImageFile.cpp`、
  `3rdparty/DocxFactory/src/zip/UnzipFile.cpp`、
  `3rdparty/libxlsxwriter/include/xlsxwriter/packager.h` 中，
  将 `minizip/zip.h`、`minizip/unzip.h` 引用改为项目自带头文件。
  COPR 11177972 混用系统与捆绑 minizip 头文件导致类型重定义。
  上游统一一套 minizip 或移除捆绑副本后可移除。

`gxde-reader` 6.6.2 的捆绑 PDFium 有多个头文件缺少 `<cstdint>`；
最初只修改 `annotation_flags.h`，COPR 11177947 暴露其他同类位置后已
撤回该构建树修改，改用 CMake 编译参数 `-include cstdint`，不再修改源码。

其他本轮调整只涉及 RPM 构建依赖和 qmake 参数：加入 `gio-qt6` 0.0.16
作为 Clipboard、Log Viewer 的依赖；修正 ICU、KF6 Syntax Highlighting、
Qt6 Multimedia/StateMachine、CUPS、libva、PyQt6、Wayland 私有头等 Fedora
开发包名称；Screen Recorder 通过 qmake 传入 Fedora FFmpeg 头文件目录。
这些没有修改上游源码。

`libimagevisualresult6` 也来自 `linuxdeepin/image-editor` 6.5.2 正式 tag；
以 RPM 生成的外层 CMake 包装工程构建 `libimagevisualresult` 子目录，
RPM 只保留 Qt6 库、头文件和数据。该子目录本身没有独立的
`cmake_minimum_required`，COPR 11178013 因此不能直接作为顶层工程配置。
其 CMake 规则覆盖 Fedora 的调试编译参数，COPR 11178040 生成空的
`debugsourcefiles.list`；RPM 对该辅助库关闭空调试包生成。
Fedora 45 当前没有提供该开发包（COPR 11177978），供 Camera 构建使用。
这不修改其上游源码。
