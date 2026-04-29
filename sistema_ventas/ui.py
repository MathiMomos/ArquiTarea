from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from . import app as backend
except ImportError:
    import app as backend


HEADER_BG = "#19324a"
HEADER_FG = "#f6f8fb"
SURFACE_BG = "#eef3f8"


class VentasUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sistema de Ventas")
        self.geometry("1240x760")
        self.minsize(1020, 640)
        self.configure(bg=SURFACE_BG)

        self.period_var = tk.StringVar(value=backend.previous_month_period())
        self.code_var = tk.StringVar()
        self.sale_date_var = tk.StringVar(value=datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S"))
        self.amount_var = tk.StringVar()
        self.status_var = tk.StringVar(value=f"Base local: {backend.DB_PATH}")
        self.table_title_var = tk.StringVar(value="Panel operativo de ventas")
        self.view_note_var = tk.StringVar(value="Carga el resumen del periodo para iniciar la jornada.")
        self.selection_var = tk.StringVar(value="Selecciona un registro para ver su detalle rapido.")
        self.metric_vars = {
            "periodo": tk.StringVar(value="-"),
            "total": tk.StringVar(value="0.00"),
            "operaciones": tk.StringVar(value="0"),
            "lider": tk.StringVar(value="Sin datos"),
            "trabajadores": tk.StringVar(value="0"),
        }

        self.current_columns: list[tuple[str, str]] = []
        self.current_rows: list[dict[str, object]] = []
        self.worker_options: list[str] = []

        self._configure_style()
        self._build_layout()
        self._load_worker_options()
        self.show_summary()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", background=HEADER_BG, foreground=HEADER_FG)
        style.configure("MetricTitle.TLabel", font=("Segoe UI", 9, "bold"))
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
            text="Sistema de Ventas",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI Semibold", 20),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Registro operativo diario y seguimiento mensual de ventas por trabajador.",
            bg=HEADER_BG,
            fg="#c9d4df",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Label(
            header,
            textvariable=self.status_var,
            bg=HEADER_BG,
            fg="#d9e3ec",
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

        operations = ttk.LabelFrame(parent, text="Registro diario", style="Section.TLabelframe")
        operations.grid(row=0, column=0, sticky="ew")
        operations.columnconfigure(0, weight=1)

        ttk.Label(operations, text="Trabajador").grid(row=0, column=0, sticky="w")
        self.worker_combo = ttk.Combobox(operations, textvariable=self.code_var, state="normal")
        self.worker_combo.grid(row=1, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(operations, text="Fecha y hora").grid(row=2, column=0, sticky="w")
        ttk.Entry(operations, textvariable=self.sale_date_var).grid(row=3, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(operations, text="Monto").grid(row=4, column=0, sticky="w")
        ttk.Entry(operations, textvariable=self.amount_var).grid(row=5, column=0, sticky="ew", pady=(4, 10))

        ttk.Button(operations, text="Registrar venta", command=self.register_sale).grid(row=6, column=0, sticky="ew")
        ttk.Label(
            operations,
            text="Usa el codigo del trabajador y la fecha real del comprobante con formato YYYY-MM-DD HH:MM:SS.",
            wraplength=250,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(10, 0))

        queries = ttk.LabelFrame(parent, text="Consultas del sistema", style="Section.TLabelframe")
        queries.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        queries.columnconfigure(0, weight=1)

        ttk.Label(queries, text="Periodo de consulta (YYYY-MM)").grid(row=0, column=0, sticky="w")
        ttk.Entry(queries, textvariable=self.period_var).grid(row=1, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(queries, text="Resumen del periodo", command=self.show_summary).grid(row=2, column=0, sticky="ew")
        ttk.Button(queries, text="Movimientos del periodo", command=self.show_sales).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(queries, text="Padron de trabajadores", command=self.show_workers).grid(
            row=4, column=0, sticky="ew", pady=(6, 0)
        )

        maintenance = ttk.LabelFrame(parent, text="Puesta en marcha", style="Section.TLabelframe")
        maintenance.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        maintenance.columnconfigure(0, weight=1)

        ttk.Button(maintenance, text="Inicializar base local", command=self.initialize_database).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(maintenance, text="Cargar datos demo", command=self.seed_demo).grid(
            row=1, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Label(
            maintenance,
            text="La aplicacion trabaja sobre su propia base y no depende de otros sistemas.",
            wraplength=250,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _build_workspace(self, parent: ttk.Frame) -> None:
        metrics = ttk.Frame(parent)
        metrics.grid(row=0, column=0, sticky="ew")
        for index in range(5):
            metrics.columnconfigure(index, weight=1)

        metric_specs = [
            ("Periodo", "periodo"),
            ("Total vendido", "total"),
            ("Operaciones", "operaciones"),
            ("Lider del mes", "lider"),
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
        ttk.Label(content, textvariable=self.view_note_var, justify="left", wraplength=860).grid(
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
        messagebox.showerror("Sistema de Ventas", message)

    def _ensure_period(self) -> str:
        return backend.validate_period(self.period_var.get().strip())

    def _safe_period(self) -> str:
        try:
            return self._ensure_period()
        except Exception:
            return backend.previous_month_period()

    def _load_worker_options(self) -> None:
        try:
            with backend.connect() as connection:
                backend.create_schema(connection)
                rows = backend.fetch_workers(connection)
        except Exception:
            rows = []

        self.worker_options = [f"{row['codigo_empleado']} - {row['nombre']}" for row in rows if row["activo"]]
        self.worker_combo.configure(values=self.worker_options)

    def _refresh_dashboard(self, period: str | None = None) -> None:
        period = period or self._safe_period()
        try:
            with backend.connect() as connection:
                backend.create_schema(connection)
                workers = backend.fetch_workers(connection)
                sales = backend.fetch_sales(connection, period)
                summary = backend.fetch_monthly_summary(connection, period)
        except Exception:
            workers = []
            sales = []
            summary = []

        total_amount = sum(float(row["monto"]) for row in sales) if sales else 0.0
        leader = summary[0] if summary else None
        self.metric_vars["periodo"].set(period)
        self.metric_vars["total"].set(f"{total_amount:.2f}")
        self.metric_vars["operaciones"].set(str(len(sales)))
        self.metric_vars["lider"].set(
            f"{leader['nombre']} ({leader['total_ventas']:.2f})" if leader else "Sin ventas"
        )
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

        self.status_var.set(f"Base de ventas lista en {backend.DB_PATH}")
        self._load_worker_options()
        self._refresh_dashboard(self._safe_period())

    def seed_demo(self) -> None:
        try:
            period = self._ensure_period()
            with backend.connect() as connection:
                inserted = backend.insert_demo_data(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron cargar los datos demo: {exc}")
            return

        self._load_worker_options()
        if inserted == 0:
            self.status_var.set(f"Ya existian ventas para {period}; no se duplicaron datos demo.")
        else:
            self.status_var.set(f"Se cargaron {inserted} ventas demo para {period}.")
        self.show_summary()

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
        self._refresh_dashboard(self._safe_period())
        self._show_table(
            "Padron de trabajadores",
            "Trabajadores registrados en el sistema comercial. Solo el personal activo puede seguir cargando ventas.",
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
        self._refresh_dashboard(period)
        self._show_table(
            f"Movimientos de ventas {period}",
            "Detalle cronologico de ventas registradas en el periodo consultado.",
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
        self._refresh_dashboard(period)
        self._show_table(
            f"Resumen mensual {period}",
            "Consolidado por trabajador para seguimiento de metas y cierre comercial del periodo.",
            [
                ("codigo_empleado", "Codigo"),
                ("nombre", "Nombre"),
                ("cantidad_ventas", "Operaciones"),
                ("total_ventas", "Total vendido"),
            ],
            data,
        )

    def register_sale(self) -> None:
        try:
            worker_code = self.code_var.get().strip()
            if " - " in worker_code:
                worker_code = worker_code.split(" - ", 1)[0]
            sale_date = self.sale_date_var.get().strip()
            amount = float(self.amount_var.get().strip())
            if not worker_code:
                raise ValueError("Ingresa un codigo de trabajador.")
            if amount < 0:
                raise ValueError("El monto no puede ser negativo.")
            with backend.connect() as connection:
                backend.create_schema(connection)
                backend.register_sale(connection, worker_code, sale_date, amount)
        except Exception as exc:
            self._show_error(f"No se pudo registrar la venta: {exc}")
            return

        self.period_var.set(sale_date[:7])
        self.code_var.set(worker_code)
        self.amount_var.set("")
        self.status_var.set(f"Venta registrada para {worker_code} por {amount:.2f} el {sale_date}.")
        self.show_sales()


def launch_ui() -> None:
    app = VentasUI()
    app.mainloop()


if __name__ == "__main__":
    launch_ui()
