"""Rights-aware Wikimedia portraits, disk cache and an asynchronous native widget.

Identity is resolved through Wikidata before its P18 file is requested from Commons.
Uncertain identities and missing licence metadata deliberately leave a silhouette.
Sources: https://www.mediawiki.org/wiki/API:Imageinfo and
https://www.wikidata.org/wiki/Wikidata:Data_access
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QRunnable, QRectF, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget
from .archive import data_directory

USER_AGENT = 'GameSense/0.6 (sports education desktop; https://github.com/dkddhairya26/Game-Sense)'
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_POOL = QThreadPool()
_POOL.setMaxThreadCount(2)
_SPORT_WORDS = {
    'NBA': ('basketball',), 'Soccer': ('footballer', 'soccer', 'association football'),
    'AFL': ('australian rules', 'australian football'),
    'F1': ('racing driver', 'formula one', 'formula 1'),
}


def plain_text(value: str) -> str:
    return html.unescape(re.sub(r'<[^>]*>', '', str(value))).strip()


def approved_license(metadata: dict) -> tuple[str, str] | None:
    """Accept explicit free licences; never infer permission from a search result."""
    short = plain_text(metadata.get('LicenseShortName', {}).get('value', ''))
    licence_url = metadata.get('LicenseUrl', {}).get('value', '')
    name = short.lower().replace('_', ' ')
    parsed = urlparse(licence_url)
    if 'noncommercial' in name or 'no derivatives' in name or '-nc' in name or '-nd' in name:
        return None
    if parsed.hostname in ('creativecommons.org', 'www.creativecommons.org'):
        if re.match(r'^/licenses/by(?:-sa)?/\d', parsed.path):
            return short, licence_url
        if parsed.path.startswith(('/publicdomain/zero/', '/publicdomain/mark/')):
            return short or 'Public domain', licence_url
    # Commons uses a public-domain help page for several PD templates.
    if name in ('public domain', 'pd', 'cc0', 'cc0 1.0'):
        return short, licence_url or 'https://commons.wikimedia.org/wiki/Help:Public_domain'
    return None


class ImageService:
    def __init__(self, cache_dir: str | Path | None = None):
        base = data_directory()
        self.cache_dir = Path(cache_dir) if cache_dir else base / 'portraits'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        bundle_root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        self.bundled_dir = bundle_root / 'data' / 'portraits' if cache_dir is None else None

    def _paths(self, stable_id):
        key = hashlib.sha256(str(stable_id).encode('utf-8')).hexdigest()
        return self.cache_dir / (key + '.json'), self.cache_dir / (key + '.image')

    def cached(self, stable_id: str) -> tuple[dict, bytes] | None:
        manifest, image_path = self._paths(stable_id)
        result = self._read_cached(stable_id, manifest, image_path)
        if result:
            return result
        if self.bundled_dir and self.bundled_dir != self.cache_dir:
            return self._read_cached(stable_id, self.bundled_dir / manifest.name,
                                     self.bundled_dir / image_path.name)
        return None

    @staticmethod
    def _read_cached(stable_id, manifest, image_path):
        try:
            meta = json.loads(manifest.read_text(encoding='utf-8'))
            if not isinstance(meta, dict):
                return None
            if meta.get('competitor_id') != stable_id:
                return None
            if not all(meta.get(key) for key in ('artist', 'source_url', 'license_url', 'modifications')):
                return None
            source_url = urlparse(meta['source_url'])
            if source_url.scheme != 'https' or source_url.hostname != 'commons.wikimedia.org':
                return None
            if not approved_license({'LicenseShortName': {'value': meta.get('license', '')},
                                     'LicenseUrl': {'value': meta.get('license_url', '')}}):
                return None
            content = image_path.read_bytes()
            if meta.get('sha256') and hashlib.sha256(content).hexdigest() != meta['sha256']:
                return None
            if QImage.fromData(content).isNull():
                return None
            return meta, content
        except (OSError, ValueError, TypeError):
            return None

    def _request(self, url: str, binary=False):
        global _LAST_REQUEST
        # One API request per second, shared by all portrait workers.
        with _REQUEST_LOCK:
            wait = 1.0 - (time.monotonic() - _LAST_REQUEST)
            if wait > 0:
                time.sleep(wait)
            _LAST_REQUEST = time.monotonic()
        request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*' if binary else 'application/json'})
        with urlopen(request, timeout=12) as response:
            length = int(response.headers.get('Content-Length', '0'))
            if length > 12_000_000:
                raise ValueError('Portrait exceeds size limit')
            data = response.read(12_000_001)
            if len(data) > 12_000_000:
                raise ValueError('Portrait exceeds size limit')
        return data if binary else json.loads(data)

    def _api(self, endpoint, **params):
        result = self._request(endpoint + '?' + urlencode({'format': 'json', **params}))
        if not isinstance(result, dict) or result.get('error'):
            raise ValueError('Portrait provider returned an API error')
        return result

    def resolve(self, stable_id: str, name: str, sport: str = '', online=True, refresh=False) -> tuple[dict, bytes] | None:
        existing = self.cached(stable_id)
        if existing or not online:
            return existing
        manifest, image_path = self._paths(stable_id)
        negative_path = manifest.with_suffix('.missing')
        if not refresh and negative_path.exists() and time.time() - negative_path.stat().st_mtime < 86400:
            return None
        result = self._api('https://www.wikidata.org/w/api.php', action='wbsearchentities',
                           search=name, language='en', uselang='en', type='item', limit=8)
        words = _SPORT_WORDS.get(sport, ())
        matches = [entry for entry in result.get('search', [])
                   if name.casefold() in (entry.get('label', '').casefold(), entry.get('match', {}).get('text', '').casefold())
                   and (not words or any(word in entry.get('description', '').lower() for word in words))]
        if len(matches) != 1:
            negative_path.touch()
            return None
        entity_id = matches[0]['id']
        entities = self._api('https://www.wikidata.org/w/api.php', action='wbgetentities',
                             ids=entity_id, props='claims')
        claims = entities.get('entities', {}).get(entity_id, {}).get('claims', {}).get('P18', [])
        files = [c.get('mainsnak', {}).get('datavalue', {}).get('value') for c in claims
                 if c.get('rank') != 'deprecated']
        files = [f for f in files if isinstance(f, str)]
        if not files:
            negative_path.touch()
            return None
        info = self._api('https://commons.wikimedia.org/w/api.php', action='query',
                         titles='File:' + files[0], prop='imageinfo',
                         iiprop='url|extmetadata|size|mime', iiurlwidth=640)
        for page in info.get('query', {}).get('pages', {}).values():
            for file_info in page.get('imageinfo', []):
                metadata = file_info.get('extmetadata', {})
                licence = approved_license(metadata)
                artist = plain_text(metadata.get('Attribution', {}).get('value', '') or metadata.get('Artist', {}).get('value', ''))
                if not licence or not artist:
                    continue
                url = file_info.get('thumburl') or file_info.get('url', '')
                if urlparse(url).hostname not in ('upload.wikimedia.org', 'thumb.wikimedia.org'):
                    continue
                content = self._request(url, binary=True)
                decoded = QImage.fromData(content)
                if decoded.isNull():
                    continue
                meta = {
                    'competitor_id': stable_id, 'name': name, 'sport': sport,
                    'wikidata_id': entity_id, 'file_title': page.get('title', ''),
                    'wikidata_label': matches[0].get('label'),
                    'identity_match': 'Unique exact Wikidata label or alias with matching sport description',
                    'image_url': url, 'source': 'Wikimedia Commons',
                    'source_url': file_info.get('descriptionurl', ''),
                    'license': licence[0], 'license_url': licence[1], 'artist': artist,
                    'width': decoded.width(), 'height': decoded.height(),
                    'original_width': file_info.get('width'), 'original_height': file_info.get('height'),
                    'usage_terms': plain_text(metadata.get('UsageTerms', {}).get('value', '')),
                    'restrictions': plain_text(metadata.get('Restrictions', {}).get('value', '')),
                    'credit': plain_text(metadata.get('Credit', {}).get('value', '')),
                    'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'sha256': hashlib.sha256(content).hexdigest(),
                    'modifications': 'Resized to fit the portrait panel; no other edits.',
                }
                temporary = image_path.with_suffix('.tmp')
                temporary.write_bytes(content)
                temporary.replace(image_path)
                temporary_meta = manifest.with_suffix('.json.tmp')
                temporary_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
                temporary_meta.replace(manifest)
                return meta, content
        negative_path.touch()
        return None


class _PortraitSignals(QObject):
    finished = Signal(str, object, object, str)


class _PortraitJob(QRunnable):
    def __init__(self, service, token, stable_id, name, sport, online):
        super().__init__()
        self.signals = _PortraitSignals()
        self.args = service, token, stable_id, name, sport, online

    def run(self):
        service, token, stable_id, name, sport, online = self.args
        try:
            result = service.resolve(stable_id, name, sport, online)
            meta, content = result if result else ({}, b'')
            error = '' if result else 'No verified licensed portrait available'
        except Exception as exc:
            meta, content, error = {}, b'', 'Portrait unavailable: ' + type(exc).__name__
        self.signals.finished.emit(token, meta, content, error)


class PortraitWidget(QWidget):
    attributionChanged = Signal(str)
    statusChanged = Signal(str)
    loaded = Signal(object)

    def __init__(self, parent=None, size=160, cache_dir=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAccessibleName('Athlete portrait')
        self.service = ImageService(cache_dir)
        self.metadata = {}
        self.pixmap = QPixmap()
        self.name = ''
        self.accent = '#59e3b1'
        self.status = 'Licensed portrait'
        self.attribution_text = ''
        self._token = ''
        self._jobs = {}
        self._athlete_key = None

    def set_athlete(self, stable_id, name, sport='', online=True):
        key = str(stable_id), str(name), str(sport), bool(online)
        if key == self._athlete_key:
            self.attributionChanged.emit(self.attribution_text)
            self.statusChanged.emit(self.status)
            return
        self._athlete_key = key
        self.name = str(name)
        self._token = str(time.monotonic_ns())
        self.pixmap = QPixmap()
        self.metadata = {}
        self.attribution_text = ''
        self.status = 'Loading portrait' if online else 'Offline portrait'
        self.attributionChanged.emit('')
        self.update()
        if not stable_id or not name:
            self.status = 'No athlete selected'
            self.update()
            return
        cached = self.service.cached(str(stable_id))
        if cached:
            self._finished(self._token, cached[0], cached[1], '')
            return
        job = _PortraitJob(self.service, self._token, str(stable_id), self.name, sport, online)
        self._jobs[self._token] = job
        job.signals.finished.connect(self._finished)
        _POOL.start(job)

    def _finished(self, token, metadata, content, error):
        self._jobs.pop(token, None)
        if token != self._token:
            return
        self.metadata = metadata
        self.pixmap = QPixmap()
        if content:
            self.pixmap.loadFromData(content)
        self.status = error or 'Wikimedia Commons · ' + metadata.get('license', '')
        attribution = ''
        if metadata:
            attribution = (f"{metadata['artist']} · {metadata['license']} · Wikimedia Commons\n"
                           f"{metadata['source_url']}\n{metadata['license_url']}\n"
                           f"{metadata['modifications']}")
        self.setToolTip(attribution or self.status)
        self.attribution_text = attribution
        self.attributionChanged.emit(attribution)
        self.statusChanged.emit(self.status)
        self.loaded.emit(metadata)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(bounds, 18, 18)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor('#152827'))
        if not self.pixmap.isNull():
            scaled = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width() - scaled.width()) // 2,
                               (self.height() - scaled.height()) // 2, scaled)
        else:
            w, h = self.width(), self.height()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#38524f'))
            painter.drawEllipse(QRectF(w*.34, h*.16, w*.32, h*.32))
            painter.drawRoundedRect(QRectF(w*.18, h*.52, w*.64, h*.55), w*.25, h*.22)
            if w >= 100:
                painter.fillRect(QRectF(0, h*.81, w, h*.19), QColor('#10201f'))
                painter.setPen(QColor('#a6bab6'))
                painter.setFont(QFont('Segoe UI', max(7, int(w/22))))
                painter.drawText(QRectF(4, h*.82, w-8, h*.15), Qt.AlignmentFlag.AlignCenter, 'PORTRAIT UNAVAILABLE')
        painter.setClipping(False)
        painter.setPen(QPen(QColor('#36564e'), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(bounds, 18, 18)
        painter.end()
