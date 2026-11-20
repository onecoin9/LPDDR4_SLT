# NuGet 包还原与构建说明

> 适用：`LPDDR4x_SLT_Standard`（.NET Framework 4.5.2 / 4.7.2 / 4.8，WinForms + 类库，`packages.config` 方式管理依赖）
> 原因：仓库不再提交 `packages/`、`bin/`、`obj/`（体积 500MB+，且都能重新生成），拉下来后**必须先还原依赖**。

---

## 一、先搞清依赖从哪来

| 文件 | 作用 |
|---|---|
| `BLL/packages.config` | 声明 BLL 依赖（Newtonsoft.Json 13.0.3） |
| `Common/packages.config` | 15 个包（EntityFramework 6.5.1、System.Data.SQLite 2.0.2、SourceGear.sqlite3 3.50.3 …） |
| `HXY_TB_MT02/packages.config` | 12 个包（CircularProgressBar、WinFormAnimation、SourceGear.sqlite3 3.50.4.2 …） |
| `Test/packages.config` | 48 个包（DotNetty、Quartz、Modbus.Net、Microsoft.Extensions.* …） |

- 所有 `.csproj` 的引用都是 `HintPath = ..\packages\<包名>.<版本>\lib\...`，即**解决方案级** `packages` 目录（与 `AC_LPDDR4x_Tool.sln` 同级）。
- 还原 = 按 `packages.config` 把包下载解压到 `packages\`。**版本号已锁定**，还原结果和原来完全一致（源码不用改）。

前置条件：Windows + .NET Framework 4.8 运行库；构建/还原需要 **Visual Studio 2019/2022（含 .NET 桌面开发工作负载）**，或独立的 `nuget.exe`。

---

## 二、方式一：Visual Studio（最省事，推荐）

1. 用 VS 打开 `AC_LPDDR4x_Tool.sln`。
2. VS 会自动还原；若没有，右键**解决方案** → **还原 NuGet 程序包**（Restore NuGet Packages）。
3. 还原完成后 `packages\` 目录会重新出现（约 425MB），解决方案资源管理器的黄色感叹号消失。
4. 生成：`生成` → `生成解决方案`（配置 `Release` + 平台 `x64`）。

> 想改回「每次打开自动还原」：`工具 → 选项 → NuGet 包管理器 → 常规 → 允许 NuGet 下载缺少的程序包`。

---

## 三、方式二：nuget.exe 命令行

### 1) 获取 nuget.exe（8.x，单文件，无需安装）

```powershell
$dst = "C:\Tools\nuget.exe"
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
curl.exe -sSL -o $dst https://dist.nuget.org/win-x86-commandline/latest/nuget.exe
& $dst help | Select-Object -First 3      # 验证：打印 NuGet 版本
```

> 内网无法直连 `dist.nuget.org` 时，从公司软件库或另一台机器拷贝 `nuget.exe` 即可（与 VS 自带版本无差别）。

### 2) 还原整个解决方案（在 `AC_LPDDR4x_Tool.sln` 所在目录执行）

```powershell
cd "D:\arcoview's documents\工作文档\LPDDR\LPDDR4x_SLT_Standard"
& C:\Tools\nuget.exe restore .\AC_LPDDR4x_Tool.sln -PackagesDirectory .\packages -NonInteractive
```

- 路径含空格、单引号（`arcoview's documents`）时**必须整体加双引号**，或像上面这样先 `cd` 再写相对路径。
- `-PackagesDirectory .\packages` 明确指定目标目录，避免还原到别处。
- 输出结尾出现 `已还原 ... 个包` / `Installed ... packages`，且 `packages\` 里能看到上表所有包名目录，即为成功。

### 3) 只还原某个项目（调试单个工程时更快）

```powershell
cd "...\LPDDR4x_SLT_Standard"
& C:\Tools\nuget.exe restore .\BLL\packages.config   -PackagesDirectory .\packages -NonInteractive
& C:\Tools\nuget.exe restore .\Common\packages.config -PackagesDirectory .\packages -NonInteractive
```

### 4) 构建（命令行）

```powershell
# 优先用 VS 自带的 MSBuild（不要用 .NET Framework 4.0 的老 msbuild）
& "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" `
   .\AC_LPDDR4x_Tool.sln /t:Build /p:Configuration=Release /p:Platform=x64 /m
```

产物：`HXY_TB_MT02\bin\x64\Release\AC_LPDDR4x_Tools.exe`。

---

## 四、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `错误 MSB4066: 无法识别元素 <PackageReference> 中的特性"Version"` + `MSBuild 14.0` 警告 | 机器上只有旧的 .NET Framework 4.0 MSBuild，nuget 探测项目图失败。**不影响 `packages.config` 还原**（日志会写"将跳过 NETCore 和 UAP 项目，仅还原 packages.config 文件"）；想消除告警就加 `-MSBuildVersion 15` 或直接用 VS 还原 |
| 还原成功但编译报"未能找到类型/命名空间" | 检查包目录名是否为 `<id>.<version>` 原样（如 `SourceGear.sqlite3.3.50.3`），且与 `packages.config` 版本一致；不一致就删掉 `packages\` 重新还原 |
| 编译报 `HintPath` 找不到 | 说明包还原到了别处（比如用户级缓存）。务必带 `-PackagesDirectory <解决方案>\packages` |
| 提示包"已安装"但目录是空的 | 上次还原被中途打断，删掉 `packages\` 重新执行 |
| 内网/离线 | `nuget restore ... -Source "D:\nuget-offline;https://api.nuget.org/v3/index.json"`（分号分隔多个源） |
| 需要清理重来 | 删 `packages\`、各项目 `bin\`、`obj\`，再还原 + 重新生成 |
| WPS/Excel 与本文无关 | 公司加密驱动只影响 Office/文本落盘，**不影响** NuGet 还原和编译产物 |

---

## 五、为什么仓库里没有 `packages/`

`packages/` 428MB、`bin/` 68MB、`obj/` 11MB —— 全部可由 `packages.config` + 源码重建，提交进 Git 会让仓库膨胀 40 倍、推送/克隆极慢。

- 忽略规则见仓库根目录 `.gitignore`（`packages/`、`[Bb]in/`、`[Oo]bj/`、`.vs/`、`*.nupkg`）。
- **确实需要把 `packages\` 一起入库**（离线交付、内网无源）时：注释掉 `.gitignore` 里的 `packages/` 与 `*.nupkg` 两行，再 `git add -f packages`。
- 更推荐的做法：把 `packages\` 里的 `.nupkg` 收进一个**本地文件源**目录（如 `D:\nuget-offline`），只分发这一个目录，还原时用 `-Source`。
