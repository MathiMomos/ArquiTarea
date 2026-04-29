import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def default_db_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().with_name("rrhh.db")
    return Path(__file__).with_name("rrhh.db")


DB_PATH = default_db_path()
PAYMENT_DAY = 15
BASE_CONCEPT_CODE = "SUELDO_BASE"
MOBILITY_CONCEPT_CODE = "MOVILIDAD"
FOOD_CONCEPT_CODE = "ALIMENTACION"
PENSION_CONCEPT_CODE = "DESCUENTO_AFP"
MOBILITY_AMOUNT = 180.00
FOOD_AMOUNT = 120.00
PENSION_RATE = 0.10

DEMO_TRABAJADORES = (
    ("E001", "Ana Lopez", 2500.00, 1),
    ("E002", "Bruno Diaz", 2300.00, 1),
    ("E003", "Carla Perez", 2800.00, 1),
    ("E004", "Diego Rojas", 2200.00, 1),
)

DEFAULT_PAYMENT_CONCEPTS = (
    (BASE_CONCEPT_CODE, "Sueldo base", "ingreso", 1),
    (MOBILITY_CONCEPT_CODE, "Movilidad", "ingreso", 1),
    (FOOD_CONCEPT_CODE, "Alimentacion", "ingreso", 1),
    (PENSION_CONCEPT_CODE, "Descuento AFP", "descuento", 1),
)


def previous_month_period(reference: date | None = None) -> str:
    reference = reference or date.today()
    first_day = reference.replace(day=1)
    previous_month_last_day = first_day - timedelta(days=1)
    return previous_month_last_day.strftime("%Y-%m")


def current_period(reference: date | None = None) -> str:
    reference = reference or date.today()
    return reference.strftime("%Y-%m")


def validate_period(period: str) -> str:
    try:
        datetime.strptime(period, "%Y-%m")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("El periodo debe tener formato YYYY-MM.") from exc
    return period


def period_start_date(period: str) -> str:
    year, month = map(int, period.split("-"))
    return date(year, month, 1).isoformat()


def payment_date_for_period(period: str) -> str:
    year, month = map(int, period.split("-"))
    return date(year, month, PAYMENT_DAY).isoformat()


def payment_date_for_period_date(period_date: str) -> str:
    return payment_date_for_period(period_date[:7])


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def create_workers_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS trabajadores (
            codigo_empleado TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            sueldo_base REAL NOT NULL CHECK (sueldo_base >= 0),
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
        )
        """
    )


def create_payment_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_codigo TEXT NOT NULL,
            periodo TEXT NOT NULL,
            fecha_pago TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            UNIQUE (trabajador_codigo, periodo),
            FOREIGN KEY (trabajador_codigo) REFERENCES trabajadores(codigo_empleado)
        );

        CREATE TABLE IF NOT EXISTS conceptos_pago (
            codigo TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('ingreso', 'descuento')),
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS pago_conceptos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pago_id INTEGER NOT NULL,
            concepto_codigo TEXT NOT NULL,
            monto REAL NOT NULL CHECK (monto >= 0),
            UNIQUE (pago_id, concepto_codigo),
            FOREIGN KEY (pago_id) REFERENCES pagos(id) ON DELETE CASCADE,
            FOREIGN KEY (concepto_codigo) REFERENCES conceptos_pago(codigo)
        );

        CREATE INDEX IF NOT EXISTS idx_pagos_periodo_trabajador
        ON pagos(periodo, trabajador_codigo);

        CREATE INDEX IF NOT EXISTS idx_pago_conceptos_pago
        ON pago_conceptos(pago_id);

        CREATE INDEX IF NOT EXISTS idx_pago_conceptos_concepto
        ON pago_conceptos(concepto_codigo);
        """
    )


def ensure_payment_concept(
    connection: sqlite3.Connection,
    code: str,
    name: str,
    kind: str = "ingreso",
    active: int = 1,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO conceptos_pago (codigo, nombre, tipo, activo)
        VALUES (?, ?, ?, ?)
        """,
        (code, name, kind, active),
    )


def ensure_default_payment_concepts(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO conceptos_pago (codigo, nombre, tipo, activo)
        VALUES (?, ?, ?, ?)
        """,
        DEFAULT_PAYMENT_CONCEPTS,
    )


def default_payment_breakdown(sueldo_base: float) -> tuple[tuple[str, float], ...]:
    rounded_base = round(sueldo_base, 2)
    return (
        (BASE_CONCEPT_CODE, rounded_base),
        (MOBILITY_CONCEPT_CODE, MOBILITY_AMOUNT),
        (FOOD_CONCEPT_CODE, FOOD_AMOUNT),
        (PENSION_CONCEPT_CODE, round(rounded_base * PENSION_RATE, 2)),
    )


def sync_payment_breakdown(connection: sqlite3.Connection, payment_id: int, sueldo_base: float) -> None:
    for concept_code, amount in default_payment_breakdown(sueldo_base):
        connection.execute(
            """
            INSERT INTO pago_conceptos (pago_id, concepto_codigo, monto)
            VALUES (?, ?, ?)
            ON CONFLICT(pago_id, concepto_codigo) DO UPDATE SET monto = excluded.monto
            """,
            (payment_id, concept_code, amount),
        )


def has_legacy_payment_schema(connection: sqlite3.Connection) -> bool:
    if not table_exists(connection, "pagos"):
        return False
    return "sueldo_base" in table_columns(connection, "pagos")


def migrate_legacy_payment_schema(connection: sqlite3.Connection) -> None:
    legacy_rows = connection.execute(
        """
        SELECT id, trabajador_codigo, periodo, fecha_pago, sueldo_base, estado
        FROM pagos
        ORDER BY id
        """
    ).fetchall()

    connection.execute("ALTER TABLE pagos RENAME TO pagos_legacy")
    create_payment_schema(connection)
    ensure_default_payment_concepts(connection)

    for row in legacy_rows:
        normalized_period = row["periodo"] if len(row["periodo"]) == 10 else period_start_date(row["periodo"])
        payment_date = payment_date_for_period_date(normalized_period)
        connection.execute(
            """
            INSERT INTO pagos (id, trabajador_codigo, periodo, fecha_pago, estado)
            VALUES (?, ?, ?, ?, ?)
            """,
            (row["id"], row["trabajador_codigo"], normalized_period, payment_date, row["estado"]),
        )
        sync_payment_breakdown(connection, row["id"], row["sueldo_base"])

    connection.execute("DROP TABLE pagos_legacy")


def create_schema(connection: sqlite3.Connection) -> None:
    create_workers_schema(connection)
    if has_legacy_payment_schema(connection):
        migrate_legacy_payment_schema(connection)
    create_payment_schema(connection)
    ensure_default_payment_concepts(connection)
    normalize_payment_periods(connection)
    connection.commit()


def normalize_payment_periods(connection: sqlite3.Connection) -> None:
    legacy_rows = connection.execute(
        """
        SELECT id, periodo, fecha_pago
        FROM pagos
        WHERE length(periodo) = 7 OR substr(fecha_pago, 1, 7) != substr(periodo, 1, 7)
        """
    ).fetchall()

    for row in legacy_rows:
        normalized_period = row["periodo"] if len(row["periodo"]) == 10 else period_start_date(row["periodo"])
        connection.execute(
            "UPDATE pagos SET periodo = ?, fecha_pago = ? WHERE id = ?",
            (normalized_period, payment_date_for_period_date(normalized_period), row["id"]),
        )


def insert_demo_data(connection: sqlite3.Connection, period: str) -> tuple[int, int]:
    create_schema(connection)
    connection.executemany(
        """
        INSERT INTO trabajadores (codigo_empleado, nombre, sueldo_base, activo)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(codigo_empleado) DO UPDATE SET
            nombre = excluded.nombre,
            sueldo_base = excluded.sueldo_base,
            activo = excluded.activo
        """,
        DEMO_TRABAJADORES,
    )
    payments_created = generate_payments(connection, period)
    return len(DEMO_TRABAJADORES), payments_created


def generate_payments(connection: sqlite3.Connection, period: str) -> int:
    create_schema(connection)
    period_date = period_start_date(period)
    payment_date = payment_date_for_period(period)
    workers = connection.execute(
        """
        SELECT codigo_empleado, sueldo_base
        FROM trabajadores
        WHERE activo = 1
        ORDER BY codigo_empleado
        """
    ).fetchall()

    created = 0
    for worker in workers:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO pagos (
                trabajador_codigo,
                periodo,
                fecha_pago,
                estado
            ) VALUES (?, ?, ?, 'pendiente')
            """,
            (
                worker["codigo_empleado"],
                period_date,
                payment_date,
            ),
        )
        payment_row = connection.execute(
            """
            SELECT id
            FROM pagos
            WHERE trabajador_codigo = ? AND periodo = ?
            """,
            (worker["codigo_empleado"], period_date),
        ).fetchone()
        sync_payment_breakdown(connection, payment_row["id"], worker["sueldo_base"])
        created += cursor.rowcount

    connection.commit()
    return created


def fetch_workers(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT codigo_empleado, nombre, sueldo_base, activo
        FROM trabajadores
        ORDER BY codigo_empleado
        """
    ).fetchall()


def fetch_payments(connection: sqlite3.Connection, period: str) -> list[sqlite3.Row]:
    period_date = period_start_date(period)
    return connection.execute(
        """
        SELECT
            p.id,
            p.trabajador_codigo,
            t.nombre,
            p.periodo,
            p.fecha_pago,
            ROUND(COALESCE(SUM(CASE WHEN c.tipo = 'ingreso' THEN pc.monto ELSE -pc.monto END), 0), 2) AS monto_pagar,
            p.estado
        FROM pagos p
        INNER JOIN trabajadores t ON t.codigo_empleado = p.trabajador_codigo
        LEFT JOIN pago_conceptos pc ON pc.pago_id = p.id
        LEFT JOIN conceptos_pago c ON c.codigo = pc.concepto_codigo
        WHERE p.periodo = ?
        GROUP BY p.id, p.trabajador_codigo, t.nombre, p.periodo, p.fecha_pago, p.estado
        ORDER BY p.trabajador_codigo
        """,
        (period_date,),
    ).fetchall()


def print_workers(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No hay trabajadores registrados en RRHH.")
        return

    print("codigo | nombre        | sueldo | activo")
    print("-------+---------------+--------+-------")
    for row in rows:
        active = "si" if row["activo"] else "no"
        print(f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['sueldo_base']:>6.2f} | {active}")


def print_payments(rows: list[sqlite3.Row], period: str) -> None:
    if not rows:
        print(f"No hay pagos para el periodo {period}.")
        return

    print(f"Pagos RRHH para el periodo {period}")
    print("codigo | nombre        | monto pagar | fecha pago  | estado")
    print("-------+---------------+-------------+-------------+----------")
    for row in rows:
        print(
            f"{row['trabajador_codigo']:<6} | {row['nombre']:<13} | {row['monto_pagar']:>11.2f} | "
            f"{row['fecha_pago']:<11} | {row['estado']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sistema aislado de RRHH.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Crea el esquema SQLite de RRHH.")

    seed_parser = subparsers.add_parser("seed-demo", help="Carga trabajadores y pagos demo.")
    seed_parser.add_argument("--periodo", type=validate_period, default=current_period())

    payments_parser = subparsers.add_parser("generar-pagos", help="Genera pagos pendientes para un periodo.")
    payments_parser.add_argument("--periodo", type=validate_period, default=current_period())

    list_payments = subparsers.add_parser("listar-pagos", help="Lista pagos de un periodo.")
    list_payments.add_argument("--periodo", type=validate_period, default=current_period())

    workers_parser = subparsers.add_parser("listar-trabajadores", help="Lista trabajadores de RRHH.")
    workers_parser.set_defaults(command="listar-trabajadores")

    subparsers.add_parser("ui", help="Abre la interfaz de escritorio del sistema de RRHH.")

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
        create_schema(connection)

        if args.command == "init-db":
            print(f"Base de RRHH inicializada en {DB_PATH}")
            return

        if args.command == "seed-demo":
            workers_loaded, payments_created = insert_demo_data(connection, args.periodo)
            print(
                f"Trabajadores demo disponibles: {workers_loaded}. "
                f"Pagos generados para {args.periodo}: {payments_created}."
            )
            return

        if args.command == "generar-pagos":
            payments_created = generate_payments(connection, args.periodo)
            print(f"Pagos generados para {args.periodo}: {payments_created}.")
            return

        if args.command == "listar-pagos":
            print_payments(fetch_payments(connection, args.periodo), args.periodo)
            return

        if args.command == "listar-trabajadores":
            print_workers(fetch_workers(connection))
            return


if __name__ == "__main__":
    main()
