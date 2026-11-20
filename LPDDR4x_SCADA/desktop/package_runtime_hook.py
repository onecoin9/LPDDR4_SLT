"""Frozen startup support and isolated acceptance mode for the release package."""
import os
import sys

# Windowed PyInstaller executables have no stdout/stderr; uvicorn formatters use them.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

if '--verify-package' in sys.argv:
    import argparse
    import hashlib
    import json
    from pathlib import Path
    import threading
    import time
    import traceback

    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-package', action='store_true')
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--with-ui', action='store_true')
    opts = parser.parse_args()
    data = Path(opts.data_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    evidence_file = data / 'package-evidence.json'
    log = (data / 'package-process.log').open('w', encoding='utf-8', buffering=1)
    sys.stdout = sys.stderr = log
    try:
        import yaml
        cfg = yaml.safe_load((data / 'config.yaml').read_text(encoding='utf-8'))
        for key in ('manual_debug', 'commboard', 'tempctrl', 'handler'):
            if (cfg.get(key) or {}).get('enabled'):
                raise ValueError(f'Verification requires {key}.enabled=false')
        if not isinstance(cfg.get('sites'), list):
            raise ValueError('Verification requires explicit mock sites')
        if not all(s['ip'] == '127.0.0.1' for site in cfg['sites'] for s in site.get('slots', [])):
            raise ValueError('Verification requires loopback-only DUT addresses')
        os.environ['SLT_DATA_DIR'] = str(data)
        exe_dir = Path(sys.executable).resolve().parent
        os.environ['SLT_FRONTEND_DIST'] = str(exe_dir / 'frontend_dist')
        import app.protocol as protocol
        from app import main
        # Always-on Handler remains functional, isolated to loopback in acceptance mode.
        if main.settings_store.error or main.handler.tx_host not in ('', '127.0.0.1', 'localhost'):
            raise ValueError('Verification requires valid loopback Handler settings')
        main.handler.rx_host = '127.0.0.1'
        import importlib
        protected = {}
        for module in ('app.protocol', 'app.license_core', 'app.license_machine', 'app.license_state', 'app.license_keys', 'app.license_container'):
            native = importlib.import_module(module)
            if not native.__file__.endswith('.pyd') or native.__doc__ is not None:
                raise RuntimeError('Protected module missing or docstring retained: ' + module)
            protected[module] = hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest()
        import uvicorn
        if not str(protocol.__file__).endswith('.pyd'):
            raise RuntimeError('Frozen protocol is not a pyd')
        if any(obj.__doc__ is not None for obj in (protocol, protocol.HsgCodec, protocol.HsgCodec.encode, protocol.HsgCodec.decode)):
            raise RuntimeError('Protocol docstrings were not stripped')
        raw = Path(protocol.__file__).read_bytes()
        evidence = {'frozen': bool(getattr(sys, 'frozen', False)), 'executable': sys.executable, 'pid': os.getpid(), 'python': sys.version, 'protocol_file': protocol.__file__, 'protocol_loader': type(protocol.__loader__).__name__, 'protocol_sha256': hashlib.sha256(raw).hexdigest(), 'hardware_enabled': {k: bool((main.CFG.get(k) or {}).get('enabled')) for k in ('manual_debug', 'commboard', 'tempctrl')}, 'handler_enabled': main.handler.enabled, 'data_dir': main.DATA_DIR, 'frontend_dist': str(exe_dir / 'frontend_dist'), 'stages': main.seq.stages, 'errors': [], 'docstrings_stripped': True}
        evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        evidence['protected_modules'] = protected
        server = uvicorn.Server(uvicorn.Config(main.app, host='127.0.0.1', port=opts.port, access_log=False, log_level='info'))
        window = None

        @main.app.get('/_package/info')
        async def package_info():
            return {**evidence, 'cfg_text': main.seq.cfg_text, 'stages': main.seq.stages}
        main.app.router.routes.insert(0, main.app.router.routes.pop())

        @main.app.post('/_package/stop')
        async def package_stop():
            server.should_exit = True
            if window is not None:
                threading.Thread(target=window.destroy, daemon=True).start()
            return {'ok': True}
        main.app.router.routes.insert(0, main.app.router.routes.pop())

        if opts.with_ui:
            import webview
            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()
            for _ in range(200):
                if server.started:
                    break
                time.sleep(0.1)
            if not server.started:
                raise RuntimeError('Packaged uvicorn startup timeout')
            window = webview.create_window('Package acceptance', f'http://127.0.0.1:{opts.port}', hidden=True, width=1100, height=700)

            def page_loaded():
                ui = {'success': False}
                try:
                    for _ in range(30):
                        value = window.evaluate_js("JSON.stringify({title:document.title,rootChildren:document.getElementById('root')?.children.length||0,textLength:document.body.innerText.length,url:location.href})")
                        ui = json.loads(value) if isinstance(value, str) else value
                        if ui.get('rootChildren', 0) > 0 and ui.get('textLength', 0) > 20:
                            window.evaluate_js("(document.querySelector('button[aria-label=\"软件授权\"]')||document.querySelector('button[aria-label=\"Software License\"]'))?.click()")
                            time.sleep(.3)
                            ui['license_dialog'] = bool(window.evaluate_js("!!document.querySelector('[role=dialog] input[type=file]') && document.body.innerText.includes('client_id')"))
                            if not ui['license_dialog']:
                                raise RuntimeError('License import dialog did not render')
                            ui['success'] = True
                            break
                        time.sleep(0.2)
                except Exception:
                    ui['exception'] = traceback.format_exc()
                (data / 'ui-evidence.json').write_text(json.dumps(ui, ensure_ascii=False, indent=2), encoding='utf-8')

            window.events.loaded += page_loaded
            webview.start(gui='edgechromium', private_mode=True)
            server.should_exit = True
            server_thread.join(timeout=10)
        else:
            server.run()
        evidence['clean_shutdown'] = True
        evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        log.flush()
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        failed = {'success': False, 'exception': traceback.format_exc()}
        evidence_file.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding='utf-8')
        log.write(failed['exception'])
        log.flush()
        raise SystemExit(1)
