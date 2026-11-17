# DTK5 源码改动登记

## 此次 Treeland 支持

- 协议来源：`linuxdeepin/treeland-protocols` 正式 tag `0.9.1`，与 `gxde-infra` 使用相同 commit 和 SHA256。
- **无新增源码 patch**。协议仅作为构建期源码放入暂存目录，不随 DTK5 RPM 安装。`dtk5gui` 不再设置 `DTK_DISABLE_TREELAND=ON`；构建脚本检查 Treeland 子构建是否成功，以及是否选中暂存的 0.9.1。
- 移除条件：若上游 `dtk5gui` 能直接依赖 Fedora 提供的兼容协议包，可去掉本地构建期暂存；当前不能直接使用 Fedora 0.5.x 的不同协议布局。

## COPR Release 序号修正（2026-11-17）

- COPR 中曾有手工迭代产生的 `6.7.43-8`，高于仓库锁文件自动计算出的
  `6.7.43-6`，导致新协议构建成功却不会升级已安装的 `-8`。
- 本轮将 Release 提升到 `9`，确保 treeland-protocols 0.9.1 和当前 dwayland
  打包能覆盖历史 COPR 版本。仅修正 RPM 版本序，**没有新增源码 patch**。

## 既有构建期源码替换

- 组件/tag：`dtk5gui 6.7.43`。
- 位置：`build.sh` 对 `dtk5gui/src/kernel/kernel.cmake` 的 `sed`。
- 原因：构建时生成器必须读取本次构建的暂存 `dsg` 配置，而不是宿主机上的 `/usr/share/dsg/configs/`。
- 修改：将该路径替换为 `$stage/usr/share/dsg/configs/`。这项修改在本次 Treeland 工作之前就已存在，并非新增。
- 移除条件：上游支持通过 CMake 参数指定构建期 `dsg` 配置目录。
