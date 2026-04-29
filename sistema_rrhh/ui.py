try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ModuleNotFoundError as exc:
    if exc.name != "tkinter":
        raise
    raise SystemExit(
        "Tkinter no esta instalado. En Ubuntu/Debian instala el paquete del sistema con: sudo apt install python3-tk"
    ) from exc

try:
    from . import app as backend
except ImportError:
    import app as backend


HEADER_BG = "#3a204e"
HEADER_FG = "#f7f2fb"
SURFACE_BG = "#f4f0f7"


class RRHHUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sistema de RRHH")
        self.geometry("1240x760")
        self.minsize(1020, 640)
        self.configure(bg=SURFACE_BG)

        self.period_var = tk.StringVar(value=backend.default_payroll_period())
        self.status_var = tk.StringVar(value=f"Base local: {backend.DB_PATH}")
        self.table_title_var = tk.StringVar(value="Control de nomina")
        self.view_note_var = tk.StringVar(
            value="Consulta la nomina del periodo devengado y la ventana de pago programada para revision humana."
        )
        self.selection_var = tk.StringVar(value="Selecciona un registro para ver su detalle rapido.")
        self.metric_vars = {
            "periodo": tk.StringVar(value="-"),
            "ventana_pago": tk.StringVar(value="-"),
            "pendientes": tk.StringVar(value="0"),
            "planilla": tk.StringVar(value="0.00"),
            "trabajadores": tk.StringVar(value="0"),
        }

        self.current_columns: list[tuple[str, str]] = []
        self.current_rows: list[dict[str, object]] = []

        self._configure_style()
        self._build_layout()
        self.show_payments()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("MetricValue.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Section.TLabelframe", padding=10)
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 9, "bold"))

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=HEADER_BG, padx=18, pady=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        tk.Label(
            header,
            text="Sistema de RRHH",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI Semibold", 20),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Operacion aislada de nomina mensual y padron de trabajadores.",
            bg=HEADER_BG,
            fg="#ddcfe8",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Label(
            header,
            textvariable=self.status_var,
            bg=HEADER_BG,
            fg="#eadff2",
            font=("Consolas", 9),
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        main = ttk.Frame(self, padding=(14, 14, 14, 14))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(main)
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        workspace = ttk.Frame(main)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)

        self._build_sidebar(sidebar)
        self._build_workspace(workspace)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        payroll = ttk.LabelFrame(parent, text="Ciclo de nomina", style="Section.TLabelframe")
        payroll.grid(row=0, column=0, sticky="ew")
        payroll.columnconfigure(0, weight=1)

        ttk.Label(payroll, text="Periodo devengado (YYYY-MM)").grid(row=0, column=0, sticky="w")
        ttk.Entry(payroll, textvariable=self.period_var).grid(row=1, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(payroll, text="Ver pagos del periodo", command=self.show_payments).grid(row=2, column=0, sticky="ew")
        ttk.Button(payroll, text="Generar pagos pendientes", command=self.generate_payments).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Label(
            payroll,
            text="La pantalla muestra el monto final y la ventana de pago del mes siguiente, previa revision humana.",
            wraplength=250,
            justify="left",
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

        people = ttk.LabelFrame(parent, text="Padron de personal", style="Section.TLabelframe")
        people.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        people.columnconfigure(0, weight=1)

        ttk.Button(people, text="Ver trabajadores", command=self.show_workers).grid(row=0, column=0, sticky="ew")
        ttk.Button(people, text="Cargar demo de RRHH", command=self.seed_demo).grid(
            row=1, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Label(
            people,
            text="El padron se mantiene separado de los demas sistemas y opera sobre su propia base local.",
            wraplength=250,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

        maintenance = ttk.LabelFrame(parent, text="Mantenimiento", style="Section.TLabelframe")
        maintenance.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        maintenance.columnconfigure(0, weight=1)

        ttk.Button(maintenance, text="Inicializar base local", command=self.initialize_database).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Label(
            maintenance,
            text="Usa esta accion cuando se despliega el sistema por primera vez o se recrea la base local.",
            wraplength=250,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))

    def _build_workspace(self, parent: ttk.Frame) -> None:
        metrics = ttk.Frame(parent)
        metrics.grid(row=0, column=0, sticky="ew")
        for index in range(5):
            metrics.columnconfigure(index, weight=1)

        metric_specs = [
            ("Periodo", "periodo"),
            ("Ventana de pago", "ventana_pago"),
            ("Pagos pendientes", "pendientes"),
            ("Total planilla", "planilla"),
            ("Trabajadores activos", "trabajadores"),
        ]
        for column, (title, key) in enumerate(metric_specs):
            card = ttk.LabelFrame(metrics, text=title, style="Section.TLabelframe")
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            ttk.Label(card, textvariable=self.metric_vars[key], style="MetricValue.TLabel").grid(row=0, column=0, sticky="w")

        content = ttk.Frame(parent)
        content.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)

        ttk.Label(content, textvariable=self.table_title_var, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(content, textvariable=self.view_note_var, wraplength=860, justify="left").grid(
            row=1, column=0, sticky="w", pady=(2, 10)
        )

        table_frame = ttk.Frame(content)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.table = ttk.Treeview(table_frame, show="headings")
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<<TreeviewSelect>>", self._on_row_selected)

        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        detail = ttk.LabelFrame(content, text="Detalle rapido", style="Section.TLabelframe")
        detail.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        detail.columnconfigure(0, weight=1)
        ttk.Label(detail, textvariable=self.selection_var, wraplength=860, justify="left").grid(
            row=0, column=0, sticky="w"
        )

    def _show_error(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showerror("Sistema de RRHH", message)

    def _ensure_period(self) -> str:
        return backend.validate_period(self.period_var.get().strip())

    def _safe_period(self) -> str:
        try:
            return self._ensure_period()
        except Exception:
            return backend.default_payroll_period()

    def _refresh_dashboard(self, period: str | None = None) -> None:
        period = period or self._safe_period()
        try:
            with backend.connect() as connection:
                backend.create_schema(connection)
                workers = backend.fetch_workers(connection)
                payments = backend.fetch_payments(connection, period)
        except Exception:
            workers = []
            payments = []

        total_planilla = sum(float(row["monto_pagar"]) for row in payments) if payments else 0.0
        pending = sum(1 for row in payments if row["estado"] == "pendiente")
        self.metric_vars["periodo"].set(period)
        payment_start = backend.payment_date_for_period(period)
        payment_end = backend.payment_window_end_for_period(period)
        self.metric_vars["ventana_pago"].set(f"{payment_start} a {payment_end}")
        self.metric_vars["pendientes"].set(str(pending))
        self.metric_vars["planilla"].set(f"{total_planilla:.2f}")
        self.metric_vars["trabajadores"].set(str(sum(1 for row in workers if row["activo"])))

    def _show_table(
        self,
        title: str,
        note: str,
        columns: list[tuple[str, str]],
        rows: list[dict[str, object]],
    ) -> None:
        self.table_title_var.set(title)
        self.view_note_var.set(note)
        self.selection_var.set("Selecciona un registro para ver su detalle rapido.")
        self.table.delete(*self.table.get_children())

        self.current_columns = columns
        self.current_rows = rows

        column_ids = [key for key, _ in columns]
        self.table.configure(columns=column_ids)

        for key, heading in columns:
            max_length = max((len(str(row.get(key, ""))) for row in rows), default=0)
            width = max(110, min(260, max(len(heading), max_length) * 9 + 24))
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, anchor="w")

        for index, row in enumerate(rows):
            self.table.insert("", "end", iid=str(index), values=[row.get(key, "") for key in column_ids])

        self.status_var.set(f"{title}: {len(rows)} registro(s).") if rows else self.status_var.set(
            f"{title}: sin registros."
        )

    def _on_row_selected(self, _event: object) -> None:
        selected = self.table.selection()
        if not selected:
            return
        row = self.current_rows[int(selected[0])]
        detail_parts = [f"{heading}: {row.get(key, '')}" for key, heading in self.current_columns]
        self.selection_var.set(" | ".join(detail_parts))

    def initialize_database(self) -> None:
        try:
            with backend.connect() as connection:
                backend.create_schema(connection)
        except Exception as exc:
            self._show_error(f"No se pudo inicializar la base: {exc}")
            return

        self.status_var.set(f"Base de RRHH lista en {backend.DB_PATH}")
        self._refresh_dashboard(self._safe_period())

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
        self._refresh_dashboard(self._safe_period())
        self._show_table(
            "Padron de trabajadores",
            "Padron interno de RRHH usado para generar pagos mensuales y controlar la actividad del personal.",
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
                "periodo": row["periodo"][:7],
                "ventana_pago": f"{row['fecha_pago']} a {row['fecha_pago_fin']}",
                "monto_pagar": f"{row['monto_pagar']:.2f}",
                "estado": row["estado"],
            }
            for row in rows
        ]
        self._refresh_dashboard(period)
        self._show_table(
            f"Nomina del periodo {period}",
            "Vista operativa de pagos: RRHH separa el periodo trabajado de la ventana real de pago del mes siguiente.",
            [
                ("trabajador_codigo", "Codigo"),
                ("nombre", "Nombre"),
                ("periodo", "Periodo"),
                ("ventana_pago", "Ventana pago"),
                ("monto_pagar", "Monto a pagar"),
                ("estado", "Estado"),
            ],
            data,
        )


def launch_ui() -> None:
    app = RRHHUI()
    app.mainloop()


if __name__ == "__main__":
    launch_ui()
