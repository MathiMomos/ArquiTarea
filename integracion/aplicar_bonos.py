from __future__ import annotations

import argparse
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
VENTAS_DB_PATH = ROOT_DIR / "sistema_ventas" / "ventas.db"
RRHH_DB_PATH = ROOT_DIR / "sistema_rrhh" / "rrhh.db"
STATE_DB_PATH = Path(__file__).with_name("estado_integracion.db")

VENTAS_THRESHOLD = 10000.00
BONUS_AMOUNT = 500.00
EXECUTION_DAY = 15
EXECUTION_HOUR = 3
PAYMENT_DAY = 15
PAYMENT_HOUR = 22


def validate_period(period: str) -> str:
    try:
        datetime.strptime(period, "%Y-%m")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("El periodo debe tener formato YYYY-MM.") from exc
    return period


def parse_execution_datetime(raw_value: str | None) -> datetime:
    if raw_value is None:
        return datetime.now().replace(microsecond=0)

    candidates = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
    for pattern in candidates:
        try:
            parsed = datetime.strptime(raw_value, pattern)
            if pattern == "%Y-%m-%d":
                return parsed.replace(hour=EXECUTION_HOUR)
            return parsed
        except ValueError:
            continue

    raise argparse.ArgumentTypeError(
        "La fecha de ejecucion debe ser YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS."
    )


def previous_month_period(reference: date | datetime) -> str:
    if isinstance(reference, datetime):
        reference_date = reference.date()
    else:
        reference_date = reference
    first_day = reference_date.replace(day=1)
    previous_month_last_day = first_day - timedelta(days=1)
    return previous_month_last_day.strftime("%Y-%m")


def quote_path(path: Path) -> str:
    return str(path).replace("'", "''")


def connect() -> sqlite3.Connection:
    if not VENTAS_DB_PATH.exists():
        raise FileNotFoundError(f"No existe la base de ventas: {VENTAS_DB_PATH}")
    if not RRHH_DB_PATH.exists():
        raise FileNotFoundError(f"No existe la base de RRHH: {RRHH_DB_PATH}")

    connection = sqlite3.connect(STATE_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"ATTACH DATABASE '{quote_path(VENTAS_DB_PATH)}' AS ventas_db")
    connection.execute(f"ATTACH DATABASE '{quote_path(RRHH_DB_PATH)}' AS rrhh_db")
    return connection


def create_state_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS ejecuciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT NOT NULL,
            ejecutado_en TEXT NOT NULL,
            estado TEXT NOT NULL,
            detalle TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bonos_aplicados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT NOT NULL,
            trabajador_codigo TEXT NOT NULL,
            ventas_totales REAL NOT NULL,
            bono REAL NOT NULL,
            aplicado_en TEXT NOT NULL,
            UNIQUE (periodo, trabajador_codigo)
        );

        CREATE INDEX IF NOT EXISTS idx_bonos_periodo
        ON bonos_aplicados(periodo, trabajador_codigo);
        """
    )
    connection.commit()


def assert_required_tables(connection: sqlite3.Connection) -> None:
    required_tables = {
        "ventas_db": {"trabajadores", "ventas"},
        "rrhh_db": {"trabajadores", "pagos"},
    }
    for alias, expected_tables in required_tables.items():
        rows = connection.execute(
            f"SELECT name FROM {alias}.sqlite_master WHERE type = 'table'"
        ).fetchall()
        available_tables = {row["name"] for row in rows}
        missing_tables = expected_tables - available_tables
        if missing_tables:
            missing_list = ", ".join(sorted(missing_tables))
            raise RuntimeError(f"La base {alias} no contiene las tablas requeridas: {missing_list}")


def fetch_eligible_workers(
    connection: sqlite3.Connection,
    period: str,
    threshold: float,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            v.trabajador_codigo AS codigo_empleado,
            t.nombre,
            ROUND(SUM(v.monto), 2) AS total_ventas
        FROM ventas_db.ventas v
        INNER JOIN ventas_db.trabajadores t ON t.codigo_empleado = v.trabajador_codigo
        WHERE strftime('%Y-%m', v.fecha) = ?
          AND t.activo = 1
        GROUP BY v.trabajador_codigo, t.nombre
        HAVING SUM(v.monto) > ?
        ORDER BY total_ventas DESC, codigo_empleado
        """,
        (period, threshold),
    ).fetchall()


def mark_execution(
    connection: sqlite3.Connection,
    period: str,
    executed_at: datetime,
    status: str,
    detail: str,
) -> None:
    connection.execute(
        """
        INSERT INTO ejecuciones (periodo, ejecutado_en, estado, detalle)
        VALUES (?, ?, ?, ?)
        """,
        (period, executed_at.isoformat(sep=" ", timespec="seconds"), status, detail),
    )
    connection.commit()


def apply_bonus_transaction(
    connection: sqlite3.Connection,
    period: str,
    executed_at: datetime,
    threshold: float,
    bonus_amount: float,
) -> dict[str, list[sqlite3.Row]]:
    eligible_workers = fetch_eligible_workers(connection, period, threshold)
    applied_workers: list[sqlite3.Row] = []
    skipped_workers: list[sqlite3.Row] = []
    execution_label = executed_at.isoformat(sep=" ", timespec="seconds")

    connection.execute("BEGIN")
    try:
        for worker in eligible_workers:
            already_applied = connection.execute(
                """
                SELECT 1
                FROM bonos_aplicados
                WHERE periodo = ? AND trabajador_codigo = ?
                """,
                (period, worker["codigo_empleado"]),
            ).fetchone()

            if already_applied is not None:
                skipped_workers.append(worker)
                continue

            update_cursor = connection.execute(
                """
                UPDATE rrhh_db.pagos
                SET
                    bono_extra = bono_extra + ?,
                    pago_final = sueldo_base + bono_extra + ?
                WHERE trabajador_codigo = ?
                  AND periodo = ?
                  AND estado = 'pendiente'
                """,
                (bonus_amount, bonus_amount, worker["codigo_empleado"], period),
            )

            if update_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se encontro un pago pendiente en RRHH para "
                    f"{worker['codigo_empleado']} en el periodo {period}."
                )

            connection.execute(
                """
                INSERT INTO bonos_aplicados (
                    periodo,
                    trabajador_codigo,
                    ventas_totales,
                    bono,
                    aplicado_en
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    period,
                    worker["codigo_empleado"],
                    worker["total_ventas"],
                    bonus_amount,
                    execution_label,
                ),
            )
            applied_workers.append(worker)

        detail = (
            f"elegibles={len(eligible_workers)}, "
            f"aplicados={len(applied_workers)}, "
            f"omitidos={len(skipped_workers)}"
        )
        connection.execute(
            """
            INSERT INTO ejecuciones (periodo, ejecutado_en, estado, detalle)
            VALUES (?, ?, 'completada', ?)
            """,
            (period, execution_label, detail),
        )
        connection.commit()
        return {
            "eligible_workers": eligible_workers,
            "applied_workers": applied_workers,
            "skipped_workers": skipped_workers,
        }
    except Exception:
        connection.rollback()
        raise


def print_result(
    period: str,
    executed_at: datetime,
    threshold: float,
    bonus_amount: float,
    result: dict[str, list[sqlite3.Row]],
) -> None:
    print(f"Integracion ejecutada para el periodo {period}")
    print(f"Fecha de ejecucion usada: {executed_at.isoformat(sep=' ', timespec='seconds')}")
    print(
        f"Regla: ventas > {threshold:.2f} => bono fijo {bonus_amount:.2f}. "
        f"Ventana sugerida: dia {EXECUTION_DAY} a las {EXECUTION_HOUR:02d}:00; "
        f"pago RRHH dia {PAYMENT_DAY} a las {PAYMENT_HOUR:02d}:00."
    )
    print()

    eligible_workers = result["eligible_workers"]
    applied_workers = result["applied_workers"]
    skipped_workers = result["skipped_workers"]

    if not eligible_workers:
        print("No hubo trabajadores elegibles para bonificacion.")
        return

    print("Elegibles detectados")
    print("codigo | nombre        | total ventas | estado")
    print("-------+---------------+--------------+-----------")
    applied_codes = {row["codigo_empleado"] for row in applied_workers}
    skipped_codes = {row["codigo_empleado"] for row in skipped_workers}

    for row in eligible_workers:
        if row["codigo_empleado"] in applied_codes:
            status = "aplicado"
        elif row["codigo_empleado"] in skipped_codes:
            status = "ya aplicado"
        else:
            status = "revisar"
        print(
            f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['total_ventas']:>12.2f} | {status}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integrador externo de bonos entre ventas y RRHH.")
    parser.add_argument("--periodo", type=validate_period, help="Periodo a procesar en formato YYYY-MM.")
    parser.add_argument(
        "--fecha-ejecucion",
        help="Fecha usada para resolver el periodo automaticamente. Formato YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS.",
    )
    parser.add_argument("--umbral", type=float, default=VENTAS_THRESHOLD)
    parser.add_argument("--bono", type=float, default=BONUS_AMOUNT)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    executed_at = parse_execution_datetime(args.fecha_ejecucion)
    period = args.periodo or previous_month_period(executed_at)

    with connect() as connection:
        create_state_schema(connection)
        assert_required_tables(connection)

        try:
            result = apply_bonus_transaction(
                connection,
                period,
                executed_at,
                args.umbral,
                args.bono,
            )
        except Exception as exc:
            mark_execution(connection, period, executed_at, "fallida", str(exc))
            raise SystemExit(f"La integracion fallo: {exc}") from exc

        print_result(period, executed_at, args.umbral, args.bono, result)


if __name__ == "__main__":
    main()
