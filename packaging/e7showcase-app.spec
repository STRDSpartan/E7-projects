# PyInstaller : application de bureau E7 Showcase (dossier autonome, sans Python à installer).
#   pyinstaller packaging/e7showcase-app.spec --noconfirm
# Résultat : dist/E7Showcase/E7Showcase(.exe)
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
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="E7Showcase")
