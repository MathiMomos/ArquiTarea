import tkinter as tk
from tkinter import messagebox, ttk

try:
    from . import app as backend
except ImportError:
    import app as backend


class RRHHUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sistema de RRHH")
        self.geometry("980x620")
        self.minsize(840, 520)

        self.period_var = tk.StringVar(value=backend.current_period())
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
        ttk.Button(quick_actions, text="Generar pagos", command=self.generate_payments).grid(
            row=2, column=0, sticky="ew", padx=8, pady=4
        )
        ttk.Button(quick_actions, text="Listar trabajadores", command=self.show_workers).grid(
            row=3, column=0, sticky="ew", padx=8, pady=4
        )
        ttk.Button(quick_actions, text="Listar pagos", command=self.show_payments).grid(
            row=4, column=0, sticky="ew", padx=8, pady=(4, 8)
        )

        filters = ttk.LabelFrame(controls, text="Periodo de trabajo")
        filters.grid(row=0, column=1, sticky="ew")
        filters.columnconfigure(1, weight=1)

        ttk.Label(filters, text="Periodo (YYYY-MM)").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Entry(filters, textvariable=self.period_var).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 4))
        ttk.Label(
            filters,
            text="RRHH maneja pagos del mes actual y espera que la integracion ajuste el bono antes del cierre.",
            wraplength=420,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 8))

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
        messagebox.showerror("Sistema de RRHH", message)

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

        self.status_var.set(f"Base de RRHH lista en {backend.DB_PATH}")

    def seed_demo(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                workers_loaded, payments_created = backend.insert_demo_data(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron cargar los datos demo: {exc}")
            return

        self.status_var.set(
            f"Trabajadores demo disponibles: {workers_loaded}. Pagos generados para {period}: {payments_created}."
        )
        self.show_payments()

    def generate_payments(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                payments_created = backend.generate_payments(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron generar los pagos: {exc}")
            return

        self.status_var.set(f"Pagos generados para {period}: {payments_created}.")
        self.show_payments()

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
                "sueldo_base": f"{row['sueldo_base']:.2f}",
                "activo": "Si" if row["activo"] else "No",
            }
            for row in rows
        ]
        self._show_table(
            "Trabajadores registrados",
            [
                ("codigo_empleado", "Codigo"),
                ("nombre", "Nombre"),
                ("sueldo_base", "Sueldo base"),
                ("activo", "Activo"),
            ],
            data,
        )

    def show_payments(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                backend.create_schema(connection)
                rows = backend.fetch_payments(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron obtener los pagos: {exc}")
            return

        data = [
            {
                "trabajador_codigo": row["trabajador_codigo"],
                "nombre": row["nombre"],
                "periodo": row["periodo"],
                "fecha_pago": row["fecha_pago"],
                "sueldo_base": f"{row['sueldo_base']:.2f}",
                "bono_extra": f"{row['bono_extra']:.2f}",
                "pago_final": f"{row['pago_final']:.2f}",
                "estado": row["estado"],
            }
            for row in rows
        ]
        self._show_table(
            f"Pagos del periodo {period}",
            [
                ("trabajador_codigo", "Codigo"),
                ("nombre", "Nombre"),
                ("periodo", "Periodo"),
                ("fecha_pago", "Fecha pago"),
                ("sueldo_base", "Base"),
                ("bono_extra", "Bono"),
                ("pago_final", "Final"),
                ("estado", "Estado"),
            ],
            data,
        )


def launch_ui() -> None:
    app = RRHHUI()
    app.mainloop()


if __name__ == "__main__":
    launch_ui()
