from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
WORK_DIR = ROOT / "build" / "pyinstaller"
SPEC_DIR = ROOT / "build" / "spec"

APPS = (
    ("ventas_desktop.py", "SistemaVentas", ROOT / "sistema_ventas" / "ventas.db", DIST_DIR / "ventas.db"),
    ("rrhh_desktop.py", "SistemaRRHH", ROOT / "sistema_rrhh" / "rrhh.db", DIST_DIR / "rrhh.db"),
)


def build_app(entrypoint: str, name: str) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        str(ROOT / entrypoint),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def copy_database(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copy2(source, target)


def main() -> None:
    try:
        __import__("PyInstaller")
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller no esta instalado. Ejecuta: python -m pip install pyinstaller"
        ) from exc

    DIST_DIR.mkdir(exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    for entrypoint, name, source_db, target_db in APPS:
        print(f"Generando {name}.exe...")
        build_app(entrypoint, name)
        copy_database(source_db, target_db)

    print("Build finalizado.")
    for _, name, _, _ in APPS:
        print(DIST_DIR / f"{name}.exe")


if __name__ == "__main__":
    main()
