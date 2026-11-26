# Occidental Maderas · Centro de etiquetas

Aplicación de escritorio para Windows con Python, Flet, SQLite e impresión RAW mediante pywin32.

## Ejecutar

Desde PowerShell, en la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Flujo de trabajo

El menú superior agrupa las acciones de **Catálogo**, **Diseños** y **Configuración**. La barra de iconos permite abrir cada área con un clic y muestra las acciones de la vista activa. Pasa el cursor por un icono para ver su nombre.

En las filas del catálogo, los iconos de lápiz y papelera permiten editar y eliminar. Para imprimir uno o más productos, marca sus casillas y pulsa **Imprimir lote**. Para borrar un lote, marca los productos, elige **Eliminar** y confirma la operación.

Usa **Buscar en** para filtrar una columna, como Factura. **Seleccionar resultados** reemplaza la selección con todos los productos que coinciden, incluso en otras páginas. **Columnas** guarda qué campos se ven en la tabla.

1. En **Catálogo**, usa **Descargar plantilla** para guardar un Excel de ejemplo. Se usa la hoja activa con las columnas `SKU` o `Código`, `Nombre` y `Descripción` opcional.
2. Importa el Excel o CSV. **Agregar y actualizar** conserva los productos anteriores. **Reemplazar catálogo** conserva únicamente los SKU del archivo. La vista previa muestra los SKU nuevos, los valores que cambian y los que se retirarán según el modo elegido.
3. En **Diseños**, consulta la tabla, carga un archivo ZPL o TSPL con **Nuevo diseño**, o usa **Ver**, **Editar** y **Borrar**.
4. En **Configuración**, las colas de Windows se cargan al entrar. Se preselecciona la impresora guardada o la predeterminada de Windows cuando aún no hay una guardada. Usa el icono de actualización junto al puerto si acabas de conectar otra impresora. Puedes cambiar el diseño predeterminado y el siguiente folio, incluso para volver a un número menor.
5. En **Preparar impresión**, ajusta las copias por producto y revisa los folios estimados. El icono de vista previa cambia el producto que se muestra. Los diseños ZPL envían una sola etiqueta a Labelary para generar el PNG con los datos del producto y un folio estimado, sin reservarlo. La vista usa 8 puntos por mm (aproximadamente 203 dpi) y toma las dimensiones de `^PW` y `^LL` cuando están presentes. Si falta alguna medida, se usa 4 pulgadas de ancho o 6 de alto, respectivamente. Los diseños TSPL muestran los valores sin consultar Labelary. Si la vista previa falla, todavía puedes imprimir.

La aplicación reutiliza `%LOCALAPPDATA%\Occidental Maderas\etiquetas.sqlite3`. El reemplazo del catálogo afecta solo a productos. Las plantillas, la impresora configurada y el consecutivo se conservan.

El catálogo de Occidental Maderas admite **Clase, Espesor, Ancho, Largo y Piezas**, con **No. Pedimento** opcional. La primera importación compatible instala el diseño **Occidental Maderas · Etiqueta con QR**. Si ya tienes un diseño predeterminado, puedes cambiarlo en **Configuración**. El repositorio contiene el código y la definición de la etiqueta. El Excel del cliente, los respaldos SQLite y los ejecutables se manejan por separado.

La vista previa indica el ancho y alto de la etiqueta en milímetros. Si el formato supera el espacio del diálogo, la imagen se reduce de manera proporcional. El tamaño físico que muestra el monitor depende de su resolución y escala.

Al detectar columnas nuevas, la importación solicita confirmación antes de incorporarlas. Por ejemplo, **Medida útil** queda disponible como `{{medida_util}}` en los diseños. Al actualizar un SKU, las columnas adicionales ausentes del archivo conservan sus valores anteriores. Un campo nuevo sin valor queda vacío. Si el diseño usa un campo vacío, la impresión pide confirmación antes de asignar los folios.

## Empaquetar para Windows

```powershell
.\.venv\Scripts\python.exe -m pip install flet-cli==0.85.3
.\.venv\Scripts\flet.exe pack main.py --name OccidentalMaderas --distpath dist-flet
```

Consulta las [bases del proyecto](docs/bases-del-proyecto.md) para ver el contrato de los diseños y los folios. Ejecuta `python -m unittest discover -s tests -v` para verificar el núcleo de etiquetas.
