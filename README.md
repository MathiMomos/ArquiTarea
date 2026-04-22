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
4. El script se ejecuta el dia `15` a las `03:00 AM`
5. RRHH paga el dia `15` a las `10:00 PM`
6. El periodo evaluado es el mes calendario anterior

Ejemplo: si el script corre el `15/05/2026` a las `03:00`, revisa las ventas de `04/2026` y ajusta el pago que RRHH procesara ese mismo `15/05/2026` por la noche.

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
4. espera que otro proceso aplique el bono antes del cierre

### `integracion/aplicar_bonos.py`

1. lee las ventas del mes anterior
2. selecciona trabajadores de `Caja` que superan el umbral
3. busca esos codigos en RRHH
4. aplica la bonificacion al pago pendiente
5. si se vuelve a ejecutar para el mismo periodo, no duplica el bono

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

Simular la corrida del dia 15 a las 03:00:

```bash
python integracion/aplicar_bonos.py --fecha-ejecucion 2026-05-15T03:00:00
```

## Observaciones

1. En RRHH puede haber otros trabajadores y otros pagos, pero el script solo toca a quienes aparecen en ventas y pertenecen a `Caja`.
2. El bono se escribe en el campo `bono_extra` del pago mensual.
3. Si el pago ya tiene exactamente ese bono aplicado, el script lo deja `sin cambio`.
4. La idea es programar el script en `Task Scheduler` para el dia 15 a las 03:00 AM.

Ejemplo de registro en Windows:

```powershell
schtasks /Create /SC MONTHLY /D 15 /TN "IntegracionBonosVentasRRHH" /TR "C:\Users\User\PycharmProjects\ArquiTarea\.venv\Scripts\python.exe C:\Users\User\PycharmProjects\ArquiTarea\integracion\aplicar_bonos.py" /ST 03:00
```
