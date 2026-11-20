# 真机联调一次性脚本 v2：断电->上电->开机键，同时监听 63001 原始日志 + 2001-2004 透传 READY 帧
# 用法: "$DAIMON_USER_PYTHON" backend/tests/live_boot_sniff2.py [listen_seconds]
import socket
import sys
import time

sys.path.insert(0, "backend")
from app.commboard import MbRtuUdpClient  # noqa: E402

BOARD_IP = "192.168.50.100"
DUT_MASK = 0x00F0  # 线 4-7

listen_s = int(sys.argv[1]) if len(sys.argv) > 1 else 90

mb = MbRtuUdpClient(BOARD_IP, 501)

socks = []
for port in [63001, 2001, 2002, 2003, 2004]:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.settimeout(0.5)
    socks.append((port, s))

print("[1] 断电 (0xA2=0x0000)...")
mb.write_multiple(0xA2, [0x0000])
time.sleep(2)
print(f"[2] 上电 (0xA2=0x{DUT_MASK:04X})...")
mb.write_multiple(0xA2, [DUT_MASK])
time.sleep(1)
print("[3] 开机键 2s (0xA4=0x0000 -> 0xFFFF)...")
mb.write_multiple(0xA4, [0x0000])
time.sleep(2)
mb.write_multiple(0xA4, [0xFFFF])

print(f"[4] 监听 63001/2001-2004 共 {listen_s}s ...")
t0 = time.time()
count = 0
while time.time() - t0 < listen_s:
    for port, s in socks:
        try:
            data, addr = s.recvfrom(2048)
        except socket.timeout:
            continue
        count += 1
        el = time.time() - t0
        if port == 63001:
            print(f"  [{count}] +{el:5.1f}s :{port} {len(data)}B | {data.decode('utf-8', errors='replace')[:140]!r}")
        else:
            print(f"  [{count}] +{el:5.1f}s :{port} {len(data)}B | {data.hex(' ')}")
print(f"结束：共收到 {count} 个包")
