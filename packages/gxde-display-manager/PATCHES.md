# GXDE Display Manager 源码补丁登记

当前新增源码补丁：**1 项**。

## `0001-systemd-conflict-with-kmscon-vt.patch`

- 组件/tag：`gxde-display-manager 1.3.7-gxde2`。
- 原因：`kmsconvt@.service` 可通过 systemd 标准的 `autovt@.service` 别名替代
  `getty@.service`，但上游 `gxdm.service` 只与 `getty@tty${SDDM_INITIAL_VT}`
  冲突。启用 kmscon 新型 fbcon 后，两者会同时占用 GXDM 初始 VT，造成 greeter
  或 FlakeWM 会话无法取得 DRM/VT。
- 修改：在 `Conflicts=` 和 `After=` 中同时加入
  `kmsconvt@tty${SDDM_INITIAL_VT}.service`。GXDM 启动时先停止同一 VT 上的 kmscon，
  并在 `ExecStartPre=` 停止当前已加载的 `kmsconvt@tty*.service`：kmscon 在其他 VT
  持有 DRM master 时同样会阻止 FlakeWM greeter 打开显卡。这里只清理 GXDM 启动
  当下的实例，不对 tty2–tty6 添加双向 `Conflicts=`，因此之后切换到文本 VT 仍可
  重新生成 kmscon，不会反向停止 GXDM。停止 GXDM 后 systemd/logind 也可按原配置
  重新生成 kmscon autovt。
- 依据：Fedora LightDM 已采用相同的 getty+kmscon 冲突/排序关系；systemd 上游
  issue #41087 也记录了各显示管理器需要兼容 kmsconvt 的问题。
- 移除条件：GXDE 正式标签的 `gxdm.service.in` 已包含同等的 kmsconvt 冲突关系。

## Fedora 适配（非源码补丁）

以下调整均通过构建参数、独立 PAM 文件或 spec 安装规则实现，不修改上游源码：

- **锁屏正式拆包（1.3.7-gxde1）**：上游已删除 GXDM 内置 locker、旧 autostart
  和锁屏专用依赖，并新增 `gxdm-settings-agent` 供 `gxde-lock 2.0.0-gxde3` 同步
  用户壁纸。因此 Release 5 中删除旧 autostart 的安装树适配已经移除；RPM 仅以
  `Recommends: gxde-lock` 表达上游的可选运行时关系，**没有新增上游源码 patch**。

- **PAM 配置**：上游 `services/gxdm.pam` 和 `gxdm-autologin.pam` 使用 Arch 的 `system-login`；Fedora 的 PAM 栈基于 `password-auth`/`postlogin`/`pam_selinux`。构建时 `-DINSTALL_PAM_CONFIGURATION=OFF` 禁用上游 PAM 安装，spec 提供 4 个 Fedora 专用 PAM 文件（`gxdm.pam`、`gxdm-autologin.pam`、`gxdm-greeter.pam`、`gxdm-rescue.pam`），基于 Fedora sddm 包的 PAM 文件适配。`gxdm-greeter.pam` 与上游模板生成的文件一致，已是通用的。
- **Rust 依赖 vendor**：`gxdm-emergency-mode` 上游未 vendor 依赖（无 `vendor/` 目录），AUR 用 `cargo fetch` 预下载。COPR 构建无网络，因此在 source prepare 阶段（本机有网络和 cargo）运行 `cargo vendor --locked --versioned-dirs`，生成 `vendor/` 目录和 `.cargo/config.toml`，打包为 `Source2`。构建时 `cargo build --offline --frozen` 使用 vendored crates。
- **`/usr/sbin`→`/usr/bin`**：`gxdm-emergency-mode` 的 systemd service 文件引用 `/usr/sbin/gxdm-emergency-mode`；Debian 布局 `/usr/sbin` 在 Fedora 是 `/usr/bin` 的符号链接。build.sh 用 `sed` 修复 service 文件路径，与 AUR 一致。spec 的 `%install` 段也处理二进制文件位置。
- **MavenPro 清理（1.3.7-gxde1）**：MavenPro 字体随上游内置 locker 一并删除，
  因此 RPM 不再下载或打包其独立 OFL 文件；许可证元数据改为覆盖当前仍随 greeter
  分发的 GPL、MIT、Creative Commons 与 Open Sans/Apache-2.0 内容。
- **SELinux 子包**：Fedora targeted 策略只预置 SDDM/GDM/LightDM 的文件上下文；GXDM
  原先以 `unconfined_service_t` 运行，PAM 认证成功后执行任何用户会话都会被拒绝
  `process transition`，helper 退出码为 2。`gxde-display-manager-selinux` 现在提供
  `gxdm.fc`，将 daemon/greeter 映射到 Fedora 已有的 `xdm_exec_t`，helpers/session
  scripts 映射到 `bin_t`，运行时目录映射到既有的 `xdm_var_*` 类型。没有增加 allow
  规则，也没有创建新权限域；复用 Fedora display-manager 策略的最小文件上下文模块。
  在 enforcing 模式下已真实进入 GXDE/FlakeWM 与 Plasma Wayland 会话验证。

若未来必须回补源码修复，先列出组件/tag、补丁内容、原因和移除条件，并向用户报告。
