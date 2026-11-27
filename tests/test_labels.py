from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from occidental.labels import (
    DEFAULT_ZPL, Item, LabelStore, missing_fields, parse_rows, read_catalog, read_catalog_file, render,
    write_catalog_example,
)
from occidental.occma import DESIGN_NAME, ZPL


class LabelsTest(unittest.TestCase):
    def test_occma_catalog_identity_and_qr(self):
        headers = ('CLASE', 'ESPESOR ', 'ANCHO', 'LARGO', 'PIEZAS', 'No. Pedimento')
        product = ('Primera  nacional', '3/4"', '6"', "8'")
        initial = parse_rows([headers, (*product, 280, 'IGNORADO')])
        updated = parse_rows([headers, (*product, 399, 'IGNORADO')])
        self.assertNotIn('pedimento', initial.fields)
        sku = initial.items[0].sku
        self.assertEqual(sku, updated.items[0].sku)
        with TemporaryDirectory() as directory:
            store = LabelStore(Path(directory) / 'labels.sqlite3')
            store.import_products(initial.items, fields=initial.fields)
            self.assertEqual(store.setting('design'), DESIGN_NAME)
            item = store.products()[0]
            self.assertEqual(missing_fields(ZPL, [item]), {sku: ['pedimento']})
            store.import_products(updated.items, fields=updated.fields)
            item, = store.products()
            item = replace(item, attributes={**item.attributes, 'pedimento': 'G-123'})
            stamp = datetime(2026, 11, 26, 8, 29, 27, tzinfo=timezone.utc)
            output = render(ZPL, 'ZPL', item, 77, timestamp=stamp)
            hex_data = re.search(rb'\^FDMA,([^\^]+)', output).group(1).replace(b'_', b'')
            payload = bytes.fromhex(hex_data.decode('ascii')).decode('utf-8')
            self.assertEqual(payload, '3/4 x 6" x 8\'\t26/11/2026\tPrimera nacional\tG-123\t399')
            hex_fields = re.findall(rb'\^FH\^FD((?:_[0-9A-F]{2})+)\^FS', output)
            text_fields = [bytes.fromhex(value.replace(b'_', b'').decode('ascii')).decode('utf-8')
                           for value in hex_fields]
            self.assertIn('26/11/2026', text_fields)

            blank = render(ZPL, 'ZPL', initial.items[0], 78, timestamp=stamp)
            hex_data = re.search(rb'\^FDMA,([^\^]+)', blank).group(1).replace(b'_', b'')
            payload = bytes.fromhex(hex_data.decode('ascii')).decode('utf-8')
            self.assertEqual(payload.split('\t'), ['3/4 x 6" x 8\'', '26/11/2026', 'Primera nacional', '', '280'])

    def test_excel_csv_and_atomic_catalog_updates(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            csv = root / 'catalog.csv'
            csv.write_text('Código;Nombre;Descripción\n001;Pino;Natural\n', encoding='utf-8-sig')
            db = LabelStore(root / 'labels.sqlite3')
            db.import_products(read_catalog(csv))
            workbook = Workbook()
            workbook.active.append(['SKU', 'Nombre'])
            workbook.active.append(['001', 'Pino tratado'])
            workbook.active.append(['002', 'Cedro'])
            excel = root / 'catalog.xlsx'
            workbook.save(excel)
            workbook.close()
            db.import_products(read_catalog(excel))
            self.assertEqual({item.sku: item.name for item in db.products()},
                             {'001': 'Pino tratado', '002': 'Cedro'})
            csv.write_text('SKU,Nombre\n001,Pino\n001,Cedro\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'repetido'):
                read_catalog(csv)
            self.assertEqual(len(db.products()), 2)

    def test_catalog_replace_and_identical_rows(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            db = LabelStore(root / 'labels.sqlite3')
            csv = root / 'catalog.csv'
            csv.write_text('SKU,Nombre\n001,Pino\n001,Pino\n', encoding='utf-8')
            products = read_catalog(csv)
            self.assertEqual(products, [Item('001', 'Pino', '')])
            db.import_products(products)
            db.import_products([Item('002', 'Cedro', '')])
            self.assertEqual(len(db.products()), 2)
            db.import_products([Item('001', 'Pino tratado', '')], replace=True)
            self.assertEqual(db.products(), [Item('001', 'Pino tratado', '')])
            example = root / 'Plantilla.xlsx'
            write_catalog_example(example)
            self.assertIn('0001', {item.sku for item in read_catalog(example)})

    def test_product_edit_duplicate_sku_and_delete(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.sqlite3'
            db = LabelStore(path)
            db.import_products([Item('A', 'Pino', ''), Item('B', 'Cedro', '')])
            with self.assertRaises(sqlite3.IntegrityError):
                db.update_product('A', 'b', 'Pino tratado', '')
            self.assertEqual({item.sku for item in db.products()}, {'A', 'B'})
            self.assertEqual(db.update_product('A', ' a1 ', ' Pino tratado ', ' Nuevo '), 'A1')
            db.delete_product('B')
            self.assertEqual(LabelStore(path).products(), [Item('A1', 'Pino tratado', 'Nuevo')])

    def test_delete_products_is_atomic(self):
        with TemporaryDirectory() as directory:
            db = LabelStore(Path(directory) / 'labels.sqlite3')
            db.import_products([Item('A', 'Pino', ''), Item('B', 'Cedro', ''), Item('C', 'MDF', '')])
            with self.assertRaisesRegex(ValueError, 'ya no está'):
                db.delete_products(['A', 'DESCONOCIDO'])
            self.assertEqual({item.sku for item in db.products()}, {'A', 'B', 'C'})
            self.assertEqual(db.delete_products(['A', 'B', 'A']), 2)
            self.assertEqual(LabelStore(db.path).products(), [Item('C', 'MDF', '')])

    def test_mixed_copies_reserve_one_contiguous_range(self):
        with TemporaryDirectory() as directory:
            db = LabelStore(Path(directory) / 'labels.sqlite3')
            first, second = Item('A', 'Pino', ''), Item('B', 'MDF', '')
            design = ('Base', 'ZPL', '^XA\n^FH^FD{{sku}}^FS\n^FH^FD{{folio}}^FS\n^XZ')
            with self.assertRaises(ValueError):
                db.prepare_print_batch([(first, 0), (second, 2)], design)
            self.assertEqual(db.next_folio(), 1)
            start, end, payload = db.prepare_print_batch([(first, 3), (second, 2)], design)
            self.assertEqual((start, end, db.next_folio()), (1, 2, 3))
            self.assertEqual(payload.count(b'^FD_41^FS'), 3)
            self.assertEqual(payload.count(b'^FD_42^FS'), 2)
            self.assertEqual(payload.count(b'^FD_31^FS'), 3)
            self.assertEqual(payload.count(b'^FD_32^FS'), 2)

    def test_history_search_and_exact_reprint(self):
        with TemporaryDirectory() as directory:
            db = LabelStore(Path(directory) / 'labels.sqlite3')
            item = Item('H-01', 'Píno', 'Primera', {
                'espesor': '1', 'ancho': '4', 'largo': '8', 'piezas': '50', 'pedimento': 'A-2',
            })
            start, end, payload, job = db.prepare_print_batch([(item, 2)], (DESIGN_NAME, 'ZPL', ZPL), printer='USB')
            self.assertEqual((start, end, db.next_folio()), (1, 1, 2))
            pending, = db.print_history('1', mode='folio')
            self.assertEqual(pending.status, 'pending')
            db.finish_print(job, 90)
            original, = db.print_history('pino', mode='product')
            self.assertEqual((original.copies, original.status), (2, 'sent'))
            date = datetime.fromisoformat(original.printed_at).strftime('%d/%m/%Y')
            self.assertEqual(db.print_history(date), [original])
            raw = re.search(rb'\^FDMA,([^\^]+)', payload)[1].replace(b'_', b'')
            scanned = bytes.fromhex(raw.decode()).decode()
            self.assertEqual(db.print_history(scanned, mode='qr'), [original])
            retry, label = db.prepare_reprint(original.id, 'USB')
            self.assertEqual(label * 2, payload)
            db.finish_print(retry)
            reprint, original_again = db.print_history(scanned, mode='qr')
            self.assertEqual(original_again, original)
            self.assertEqual((reprint.folio, reprint.reprint, reprint.copies, reprint.status), ('1', 1, 1, 'uncertain'))
            self.assertEqual(db.next_folio(), 2)

    def test_stale_import_preview_does_not_replace_products(self):
        with TemporaryDirectory() as directory:
            db = LabelStore(Path(directory) / 'labels.sqlite3')
            first, second = Item('A', 'Pino', ''), Item('B', 'MDF', '')
            db.import_products([first])
            preview = {item.sku: item for item in db.products()}
            db.import_products([second])
            with self.assertRaisesRegex(ValueError, 'El catálogo cambió'):
                db.import_products([first], replace=True, expected=preview)
            self.assertEqual({item.sku for item in db.products()}, {'A', 'B'})

    def test_imported_fields_merge_and_print_with_missing_values(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            db = LabelStore(root / 'labels.sqlite3')
            db.import_products([Item('A', 'Pino', ''), Item('B', 'Cedro', '')])
            csv = root / 'attributes.csv'
            csv.write_text('SKU,Nombre,Medida útil\nA,Pino,30 CM\nC,MDF,45 CM\n', encoding='utf-8')
            imported = read_catalog_file(csv)
            self.assertEqual(imported.fields, {'medida_util': 'Medida útil'})
            db.import_products(imported.items, fields=imported.fields)
            db.import_products([Item('A', 'Pino', '')])
            reopened = LabelStore(db.path)
            products = {item.sku: item for item in reopened.products()}
            self.assertEqual(products['A'].attributes, {'medida_util': '30 CM'})
            self.assertEqual(products['B'].attributes, {})
            self.assertEqual(products['C'].attributes, {'medida_util': '45 CM'})
            design = '^XA\n^FH^FD{{medida_util}}^FS\n^FH^FD{{folio}}^FS\n^XZ'
            reopened.save_design('Medidas', 'ZPL', design)
            self.assertEqual(missing_fields(design, [products['A'], products['B']]), {'B': ['medida_util']})
            _, _, payload = reopened.prepare_print([products['A'], products['B']], 1, ('Medidas', 'ZPL', design))
            self.assertIn(b'^FD_33_30_20_43_4D^FS', payload)
            self.assertIn(b'^FD^FS', payload)

    def test_design_rename_and_delete_persist(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.sqlite3'
            db = LabelStore(path)
            original = db.designs()[0][0]
            db.save_settings('USB', original, 41)
            db.save_design('Mi etiqueta', 'ZPL', DEFAULT_ZPL, original=original)
            self.assertEqual(db.setting('design'), 'Mi etiqueta')
            db.delete_design('Mi etiqueta')
            reopened = LabelStore(path)
            self.assertEqual(reopened.designs(), [])
            self.assertEqual(reopened.setting('design'), '')
            self.assertEqual(reopened.next_folio(), 41)

    def test_concurrent_jobs_reserve_distinct_folios(self):
        with TemporaryDirectory() as directory:
            db = LabelStore(Path(directory) / 'labels.sqlite3')
            product = Item('01', 'Madera ^XZ', 'Descripción')
            design = db.designs()[0]

            def reserve(_):
                start, end, data = db.prepare_print([product], 2, design)
                self.assertEqual(data.count(b'^XZ'), 2)
                self.assertEqual(data.count(b'^XA'), 2)
                return start, end

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(reserve, range(2))), [(1, 1), (2, 2)])
            self.assertEqual(LabelStore(db.path).next_folio(), 3)
            db.save_settings('USB', design[0], 10)
            self.assertEqual(db.prepare_print([Item('A', 'Pino', '')], 1, design)[:2], (10, 10))
            db.save_settings('USB', design[0], 1)
            self.assertEqual(LabelStore(db.path).next_folio(), 1)
            self.assertEqual(db.prepare_print([Item('A', 'Pino', '')], 2, design)[:2], (1, 1))
            self.assertEqual(db.next_folio(), 2)
            with self.assertRaisesRegex(ValueError, 'positivo'):
                db.save_settings('USB', design[0], 0)
