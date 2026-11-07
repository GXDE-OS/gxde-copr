# GXDE infra 源码补丁登记

当前新增源码补丁：**1 项**。

## Deepin Qt 平台主题限定到 GXDE 会话（Release 3）

- 上游 `/etc/profile.d/gxde.sh` 无条件导出 `QT_QPA_PLATFORMTHEME=deepin`，导致只要
  安装了 `gxde-infra`，Plasma/KDE 会话中的所有 Qt 程序也会加载 Deepin 平台主题，
  覆盖 Plasma 自己的配色、控件和图标设置。
- RPM 安装阶段将该导出改为按会话判断：仅 `XDG_CURRENT_DESKTOP`、
  `XDG_SESSION_DESKTOP` 或 `DESKTOP_SESSION` 表明 GXDE/Deepin 时启用。GXDM 会在
  打开 PAM 会话前设置这些变量，因此 GXDE 与 FlakeWM 仍使用 Deepin 主题，KDE
  和其他桌面不会被影响。
- 这是安装配置适配，**没有新增上游源码 patch**。

## Fedora 全局 Qt 平台变量修正（Release 2）

- `gxde-desktop-base 2026.11.03` 安装的 `/etc/profile.d/gxde.sh` 全局设置
  `QT_QPA_PLATFORM=dxcb;xcb;dwayland;wayland`。Display Manager 的 Wayland greeter
  同样会读取该文件，Qt 因而在 `WAYLAND_DISPLAY` 已有、`DISPLAY` 尚未设置时优先加载
  XCB；Plasma Login Manager 的 greeter/wallpaper 随即在 `libQt6XcbQpa` 中段错误，
  GXDM 也无法稳定显示 greeter。
- RPM 在 `%install` 的 buildroot 中删除这一项，让 Qt 根据会话自动选择平台；
  `DTK2_XWAYLAND` 等其他 GXDE 设置不变。`QT_QPA_PLATFORMTHEME` 后续在 Release 3
  改为仅 GXDE 会话启用。
- 这是安装配置适配，**没有新增上游源码 patch**。已在 Fedora 45 测试机分别验证
  Plasma Login Manager 和 `GXDM + FlakeWM + gxdm-greeter-neo` 正常运行。

## xdg-desktop-portal-gxde 1.2.5 手动更新

- 从正式标签 `1.2.4` 更新到 `1.2.5`（提交 `c16a49325a5a`）；录屏 PipeWire 缓冲区标志修复已由上游提交 `58d31d2` 提供。
- 此次 **没有新增 RPM 源码补丁**；原有的 `0001-network-utils-lrelease-path.patch` 继续用于另一个组件。上游自带的 `patch_dmabuf_header.py` 在新标签中仍存在，不属于 RPM 补丁。

## 0001-network-utils-lrelease-path.patch

- 组件/tag：`gxde-network-utils-qt6 6.0.1-arch1`，提交 `2d3ecd17b03e`。
- 原因：上游 `translate_generation.sh` 将 Qt6 `lrelease` 固定为 `/usr/lib/qt6/bin/lrelease`；Fedora 45 的 `qt6-linguist` 提供 `/usr/bin/lrelease-qt6`，导致 COPR 11170578 的翻译生成失败。
- 修改：优先通过 `PATH` 查找 `lrelease-qt6`，其次查找 `lrelease`，缺失时明确报错。保留翻译生成，不触及 C++ 源码。
- 移除条件：GXDE 正式标签的脚本不再使用固定路径，且在 Fedora 45 完成构建验证。

已在此轮对用户报告。

- `xdg-desktop-portal-gxde` 的 `patch_dmabuf_header.py` 是上游 tag 自带的生成代码修正，未由 RPM 添加或修改。
- 上游仓库内已有的 `.pc`/`arch` 补丁或构建规则均保留在对应的锁定 commit 中，RPM 不额外应用。
- Fedora 缺少 `deepin-policy-ts-convert`；构建时直接调用 `deepin-gettext-tools` 正式标签所带脚本，保留 policy 翻译，无需修改 `gxde-api` 源码。
- Fedora 的 ALSA 头文件位于 `/usr/include/alsa/asoundlib.h`，而 GXDE Go 绑定使用 `<asoundlib.h>`；仅给 CGo 传入 `-I/usr/include/alsa`，不修改头文件或绑定源码。
- Qt6 网络库的 qmake 项目默认把库装在 `/usr/lib`，RPM 构建参数将其目标目录设为 Fedora 的 `%{_libdir}`，并让链接器搜索暂存的该目录；不修改项目文件。
- `gxde-movie-reborn` 自带测试可执行文件在 Fedora 默认 PIE 链接下需要位置无关对象；通过 CMake 的 `CMAKE_POSITION_INDEPENDENT_CODE=ON` 编译，不修改测试或播放器源码。
- RPM 安装阶段只筛选 Fedora 不适用的 Debian 配置路径与重复 schema，不修改编译源码。
- `gxde-api` 的 `.pkla` 文件仍被打包；其 `/var/lib/polkit-1` 父目录由 Fedora `polkit-pkla-compat` 提供并保持 `root:polkitd 0750`，RPM 不重复占有这些目录，同时依赖该兼容包解析规则。无需修改 `gxde-api` 源码。

若未来必须回补源码修复，先列出组件/tag、补丁内容、原因和移除条件，并向用户报告。
