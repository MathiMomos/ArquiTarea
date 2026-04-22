from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from sqlite3 import Connection, Row, connect

VENTAS_DB = Path(__file__).resolve().parent.parent / "sistema_ventas" / "ventas.db"
RRHH_DB = Path(__file__).resolve().parent.parent / "sistema_rrhh" / "rrhh.db"

TARGET_AREA = "Caja"
VENTAS_THRESHOLD = 10000.00
BONUS_AMOUNT = 500.00
SALES_CUTOFF_DAY = 14
EXECUTION_DAY = 15
EXECUTION_HOUR = 3
PAYMENT_DAY = 15
PAYMENT_HOUR = 22


def current_period(reference: date | datetime) -> str:
    reference_date = reference.date() if isinstance(reference, datetime) else reference
    return reference_date.strftime("%Y-%m")


def period_start_date(period: str) -> str:
    year, month = map(int, period.split("-"))
    return date(year, month, 1).isoformat()


def connect_database(path: Path) -> Connection:
    if not path.exists():
        raise FileNotFoundError(f"No existe la base de datos: {path}")

    connection = connect(path)
    connection.row_factory = Row
    return connection


def get_eligible_workers(
    sales_connection: Connection,
    period: str,
    threshold: float,
) -> list[Row]:
    period_date = period_start_date(period)
    sales_cutoff = date.fromisoformat(period_date).replace(day=SALES_CUTOFF_DAY).isoformat()
    return sales_connection.execute(
        """
        SELECT
            t.codigo_empleado,
            t.nombre,
            ROUND(SUM(v.monto), 2) AS total_ventas
        FROM ventas v
        INNER JOIN trabajadores t ON t.codigo_empleado = v.trabajador_codigo
        WHERE v.fecha >= ?
          AND v.fecha <= ?
          AND t.activo = 1
          AND t.area = ?
        GROUP BY t.codigo_empleado, t.nombre
        HAVING SUM(v.monto) > ?
        ORDER BY total_ventas DESC, t.codigo_empleado
        """,
        (period_date, sales_cutoff, TARGET_AREA, threshold),
    ).fetchall()


def get_payments_by_employee(
    hr_connection: Connection,
    period_date: str,
    employee_codes: list[str],
) -> dict[str, Row]:
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
        [period_date, *employee_codes],
    ).fetchall()
    return {row["trabajador_codigo"]: row for row in rows}


def apply_bonus(
    sales_connection: Connection,
    hr_connection: Connection,
    period: str,
    threshold: float,
    bonus_amount: float,
) -> dict[str, list[Row]]:
    eligible_workers = get_eligible_workers(sales_connection, period, threshold)
    if not eligible_workers:
        return {
            "eligible_workers": [],
            "updated_workers": [],
            "unchanged_workers": [],
        }

    employee_codes = [row["codigo_empleado"] for row in eligible_workers]
    period_date = period_start_date(period)
    expected_bonus = round(bonus_amount, 2)
    updated_workers: list[Row] = []
    unchanged_workers: list[Row] = []

    hr_connection.execute("BEGIN")
    try:
        payments_by_employee = get_payments_by_employee(hr_connection, period_date, employee_codes)

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
                (expected_bonus, expected_final, worker["codigo_empleado"], period_date),
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
    result: dict[str, list[Row]],
) -> None:
    print(f"Integracion ejecutada para el periodo {period}")
    print(f"Fecha de ejecucion usada: {executed_at.isoformat(sep=' ', timespec='seconds')}")
    print(
        f"Se reviso solo al personal de {TARGET_AREA}, con ventas desde el inicio del mes hasta el dia {SALES_CUTOFF_DAY}. "
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
            status = "ya aplicado"
        else:
            status = "revisar"
        print(
            f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['total_ventas']:>12.2f} | {status}"
        )

def main() -> None:
    executed_at = datetime.now().replace(microsecond=0)
    period = current_period(executed_at)

    with connect_database(VENTAS_DB) as sales_connection, connect_database(RRHH_DB) as hr_connection:
        try:
            result = apply_bonus(
                sales_connection,
                hr_connection,
                period,
                VENTAS_THRESHOLD,
                BONUS_AMOUNT,
            )
        except Exception as exc:
            raise SystemExit(f"La integracion fallo: {exc}") from exc

        print_result(period, executed_at, VENTAS_THRESHOLD, BONUS_AMOUNT, result)


if __name__ == "__main__":
    main()
