# 真机联调一次性脚本：断电->上电->长按开机键，同时监听 63001 的 [DUTx] 日志
# 用法: "$DAIMON_USER_PYTHON" backend/tests/live_boot_sniff.py [listen_seconds]
import socket
import sys
import time

sys.path.insert(0, "backend")
from app.commboard import MbRtuUdpClient  # noqa: E402

BOARD_IP = "192.168.50.100"
LISTEN_PORT = 63001
DUT_MASK = 0x00F0  # 线 4-7

listen_s = int(sys.argv[1]) if len(sys.argv) > 1 else 60

mb = MbRtuUdpClient(BOARD_IP, 501)

sniff = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sniff.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sniff.bind(("0.0.0.0", LISTEN_PORT))
sniff.settimeout(0.5)

print(f"[1] 断电 (0xA2=0x0000)...")
mb.write_multiple(0xA2, [0x0000])
time.sleep(2)

print(f"[2] 上电 (0xA2=0x{DUT_MASK:04X})...")
mb.write_multiple(0xA2, [DUT_MASK])
time.sleep(1)

print("[3] 长按开机键 3s (0xA4=0x0000 -> 0xFFFF)...")
mb.write_multiple(0xA4, [0x0000])
time.sleep(3)
mb.write_multiple(0xA4, [0xFFFF])

print(f"[4] 监听 {LISTEN_PORT} {listen_s}s ...")
t0 = time.time()
count = 0
while time.time() - t0 < listen_s:
    try:
        data, addr = sniff.recvfrom(2048)
    except socket.timeout:
        continue
    count += 1
    text = data.decode("utf-8", errors="replace")
    print(f"  [{count}] {addr[0]}:{addr[1]} {len(data)}B | {text[:160]!r}")

print(f"结束：共收到 {count} 个包")
