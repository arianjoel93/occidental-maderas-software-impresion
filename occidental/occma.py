"""Catalog field names and the client label format."""

FIELDS = {'espesor': 'Espesor', 'ancho': 'Ancho', 'largo': 'Largo', 'piezas': 'Piezas'}
DESIGN_NAME = 'Occidental Maderas · Etiqueta con QR'
ZPL = """^XA
~TA000
~JSN
^LT0
^MNW
^MTT
^PON
^PMN
^LH0,0
^JMA
^PR8,8
~SD15
^LRN
^CI28
^PA0,1,1,0
^MMT
^PW831
^LL609
^LS0
^FO489,172^BQN,2,4^FH^FDMA,{{qr_occma}}^FS
^FT0,257^A0N,36,35^FB423,2,9,C,0^FH^FD{{clase}}^FS
^FT0,102^A0N,68,68^FB831,1,0,C,0^FH^FD{{medidas}}^FS
^FT0,409^A0N,70,68^FB355,1,0,C,0^FH^FD{{piezas_texto}}^FS
^FT291,527^A0N,28,28^FB249,1,0,C,0^FDFolio^FS
^FT291,567^A0N,37,35^FB249,1,0,C,0^FH^FD{{folio}}^FS
^FT60,527^A0N,28,28^FDFecha de entrada^FS
^FT49,567^A0N,25,22^FH^FD{{fecha_entrada}}^FS
^FT564,527^A0N,28,28^FDNo. Pedimento^FS
^FT553,567^A0N,25,22^FH^FD{{pedimento}}^FS
^XZ"""
