# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import sys
stage = Path(os.environ['SLT_BUILD_STAGE'])
here = stage / 'desktop'
sys.path.insert(0, str(here))
from release_policy import HIDDEN_IMPORTS, EXCLUDES
backend = stage / 'backend'
assert not (backend / 'app/protocol.py').exists()
assert list((backend / 'app').glob('protocol*.pyd'))
a = Analysis([str(stage / 'desktop/desktop.py')],
    pathex=[str(backend), str(stage / 'desktop')], binaries=[], datas=[],
    hiddenimports=HIDDEN_IMPORTS, hookspath=[], hooksconfig={},
    runtime_hooks=[str(here / 'package_runtime_hook.py')],
    excludes=EXCLUDES, noarchive=False, optimize=2)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='LPDDR4x_SCADA_PYD',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LPDDR4x_SCADA_PYD')
