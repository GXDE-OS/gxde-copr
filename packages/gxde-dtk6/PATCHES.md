# DTK6 源码补丁登记

当前补丁：**无**。不使用 sed 或其他隐式源码修改。

## Treeland 0.7.0 构建期依赖

- `linuxdeepin/treeland-protocols` 正式 tag `0.7.0`，与 `gxde-infra` 使用相同 commit 和 SHA256。
- **无源码 patch**。协议仅暂存供 `dtk6gui` 编译，不随 DTK6 RPM 安装。移除 `DTK_DISABLE_TREELAND=ON`，并检查 Treeland 子构建成功且使用暂存的协议。
- 移除条件：Fedora 提供兼容的协议包，且可直接作为 DTK6 构建依赖。

## 已移除：0001-dtk6core-qt611-entrylist.patch

- 组件/tag：`dtk6core 6.0.48`。
- 上游来源：[e3a80079](https://github.com/GXDE-OS/dtk6core/commit/e3a80079cc185fe5c000d9490f72926629088ecb)。仅添加源码目录前缀，补丁内容相同。
- 原因：COPR 11170214 的 Qt 6.11 中，旧 `QFSFileEngine::entryList` 已移除。
- 修改：仅在 Qt < 6.11 时编译旧 entryList 声明和实现，新版沿用已有 beginEntryList。
- 移除条件：正式 tag 包含上述提交并通过 Fedora 45 验证。
- Release 4 曾应用；现已切换到正式 tag `6.0.48-gxde1`（`5b38ef81734e`），确认包含上述修复，删除回补补丁。新标签的 Fedora 构建待验证。已向用户报告。


## 已移除：0001-dtk6log-find-qt6-coreprivate.patch

Release 2 曾针对 `dtk6log 0.0.5` 补充 Qt ≥ 6.10 的 CorePrivate 查找。
重新核对远端后发现正式 tag `0.0.6-1` 已包含该修复；旧 tag 识别规则漏掉了数字后缀。
Release 3 修正 tag 识别、采用 `0.0.6-1` 并移除补丁。已经向用户报告。
后续任何补丁或源码修改都必须记录组件/tag、原因、移除条件并向用户报告。
