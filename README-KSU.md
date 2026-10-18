# Nokia 7 Plus (B2N) — 4.4.192 + ReSukiSU/BakaSU CI

这个分支只放 **CI 工作流、设备内核配置、手动 hook 补丁和 boot 重打包脚本**，不重复存 1.1 GB 内核源码。  
工作流会从本仓库的 Release 下载：

- `Nokia7plus_V4.16H.tar.gz`（内核源码）
- `boot_b_stock.img`（原厂 boot_b，用于保留 ramdisk/DTB）

编译完成后直接产出可 fastboot 刷入的 `boot_b-ksu.img`，不需要手动打包。

已验证：

- 源码：Nokia 官方 4.16H OSS，Linux **4.4.192**
- 设备：Nokia 7 Plus `B2N_sprout`，Android 10 `00WW_4_15F` / `00WW_4_15G`
- 内核配置来自设备 `/proc/config.gz`，`olddefconfig` 零差异
- 原厂 `vermagic = 4.4.192-perf+ SMP preempt mod_unload modversions aarch64`
- 原厂 vendor 模块的 `__versions` CRC 与编译结果 **全部匹配**
- 内核内嵌 FIH 签名公钥（`certs/fih/signing_key.pem`），原厂模块签名校验可通过
- BakaSU 版本：`v4.2.0-rc3`（内核版本号 35171，与 release manager APK 一致）
- 手动 hook：`stat` / `execveat` / `faccessat` / `sys_reboot`
- 自动 hook：`setuid` / `init.rc` / `input`（LSM + input_handler）
- 额外开启：`CONFIG_OVERLAY_FS=y`，供 metamodule 使用
- 设备实测：刷入 `boot_b-ksu.img` 后可正常开机，Wi-Fi 模块正常加载，ReSukiSU 管理器显示“工作中 / Built-in”
- `boot_b-ksu.img` 的 header SHA1 校验和算法与 Magiskboot 一致，已在设备上实际刷入验证

## 一、准备 Release 资源

CI 需要仓库 Release 里有一个固定 tag 和两个资源：

- tag：`kernel-source-4.16H`
- `Nokia7plus_V4.16H.tar.gz`（约 178 MB）
- `boot_b_stock.img`（约 64 MB，原厂 boot_b）

本机文件位置：

- `Kernel/Nokia7plus_V4.16H.tar.gz`
- `Kernel/boot_b_stock.img`（md5 `8ee80187de9f99144ea563cbf9f5c134`）

> **不要用 README 编辑器里的“附件/图片”按钮上传。**
> `We don't support that file type` 是 Markdown 编辑器的附件限制，而且会把大文件塞进仓库。
> 正确入口是仓库首页右侧的 **Releases** → `Attach binaries`。

网页操作：

1. 打开 fork 仓库首页 → 右侧 **Releases** → 编辑已有的 `kernel-source-4.16H`（或新建）
2. 在 **Attach binaries by dropping them here or selecting them** 区域上传：
   - `Nokia7plus_V4.16H.tar.gz`
   - `boot_b_stock.img`
3. **Update release / Publish release**

或者用 `gh`：

```bash
gh release create kernel-source-4.16H \
  "/path/to/Nokia7plus_V4.16H.tar.gz" \
  "/path/to/boot_b_stock.img" \
  --title "Nokia 7 Plus 4.16H kernel source + stock boot" \
  --notes "Source and stock boot_b for CI"
```

工作流下载地址：

```text
https://github.com/<你的仓库>/releases/download/kernel-source-4.16H/Nokia7plus_V4.16H.tar.gz
https://github.com/<你的仓库>/releases/download/kernel-source-4.16H/boot_b_stock.img
```

如果放在别的仓库/Release，改 `.github/workflows/build-ksu.yml` 里的 `KERNEL_SOURCE_TAG` / `url`。

## 二、推送 CI 分支

把本目录内容放到 fork 仓库的 `ci` 分支，然后推送：

```bash
git checkout -b ci
git add .github ci README-KSU.md
git commit -m "ci: build 4.4.192 kernel with BakaSU"
git push origin ci
```

推送到 `ci` 或 `ksu-4.4.192` 会自动触发构建；也可以在 Actions 页面手动 `Run workflow`。

## 三、构建产物

Actions 产物：

- **`boot_b-ksu.img`**：约 64 MB，可直接 `fastboot flash boot_b`
- `Image.gz`：约 12 MB，供检查/手动重打包
- `Image.gz-dtb`：约 25 MB，含编译出的 DTB，仅供检查
- `out/.config`
- `build.log`

`boot_b-ksu.img` 的生成方式：

1. 从 Release 下载原厂 `boot_b_stock.img`
2. 解出原厂 ramdisk 和 append 在 kernel 后面的原厂 DTB
3. 用新编译的 `Image.gz` 替换原厂 gzip 内核，保留原厂 ramdisk + DTB
4. 按 Magiskboot 相同算法重算 boot header 的 SHA1 checksum
5. 补齐到原厂 64 MiB 大小

## 四、刷机

CI 产物直接刷：

```bash
adb reboot bootloader
fastboot flash boot_b boot_b-ksu.img
fastboot --set-active=b
fastboot reboot
```

回退到 Magisk（slot A）：

```bash
fastboot --set-active=a
fastboot reboot
```

### 手动重打包（备用）

如果哪天想手动做，不要直接把 `Image.gz-dtb` 当 `kernel`，否则会和原厂 DTB 叠加（内核体积会到 45 MB 左右）。正确做法是只用 `Image.gz`，保留原厂 `kernel_dtb`：

```bash
cd /data/local/tmp
cp /sdcard/Download/boot_b_stock.img .
magiskboot unpack boot_b_stock.img
cp /sdcard/Download/Image.gz kernel
magiskboot repack boot_b_stock.img new-boot.img
```

## 五、metamodule

BakaSU 的模块系统需要 metamodule 才能挂载 `/data/adb/modules`。当前内核已开启 `CONFIG_OVERLAY_FS=y`，推荐：

- `KernelSU-Modules-Repo/meta-overlayfs`（OverlayFS，官方参考实现）
- 如果 4.4 上 OverlayFS 方案不稳定，可换 `KernelSU-Modules-Repo/meta-mm` 或 `magic_mount_rs`（Magic Mount）

安装 metamodule 并重启后：

- 现有 Magisk 模块会出现在模块页并尝试挂载
- `/system/bin/su` 会出现，`su -c id` 可用
- 管理器 “超级用户” 页可管理授权

## 六、注意事项

- `boot_b_stock.img` 必须是 **4.15G 的原厂 boot_b**（md5 `8ee80187de9f99144ea563cbf9f5c134`），不要用别的槽位/版本。
- 当前内核构建目标是 `Image.gz-dtb`，不编译外部模块；原厂 `/vendor/lib/modules/*.ko` 直接复用。
- 源码路径不能带空格，工作流解压到 `$GITHUB_WORKSPACE/kernel`，符合要求。
- `LOCALVERSION=+` 用于得到 `4.4.192-perf+`，不要删。
- 旧 workflow 直接 clone AOSP GCC 4.9 仓库现在拿不到编译器；这里改用 LineageOS 的 prebuilt 镜像。
- GitHub Release 上传 `.tar.gz` / `.img` 即可；`.tar.bz2` 在 Markdown 编辑器里会报 `We don't support that file type`，但 Release 资源本身通常支持。为了避免踩坑，CI 统一用 `.tar.gz`。
