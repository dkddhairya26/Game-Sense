"""Offline checks for portrait permissions, caching and chart calculations."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from gamesense.images import ImageService, PortraitWidget, approved_license, plain_text
from gamesense.charts import AnalyticsChart, MODES, available_metrics


class PortraitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_explicit_licence_permissions(self):
        def check(name, url):
            return approved_license({'LicenseShortName': {'value': name}, 'LicenseUrl': {'value': url}})
        self.assertIsNotNone(check('CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'))
        self.assertIsNotNone(check('CC BY 3.0', 'https://creativecommons.org/licenses/by/3.0/'))
        self.assertIsNotNone(check('Public domain', ''))
        self.assertIsNone(check('CC BY-NC 4.0', 'https://creativecommons.org/licenses/by-nc/4.0/'))
        self.assertIsNone(check('CC BY-SA 4.0', 'https://example.com/licenses/by-sa/4.0/'))
        self.assertIsNone(check('', ''))
        self.assertEqual(plain_text('<a href="x">Photographer &amp; co.</a>'), 'Photographer & co.')

    def test_cache_requires_licence_and_decodable_image(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            service = ImageService(tmp)
            manifest, image_path = service._paths('../../id')
            self.assertEqual(manifest.parent, Path(tmp))
            image = QImage(8, 8, QImage.Format.Format_RGB32)
            image.fill(QColor('green'))
            payload = QByteArray()
            buffer = QBuffer(payload)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, 'PNG')
            image_path.write_bytes(bytes(payload))
            manifest.write_text(json.dumps({'competitor_id': '../../id', 'artist': 'Test Author',
                                            'source_url': 'https://commons.wikimedia.org/wiki/File:Test.png',
                                            'modifications': 'Test fixture', 'license': 'CC BY 4.0',
                                            'license_url': 'https://creativecommons.org/licenses/by/4.0/'}))
            self.assertIsNotNone(service.cached('../../id'))
            self.assertIsNotNone(service.resolve('../../id', 'Unknown', online=False))
            manifest.write_text('{}')
            self.assertIsNone(service.cached('../../id'))
            self.assertIsNone(service.resolve('absent', 'Unknown', online=False))

    def test_wikidata_ambiguity_never_downloads_a_guess(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            service = ImageService(tmp)
            calls = []
            def api(*args, **kwargs):
                calls.append(kwargs)
                return {'search': [{'id': 'Q1', 'label': 'A Player', 'description': 'basketball player'},
                                   {'id': 'Q2', 'label': 'A Player', 'description': 'basketball player'}]}
            service._api = api
            self.assertIsNone(service.resolve('player:1', 'A Player', 'NBA'))
            self.assertEqual(len(calls), 1)
            # Negative cache avoids repeated calls for an unavailable identity.
            self.assertIsNone(service.resolve('player:1', 'A Player', 'NBA'))
            self.assertEqual(len(calls), 1)

    def test_bundled_portraits_keep_credits_on_repeated_selection(self):
        source = Path(__file__).resolve().parents[1] / 'data' / 'portraits'
        service = ImageService(source)
        manifests = list(source.glob('*.json'))
        self.assertGreaterEqual(len(manifests), 6)
        for manifest in manifests:
            metadata = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertIsNotNone(service.cached(metadata['competitor_id']))
        widget = PortraitWidget(cache_dir=source)
        credits = []
        widget.attributionChanged.connect(credits.append)
        widget.set_athlete('f1db:lewis-hamilton', 'Lewis Hamilton', 'F1', online=False)
        self.assertFalse(widget.pixmap.isNull())
        self.assertIn('CC BY 2.0', credits[-1])
        widget.set_athlete('f1db:lewis-hamilton', 'Lewis Hamilton', 'F1', online=False)
        self.assertIn('Governo do Estado', credits[-1])
        widget.close()


class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.chart = AnalyticsChart()
        # Test fixtures exercise calculations; never shipped as sports observations.
        self.df = pd.DataFrame([
            {'competitor_id': 'a', 'competitor': 'Shared Name', 'team': 'A', 'date': '2020-01-01', 'season': '2020', 'points': 10., 'rebounds': 2., 'assists': 3.},
            {'competitor_id': 'a', 'competitor': 'Shared Name', 'team': 'B', 'date': '2020-01-02', 'season': '2020', 'points': 20., 'rebounds': 4., 'assists': 5.},
            {'competitor_id': 'a', 'competitor': 'Shared Name', 'team': 'B', 'date': '2022-01-01', 'season': '2022', 'points': 30., 'rebounds': 6., 'assists': 7.},
            {'competitor_id': 'b', 'competitor': 'Shared Name', 'team': 'C', 'date': '2021-01-01', 'season': '2021', 'points': 4., 'rebounds': 8., 'assists': 9.},
            {'competitor_id': 'b', 'competitor': 'Shared Name', 'team': 'C', 'date': '2022-01-01', 'season': '2022', 'points': np.nan, 'rebounds': 7., 'assists': 8.},
        ])

    def tearDown(self):
        self.chart.close()

    def test_every_mode_renders_and_exports(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            for mode in MODES:
                with self.subTest(mode=mode):
                    self.chart.plot(self.df, 'NBA', ['a', 'b'], 'points', mode=mode, secondary_metric='rebounds')
                    self.chart.canvas.draw()
                    self.chart.export_png(Path(tmp) / 'chart.png')
                    self.chart.export_csv(Path(tmp) / 'chart.csv')
                    self.assertGreater((Path(tmp) / 'chart.png').stat().st_size, 1000)
                    self.assertFalse(self.chart.plotted_data.empty)

    def test_season_alignment_and_missing_values(self):
        self.chart.plot(self.df, 'NBA', ['a', 'b'], 'points', mode='Season trend')
        data = self.chart.plotted_data
        first = data.loc[data['competitor_id'] == 'a'].set_index('season')
        second = data.loc[data['competitor_id'] == 'b'].set_index('season')
        self.assertEqual(first.loc['2020', 'mean_points'], 15.)
        self.assertTrue(pd.isna(first.loc['2021', 'mean_points']))
        self.assertEqual(second.loc['2021', 'mean_points'], 4.)
        self.assertTrue(pd.isna(second.loc['2022', 'mean_points']))

    def test_rolling_average_uses_real_observations(self):
        self.chart.plot(self.df, 'NBA', ['a'], 'points', mode='Rolling average')
        self.assertEqual(self.chart.plotted_data['points'].tolist(), [10., 15., 20.])

    def test_empty_missing_and_nonadditive_cumulative(self):
        self.chart.plot(pd.DataFrame(), 'Soccer')
        self.assertTrue(self.chart.plotted_data.empty)
        self.chart.plot(self.df.assign(finish_position=1.), 'F1', ['a'], 'finish_position', mode='Cumulative total')
        self.assertTrue(self.chart.plotted_data.empty)
        self.assertIn('unavailable', self.chart.explanation.text())
        self.assertNotIn('season', available_metrics(self.df))
        self.assertNotIn('competitor_id', available_metrics(self.df))

    def test_duration_and_percentage_cumulative_guards(self):
        for metric in ('fastest_lap_time_ms', 'points_pg', 'championship_points'):
            with self.subTest(metric=metric):
                self.chart.plot(self.df.assign(**{metric: 3.}), 'F1', ['a'], metric, mode='Cumulative total')
                self.assertTrue(self.chart.plotted_data.empty)

    def test_rate_denominators_lower_better_and_season_dates(self):
        source = self.df.iloc[:2].assign(points_pg=[10.,30.], games_played=[1.,3.],
                                         fastest_lap_time_ms=[90000.,80000.], record_kind='season_total', date_precision='season')
        self.chart.plot(source, 'NBA', ['a'], 'points_pg', mode='Season trend')
        self.assertEqual(self.chart.plotted_data['mean_points_pg'].tolist(), [25.])
        self.chart.plot(source, 'NBA', ['a'], 'points_pg', mode='Rolling average')
        self.assertEqual(self.chart.plotted_data['points_pg'].tolist(), [10.,25.])
        self.assertEqual(self.chart._axes.get_xlabel(), 'Season')
        self.assertIn('do not represent individual game dates', self.chart.explanation.text())
        source = self.df.iloc[[0,3]].assign(fastest_lap_time_ms=[90000.,80000.])
        self.chart.plot(source, 'F1', metric='fastest_lap_time_ms', mode='Ranking')
        self.assertEqual(self.chart.plotted_data['competitor_id'].tolist(), ['a','b'])
        # Namesakes have separate y positions and unambiguous visible identities.
        ticks = [tick.get_text() for tick in self.chart._axes.get_yticklabels()]
        self.assertEqual(len(set(ticks)),2)

    def test_racing_charts_use_observed_positions_standings_and_stops(self):
        source = self.df.iloc[:3].assign(grid_position=[2.,3.,4.],finish_position=[1.,4.,2.],
                                        round=[1,2,3],championship_points=[25.,37.,55.],
                                        fastest_lap_time_ms=[92000.,88000.,91000.],
                                        pit_stop_events=[[{'stop':1,'lap':12,'duration_ms':23000}],[],[]])
        for mode in ('Grid vs finish','Championship evolution','Lap duration','Pit-stop timeline'):
            with self.subTest(mode=mode):
                self.chart.plot(source,'F1',['a'],metric='points',mode=mode)
                self.chart.canvas.draw()
                self.assertFalse(self.chart.plotted_data.empty)
                self.assertEqual(self.chart._axes.get_title(loc='left'),mode.upper())
        self.assertEqual(self.chart.plotted_data['lap'].tolist(),[12])
        self.assertEqual(self.chart.plotted_data['duration_ms'].tolist(),[23000])

    def test_spatial_charts_require_declared_coordinate_schema(self):
        source = self.df.iloc[:1].assign(spatial_source='StatsBomb 120x80 event coordinates',
                                         shot_events=[[{'x':108.,'y':40.,'xg':.6,'outcome':'Goal'},
                                                       {'x':999.,'y':50.,'xg':.8,'outcome':'Goal'}]],
                                         pass_links=[{'Recipient':3}])
        self.chart.plot(source,'Soccer',['a'],mode='Shot map')
        self.chart.canvas.draw()
        self.assertEqual(self.chart.plotted_data['x'].tolist(),[108.])
        self.assertEqual(self.chart.plotted_data['xg'].tolist(),[.6])
        self.chart.plot(source,'Soccer',['a'],mode='Shot density')
        self.chart.canvas.draw()
        self.chart.plot(source,'Soccer',['a'],mode='Passing network')
        self.assertEqual(self.chart.plotted_data['passes'].tolist(),[3])
        self.assertIn('abstract network',self.chart.explanation.text())
        self.chart.plot(source.assign(spatial_source='unknown'),'Soccer',['a'],mode='Shot map')
        self.assertIn('Showing observed season trends',self.chart.explanation.text())


if __name__ == '__main__':
    unittest.main()
