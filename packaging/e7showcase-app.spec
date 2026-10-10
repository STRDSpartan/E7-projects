# PyInstaller : application de bureau E7 Showcase (dossier autonome, sans Python à installer).
#   pyinstaller packaging/e7showcase-app.spec --noconfirm
# Résultat : dist/E7Showcase/E7Showcase(.exe)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src" / "e7showcase"

datas = [
    (str(ROOT / "config"), "e7showcase/_config"),
    (str(ROOT / "data" / "reference"), "e7showcase/_reference"),
    (str(SRC / "render" / "templates"), "e7showcase/render/templates"),
    (str(SRC / "app" / "ui.html"), "e7showcase/app"),
]
binaries = []
hiddenimports = ["e7showcase.scanner.hero_scanner", "e7showcase.vision.ocr"]
for package in ("rapidocr_onnxruntime", "onnxruntime"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
try:
    datas += collect_data_files("webview")
    hiddenimports += ["webview"]
except Exception:  # pywebview absent : l'application s'ouvre dans le navigateur
    pass

# Icône et informations de version (Propriétés → Détails de l'exécutable Windows)
ICON = ROOT / "packaging" / "windows" / "build" / "e7showcase.ico"
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
                StringStruct("CompanyName", "E7 Showcase (projet communautaire)"),
                StringStruct("FileDescription", "E7 Showcase — vitrines Epic Seven"),
                StringStruct("FileVersion", VERSION),
                StringStruct("ProductName", "E7 Showcase"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("OriginalFilename", "E7Showcase.exe"),
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
    name="E7Showcase",
    console=False,
    icon=str(ICON) if ICON.is_file() else None,
    version=version_file,
)
coll = COLLECT(exe, a.binaries, a.datas, name="E7Showcase")
