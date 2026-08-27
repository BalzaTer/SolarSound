# -*- mode: python ; coding: utf-8 -*-
#
# Spec PyInstaller pour SolarSound.
# A lancer DEPUIS LA RACINE DU PROJET (dossier contenant main.py),
# avec le venv du projet activé :
#
#   pyinstaller build\solarsound.spec --noconfirm
#
# (adapte le chemin "build\solarsound.spec" si tu le copies ailleurs)

import os

block_cipher = None

# Racine du projet = dossier qui contient main.py, icons/, solarsound.ico
PROJECT_ROOT = os.getcwd()

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, 'icons'), 'icons'),
        (os.path.join(PROJECT_ROOT, 'solarsound.ico'), '.'),
    ],
    hiddenimports=[
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'soundfile',
        'sounddevice',
        'mutagen',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tests',
        'numpy.random',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Les traductions Qt ne sont pas utilisées par SolarSound et ajoutent plusieurs
# Mo de fichiers à extraire dans le mode onefile.
a.datas = [
    entry for entry in a.datas
    if 'translations' not in entry[0].replace('\\', '/')
    and not entry[0].replace('\\', '/').startswith('numpy-')
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='SolarSound',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX corrompt certaines DLL Qt6 -> erreur "failed to allocate
                        # temporary input buffer" au lancement du .exe (bug connu
                        # PyInstaller + UPX + PyQt6). On désactive complètement UPX.
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # pas de fenêtre console (appli graphique)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'solarsound.ico'),
)
