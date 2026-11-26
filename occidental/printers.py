from occidental.raw_printing import print_raw


def list_printers():
    import win32print

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return sorted(win32print.EnumPrinters(flags, None, 4), key=lambda item: item['pPrinterName'].casefold())


def printer_port(name):
    import win32print

    handle = win32print.OpenPrinter(name)
    try:
        return win32print.GetPrinter(handle, 2).get('pPortName', '')
    finally:
        win32print.ClosePrinter(handle)


def default_printer():
    import pywintypes
    import win32print

    try:
        return win32print.GetDefaultPrinter()
    except pywintypes.error as error:
        if error.winerror in {2, 1801}:
            return None
        raise


def submit(name, payload):
    return print_raw(name, payload, 'Occidental Maderas · Etiquetas')
