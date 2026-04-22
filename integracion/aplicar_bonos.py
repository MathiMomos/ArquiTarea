from __future__ import annotations

import argparse
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
VENTAS_DB_PATH = ROOT_DIR / "sistema_ventas" / "ventas.db"
RRHH_DB_PATH = ROOT_DIR / "sistema_rrhh" / "rrhh.db"

TARGET_AREA = "Caja"
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

    raw_value = raw_value.strip()
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "La fecha de ejecucion debe ser YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS."
        ) from exc

    if len(raw_value) == 10:
        parsed = parsed.replace(hour=EXECUTION_HOUR)

    return parsed.replace(microsecond=0)


def previous_month_period(reference: date | datetime) -> str:
    reference_date = reference.date() if isinstance(reference, datetime) else reference
    first_day = reference_date.replace(day=1)
    previous_month_last_day = first_day - timedelta(days=1)
    return previous_month_last_day.strftime("%Y-%m")


def connect_database(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"No existe la base de datos: {path}")

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def assert_required_tables(
    connection: sqlite3.Connection,
    database_name: str,
    expected_tables: set[str],
) -> None:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    available_tables = {row["name"] for row in rows}
    missing_tables = expected_tables - available_tables
    if missing_tables:
        missing_list = ", ".join(sorted(missing_tables))
        raise RuntimeError(f"La base {database_name} no contiene las tablas requeridas: {missing_list}")


def fetch_eligible_workers(
    sales_connection: sqlite3.Connection,
    period: str,
    threshold: float,
) -> list[sqlite3.Row]:
    return sales_connection.execute(
        """
        SELECT
            t.codigo_empleado,
            t.nombre,
            ROUND(SUM(v.monto), 2) AS total_ventas
        FROM ventas v
        INNER JOIN trabajadores t ON t.codigo_empleado = v.trabajador_codigo
        WHERE strftime('%Y-%m', v.fecha) = ?
          AND t.activo = 1
          AND t.area = ?
        GROUP BY t.codigo_empleado, t.nombre
        HAVING SUM(v.monto) > ?
        ORDER BY total_ventas DESC, t.codigo_empleado
        """,
        (period, TARGET_AREA, threshold),
    ).fetchall()


def fetch_payments_by_employee(
    hr_connection: sqlite3.Connection,
    period: str,
    employee_codes: list[str],
) -> dict[str, sqlite3.Row]:
    if not employee_codes:
        return {}

    placeholders = ", ".join("?" for _ in employee_codes)
    rows = hr_connection.execute(
        f"""
        SELECT trabajador_codigo, sueldo_base, bono_extra, pago_final, estado
        FROM pagos
        WHERE periodo = ?
          AND trabajador_codigo IN ({placeholders})
        """,
        [period, *employee_codes],
    ).fetchall()
    return {row["trabajador_codigo"]: row for row in rows}


def apply_bonus(
    sales_connection: sqlite3.Connection,
    hr_connection: sqlite3.Connection,
    period: str,
    threshold: float,
    bonus_amount: float,
) -> dict[str, list[sqlite3.Row]]:
    eligible_workers = fetch_eligible_workers(sales_connection, period, threshold)
    if not eligible_workers:
        return {
            "eligible_workers": [],
            "updated_workers": [],
            "unchanged_workers": [],
        }

    employee_codes = [row["codigo_empleado"] for row in eligible_workers]
    expected_bonus = round(bonus_amount, 2)
    updated_workers: list[sqlite3.Row] = []
    unchanged_workers: list[sqlite3.Row] = []

    hr_connection.execute("BEGIN")
    try:
        payments_by_employee = fetch_payments_by_employee(hr_connection, period, employee_codes)

        for worker in eligible_workers:
            payment = payments_by_employee.get(worker["codigo_empleado"])
            if payment is None:
                raise RuntimeError(
                    "No se encontro un pago en RRHH para "
                    f"{worker['codigo_empleado']} en el periodo {period}."
                )

            if payment["estado"] != "pendiente":
                raise RuntimeError(
                    "El pago de RRHH ya no esta pendiente para "
                    f"{worker['codigo_empleado']} en el periodo {period}."
                )

            expected_final = round(payment["sueldo_base"] + expected_bonus, 2)
            if (
                round(payment["bono_extra"], 2) == expected_bonus
                and round(payment["pago_final"], 2) == expected_final
            ):
                unchanged_workers.append(worker)
                continue

            update_cursor = hr_connection.execute(
                """
                UPDATE pagos
                SET
                    bono_extra = ?,
                    pago_final = ?
                WHERE trabajador_codigo = ?
                  AND periodo = ?
                  AND estado = 'pendiente'
                """,
                (expected_bonus, expected_final, worker["codigo_empleado"], period),
            )
            if update_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo actualizar el pago de RRHH para "
                    f"{worker['codigo_empleado']} en el periodo {period}."
                )

            updated_workers.append(worker)

        hr_connection.commit()
        return {
            "eligible_workers": eligible_workers,
            "updated_workers": updated_workers,
            "unchanged_workers": unchanged_workers,
        }
    except Exception:
        hr_connection.rollback()
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
        f"Se reviso solo al personal de {TARGET_AREA}. "
        f"Regla: ventas > {threshold:.2f} => bono fijo {bonus_amount:.2f}."
    )
    print(
        f"Ventana sugerida: dia {EXECUTION_DAY} a las {EXECUTION_HOUR:02d}:00; "
        f"pago RRHH dia {PAYMENT_DAY} a las {PAYMENT_HOUR:02d}:00."
    )
    print()

    eligible_workers = result["eligible_workers"]
    updated_workers = result["updated_workers"]
    unchanged_workers = result["unchanged_workers"]

    if not eligible_workers:
        print("No hubo trabajadores de caja elegibles para bonificacion.")
        return

    print("Trabajadores elegibles")
    print("codigo | nombre        | total ventas | estado")
    print("-------+---------------+--------------+-----------")
    updated_codes = {row["codigo_empleado"] for row in updated_workers}
    unchanged_codes = {row["codigo_empleado"] for row in unchanged_workers}

    for row in eligible_workers:
        if row["codigo_empleado"] in updated_codes:
            status = "actualizado"
        elif row["codigo_empleado"] in unchanged_codes:
            status = "sin cambio"
        else:
            status = "revisar"
        print(
            f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['total_ventas']:>12.2f} | {status}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integra ventas con RRHH para aplicar bonos.")
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

    with connect_database(VENTAS_DB_PATH) as sales_connection, connect_database(RRHH_DB_PATH) as hr_connection:
        assert_required_tables(sales_connection, "ventas.db", {"trabajadores", "ventas"})
        assert_required_tables(hr_connection, "rrhh.db", {"trabajadores", "pagos"})

        try:
            result = apply_bonus(
                sales_connection,
                hr_connection,
                period,
                args.umbral,
                args.bono,
            )
        except Exception as exc:
            raise SystemExit(f"La integracion fallo: {exc}") from exc

        print_result(period, executed_at, args.umbral, args.bono, result)


if __name__ == "__main__":
    main()
