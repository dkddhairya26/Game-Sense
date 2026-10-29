"""Small cached HTTP client shared by historical data providers.

No third-party HTTP dependency. Requests are serialized per host, rate-limited,
bounded, cancellable between chunks, and cached atomically for offline reuse.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class Cancelled(Exception):
    """A download was cancelled; committed records remain available."""


class HttpClient:
    _lock = threading.Lock()
    _recent = defaultdict(deque)

    def __init__(self, cache_dir, cancel=None, timeout=25, offline=False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cancel = cancel or threading.Event()
        self.timeout = timeout
        self.offline = offline

    def check(self):
        if self.cancel.is_set():
            raise Cancelled("Download cancelled. Saved pages will be reused on resume.")

    def pause(self, seconds):
        if self.cancel.wait(max(0, seconds)):
            self.check()

    def _throttle(self, host):
        # Jolpica: 4/s burst, 500/hour sustained. A conservative 8 s gap
        # stays below both limits even throughout a multi-season download.
        interval = 8.0 if host == 'api.jolpi.ca' else .3
        while True:
            self.check()
            with self._lock:
                recent = self._recent[host]
                now = time.monotonic()
                delay = interval - (now - recent[-1]) if recent else 0
                if delay <= 0:
                    recent.append(now)
                    while len(recent) > 2:
                        recent.popleft()
                    return
            self.pause(delay)

    def get_bytes(self, url, *, max_age=86400, headers=None, max_bytes=120_000_000):
        self.check()
        if urlparse(url).scheme != 'https':
            raise ValueError('Data providers must use HTTPS.')
        key = sha256(url.encode('utf-8')).hexdigest()
        cached = self.cache_dir / (key + '.bin')
        if cached.exists() and (self.offline or time.time() - cached.stat().st_mtime < max_age):
            return cached.read_bytes()
        if self.offline:
            raise OSError('Offline: this source is not in the HTTP cache.')
        request_headers = {'User-Agent': 'GameSense/0.6.0 (+https://github.com/dkddhairya26/Game-Sense)', 'Accept': 'application/json'}
        request_headers.update(headers or {})
        for attempt in range(4):
            self.check()
            self._throttle(urlparse(url).hostname)
            try:
                request = Request(url, headers=request_headers)
                with urlopen(request, timeout=self.timeout) as response:
                    length = response.headers.get('Content-Length')
                    if length and int(length) > max_bytes:
                        raise ValueError('Provider response exceeds the download size limit.')
                    data = bytearray()
                    while True:
                        self.check()
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        data.extend(chunk)
                        if len(data) > max_bytes:
                            raise ValueError('Provider response exceeds the download size limit.')
                temporary = cached.with_suffix('.part-' + str(threading.get_ident()))
                temporary.write_bytes(data)
                temporary.replace(cached)
                return bytes(data)
            except HTTPError as exc:
                if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 3:
                    raise OSError(f'Provider returned HTTP {exc.code}; retry later.') from exc
                retry = exc.headers.get('Retry-After', '')
                try:
                    delay = float(retry)
                except ValueError:
                    try:
                        delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        delay = 2 ** attempt * 2
                self.pause(min(max(delay, 1), 3600))
            except (URLError, TimeoutError) as exc:
                if attempt == 3:
                    raise OSError('Cannot reach data provider. Check your connection and retry; saved data is available offline.') from exc
                self.pause(2 ** attempt * 2)
        raise OSError('Download failed.')

    def get_json(self, url, **kwargs):
        return json.loads(self.get_bytes(url, **kwargs).decode('utf-8-sig'))
