# Guía de trabajo

## Propósito y estructura

Aplicación local de Streamlit para el informe gerencial de ejecución comercial de SOFTYS. La interfaz y sus explicaciones se mantienen en español.

- [app.py](./app.py): entrada de Streamlit; carga cacheada, filtros mensuales y por dimensión, gráficos Plotly, alertas y descargas CSV. Contiene ocho pestañas: resumen, cobertura, NSG, PEG, lineamientos, precios, SOD y POP.
- [analisis.py](./analisis.py): lectura y normalización de fuentes, maestro de PDV, pesos, cálculos y agregaciones. No depende de Streamlit y no modifica los Excel.
- [requirements.txt](./requirements.txt): dependencias declaradas. NumPy también se importa directamente en ambos módulos, aunque actualmente llega como dependencia transitiva.
- [Datos/](./Datos/): cierres en subcarpetas `AAAA-MM`.
- [configuracion/](./configuracion/): Excel de ponderaciones y archivos maestros. `BASE DE PDV.xlsx` se usa como maestro de segmentación para regional, canal y tipología (`NIVEL 3`: Oro/Plata/Bronce; `NIVEL 4`: canal).
- [exportaciones/](./exportaciones/) y [referencias/](./referencias/): insumos y material de referencia; la aplicación no los carga automáticamente como cierres.
- [assets_softys_logo.png](./assets_softys_logo.png) y [.streamlit/config.toml](./.streamlit/config.toml): identidad visual local basada en la paleta Softys (#0773A5, #2D4159 y blanco), para que la interfaz no dependa de una descarga en tiempo de ejecución.

## Entorno y comandos

El entorno verificado en esta máquina es `.venv_informe`, con Python 3.14.8 y Streamlit 1.67.0. Existe además `.venv`; comprobar el intérprete seleccionado antes de ejecutar comandos. No dar por hecho que `python`, `python3` o `streamlit` en PATH corresponden al proyecto.

Desde la raíz, en PowerShell:

```powershell
# Instalar dependencias solo cuando haga falta
& ./.venv_informe/Scripts/python.exe -m pip install -r requirements.txt

# Ejecutar la aplicación
& ./.venv_informe/Scripts/python.exe -m streamlit run app.py

# Comprobar sintaxis después de editar Python
& ./.venv_informe/Scripts/python.exe -m py_compile app.py analisis.py
```

No se encontraron pruebas automatizadas, configuración de lint ni tareas de VS Code. Para cambios de cálculo, validar con casos pequeños de DataFrame que comprueben resultados esperados y denominadores; para cambios de interfaz, revisar la aplicación con el cierre y los filtros afectados. Una comprobación de sintaxis no valida los indicadores ni la carga de fuentes. No incorporar entornos virtuales ni cachés a entregables.

## Contrato de fuentes

- Los nombres canónicos de archivos admitidos están en `FILES` de [analisis.py](./analisis.py). El lector intenta primero el nombre exacto y luego acepta un prefijo del sistema de exportación cuando el nombre termina en el nombre canónico.
- Los Excel de [Datos/2026-10/](./Datos/2026-10/) tienen prefijos como `NSG_`, `PDG_` y `COBERTURA_`; esos archivos ahora se resuelven sin renombrar originales. Si hay más de una coincidencia, se usa la primera en orden alfabético y debe revisarse la calidad de fuentes.
- Las filas con fecha se restringen al mes seleccionado; los archivos sin fecha se asignan al cierre de su carpeta.
- Los pesos se leen de `configuracion/AAAA-MM/MEDICIÓN ACTUAL FDE 2026.xlsx` cuando existe y, en caso contrario, del archivo con el mismo nombre en [configuracion/](./configuracion/). No se busca automáticamente el directorio mensual anterior. El portafolio sí se limita a vigencias no posteriores al cierre.
- `configuracion/BASE DE PDV.xlsx` aporta las dimensiones comerciales y `configuracion/maestro_pdv.csv` puede completar o corregir casos puntuales. Los conflictos de dimensiones quedan como `POR VALIDAR`; no inferir canal o tipología por el nombre del PDV.
- PRE y SOD requieren fuentes de cumplimiento validadas para mostrar esos indicadores. Los precios observados y los conteos de exhibiciones no sustituyen esas fuentes. La interfaz menciona plantillas, pero no existe una carpeta de plantillas en la estructura inicial.

## Reglas que deben conservarse

- Mantener los cálculos de negocio en [analisis.py](./analisis.py) y la presentación en [app.py](./app.py). Respetar los nombres de columnas en español, sus tildes y los identificadores de PDV normalizados.
- Promediar visitas por PDV y después entre PDV, según el indicador. Cada KPI conserva su población y denominador; no sumar prioridades de bases distintas como FDE nacional.
- NSG usa el resultado reportado para cumplimiento y pesos configurados para alertas de SKU. No reemplazarlo silenciosamente por otro cálculo ni inventar pesos para productos sin homologación.
- PEG usa mínimos y pesos propios por categoría; limita el aporte de cada categoría a 100% y excluye visitas incompletas. No trasladar pesos SKU de NSG a PEG o lineamientos.
- Cobertura usa PDV programados atendidos / PDV programados. Frecuencia usa visitas realizadas en ruta / programadas y puede superar 100%; excluir extra ruta.
- Conservar las advertencias de calidad, fuentes ausentes y límites metodológicos. No presentar falta de datos como cero cumplimiento, inventar tendencias ni calcular FDE total sin fuentes y reglas validadas.
- Mantener los originales de Excel y presentaciones. Aplicar transformaciones en memoria salvo petición expresa de generar o actualizar archivos.
- La caché de preparación depende del cierre y de una firma de rutas, tamaños y fechas de modificación de datos y configuración. Si cambia la carga, conservar una invalidación coherente.
- Usar UTF-8 para código y documentación, y UTF-8 con BOM para las descargas CSV, como hace la interfaz actual.
- Preferir cambios acotados y el estilo existente. No mezclar una corrección funcional con una reformateación masiva o un rediseño.
