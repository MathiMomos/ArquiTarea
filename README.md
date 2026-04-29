# Sistemas aislados de ventas y RRHH

Este proyecto arma un caso simple de integracion entre dos sistemas que no se pueden modificar.

Cada sistema funciona como un monolito aislado: tiene su propia base local, su propia logica y ahora tambien su propia interfaz de escritorio.

Tambien se pueden empaquetar como binarios de escritorio independientes. En Windows se generan `.exe` y en Linux se genera un binario nativo con el mismo nombre.

1. `sistema_ventas` guarda las ventas de los trabajadores en `SQLite`.
2. `sistema_rrhh` guarda los pagos de los trabajadores en otra base `SQLite`.

Los dos sistemas son cajas negras. No se comunican entre si y la unica forma de integrarlos es accediendo a sus bases locales.

## Problema

La institucion quiere pagar una bonificacion extra a los trabajadores de `Caja` que superen cierto monto de ventas mensual. El inconveniente es que ventas y RRHH estan separados.

La salida elegida en este proyecto es un script externo en Python que:

1. abre `ventas.db`
2. busca a los trabajadores de `Caja` con ventas superiores al umbral
3. toma su `codigo_empleado`
4. abre `rrhh.db`
5. exige que el concepto `BONO_EXTRA` haya sido preparado externamente en RRHH
6. localiza el pago pendiente del mismo periodo
7. registra el bono en el pago pendiente
8. deja que RRHH muestre solo el monto final actualizado, sin detallar internamente el bono

No se crea una tercera base. La integracion existe solo como codigo Python.

## Regla de negocio usada

1. Solo se revisa al personal de `Caja`
2. Umbral de ventas: `10000.00`
3. Bono fijo: `500.00`
4. El periodo de ventas va desde el dia `1` hasta el ultimo dia del mes
5. El script batch se ejecuta el dia `1` de cada mes a las `02:00 AM`
6. El batch procesa el periodo de ventas del mes anterior
7. RRHH no paga el mismo dia del cierre comercial; paga durante la primera semana del mes siguiente, previa revision humana
8. El calendario comercial y el calendario de pago son distintos: el `periodo` refleja el mes trabajado y la `ventana de pago` refleja cuando RRHH puede depositar

Ejemplo: si el script corre el `01/05/2026` a las `02:00`, revisa las ventas acumuladas entre `01/04/2026` y `30/04/2026`, y ajusta el pago pendiente de RRHH para el periodo `2026-04`. Ese pago queda programado dentro de la ventana `01/05/2026` a `07/05/2026`.

## Estructura

```text
.
|-- integracion/
|   |-- aplicar_bonos.py
|   |-- preparar_concepto_bono.py
|   `-- bonos_ui.py
|-- sistema_rrhh/
|   |-- app.py
|   `-- ui.py
|-- sistema_ventas/
|   |-- app.py
|   `-- ui.py
|-- main.py
`-- README.md
```

## Archivos principales

### `sistema_ventas/app.py`

1. crea `ventas.db`
2. registra trabajadores y ventas
3. guarda cada venta con fecha y hora en el campo `fecha`
4. permite cargar datos de ejemplo
5. permite listar ventas y ver resumenes mensuales
6. ofrece una interfaz de escritorio propia para operar el sistema sin usar otra aplicacion

### `sistema_rrhh/app.py`

1. crea `rrhh.db`
2. registra trabajadores y pagos del periodo
3. guarda cada pago con una cabecera en `pagos` y sus montos en `pago_conceptos`
4. administra internamente el catalogo de `conceptos_pago`, con conceptos base como `SUELDO_BASE`, `MOVILIDAD`, `ALIMENTACION` y `DESCUENTO_AFP`
5. guarda el `periodo` como fecha completa del primer dia del mes, por ejemplo `2026-06-01`
6. separa el `periodo` trabajado de la ventana real de pago mediante `fecha_pago` y `fecha_pago_fin`
7. deja los pagos en estado `pendiente` para permitir revision humana antes del deposito
8. calcula el monto a pagar sumando ingresos y restando descuentos
9. ofrece una interfaz de escritorio propia para operar el sistema sin usar otra aplicacion
10. expone vistas SQL `vw_detalle_pagos` y `vw_resumen_pagos` para revisar detalle por concepto y monto final desde la base

### `integracion/aplicar_bonos.py`

1. toma la fecha actual del sistema
2. toma el mes anterior como periodo de ventas a procesar
3. lee las ventas acumuladas desde el dia 1 hasta el ultimo dia de ese mes
4. selecciona trabajadores de `Caja` que superan el umbral
5. verifica que `BONO_EXTRA` ya exista en RRHH
6. busca esos codigos en RRHH
7. aplica la bonificacion al pago pendiente
8. si se vuelve a ejecutar para el mismo periodo, no duplica el bono

### `integracion/preparar_concepto_bono.py`

1. crea el concepto `BONO_EXTRA` en la base de RRHH
2. se ejecuta una sola vez o cuando se reinstala la base de RRHH
3. deja listo el catalogo para que luego corra `aplicar_bonos.py`

### `integracion/bonos_ui.py`

1. prepara externamente el concepto `BONO_EXTRA`
2. ejecuta la integracion desde una consola externa
3. lista los bonos aplicados por periodo
4. busca por `codigo_empleado`
5. puede filtrar por periodo
6. muestra el bono aplicado y el monto final a pagar

## Comandos

Inicializar ventas:

```bash
python sistema_ventas/app.py init-db
```

Cargar demo de ventas:

```bash
python sistema_ventas/app.py seed-demo
```

Ver trabajadores de ventas:

```bash
python sistema_ventas/app.py listar-trabajadores
```

Ver resumen mensual de ventas:

```bash
python sistema_ventas/app.py resumen-mensual
```

Abrir interfaz de ventas:

```bash
python sistema_ventas/app.py ui
```

Inicializar RRHH:

```bash
python sistema_rrhh/app.py init-db
```

Cargar demo de RRHH:

```bash
python sistema_rrhh/app.py seed-demo
```

Ver pagos de RRHH:

```bash
python sistema_rrhh/app.py listar-pagos
```

Consultar detalle por concepto directamente en la base de RRHH:

```sql
SELECT *
FROM vw_detalle_pagos
WHERE periodo = '2026-04-01'
ORDER BY trabajador_codigo, concepto_codigo;
```

Preparar concepto externo del bono en RRHH:

```bash
python integracion/preparar_concepto_bono.py
```

Abrir consulta externa de bonos:

```bash
python integracion/bonos_ui.py
```

Abrir interfaz de RRHH:

```bash
python sistema_rrhh/app.py ui
```

Generar binarios de escritorio:

```bash
python build_exes.py
```

Binarios generados:

```text
Windows: dist/SistemaVentas.exe
Windows: dist/SistemaRRHH.exe
Linux:   dist/SistemaVentas
Linux:   dist/SistemaRRHH
```

Al ejecutarse empaquetados, cada aplicacion usa su base SQLite junto al binario generado:

```text
dist/ventas.db
dist/rrhh.db
```

Ejecutar integracion:

```bash
python integracion/aplicar_bonos.py
```

## Demo en vivo

Si se quiere mostrar el flujo en vivo sin esperar al cron real, se puede ejecutar manualmente.

Preparar el concepto `BONO_EXTRA` en RRHH:

```bash
python integracion/preparar_concepto_bono.py
```

Ejecutar manualmente el proceso batch de bonos:

```bash
python integracion/aplicar_bonos.py
```

Importante:

1. `aplicar_bonos.py` simula el cronjob, pero usa la fecha actual del sistema para decidir que periodo procesar.
2. Con la regla actual, ese script toma el mes anterior al actual.
3. Si se necesita elegir el periodo manualmente durante la exposicion, lo mas comodo es usar `integracion/bonos_ui.py`.

Abrir la consola externa para demo manual por periodo:

```bash
python integracion/bonos_ui.py
```

Flujo recomendado para exponer en vivo:

1. Inicializar ventas y RRHH.
2. Cargar demo para un periodo conocido, por ejemplo `2026-03`.
3. Abrir `integracion/bonos_ui.py`.
4. Indicar el periodo a procesar.
5. Ejecutar `Preparar concepto bono`.
6. Ejecutar `Ejecutar integracion`.
7. Mostrar `Ver bonos del periodo` o revisar `sistema_rrhh/app.py listar-pagos --periodo 2026-03`.

## Observaciones

1. En RRHH puede haber otros trabajadores y otros pagos, pero el script solo toca a quienes aparecen en ventas y pertenecen a `Caja`.
2. RRHH ya no guarda columnas fijas por concepto; usa `conceptos_pago` y `pago_conceptos` para modelar cada monto del pago.
3. `BONO_EXTRA` no viene precargado en RRHH; se prepara externamente con `integracion/preparar_concepto_bono.py`.
4. RRHH muestra el monto final a pagar; el detalle especifico del bono se consulta desde `integracion/bonos_ui.py`.
5. `aplicar_bonos.py` no pide argumentos. Usa la fecha actual del sistema para calcular el periodo a procesar.
6. Si se quiere forzar otro periodo, se puede usar `integracion/bonos_ui.py` y ejecutar la integracion para el mes deseado.
7. La idea es programar el script en `Task Scheduler` en Windows o con `cron`/`systemd timer` en Linux para el dia 1 a las 02:00 AM.
8. Las interfaces de `ventas` y `RRHH` son independientes; ninguna llama directamente a la otra.
9. La integracion sigue siendo externa y batch: el unico punto de cruce es `integracion/aplicar_bonos.py`.
10. `build_exes.py` empaqueta los dos monolitos como aplicaciones de escritorio separadas para el sistema operativo donde se ejecute el build.
11. Para abrir las interfaces con Python en Linux, normalmente hace falta tener instalado `tkinter` desde el paquete del sistema, por ejemplo `python3-tk`.
12. En Ubuntu o Debian, si aparece el error `No module named tkinter`, instalalo con `sudo apt update && sudo apt install python3-tk`.
13. Los datos demo ahora incluyen mas cajeros y los mismos codigos de empleado en ambos sistemas para que la integracion sea mas facil de explicar en la exposicion.


# Guion

**1. Nic: Context and Architecture**

“Good morning everyone.

Today we are presenting a case of isolated systems and how they can be integrated without modifying their internal logic.

In this project, we work with two separate systems.

The first one is the Sales System. Its purpose is to register workers, store sales transactions, and generate monthly sales summaries. It operates independently and stores its information in its own local SQLite database.

The second one is the HR System. Its purpose is to manage workers, generate payroll payments, and calculate the final amount that each employee should receive. It also works independently and has its own separate SQLite database.

The important idea here is that these are isolated systems. That means they are independent monoliths. Each one has its own interface, its own business logic, and its own data storage. They do not call each other directly, they do not share a common application layer, and they are treated like black boxes.

This kind of scenario is very realistic in real organizations. Many companies already have systems in production that cannot be easily modified, either because of technical limitations, lack of documentation, or operational risk.

So the challenge in this project is not building one big integrated system from scratch. The challenge is connecting two systems that already exist and are intentionally separate.

That is the context of our work.

Now that we understand the architecture, the next step is to see how both systems behave independently.”

**2. Mathias: Demonstration of the Isolated Systems**

“Now I will briefly demonstrate the two systems to show how they work in isolation.

First, this is the Sales System.

In this system, we can initialize the local database, load demo data, register sales, list workers, and display monthly summaries. Its focus is purely commercial. It records who sold, when they sold, and how much they sold.

Now, this is the HR System.

This system is responsible for payroll. Here we can initialize the HR database, load workers, generate payroll payments for a specific period, and view the final amount that each worker should receive.

What matters most in this demonstration is not only what each system does, but also what each system does not do.

The Sales System does not know anything about payroll payments.
It does not know whether a worker has already been paid.
It does not know about payroll concepts like salary, deductions, or bonuses.

At the same time, the HR System does not track monthly sales.
It does not know which cashier exceeded the sales threshold.
It only knows how to calculate and display payroll information.

So even though both systems contain the same employee codes, they are still separated by design.
They have different interfaces, different responsibilities, and different databases.

This separation is exactly what creates the business problem we needed to solve.”

**3. Leo: Business Problem and Functional Solution**

“At this point, the business problem becomes clear.

The institution wants to grant an extra bonus to workers in the Cashier area if they exceed a monthly sales threshold.

From a business perspective, this rule is simple:
if a cashier sells more than a certain amount during the month, they should receive an additional bonus.

However, technically this becomes difficult because the required information is split across two isolated systems.

The Sales System knows the sales performance.
The HR System knows the payroll payment that will eventually be deposited.

So the real problem is this:
how can we use sales information to affect payroll, if both systems are isolated and we are not allowed to directly modify them?

There is also an important functional rule in the final version of the project.

We now separate the sales calendar from the payment calendar.

The sales period goes from the first day of the month to the last day of the same month.
For example, March sales are counted from March 1st to March 31st.

Then, the integration is executed on the first day of the following month at 2:00 AM.
That means the March sales are processed on April 1st.

After that, HR does not immediately pay at the same moment.
Instead, payroll remains in a payment window during the first week of the next month, from April 1st to April 7th, with human review before the final payment.

So we are separating two timelines:
the month in which the work and sales happened,
and the later window in which payroll is actually reviewed and paid.

To solve the problem, we created an external integration process.

Instead of merging the two systems, we use a Python script as a bridge.
This script reads the Sales database, identifies the eligible cashiers, then connects to the HR database and applies the bonus to the correct pending payroll record.

This approach preserves the isolation of both systems while still solving the real business requirement.”

**4. Alonsin: Technical Explanation of the Integration**

“Now I will explain the technical side of the solution.

The central component is the script called `aplicar_bonos.py`.

Its job is to process one monthly sales period and write the bonus into the HR payroll data before the payment window is completed.

The script begins by determining which period must be processed.
In the final version of the project, it does not process the current month.
It processes the previous month.
So if the script runs on April 1st, it processes the sales period for March.

After that, it calculates the sales window using the full calendar month.
Technically, this means the query searches sales from the first day of the month at `00:00:00` until the last day of the month at `23:59:59`.

Then the script runs a query against the Sales database.
Conceptually, the query does the following:
- joins sales with workers
- filters only active workers
- filters only workers in the `Caja`, or Cashier, area
- restricts the rows to the selected monthly time window
- groups the results by employee
- sums the total sales
- keeps only workers whose total sales exceed the threshold

So this is not checking individual transactions one by one in application memory.
The database is doing the aggregation through SQL using `SUM`, `GROUP BY`, and `HAVING`.

This is important because it makes the filtering logic clearer and more scalable.

Once the script gets the eligible workers, it extracts their employee codes.
Then it moves to the HR database.

In HR, the script first verifies that the payment concept `BONO_EXTRA` already exists.
This is a validation step.
The integration is not allowed to invent a payroll concept on the fly during the main execution.
That concept must already be prepared in HR or through the external setup tool.

After that, the script queries the `pagos` table to find the payroll record for each eligible employee for the corresponding payroll period.
It also checks the current bonus amount, if one already exists, by joining with `pago_conceptos`.

Technically, the script is looking for:
- the employee’s payroll row for that period
- a payment in `pendiente` status
- and whether a `BONO_EXTRA` concept was already inserted

This is very important because it prevents duplication.
If the bonus was already applied for that employee and that month, the script does not insert it again.

If the bonus is missing, the script either updates or inserts the `BONO_EXTRA` row in `pago_conceptos`.

That means the script does not rewrite the whole payroll calculation.
Instead, it uses the HR system’s own internal structure.
HR already calculates final payment amounts from payroll concepts, so by inserting `BONO_EXTRA` as an income concept, the final amount automatically increases in a consistent way.

This is one of the strongest parts of the design:
the integration does not bypass HR logic,
it works through HR’s existing payroll model.

So, in summary, the technical flow is:
identify eligible workers in Sales,
map them by employee code,
find their pending payroll in HR,
validate the bonus concept,
and then write the bonus as structured payroll data.”

**5. Andres: Queries, Scheduling, UI, and Final Result**

“I will explain how the integration is executed operationally, how the database result can be reviewed, and why this design makes sense in practice.

First, this solution is implemented as a batch process.

That means the integration is not triggered every time someone makes a sale.
Instead, it runs at a scheduled moment after the monthly sales period has ended.

In our project, the intended schedule is:
the cron job runs on the first day of each month at 2:00 AM.

For example:
sales from March 1st to March 31st are processed on April 1st at 2:00 AM.

This makes sense because the month is already closed, so the script can safely evaluate the full sales period.
At the same time, HR still has time to review payroll before payments are actually made during the first week of the month.

So the integration is designed around two separate business calendars:
the commercial period,
and the payroll payment window.

From a technical perspective, the HR side also exposes the result in a structured way.

The HR database contains:
- `pagos`, which stores the payroll header for each worker and period
- `pago_conceptos`, which stores individual payroll concepts like salary, mobility, food allowance, pension deduction, and now `BONO_EXTRA`
- SQL views such as `vw_detalle_pagos` and `vw_resumen_pagos`, which make it easier to inspect the final result

The bonus review UI is built on top of this integration layer.

This external UI allows us to:
- prepare the `BONO_EXTRA` concept
- execute the integration manually if needed
- list all bonuses applied for a given period
- search bonuses by employee code
- display the final payroll amount after the bonus has been applied

Technically, when the bonus UI queries applied bonuses, it reads payroll rows that already contain the `BONO_EXTRA` concept and combines them with the payroll totals.
So the UI is not guessing the result.
It is reading the final state from the database after the integration.

This gives us a clear audit trail.

For example, after processing period `2026-03`, we can see:
- which cashiers were eligible
- the amount of bonus applied
- the payment window in HR, such as `2026-04-01` to `2026-04-07`
- and the updated final payroll amount

That is useful both technically and operationally, because it allows verification before the final payment is completed.

To conclude, this solution has several strengths:
- it keeps both systems isolated
- it solves a real cross-system business rule
- it uses SQL aggregation and structured payroll concepts instead of fragile manual logic
- it separates the sales period from the payment moment
- and it leaves a transparent record of the applied bonuses

Its main limitation is that it still depends on both systems using the same employee codes and having compatible period definitions.
But given the constraint of isolated systems, this is a practical and well-structured solution.

Thank you.”

**Suggested transitions**
- Nic to Mathias:
  “Now that we understand the architecture, let’s see both systems working independently.”

- Mathias to Leo:
  “Once we see the systems in isolation, the business problem becomes much easier to understand.”

- Leo to Alonsin:
  “Now let’s move from the functional problem to the technical implementation.”

- Alonsin to Andres:
  “Finally, let’s see how this integration is scheduled, reviewed, and validated in practice.”

**Extra recommendation**
For the technical parts, especially `Alonsin` and `Andres`, it will sound stronger if the slide includes these keywords:
- `JOIN`
- `GROUP BY`
- `HAVING`
- `pending payment`
- `payroll concepts`
- `batch integration`
- `payment window`