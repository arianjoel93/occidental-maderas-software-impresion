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

El catálogo del cliente se reconoce por los encabezados Clase, Espesor, Ancho, Largo y Piezas. Sin un SKU de origen, se genera uno a partir de la clase y las tres medidas, para que una reimportación actualice las piezas de la misma combinación. El pedimento se captura en **Preparar impresión**. **Aplicar pedimento** llena las filas del lote y después se puede editar cada fila. Todas las copias de un producto usan el valor de su fila. La app ignora la columna de pedimento al importar y cada trabajo comienza con los campos de pedimento vacíos.

El primer catálogo compatible instala el diseño **Occidental Maderas · Etiqueta con QR**. El tamaño original es 831 × 609 puntos. La fecha de entrada se toma del reloj local al generar el lote y se imprime con formato `DD/MM/AAAA`. El folio avanza en cada etiqueta.

El QR contiene cinco valores separados por cuatro tabulaciones ASCII, en este orden: Producto (medidas), Fecha de entrada (`DD/MM/AAAA`), Descripción (clase), No. Pedimento y Piezas (cantidad). Si falta el pedimento, el QR conserva las dos tabulaciones consecutivas que corresponden a ese campo vacío. El QR termina en Piezas. Para capturar desde un lector en modo teclado, sitúa el cursor en Producto, ajusta el lector para que emita el carácter de tabulación como la tecla Tab y desactiva su sufijo automático si agrega Enter o Tab. El orden de foco del formulario y su formato de fecha deben coincidir con el contenido del QR.

Cada fila del lote recibe un folio. Si se solicitan dos copias, se envían dos etiquetas idénticas con el mismo folio. Un trabajo admite hasta 500 impresiones y 8 MB de comandos. SQLite reserva el rango y guarda la etiqueta original antes de enviarla a Windows. Si se interrumpe el envío, revisa la cola antes de reimprimir. El estado Enviado indica que Windows recibió el trabajo.

En **Historial** se puede buscar por folio, fecha de impresión, producto o QR. El QR puede coincidir con varios folios, ya que contiene datos de producto y carece de folio. Elige el registro correcto antes de reimprimir. La reimpresión envía una copia del comando original, con su folio y fecha, y registra un intento nuevo sin avanzar el consecutivo. El historial empieza con los trabajos generados por la versión 1.0.3.

El catálogo y el consecutivo pertenecen a la base local del perfil de Windows. La unicidad entre varias computadoras requiere una fuente de folios compartida.

## Flujo de impresión en escritorio

El **Catálogo** muestra los botones para imprimir y borrar junto al total de productos seleccionados. El botón de importación está en el encabezado y el menú de acciones incluye la descarga de la plantilla. La paginación queda debajo de la tabla.

En **Preparar impresión**, la impresora y el diseño guardados aparecen como datos de consulta. Los ajustes generales de copias y pedimento preceden a la tabla, donde se pueden editar por producto. El pie muestra el número de productos y etiquetas, con los botones **Cancelar** e **Imprimir**. La vista previa ZPL aparece en una fila propia.

En **Historial**, la acción **Reimprimir** abre una confirmación con el folio, el producto y el pedimento recuperado del QR registrado, cuando está disponible. El operador elige la impresora antes de confirmar.
