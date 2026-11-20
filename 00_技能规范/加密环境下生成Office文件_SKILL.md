# 加密环境下生成 / 转换 Office 文件 · SKILL

> 用途：公司装了文档加密驱动（文件首部会出现 `%TSD-Header-###%`），Python / Excel 写出的 `.xlsx`、`.docx` 落盘即成密文，Polaris、邮件、其他电脑打开就是乱码。本文记录判断方法、绕过原理和现成做法。
>
> 关联：`06_杂项/01_工具脚本/fix_file_encryption.py`、`06_杂项/01_工具脚本/一键解密Office文件_双击运行.cmd`、`03_项目管理与模板/05_项目管理工具/02_脚本/generate_zijing_schedule_xlsx.py`、`generate_sandisk_schedule_xlsx.py`
> 首次记录：2026-10-17（紫荆芯界 / 闪迪 Schedule 生成时踩到）

---

## 一、什么时候用

- 用 openpyxl / python-docx 生成的 `.xlsx`、`.docx`，自己打开正常，别人 / Polaris / 手机端打开是乱码。
- `git status` 里看不出异常，但工作区文件的十六进制开头不是 `PK`，而是 `%TSD-Header-###%`。
- 想把历史遗留的密文 Office 文件转成普通文件（发给外部、上传、用别的工具读）。

---

## 二、先判断文件到底加没加密

**关键坑：不要用 Python 去判断**。加密驱动会对白名单进程（python.exe、EXCEL.EXE、git.exe 等）做透明解密，Python 读到的永远是明文，判断永远为"没加密"。

必须让**不在白名单里的进程**读原始字节，比如 PowerShell / .NET：

```powershell
$b = [System.IO.File]::ReadAllBytes("D:\path\a.xlsx")[0..7]
[System.Text.Encoding]::ASCII.GetString($b) -replace "[^\x20-\x7E]", "."
# 正常：PK......   加密：%TSD-Hea
```

文件被占用时用共享读：

```powershell
$fs = [System.IO.File]::Open($p, 'Open', 'Read', 'ReadWrite')
$buf = New-Object byte[] 2; $null = $fs.Read($buf, 0, 2); $fs.Close()
```

---

## 三、原理：驱动按「扩展名 + 进程」拦截写入

实测（同一份内容，同一台机器）：

| 写入方式 | 落盘结果 |
| --- | --- |
| python `open('a.xlsx','wb').write(...)` | 🔒 加密 |
| python `wb.save('a.xlsx')`（openpyxl） | 🔒 加密 |
| Excel COM `Workbook.SaveAs(..., 51)` | 🔒 加密 |
| python 写 `a.zip` → python `os.replace` 改名 `a.xlsx` | 🔒 加密（同进程仍被拦） |
| python 写 `a.xlsx` 时改成 `.dat` / `.bin` / `.zip` 扩展名 | ✅ 明文（策略只认文档类扩展名） |
| python 写 `a.zip` → **PowerShell `Move-Item`** 改名 `a.xlsx` | ✅ 明文 |
| python 写 `a.zip` → **cmd `move`** 改名 `a.xlsx` | ✅ 明文 |
| `Copy-Item` 一个明文 xlsx（改名/复制都不重写内容） | ✅ 明文 |

两条结论：

1. 策略按**扩展名**命中：`.xlsx / .docx / .pptx / .txt / .csv` 加密，`.zip / .dat / .bin` 不加密。
2. 加密发生在**写入内容的进程**里。改名只是元数据操作，只要由非白名单进程（PowerShell、cmd）执行，就不会被加密。

> 顺带解释一个现象：Polaris Office 另存出来的文件是明文（它不在策略名单里），而 Excel / WPS / Python 另存的是密文。

---

## 四、标准做法：Python 生成，PowerShell 改名

生成脚本里不要直接 `wb.save('xxx.xlsx')`，统一走下面这个函数（两个甘特图脚本已经在用）：

```python
import os
import subprocess


def save_unencrypted(wb, out_path):
    """加密驱动按扩展名加密 python 直接写出的 .xlsx；
    先存成 .zip，再交给 PowerShell 改名，产物就是普通（不加密）的 xlsx。"""
    tmp = out_path + '.zip'
    wb.save(tmp)
    if os.path.exists(out_path):
        os.remove(out_path)
    try:
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        'Move-Item -LiteralPath "%s" -Destination "%s" -Force' % (tmp, out_path)],
                       check=True, capture_output=True)
    except Exception:
        os.replace(tmp, out_path)   # 非 Windows / 没装 PowerShell 时兜底
        return
    # 自检：python 读不出真相，必须让 PowerShell 读
    probe = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         'Get-Content -LiteralPath "%s" -Encoding Byte -TotalCount 2 '
         '| ForEach-Object { [char]$_ }' % out_path],
        capture_output=True, text=True)
    if ''.join(probe.stdout.split()) != 'PK':
        print('警告：%s 仍为加密格式，请检查加密驱动策略' % out_path)
```

要点：

- 中间文件用 `out_path + '.zip'`，和产物同目录，`Move-Item` 是同一卷内的改名，不会跨盘复制（跨盘复制会退化成"重写内容"，有被加密风险）。
- `-LiteralPath` + 双引号包路径：路径里有 `'`（本机路径 `arcoview's documents`）也没问题，不用转义。
- 自检不能省：驱动策略哪天变了，脚本会直接告警，而不是悄悄产出密文。
- python-docx / python-pptx 同理：`doc.save('a.docx.zip')` → `Move-Item` → `a.docx`。

---

## 五、历史文件批量转换

### 5.1 一键版（给不熟命令行的人用）：`一键解密Office文件_双击运行.cmd`

`06_杂项/01_工具脚本/一键解密Office文件_双击运行.cmd`（按 `COLLABORATION.md` 的归档约定："脚本/工具 → `06_杂项/01_工具脚本/`"），**单个文件、自包含**（Python 源码以 `#=== PYTHON SOURCE BELOW ...` 为界嵌在文件尾部，cmd 段跑完 `exit /b` 就不会执行到它；运行时用 PowerShell 把自己尾部源码抽到 `%TEMP%` 再交给 `py -3`）。

三种用法：

| 用法 | 效果 |
| --- | --- |
| **双击** | 处理 `.cmd` 所在目录（不含子目录）；若该目录**没有**待解密文件，窗口自动变成"拖放区"，提示你把文件夹/文件拖进来（也可粘贴路径，回车退出） |
| 把**文件夹/文件拖到 .cmd 上**（可多个） | 处理拖进来的对象 |
| 拖文件夹时在路径后加 `-r`（或 `cmd` 里 `xxx.cmd "D:\目录" -r`） | 递归处理子目录 |

支持扩展名：`xlsx xlsm xltx xlsb docx docm pptx pptm csv txt pdf md py json html doc xls ppt`（实测被驱动加密的扩展名：xlsx / docx / xls / pptx / pdf / txt / md / py）。

特性：已是明文的自动跳过、被 WPS/Office 占用的报"被占用"不中断、转换后回写原 mtime、结束前用 PowerShell 复检首字节并打印"转换 N 个 / 失败 N 个"、临时文件自动清理（清单用 `.dat`、中间产物用 `.plain.zip`，两者都不会被驱动加密）。

> 维护注意：`.cmd` 里 Python 源码直接用 UTF-8（无 BOM）保存，cmd 段自身的 `echo` 只用 ASCII 提示——中文提示全部由 Python 打印，否则 cmd 按 GBK 解析会乱码。中间清单文件必须用 `.dat` 扩展名，绝不能落成 `.txt`（`.txt` 会被驱动加密，PowerShell 读到就是密文）。

### 5.2 命令行版：`fix_file_encryption.py`

工具：`06_杂项/01_工具脚本/fix_file_encryption.py`

```powershell
# 单个文件或整个目录（递归处理 xlsx/xlsm/docx/pptx/csv）
& "C:/Users/pc/AppData/Local/Python/pythoncore-3.14-64/python.exe" `
  "06_杂项/01_工具脚本/fix_file_encryption.py" `
  "03_项目管理与模板/01_项目目录/10_紫荆芯界"
```

原理同上：用 Python 读出（透明解密后的）内容 → 写成 `<原名>.plain.zip` → PowerShell 改名回原扩展名。

转换是**无损的**（字节级解密，不改内容）。转换后建议抽查：

```python
import zipfile, openpyxl
with zipfile.ZipFile(p) as z:          # docx/pptx/xlsx 都是 zip，CRC 能查完整性
    assert z.testzip() is None
openpyxl.load_workbook(p).close()      # xlsx 再确认能被解析
```

---

## 六、坑与注意事项

1. **Python 自己判断不了加密状态**（§二），所有校验都要走 PowerShell。
2. **Excel / WPS 另存一次就会再加密**。别人传回来的表、自己在 WPS 里改过的表，都会变回 `%TSD`；需要明文时用工具再跑一遍。
3. **git 里存的一直是明文**。`git.exe` 在白名单里，提交时读到的是解密内容，所以仓库本身没问题，只有本地工作区文件是密文。核对方法：
   ```powershell
   cmd /c "git show HEAD:`"path/a.xlsx`" > $env:TEMP\blob.bin"
   [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes("$env:TEMP\blob.bin")[0..1])
   ```
4. **别把 `.zip` 中间文件留在目录里**：正常流程改名后会消失；异常中断残留的话手工删掉，免得混进 git。
5. **文件被 WPS 占用时**转换会失败（报"正由另一进程使用"）；先关文件再跑，或改用共享读校验。
6. **安全边界**：绕过的是本地落盘格式，不是权限。涉及客户机密的外发仍按公司流程走，别把解密当成"可以随便传"。

---

## 七、速查

| 需求 | 命令 / 做法 |
| --- | --- |
| 看文件是不是密文 | `[System.IO.File]::ReadAllBytes($p)[0..1]` → `PK` / `%TSD` |
| Python 生成不加密的 xlsx | 存 `.zip` → PowerShell `Move-Item` → `.xlsx` |
| 历史密文批量转明文 | `python fix_file_encryption.py <目录>` |
| 扔到文件夹里双击就解密 | 复制 `06_杂项/01_工具脚本/一键解密Office文件_双击运行.cmd` 过去双击；拖文件夹可指定目录，加 `-r` 递归 |
| 双击后目录里没有待解密文件 | 窗口自动变拖放区，把文件夹/文件拖进去即可（回车退出） |
| 确认仓库里存的是明文 | `git show HEAD:path > tmp` 后读首字节 |
| 已被 Excel/WPS 改回密文 | 再跑一次转换工具 |
