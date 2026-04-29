from datetime import datetime

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
    from . import aplicar_bonos as backend
except ImportError:
    import aplicar_bonos as backend


HEADER_BG = "#153e3b"
HEADER_FG = "#eefaf8"
SURFACE_BG = "#eef7f6"


def validate_period(period: str) -> str:
    value = period.strip()
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("El periodo debe tener formato YYYY-MM.") from exc
    return value


def validate_optional_period(period: str) -> str | None:
    value = period.strip()
    if not value:
        return None
    return validate_period(value)


class BonusQueryUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Consola de Integracion de Bonos")
        self.geometry("1280x780")
        self.minsize(1040, 660)
        self.configure(bg=SURFACE_BG)

        self.execution_period_var = tk.StringVar(value=datetime.now().strftime("%Y-%m"))
        self.worker_code_var = tk.StringVar()
        self.query_period_var = tk.StringVar()
        self.status_var = tk.StringVar(value=f"Origen ventas: {backend.VENTAS_DB} | Destino RRHH: {backend.RRHH_DB}")
        self.table_title_var = tk.StringVar(value="Consola externa de integracion")
        self.view_note_var = tk.StringVar(value="Primero prepara el concepto externo y luego ejecuta la integracion o consulta los bonos aplicados.")
        self.selection_var = tk.StringVar(value="Selecciona un registro para ver el detalle rapido.")
        self.metric_vars = {
            "periodo": tk.StringVar(value="-"),
            "ventana": tk.StringVar(value="-"),
            "regla": tk.StringVar(value=f"> {backend.VENTAS_THRESHOLD:.2f} / {backend.BONUS_AMOUNT:.2f}"),
            "resultado": tk.StringVar(value="Sin ejecutar"),
        }

        self.current_columns: list[tuple[str, str]] = []
        self.current_rows: list[dict[str, object]] = []

        self._configure_style()
        self._build_layout()
        self.show_period_bonuses()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("MetricValue.TLabel", font=("Segoe UI", 15, "bold"))
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
            text="Consola de Integracion de Bonos",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI Semibold", 20),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Herramienta externa que cruza ventas y RRHH sin modificar sus interfaces internas.",
            bg=HEADER_BG,
            fg="#cbe6e2",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Label(
            header,
            textvariable=self.status_var,
            bg=HEADER_BG,
            fg="#d8f1ed",
            font=("Consolas", 8),
            justify="right",
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

        execution = ttk.LabelFrame(parent, text="Ejecucion batch", style="Section.TLabelframe")
        execution.grid(row=0, column=0, sticky="ew")
        execution.columnconfigure(0, weight=1)

        ttk.Label(execution, text="Periodo a procesar (YYYY-MM)").grid(row=0, column=0, sticky="w")
        ttk.Entry(execution, textvariable=self.execution_period_var).grid(row=1, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(execution, text="Preparar concepto bono", command=self.prepare_bonus_concept).grid(
            row=2, column=0, sticky="ew"
        )
        ttk.Button(execution, text="Ejecutar integracion", command=self.run_integration).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(execution, text="Ver bonos del periodo", command=self.show_period_bonuses).grid(
            row=4, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Label(
            execution,
            text="El flujo operativo es preparar el concepto en RRHH y luego aplicar el bono solo a pagos pendientes.",
            wraplength=260,
            justify="left",
        ).grid(row=5, column=0, sticky="w", pady=(10, 0))

        query = ttk.LabelFrame(parent, text="Consulta por trabajador", style="Section.TLabelframe")
        query.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        query.columnconfigure(0, weight=1)

        ttk.Label(query, text="Codigo de trabajador").grid(row=0, column=0, sticky="w")
        ttk.Entry(query, textvariable=self.worker_code_var).grid(row=1, column=0, sticky="ew", pady=(4, 10))
        ttk.Label(query, text="Periodo (opcional)").grid(row=2, column=0, sticky="w")
        ttk.Entry(query, textvariable=self.query_period_var).grid(row=3, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(query, text="Buscar bonos", command=self.search_bonuses).grid(row=4, column=0, sticky="ew")

        environment = ttk.LabelFrame(parent, text="Contexto operativo", style="Section.TLabelframe")
        environment.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        environment.columnconfigure(0, weight=1)

        ttk.Label(
            environment,
            text=(
                "Ventana de ventas: desde el dia 15 del mes anterior hasta el dia 14 del periodo. "
                "Esta consola no reemplaza RRHH; solo deja trazado externo del bono aplicado."
            ),
            wraplength=260,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    def _build_workspace(self, parent: ttk.Frame) -> None:
        metrics = ttk.Frame(parent)
        metrics.grid(row=0, column=0, sticky="ew")
        for index in range(4):
            metrics.columnconfigure(index, weight=1)

        metric_specs = [
            ("Periodo operativo", "periodo"),
            ("Ventana de ventas", "ventana"),
            ("Regla", "regla"),
            ("Resultado", "resultado"),
        ]
        for column, (title, key) in enumerate(metric_specs):
            card = ttk.LabelFrame(metrics, text=title, style="Section.TLabelframe")
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            ttk.Label(card, textvariable=self.metric_vars[key], style="MetricValue.TLabel", wraplength=220).grid(
                row=0, column=0, sticky="w"
            )

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

    def _set_period_context(self, period: str) -> None:
        sales_start, sales_cutoff = backend.sales_window(period)
        self.metric_vars["periodo"].set(period)
        self.metric_vars["ventana"].set(f"{sales_start} a {sales_cutoff}")

    def _show_error(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showerror("Consola de Integracion", message)

    def _show_table(
        self,
        title: str,
        note: str,
        columns: list[tuple[str, str]],
        rows: list[dict[str, object]],
    ) -> None:
        self.table_title_var.set(title)
        self.view_note_var.set(note)
        self.selection_var.set("Selecciona un registro para ver el detalle rapido.")
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

    def run_integration(self) -> None:
        try:
            period = validate_period(self.execution_period_var.get())
            with backend.connect_database(backend.VENTAS_DB) as sales_connection, backend.connect_database(
                backend.RRHH_DB
            ) as hr_connection:
                eligible_workers, updated_codes = backend.apply_bonus(sales_connection, hr_connection, period)
        except Exception as exc:
            self._show_error(f"No se pudo ejecutar la integracion: {exc}")
            return

        self._set_period_context(period)
        self.metric_vars["resultado"].set(f"{len(updated_codes)} actualizado(s)")
        data = [
            {
                "codigo_empleado": row["codigo_empleado"],
                "nombre": row["nombre"],
                "total_ventas": f"{row['total_ventas']:.2f}",
                "estado": "actualizado" if row["codigo_empleado"] in updated_codes else "ya aplicado",
            }
            for row in eligible_workers
        ]
        self._show_table(
            f"Resultado de integracion {period}",
            "Trabajadores elegibles segun ventas del periodo. El bono se escribe externamente y RRHH solo recibira el monto final actualizado.",
            [
                ("codigo_empleado", "Codigo"),
                ("nombre", "Nombre"),
                ("total_ventas", "Ventas acumuladas"),
                ("estado", "Resultado"),
            ],
            data,
        )

    def prepare_bonus_concept(self) -> None:
        try:
            with backend.connect_database(backend.RRHH_DB) as connection:
                backend.register_bonus_concept(connection)
                connection.commit()
        except Exception as exc:
            self._show_error(f"No se pudo preparar el concepto bono: {exc}")
            return

        period = validate_period(self.execution_period_var.get())
        self._set_period_context(period)
        self.metric_vars["resultado"].set("Concepto preparado")
        self._show_table(
            "Concepto de bono preparado",
            "El concepto BONO_EXTRA ya esta disponible en RRHH para que la integracion mensual pueda registrar bonificaciones.",
            [("paso", "Paso"), ("detalle", "Detalle")],
            [
                {
                    "paso": "Preparacion",
                    "detalle": "BONO_EXTRA registrado en RRHH y listo para su aplicacion externa.",
                }
            ],
        )

    def show_period_bonuses(self) -> None:
        try:
            period = validate_period(self.execution_period_var.get())
            with backend.connect_database(backend.RRHH_DB) as connection:
                rows = backend.fetch_bonus_period_payments(connection, period)
        except Exception as exc:
            self._show_error(f"No se pudieron obtener los bonos del periodo: {exc}")
            return

        self._set_period_context(period)
        self.metric_vars["resultado"].set(f"{len(rows)} bono(s) aplicado(s)")
        data = [
            {
                "trabajador_codigo": row["trabajador_codigo"],
                "nombre": row["nombre"],
                "fecha_pago": row["fecha_pago"],
                "bono_monto": f"{row['bono_monto']:.2f}",
                "monto_pagar": f"{row['monto_pagar']:.2f}",
                "estado": row["estado"],
            }
            for row in rows
        ]
        self._show_table(
            f"Bonos aplicados en {period}",
            "Listado externo de pagos que ya recibieron el concepto de bonificacion para el periodo seleccionado.",
            [
                ("trabajador_codigo", "Codigo"),
                ("nombre", "Nombre"),
                ("fecha_pago", "Fecha pago"),
                ("bono_monto", "Bono"),
                ("monto_pagar", "Monto a pagar"),
                ("estado", "Estado"),
            ],
            data,
        )

    def search_bonuses(self) -> None:
        worker_code = self.worker_code_var.get().strip().upper()
        if not worker_code:
            self._show_error("Debes ingresar un codigo de trabajador.")
            return

        try:
            period = validate_optional_period(self.query_period_var.get())
            with backend.connect_database(backend.RRHH_DB) as connection:
                rows = backend.fetch_bonus_payments(connection, worker_code, period)
        except Exception as exc:
            self._show_error(f"No se pudieron consultar los bonos: {exc}")
            return

        context_period = period or (rows[0]["periodo"][:7] if rows else datetime.now().strftime("%Y-%m"))
        self._set_period_context(context_period)
        self.metric_vars["resultado"].set(f"{len(rows)} coincidencia(s)")
        data = [
            {
                "trabajador_codigo": row["trabajador_codigo"],
                "nombre": row["nombre"],
                "periodo": row["periodo"][:7],
                "fecha_pago": row["fecha_pago"],
                "bono_monto": f"{row['bono_monto']:.2f}",
                "monto_pagar": f"{row['monto_pagar']:.2f}",
                "estado": row["estado"],
            }
            for row in rows
        ]
        period_label = period or "todos los periodos"
        self._show_table(
            f"Bonos de {worker_code} en {period_label}",
            "Consulta puntual para auditar cuanto bono se aplico y en que pago final quedo reflejado.",
            [
                ("trabajador_codigo", "Codigo"),
                ("nombre", "Nombre"),
                ("periodo", "Periodo"),
                ("fecha_pago", "Fecha pago"),
                ("bono_monto", "Bono"),
                ("monto_pagar", "Monto a pagar"),
                ("estado", "Estado"),
            ],
            data,
        )


def launch_ui() -> None:
    app = BonusQueryUI()
    app.mainloop()


if __name__ == "__main__":
    launch_ui()
