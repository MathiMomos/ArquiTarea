# Sistemas aislados: ventas, RRHH e integracion por base de datos

Este proyecto simula dos sistemas que funcionan como cajas negras:

1. `sistema_ventas`: registra ventas de trabajadores en `SQLite`.
2. `sistema_rrhh`: administra pagos de trabajadores en otra base `SQLite`.

Ambos sistemas son aislados y no se modifican para comunicarse entre si.

## Problema de arquitectura

La institucion necesita que los trabajadores con ventas superiores a un umbral reciban una bonificacion extra en su pago. El problema es que:

1. Ventas y RRHH no se comunican.
2. Ambos sistemas son cajas negras.
3. Solo se puede acceder a sus bases de datos locales.

## Solucion implementada

Se crea un integrador externo en Python, `integracion/aplicar_bonos.py`, que:

1. Lee la base `sistema_ventas/ventas.db`.
2. Calcula las ventas del mes calendario anterior.
3. Detecta trabajadores con ventas `> 10000.00`.
4. Actualiza la base `sistema_rrhh/rrhh.db` sumando una bonificacion fija de `500.00` al pago final.
5. Guarda auditoria propia en `integracion/estado_integracion.db` para no aplicar el bono dos veces.

## Parametros de negocio

1. Umbral de ventas: `10000.00`
2. Bono fijo: `500.00`
3. Ejecucion sugerida del integrador: dia `15` a las `03:00 AM`
4. Pago de RRHH: dia `15` a las `10:00 PM`
5. Periodo evaluado: mes calendario anterior

Ejemplo: si el integrador corre el `15/05` a las `03:00`, revisa las ventas de `04/2026` y ajusta el pago que RRHH liquidara el `15/05` a las `22:00`.

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

## Comandos principales

### 1. Inicializar base de ventas

```bash
python sistema_ventas/app.py init-db
```

### 2. Cargar datos demo en ventas

```bash
python sistema_ventas/app.py seed-demo
```

### 3. Ver resumen mensual de ventas

```bash
python sistema_ventas/app.py resumen-mensual
```

### 4. Inicializar base de RRHH

```bash
python sistema_rrhh/app.py init-db
```

### 5. Cargar trabajadores y pagos demo en RRHH

```bash
python sistema_rrhh/app.py seed-demo
```

### 6. Ver pagos antes de la integracion

```bash
python sistema_rrhh/app.py listar-pagos
```

### 7. Ejecutar integracion de bonos

```bash
python integracion/aplicar_bonos.py
```

### 8. Ver pagos despues de la integracion

```bash
python sistema_rrhh/app.py listar-pagos
```

## Opciones utiles

Los tres scripts aceptan `--periodo YYYY-MM` para trabajar sobre un mes especifico.

El integrador tambien acepta una fecha de ejecucion simulada:

```bash
python integracion/aplicar_bonos.py --fecha-ejecucion 2026-04-15T03:00:00
```

Si no se envian parametros, el periodo se resuelve como el mes anterior a la fecha actual.

## Programacion mensual en Windows

El integrador puede programarse en `Task Scheduler` para el dia 15 a las 03:00 AM.

Ejemplo usando `schtasks`:

```powershell
schtasks /Create /SC MONTHLY /D 15 /TN "IntegracionBonosVentasRRHH" /TR "C:\Users\User\PycharmProjects\ArquiTarea\.venv\Scripts\python.exe C:\Users\User\PycharmProjects\ArquiTarea\integracion\aplicar_bonos.py" /ST 03:00
```

## Nota tecnica importante

La integracion no modifica el codigo interno de ventas ni de RRHH. Solo trabaja sobre sus bases SQLite, por lo que respeta la restriccion de que ambos sistemas son cajas negras.
