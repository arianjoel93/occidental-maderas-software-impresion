from urllib.error import HTTPError
import unittest
from unittest.mock import patch

from occidental.labelary import label_size, preview_png


class LabelaryTest(unittest.TestCase):
    def test_posts_raw_zpl_with_inferred_label_dimensions(self):
        zpl = b'^XA^PW480^LL240^FO25,25^FDTest^FS^XZ'
        png = b'\x89PNG\r\n\x1a\n' + b'simulated image'
        with patch('occidental.labelary.urlopen') as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = png
            self.assertEqual(preview_png(zpl), png)
            request = open_url.call_args.args[0]
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(request.data, zpl)
            self.assertEqual(request.get_header('Accept'), 'image/png')
            self.assertTrue(request.full_url.endswith('/8dpmm/labels/2.3646x1.1823/0/'))

    def test_missing_size_and_rate_limit(self):
        self.assertEqual(label_size(b'^XA^XZ'), (4.0, 6.0))
        error = HTTPError('https://api.labelary.com', 429, 'Too Many Requests', {}, None)
        with patch('occidental.labelary.urlopen', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'demasiadas solicitudes'):
                preview_png(b'^XA^XZ')
