def print_raw(printer_name: str, payload: bytes, title: str) -> int:
    """Submit printer-language bytes to a named Windows print queue."""
    if not printer_name.strip() or not payload:
        raise ValueError('Indica una impresora y datos de impresión.')

    import win32print

    printer = win32print.OpenPrinter(printer_name)
    try:
        job_id = win32print.StartDocPrinter(printer, 1, (title, None, 'RAW'))
        try:
            win32print.StartPagePrinter(printer)
            if win32print.WritePrinter(printer, payload) != len(payload):
                raise OSError('La cola recibió solo una parte del trabajo.')
            win32print.EndPagePrinter(printer)
            win32print.EndDocPrinter(printer)
        except Exception as error:
            try:
                win32print.AbortPrinter(printer)
            except OSError as abort_error:
                error.add_note(f'AbortPrinter failed: {abort_error}')
            raise
        return job_id
    finally:
        win32print.ClosePrinter(printer)
