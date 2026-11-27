"""Release information and operator guidance."""

VERSION = '1.0.9'
PUBLISHER = 'Corporación Tectronic S.A. de C.V.'
SUPPORT_EMAIL = 'soporte@tectronic.mx'
SUPPORT_PHONE = '+52 1 33 1940 6154'
WHATSAPP_URL = 'https://wa.me/523319406154'
MANUAL_FILE = 'Manual_Usuario_Occidental_Maderas.pdf'

GUIDE = (
    ('Configurar el equipo', (
        'En Configuración selecciona la impresora de Windows y guarda el diseño predeterminado. Para las etiquetas de madera, elige Occidental Maderas · Etiqueta con QR.',
        'Comprueba el siguiente folio. Si lo reduces puedes repetir números ya impresos. Guarda la configuración.',
    )),
    ('Importar y consultar productos', (
        'En Catálogo abre ⋯ y elige Importar Excel o CSV. Para madera, el archivo usa Clase, Espesor, Ancho, Largo y Piezas.',
        'Revisa las altas, cambios y retiros. Agregar y actualizar conserva los demás productos. Reemplazar catálogo conserva únicamente los del archivo.',
        'Busca por clase o medida. Usa el lápiz de la fila para corregir un producto.',
    )),
    ('Preparar e imprimir', (
        'Marca los productos y pulsa Imprimir lote. En Aplicar al lote puedes asignar un pedimento y una cantidad de copias a todas las filas.',
        'Ajusta las excepciones por fila. Las copias de un producto comparten folio y pedimento. Usa el ojo para revisar la vista previa.',
        'Pulsa Imprimir y verifica la salida física. Trabajo enviado indica que Windows recibió el trabajo.',
    )),
    ('Consultar y reimprimir', (
        'En Historial busca por folio, fecha de impresión, producto o Leer QR. Si el QR coincide con varias etiquetas, identifica el folio y la fecha que necesitas.',
        'Pulsa Reimprimir en la fila. Se conserva el folio y el contenido original de la etiqueta.',
    )),
)

TROUBLESHOOTING = (
    ('La impresora no aparece', 'Revisa la conexión y el controlador en Windows. Actualiza la lista en Configuración y guarda la cola correcta.'),
    ('El trabajo se envió pero no salió', 'Revisa la cola de Windows, el material y los avisos de la impresora. Comprueba si salió alguna copia antes de reenviar.'),
    ('El QR no llena el formulario', 'Coloca el cursor en Producto. El lector debe emitir Tab entre Producto, Fecha de entrada, Descripción, No. Pedimento y Piezas. Comprueba que la fecha acepte DD/MM/AAAA.'),
    ('El pedimento aparece vacío', 'Captúralo en Preparar impresión y confirma el valor de la fila antes de imprimir.'),
    ('La vista previa no carga', 'Usa Reintentar y revisa la conexión a internet. La vista previa ZPL utiliza Labelary.'),
    ('Necesito restaurar un respaldo', 'Cierra la app. Conserva una copia de la base actual y contacta a soporte antes de sustituirla. Confirma el siguiente folio al terminar.'),
)
