from datetime import date, datetime, timedelta
from pathlib import Path
from sqlite3 import Connection, Row, connect
import sys


def database_paths() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
        return root / "ventas.db", root / "rrhh.db"

    root = Path(__file__).resolve().parent.parent
    return root / "sistema_ventas" / "ventas.db", root / "sistema_rrhh" / "rrhh.db"


VENTAS_DB, RRHH_DB = database_paths()

TARGET_AREA = "Caja"
VENTAS_THRESHOLD = 10000.00
BONUS_AMOUNT = 500.00
SALES_WINDOW_START_DAY = 15
SALES_CUTOFF_DAY = 14
EXECUTION_DAY = 15
EXECUTION_HOUR = 3
PAYMENT_DAY = 15
PAYMENT_HOUR = 8

def period_start_date(period: str) -> str:
    year, month = map(int, period.split("-"))
    return date(year, month, 1).isoformat()


def sales_window(period: str) -> tuple[str, str]:
    period_date = date.fromisoformat(period_start_date(period))
    previous_month_last_day = period_date - timedelta(days=1)
    sales_start = previous_month_last_day.replace(day=SALES_WINDOW_START_DAY).isoformat()
    sales_cutoff = period_date.replace(day=SALES_CUTOFF_DAY).isoformat()
    return sales_start, sales_cutoff


def connect_database(path: Path) -> Connection:
    if not path.exists():
        raise FileNotFoundError(f"No existe la base de datos: {path}")

    connection = connect(path)
    connection.row_factory = Row
    return connection


def get_eligible_workers(
    sales_connection: Connection,
    period: str,
) -> list[Row]:
    sales_start, sales_cutoff = sales_window(period)
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
        (sales_start, sales_cutoff, TARGET_AREA, VENTAS_THRESHOLD),
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
) -> tuple[list[Row], set[str]]:
    eligible_workers = get_eligible_workers(sales_connection, period)
    if not eligible_workers:
        return [], set()

    employee_codes = [row["codigo_empleado"] for row in eligible_workers]
    period_date = period_start_date(period)
    expected_bonus = round(BONUS_AMOUNT, 2)
    updated_codes: set[str] = set()

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

            updated_codes.add(worker["codigo_empleado"])

        hr_connection.commit()
        return eligible_workers, updated_codes
    except Exception:
        hr_connection.rollback()
        raise


def print_result(
    period: str,
    executed_at: datetime,
    eligible_workers: list[Row],
    updated_codes: set[str],
) -> None:
    sales_start, sales_cutoff = sales_window(period)
    print(f"Integracion ejecutada para el periodo {period}")
    print(f"Fecha de ejecucion usada: {executed_at.isoformat(sep=' ', timespec='seconds')}")
    print(
        f"Se reviso solo al personal de {TARGET_AREA}, con ventas desde {sales_start} hasta {sales_cutoff}. "
        f"Regla: ventas > {VENTAS_THRESHOLD:.2f} => bono fijo {BONUS_AMOUNT:.2f}."
    )
    print(
        f"Ventana sugerida: dia {EXECUTION_DAY} a las {EXECUTION_HOUR:02d}:00; "
        f"pago RRHH dia {PAYMENT_DAY} a las {PAYMENT_HOUR:02d}:00."
    )
    print()

    if not eligible_workers:
        print("No hubo trabajadores de caja elegibles para bonificacion.")
        return

    print("Trabajadores elegibles")
    print("codigo | nombre        | total ventas | estado")
    print("-------+---------------+--------------+-----------")

    for row in eligible_workers:
        if row["codigo_empleado"] in updated_codes:
            status = "actualizado"
        else:
            status = "ya aplicado"
        print(
            f"{row['codigo_empleado']:<6} | {row['nombre']:<13} | {row['total_ventas']:>12.2f} | {status}"
        )

def main() -> None:
    executed_at = datetime.now().replace(microsecond=0)
    period = executed_at.strftime("%Y-%m")

    with connect_database(VENTAS_DB) as sales_connection, connect_database(RRHH_DB) as hr_connection:
        try:
            eligible_workers, updated_codes = apply_bonus(sales_connection, hr_connection, period)
        except Exception as exc:
            raise SystemExit(f"La integracion fallo: {exc}") from exc

        print_result(period, executed_at, eligible_workers, updated_codes)


if __name__ == "__main__":
    main()
