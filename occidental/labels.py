from contextlib import closing
import csv
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

from occidental.occma import DESIGN_NAME, FIELDS as OCCMA_FIELDS, PREVIOUS_ZPLS, ZPL as OCCMA_ZPL

@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    description: str
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogImport:
    items: list[Item]
    fields: dict[str, str]


@dataclass(frozen=True)
class PrintHistoryEntry:
    id: int
    folio: str
    printed_at: str
    product: str
    sku: str
    copies: int
    printer: str
    status: str
    reprint: bool
    qr: str = ''

    @property
    def pedimento(self):
        fields = (self.qr or '').split('\t')
        return fields[3] if len(fields) == 5 else ''


DEFAULT_ZPL = """^XA
^CI28
^PW480
^LL240
^FO24,20^A0N,35,28^FH^FD{{nombre}}^FS
^FO24,67^A0N,24,20^FH^FD{{sku}}^FS
^FO24,103^FB430,3,4,L,0^A0N,23,19^FH^FD{{descripcion}}^FS
^FO24,195^A0N,26,23^FH^FDFolio {{folio}}^FS
^XZ"""
TOKENS = re.compile(r'\{\{\s*(\w+)\s*\}\}')
LIMIT = 500
BUILTIN_FIELDS = {'sku': 'SKU', 'nombre': 'Nombre', 'descripcion': 'Descripción', 'folio': 'Folio'}
LABEL_FIELDS = {'clase': 'Clase', 'medidas': 'Medidas', 'piezas_texto': 'Piezas con unidad',
                'pedimento': 'No. Pedimento', 'fecha_entrada': 'Fecha de entrada automática',
                'qr_occma': 'QR de Occidental Maderas'}
PEDIMENTO_COLUMNS = {'pedimento', 'no_pedimento', 'numero_de_pedimento', 'no_de_pedimento'}


def key(value):
    folded = unicodedata.normalize('NFD', str(value or '').casefold().strip())
    return ''.join(char for char in folded if not unicodedata.combining(char))


def read_catalog(path: Path) -> list[Item]:
    return read_catalog_file(path).items


def read_catalog_file(path: Path) -> CatalogImport:
    if path.suffix.lower() == '.xlsx':
        from openpyxl import load_workbook

        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            return parse_rows(workbook.active.values)
        finally:
            workbook.close()
    if path.suffix.lower() != '.csv':
        raise ValueError('Selecciona un archivo XLSX o CSV.')
    raw = path.read_bytes()
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = raw.decode('cp1252')
    import io

    try:
        dialect = csv.Sniffer().sniff(content.partition('\n')[0], delimiters=',;\t')
    except csv.Error as error:
        raise ValueError('El CSV debe incluir encabezados separados por coma, punto y coma o tabulador.') from error
    return parse_rows(csv.reader(io.StringIO(content, newline=''), dialect))


def parse_rows(rows):
    rows = iter(rows)
    labels = [str(value).strip() if value is not None else '' for value in next(rows, ())]
    headers = [re.sub(r'[^a-z0-9]+', '_', key(label)).strip('_') for label in labels]
    if 'clase' in headers and set(OCCMA_FIELDS).issubset(headers) and 'nombre' not in headers:
        return parse_occma_rows(headers, labels, rows)
    sku_columns = [index for index, name in enumerate(headers) if name in {'sku', 'codigo'}]
    if len(sku_columns) != 1 or headers.count('nombre') != 1 or headers.count('descripcion') > 1:
        raise ValueError('Usa una columna SKU o Código, una columna Nombre y, opcionalmente, Descripción.')
    indices = (sku_columns[0], headers.index('nombre'),
               headers.index('descripcion') if 'descripcion' in headers else None)
    fields = {}
    for index, (header, label) in enumerate(zip(headers, labels)):
        if index in indices or not label or header in PEDIMENTO_COLUMNS:
            continue
        if not header or header in BUILTIN_FIELDS or header in fields:
            raise ValueError(f'El encabezado «{label}» genera una variable inválida, reservada o repetida.')
        fields[header] = label
    products = []
    seen = {}
    for number, row in enumerate(rows, 2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        sku, name, description = (
            str(row[index]).strip() if index is not None and index < len(row) and row[index] is not None else ''
            for index in indices
        )
        if not sku or not name:
            raise ValueError(f'Fila {number}: SKU y nombre son obligatorios.')
        attributes = {header: str(row[index]).strip() if index < len(row) and row[index] is not None else ''
                      for index, header in enumerate(headers) if header in fields}
        item = Item(sku.upper(), name, description, attributes)
        previous = seen.get(item.sku)
        if previous is not None:
            if previous != item:
                raise ValueError(f'Fila {number}: el SKU {sku} está repetido con datos distintos.')
            continue
        seen[item.sku] = item
        products.append(item)
    if not products:
        raise ValueError('El archivo no contiene productos.')
    return CatalogImport(products, fields)


def parse_occma_rows(headers, labels, rows):
    headers = ['' if header in PEDIMENTO_COLUMNS else 'sku' if header == 'codigo' else header
               for header in headers]
    named = [header for header in headers if header]
    if len(named) != len(set(named)):
        raise ValueError('El catálogo contiene encabezados repetidos.')
    fields = dict(OCCMA_FIELDS)
    taken = {'clase', 'sku', *OCCMA_FIELDS}
    for header, label in zip(headers, labels):
        if header and header not in taken:
            if header in BUILTIN_FIELDS or header in LABEL_FIELDS:
                raise ValueError(f'El encabezado «{label}» está reservado para la etiqueta.')
            fields[header] = label

    def converted():
        yield ['SKU', 'Nombre', 'Descripción', *fields.values()]
        for number, row in enumerate(rows, 2):
            values = {header: str(value).strip() if value is not None else ''
                      for header, value in zip(headers, row) if header}
            if not any(values.values()):
                continue
            if any(not values.get(name) for name in ('clase', *OCCMA_FIELDS)):
                raise ValueError(f'Fila {number}: completa clase, espesor, ancho, largo y piezas.')
            if not re.fullmatch(r'[0-9]+', values['piezas']):
                raise ValueError(f'Fila {number}: piezas debe ser un entero no negativo.')
            identity = '\x1f'.join(key(values[name]) for name in ('clase', 'espesor', 'ancho', 'largo'))
            sku = values.get('sku') or 'OCC-' + sha256(identity.encode()).hexdigest()[:16].upper()
            yield [sku, values['clase'], values['clase'], *(values.get(name, '') for name in fields)]

    result = parse_rows(converted())
    renames = {re.sub(r'[^a-z0-9]+', '_', key(label)).strip('_'): name for name, label in fields.items()}
    return CatalogImport([Item(item.sku, item.name, item.description,
                               {renames[name]: value for name, value in item.attributes.items()})
                          for item in result.items], fields)


def write_catalog_example(path: Path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    with closing(Workbook()) as workbook:
        sheet = workbook.active
        sheet.title = 'Productos'
        sheet.append(['SKU', 'Nombre', 'Descripción'])
        sheet.append(['0001', 'Tablero MDF', 'Espesor 15 mm'])
        sheet.append(['PIN-002', 'Polín de pino', 'Madera dimensionada'])
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='171717')
        for column, width in zip('ABC', (18, 30, 44)):
            sheet.column_dimensions[column].width = width
        sheet.column_dimensions['A'].number_format = '@'
        sheet.freeze_panes = 'A2'
        workbook.save(path)


def design_fields(source):
    return list(dict.fromkeys(match.group(1) for match in TOKENS.finditer(source)))


def item_values(item):
    return {**item.attributes, 'sku': item.sku, 'nombre': item.name, 'descripcion': item.description}


def label_values(item):
    values = item_values(item)
    dimensions = [values.get(name, '').strip() for name in ('espesor', 'ancho', 'largo')]
    if all(dimensions):
        values['medidas'] = ' x '.join((dimensions[0].rstrip('"'), *dimensions[1:]))
    values['clase'] = values.get('clase') or item.description
    if values.get('piezas'):
        values['piezas_texto'] = values['piezas'] + ' pza'
    return values


def missing_fields(source, items):
    fields = [field for field in design_fields(source) if field not in {'folio', 'fecha_entrada', 'qr_occma'}]
    return {item.sku: missing for item in items
            if (missing := [field for field in fields if not label_values(item).get(field, '').strip()])}


def validate_design(source, language, extra_fields=()):
    fields = set(design_fields(source))
    if 'folio' not in fields:
        raise ValueError('Incluye {{folio}} en el diseño.')
    unknown = fields - BUILTIN_FIELDS.keys() - LABEL_FIELDS.keys() - set(extra_fields)
    if unknown:
        raise ValueError('Variables fuera del catálogo: ' + ', '.join(sorted(unknown)))
    if language == 'ZPL':
        if source.count('^XA') != 1 or source.count('^XZ') != 1 or not source.strip().startswith('^XA') or not source.strip().endswith('^XZ'):
            raise ValueError('El diseño ZPL debe contener un formato entre ^XA y ^XZ.')
        for line in source.splitlines():
            if TOKENS.search(line) and ('^FH^FD' not in line or not all(
                '^FH^FD' in line[:match.start()] and '^FS' in line[match.end():]
                for match in TOKENS.finditer(line)
            )):
                raise ValueError('En ZPL, coloca cada línea con variables dentro de ^FH^FD…^FS.')
        if '^PQ' in source.upper():
            raise ValueError('Las copias se controlan desde la aplicación. Quita el comando ^PQ.')
    elif language == 'TSPL':
        commands = [line.strip().upper() for line in source.splitlines() if line.strip().upper().startswith('PRINT')]
        if commands not in (['PRINT 1'], ['PRINT 1,1'], ['PRINT 1, 1']):
            raise ValueError('El diseño TSPL debe contener un solo PRINT 1 o PRINT 1,1.')
    else:
        raise ValueError('Lenguaje de impresión no admitido.')


def occma_qr(values):
    fields = ('medidas', 'fecha_entrada', 'clase', 'pedimento', 'piezas')
    return '\t'.join(' '.join(values.get(field, '').split()) for field in fields)


def render(source, language, item, folio, *, timestamp=None):
    date = timestamp or datetime.now().astimezone()
    values = {**label_values(item), 'folio': str(folio),
              'fecha_entrada': date.strftime('%d/%m/%Y')}
    if 'qr_occma' in design_fields(source):
        # Only the four delimiters may emit navigation keystrokes.
        values['qr_occma'] = occma_qr(values)
        if source == OCCMA_ZPL and len(values['qr_occma'].encode('utf-8')) > 84:
            # A byte-mode M QR above 84 bytes needs more than 37 modules per side.
            source = source.replace('^BQN,2,9', '^BQN,2,7', 1)

    def replace(match):
        field = match.group(1)
        value = values.get(field, '')
        if field != 'qr_occma':
            value = ' '.join(value.split())
        if language == 'ZPL':
            return ''.join(f'_{byte:02X}' for byte in value.encode('utf-8'))
        return ''.join(char if char.isprintable() and char != '"' else ' ' for char in value)

    return ('\r\n'.join(TOKENS.sub(replace, source).strip().splitlines()) + '\r\n').encode('utf-8')


class LabelStore:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL)')
            if not any(column[1] == 'attributes' for column in db.execute('PRAGMA table_info(products)')):
                db.execute("ALTER TABLE products ADD COLUMN attributes TEXT NOT NULL DEFAULT '{}'")
            db.execute('CREATE TABLE IF NOT EXISTS catalog_fields (key TEXT PRIMARY KEY, label TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS designs (name TEXT PRIMARY KEY, language TEXT NOT NULL, source TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('''CREATE TABLE IF NOT EXISTS print_jobs (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, printer TEXT NOT NULL,
                status TEXT NOT NULL, windows_job TEXT, reprint INTEGER NOT NULL DEFAULT 0
            )''')
            db.execute('''CREATE TABLE IF NOT EXISTS print_labels (
                id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES print_jobs(id),
                folio TEXT NOT NULL, sku TEXT NOT NULL, product TEXT NOT NULL, copies INTEGER NOT NULL,
                qr TEXT, payload BLOB NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS print_labels_folio ON print_labels(folio)')
            db.execute('CREATE INDEX IF NOT EXISTS print_labels_qr ON print_labels(qr)')
            db.executemany("UPDATE designs SET source=? WHERE name=? AND language='ZPL' AND source=?",
                           ((OCCMA_ZPL, DESIGN_NAME, prior) for prior in PREVIOUS_ZPLS))
            db.execute("INSERT OR IGNORE INTO settings VALUES ('next_folio', '1')")
            seeded = db.execute("SELECT 1 FROM settings WHERE key='designs_initialized'").fetchone()
            if not seeded:
                db.execute('INSERT OR IGNORE INTO designs VALUES (?, ?, ?)', ('Etiqueta base ZPL', 'ZPL', DEFAULT_ZPL))
                db.execute("INSERT INTO settings VALUES ('designs_initialized', '1')")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def products(self):
        with closing(self.connect()) as db:
            return [Item(sku, name, description, json.loads(attributes)) for sku, name, description, attributes
                    in db.execute('SELECT sku, name, description, attributes FROM products ORDER BY name, sku')]

    def catalog_fields(self):
        with closing(self.connect()) as db:
            return {name: label for name, label in db.execute('SELECT key, label FROM catalog_fields ORDER BY rowid')
                    if name not in PEDIMENTO_COLUMNS}

    def import_products(self, items, *, replace=False, fields=None, expected=None):
        if not items:
            raise ValueError('El archivo no contiene productos.')
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if expected is not None:
                current = {sku: Item(sku, name, description, json.loads(attributes))
                           for sku, name, description, attributes in db.execute(
                               'SELECT sku, name, description, attributes FROM products')}
                if current != expected:
                    raise ValueError('El catálogo cambió después de la revisión. Importa el archivo de nuevo.')
            if replace:
                db.execute('DELETE FROM products')
            db.executemany('INSERT OR IGNORE INTO catalog_fields (key, label) VALUES (?, ?)',
                           (fields or {}).items())
            db.executemany('''
                INSERT INTO products (sku, name, description, attributes) VALUES (?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET name=excluded.name, description=excluded.description,
                    attributes=json_patch(products.attributes, excluded.attributes)
            ''', ((item.sku, item.name, item.description, json.dumps(item.attributes)) for item in items))
            if OCCMA_FIELDS.keys() <= (fields or {}).keys() and any(
                OCCMA_FIELDS.keys() <= item.attributes.keys() for item in items
            ):
                seeded = db.execute("SELECT 1 FROM settings WHERE key='occma_design_initialized'").fetchone()
                if not seeded:
                    db.execute('INSERT OR IGNORE INTO designs VALUES (?, ?, ?)', (DESIGN_NAME, 'ZPL', OCCMA_ZPL))
                    db.execute("INSERT INTO settings VALUES ('occma_design_initialized', '1')")
                    db.execute("INSERT OR IGNORE INTO settings VALUES ('design', ?)", (DESIGN_NAME,))

    def update_product(self, original_sku, sku, name, description, *, attributes=None):
        sku, name, description = sku.strip().upper(), name.strip(), description.strip()
        if not sku or not name:
            raise ValueError('Escribe el SKU y el nombre del producto.')
        with closing(self.connect()) as db, db:
            result = db.execute('UPDATE products SET sku=?, name=?, description=?, '
                                'attributes=json_patch(attributes, ?) WHERE sku=?',
                                (sku, name, description, json.dumps(attributes or {}), original_sku))
            if not result.rowcount:
                raise ValueError('El producto ya no está en el catálogo.')
        return sku

    def create_product(self, sku, name, description, *, attributes=None):
        sku, name = sku.strip().upper(), name.strip()
        if not sku or not name:
            raise ValueError('Escribe el SKU y el nombre del producto.')
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO products (sku, name, description, attributes) VALUES (?, ?, ?, ?)',
                       (sku, name, description.strip(), json.dumps(attributes or {})))
        return sku

    def delete_product(self, sku):
        with closing(self.connect()) as db, db:
            result = db.execute('DELETE FROM products WHERE sku=?', (sku,))
            if not result.rowcount:
                raise ValueError('El producto ya no está en el catálogo.')

    def delete_products(self, skus):
        unique_skus = tuple(dict.fromkeys(skus))
        with closing(self.connect()) as db, db:
            result = db.executemany('DELETE FROM products WHERE sku=?',
                                    ((sku,) for sku in unique_skus))
            if result.rowcount != len(unique_skus):
                raise ValueError('Algún producto ya no está en el catálogo. Actualiza la selección e inténtalo de nuevo.')
            return result.rowcount

    def designs(self):
        with closing(self.connect()) as db:
            return db.execute('SELECT name, language, source FROM designs ORDER BY name').fetchall()

    def save_design(self, name, language, source, *, original=None):
        name = name.strip()
        if not name:
            raise ValueError('Escribe un nombre para el diseño.')
        validate_design(source, language, self.catalog_fields())
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if original is None:
                db.execute('INSERT INTO designs VALUES (?, ?, ?)', (name, language, source))
            else:
                updated = db.execute('UPDATE designs SET name=?, language=?, source=? WHERE name=?',
                                     (name, language, source, original))
                if not updated.rowcount:
                    raise ValueError('El diseño ya no existe.')
                db.execute("UPDATE settings SET value=? WHERE key='design' AND value=?", (name, original))

    def delete_design(self, name):
        with closing(self.connect()) as db, db:
            db.execute('DELETE FROM designs WHERE name=?', (name,))
            db.execute("DELETE FROM settings WHERE key='design' AND value=?", (name,))

    def setting(self, name, default=''):
        with closing(self.connect()) as db:
            result = db.execute('SELECT value FROM settings WHERE key=?', (name,)).fetchone()
        return result[0] if result else default

    def hidden_catalog_columns(self):
        return set(json.loads(self.setting('hidden_catalog_columns', '[]')))

    def save_hidden_catalog_columns(self, columns):
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO settings VALUES ('hidden_catalog_columns', ?)",
                       (json.dumps(sorted(columns)),))

    def save_settings(self, printer, design, next_folio):
        if type(next_folio) is not int or next_folio < 1:
            raise ValueError('Escribe el siguiente folio como un número entero positivo.')
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.executemany('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                           (('printer', printer), ('design', design), ('next_folio', str(next_folio))))

    def prepare_print(self, items, copies, design):
        return self.prepare_print_batch([(item, copies) for item in items], design)

    def prepare_print_batch(self, entries, design, *, printer=None):
        if any(type(copies) is not int or copies < 1 for _, copies in entries):
            raise ValueError('Cada producto debe tener al menos una copia.')
        if not 1 <= sum(copies for _, copies in entries) <= LIMIT:
            raise ValueError(f'Cada trabajo admite entre 1 y {LIMIT} etiquetas.')
        _, language, source = design
        validate_design(source, language, self.catalog_fields())
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            start = int(db.execute("SELECT value FROM settings WHERE key='next_folio'").fetchone()[0])
            timestamp = datetime.now().astimezone()
            payload = bytearray()
            folio = start
            job = None if printer is None else db.execute(
                "INSERT INTO print_jobs(created_at, printer, status) VALUES (?, ?, 'pending')",
                (timestamp.isoformat(timespec='seconds'), printer),
            ).lastrowid
            with_qr = 'qr_occma' in design_fields(source)
            for item, copies in entries:
                label = render(source, language, item, folio, timestamp=timestamp)
                if len(payload) + len(label) * copies > 8 * 1024 * 1024:
                    raise ValueError('El trabajo supera 8 MB. Reduce el tamaño del lote.')
                payload.extend(label * copies)
                if job is not None:
                    values = label_values(item)
                    values['fecha_entrada'] = timestamp.strftime('%d/%m/%Y')
                    product = ' · '.join(filter(None, (item.name, values.get('medidas'))))
                    db.execute('''INSERT INTO print_labels(job_id, folio, sku, product, copies, qr, payload)
                                  VALUES (?, ?, ?, ?, ?, ?, ?)''',
                               (job, str(folio), item.sku, product, copies,
                                occma_qr(values) if with_qr else None, label))
                folio += 1
            # Commit before spooling so an uncertain print can never reuse these folios.
            db.execute("UPDATE settings SET value=? WHERE key='next_folio'", (str(folio),))
            batch = (start, folio - 1, bytes(payload))
            return batch if job is None else (*batch, job)

    def finish_print(self, job, windows_job=None):
        status = 'uncertain' if windows_job is None else 'sent'
        with closing(self.connect()) as db, db:
            db.execute('UPDATE print_jobs SET status=?, windows_job=? WHERE id=?',
                       (status, windows_job, job))

    def print_history(self, query='', *, mode='all', offset=0, limit=40):
        query = query.strip() if mode != 'qr' else query
        date_query = query
        if mode in {'all', 'date'} and '/' in query:
            try:
                date_query = datetime.strptime(query, '%d/%m/%Y').date().isoformat()
            except ValueError:
                pass
        with closing(self.connect()) as db:
            db.create_function('search_key', 1, key, deterministic=True)
            term = key(query)
            # instr treats the operator input as literal text.
            clauses = {
                'all': '(l.folio = ? OR instr(search_key(l.product || \' \' || l.sku), ?) > 0 OR instr(j.created_at, ?) = 1)',
                'folio': 'l.folio = ?',
                'date': 'instr(j.created_at, ?) = 1',
                'product': "instr(search_key(l.product || ' ' || l.sku), ?) > 0",
                'qr': 'l.qr = ?',
            }
            arguments = {'all': (query, term, date_query), 'date': (date_query,), 'product': (term,)}
            where = clauses[mode] if query else '1'
            params = arguments.get(mode, (query,)) if query else ()
            rows = db.execute(f'''SELECT l.id, l.folio, j.created_at, l.product, l.sku, l.copies,
                                         j.printer, j.status, j.reprint, l.qr
                                  FROM print_labels l JOIN print_jobs j ON j.id=l.job_id
                                  WHERE {where} ORDER BY l.id DESC LIMIT ? OFFSET ?''',
                              (*params, limit, offset))
            return [PrintHistoryEntry(*row) for row in rows]

    def prepare_reprint(self, label_id, printer):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            label = db.execute('SELECT folio, sku, product, qr, payload FROM print_labels WHERE id=?',
                               (label_id,)).fetchone()
            if label is None:
                raise ValueError('La etiqueta ya no está en el historial.')
            folio, sku, product, qr, payload = label
            job = db.execute("INSERT INTO print_jobs(created_at, printer, status, reprint) VALUES (?, ?, 'pending', 1)",
                             (datetime.now().astimezone().isoformat(timespec='seconds'), printer)).lastrowid
            db.execute('''INSERT INTO print_labels(job_id, folio, sku, product, copies, qr, payload)
                          VALUES (?, ?, ?, ?, 1, ?, ?)''', (job, folio, sku, product, qr, payload))
            return job, payload

    def next_folio(self):
        return int(self.setting('next_folio', '1'))
