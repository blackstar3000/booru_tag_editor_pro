# core/danbooru_client.py
# Production-ready Danbooru API client with custom User-Agent, caching, rate limiting, retries, and background workers.

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import cloudscraper
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool

from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

# --- Configuration ---
CACHE_TTL = 3600  # 1 hour
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0  # seconds
REQUESTS_PER_SECOND = 10  # Danbooru free tier allows 10 reads/sec
RATE_LIMIT_BURST = 5

# Custom User-Agent that identifies the app (as recommended by Danbooru forum)
APP_USER_AGENT = "BooruTagEditorPro/1.0 (user: bossgame; contact: bossgame@example.com)"

# --- Helper Classes ---

class _CacheManager:
    """LRU cache with TTL."""
    def __init__(self, ttl=CACHE_TTL, maxsize=1000):
        self._ttl = ttl
        self._cache = {}
        self._access_order = []

    def get(self, key):
        if key not in self._cache:
            return None
        entry = self._cache[key]
        if datetime.now() > entry['expires']:
            del self._cache[key]
            return None
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        return entry['value']

    def put(self, key, value):
        if len(self._cache) >= 1000:
            old_key = self._access_order.pop(0)
            del self._cache[old_key]
        self._cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=self._ttl)
        }
        self._access_order.append(key)

    def clear(self):
        self._cache.clear()
        self._access_order.clear()


class _RateLimiter:
    def __init__(self, requests_per_sec=1, burst=1):
        self._interval = 1.0 / requests_per_sec
        self._last_request_time = 0
        self._lock = threading.Lock()

    def wait_if_needed(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._interval:
                sleep_time = self._interval - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class _RequestWorker(QRunnable):
    def __init__(self, method, url, params, headers, cookies, retry_count):
        super().__init__()
        self.method = method
        self.url = url
        self.params = params
        self.headers = headers
        self.cookies = cookies
        self.retry_count = retry_count
        self.signals = WorkerSignals()

    def run(self):
        try:
            # Use cloudscraper to mimic a real browser
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False,
                }
            )
            # Set headers including custom User-Agent
            scraper.headers.update(self.headers)
            if self.cookies:
                for item in self.cookies.split(';'):
                    if '=' in item:
                        key, val = item.strip().split('=', 1)
                        scraper.cookies.set(key.strip(), val.strip())
            response = scraper.request(self.method, self.url, params=self.params, timeout=15)
            self.signals.finished.emit(response)
        except Exception as e:
            self.signals.error.emit(str(e))


class _ImageFetchWorker(QRunnable):
    """Worker for downloading preview images in the background."""
    def __init__(self, url, rate_limiter, headers=None, cookies=None):
        super().__init__()
        self.url = url
        self.rate_limiter = rate_limiter
        self.headers = headers or {}
        self.cookies = cookies or ""
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.rate_limiter.wait_if_needed()
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False,
                }
            )
            scraper.headers.update(self.headers)
            if self.cookies:
                for item in self.cookies.split(';'):
                    if '=' in item:
                        key, val = item.strip().split('=', 1)
                        scraper.cookies.set(key.strip(), val.strip())
            response = scraper.get(self.url, timeout=15)
            self.signals.finished.emit(response)
        except Exception as e:
            self.signals.error.emit(str(e))


class DanbooruClient(QObject):
    tag_info_fetched = pyqtSignal(str, dict)
    tag_info_error = pyqtSignal(str, str)
    autocomplete_results = pyqtSignal(str, list)
    autocomplete_error = pyqtSignal(str, str)
    wiki_fetched = pyqtSignal(str, str)
    wiki_error = pyqtSignal(str, str)
    example_posts_fetched = pyqtSignal(str, list)
    example_posts_error = pyqtSignal(str, str)
    preview_loaded = pyqtSignal(str, int, object)
    credentials_missing = pyqtSignal()

    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
        self._username = None
        self._api_key = None
        self._cookies = None
        self._rate_limiter = _RateLimiter(REQUESTS_PER_SECOND, RATE_LIMIT_BURST)
        self._tag_cache = _CacheManager(ttl=CACHE_TTL, maxsize=500)
        self._wiki_cache = _CacheManager(ttl=CACHE_TTL, maxsize=200)
        self._autocomplete_cache = _CacheManager(ttl=CACHE_TTL, maxsize=200)
        self._request_queue = []
        self._threadpool = QThreadPool()
        self._threadpool.setMaxThreadCount(4)
        self._reload_credentials()

        # Also store the custom User-Agent as a constant for use in requests
        self.user_agent = APP_USER_AGENT

    def _reload_credentials(self):
        self._username = self.settings.danbooru_username or ""
        self._api_key = self.settings.danbooru_api_key or ""
        self._cookies = self.settings.danbooru_cookies or ""
        logger.info(f"Credentials loaded for user: {self._username}")
        if not self._username or not self._api_key:
            self.credentials_missing.emit()

    def _get_auth_params(self):
        if self._username and self._api_key:
            auth = (self._username, self._api_key)
            params = {}
        else:
            auth = None
            params = {'login': self._username, 'api_key': self._api_key} if self._username and self._api_key else {}
        return auth, params

    def _process_queue(self):
        if not self._request_queue:
            return
        item = self._request_queue.pop(0)

        self._rate_limiter.wait_if_needed()

        # Build request details
        auth, auth_params = self._get_auth_params()
        req_params = auth_params.copy()
        if item.get('params'):
            req_params.update(item['params'])

        # Headers with custom User-Agent
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://danbooru.donmai.us/',
            'Origin': 'https://danbooru.donmai.us',
        }

        url = f"https://danbooru.donmai.us/{item['endpoint']}"
        worker = _RequestWorker(
            method='GET',
            url=url,
            params=req_params,
            headers=headers,
            cookies=self._cookies,
            retry_count=0
        )

        if item['type'] == 'tag_info':
            tag = item['tag']
            worker.signals.finished.connect(lambda resp, tag=tag: self._handle_tag_response(tag, resp))
            worker.signals.error.connect(lambda err, tag=tag: self.tag_info_error.emit(tag, err))
        elif item['type'] == 'autocomplete':
            query = item['query']
            worker.signals.finished.connect(lambda resp, query=query: self._handle_autocomplete_response(query, resp))
            worker.signals.error.connect(lambda err, query=query: self.autocomplete_error.emit(query, err))
        elif item['type'] == 'wiki':
            tag = item['tag']
            worker.signals.finished.connect(lambda resp, tag=tag: self._handle_wiki_response(tag, resp))
            worker.signals.error.connect(lambda err, tag=tag: self.wiki_error.emit(tag, err))
        elif item['type'] == 'example_posts':
            tag = item['tag']
            worker.signals.finished.connect(lambda resp, tag=tag: self._handle_example_posts_response(tag, resp))
            worker.signals.error.connect(lambda err, tag=tag: self.example_posts_error.emit(tag, err))

        self._threadpool.start(worker)

    def _enqueue_request(self, request_type, endpoint, params, tag=None, query=None):
        self._request_queue.append({
            'type': request_type,
            'endpoint': endpoint,
            'params': params,
            'tag': tag,
            'query': query,
        })
        self._process_queue()

    def fetch_wiki(self, tag: str):
        if not tag:
            return
        cached = self._wiki_cache.get(tag)
        if cached is not None:
            self.wiki_fetched.emit(tag, cached)
            return
        if not self._username or not self._api_key:
            return
        params = {'search[title]': tag}
        self._enqueue_request('wiki', 'wiki_pages.json', params, tag=tag)

    def _handle_wiki_response(self, tag, response):
        try:
            if response.status_code == 200:
                data = response.json()
                if data:
                    body = data[0].get('body', '')
                    self._wiki_cache.put(tag, body)
                    self.wiki_fetched.emit(tag, body)
                else:
                    self.wiki_fetched.emit(tag, '')
            else:
                self.wiki_error.emit(tag, f"HTTP {response.status_code}")
        except Exception as e:
            self.wiki_error.emit(tag, f"Error parsing wiki: {e}")
        self._process_queue()

    def fetch_example_posts(self, tag: str):
        if not tag:
            return
        if not self._username or not self._api_key:
            return
        params = {'tags': tag, 'limit': 3}
        self._enqueue_request('example_posts', 'posts.json', params, tag=tag)

    def _handle_example_posts_response(self, tag, response):
        try:
            if response.status_code == 200:
                posts = response.json()
                simplified = []
                for post in posts[:3]:
                    simplified.append({
                        'id': post.get('id'),
                        'preview_url': post.get('preview_file_url'),
                        'file_url': post.get('file_url'),
                        'large_url': post.get('large_file_url'),
                    })
                self.example_posts_fetched.emit(tag, simplified)
            else:
                self.example_posts_error.emit(tag, f"HTTP {response.status_code}")
        except Exception as e:
            self.example_posts_error.emit(tag, f"Error parsing posts: {e}")
        self._process_queue()

    def fetch_preview_image(self, tag: str, index: int, url: str):
        """Download a preview thumbnail image in the background."""
        if not url:
            return
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://danbooru.donmai.us/',
        }
        worker = _ImageFetchWorker(url, self._rate_limiter, headers, self._cookies)
        worker.signals.finished.connect(lambda resp, tag=tag, idx=index: self._handle_preview_image(tag, idx, resp))
        self._threadpool.start(worker)

    def _handle_preview_image(self, tag, index, response):
        try:
            if response.status_code == 200:
                from PyQt5.QtGui import QPixmap
                from PyQt5.QtCore import QByteArray
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray(response.content))
                if not pixmap.isNull():
                    self.preview_loaded.emit(tag, index, pixmap)
        except Exception:
            pass

    def fetch_tag_info(self, tag: str):
        if not tag:
            return
        cached = self._tag_cache.get(tag)
        if cached is not None:
            self.tag_info_fetched.emit(tag, cached)
            return
        if not self._username or not self._api_key:
            self.credentials_missing.emit()
            return
        params = {'search[name]': tag}
        self._enqueue_request('tag_info', 'tags.json', params, tag=tag)

    def _handle_tag_response(self, tag, response):
        try:
            if response.status_code == 200:
                data = response.json()
                if data:
                    info = data[0]
                    self._tag_cache.put(tag, info)
                    self.tag_info_fetched.emit(tag, info)
                else:
                    self.tag_info_error.emit(tag, "Tag not found")
            else:
                self.tag_info_error.emit(tag, f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as e:
            self.tag_info_error.emit(tag, f"Error parsing response: {e}")
        self._process_queue()

    def autocomplete(self, query: str):
        if len(query) < 2:
            self.autocomplete_results.emit(query, [])
            return
        cached = self._autocomplete_cache.get(query)
        if cached is not None:
            self.autocomplete_results.emit(query, cached)
            return
        if not self._username or not self._api_key:
            self.credentials_missing.emit()
            return
        params = {'search[name_matches]': f'{query}*', 'limit': 10}
        self._enqueue_request('autocomplete', 'tags.json', params, query=query)

    def _handle_autocomplete_response(self, query, response):
        try:
            if response.status_code == 200:
                data = response.json()
                tags = [
                    {
                        'name': tag['name'],
                        'category': tag.get('category', 0),
                        'post_count': tag.get('post_count', 0),
                    }
                    for tag in data
                ]
                self._autocomplete_cache.put(query, tags)
                self.autocomplete_results.emit(query, tags)
            else:
                self.autocomplete_error.emit(query, f"HTTP {response.status_code}")
        except Exception as e:
            self.autocomplete_error.emit(query, f"Error parsing response: {e}")
        self._process_queue()

    def reload_settings(self):
        self._reload_credentials()
        self._tag_cache.clear()
        self._wiki_cache.clear()
        self._autocomplete_cache.clear()