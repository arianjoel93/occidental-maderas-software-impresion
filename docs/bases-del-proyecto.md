# Bases del centro de etiquetas

## Componentes

- `main.py` inicia el cliente de escritorio Flet.
- `occidental/flet_app.py` ubica la base SQLite y presenta el catálogo, la tabla de diseños, la configuración y los diálogos.
- `occidental/labels.py` valida importaciones, guarda diseños, serializa la reserva de folios y genera los comandos.
- `occidental/printers.py` descubre colas instaladas, consulta el puerto y delega el envío RAW en `occidental/raw_printing.py`.

Los documentos se escriben en español y los comentarios técnicos del código en inglés.

## Interfaz de escritorio

Las tres vistas usan una barra superior con icono y nombre de sección. Cada vista muestra sus propias acciones. En Catálogo, la casilla del encabezado selecciona la página y el menú de más acciones contiene la importación, la descarga de plantilla y la selección de resultados. Duplicar abre el formulario con los datos del producto y pide un SKU nuevo. En Configuración, las etiquetas se alinean a la izquierda y los tres controles tienen el mismo tamaño.

Los diálogos comparten encabezado, área de contenido y acciones. Si el contenido supera el espacio disponible, el cuerpo permite desplazarse y las acciones quedan al pie. En listados y etiquetas de variables, los valores largos se pensaron para mostrar el texto completo al pasar el puntero cuando el espacio obliga a recortarlo. Las casillas seleccionadas usan fondo azul claro y una marca de alto contraste. Los avisos flotantes usan color e icono según su tipo.

## Importación y diseños

El CSV admite UTF-8 y Windows-1252, con coma, punto y coma o tabulador. Se valida el archivo completo antes de guardar. Las filas idénticas con el mismo SKU se consolidan. Si un mismo SKU aparece en el archivo con datos contradictorios, se solicita corregirlo. Al agregar al catálogo, un SKU existente se actualiza únicamente cuando cambia el nombre o la descripción. Al reemplazar, la sustitución del catálogo ocurre en una sola transacción. El consecutivo se comparte entre todos los productos y diseños de la base local.

Los diseños admiten `{{sku}}`, `{{nombre}}`, `{{descripcion}}` y `{{folio}}`. El folio es obligatorio. Para ZPL usa un único par `^XA` y `^XZ`, coloca los campos variables en `^FH^FD…^FS` y usa `^CI28` para texto UTF-8 cuando la impresora lo admita. La plantilla incluida mide 480 × 240 puntos, aproximadamente 60 × 30 mm a 203 dpi. En TSPL usa un único `PRINT 1` o `PRINT 1,1` y configura la codificación, medidas y fuente según el equipo. La vista de datos de la aplicación muestra los valores que se sustituyen en el diseño. Las dimensiones, fuentes y ajuste se validan con la impresora.

## Folios y envío

En **Configuración → Siguiente folio** se puede ajustar el número hacia arriba o hacia abajo. El próximo lote comienza en el valor guardado. Si se elige un folio que ya se imprimió, se puede repetir ese número.

### Etiqueta de Occidental Maderas

El catálogo del cliente se reconoce por los encabezados Clase, Espesor, Ancho, Largo y Piezas. Sin un SKU de origen, se genera uno a partir de la clase y las tres medidas, para que una reimportación actualice las piezas de la misma combinación. Si el archivo carece de pedimento, la importación por adición conserva los pedimentos capturados. Se pueden introducir en Editar producto o incluir en una columna opcional `No. Pedimento`.

El primer catálogo compatible instala el diseño **Occidental Maderas · Etiqueta con QR**. El tamaño original es 831 × 609 puntos. La fecha de entrada se toma del reloj local al generar el lote y el folio avanza en cada etiqueta. Para integrarse con otra aplicación, el lector debe entregar el texto del QR a un parser JSON UTF-8. La versión `v: 1` incluye `sku`, `clase`, `espesor`, `ancho`, `largo`, `medidas`, `piezas`, `pedimento`, `folio` entero y `fecha_entrada` en ISO 8601 con zona horaria. Las cantidades y medidas del catálogo se transmiten como texto para respetar las fracciones y unidades.

La aplicación genera un formato por etiqueta, incluidas las copias, con un folio propio. Un trabajo admite hasta 500 etiquetas y 8 MB de comandos. SQLite reserva el rango en una transacción antes de enviar los datos a Windows. Si Windows o la impresora interrumpen el trabajo, puede quedar un salto en el consecutivo. Se conserva la reserva para evitar duplicar una etiqueta que pudo haberse impreso. El número de trabajo indica que Windows recibió los datos. La salida física se verifica en el equipo.

El catálogo y el consecutivo pertenecen a la base local del perfil de Windows. La unicidad entre varias computadoras requiere una fuente de folios compartida.
