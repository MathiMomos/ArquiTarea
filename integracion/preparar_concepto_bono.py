import argparse
import sys
from pathlib import Path
from sqlite3 import Connection, connect


def resolve_database_paths(
    ventas_db_override: Path | None = None,
    rrhh_db_override: Path | None = None,
    use_dev: bool = False,
) -> tuple[Path, Path]:
    if ventas_db_override and rrhh_db_override:
        return ventas_db_override, rrhh_db_override

    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
        return root / "ventas.db", root / "rrhh.db"

    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"

    if use_dev:
        return repo_root / "sistema_ventas" / "ventas.db", repo_root / "sistema_rrhh" / "rrhh.db"

    return dist_dir / "ventas.db", dist_dir / "rrhh.db"


def parse_args() -> tuple[argparse.Namespace, Path, Path]:
    parser = argparse.ArgumentParser(description="Preparar concepto de bono en RRHH")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Usar bases de datos de desarrollo",
    )
    parser.add_argument(
        "--ventas-db",
        type=Path,
        help="Ruta personalizada a la base de datos de ventas",
    )
    parser.add_argument(
        "--rrhh-db",
        type=Path,
        help="Ruta personalizada a la base de datos de RRHH",
    )

    args = parser.parse_args()

    ventas_override = Path(args.ventas_db) if args.ventas_db else None
    rrhh_override = Path(args.rrhh_db) if args.rrhh_db else None
    VENTAS_DB, RRHH_DB = resolve_database_paths(ventas_override, rrhh_override, args.dev)

    return args, VENTAS_DB, RRHH_DB


args, VENTAS_DB, RRHH_DB = parse_args()


BONUS_CONCEPT_CODE = "BONO_EXTRA"
BONUS_CONCEPT_NAME = "Bono extra"


def connect_database(path: Path) -> Connection:
    if not path.exists():
        raise FileNotFoundError(f"No existe la base de datos: {path}")

    connection = connect(path)
    connection.row_factory = Connection.row_factory
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def register_bonus_concept(hr_connection: Connection) -> None:
    hr_connection.execute(
        """
        INSERT OR IGNORE INTO conceptos_pago (codigo, nombre, tipo, activo)
        VALUES (?, ?, 'ingreso', 1)
        """,
        (BONUS_CONCEPT_CODE, BONUS_CONCEPT_NAME),
    )


def main() -> None:
    print(f"[INFO] RRHH DB: {RRHH_DB}")

    with connect_database(RRHH_DB) as connection:
        register_bonus_concept(connection)
        connection.commit()

    print(f"Concepto {BONUS_CONCEPT_CODE} disponible en {RRHH_DB}")


if __name__ == "__main__":
    main()