import asyncio
from dataclasses import replace
from datetime import datetime
import shutil
import os
from pathlib import Path
import sqlite3

import flet as ft

from occidental.help_content import (
    GUIDE, MANUAL_FILE, PUBLISHER, SUPPORT_EMAIL, SUPPORT_PHONE, TROUBLESHOOTING, VERSION, WHATSAPP_URL,
)

from occidental.labels import (
    BUILTIN_FIELDS, LABEL_FIELDS, LIMIT, PEDIMENTO_COLUMNS, LabelStore, design_fields, item_values, key, label_values,
    missing_fields, read_catalog_file, render, write_catalog_example,
)
from occidental.labelary import label_size, preview_png
from occidental.occma import FIELDS as OCCMA_FIELDS
from occidental.printers import default_printer, list_printers, printer_port, submit


APP_NAME = 'Control de impresión Accidental Maderas y Derivados'
RESOURCES = Path(__file__).resolve().with_name('resources')
INK = '#22272B'
MUTED = '#586169'
LINE = '#CDD3D9'
PAPER = '#FFFFFF'
WORKSPACE = '#FAF9F8'
CHROME = '#F3F1EF'
GRID_HEADER = '#EBE9E7'
TAB_ACTIVE = '#CCD4DE'
COMPACT_HEIGHT = 44
SOFT = '#E7EBEF'
SELECTED = '#DCE5EF'
ACCENT = '#344F69'
DANGER = '#A43332'
FIELD_HEIGHT = 56
PAGE_SIZE = 40
FIELD_STYLE = dict(height=FIELD_HEIGHT, border_radius=10, border_color='#B7B7B7',
                   focused_border_color=ACCENT, filled=True, fill_color=PAPER)
NOTICES = {
    'success': ('Operación completada', ft.Icons.CHECK_CIRCLE_OUTLINE, '#17613C', '#EDF8F1', '#B2D8BF'),
    'info': ('Información', ft.Icons.INFO_OUTLINE, '#194F85', '#EDF5FF', '#B8D4EF'),
    'warning': ('Requiere atención', ft.Icons.WARNING_AMBER_ROUNDED, '#805016', '#FFF7E7', '#EAD2A2'),
    'error': ('No se pudo completar', ft.Icons.ERROR_OUTLINE, '#932C35', '#FFF0F0', '#EAC0C4'),
}


def title(text, size=28):
    return ft.Text(text, size=size, weight=ft.FontWeight.W_700, color=INK)


def surface(content, *, expand=False, padding=18):
    return ft.Container(
        content=content, expand=expand, padding=padding, bgcolor=PAPER,
        border=ft.Border.all(1, LINE), border_radius=12,
    )


def action(text, callback, icon=None, *, primary=False, disabled=False, height=40, width=None, danger=False):
    control = ft.FilledButton if primary or danger else ft.OutlinedButton
    return control(content=text, icon=icon, on_click=callback, disabled=disabled,
                   height=height, width=width, style=ft.ButtonStyle(
                       shape=ft.RoundedRectangleBorder(radius=8),
                       bgcolor=DANGER if danger else None, color=PAPER if danger else None,
                   ))


def badge(text, *, code=False):
    return ft.Container(
        ft.Text(text, size=12, color=ACCENT, weight=ft.FontWeight.W_600,
                font_family='Consolas' if code else None, max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS, tooltip=text),
        bgcolor=SOFT, border_radius=6, padding=ft.Padding.symmetric(horizontal=9, vertical=4),
        width=220 if len(text) > 32 else None,
    )


def message_strip(text, kind):
    _, symbol, color, fill, edge = NOTICES[kind]
    return ft.Container(
        ft.Row([ft.Icon(symbol, size=19, color=color), ft.Text(text, color=color, size=13, expand=True)],
               spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
        padding=12, bgcolor=fill, border=ft.Border.all(1, edge), border_radius=8,
    )


def panel_heading(heading, icon, *, color=ACCENT):
    caption = title(heading, 20)
    caption.expand = True
    return ft.Row([ft.Icon(icon, color=color, size=21), caption], spacing=10)


def checkbox(**properties):
    return ft.Checkbox(
        fill_color={ft.ControlState.SELECTED: '#EDF4FB', ft.ControlState.DEFAULT: PAPER},
        check_color=ACCENT, border_side=ft.BorderSide(1.4, '#8394A4'),
        shape=ft.RoundedRectangleBorder(radius=4), overlay_color='#15344F69',
        **properties,
    )


def icon_action(symbol, tooltip, handler, *, danger=False):
    return ft.IconButton(
        icon=symbol, icon_size=18, tooltip=tooltip, on_click=handler, width=36, height=36,
        style=ft.ButtonStyle(color=INK, overlay_color='#16A8303A' if danger else '#14171717',
                             shape=ft.RoundedRectangleBorder(radius=8)),
    )


def form_column(controls, *, spacing=14):
    return ft.Column(controls, spacing=spacing, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                     tight=True)


def form_select(label, *, value=None, options=()):
    return ft.Dropdown(label=label, value=value, options=list(options),
                       expanded_insets=ft.Padding.all(0), **FIELD_STYLE)


def compact_field_style():
    return {**FIELD_STYLE, 'height': COMPACT_HEIGHT, 'border_radius': 7,
            'content_padding': ft.Padding.symmetric(horizontal=12, vertical=8)}


def compact_select(*, value, options):
    return ft.Dropdown(value=value, options=list(options), expanded_insets=ft.Padding.all(0),
                       **compact_field_style())


def grid_frame(content, *, expand=False):
    return ft.Container(content, expand=expand, border=ft.Border.all(1, LINE),
                        border_radius=9, clip_behavior=ft.ClipBehavior.ANTI_ALIAS)


def grid_cell(content, *, expand=None, width=None, edge=True, padding=12, visible=True):
    return ft.Container(content, expand=expand, width=width, visible=visible,
                        padding=ft.Padding.symmetric(horizontal=padding), alignment=ft.Alignment.CENTER_LEFT,
                        border=ft.Border.only(right=ft.BorderSide(1, LINE)) if edge else None)


def grid_row(cells, *, header=False, selected=False):
    return ft.Container(ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
                        height=40 if header else 43,
                        bgcolor=GRID_HEADER if header else SELECTED if selected else PAPER,
                        border=ft.Border.only(bottom=ft.BorderSide(1, LINE)))


def truncated(text):
    return ft.Text(text, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=text)


def option(value):
    return ft.DropdownOption(key=value, text=value)


class LabelApp:
    def __init__(self, page, store, products=None):
        self.page = page
        self.store = store
        self.products = store.products() if products is None else products
        self.selected = set()
        self.search = ''
        self.search_field = ''
        self.catalog_page = 0
        self.active_tab = 'Catálogo'
        self.busy = False
        self.windows_printers = []
        self.windows_default = None
        self.picker = ft.FilePicker()
        self.launcher = ft.UrlLauncher()
        self.clipboard = ft.Clipboard()
        self.page.services.extend([self.picker, self.launcher, self.clipboard])
        self.toast = ft.Container(
            visible=False, top=112, right=24, width=390, border_radius=12,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            shadow=ft.BoxShadow(color='#28171717', blur_radius=20, offset=ft.Offset(0, 5)),
        )
        self.page.overlay.append(self.toast)
        self.page.theme = ft.Theme(
            font_family='Segoe UI', color_scheme_seed=INK,
            color_scheme=ft.ColorScheme(
                primary=INK, on_primary=PAPER, primary_container=SOFT, on_primary_container=INK,
                secondary='#454545', on_secondary=PAPER, secondary_container=SOFT, on_secondary_container=INK,
                tertiary=MUTED, on_tertiary=PAPER, surface=PAPER, on_surface=INK,
                surface_container=WORKSPACE, surface_container_high=PAPER,
                on_surface_variant=MUTED, outline='#868686', outline_variant=LINE,
                error=INK, on_error=PAPER, error_container=SOFT, on_error_container=INK,
            ),
        )
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.bgcolor = WORKSPACE
        self.page.padding = 0
        self.page.spacing = 0
        self.content = ft.Column(expand=True, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.menu = ft.Row(spacing=14)
        self.toolbar = ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.toolbar_band = ft.Container(self.toolbar, height=58, padding=ft.Padding.symmetric(horizontal=22),
                                         bgcolor=CHROME, border=ft.Border.only(bottom=ft.BorderSide(1, LINE)))
        self.catalog()
        self.draw_navigation()
        self.page.on_resize = self.resize_catalog
        self.page.add(
            ft.Container(self.menu, height=58, padding=ft.Padding.symmetric(horizontal=22),
                         bgcolor=CHROME, border=ft.Border.only(bottom=ft.BorderSide(1, LINE))),
            self.toolbar_band,
            ft.Container(self.content, expand=True, padding=ft.Padding.all(22), bgcolor=WORKSPACE),
        )

    def dismiss_notice(self, _):
        self.toast.visible = False
        self.toast.content = None
        self.page.update()

    def notice(self, message, *, kind='success', heading=None):
        caption, symbol, color, _, border = NOTICES[kind]
        self.toast.bgcolor = PAPER
        self.toast.border = ft.Border.all(1, border)
        notification = ft.Row([
            ft.Icon(symbol, size=23, color=color),
            ft.Column([
                ft.Text(heading or caption, color=color, size=14, weight=ft.FontWeight.W_700,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, tooltip=heading or caption),
                ft.Text(message, color=MUTED, size=13, max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=message),
            ], spacing=3, expand=True),
            icon_action(ft.Icons.CLOSE, 'Cerrar notificación', self.dismiss_notice),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)
        self.toast.content = notification
        self.toast.visible = True
        self.page.update()
        self.page.run_task(self.expire_notice, notification, 9 if kind in ('warning', 'error') else 5)

    async def expire_notice(self, notification, seconds):
        await asyncio.sleep(seconds)
        if self.toast.content is notification:
            self.dismiss_notice(None)

    def close(self):
        self.page.pop_dialog()

    def dialog(self, heading, content, actions, *, max_height=None, footer_gap=0):
        vertical_inset = max(24, ((self.page.height or 0) - max_height) / 2) if max_height else 24
        symbol = next((icon for prefix, icon in (
            ('Borrar', ft.Icons.DELETE_OUTLINE), ('Editar', ft.Icons.EDIT_OUTLINED),
            ('Preparar', ft.Icons.PRINT_OUTLINED), ('Revisar importación', ft.Icons.UPLOAD_FILE_OUTLINED),
            ('Columnas', ft.Icons.VIEW_COLUMN_OUTLINED), ('Hay variables', ft.Icons.WARNING_AMBER_ROUNDED),
            ('Ver', ft.Icons.VISIBILITY_OUTLINED), ('Nuevo', ft.Icons.POST_ADD),
            ('Confirmar', ft.Icons.LABEL_OUTLINE),
        ) if heading.startswith(prefix)), ft.Icons.INFO_OUTLINE)
        heading_color = (DANGER if heading.startswith('Borrar') else
                         NOTICES['warning'][2] if heading.startswith('Hay variables') else ACCENT)
        dialog = ft.AlertDialog(
            modal=True, title=ft.Container(
                panel_heading(heading, symbol, color=heading_color), bgcolor=WORKSPACE,
                padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                border=ft.Border.only(bottom=ft.BorderSide(1, LINE)),
            ), content=content, bgcolor=PAPER,
            scrollable=True, inset_padding=ft.Padding.symmetric(horizontal=40, vertical=vertical_inset),
            title_padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, barrier_color='#660F1720',
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=16),
            actions_padding=ft.Padding.only(left=16, top=footer_gap, right=16, bottom=16),
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=actions, actions_alignment=ft.MainAxisAlignment.END, actions_overflow_button_spacing=8,
        )
        self.page.show_dialog(dialog)
        return dialog

    def navigate(self, tab):
        self.active_tab = tab
        {'Catálogo': self.catalog, 'Diseños': self.designs, 'Historial': self.history,
         'Configuración': self.settings, 'Ayuda': self.help_page}[tab]()
        self.draw_navigation()
        self.page.update()
        if tab == 'Configuración':
            self.page.run_task(self.discover_printers, None, quiet=True)

    def area_action(self, area, callback):
        if self.active_tab != area:
            self.navigate(area)
        return callback()

    def open_catalog_search(self):
        self.page.run_task(self.search_box.focus)

    def print_selected(self, _):
        self.prepare([item for item in self.products if item.sku in self.selected])

    def draw_navigation(self):
        areas = (
            ('Catálogo', ft.Icons.LAYERS_OUTLINED),
            ('Diseños', ft.Icons.LOCAL_OFFER_OUTLINED),
            ('Historial', ft.Icons.HISTORY),
            ('Configuración', ft.Icons.SETTINGS_OUTLINED),
            ('Ayuda', ft.Icons.HELP_OUTLINE),
        )
        self.menu.controls = [
            ft.Row([title('OM', 24), ft.VerticalDivider(width=12, color=LINE),
                    title('Occidental Maderas', 14)], spacing=4, height=38),
        ] + [
            ft.TextButton(content=area, icon=icon, height=40,
                          style=ft.ButtonStyle(color=INK, bgcolor=TAB_ACTIVE if area == self.active_tab else None,
                                               shape=ft.RoundedRectangleBorder(radius=7)),
                          on_click=lambda _, area=area: self.navigate(area))
            for area, icon in areas
        ]
        selected = [item for item in self.products if item.sku in self.selected]
        single = selected[0] if len(selected) == 1 else None

        def command(label, icon, handler, *, disabled=False):
            return ft.TextButton(content=label, icon=icon, on_click=handler, disabled=disabled,
                                 style=ft.ButtonStyle(color={ft.ControlState.DEFAULT: INK,
                                                             ft.ControlState.DISABLED: '#777777'}))

        def rule():
            return ft.VerticalDivider(width=15, thickness=1, color=LINE)

        if self.active_tab == 'Catálogo':
            self.toolbar.controls = [
                ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ, tooltip='Más acciones del catálogo', items=[
                    ft.PopupMenuItem(content='Actualizar', icon=ft.Icons.REFRESH,
                                     on_click=lambda _: self.refresh_products()),
                    ft.PopupMenuItem(content='Editar', icon=ft.Icons.EDIT_OUTLINED,
                                     disabled=single is None, on_click=lambda _: self.edit_product(single)),
                    ft.PopupMenuItem(content='Duplicar', icon=ft.Icons.CONTENT_COPY_OUTLINED,
                                     disabled=single is None, on_click=lambda _: self.edit_product(single, duplicate=True)),
                    ft.PopupMenuItem(content='Importar Excel o CSV', icon=ft.Icons.UPLOAD_FILE_OUTLINED,
                                     on_click=self.import_catalog),
                    ft.PopupMenuItem(content='Descargar plantilla', icon=ft.Icons.DOWNLOAD_OUTLINED,
                                     on_click=self.download_example),
                    ft.PopupMenuItem(content='Buscar productos', icon=ft.Icons.SEARCH,
                                     on_click=lambda _: self.open_catalog_search()),
                    ft.PopupMenuItem(content='Seleccionar resultados', on_click=lambda _: self.select_results(self.filtered)),
                    ft.PopupMenuItem(content='Limpiar selección', on_click=self.clear_selection),
                ]),
            ]
        elif self.active_tab == 'Diseños':
            self.toolbar.controls = [
                action('Nuevo diseño', lambda _: self.design_editor(), ft.Icons.ADD, primary=True),
                rule(),
                command('Actualizar', ft.Icons.REFRESH, lambda _: self.navigate('Diseños')),
            ]
        else:
            self.toolbar.controls = []
        self.toolbar_band.visible = bool(self.toolbar.controls) and self.active_tab != 'Catálogo'
        if self.active_tab == 'Catálogo':
            self.catalog_commands.controls = list(self.toolbar.controls)
            self.toolbar.controls = []

    def catalog(self):
        self.fields = self.store.catalog_fields()
        self.hidden_columns = self.store.hidden_catalog_columns()
        self.occma_catalog = bool(self.products) and all(
            OCCMA_FIELDS.keys() <= item.attributes.keys() for item in self.products
        )
        catalog_fields = self.fields
        if self.occma_catalog:
            catalog_fields = {**OCCMA_FIELDS, **self.fields}
            catalog_fields = {field: label for field, label in catalog_fields.items()
                              if field in OCCMA_FIELDS or
                              any(field in item.attributes for item in self.products)}
        self.column_labels = ({'descripcion': 'Clase'} if self.occma_catalog else
                              {'nombre': 'Nombre', 'descripcion': 'Descripción'}) | catalog_fields
        self.table_fields = [field for field in catalog_fields if field not in self.hidden_columns]
        search_fields = {'sku': 'SKU', **self.column_labels}
        if self.search_field not in search_fields:
            self.search_field = ''
        self.search_box = ft.TextField(
            value=self.search, hint_text='Buscar clase o medida…' if self.occma_catalog else
            'Buscar producto, SKU o descripción…', expand=True,
            prefix_icon=ft.Icons.SEARCH, **compact_field_style(),
            on_change=self.filter_catalog,
        )
        field_filter = compact_select(value=self.search_field, options=[
            ft.DropdownOption(key='', text='Todos'),
            *[ft.DropdownOption(key=field, text=label) for field, label in search_fields.items()],
        ])
        field_filter.width = 160

        def change_filter(event):
            self.search_field = event.control.value or ''
            self.catalog_page = 0
            self.change_page(0)

        field_filter.on_select = change_filter
        self.catalog_rows = ft.Column(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO)
        self.catalog_commands = ft.Row(tight=True)
        self.selection_count = title('', 14)
        self.batch_print = action('Imprimir lote', self.print_selected, ft.Icons.PRINT_OUTLINED, primary=True)
        self.batch_delete = action('Borrar seleccionados', self.confirm_delete_selected, ft.Icons.DELETE_OUTLINE)
        self.pagination = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.page_checkbox = checkbox(tooltip='Seleccionar página', on_change=self.toggle_page_selection)
        header = self.product_row(self.page_checkbox, title('SKU', 13), title('Producto', 13),
                                  title(self.column_labels['descripcion'], 13), title('Acciones', 13),
                                  extras=[truncated(self.fields[field]) for field in self.table_fields], header=True)
        self.catalog_grid = grid_frame(ft.Column([header, self.catalog_rows], spacing=0))
        if self.table_fields:
            self.wide_table = ft.Container(self.catalog_grid, width=self.catalog_table_width())
            table = ft.Row([self.wide_table], scroll=ft.ScrollMode.AUTO,
                           vertical_alignment=ft.CrossAxisAlignment.START)
        else:
            self.wide_table = None
            table = self.catalog_grid
        self.content.controls = [
            ft.Row([ft.Container(title('Catálogo de productos', 30), expand=True),
                    action('Importar Excel o CSV', self.import_catalog, ft.Icons.UPLOAD_FILE_OUTLINED),
                    self.catalog_commands],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.search_box, ft.Text('Buscar en:'), field_filter,
                    action('Columnas', self.choose_columns, ft.Icons.VIEW_COLUMN_OUTLINED,
                           height=COMPACT_HEIGHT)],
                   spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                ft.Row([self.selection_count, self.batch_print, self.batch_delete],
                       spacing=14, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=SOFT, border_radius=7, padding=ft.Padding.symmetric(horizontal=12, vertical=5),
            ),
            ft.Container(
                ft.Column([table], horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                          scroll=ft.ScrollMode.AUTO),
                expand=True, clip_behavior=ft.ClipBehavior.HARD_EDGE, bgcolor=WORKSPACE,
            ),
            ft.Container(self.pagination, border=ft.Border.only(top=ft.BorderSide(1, LINE)),
                         bgcolor=WORKSPACE, padding=ft.Padding.only(top=12)),
        ]
        self.draw_products()

    def catalog_table_width(self):
        minimum = (350 if self.occma_catalog else 690) + 116 * len(self.table_fields)
        return max((self.page.width or 1200) - 44, minimum)

    def choose_columns(self, _):
        labels = self.column_labels
        choices = {field: checkbox(label=ft.Text(label, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                                tooltip=label), value=field not in self.hidden_columns)
                   for field, label in labels.items()}

        def save(_):
            self.store.save_hidden_catalog_columns(field for field, box in choices.items() if not box.value)
            self.close()
            self.navigate('Catálogo')

        self.dialog('Columnas del catálogo', ft.Container(form_column([
            ft.Text('Elige las columnas que quieres mostrar.', color=MUTED),
            *choices.values(),
        ]), width=380), [
            action('Cancelar', lambda _: self.close()),
            action('Aplicar', save, primary=True),
        ], max_height=520)

    def resize_catalog(self, _):
        if self.active_tab == 'Catálogo':
            if self.wide_table is not None:
                self.wide_table.width = self.catalog_table_width()
            self.size_catalog_grid()
            self.page.update()

    def size_catalog_grid(self):
        rows_height = 43 * len(self.visible_products) if self.visible_products else 68
        available = (self.page.height or 720) - 340
        self.catalog_grid.height = min(42 + rows_height, max(110, available))

    def product_row(self, mark, sku, name, description, operation, *, extras=(), header=False, selected=False):
        cells = [grid_cell(mark, width=52, padding=4), grid_cell(sku, expand=2, visible=not self.occma_catalog),
                 grid_cell(name, expand=2, visible=not self.occma_catalog and 'nombre' not in self.hidden_columns),
                 grid_cell(description, expand=4, visible='descripcion' not in self.hidden_columns),
                 *[grid_cell(value, width=116) for value in extras],
                 grid_cell(operation, width=104, edge=False)]
        return grid_row(cells, header=header, selected=selected)

    def toggle_page_selection(self, event):
        page_skus = {item.sku for item in self.visible_products}
        if event.control.value:
            self.selected.update(page_skus)
        else:
            self.selected.difference_update(page_skus)
        self.change_page(0)

    def filter_catalog(self, event):
        self.search = event.control.value or ''
        self.catalog_page = 0
        self.change_page(0)

    def draw_products(self):
        term = key(self.search)
        def matches(item):
            values = item_values(item)
            searchable = (value for field, value in values.items() if field not in PEDIMENTO_COLUMNS)
            return term in key(values.get(self.search_field, '') if self.search_field else ' '.join(searchable))

        shown = [item for item in self.products if matches(item)]
        last_page = max(0, (len(shown) - 1) // PAGE_SIZE)
        self.catalog_page = min(self.catalog_page, last_page)
        start = self.catalog_page * PAGE_SIZE
        visible = shown[start:start + PAGE_SIZE]
        self.filtered, self.visible_products = shown, visible
        self.size_catalog_grid()
        self.page_checkbox.disabled = not visible
        self.page_checkbox.value = bool(visible) and all(item.sku in self.selected for item in visible)
        rows = [
            self.product_row(
                checkbox(value=item.sku in self.selected, tooltip=f'Seleccionar {item.sku}',
                         on_change=lambda event, sku=item.sku: self.mark(sku, event.control.value)),
                truncated(item.sku), truncated(item.name), truncated(item.description),
                ft.Row([
                    icon_action(ft.Icons.EDIT_OUTLINED, 'Editar producto',
                                lambda _, item=item: self.edit_product(item)),
                    icon_action(ft.Icons.DELETE_OUTLINE, 'Borrar producto',
                                lambda _, item=item: self.confirm_delete_product(item), danger=True),
                ], spacing=3),
                extras=[truncated(item.attributes.get(field, '')) for field in self.table_fields],
                selected=item.sku in self.selected,
            ) for item in visible
        ]
        self.catalog_rows.controls = rows or [
            ft.Container(ft.Text('No hay resultados.' if self.search else 'Importa un catálogo de Excel o CSV para comenzar.',
                                 color=MUTED), padding=22)
        ]
        summary = f'{start + 1}–{start + len(visible)} de {len(shown)}' if visible else '0 productos'
        count = len(self.selected)
        self.selection_count.value = '1 producto seleccionado' if count == 1 else f'{count} productos seleccionados'
        self.batch_print.disabled = self.batch_delete.disabled = not count
        self.pagination.controls = [
            ft.Text(summary, color=MUTED),
            ft.Row([
                action('', lambda _: self.change_page(-1), ft.Icons.CHEVRON_LEFT,
                       disabled=self.catalog_page == 0, height=36),
                ft.Container(ft.Text(str(self.catalog_page + 1), color=INK), width=38, height=36,
                             border_radius=7, bgcolor=TAB_ACTIVE, alignment=ft.Alignment.CENTER),
                action('', lambda _: self.change_page(1), ft.Icons.CHEVRON_RIGHT,
                       disabled=self.catalog_page == last_page, height=36),
            ], spacing=7),
        ]

    def change_page(self, step):
        self.catalog_page += step
        self.draw_products()
        self.draw_navigation()
        self.page.update()

    def mark(self, sku, checked):
        if checked:
            self.selected.add(sku)
        else:
            self.selected.discard(sku)
        self.change_page(0)

    def select_page(self, items):
        self.selected.update(item.sku for item in items)
        self.change_page(0)

    def select_results(self, items):
        self.selected = {item.sku for item in items}
        self.change_page(0)

    def clear_selection(self, _):
        self.selected.clear()
        self.change_page(0)

    def refresh_products(self):
        self.products = self.store.products()
        self.selected.intersection_update(item.sku for item in self.products)
        self.change_page(0)

    def edit_product(self, item, *, duplicate=False):
        heading = 'Duplicar producto' if duplicate else 'Editar producto'
        sku = ft.TextField(label='SKU', value='' if duplicate else item.sku, **FIELD_STYLE)
        name = ft.TextField(label='Nombre', value=item.name, **FIELD_STYLE)
        is_occma = OCCMA_FIELDS.keys() <= item.attributes.keys()
        description = ft.TextField(label='Clase' if is_occma else 'Descripción', value=item.description, **FIELD_STYLE)
        extras = {field: ft.TextField(label=label, value=item.attributes.get(field, ''), **FIELD_STYLE)
                  for field, label in self.fields.items()}
        error = ft.Text('', color=NOTICES['error'][2], size=13)

        def save(_):
            try:
                values = (sku.value or '', (description if is_occma else name).value or '', description.value or '')
                attributes = {field: (entry.value or '').strip() for field, entry in extras.items()}
                if duplicate:
                    updated_sku = self.store.create_product(*values, attributes=attributes)
                else:
                    updated_sku = self.store.update_product(item.sku, *values, attributes=attributes)
            except (ValueError, sqlite3.Error) as exc:
                error.value = 'Ese SKU ya está en el catálogo.' if isinstance(exc, sqlite3.IntegrityError) else str(exc)
                self.page.update()
                return
            if not duplicate and item.sku in self.selected:
                self.selected.discard(item.sku)
                self.selected.add(updated_sku)
            self.close()
            self.refresh_products()
            self.notice(f'Se guardó {updated_sku} en el catálogo.',
                        heading='Producto duplicado' if duplicate else 'Producto actualizado')

        content = ft.Container(
            width=540, height=550, bgcolor=PAPER,
            content=ft.Column([
                ft.Container(panel_heading(heading, ft.Icons.CONTENT_COPY_OUTLINED if duplicate else
                                           ft.Icons.EDIT_OUTLINED), bgcolor=WORKSPACE,
                             padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                             border=ft.Border.only(bottom=ft.BorderSide(1, LINE))),
                ft.Container(ft.Column(
                    [sku, *([] if is_occma else [name]), description, *extras.values(), error],
                    spacing=10, scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ), expand=True, padding=ft.Padding.symmetric(horizontal=20, vertical=12)),
                ft.Container(ft.Row([
                    action('Cancelar', lambda _: self.close()),
                    action('Guardar cambios', save, ft.Icons.SAVE_OUTLINED, primary=True),
                ], alignment=ft.MainAxisAlignment.END, wrap=True),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    border=ft.Border.only(top=ft.BorderSide(1, LINE))),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )
        self.page.show_dialog(ft.AlertDialog(
            modal=True, semantics_label=heading, content=content, content_padding=0,
            bgcolor=PAPER, shape=ft.RoundedRectangleBorder(radius=12),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS, barrier_color='#660F1720',
        ))

    def confirm_delete_selected(self, _):
        skus = tuple(sorted(self.selected))
        if not skus:
            return
        problem = ft.Text('', color=NOTICES['error'][2], size=13, visible=False)

        async def delete(_):
            if confirm.disabled:
                return
            confirm.disabled = True
            cancel.disabled = True
            self.page.update()
            try:
                count = await asyncio.to_thread(self.store.delete_products, skus)
            except (ValueError, sqlite3.Error) as exc:
                problem.value = str(exc)
                problem.visible = True
                confirm.disabled = False
                cancel.disabled = False
                self.page.update()
                return
            self.close()
            self.refresh_products()
            self.notice(f'Se eliminaron {count} productos del catálogo.', heading='Lote eliminado')

        cancel = action('Cancelar', lambda _: self.close())
        confirm = action('Borrar seleccionados', delete, ft.Icons.DELETE_OUTLINE, danger=True)
        self.dialog('Borrar productos seleccionados', ft.Container(form_column([
            ft.Text(f'¿Quieres borrar {len(skus)} productos del catálogo?'),
            ft.Row([*[badge(sku, code=True) for sku in skus[:8]],
                    *([ft.Text(f'+{len(skus) - 8} más', color=MUTED)] if len(skus) > 8 else [])],
                   wrap=True),
            message_strip('Esta acción no se puede deshacer.', 'error'),
            problem,
        ]), width=460), [cancel, confirm])

    def confirm_delete_product(self, item):
        def delete(_):
            try:
                self.store.delete_product(item.sku)
            except (ValueError, sqlite3.Error) as exc:
                problem.value = str(exc)
                self.page.update()
                return
            self.close()
            self.refresh_products()
            self.notice(f'{item.name} ({item.sku}) se retiró del catálogo.', heading='Producto eliminado')

        problem = ft.Text('', color=NOTICES['error'][2], size=13)
        self.dialog('Borrar producto', ft.Container(form_column([
            ft.Text(item.name), ft.Row([badge(item.sku, code=True)]),
            message_strip('El producto se eliminará del catálogo.', 'error'), problem,
        ]), width=440), [
            action('Cancelar', lambda _: self.close()),
            action('Borrar producto', delete, ft.Icons.DELETE_OUTLINE, danger=True),
        ])

    async def download_example(self, _):
        try:
            path = await self.picker.save_file(file_name='Plantilla_Productos.xlsx',
                                               file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['xlsx'])
            if path:
                destination = Path(path)
                if destination.suffix.lower() != '.xlsx':
                    destination = destination.with_suffix('.xlsx')
                await asyncio.to_thread(write_catalog_example, destination)
                self.notice(f'Plantilla guardada en {destination}.')
        except Exception as error:
            self.notice(str(error), kind='error', heading='La plantilla no se guardó')

    async def import_catalog(self, _):
        try:
            picked = await self.picker.pick_files(file_type=ft.FilePickerFileType.CUSTOM,
                                                  allowed_extensions=['xlsx', 'csv'])
            if not picked:
                return
            imported = await asyncio.to_thread(read_catalog_file, Path(picked[0].path))
        except Exception as error:
            self.notice(str(error), kind='error', heading='Error al leer el catálogo')
            return
        items = imported.items
        registered = self.store.catalog_fields()
        new_fields = {field: label for field, label in imported.fields.items() if field not in registered}
        existing = {item.sku: item for item in self.store.products()}

        async def apply_import(replace):
            self.close()
            try:
                await asyncio.to_thread(self.store.import_products, items, replace=replace,
                                        fields=imported.fields, expected=existing)
                self.products = self.store.products()
                if replace:
                    self.selected.clear()
                self.navigate('Catálogo')
                self.notice(f'Catálogo actualizado. {len(self.products):,} productos disponibles.')
            except Exception as error:
                self.notice(str(error), kind='error', heading='La importación no se guardó')

        def choose_import():
            mode = form_select('Modo de importación', value='merge', options=[
                ft.DropdownOption(key='merge', text='Agregar y actualizar'),
                ft.DropdownOption(key='replace', text='Reemplazar catálogo'),
            ])
            group = form_select('Mostrar', value='new', options=[
                ft.DropdownOption(key='new', text='Productos nuevos'),
                ft.DropdownOption(key='changed', text='Productos con cambios'),
                ft.DropdownOption(key='removed', text='Productos que se retirarán'),
            ])
            counts = [ft.Text('0', size=22, color=INK, weight=ft.FontWeight.W_700) for _ in range(3)]
            position = ft.Text(color=MUTED)
            rows = form_column([], spacing=8)
            labels = {**BUILTIN_FIELDS, **registered, **imported.fields}
            page_index = 0
            incoming_skus = {item.sku for item in items}

            def change_row(field, before, after, *, header=False):
                return ft.Container(ft.Row([
                    ft.Text(field, expand=2, size=13, color=INK if header else MUTED),
                    ft.Text(before, expand=3, size=13, selectable=not header),
                    ft.Container(ft.Icon(ft.Icons.ARROW_FORWARD, size=14, color=MUTED,
                                         opacity=0 if header else 1), width=18),
                    ft.Text(after, expand=3, size=13, selectable=not header),
                ], vertical_alignment=ft.CrossAxisAlignment.START), bgcolor=SOFT if header else PAPER,
                   padding=8, border=ft.Border.only(bottom=ft.BorderSide(1, LINE)))

            def record_row(sku, detail):
                if group.value == 'changed':
                    contents = [change_row('Campo', 'Anterior', 'Nuevo', header=True),
                                *[change_row(*difference) for difference in detail]]
                else:
                    contents = [ft.Text(detail, color=MUTED, selectable=True, size=13)]
                return surface(form_column([title(sku, 13), *contents], spacing=4), padding=9)

            def draw():
                nonlocal page_index
                replace = mode.value == 'replace'
                additions, changes, removals = [], [], []
                for item in items:
                    if item.sku not in existing:
                        additions.append((item.sku, item.name))
                        continue
                    before = item_values(existing[item.sku])
                    after = item_values(item)
                    if not replace:
                        after = {**before, **after}
                    differences = [
                        (labels.get(field, field), before.get(field) or 'Vacío', after.get(field) or 'Vacío')
                        for field in dict.fromkeys([*before, *after])
                        if before.get(field, '') != after.get(field, '')
                    ]
                    if differences:
                        changes.append((item.sku, differences))
                if replace:
                    removals = [(sku, item.name) for sku, item in existing.items() if sku not in incoming_skus]
                for control, group_rows in zip(counts, (additions, changes, removals)):
                    control.value = str(len(group_rows))
                visible = {'new': additions, 'changed': changes, 'removed': removals}[group.value]
                last = max(0, (len(visible) - 1) // 12)
                page_index = min(page_index, last)
                rows.controls = [
                    record_row(sku, detail)
                    for sku, detail in visible[page_index * 12:(page_index + 1) * 12]
                ] or [ft.Text('Sin registros en este grupo.', color=MUTED)]
                position.value = f'{page_index + 1} de {last + 1}'
                previous.disabled, forward.disabled = page_index == 0, page_index >= last
                apply_button.content = 'Reemplazar catálogo' if replace else 'Agregar y actualizar'
                self.page.update()

            def paginate(step):
                nonlocal page_index
                page_index = max(0, page_index + step)
                draw()

            def reset(_):
                nonlocal page_index
                page_index = 0
                draw()

            async def apply(_):
                await apply_import(mode.value == 'replace')

            previous = icon_action(ft.Icons.CHEVRON_LEFT, 'Página anterior', lambda _: paginate(-1))
            forward = icon_action(ft.Icons.CHEVRON_RIGHT, 'Página siguiente', lambda _: paginate(1))
            apply_button = action('Agregar y actualizar', apply, primary=True)
            mode.on_select = group.on_select = reset
            mode.expand = group.expand = True
            self.dialog('Revisar importación', ft.Container(form_column([
                ft.Row([mode, group], spacing=12),
                ft.Row([
                    surface(form_column([ft.Text(label, color=MUTED, size=12), count], spacing=3),
                            expand=True, padding=11)
                    for label, count in zip(('Nuevos', 'Cambios', 'Retiros'), counts)
                ], spacing=10),
                ft.Row([previous, position, forward], alignment=ft.MainAxisAlignment.END), rows,
            ]), width=680), [
                action('Cancelar', lambda _: self.close()),
                apply_button,
            ], max_height=650)
            draw()

        def accept_fields(_):
            self.close()
            choose_import()

        if new_fields:
            self.dialog('Confirmar nuevas variables', ft.Container(form_column([
                ft.Text('Se agregarán estas columnas al catálogo y estarán disponibles en los diseños. Los productos sin valor conservarán el campo vacío.'),
                *[ft.Container(ft.Row([ft.Text(label, expand=True), badge('{{' + field + '}}', code=True)],
                                     vertical_alignment=ft.CrossAxisAlignment.START),
                               padding=9, bgcolor=WORKSPACE, border_radius=6)
                  for field, label in new_fields.items()],
            ]), width=500), [
                action('Cancelar importación', lambda _: self.close()),
                action('Incluir variables', accept_fields, primary=True),
            ], max_height=520)
        else:
            choose_import()

    def designs(self):
        def row(name, language, actions, *, header=False):
            return grid_row([grid_cell(name, expand=3), grid_cell(language, expand=1),
                             grid_cell(actions, width=148, edge=False)], header=header)

        rows = []
        for record in self.store.designs():
            name, language, _ = record
            rows.append(row(truncated(name), ft.Row([ft.Container(ft.Text(language, size=12, color=INK), bgcolor=TAB_ACTIVE,
                                                      padding=ft.Padding.symmetric(horizontal=13, vertical=3),
                                                      border_radius=20)]), ft.Row([
                icon_action(ft.Icons.VISIBILITY_OUTLINED, 'Ver diseño',
                            lambda _, record=record: self.design_editor(record, view=True)),
                icon_action(ft.Icons.EDIT_OUTLINED, 'Editar diseño',
                            lambda _, record=record: self.design_editor(record)),
                icon_action(ft.Icons.DELETE_OUTLINE, 'Borrar diseño',
                            lambda _, name=name: self.confirm_delete(name), danger=True),
            ], spacing=3)))
        header = row(title('Nombre', 13), title('Lenguaje', 13), title('Acciones', 13), header=True)
        self.content.controls = [
            title('Diseños de etiquetas', 28),
            ft.Column([grid_frame(ft.Column([
                header, *rows,
                *([] if rows else [ft.Container(ft.Text('Todavía no hay diseños.', color=MUTED), padding=14)]),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))],
                      expand=True, scroll=ft.ScrollMode.AUTO,
                      horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        ]

    def design_editor(self, record=None, *, view=False):
        original, language, source = record or (None, 'ZPL', '')
        name = ft.TextField(label='Nombre', value=original or '', read_only=view, **FIELD_STYLE)
        format_box = form_select('Lenguaje', value=language, options=[option('ZPL'), option('TSPL')])
        format_box.disabled = view
        field = ft.TextField(label='Código de impresión', multiline=True, min_lines=3, max_lines=12,
                             value=source, read_only=view, bgcolor='#242A30', border_radius=8,
                             border_color='#414B54', focused_border_color='#7896B4',
                             color='#F1F4F6', cursor_color='#F1F4F6',
                             label_style=ft.TextStyle(color='#ADBCCB'),
                             text_style=ft.TextStyle(font_family='Consolas', size=14))
        error = ft.Text('', color=NOTICES['error'][2], weight=ft.FontWeight.W_600)

        async def load(_):
            try:
                picked = await self.picker.pick_files(file_type=ft.FilePickerFileType.CUSTOM,
                                                      allowed_extensions=['zpl', 'tspl', 'txt'])
                if picked:
                    path = Path(picked[0].path)
                    field.value = path.read_text(encoding='utf-8-sig')
                    if not name.value:
                        name.value = path.stem
                    if path.suffix.lower() in {'.zpl', '.tspl'}:
                        format_box.value = path.suffix[1:].upper()
                    self.page.update()
            except Exception as exc:
                error.value = str(exc)
                self.page.update()

        def save(_):
            try:
                self.store.save_design(name.value or '', format_box.value, field.value or '', original=original)
            except (ValueError, sqlite3.Error) as exc:
                error.value = 'Ya existe un diseño con ese nombre.' if isinstance(exc, sqlite3.IntegrityError) else str(exc)
                self.page.update()
                return
            self.close()
            self.navigate('Diseños')
            self.notice('Diseño guardado.')

        available = {**BUILTIN_FIELDS, **LABEL_FIELDS, **self.store.catalog_fields()}
        format_box.expand = not view
        language_row = (format_box if view else
                        ft.Row([format_box, action('Cargar archivo', load, ft.Icons.UPLOAD_FILE,
                                                   height=FIELD_HEIGHT)], spacing=12))
        fields = [name, language_row, field, title('Variables', 13),
                  ft.Row([badge('{{' + field + '}}', code=True) for field in available], wrap=True), error]
        buttons = [action('Cerrar' if view else 'Cancelar', lambda _: self.close())]
        if not view:
            buttons.append(action('Guardar diseño', save, primary=True))
        self.dialog('Ver diseño' if view else ('Editar diseño' if record else 'Nuevo diseño'),
                    ft.Container(form_column(fields), width=590), buttons)

    def confirm_delete(self, name):
        def delete(_):
            try:
                self.store.delete_design(name)
            except sqlite3.Error as exc:
                self.notice(str(exc), kind='error', heading='El diseño no se pudo borrar')
                return
            self.close()
            self.navigate('Diseños')
            self.notice('Diseño eliminado.')
        self.dialog('Borrar diseño', ft.Container(form_column([
            ft.Text(f'¿Quieres eliminar «{name}»?'),
            message_strip('Esta acción no se puede deshacer.', 'error'),
        ]), width=430), [
            action('Cancelar', lambda _: self.close()),
            action('Borrar diseño', delete, danger=True),
        ])

    async def load_printers(self):
        found, default = await asyncio.gather(asyncio.to_thread(list_printers),
                                              asyncio.to_thread(default_printer))
        self.windows_printers = [item['pPrinterName'] for item in found]
        self.windows_default = default if default in self.windows_printers else None

    def printer_options(self, saved=None):
        options = [ft.DropdownOption(key=name, text=f'{name} · Predeterminada de Windows'
                   if name == self.windows_default else name) for name in self.windows_printers]
        if saved and saved not in self.windows_printers:
            options.insert(0, option(saved))
        return options

    def settings(self):
        current = self.store.setting('printer')
        printers = compact_select(value=current or self.windows_default,
                               options=self.printer_options(current))
        port = ft.Text('Buscando impresoras instaladas…', color=MUTED, size=13, expand=True)
        designs = self.store.designs()
        names = [record[0] for record in designs]
        default = self.store.setting('design', 'Etiqueta base ZPL')
        template = compact_select(value=default if default in names else None,
                               options=[option(name) for name in names])
        next_folio = ft.TextField(value=str(self.store.next_folio()), keyboard_type=ft.KeyboardType.NUMBER,
                                 **compact_field_style())
        port_icon = ft.Icon(ft.Icons.INFO_OUTLINE, color=ACCENT, size=19)

        async def update_port(_=None):
            selected = printers.value
            port_icon.name, port_icon.color = ft.Icons.INFO_OUTLINE, ACCENT
            if not selected:
                port.value = 'Selecciona una impresora instalada.' if self.windows_printers else 'Windows no devolvió impresoras instaladas.'
                self.page.update()
                return
            if selected not in self.windows_printers:
                port.value = 'La impresora guardada no está disponible. Puedes elegir otra o volver a buscar.'
                self.page.update()
                return
            try:
                value = await asyncio.to_thread(printer_port, selected)
                if selected == printers.value:
                    port.value = f'Cola instalada en Windows · Puerto {value}' if value else 'La cola no informó su puerto.'
                    if value:
                        port_icon.name, port_icon.color = ft.Icons.CHECK_CIRCLE, NOTICES['success'][2]
            except Exception as exc:
                if selected == printers.value:
                    port.value = f'No se pudo consultar el puerto: {exc}'
            self.page.update()

        printers.on_select = update_port

        async def discover(_, *, quiet=False):
            try:
                await self.load_printers()
                if self.discover_printers is not discover or self.active_tab != 'Configuración':
                    return
                selected = printers.value or self.windows_default
                printers.options = self.printer_options(selected)
                printers.value = selected
                await update_port()
                if not quiet and self.active_tab == 'Configuración':
                    self.notice(f'{len(self.windows_printers)} colas disponibles.', kind='info', heading='Impresoras actualizadas')
            except Exception as exc:
                if self.discover_printers is discover and self.active_tab == 'Configuración':
                    port.value = 'Windows no pudo completar la búsqueda de impresoras.'
                    self.notice(str(exc), kind='error', heading='No se pudieron consultar las impresoras')

        def save(_):
            try:
                value = (next_folio.value or '').strip()
                if not value.isascii() or not value.isdecimal() or len(value) > 18:
                    raise ValueError('Escribe el siguiente folio como un número entero positivo.')
                self.store.save_settings(printers.value or '', template.value or '', int(value))
                self.notice('Se actualizaron la impresora, el diseño y el siguiente folio.',
                            heading='Configuración guardada')
            except (ValueError, sqlite3.Error) as exc:
                self.notice(str(exc), kind='error', heading='Configuración sin guardar')

        self.discover_printers = discover
        self.save_preferences = save
        def setting_row(label, control):
            control.expand = True
            return ft.Row([ft.Container(title(label, 14), width=218), control],
                          vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16)

        form = form_column([
            setting_row('Impresora', printers),
            setting_row('Diseño predeterminado', template),
            setting_row('Siguiente folio', next_folio),
            ft.Divider(height=14, thickness=1, color=LINE),
            ft.Row([port_icon, port,
                    icon_action(ft.Icons.REFRESH, 'Actualizar impresoras', discover)]),
            ft.Row([action('Guardar configuración', save, ft.Icons.SAVE_OUTLINED, primary=True)],
                   alignment=ft.MainAxisAlignment.CENTER),
        ], spacing=10)
        self.content.controls = [
            ft.Column([ft.Container(surface(form, padding=28), width=720, margin=ft.Margin.only(top=14))],
                      expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO),
        ]

    def help_page(self):
        async def open_link(url):
            try:
                await self.launcher.launch_url(url)
            except Exception:
                self.notice('Usa el número o el correo que aparece en Soporte técnico.',
                            kind='error', heading='No se pudo abrir el enlace')

        async def save_manual(_):
            try:
                path = await self.picker.save_file(file_name=MANUAL_FILE,
                                                  file_type=ft.FilePickerFileType.CUSTOM,
                                                  allowed_extensions=['pdf'])
                if path:
                    destination = Path(path)
                    if destination.suffix.lower() != '.pdf':
                        destination = destination.with_suffix('.pdf')
                    await asyncio.to_thread(shutil.copyfile, RESOURCES / MANUAL_FILE, destination)
                    self.notice('Manual guardado en PDF.')
            except Exception as error:
                self.notice(str(error), kind='error', heading='No se pudo guardar el manual')

        async def copy_support(_):
            printer = self.store.setting('printer') or 'Sin configurar'
            design = self.store.setting('design') or 'Sin configurar'
            await self.clipboard.set(f'{APP_NAME}\nVersión {VERSION}\nImpresora: {printer}\nDiseño: {design}')
            self.notice('Datos de soporte copiados.')

        logo = (RESOURCES / 'tectronic.png').read_bytes()

        def logo_tile(size):
            return ft.Container(
                ft.Image(src=logo, width=size - 14, height=size - 14,
                         fit=ft.BoxFit.CONTAIN, semantics_label='Logo de Tectronic'),
                width=size, height=size, bgcolor=PAPER, border_radius=14, alignment=ft.Alignment.CENTER,
                border=ft.Border.all(1, LINE),
            )

        def panel(heading, points, icon):
            shape = ft.RoundedRectangleBorder(radius=12, side=ft.BorderSide(1, LINE))
            return ft.ExpansionTile(
                title=ft.Text(heading, size=15, weight=ft.FontWeight.W_600),
                leading=ft.Container(ft.Icon(icon, size=18, color=ACCENT), width=36, height=36,
                                     bgcolor=SELECTED, border_radius=9, alignment=ft.Alignment.CENTER),
                controls=[ft.Container(form_column(points, spacing=10),
                                       padding=ft.Padding.only(left=18, top=12, right=18, bottom=16),
                                       border=ft.Border.only(top=ft.BorderSide(1, LINE)), bgcolor=PAPER)],
                expanded_cross_axis_alignment=ft.CrossAxisAlignment.STRETCH,
                tile_padding=ft.Padding.symmetric(horizontal=14), min_tile_height=60,
                shape=shape, collapsed_shape=shape, bgcolor=SELECTED, collapsed_bgcolor=PAPER,
                text_color=INK, collapsed_text_color=INK, icon_color=ACCENT, collapsed_icon_color=MUTED,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )

        guide_icons = (ft.Icons.SETTINGS_OUTLINED, ft.Icons.INVENTORY_2_OUTLINED,
                       ft.Icons.PRINT_OUTLINED, ft.Icons.HISTORY)
        guide = form_column([
            title('Guía rápida', 21),
            *[panel(heading, [ft.Text(f'{index}. {step}', selectable=True, size=14)
                              for index, step in enumerate(steps, 1)], icon)
              for (heading, steps), icon in zip(GUIDE, guide_icons)],
        ], spacing=10)
        problems = form_column([
            title('Solución de problemas', 21),
            *[panel(heading, [ft.Text(detail, selectable=True, size=14)], ft.Icons.BUILD_OUTLINED)
              for heading, detail in TROUBLESHOOTING],
        ], spacing=10)
        support = surface(form_column([
            ft.Row([logo_tile(58),
                    ft.Column([title('Soporte técnico', 21), ft.Text(PUBLISHER, color=MUTED)],
                              spacing=3, expand=True)], spacing=14),
            ft.Text(f'{SUPPORT_PHONE}  ·  {SUPPORT_EMAIL}', selectable=True),
            ft.Row([
                action('Abrir WhatsApp', lambda _: self.page.run_task(open_link, WHATSAPP_URL),
                       ft.Icons.CHAT_OUTLINED, primary=True),
                action('Enviar correo', lambda _: self.page.run_task(open_link, f'mailto:{SUPPORT_EMAIL}'),
                       ft.Icons.MAIL_OUTLINE),
                action('Copiar datos de soporte', copy_support, ft.Icons.CONTENT_COPY_OUTLINED),
            ], wrap=True),
        ]))
        about = form_column([
            ft.Container(ft.Row([
                logo_tile(86),
                ft.Column([
                    ft.Text(PUBLISHER, color=ACCENT, weight=ft.FontWeight.W_600, size=14),
                    title(APP_NAME, 25),
                    ft.Row([badge(f'Versión {VERSION}'), badge('Windows')], wrap=True),
                ], spacing=8, expand=True),
            ], spacing=20), bgcolor=SELECTED, padding=24, border_radius=16,
                border=ft.Border.all(1, LINE)),
            surface(form_column([
                title('Acerca del software', 19),
                ft.Text('Prepara e imprime etiquetas en ZPL y TSPL, consulta el historial y reimprime por folio.', size=14),
                ft.Divider(height=12, color=LINE),
                title('Notas de versión', 16),
                ft.Text(f'{VERSION} · Nuevo diseño de Acerca de, Guía rápida y Problemas comunes.', size=14),
            ], spacing=8)),
        ], spacing=12)
        tab_content = ft.Column([
            ft.TabBar(tabs=[ft.Tab(label=label) for label in ('Guía rápida', 'Problemas comunes', 'Soporte', 'Acerca de')]),
            ft.TabBarView(expand=True, controls=[
                ft.Column([body], scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
                for body in (guide, problems, support, about)
            ]),
        ], expand=True)
        tabs = ft.Tabs(content=tab_content, length=4, expand=True)
        self.content.controls = [
            title('Ayuda', 30),
            ft.Row([
                action('Ver guía rápida', lambda _: self.page.run_task(tabs.move_to, 0), ft.Icons.MENU_BOOK, primary=True),
                action('Guardar manual en PDF', save_manual, ft.Icons.DOWNLOAD_OUTLINED),
                action('Contactar soporte', lambda _: self.page.run_task(tabs.move_to, 2), ft.Icons.SUPPORT_AGENT),
            ], wrap=True),
            tabs,
        ]

    def history(self):
        offset = 0
        active_qr = None
        search = ft.TextField(hint_text='Busca por folio, fecha o producto', expand=True,
                              prefix_icon=ft.Icons.SEARCH, **compact_field_style())
        mode = compact_select(value='all', options=[
            ft.DropdownOption(key=value, text=name) for value, name in (
                ('all', 'Todos'), ('folio', 'Folio'), ('date', 'Fecha de impresión'), ('product', 'Producto'),
            )
        ])
        mode.width = 185
        mode.label = 'Filtros'
        search.height = mode.height = 48
        rows = ft.Column(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO)
        status = ft.Text(size=13, color=MUTED)
        next_page = icon_action(ft.Icons.CHEVRON_RIGHT, 'Página siguiente', lambda _: paginate(PAGE_SIZE))
        previous = icon_action(ft.Icons.CHEVRON_LEFT, 'Página anterior', lambda _: paginate(-PAGE_SIZE))

        def table_row(values, *, header=False):
            widths = (100, None, 145, 65, 125, 130)
            cells = [grid_cell(value, width=width, expand=1 if width is None else None,
                               padding=7, edge=index < len(widths) - 1)
                     for index, (value, width) in enumerate(zip(values, widths))]
            return grid_row(cells, header=header)

        def draw():
            mode_value = 'qr' if active_qr is not None else mode.value
            query = active_qr if active_qr is not None else (search.value or '')
            found = self.store.print_history(query, mode=mode_value, offset=offset, limit=PAGE_SIZE + 1)
            states = {'sent': 'Enviado', 'pending': 'Sin confirmar', 'uncertain': 'Envío incierto'}
            rows.controls = [
                table_row([
                    ft.Text(entry.folio, font_family='Consolas', weight=ft.FontWeight.W_700,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=entry.folio),
                    truncated(entry.product),
                    truncated(datetime.fromisoformat(entry.printed_at).strftime('%d/%m/%Y %H:%M')),
                    ft.Text(str(entry.copies), size=13),
                    truncated(states[entry.status] + (' · Reimpresión' if entry.reprint else '')),
                    action('Reimprimir', lambda _, entry=entry: self.reprint(entry, draw),
                           ft.Icons.PRINT_OUTLINED, height=34),
                ]) for entry in found[:PAGE_SIZE]
            ] or [ft.Container(ft.Text('No se encontraron etiquetas.', color=MUTED), padding=18)]
            previous.disabled = offset == 0
            next_page.disabled = len(found) <= PAGE_SIZE
            status.value = f'Página {offset // PAGE_SIZE + 1}' + (' · Coincidencias del QR' if active_qr else '')
            self.page.update()

        def paginate(step):
            nonlocal offset
            offset = max(0, offset + step)
            draw()

        def search_changed(_):
            nonlocal offset, active_qr
            offset, active_qr = 0, None
            draw()

        def scan(_):
            fields = [ft.TextField(label=name, autofocus=index == 0, **FIELD_STYLE)
                      for index, name in enumerate(('Producto', 'Fecha de entrada', 'Descripción',
                                                    'No. Pedimento', 'Piezas'))]

            def find(_):
                nonlocal offset, active_qr
                values = [(field.value or '').strip() for field in fields]
                if not all(values[index] for index in (0, 1, 2, 4)):
                    error.value = 'Escanea el QR completo o captura los cinco campos. El pedimento puede quedar vacío.'
                    self.page.update()
                    return
                active_qr = '\t'.join(values)
                offset = 0
                search.value = ''
                self.close()
                draw()

            fields[-1].on_submit = find
            error = ft.Text(color=DANGER, size=13)
            self.dialog('Buscar por QR', ft.Container(form_column([
                ft.Text('Coloca el cursor en Producto, escanea la etiqueta y pulsa Buscar. '
                        'Si hay etiquetas con los mismos datos, elige el folio correcto.', color=MUTED),
                *fields, error,
            ]), width=460), [
                action('Cancelar', lambda _: self.close()),
                action('Buscar', find, ft.Icons.SEARCH, primary=True),
            ], max_height=540)

        search.on_change = mode.on_select = search_changed
        self.content.controls = [
            title('Historial de impresión', 30),
            ft.Row([search, mode, action('Leer QR', scan, ft.Icons.QR_CODE_SCANNER, height=48),
                    icon_action(ft.Icons.REFRESH, 'Actualizar historial', lambda _: draw())],
                   spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            grid_frame(ft.Column([
                table_row([title(name, 13) for name in ('Folio', 'Producto', 'Fecha de impresión',
                                                        'Copias', 'Estado', 'Acciones')], header=True),
                rows,
            ], expand=True, spacing=0), expand=True),
            ft.Row([status, ft.Row([previous, next_page], spacing=4)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]
        draw()

    async def spool_job(self, printer, job, payload, notice):
        try:
            windows_job = await asyncio.to_thread(submit, printer, payload)
        except Exception as exc:
            await asyncio.to_thread(self.store.finish_print, job)
            self.notice(f'{notice}. Revisa la cola antes de reimprimir. {exc}',
                        kind='warning', heading='Envío sin confirmar')
        else:
            await asyncio.to_thread(self.store.finish_print, job, windows_job)
            self.notice(f'{notice} · Trabajo de Windows {windows_job}.', heading='Trabajo enviado')

    def reprint(self, entry, refresh):
        if self.busy:
            return
        printer = form_select('Impresora')
        status = ft.Text('Buscando impresoras…', size=13, color=MUTED)

        async def send_again(_):
            if self.busy or send.disabled:
                return
            self.busy = True
            selected = printer.value
            self.close()
            try:
                available = await asyncio.to_thread(list_printers)
                if selected not in {item['pPrinterName'] for item in available}:
                    raise ValueError('La impresora elegida ya no está disponible.')
                job, payload = await asyncio.to_thread(self.store.prepare_reprint, entry.id, selected)
                await self.spool_job(selected, job, payload, f'Folio {entry.folio}')
            except (OSError, sqlite3.Error, ValueError) as exc:
                self.notice(str(exc), kind='error', heading='No se pudo reimprimir')
            finally:
                self.busy = False
                if self.active_tab == 'Historial':
                    refresh()

        send = action('Reimprimir una copia', send_again, ft.Icons.PRINT_OUTLINED, primary=True, disabled=True)
        dialog = self.dialog('Reimprimir etiqueta', ft.Container(form_column([
            ft.Container(form_column([
                title(f'Folio {entry.folio}', 17),
                ft.Text(f'Producto: {entry.product} ({entry.sku})'),
                ft.Text(f'No. Pedimento: {entry.pedimento or "Sin pedimento registrado"}'),
            ], spacing=5), bgcolor=SOFT, padding=12, border_radius=8),
            ft.Text('Se enviará una copia con los datos y el folio originales.', color=MUTED),
            printer, status,
        ]), width=470), [action('Cancelar', lambda _: self.close()), send])

        async def options():
            try:
                await self.load_printers()
                if not dialog.open:
                    return
                choices = self.windows_printers
                saved = self.store.setting('printer')
                printer.options = self.printer_options()
                printer.value = next((name for name in (entry.printer, saved, self.windows_default)
                                      if name in choices), choices[0] if choices else None)
                status.value = '' if choices else 'No hay impresoras disponibles.'
                send.disabled = not printer.value
            except Exception:
                status.value = 'No se pudieron consultar las impresoras de Windows.'
            if dialog.open:
                self.page.update()

        self.page.run_task(options)

    def prepare(self, items):
        if self.busy or not items:
            return
        records = {record[0]: record for record in self.store.designs()}
        selected = self.store.setting('printer')
        layout = records.get(self.store.setting('design'))
        copies = ft.TextField(tooltip='Copias para todos', expand=True, value='1',
                              keyboard_type=ft.KeyboardType.NUMBER, **compact_field_style())
        quantities = [ft.TextField(value='1', width=64, height=40, dense=True,
                                   tooltip=f'Copias de {item.sku}', keyboard_type=ft.KeyboardType.NUMBER)
                      for item in items]
        common_pedimento = ft.TextField(tooltip='No. Pedimento para todo el lote', expand=True, **compact_field_style())
        pedimentos = [
            ft.TextField(value='', height=40, dense=True, tooltip=f'No. Pedimento de {item.sku}')
            for item in items
        ]
        preview = ft.Container()
        active_preview = 0
        preview_key = None
        preview_revision = 0
        preview_lock = asyncio.Lock()
        summary = ft.Text(color=INK, weight=ft.FontWeight.W_600, expand=True)
        design_name = f'{layout[0]} ({layout[1]})' if layout else 'Sin diseño'
        configuration = ft.Container(
            ft.Row([ft.Icon(ft.Icons.PRINT_OUTLINED, size=19),
                    ft.Text(f'{selected or "Sin impresora"} · {design_name}',
                            expand=True, weight=ft.FontWeight.W_600)], spacing=9),
            bgcolor=SOFT, border_radius=7, padding=12,
        )
        printer_message = ft.Text('Verificando impresora configurada…', color=MUTED, size=13)
        ready = False

        def quantity(value):
            raw = (value or '').strip()
            return int(raw) if raw.isascii() and raw.isdecimal() and len(raw) <= 3 else 0

        def print_item(index):
            item = items[index]
            return replace(item, attributes={**item.attributes, 'pedimento': (pedimentos[index].value or '').strip()})

        def draw_preview(first, *, retry=False):
            nonlocal preview_key, preview_revision
            if layout is None:
                preview_key = None
                preview.content = message_strip('Guarda el diseño predeterminado en Configuración.', 'warning')
                return
            item = print_item(active_preview)
            folio = first + active_preview
            design_name, language, source = layout
            values = {**item_values(item), 'folio': str(folio)}
            labels = {**BUILTIN_FIELDS, **LABEL_FIELDS, **self.fields}
            heading = title(f'Vista de datos · {item.sku}', 14)
            if language != 'ZPL':
                preview_key = None
                fields = [
                    ft.Text(f'{labels.get(field, field)}: {values.get(field) or "Vacío"}',
                            size=13, selectable=True, color=MUTED)
                    for field in design_fields(source)
                ]
                preview.content = form_column([
                    heading, ft.Text('Datos que se enviarán · Folio estimado', color=MUTED, size=12),
                    *fields,
                ], spacing=6)
                return

            requested = (design_name, item.sku, folio, item.attributes['pedimento'])
            if requested == preview_key and not retry:
                return
            preview_key = requested
            preview_revision += 1
            revision = preview_revision
            zpl = render(source, 'ZPL', item, folio)
            width_inches, height_inches = label_size(zpl)
            width_px, height_px = width_inches * 96, height_inches * 96
            scale = min(1, 650 / width_px, 300 / height_px)
            dimensions = f'{width_inches * 25.4:.1f} × {height_inches * 25.4:.1f} mm'
            display_scale = ' · Reducida para caber' if scale < 1 else ''
            result = ft.Container(
                ft.Row([ft.ProgressRing(width=18, height=18, stroke_width=2),
                        ft.Text('Generando vista previa en Labelary…', color=MUTED)], spacing=10),
                padding=14, border=ft.Border.all(1, LINE), border_radius=8, bgcolor=SOFT,
            )
            preview.content = form_column([
                ft.Row([ft.Container(ft.Text(f'Vista previa ZPL · {item.sku}', size=14,
                                             color=INK, weight=ft.FontWeight.W_700), expand=True),
                        badge(dimensions)], vertical_alignment=ft.CrossAxisAlignment.START),
                result,
                ft.Text(f'203 dpi{display_scale} · Folio estimado: {folio}\n'
                        'El ZPL de esta etiqueta se envía a Labelary.',
                        size=12, color=MUTED),
            ], spacing=6)

            def still_current():
                return dialog.open and preview_revision == revision and preview_key == requested

            def try_again(_):
                draw_preview(self.store.next_folio(), retry=True)
                self.page.update()

            async def load_preview():
                await asyncio.sleep(0.4)
                async with preview_lock:
                    if not still_current():
                        return
                    try:
                        image = await asyncio.to_thread(preview_png, zpl)
                    except ValueError as error:
                        if not still_current():
                            return
                        result.content = form_column([
                            ft.Text(str(error), color=NOTICES['warning'][2]),
                            ft.Row([action('Reintentar', try_again, ft.Icons.REFRESH)]),
                        ], spacing=8)
                    else:
                        if not still_current():
                            return
                        result.content = ft.Image(
                            src=image, width=width_px * scale, height=height_px * scale, fit=ft.BoxFit.CONTAIN,
                            semantics_label=f'Vista previa ZPL de {item.sku}, folio estimado {folio}',
                        )
                        result.alignment = ft.Alignment.CENTER
                    self.page.update()

            self.page.run_task(load_preview)

        def update_summary(_=None):
            counts = [quantity(field.value) for field in quantities]
            count = sum(counts)
            first = self.store.next_folio()
            valid_count = all(counts) and count <= LIMIT
            products_text = '1 producto' if len(items) == 1 else f'{len(items)} productos'
            labels_text = '1 etiqueta' if count == 1 else f'{count} etiquetas'
            summary.value = (f'{products_text} · {labels_text}' if valid_count
                             else f'Indica de 1 a {LIMIT} etiquetas en total.')
            send.disabled = not (ready and valid_count and layout is not None) or self.busy
            draw_preview(first)
            self.page.update()

        def show_item(index):
            nonlocal active_preview
            batch_rows[active_preview].bgcolor = PAPER
            active_preview = index
            batch_rows[active_preview].bgcolor = SELECTED
            update_summary()

        def apply_copies(_):
            for field in quantities:
                field.value = copies.value
            update_summary()

        def apply_pedimento(_):
            for field in pedimentos:
                field.value = common_pedimento.value
            update_summary()

        async def load_options():
            nonlocal ready
            if not selected:
                printer_message.value = 'Guarda una impresora en Configuración para poder imprimir.'
                self.page.update()
                return
            try:
                available = await asyncio.to_thread(list_printers)
            except Exception:
                if dialog.open:
                    printer_message.value = 'No se pudieron consultar las impresoras. Revísalas en Configuración.'
                    self.page.update()
                return
            if not dialog.open:
                return
            ready = selected in {item['pPrinterName'] for item in available}
            printer_message.value = '' if ready else 'La impresora guardada no está disponible. Revísala en Configuración.'
            printer_message.visible = not ready
            update_summary()

        async def send_labels(_):
            if self.busy or send.disabled:
                return
            entries = [(print_item(index), quantity(field.value)) for index, field in enumerate(quantities)]
            self.busy = True
            self.close()
            try:
                available = await asyncio.to_thread(list_printers)
                if selected not in {item['pPrinterName'] for item in available}:
                    raise ValueError('La cola ya no está instalada. Selecciona otra en Configuración.')
                first, last, payload, job = await asyncio.to_thread(
                    self.store.prepare_print_batch, entries, layout, printer=selected,
                )
                await self.spool_job(selected, job, payload, f'Folios {first}-{last}')
            except Exception as exc:
                self.notice(str(exc), kind='error', heading='No se pudo preparar la impresión')
            finally:
                self.busy = False

        async def print_labels(event):
            if self.busy or send.disabled:
                return
            missing = missing_fields(layout[2], (print_item(index) for index in range(len(items))))
            if not missing:
                await send_labels(event)
                return
            labels = {**BUILTIN_FIELDS, **LABEL_FIELDS, **self.store.catalog_fields()}
            details = [ft.Container(ft.Row([
                ft.Text('SKU', expand=2, weight=ft.FontWeight.W_600),
                ft.Text('Campos vacíos', expand=3, weight=ft.FontWeight.W_600),
            ]), padding=9, bgcolor=SOFT, border_radius=6)]
            details.extend(ft.Container(ft.Row([
                ft.Text(sku, expand=2, size=13, selectable=True),
                ft.Text(', '.join(labels.get(field, field) for field in fields),
                        expand=3, color=MUTED, size=13, selectable=True),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
                padding=9, border=ft.Border.only(bottom=ft.BorderSide(1, LINE)))
                for sku, fields in list(missing.items())[:10])
            if len(missing) > 10:
                details.append(ft.Text(f'Y {len(missing) - 10} productos más.', color=MUTED))

            async def confirm(_):
                if self.busy:
                    return
                self.close()
                await send_labels(None)

            self.dialog('Hay variables sin valor', ft.Container(form_column([
                message_strip(f'{len(missing)} de {len(items)} productos tienen datos faltantes. '
                              'Esos campos se imprimirán vacíos.', 'warning'),
                *details,
            ]), width=480), [
                action('Volver', lambda _: self.close()),
                action('Imprimir de todos modos', confirm, primary=True),
            ], max_height=520)

        send = action('Imprimir', print_labels, ft.Icons.PRINT_OUTLINED,
                      primary=True, disabled=True, height=46, width=148)
        for entry in [*quantities, *pedimentos]:
            entry.on_change = update_summary

        def batch_row(product, copy, pedimento, view, *, header=False, selected=False):
            return grid_row([
                grid_cell(product, expand=4), grid_cell(copy, width=96, padding=8),
                grid_cell(pedimento, expand=3), grid_cell(view, width=48, padding=5, edge=False),
            ], header=header, selected=selected)

        batch_rows = [
            batch_row(
                truncated(' · '.join(filter(None, (item.name, item.sku, label_values(item).get('medidas'))))),
                entry, pedimentos[index],
                icon_action(ft.Icons.VISIBILITY_OUTLINED, f'Ver etiqueta de {item.sku}',
                            lambda _, index=index: show_item(index)),
                selected=index == active_preview,
            ) for index, (item, entry) in enumerate(zip(items, quantities))
        ]
        batch = grid_frame(form_column([
            batch_row(title('Producto', 13), title('Copias', 13), title('No. Pedimento', 13),
                      ft.Text(''), header=True),
            ft.Container(ft.ListView(controls=batch_rows, spacing=0),
                         height=min(172, len(batch_rows) * 43)),
        ], spacing=0))
        footer = ft.Row([
            summary, action('Cancelar', lambda _: self.close(), height=46, width=148), send,
        ], width=min(760, max(340, (self.page.width or 880) - 120)),
           spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        dialog = self.dialog('Preparar impresión', ft.Container(form_column([
            configuration,
            printer_message,
            ft.Row([ft.Text('Copias para todos', width=175), copies,
                    action('Aplicar a todos', apply_copies, height=COMPACT_HEIGHT, width=175)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([ft.Text('Pedimento para el lote', width=175), common_pedimento,
                    action('Aplicar pedimento', apply_pedimento, height=COMPACT_HEIGHT, width=175)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            batch,
            surface(preview, padding=12),
        ], spacing=10), width=760), [footer], max_height=800, footer_gap=12)
        update_summary()
        self.page.run_task(load_options)


def startup_panel(*, retry=None):
    if retry is None:
        indicator = ft.Container(
            ft.Stack([
                ft.ProgressRing(width=76, height=76, stroke_width=3, color=ACCENT, bgcolor=SOFT,
                                semantics_label='Cargando catálogo'),
                ft.Container(ft.Icon(ft.Icons.LAYERS_OUTLINED, size=29, color=ACCENT),
                             width=54, height=54, border_radius=16, bgcolor=SELECTED,
                             alignment=ft.Alignment.CENTER),
            ], width=76, height=76, alignment=ft.Alignment.CENTER),
            alignment=ft.Alignment.CENTER,
        )
        status = [ft.Text('Abriendo el catálogo…', color=MUTED, size=14, text_align=ft.TextAlign.CENTER)]
    else:
        indicator = ft.Icon(ft.Icons.ERROR_OUTLINE, color=DANGER, size=38)
        status = [
            ft.Text('No se pudo abrir la base de datos local.', color=MUTED, size=14,
                    text_align=ft.TextAlign.CENTER),
            action('Reintentar', retry, ft.Icons.REFRESH, primary=True),
        ]
    return ft.Container(
        ft.Container(
            ft.Column([indicator, ft.Text(APP_NAME, size=24, weight=ft.FontWeight.W_700, color=INK,
                                         text_align=ft.TextAlign.CENTER), *status], tight=True, spacing=12,
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=380, bgcolor=PAPER, border_radius=22, border=ft.Border.all(1, LINE),
            padding=ft.Padding.symmetric(horizontal=28, vertical=32),
            shadow=ft.BoxShadow(blur_radius=28, color='#18344F69', offset=ft.Offset(0, 10)),
        ),
        expand=True, alignment=ft.Alignment.CENTER, bgcolor=WORKSPACE,
    )


async def main(page: ft.Page):
    page.title = APP_NAME
    page.theme = ft.Theme(font_family='Segoe UI', color_scheme_seed=ACCENT)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.min_width = 880
    page.window.min_height = 620
    page.window.width = 1200
    page.window.height = 760
    data = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))

    def open_catalog():
        store = LabelStore(data / 'Occidental Maderas' / 'etiquetas.sqlite3')
        return store, store.products()

    async def load(_=None):
        page.controls[:] = [startup_panel()]
        page.update()
        started = asyncio.get_running_loop().time()
        try:
            store, products = await asyncio.to_thread(open_catalog)
        except (OSError, sqlite3.Error, ValueError):
            page.controls[:] = [startup_panel(retry=load)]
            page.update()
            return
        # Keep fast loads visible briefly to avoid a single-frame flash.
        remaining = 0.55 - (asyncio.get_running_loop().time() - started)
        if remaining > 0:
            await asyncio.sleep(remaining)
        page.controls.clear()
        LabelApp(page, store, products)

    await load()
