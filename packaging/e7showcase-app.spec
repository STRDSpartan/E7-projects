# PyInstaller : application de bureau Zealot (dossier autonome, sans Python à installer).
#   pyinstaller packaging/e7showcase-app.spec --noconfirm
# Résultat : dist/Zealot/Zealot(.exe)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src" / "e7showcase"

datas = [
    (str(ROOT / "config"), "e7showcase/_config"),
    (str(ROOT / "data" / "reference"), "e7showcase/_reference"),
    (str(SRC / "render" / "templates"), "e7showcase/render/templates"),
    (str(SRC / "app" / "ui.html"), "e7showcase/app"),
    (str(SRC / "app" / "anim.html"), "e7showcase/app"),
]
binaries = []
hiddenimports = ["e7showcase.scanner.hero_scanner", "e7showcase.vision.ocr", "httpx"]
for package in ("rapidocr_onnxruntime", "onnxruntime"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
# Fenêtre native : pywebview + pythonnet (WebView2 via .NET sous Windows)
for package in ("webview", "clr_loader", "pythonnet", "clr"):
    try:
        d, b, h = collect_all(package)
    except Exception:  # paquet absent sur cette plateforme
        continue
    datas += d
    binaries += b
    hiddenimports += h

# Icône et informations de version (Propriétés → Détails de l'exécutable Windows)
ICON = ROOT / "packaging" / "windows" / "build" / "zealot.ico"
VERSION = next(
    line.split('"')[1]
    for line in (SRC / "__init__.py").read_text(encoding="utf-8").splitlines()
    if line.startswith("__version__")
)
version_file = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct,
        VSVersionInfo,
    )

    nums = tuple(int(x) for x in (VERSION.split(".") + ["0", "0", "0"])[:4])
    version_file = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[
            StringFileInfo([StringTable("040C04B0", [
                StringStruct("CompanyName", "Shattered Spartan"),
                StringStruct("FileDescription", "Zealot — compagnon Epic Seven"),
                StringStruct("FileVersion", VERSION),
                StringStruct("ProductName", "Zealot"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("OriginalFilename", "Zealot.exe"),
                StringStruct("LegalCopyright", "MIT — projet non officiel"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
        ],
    )

a = Analysis(
    [str(SRC / "app" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["playwright", "discord", "mss", "keyboard", "tkinter", "matplotlib", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Zealot",
    console=False,
    icon=str(ICON) if ICON.is_file() else None,
    version=version_file,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Zealot")
