"""Verify the frozen EXE with isolated mock data, WebView2, and relocation."""
import asyncio
import argparse
import datetime
import shutil
import socket
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import urllib.request
import websockets

parser = argparse.ArgumentParser()
parser.add_argument('--package', required=True)
parser.add_argument('--build-report', help='Internal build report outside the customer package')
parser.add_argument('--without-ui', action='store_true')
parser.add_argument('--license-file', help='本机有效授权，仅用于隔离冒烟，不含管理端私钥')
parser.add_argument('--qa-key-file', help='管理端密钥只由独立QA进程使用，绝不传给EXE')
opts = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
package = Path(opts.package).resolve()
exe = package / 'LPDDR4x_SCADA_PYD.exe'
assert exe.is_file()
build_report_path = Path(opts.build_report).resolve() if opts.build_report else package / 'BUILD_REPORT.json'
build_report = json.loads(build_report_path.read_text(encoding='utf-8'))
qa = repo / 'desktop/build' / ('qa_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
qa.mkdir(parents=True, exist_ok=False)
(qa / 'logs').mkdir()
fixture = qa / 'fixture'
(fixture / 'app').mkdir(parents=True)
for name in ('__init__.py', 'cfg.py', 'protocol.py'):
    shutil.copy2(repo / 'backend/app' / name, fixture / 'app' / name)
shutil.copy2(repo / 'backend/mock_dut.py', fixture / 'mock_dut.py')
sys.path.insert(0, str(repo / 'backend'))
from app.localdata import init_mock_data

def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
for site in range(351, 401):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('0.0.0.0', 21000 + (site - 1) * 100 + 1))
        break
    except OSError:
        continue
else:
    raise RuntimeError('No isolated DUT port')
ports = {'site': site, 'slot': 1, 'mock_udp': free_port(socket.SOCK_DGRAM),
         'log_udp': free_port(socket.SOCK_DGRAM), 'http': free_port(socket.SOCK_STREAM)}
init_mock_data(str(qa / 'runtime'), site=site, mock_port=ports['mock_udp'], log_port=ports['log_udp'])
import yaml
mock_cfg_path = qa / 'runtime/config.yaml'
mock_cfg = yaml.safe_load(mock_cfg_path.read_text(encoding='utf-8'))
ports['handler'] = free_port(socket.SOCK_STREAM)
mock_cfg['handler'].update(rx_port=ports['handler'], tx_host='127.0.0.1')
mock_cfg_path.write_text(yaml.safe_dump(mock_cfg), encoding='utf-8')
(qa / 'ports.json').write_text(json.dumps(ports), encoding='utf-8')
base = f"http://127.0.0.1:{ports['http']}"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
children = []
handles = []
env = os.environ.copy()
env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='', PYTHONUNBUFFERED='1')
result = {'success': False, 'package': str(package), 'ports': ports}

def http(path, body=None, headers=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json', **(headers or {})})
    with opener.open(req, timeout=4) as response:
        return json.load(response)

def start(cmd, name):
    h = (qa / 'logs' / name).open('wb')
    handles.append(h)
    p = subprocess.Popen(cmd, cwd=qa, env=env, stdin=subprocess.DEVNULL, stdout=h, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    children.append(p)
    return p

def select_dut(snapshot):
    site = next(s for s in snapshot['sites'] if s['id'] == ports['site'])
    return next(d for d in site['duts'] if d['slot'] == ports['slot'])

async def flow():
    backend = start([str(exe), '--verify-package', '--data-dir', str(qa / 'runtime'), '--port', str(ports['http'])] + ([] if opts.without_ui else ['--with-ui']), 'exe-launch.log')
    deadline = time.monotonic() + 45
    while True:
        assert backend.poll() is None, 'Packaged executable exited during startup'
        try:
            result['startup'] = http('/_package/info')
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            await asyncio.sleep(0.2)
    assert result['startup']['frozen'] is True
    assert result['startup']['protocol_file'].endswith('.pyd')
    assert result['startup']['protocol_sha256'] == build_report['pyd_sha256']
    assert result['startup']['protected_modules'] == build_report['protected_modules']
    assert not any(result['startup']['hardware_enabled'].values())
    assert result['startup']['handler_enabled'] is True
    missing = http('/api/license/status')
    assert missing['state'] == 'missing' and not missing['allowedToStart']
    license_file = Path(opts.license_file) if opts.license_file else package / 'license/license.lic'
    if not license_file.is_file():
        raise FileNotFoundError('Smoke requires a valid license for this Windows machine')
    result['license_missing_ui_started'] = True
    with opener.open(base + '/', timeout=4) as response:
        html = response.read().decode('utf-8')
    assert 'assets/index-' in html
    result['frontend_http_ok'] = True
    deadline = time.monotonic() + 35
    while not opts.without_ui and not (qa / 'runtime/ui-evidence.json').exists():
        assert backend.poll() is None, 'Packaged UI exited during startup'
        assert time.monotonic() < deadline, 'Hidden WebView2 page never finished loading'
        await asyncio.sleep(0.3)
    result['ui'] = {'success': None, 'skipped': True} if opts.without_ui else json.loads((qa / 'runtime/ui-evidence.json').read_text(encoding='utf-8'))
    if not opts.without_ui:
        assert result['ui']['success'], result['ui']
    deadline = time.monotonic() + 5
    settings_state = http('/api/settings')
    while not opts.without_ui and settings_state['settings']['browserMigrationPending']:
        assert time.monotonic() < deadline, 'Browser settings migration did not complete'
        await asyncio.sleep(.1)
        settings_state = http('/api/settings')
    assert settings_state['valid'] and settings_state['handlerStatus']['enabled']
    assert settings_state['handlerStatus']['running']
    assert 'enabled' not in settings_state['settings']['handler']
    reply = http('/api/settings', {'basic': {'theme': 'light'}}, {'If-Match': settings_state['revision']})
    assert reply['ok'] and json.loads((qa / 'runtime/settings.json').read_text(encoding='utf-8'))['basic']['theme'] == 'light'
    alternate = qa / 'runtime/selected_settings.json'
    alternate.write_text(json.dumps(reply['settings']), encoding='utf-8')
    selected = http('/api/settings/select', {'path': str(alternate)})
    assert selected['path'] == str(alternate) and selected['settings'] == reply['settings']
    assert json.loads((qa / 'runtime/.settings.active').read_text(encoding='utf-8')) == alternate.name
    reader, writer = await asyncio.open_connection('127.0.0.1', ports['handler'])
    writer.write(b'{"method":"getversion","data":{}}'); await writer.drain()
    response = json.loads(await asyncio.wait_for(reader.read(4096), 3))
    assert response['status'] == 'success'
    writer.close(); await writer.wait_closed()
    result['unified_settings'] = {'single_json': True, 'selection_persisted': True, 'handler_listening': True}
    mock = start([sys.executable, '-B', str(repo / 'desktop/mock_package.py'), '--qa', str(qa)], 'mock-process.log')
    deadline = time.monotonic() + 12
    while True:
        assert mock.poll() is None
        dut = select_dut(http('/api/duts'))
        if dut['connected']:
            break
        assert time.monotonic() < deadline, 'Mock did not become online'
        await asyncio.sleep(0.2)
    profile = {'name': 'PACK-PYD-16Gb', 'rankEnabled': True, 'rankCapacityGb': [1, 0], 'channels': {'ch1': True, 'ch2': True}, 'pl1Enabled': True, 'pl2Enabled': True, 'params': [{'id': 1, 'name': 'VDD1(mV)', 'value': '1950', 'checked': True}], 'pl2': {'patterns': {'default': [{'name': 'test_random_value', 'checked': True}]}}, 'mr': {'ch1': [], 'ch2': []}}
    cfg = {'product': profile['name'], 'workOrder': 'PACK-PYD', 'lotNo': time.strftime('%H%M%S'), 'operator': 'isolated-package-qa', 'profile': profile, 'ioControl': {'action': 'none'}}
    result['config_response'] = http('/api/config', cfg)
    assert result['config_response']['ok']
    try:
        http('/api/test/start', {'site': ports['site'], 'slots': [1]})
        raise AssertionError('Unlicensed start accepted')
    except urllib.error.HTTPError as denied:
        assert denied.code == 403
        result['unlicensed_start_blocked'] = True
    assert http('/api/test/stop', {'site': ports['site'], 'slots': [1]})['stopped'] == []
    result['license'] = http('/api/license/import', {'content': license_file.read_text(encoding='utf-8')})
    assert result['license']['allowedToStart']
    armored_text = license_file.read_text(encoding='utf-8')
    assert armored_text.startswith('SLT2.')
    # 篡改装甲（翻转一个 base64 字符）与明文 JSON（v1 已废止）都必须被拒
    flip = 'A' if armored_text[30] != 'A' else 'B'
    tampered_armored = armored_text[:30] + flip + armored_text[31:]
    for bad_content in (tampered_armored, '{"format":"tampered"}'):
        try:
            http('/api/license/import', {'content': bad_content})
            raise AssertionError('Invalid import accepted')
        except urllib.error.HTTPError as denied:
            assert denied.code == 400
    assert http('/api/license/status')['allowedToStart']
    result['failed_import_kept_old_license'] = True
    result['configured'] = http('/_package/info')
    assert result['configured']['stages'] == ['PL', 'LK', 'APK']
    batch = result['config_response']['batch']
    messages = []
    done = None
    t0 = time.monotonic()
    async with websockets.connect(base.replace('http:', 'ws:') + '/ws', proxy=None) as ws:
        if opts.qa_key_file:
            import base64
            sys.path.insert(0, str(repo))
            from cryptography.hazmat.primitives import serialization
            from licensing_tools.license_container import KIND_LICENSE, open_container, seal
            from licensing_tools.private_key import load_key
            key_id, signing_key = load_key(opts.qa_key_file)
            public_b64 = base64.b64encode(signing_key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode('ascii')
            short = json.loads(open_container(KIND_LICENSE, armored_text.encode('ascii'), [public_b64]))
            assert short['keyId'] == key_id
            stamp = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
            short['payload'].update(issuedAt=stamp.isoformat(), notBefore=stamp.isoformat(), expiresAt=(stamp + datetime.timedelta(seconds=5)).isoformat())
            del short['signature']
            signature = signing_key.sign(json.dumps(short, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())
            short['signature'] = base64.b64encode(signature).decode()
            short_armored = seal(KIND_LICENSE, json.dumps(short, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode(), public_b64)
            assert http('/api/license/import', {'content': short_armored.decode('ascii')})['allowedToStart']
        result['start_response'] = http('/api/test/start', {'site': ports['site'], 'slots': [1]})
        assert result['start_response']['started'] == [[ports['site'], 1]]
        deadline = time.monotonic() + 110
        while time.monotonic() < deadline:
            assert backend.poll() is None and mock.poll() is None, 'Process exited during test'
            if opts.qa_key_file and time.monotonic() - t0 > 6 and 'expired_during_run' not in result:
                assert http('/api/license/status')['state'] == 'expired'
                assert select_dut(http('/api/duts'))['state'] == 'TESTING'
                result['expired_during_run'] = True
            try:
                obj = json.loads(await asyncio.wait_for(ws.recv(), timeout=1))
            except TimeoutError:
                continue
            for msg in (obj if isinstance(obj, list) else [obj]):
                messages.append(msg)
                if msg.get('type') == 'dut_result' and msg.get('site') == ports['site'] and msg.get('slot') == 1:
                    done = msg
            if done:
                break
    (qa / 'logs/websocket-messages.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf-8')
    assert done is not None and done['result'] == 'PASS' and done['failItem'] == '', done
    result['result_event'] = done
    result['elapsed_sec'] = round(time.monotonic() - t0, 3)
    await asyncio.sleep(0.5)
    result['final_dut'] = select_dut(http('/api/duts'))
    assert result['final_dut']['state'] == 'PASS'
    if opts.qa_key_file:
        assert result.get('expired_during_run'), 'Mock ended before expiry was exercised'
        try:
            http('/api/test/start', {'site': ports['site'], 'slots': [1]})
            raise AssertionError('New run accepted after expiry')
        except urllib.error.HTTPError as denied:
            assert denied.code == 403
            result['expired_new_run_blocked'] = True
    csv_paths = list((qa / 'runtime/records').glob(f'*/{batch}/summary.csv'))
    assert len(csv_paths) == 1
    with csv_paths[0].open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]['result'] == 'PASS' and rows[0]['fail_item'] == ''
    result['csv'] = {'path': str(csv_paths[0]), 'rows': rows}
    result['records_response'] = http(f'/api/records?date={csv_paths[0].parent.parent.name}&batch={batch}')
    assert result['records_response']['rows'] == rows
    assert http('/api/products')[profile['name']] == profile
    assert (qa / 'logs/transmitted.cfg').read_text(encoding='utf-8') == result['configured']['cfg_text']
    result['cfg_bytes_match'] = True
    wire = [json.loads(line) for line in (qa / 'logs/mock-wire.jsonl').read_text(encoding='utf-8').splitlines()]
    result['wire_counts'] = dict(Counter(x['direction'] + ':' + str(x['cmd']) for x in wire))
    steps = sorted({m.get('step') for m in messages if m.get('type') == 'dut_status' and m.get('state') == 'TESTING'})
    assert {'pl_check', 'lk_pattern', 'apk_memtester'}.issubset(steps)
    result['steps'] = steps
    result['error_logs'] = [m for m in messages if m.get('type') == 'log' and m.get('level') == 'ERROR']
    assert not result['error_logs'], result['error_logs']
    result['success'] = True

try:
    asyncio.run(flow())
except Exception:
    result['exception'] = traceback.format_exc()
finally:
    try:
        http('/_package/stop', {})
    except Exception:
        pass
    for i, p in enumerate(children):
        if p.poll() is None:
            try:
                if i == 0:
                    p.wait(timeout=12)
                else:
                    p.terminate()
                    p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=3)
    result['processes'] = [{'pid': p.pid, 'exit_code': p.returncode} for p in children]
    if children and children[0].returncode != 0:
        result['success'] = False
    for h in handles:
        h.close()
    (qa / 'logs/package-smoke-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: result.get(key) for key in ('success', 'elapsed_sec', 'ui', 'result_event', 'wire_counts', 'error_logs', 'exception', 'processes')}, ensure_ascii=False), flush=True)
if result['success']:
    import yaml
    blocked_data = qa / 'blocked_runtime'
    blocked_data.mkdir()
    blocked_cfg = yaml.safe_load((qa / 'runtime/config.yaml').read_text(encoding='utf-8'))
    blocked_cfg['handler'] = {'enabled': True, 'host': '127.0.0.1', 'tx_host': '127.0.0.1'}
    (blocked_data / 'config.yaml').write_text(yaml.safe_dump(blocked_cfg), encoding='utf-8')
    blocked = subprocess.run([str(exe), '--verify-package', '--data-dir', str(blocked_data), '--port', str(free_port(socket.SOCK_STREAM))],
        cwd=qa, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    result['hardware_guard'] = {'success': blocked.returncode == 1, 'exit_code': blocked.returncode}
    if blocked.returncode != 1:
        raise RuntimeError('Optimized EXE accepted hardware-enabled verification data')
    relocated = qa / 'relocated_package'
    shutil.copytree(package, relocated)
    relocation_data = qa / 'relocation_runtime'
    relocation_data.mkdir()
    shutil.copy2(qa / 'runtime/config.yaml', relocation_data / 'config.yaml')
    new_port = free_port(socket.SOCK_STREAM)
    new_base = f'http://127.0.0.1:{new_port}'
    relocated_exe = relocated / exe.name
    proc = subprocess.Popen([str(relocated_exe), '--verify-package', '--data-dir', str(relocation_data), '--port', str(new_port)],
        cwd=qa, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 30
        while True:
            assert proc.poll() is None, 'Relocated EXE exited early'
            try:
                with opener.open(new_base + '/_package/info', timeout=2) as response:
                    relocated_info = json.load(response)
                break
            except OSError:
                assert time.monotonic() < deadline
                time.sleep(0.2)
        assert Path(relocated_info['protocol_file']).is_relative_to(relocated)
        assert relocated_info['protocol_sha256'] == build_report['pyd_sha256']
        assert relocated_info['docstrings_stripped']
        with opener.open(new_base + '/', timeout=3) as response:
            assert b'assets/index-' in response.read()
        result['relocation'] = {'success': True, 'info': relocated_info}
    except Exception:
        result['success'] = False
        result['relocation'] = {'success': False, 'exception': traceback.format_exc()}
    finally:
        try:
            req = urllib.request.Request(new_base + '/_package/stop', data=b'{}', headers={'Content-Type': 'application/json'})
            opener.open(req, timeout=3).close()
            proc.wait(timeout=10)
        except Exception:
            proc.kill(); proc.wait(timeout=3)
        result['relocation_exit_code'] = proc.returncode
        result['success'] = result['success'] and proc.returncode == 0
    (qa / 'logs/package-smoke-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
if result['success']:
    build_report.update(smoke_verified=True, ui_verified=not opts.without_ui, qa_dir=str(qa))
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'success': result['success'], 'relocation': result.get('relocation', {}).get('success'), 'qa': str(qa)}, ensure_ascii=False), flush=True)
sys.exit(0 if result['success'] else 1)
