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
