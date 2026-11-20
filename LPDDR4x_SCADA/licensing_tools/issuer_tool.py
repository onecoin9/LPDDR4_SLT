"""Internal issuer GUI/CLI, kept separate from the customer application."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from licensing_tools.client_request import read_request
from licensing_tools.issue_license import issue
from licensing_tools.private_key import create_key, load_key


def make_window(key_path, hidden=False):
    window = tk.Tk()
    if hidden:
        window.withdraw()
    window.title("LPDDR4x SCADA · 管理端授权签发")
    window.geometry("700x420")
    window.resizable(False, False)
    panel = ttk.Frame(window, padding=24)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="离线授权签发", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))
    request_path, customer = tk.StringVar(), tk.StringVar()
    expiry = tk.StringVar(value=(dt.date.today()+dt.timedelta(days=30)).isoformat())
    key_id, private = load_key(key_path)
    del private
    ttk.Label(panel, text="管理端密钥：" + key_id).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 18))
    def choose():
        path = filedialog.askopenfilename(parent=window, title="选择客户申请文件 client_id")
        if not path:
            return
        try:
            req = read_request(Path(path).read_bytes())
            request_path.set(path)
            preview.set(req["clientId"])
        except (OSError, ValueError):
            messagebox.showerror("申请无效", "请选择新版 ClientIDTool 导出的 client_id 申请文件（SLT2 封装；留档的旧明文申请也可读取）。", parent=window)
    ttk.Label(panel, text="申请文件").grid(row=2, column=0, sticky="e", padx=(0, 12))
    ttk.Entry(panel, textvariable=request_path, width=52, state="readonly").grid(row=2, column=1, sticky="ew")
    ttk.Button(panel, text="浏览", command=choose).grid(row=2, column=2, padx=(8, 0))
    preview = tk.StringVar()
    ttk.Label(panel, text="机器编号").grid(row=3, column=0, sticky="e", padx=(0, 12), pady=12)
    ttk.Entry(panel, textvariable=preview, state="readonly", font=("Consolas", 9)).grid(row=3, column=1, columnspan=2, sticky="ew")
    ttk.Label(panel, text="客户名称").grid(row=4, column=0, sticky="e", padx=(0, 12))
    ttk.Entry(panel, textvariable=customer).grid(row=4, column=1, columnspan=2, sticky="ew")
    ttk.Label(panel, text="有效期至").grid(row=5, column=0, sticky="e", padx=(0, 12), pady=12)
    ttk.Entry(panel, textvariable=expiry).grid(row=5, column=1, sticky="ew")
    ttk.Label(panel, text="YYYY-MM-DD").grid(row=5, column=2, padx=(8, 0))
    ttk.Label(panel, text="到期日按北京时间计，包含所选日期全天。签发前请核对机器编号、客户及期限。",
              wraplength=610).grid(row=6, column=0, columnspan=3, sticky="w", pady=12)
    def sign():
        if not request_path.get() or not customer.get().strip():
            messagebox.showerror("信息不完整", "请先选择申请文件并填写客户名称。", parent=window)
            return
        if not messagebox.askyesno("确认签发", f"客户：{customer.get()}\n有效期至：{expiry.get()}（北京时间）\n确认签发此电脑的授权？", parent=window):
            return
        target = filedialog.asksaveasfilename(parent=window, initialfile="license.lic", defaultextension=".lic", filetypes=[("License", "*.lic")])
        if not target:
            return
        try:
            # The save dialog makes overwriting explicit; signing itself still uses exclusive creation.
            if Path(target).exists():
                messagebox.showerror("文件已存在", "请选择新的文件名，避免覆盖已有授权。", parent=window)
                return
            issue(request_path.get(), key_path, customer.get(), expiry.get(), target)
            messagebox.showinfo("签发成功", "请将 license.lic 返回客户，由客户在上位机设置页导入。", parent=window)
        except (ValueError, OSError):
            messagebox.showerror("签发失败", "请检查申请文件、客户名称、期限和密钥文件。", parent=window)
    ttk.Button(panel, text="签发 license.lic", command=sign).grid(row=7, column=1, columnspan=2, sticky="e", pady=15)
    panel.columnconfigure(1, weight=1)
    return window


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--key-file", default=str(Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent / "keys/issuer.private.key"))
    p.add_argument("--init-key", action="store_true")
    p.add_argument("--public-out")
    p.add_argument("--request")
    p.add_argument("--customer")
    p.add_argument("--expires-on")
    p.add_argument("--days", type=int)
    p.add_argument("--output")
    p.add_argument("--verify-gui", action="store_true")
    p.add_argument("--verify-report")
    a = p.parse_args()
    if a.init_key:
        if not a.public_out:
            p.error("--public-out is required for key initialization")
        create_key(a.key_file, a.public_out)
        print(json.dumps({"keyCreated": True}))
        return
    if a.request:
        if not a.customer or (not a.expires_on and a.days is None) or not a.output:
            p.error("--customer, --expires-on (or --days) and --output are required")
        result = issue(a.request, a.key_file, a.customer, a.expires_on, a.output, days=a.days)
        print(json.dumps({"issued": True, "expiresAt": result["expiresAt"]}))
        return
    window = make_window(a.key_file, a.verify_gui)
    if a.verify_gui:
        window.update_idletasks()
        window.destroy()
        result = {"guiReady": True}
        if a.verify_report:
            Path(a.verify_report).write_text(json.dumps(result), encoding="utf-8")
        print(json.dumps(result))
    else:
        window.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if not any(flag in sys.argv for flag in ("--init-key", "--request", "--verify-gui")):
            messagebox.showerror("签发工具不可用", "无法读取管理端密钥，请联系授权管理员。")
        else:
            print("License issuer failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
