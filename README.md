# Sistemas aislados de ventas y RRHH

Este proyecto arma un caso simple de integracion entre dos sistemas que no se pueden modificar.

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
6. actualiza `bono_extra` y `pago_final`

No se crea una tercera base. La integracion existe solo como codigo Python.

## Regla de negocio usada

1. Solo se revisa al personal de `Caja`
2. Umbral de ventas: `10000.00`
3. Bono fijo: `500.00`
4. El dia `14` a las `10:00 PM` se cierra la venta del mes para efectos del bono
5. El script se ejecuta el dia `15` a las `03:00 AM`
6. RRHH paga el dia `15` a las `10:00 PM`
7. Se consideran las ventas desde el primer dia del mes hasta el cierre del dia 14

Ejemplo: si el script corre el `15/05/2026` a las `03:00`, revisa las ventas acumuladas entre `01/05/2026` y `14/05/2026` y ajusta el pago que RRHH procesara ese mismo `15/05/2026` por la noche.

## Estructura

```text
.
|-- integracion/
|   `-- aplicar_bonos.py
|-- sistema_rrhh/
|   `-- app.py
|-- sistema_ventas/
|   `-- app.py
|-- main.py
`-- README.md
```

## Archivos principales

### `sistema_ventas/app.py`

1. crea `ventas.db`
2. registra trabajadores y ventas
3. permite cargar datos de ejemplo
4. permite listar ventas y ver resumenes mensuales

### `sistema_rrhh/app.py`

1. crea `rrhh.db`
2. registra trabajadores y pagos del periodo
3. deja los pagos en estado `pendiente`
4. guarda el `periodo` como fecha completa del primer dia del mes, por ejemplo `2026-06-01`
5. espera que otro proceso aplique el bono antes del cierre

### `integracion/aplicar_bonos.py`

1. toma la fecha actual del sistema
2. toma el mes actual como periodo de pago
3. lee las ventas acumuladas desde el dia 1 hasta el dia 14 de ese mes
4. selecciona trabajadores de `Caja` que superan el umbral
5. busca esos codigos en RRHH
6. aplica la bonificacion al pago pendiente
7. si se vuelve a ejecutar para el mismo periodo, no duplica el bono

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

Ejecutar integracion:

```bash
python integracion/aplicar_bonos.py
```

## Observaciones

1. En RRHH puede haber otros trabajadores y otros pagos, pero el script solo toca a quienes aparecen en ventas y pertenecen a `Caja`.
2. El bono se escribe en el campo `bono_extra` del pago mensual.
3. `aplicar_bonos.py` no pide argumentos. Usa la fecha actual del sistema para calcular el periodo a procesar.
4. La idea es programar el script en `Task Scheduler` para el dia 15 a las 03:00 AM.
