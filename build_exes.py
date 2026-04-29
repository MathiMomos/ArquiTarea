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
    ("integracion/aplicar_bonos.py", "AplicarBonos"),
    ("integracion/preparar_concepto_bono.py", "PrepararBono"),
)


def built_app_path(name: str) -> Path:
    suffix = ".exe" if sys.platform.startswith("win") else ""
    return DIST_DIR / f"{name}{suffix}"


def build_app(entrypoint: str, name: str) -> None:
    is_console = "integracion/" in entrypoint

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
    ]
    if not is_console:
        command.append("--windowed")

    command.append(str(ROOT / entrypoint))
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

    for app in APPS:
        entrypoint = app[0]
        name = app[1]
        print(f"Generando {built_app_path(name).name}...")
        build_app(entrypoint, name)
        if len(app) == 4:
            source_db = app[2]
            target_db = app[3]
            copy_database(source_db, target_db)

    print("Build finalizado.")
    for app in APPS:
        print(built_app_path(app[1]))


if __name__ == "__main__":
    main()
