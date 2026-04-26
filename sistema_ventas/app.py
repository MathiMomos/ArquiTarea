import argparse
import calendar
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def default_db_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().with_name("ventas.db")
    return Path(__file__).with_name("ventas.db")


DB_PATH = default_db_path()

DEMO_TRABAJADORES = (
    ("E001", "Ana Lopez", "Caja", 1),
    ("E002", "Bruno Diaz", "Caja", 1),
    ("E003", "Carla Perez", "Caja", 1),
    ("E004", "Diego Rojas", "Supervision", 1),
)

DEMO_VENTAS = {
    "E001": ((5, 4200.00), (12, 3900.00), (14, 4400.00)),
    "E002": ((7, 2800.00), (15, 2500.00), (22, 3000.00)),
    "E003": ((2, 6100.00), (8, 5400.00), (14, 6200.00)),
    "E004": ((10, 4000.00), (17, 3500.00), (25, 2500.00)),
}


def previous_month_period(reference: date | None = None) -> str:
    reference = reference or date.today()
    first_day = reference.replace(day=1)
    previous_month_last_day = first_day - timedelta(days=1)
    return previous_month_last_day.strftime("%Y-%m")


def validate_period(period: str) -> str:
    try:
        datetime.strptime(period, "%Y-%m")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("El periodo debe tener formato YYYY-MM.") from exc
    return period


def day_in_period(period: str, day: int) -> str:
    year, month = map(int, period.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    safe_day = min(day, last_day)
    return date(year, month, safe_day).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS trabajadores (
            codigo_empleado TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            area TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_codigo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            monto REAL NOT NULL CHECK (monto >= 0),
            FOREIGN KEY (trabajador_codigo) REFERENCES trabajadores(codigo_empleado)
        );

        CREATE INDEX IF NOT EXISTS idx_ventas_trabajador_fecha
        ON ventas(trabajador_codigo, fecha);
        """
    )
    connection.commit()


def insert_demo_data(connection: sqlite3.Connection, period: str) -> int:
    create_schema(connection)
    connection.executemany(
        """
        INSERT INTO trabajadores (codigo_empleado, nombre, area, activo)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(codigo_empleado) DO UPDATE SET
            nombre = excluded.nombre,
            area = excluded.area,
            activo = excluded.activo
        """,
        DEMO_TRABAJADORES,
    )

    existing_rows = connection.execute(
        "SELECT COUNT(*) AS total FROM ventas WHERE strftime('%Y-%m', fecha) = ?",
        (period,),
    ).fetchone()["total"]
    if existing_rows:
        connection.commit()
        return 0

    inserted = 0
    for worker_code, sales in DEMO_VENTAS.items():
        for day, amount in sales:
            connection.execute(
                "INSERT INTO ventas (trabajador_codigo, fecha, monto) VALUES (?, ?, ?)",
                (worker_code, day_in_period(period, day), amount),
            )
            inserted += 1

    connection.commit()
    return inserted


def register_sale(connection: sqlite3.Connection, worker_code: str, sale_date: str, amount: float) -> None:
    create_schema(connection)
    worker = connection.execute(
        "SELECT codigo_empleado FROM trabajadores WHERE codigo_empleado = ?",
        (worker_code,),
    ).fetchone()
    if worker is None:
        raise ValueError(f"El trabajador {worker_code} no existe en ventas.")

    connection.execute(
        "INSERT INTO ventas (trabajador_codigo, fecha, monto) VALUES (?, ?, ?)",
        (worker_code, sale_date, amount),
    )
    connection.commit()


def fetch_workers(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT codigo_empleado, nombre, area, activo
        FROM trabajadores
        ORDER BY codigo_empleado
        """
    ).fetchall()


def fetch_sales(connection: sqlite3.Connection, period: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT v.id, v.trabajador_codigo, t.nombre, v.fecha, v.monto
        FROM ventas v
        INNER JOIN trabajadores t ON t.codigo_empleado = v.trabajador_codigo
        WHERE strftime('%Y-%m', v.fecha) = ?
        ORDER BY v.fecha, v.trabajador_codigo, v.id
        """,
        (period,),
    ).fetchall()


def fetch_monthly_summary(connection: sqlite3.Connection, period: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            v.trabajador_codigo AS codigo_empleado,
            t.nombre,
            COUNT(*) AS cantidad_ventas,
            ROUND(SUM(v.monto), 2) AS total_ventas
        FROM ventas v
        INNER JOIN trabajadores t ON t.codigo_empleado = v.trabajador_codigo
        WHERE strftime('%Y-%m', v.fecha) = ?
        GROUP BY v.trabajador_codigo, t.nombre
        ORDER BY total_ventas DESC, codigo_empleado
        """,
        (period,),
    ).fetchall()


def print_workers(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No hay trabajadores registrados en ventas.")
        return

    print("codigo | nombre        | area                    | activo")
    print("-------+---------------+-------------------------+-------")
    for row in rows:
        active = "si" if row["activo"] else "no"
        print(f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['area']:<23} | {active}")


def print_sales(rows: list[sqlite3.Row], period: str) -> None:
    if not rows:
        print(f"No hay ventas registradas para el periodo {period}.")
        return

    print(f"Ventas del periodo {period}")
    print("id | codigo | nombre        | fecha       | monto")
    print("---+--------+---------------+-------------+----------")
    for row in rows:
        print(
            f"{row['id']:<2} | {row['trabajador_codigo']:<6} | {row['nombre']:<13} | "
            f"{row['fecha']:<11} | {row['monto']:>8.2f}"
        )


def print_summary(rows: list[sqlite3.Row], period: str) -> None:
    if not rows:
        print(f"No hay ventas para resumir en el periodo {period}.")
        return

    print(f"Resumen mensual de ventas para {period}")
    print("codigo | nombre        | ventas | total")
    print("-------+---------------+--------+-----------")
    for row in rows:
        print(
            f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['cantidad_ventas']:<6} | "
            f"{row['total_ventas']:>9.2f}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sistema aislado de ventas.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Crea el esquema SQLite de ventas.")

    seed_parser = subparsers.add_parser("seed-demo", help="Carga trabajadores y ventas demo.")
    seed_parser.add_argument("--periodo", type=validate_period, default=previous_month_period())

    worker_parser = subparsers.add_parser("listar-trabajadores", help="Lista trabajadores del sistema.")
    worker_parser.set_defaults(command="listar-trabajadores")

    sales_parser = subparsers.add_parser("listar-ventas", help="Lista ventas del periodo.")
    sales_parser.add_argument("--periodo", type=validate_period, default=previous_month_period())

    summary_parser = subparsers.add_parser("resumen-mensual", help="Resume ventas por trabajador.")
    summary_parser.add_argument("--periodo", type=validate_period, default=previous_month_period())

    register_parser = subparsers.add_parser("registrar-venta", help="Registra una venta manual.")
    register_parser.add_argument("--codigo", required=True)
    register_parser.add_argument("--fecha", required=True)
    register_parser.add_argument("--monto", type=float, required=True)

    subparsers.add_parser("ui", help="Abre la interfaz de escritorio del sistema de ventas.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ui":
        try:
            from .ui import launch_ui
        except ImportError:
            from ui import launch_ui

        launch_ui()
        return

    with connect() as connection:
        if args.command == "init-db":
            create_schema(connection)
            print(f"Base de ventas inicializada en {DB_PATH}")
            return

        if args.command == "seed-demo":
            inserted = insert_demo_data(connection, args.periodo)
            if inserted == 0:
                print(f"Ya existian ventas para {args.periodo}; no se duplicaron datos demo.")
            else:
                print(f"Se cargaron {inserted} ventas demo en {DB_PATH} para el periodo {args.periodo}.")
            return

        if args.command == "listar-trabajadores":
            print_workers(fetch_workers(connection))
            return

        if args.command == "listar-ventas":
            print_sales(fetch_sales(connection, args.periodo), args.periodo)
            return

        if args.command == "resumen-mensual":
            print_summary(fetch_monthly_summary(connection, args.periodo), args.periodo)
            return

        if args.command == "registrar-venta":
            register_sale(connection, args.codigo, args.fecha, args.monto)
            print(f"Venta registrada para {args.codigo} por {args.monto:.2f} el {args.fecha}.")
            return


if __name__ == "__main__":
    main()
