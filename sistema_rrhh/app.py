from __future__ import annotations

import argparse
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).with_name("rrhh.db")
PAYMENT_DAY = 15

DEMO_TRABAJADORES = (
    ("E001", "Ana Lopez", 2500.00, 1),
    ("E002", "Bruno Diaz", 2300.00, 1),
    ("E003", "Carla Perez", 2800.00, 1),
    ("E004", "Diego Rojas", 2200.00, 1),
    ("E010", "Luisa Campos", 2100.00, 1),
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


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS trabajadores (
            codigo_empleado TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            sueldo_base REAL NOT NULL CHECK (sueldo_base >= 0),
            activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_codigo TEXT NOT NULL,
            periodo TEXT NOT NULL,
            fecha_pago TEXT NOT NULL,
            sueldo_base REAL NOT NULL CHECK (sueldo_base >= 0),
            bono_extra REAL NOT NULL DEFAULT 0 CHECK (bono_extra >= 0),
            pago_final REAL NOT NULL CHECK (pago_final >= 0),
            estado TEXT NOT NULL DEFAULT 'pendiente',
            UNIQUE (trabajador_codigo, periodo),
            FOREIGN KEY (trabajador_codigo) REFERENCES trabajadores(codigo_empleado)
        );

        CREATE INDEX IF NOT EXISTS idx_pagos_periodo_trabajador
        ON pagos(periodo, trabajador_codigo);
        """
    )
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
        INSERT OR IGNORE INTO trabajadores (codigo_empleado, nombre, sueldo_base, activo)
        VALUES (?, ?, ?, ?)
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
                sueldo_base,
                bono_extra,
                pago_final,
                estado
            ) VALUES (?, ?, ?, ?, 0, ?, 'pendiente')
            """,
            (
                worker["codigo_empleado"],
                period_date,
                payment_date,
                worker["sueldo_base"],
                worker["sueldo_base"],
            ),
        )
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
            p.sueldo_base,
            p.bono_extra,
            p.pago_final,
            p.estado
        FROM pagos p
        INNER JOIN trabajadores t ON t.codigo_empleado = p.trabajador_codigo
        WHERE p.periodo = ?
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
    print("codigo | nombre        | base    | bono    | final   | fecha pago  | estado")
    print("-------+---------------+---------+---------+---------+-------------+----------")
    for row in rows:
        print(
            f"{row['trabajador_codigo']:<6} | {row['nombre']:<13} | {row['sueldo_base']:>7.2f} | "
            f"{row['bono_extra']:>7.2f} | {row['pago_final']:>7.2f} | {row['fecha_pago']:<11} | {row['estado']}"
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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

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
