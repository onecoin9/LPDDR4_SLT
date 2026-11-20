"""运行实际 REST 函数，隔离模块装配以避免真实配置和设备 I/O。"""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from app.manual import ManualDebugError


def api(name, **context):
    tree = ast.parse((Path(__file__).parents[1] / 'app' / 'main.py').read_text(encoding='utf-8-sig'))
    fn = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    fn.decorator_list = []
    scope = dict(Body=lambda *a, **kw: None, HTTPException=HTTPException,
                 ManualDebugError=ManualDebugError, **context)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'main.py', 'exec'), scope)
    return scope[name]


class StateApi(unittest.IsolatedAsyncioTestCase):
    async def test_non_boolean_power_requests_rejected_without_commands(self):
        for name in ('api_manual_power', 'api_manual_power_all'):
            for on in ('false', 0, 1, None, [], {}):
                with self.subTest(name=name, on=on):
                    fn = api(name)
                    with self.assertRaises(HTTPException) as error:
                        await fn({'dut': 1, 'on': on})
                    self.assertEqual(error.exception.status_code, 400)

    async def test_mapping_change_while_powered_rejected(self):
        md = SimpleNamespace(run_mode='full_run', board_host='192.0.2.1', dut_lines=[4],
                             dut_channels=[5], _power={1: True}, log_dir_abs=lambda: 'log')
        runner = SimpleNamespace(power_lock=asyncio.Lock())
        fn = api('api_manual_settings_save', mdbg=md, runner=runner)
        for body in ({'boardHost': '192.0.2.2'}, {'dutChannels': [6]}, {'dut_lines': [3]}):
            with self.assertRaises(HTTPException) as error: await fn(body)
            self.assertEqual(error.exception.status_code, 400)

    async def test_same_mapping_and_cfg_save_does_not_close_active_log(self):
        changed = []
        md = SimpleNamespace(run_mode='full_run', board_host='192.0.2.1', dut_lines=[4],
                             dut_channels=[5], _power={1: True}, log_dir_abs=lambda: 'log',
                             apply_settings=lambda body, path: body)
        async def io(fn, *args): return fn(*args)
        runner = SimpleNamespace(power_lock=asyncio.Lock(), _io=io)
        logch = SimpleNamespace(file_sink=SimpleNamespace(set_dir=lambda d: changed.append(d)))
        fn = api('api_manual_settings_save', mdbg=md, runner=runner, logch=logch,
                 CFG_PATH='unused', _push_manual_state=lambda: None)
        await fn({'boardHost': '192.0.2.1', 'cfgContent': 'new next-run cfg'})
        self.assertEqual(changed, [])
