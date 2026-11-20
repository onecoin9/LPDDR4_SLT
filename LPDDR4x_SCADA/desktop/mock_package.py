"""Isolated QA adapter for the existing mock DUT; never talks to hardware."""
import asyncio
import argparse
import json
import os
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--qa', required=True)
args = parser.parse_args()
qa = Path(args.qa).resolve()
fixture = qa / 'fixture'
os.chdir(fixture)
sys.path.insert(0, str(fixture))
import mock_dut
from app.protocol import parse_frame, build_frame, ROLE_SLAVE, CMD_START_TEST
ports = json.loads((qa / 'ports.json').read_text(encoding='utf-8'))
mock_dut.LOG_PORT = ports['log_udp']
trace = (qa / 'logs/mock-wire.jsonl').open('w', encoding='utf-8', buffering=1)
original_send = mock_dut.MockDut._send_frame
original_receive = mock_dut.MockDut.datagram_received

def record(direction, data):
    parsed = parse_frame(data)
    trace.write(json.dumps({'monotonic': time.monotonic(), 'direction': direction, 'cmd': None if parsed is None else f'0x{parsed[0]:02X}', 'frame_hex': data.hex()}) + '\n')
    if direction == 'pc_to_mock' and parsed and parsed[0] == CMD_START_TEST:
        (qa / 'logs/transmitted.cfg').write_text(parsed[1].decode('utf-8'), encoding='utf-8')

def send(self, cmd, payload):
    record('mock_to_pc', build_frame(ROLE_SLAVE, cmd, payload))
    return original_send(self, cmd, payload)

def receive(self, data, addr):
    record('pc_to_mock', data)
    return original_receive(self, data, addr)

mock_dut.MockDut._send_frame = send
mock_dut.MockDut.datagram_received = receive
port_base = ports['mock_udp'] - (ports['site'] - 1) * 100 - ports['slot']
sys.argv = ['mock_dut.py', '--sites', str(ports['site']), '--slots', str(ports['slot']), '--port-base', str(port_base), '--pass-rate', '1']
asyncio.run(mock_dut.main())
