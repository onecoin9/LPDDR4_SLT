"""Customer-side machine request exporter; contains no issuer imports or private key."""
import argparse
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

REPO = Path(__file__).resolve().parents[1]
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(REPO / "backend"))
    sys.path.insert(0, str(REPO))
from app.license_machine import machine_fingerprint
from licensing_tools.client_request import create_request, peek_client_id


def export_request(path):
    raw = create_request(machine_fingerprint())
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as out:
        out.write(raw)
    return target


def make_window(hidden=False):
    window = tk.Tk()
    if hidden:
        window.withdraw()
    window.title("LPDDR4x SCADA · 授权申请工具")
    window.geometry("660x310")
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="生成这台电脑的授权申请", font=("Segoe UI", 17, "bold")).pack(anchor="w")
    ttk.Label(frame, text="导出 client_id 文件，交给授权管理员。收到 license.lic 后在上位机设置页导入。",
              wraplength=590).pack(anchor="w", pady=(10, 18))
    request = create_request(machine_fingerprint())
    client_id = peek_client_id(request)
    ttk.Label(frame, text="本机申请编号").pack(anchor="w")
    field = ttk.Entry(frame, width=68, font=("Consolas", 10))
    field.insert(0, client_id)
    field.configure(state="readonly")
    field.pack(fill="x", pady=(6, 12))
    ttk.Label(frame, text="支持 Windows 10 / Windows 11。系统重装或更换主板后，请重新申请。",
              wraplength=580).pack(anchor="w")
    def save():
        target = filedialog.asksaveasfilename(parent=window, initialfile="client_id", title="保存授权申请")
        if not target:
            return
        try:
            Path(target).write_bytes(request)
            messagebox.showinfo("申请已导出", "请将该文件交给授权管理员。", parent=window)
        except OSError:
            messagebox.showerror("导出失败", "无法保存文件，请选择可以写入的文件夹。", parent=window)
    ttk.Button(frame, text="导出 client_id", command=save).pack(anchor="e", pady=(20, 0))
    return window, client_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--verify-gui", action="store_true")
    parser.add_argument("--verify-report")
    args = parser.parse_args()
    if args.output:
        export_request(args.output)
        print(json.dumps({"requestExported": True}))
        return
    window, client_id = make_window(args.verify_gui)
    if args.verify_gui:
        window.update_idletasks()
        assert len(client_id) == 64
        window.destroy()
        result = {"guiReady": True, "clientIdLength": 64}
        if args.verify_report:
            Path(args.verify_report).write_text(json.dumps(result), encoding="utf-8")
        print(json.dumps(result))
        return
    window.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if not any(flag in sys.argv for flag in ("--output", "--verify-gui")):
            messagebox.showerror("无法生成申请", "机器信息读取失败，请联系管理员并检查 Windows 系统服务。")
        else:
            print("Client ID export failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
