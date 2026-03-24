# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MFClab."""

import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'ui' / 'mainwindow.ui'), 'ui'),
    ],
    hiddenimports=[
        'src',
        'src.main_window',
        'src.csv_loader',
        'src.signal_context',
        'src.filter_chain',
        'src.fft_engine',
        'src.param_form',
        'src.chain_card',
        'src.resources',
        'src.filters',
        'src.filters.base',
        'src.filters.moving_average',
        'src.filters.median',
        'src.filters.fir',
        'src.filters.iir_lpf',
        'src.filters.biquad_lowpass',
        'src.filters.critical_damped_lpf',
        'src.filters.lead_compensator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MFClab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
