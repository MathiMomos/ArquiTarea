from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from . import app as backend
except ImportError:
    import app as backend


class VentasUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sistema de Ventas")
        self.geometry("980x620")
        self.minsize(840, 520)

        self.period_var = tk.StringVar(value=backend.previous_month_period())
        self.code_var = tk.StringVar()
        self.sale_date_var = tk.StringVar(value=date.today().isoformat())
        self.amount_var = tk.StringVar()
        self.status_var = tk.StringVar(value=f"Base local: {backend.DB_PATH}")
        self.table_title_var = tk.StringVar(value="Sin datos cargados")

        self._build_layout()
        self.show_workers()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        controls = ttk.Frame(self, padding=12)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        quick_actions = ttk.LabelFrame(controls, text="Acciones")
        quick_actions.grid(row=0, column=0, sticky="nw", padx=(0, 12))

        ttk.Button(quick_actions, text="Inicializar BD", command=self.initialize_database).grid(
            row=0, column=0, sticky="ew", padx=8, pady=(8, 4)
        )
        ttk.Button(quick_actions, text="Cargar demo", command=self.seed_demo).grid(
            row=1, column=0, sticky="ew", padx=8, pady=4
        )
        ttk.Button(quick_actions, text="Listar trabajadores", command=self.show_workers).grid(
            row=2, column=0, sticky="ew", padx=8, pady=4
        )
        ttk.Button(quick_actions, text="Listar ventas", command=self.show_sales).grid(
            row=3, column=0, sticky="ew", padx=8, pady=4
        )
        ttk.Button(quick_actions, text="Resumen mensual", command=self.show_summary).grid(
            row=4, column=0, sticky="ew", padx=8, pady=(4, 8)
        )

        filters = ttk.LabelFrame(controls, text="Filtros y registro")
        filters.grid(row=0, column=1, sticky="ew")
        filters.columnconfigure(1, weight=1)
        filters.columnconfigure(3, weight=1)

        ttk.Label(filters, text="Periodo (YYYY-MM)").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Entry(filters, textvariable=self.period_var).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 4))

        ttk.Label(filters, text="Codigo").grid(row=0, column=2, sticky="w", padx=8, pady=(8, 4))
        ttk.Entry(filters, textvariable=self.code_var).grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=(8, 4))

        ttk.Label(filters, text="Fecha venta").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(filters, textvariable=self.sale_date_var).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=4)

        ttk.Label(filters, text="Monto").grid(row=1, column=2, sticky="w", padx=8, pady=4)
        ttk.Entry(filters, textvariable=self.amount_var).grid(row=1, column=3, sticky="ew", padx=(0, 8), pady=4)

        ttk.Button(filters, text="Registrar venta", command=self.register_sale).grid(
            row=2, column=3, sticky="e", padx=8, pady=(4, 8)
        )

        title = ttk.Label(self, textvariable=self.table_title_var, padding=(12, 0), font=("Segoe UI", 10, "bold"))
        title.grid(row=1, column=0, sticky="w")

        table_frame = ttk.Frame(self, padding=(12, 8, 12, 8))
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.table = ttk.Treeview(table_frame, show="headings")
        self.table.grid(row=0, column=0, sticky="nsew")

        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        status = ttk.Label(self, textvariable=self.status_var, padding=(12, 0, 12, 12))
        status.grid(row=3, column=0, sticky="ew")

    def _show_error(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showerror("Sistema de Ventas", message)

    def _ensure_period(self) -> str:
        return backend.validate_period(self.period_var.get().strip())

    def _show_table(self, title: str, columns: list[tuple[str, str]], rows: list[dict[str, object]]) -> None:
        self.table_title_var.set(title)
        self.table.delete(*self.table.get_children())

        column_ids = [key for key, _ in columns]
        self.table.configure(columns=column_ids)

        for key, heading in columns:
            max_length = max((len(str(row.get(key, ""))) for row in rows), default=0)
            width = max(110, min(260, max(len(heading), max_length) * 9 + 20))
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, anchor="w")

        for row in rows:
            self.table.insert("", "end", values=[row.get(key, "") for key in column_ids])

        if rows:
            self.status_var.set(f"{title}: {len(rows)} registro(s).")
        else:
            self.status_var.set(f"{title}: sin registros.")

    def initialize_database(self) -> None:
        try:
            with backend.connect() as connection:
                backend.create_schema(connection)
        except Exception as exc:
            self._show_error(f"No se pudo inicializar la base: {exc}")
            return

        self.status_var.set(f"Base de ventas lista en {backend.DB_PATH}")

    def seed_demo(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                inserted = backend.insert_demo_data(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron cargar los datos demo: {exc}")
            return

        if inserted == 0:
            self.status_var.set(f"Ya existian ventas para {period}; no se duplicaron datos demo.")
        else:
            self.status_var.set(f"Se cargaron {inserted} ventas demo para {period}.")
        self.show_sales()

    def show_workers(self) -> None:
        try:
            with backend.connect() as connection:
                backend.create_schema(connection)
                rows = backend.fetch_workers(connection)
        except Exception as exc:
            self._show_error(f"No se pudieron obtener los trabajadores: {exc}")
            return

        data = [
            {
                "codigo_empleado": row["codigo_empleado"],
                "nombre": row["nombre"],
                "area": row["area"],
                "activo": "Si" if row["activo"] else "No",
            }
            for row in rows
        ]
        self._show_table(
            "Trabajadores registrados",
            [("codigo_empleado", "Codigo"), ("nombre", "Nombre"), ("area", "Area"), ("activo", "Activo")],
            data,
        )

    def show_sales(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                backend.create_schema(connection)
                rows = backend.fetch_sales(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron obtener las ventas: {exc}")
            return

        data = [
            {
                "id": row["id"],
                "trabajador_codigo": row["trabajador_codigo"],
                "nombre": row["nombre"],
                "fecha": row["fecha"],
                "monto": f"{row['monto']:.2f}",
            }
            for row in rows
        ]
        self._show_table(
            f"Ventas del periodo {period}",
            [
                ("id", "ID"),
                ("trabajador_codigo", "Codigo"),
                ("nombre", "Nombre"),
                ("fecha", "Fecha"),
                ("monto", "Monto"),
            ],
            data,
        )

    def show_summary(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                backend.create_schema(connection)
                rows = backend.fetch_monthly_summary(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudo generar el resumen: {exc}")
            return

        data = [
            {
                "codigo_empleado": row["codigo_empleado"],
                "nombre": row["nombre"],
                "cantidad_ventas": row["cantidad_ventas"],
                "total_ventas": f"{row['total_ventas']:.2f}",
            }
            for row in rows
        ]
        self._show_table(
            f"Resumen mensual {period}",
            [
                ("codigo_empleado", "Codigo"),
                ("nombre", "Nombre"),
                ("cantidad_ventas", "Ventas"),
                ("total_ventas", "Total"),
            ],
            data,
        )

    def register_sale(self) -> None:
        try:
            worker_code = self.code_var.get().strip()
            sale_date = self.sale_date_var.get().strip()
            amount = float(self.amount_var.get().strip())
            if not worker_code:
                raise ValueError("Ingresa un codigo de trabajador.")
            if amount < 0:
                raise ValueError("El monto no puede ser negativo.")
            date.fromisoformat(sale_date)
            with backend.connect() as connection:
                backend.create_schema(connection)
                backend.register_sale(connection, worker_code, sale_date, amount)
        except Exception as exc:
            self._show_error(f"No se pudo registrar la venta: {exc}")
            return

        self.period_var.set(sale_date[:7])
        self.amount_var.set("")
        self.status_var.set(f"Venta registrada para {worker_code} por {amount:.2f} el {sale_date}.")
        self.show_sales()


def launch_ui() -> None:
    app = VentasUI()
    app.mainloop()


if __name__ == "__main__":
    launch_ui()
