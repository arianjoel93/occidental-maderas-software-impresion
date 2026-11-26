from math import ceil
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DOTS_PER_MM = 8
LABELARY_DPI = 203
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
FALLBACK_INCHES = (4.0, 6.0)


def label_dots(zpl: bytes) -> tuple[int, int]:
    dimensions = []
    for command in (b'PW', b'LL'):
        matches = re.findall(rb'\^' + command + rb'\s*(\d+)', zpl, re.IGNORECASE)
        dimensions.append(int(matches[-1]) if matches else 0)
    return dimensions[0], dimensions[1]


def label_size(zpl: bytes) -> tuple[float, float]:
    width, height = label_dots(zpl)
    return (width / (DOTS_PER_MM * 25.4) if width else FALLBACK_INCHES[0],
            height / (DOTS_PER_MM * 25.4) if height else FALLBACK_INCHES[1])


def preview_png(zpl: bytes) -> bytes:
    # Labelary converts 8dpmm requests at 203 dpi and truncates fractional dots.
    width, height = (ceil(dots * 10_000 / LABELARY_DPI) / 10_000 if dots else fallback
                     for dots, fallback in zip(label_dots(zpl), FALLBACK_INCHES))
    request = Request(
        f'https://api.labelary.com/v1/printers/{DOTS_PER_MM}dpmm/labels/{width:.4f}x{height:.4f}/0/',
        data=zpl, method='POST',
        headers={'Accept': 'image/png', 'Content-Type': 'application/x-www-form-urlencoded'},
    )
    try:
        with urlopen(request, timeout=8) as response:
            image = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        error.close()
        if error.code == 429:
            raise ValueError('Labelary recibió demasiadas solicitudes. Espera un momento y vuelve a intentar.') from error
        raise ValueError(f'Labelary no pudo generar la vista previa (HTTP {error.code}).') from error
    except (URLError, TimeoutError, OSError) as error:
        raise ValueError('No se pudo conectar con Labelary. Revisa tu conexión y vuelve a intentar.') from error
    if len(image) > MAX_RESPONSE_BYTES or not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Labelary no devolvió una imagen PNG válida para esta etiqueta.')
    return image
