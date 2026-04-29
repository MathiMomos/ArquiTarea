# Sistemas aislados de ventas y RRHH

Este proyecto arma un caso simple de integracion entre dos sistemas que no se pueden modificar.

Cada sistema funciona como un monolito aislado: tiene su propia base local, su propia logica y ahora tambien su propia interfaz de escritorio.

Tambien se pueden empaquetar como ejecutables independientes de Windows para abrirlos con doble clic.

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
5. localiza el pago pendiente del mismo periodo
6. crea el concepto `BONO_EXTRA` si hace falta y lo registra en el pago pendiente
7. deja que RRHH muestre solo el monto final actualizado, sin detallar internamente el bono

No se crea una tercera base. La integracion existe solo como codigo Python.

## Regla de negocio usada

1. Solo se revisa al personal de `Caja`
2. Umbral de ventas: `10000.00`
3. Bono fijo: `500.00`
4. El dia `14` a las `10:00 PM` se cierra la venta del mes para efectos del bono
5. El script se ejecuta el dia `15` a las `03:00 AM`
6. RRHH paga el dia `15` a las `08:00 AM`
7. Se consideran las ventas desde el dia `15` del mes anterior hasta el cierre del dia `14` del mes actual

Ejemplo: si el script corre el `15/05/2026` a las `03:00`, revisa las ventas acumuladas entre `15/04/2026` y `14/05/2026` y ajusta el pago que RRHH procesara ese mismo `15/05/2026` a las `08:00`.

## Estructura

```text
.
|-- integracion/
|   |-- aplicar_bonos.py
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
3. permite cargar datos de ejemplo
4. permite listar ventas y ver resumenes mensuales
5. ofrece una interfaz de escritorio propia para operar el sistema sin usar otra aplicacion

### `sistema_rrhh/app.py`

1. crea `rrhh.db`
2. registra trabajadores y pagos del periodo
3. guarda cada pago con una cabecera en `pagos` y sus montos en `pago_conceptos`
4. administra internamente el catalogo de `conceptos_pago`, con conceptos base como `SUELDO_BASE`, `MOVILIDAD`, `ALIMENTACION` y `DESCUENTO_AFP`
5. guarda el `periodo` como fecha completa del primer dia del mes, por ejemplo `2026-06-01`
6. deja los pagos en estado `pendiente`
7. calcula el monto a pagar sumando ingresos y restando descuentos
8. ofrece una interfaz de escritorio propia para operar el sistema sin usar otra aplicacion

### `integracion/aplicar_bonos.py`

1. toma la fecha actual del sistema
2. toma el mes actual como periodo de pago
3. lee las ventas acumuladas desde el dia 15 del mes anterior hasta el dia 14 de ese mes
4. selecciona trabajadores de `Caja` que superan el umbral
5. busca esos codigos en RRHH
6. aplica la bonificacion al pago pendiente
7. si se vuelve a ejecutar para el mismo periodo, no duplica el bono

### `integracion/bonos_ui.py`

1. ejecuta la integracion desde una consola externa
2. lista los bonos aplicados por periodo
3. busca por `codigo_empleado`
4. puede filtrar por periodo
5. muestra el bono aplicado y el monto final a pagar

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

Abrir consulta externa de bonos:

```bash
python integracion/bonos_ui.py
```

Abrir interfaz de RRHH:

```bash
python sistema_rrhh/app.py ui
```

Generar ejecutables `.exe`:

```bash
python build_exes.py
```

Ejecutables generados:

```text
dist/SistemaVentas.exe
dist/SistemaRRHH.exe
```

Al ejecutarse empaquetados, cada aplicacion usa su base SQLite junto al `.exe`:

```text
dist/ventas.db
dist/rrhh.db
```

Ejecutar integracion:

```bash
python integracion/aplicar_bonos.py
```

## Observaciones

1. En RRHH puede haber otros trabajadores y otros pagos, pero el script solo toca a quienes aparecen en ventas y pertenecen a `Caja`.
2. RRHH ya no guarda columnas fijas por concepto; usa `conceptos_pago` y `pago_conceptos` para modelar cada monto del pago.
3. `BONO_EXTRA` no viene precargado en RRHH; la integracion lo inserta cuando encuentra trabajadores elegibles.
4. RRHH muestra el monto final a pagar; el detalle especifico del bono se consulta desde `integracion/bonos_ui.py`.
5. `aplicar_bonos.py` no pide argumentos. Usa la fecha actual del sistema para calcular el periodo a procesar.
6. La idea es programar el script en `Task Scheduler` para el dia 15 a las 03:00 AM.
7. Las interfaces de `ventas` y `RRHH` son independientes; ninguna llama directamente a la otra.
8. La integracion sigue siendo externa y batch: el unico punto de cruce es `integracion/aplicar_bonos.py`.
9. `build_exes.py` empaqueta los dos monolitos como aplicaciones de escritorio separadas para Windows.
