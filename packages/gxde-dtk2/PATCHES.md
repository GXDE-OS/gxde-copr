# GXDE DTK2 源码补丁

## 0001-factory-python-glob.patch

- 组件/tag：`dde-qt-dbus-factory 6.1.0-gxde6`，commit `7278ee0df4eda911f2860d1a5d73979c4afe781d`。
- 原因：COPR 11170427 在 Fedora 45 的 Python 上因 `glob.glob1` 已移除而使代码生成失败；GXDE 主分支尚未修复。
- 修改：三处 `glob.glob1(目录, 匹配式)` 改为 `glob.glob(匹配式, root_dir=目录)`，仍返回目录内的相对文件名。Python 3.10+ 支持 `root_dir`。
- 移除条件：GXDE 正式新标签包含兼容 Python 的代码生成修复，并通过 Fedora 45 构建。
- Release 2 开始应用；已向用户报告。补丁文件固定包含在 SRPM 中，不在构建时下载。

构建脚本另外生成指向临时 staging 目录的 pkg-config 副本，不修改上游源码。
任何新增源码补丁必须记录对应 tag、来源、原因、移除条件，并向用户报告。
