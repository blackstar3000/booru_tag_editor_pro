# core/booru_client_base.py
# Abstract base class for all booru API clients.

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import cloudscraper
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool

logger = logging.getLogger(__name__)

CACHE_TTL = 3600


def _normalize_tag(tag: str) -> str:
    """Normalize a tag for booru API queries: lowercase, underscores, no backslashes."""
    return (tag.strip().lower()
            .replace(" ", "_")
            .replace("\\(", "(")
            .replace("\\)", ")"))
REQUESTS_PER_SECOND = 5
RATE_LIMIT_BURST = 3
APP_USER_AGENT = "BooruTagEditorPro/1.0 (user: bossgame; contact: bossgame@example.com)"


class CacheManager:
    """LRU cache with TTL."""
    def __init__(self, ttl=CACHE_TTL, maxsize=1000):
        self._ttl = ttl
        self._maxsize = maxsize
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
        if key in self._access_order:
            self._access_order.remove(key)
        if len(self._cache) >= self._maxsize:
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


class RateLimiter:
    def __init__(self, requests_per_sec=1, burst=1):
        self._interval = 1.0 / requests_per_sec
        self._last_request_time = 0
        self._lock = threading.Lock()

    def wait_if_needed(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_request_time = time.time()


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class RequestWorker(QRunnable):
    def __init__(self, method, url, params, headers, cookies, user_agent, auth=None):
        super().__init__()
        self.method = method
        self.url = url
        self.params = params
        self.headers = headers
        self.cookies = cookies
        self.user_agent = user_agent
        self.auth = auth
        self.signals = WorkerSignals()

    def run(self):
        try:
            scraper = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
            )
            scraper.headers.update(self.headers)
            if self.cookies:
                for item in self.cookies.split(';'):
                    if '=' in item:
                        key, val = item.strip().split('=', 1)
                        scraper.cookies.set(key.strip(), val.strip())
            response = scraper.request(self.method, self.url, params=self.params, auth=self.auth, timeout=15)
            self.signals.finished.emit(response)
        except Exception as e:
            self.signals.error.emit(str(e))


class ImageFetchWorker(QRunnable):
    def __init__(self, url, rate_limiter, headers=None, cookies=""):
        super().__init__()
        self.url = url
        self.rate_limiter = rate_limiter
        self.headers = headers or {}
        self.cookies = cookies
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.rate_limiter.wait_if_needed()
            scraper = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
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


class BooruClientBase(QObject):
    """Base class for all booru API clients.

    Provides common signals, caching, rate limiting, and request infrastructure.
    Subclasses must implement the abstract methods for their specific API.
    """

    # Common signals
    tag_info_fetched = pyqtSignal(str, str, dict)       # (source_name, tag, info)
    tag_info_error = pyqtSignal(str, str, str)           # (source_name, tag, error)
    autocomplete_results = pyqtSignal(str, str, list)    # (source_name, query, tags)
    autocomplete_error = pyqtSignal(str, str, str)       # (source_name, query, error)
    wiki_fetched = pyqtSignal(str, str, str)             # (source_name, tag, body)
    wiki_error = pyqtSignal(str, str, str)               # (source_name, tag, error)
    example_posts_fetched = pyqtSignal(str, str, list)   # (source_name, tag, posts)
    example_posts_error = pyqtSignal(str, str, str)      # (source_name, tag, error)
    post_fetched = pyqtSignal(str, dict)                  # (source_name, post_data)
    post_fetch_error = pyqtSignal(str, str)               # (source_name, error)
    search_posts_results = pyqtSignal(str, str, list)    # (source_name, query, posts)
    search_posts_error = pyqtSignal(str, str, str)       # (source_name, query, error)
    preview_loaded = pyqtSignal(str, str, int, object)   # (source_name, tag, index, pixmap)
    credentials_missing = pyqtSignal(str)                # (source_name)

    def __init__(self, source_name: str, base_url: str, requests_per_sec: int = REQUESTS_PER_SECOND):
        super().__init__()
        self.source_name = source_name
        self.base_url = base_url.rstrip('/')
        self.user_agent = APP_USER_AGENT
        self._rate_limiter = RateLimiter(requests_per_sec, RATE_LIMIT_BURST)
        self._tag_cache = CacheManager(ttl=CACHE_TTL, maxsize=500)
        self._wiki_cache = CacheManager(ttl=CACHE_TTL, maxsize=200)
        self._autocomplete_cache = CacheManager(ttl=CACHE_TTL, maxsize=200)
        self._request_queue = []
        self._threadpool = QThreadPool()
        self._threadpool.setMaxThreadCount(4)
        self._enabled = True
        self._requires_auth = False

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        if isinstance(value, str):
            self._enabled = value.lower() in ('true', '1', 'yes')
        else:
            self._enabled = bool(value)

    @property
    def requires_auth(self):
        return self._requires_auth

    def _get_headers(self) -> dict:
        """Return request headers for this source."""
        raise NotImplementedError

    def _get_auth_params(self) -> tuple:
        """Return (auth, params) for authentication."""
        raise NotImplementedError

    def _has_credentials(self) -> bool:
        """Return True if valid credentials are configured."""
        raise NotImplementedError

    def _parse_tag_search(self, data: Any, query: str) -> list:
        """Parse API response into normalized tag list: [{name, category, post_count}]"""
        raise NotImplementedError

    def _parse_tag_info(self, data: Any, tag: str) -> dict:
        """Parse API response into normalized tag info dict."""
        raise NotImplementedError

    def _parse_wiki(self, data: Any, tag: str) -> str:
        """Parse API response into wiki body string."""
        raise NotImplementedError

    def _parse_posts(self, data: Any, tag: str) -> list:
        """Parse API response into normalized post list: [{id, preview_url, file_url, large_url}]"""
        raise NotImplementedError

    def _get_tag_search_endpoint(self) -> str:
        """Return the API endpoint for tag search."""
        raise NotImplementedError

    def _get_tag_info_endpoint(self) -> str:
        """Return the API endpoint for tag info."""
        raise NotImplementedError

    def _get_wiki_endpoint(self) -> str:
        """Return the API endpoint for wiki."""
        raise NotImplementedError

    def _get_posts_endpoint(self) -> str:
        """Return the API endpoint for posts."""
        raise NotImplementedError

    def _enqueue_request(self, request_type, endpoint, params, tag=None, query=None):
        self._request_queue.append({
            'type': request_type,
            'endpoint': endpoint,
            'params': params,
            'tag': tag,
            'query': query,
        })
        self._process_queue()

    def _process_queue(self):
        if not self._request_queue:
            return
        item = self._request_queue.pop(0)

        self._rate_limiter.wait_if_needed()

        auth, auth_params = self._get_auth_params()
        req_params = auth_params.copy()
        if item.get('params'):
            req_params.update(item['params'])

        headers = self._get_headers()
        endpoint = item['endpoint']
        if endpoint:
            url = f"{self.base_url}/{endpoint}"
        else:
            url = self.base_url

        worker = RequestWorker(
            method='GET', url=url, params=req_params,
            headers=headers, cookies=self._get_cookies(), user_agent=self.user_agent,
            auth=auth
        )

        if item['type'] == 'tag_info':
            tag = item['tag']
            worker.signals.finished.connect(lambda resp, t=tag: self._handle_tag_info_response(t, resp))
            worker.signals.error.connect(lambda err, t=tag: self.tag_info_error.emit(self.source_name, t, err))
        elif item['type'] == 'autocomplete':
            query = item['query']
            worker.signals.finished.connect(lambda resp, q=query: self._handle_autocomplete_response(q, resp))
            worker.signals.error.connect(lambda err, q=query: self.autocomplete_error.emit(self.source_name, q, err))
        elif item['type'] == 'wiki':
            tag = item['tag']
            worker.signals.finished.connect(lambda resp, t=tag: self._handle_wiki_response(t, resp))
            worker.signals.error.connect(lambda err, t=tag: self.wiki_error.emit(self.source_name, t, err))
        elif item['type'] == 'example_posts':
            tag = item['tag']
            worker.signals.finished.connect(lambda resp, t=tag: self._handle_example_posts_response(t, resp))
            worker.signals.error.connect(lambda err, t=tag: self.example_posts_error.emit(self.source_name, t, err))
        elif item['type'] == 'fetch_post':
            post_id = item['tag']
            worker.signals.finished.connect(lambda resp, pid=post_id: self._handle_fetch_post_response(pid, resp))
            worker.signals.error.connect(lambda err, pid=post_id: self.post_fetch_error.emit(self.source_name, err))
        elif item['type'] == 'search_posts':
            query = item['tag']
            worker.signals.finished.connect(lambda resp, q=query: self._handle_search_posts_response(q, resp))
            worker.signals.error.connect(lambda err, q=query: self.search_posts_error.emit(self.source_name, q, err))

        self._threadpool.start(worker)

    def _get_cookies(self) -> str:
        """Return cookies string for this source."""
        raise NotImplementedError

    def fetch_tag_info(self, tag: str):
        if not tag or not self._enabled:
            return
        cached = self._tag_cache.get(tag)
        if cached is not None:
            self.tag_info_fetched.emit(self.source_name, tag, cached)
            return
        if not self._has_credentials():
            self.credentials_missing.emit(self.source_name)
            return
        params = self._get_tag_search_params(tag)
        self._enqueue_request('tag_info', self._get_tag_info_endpoint(), params, tag=tag)

    def _get_tag_search_params(self, tag: str) -> dict:
        """Return params for searching a specific tag."""
        raise NotImplementedError

    def _handle_tag_info_response(self, tag, response):
        try:
            if response.status_code == 200:
                data = response.json()
                info = self._parse_tag_info(data, tag)
                if info:
                    self._tag_cache.put(tag, info)
                    self.tag_info_fetched.emit(self.source_name, tag, info)
                else:
                    self.tag_info_error.emit(self.source_name, tag, "Tag not found")
            elif self._cf_blocked(response):
                self.tag_info_error.emit(self.source_name, tag,
                    "Cloudflare blocked — check cookies/credentials or try again later")
            else:
                self.tag_info_error.emit(self.source_name, tag, f"HTTP {response.status_code}")
        except Exception as e:
            self.tag_info_error.emit(self.source_name, tag, f"Error: {e}")
        self._process_queue()

    def autocomplete(self, query: str):
        if len(query) < 2 or not self._enabled:
            self.autocomplete_results.emit(self.source_name, query, [])
            return
        cached = self._autocomplete_cache.get(query)
        if cached is not None:
            self.autocomplete_results.emit(self.source_name, query, cached)
            return
        if not self._has_credentials():
            return
        params = self._get_autocomplete_params(query)
        self._enqueue_request('autocomplete', self._get_tag_search_endpoint(), params, query=query)

    def _get_autocomplete_params(self, query: str) -> dict:
        """Return params for autocomplete search."""
        raise NotImplementedError

    def _handle_autocomplete_response(self, query, response):
        try:
            if response.status_code == 200:
                data = response.json()
                tags = self._parse_tag_search(data, query)
                self._autocomplete_cache.put(query, tags)
                self.autocomplete_results.emit(self.source_name, query, tags)
            elif self._cf_blocked(response):
                self.autocomplete_error.emit(self.source_name, query,
                    "Cloudflare blocked — check cookies/credentials or try again later")
            else:
                self.autocomplete_error.emit(self.source_name, query, f"HTTP {response.status_code}")
        except Exception as e:
            self.autocomplete_error.emit(self.source_name, query, f"Error: {e}")
        self._process_queue()

    def fetch_wiki(self, tag: str):
        if not tag or not self._enabled:
            return
        cached = self._wiki_cache.get(tag)
        if cached is not None:
            self.wiki_fetched.emit(self.source_name, tag, cached)
            return
        if not self._has_credentials():
            return
        params = self._get_wiki_params(tag)
        self._enqueue_request('wiki', self._get_wiki_endpoint(), params, tag=tag)

    def _get_wiki_params(self, tag: str) -> dict:
        """Return params for wiki search."""
        raise NotImplementedError

    def _handle_wiki_response(self, tag, response):
        try:
            if response.status_code == 200:
                data = response.json()
                body = self._parse_wiki(data, tag)
                self._wiki_cache.put(tag, body)
                self.wiki_fetched.emit(self.source_name, tag, body)
            else:
                self.wiki_error.emit(self.source_name, tag, f"HTTP {response.status_code}")
        except Exception as e:
            self.wiki_error.emit(self.source_name, tag, f"Error: {e}")
        self._process_queue()

    def fetch_example_posts(self, tag: str):
        if not tag or not self._enabled:
            return
        if not self._has_credentials():
            return
        params = self._get_posts_params(tag)
        self._enqueue_request('example_posts', self._get_posts_endpoint(), params, tag=tag)

    def _get_posts_params(self, tag: str) -> dict:
        """Return params for fetching posts."""
        raise NotImplementedError

    def _cf_blocked(self, response) -> bool:
        """Detect Cloudflare challenge pages."""
        return (response.status_code in (403, 422, 503)
                and 'text/html' in response.headers.get('content-type', '')
                and ('Just a moment' in response.text[:500]
                     or 'challenge-platform' in response.text[:500]))

    def _handle_example_posts_response(self, tag, response):
        try:
            if response.status_code == 200:
                data = response.json()
                posts = self._parse_posts(data, tag)[:3]
                self.example_posts_fetched.emit(self.source_name, tag, posts)
            elif self._cf_blocked(response):
                self.example_posts_error.emit(self.source_name, tag,
                    "Cloudflare blocked — check cookies/credentials or try again later")
            else:
                self.example_posts_error.emit(self.source_name, tag, f"HTTP {response.status_code}")
        except Exception as e:
            self.example_posts_error.emit(self.source_name, tag, f"Error: {e}")
        self._process_queue()

    def search_posts(self, query: str, limit: int = 20):
        """Search for posts by tag query, returning up to limit results."""
        if not query or not self._enabled:
            return
        params = self._get_posts_params(query)
        params['limit'] = limit
        self._enqueue_request('search_posts', self._get_posts_endpoint(), params, tag=query)

    def _handle_search_posts_response(self, query, response):
        try:
            if response.status_code == 200:
                data = response.json()
                posts = self._parse_posts(data, query)
                self.search_posts_results.emit(self.source_name, query, posts)
            elif self._cf_blocked(response):
                self.search_posts_error.emit(self.source_name, query,
                    "Cloudflare blocked — check cookies/credentials or try again later")
            else:
                self.search_posts_error.emit(self.source_name, query, f"HTTP {response.status_code}")
        except Exception as e:
            self.search_posts_error.emit(self.source_name, query, f"Error: {e}")
        self._process_queue()

    def fetch_preview_image(self, tag: str, index: int, url: str):
        if not url or not self._enabled:
            return
        headers = self._get_headers()
        headers['Accept'] = 'image/webp,image/apng,image/*,*/*;q=0.8'
        worker = ImageFetchWorker(url, self._rate_limiter, headers, self._get_cookies())
        worker.signals.finished.connect(
            lambda resp, t=tag, idx=index: self._handle_preview_image(t, idx, resp)
        )
        self._threadpool.start(worker)

    def fetch_post_by_id(self, post_id: str):
        """Fetch a single post by ID. Subclasses must implement _get_post_params/_parse_post."""
        if not post_id or not self._enabled:
            return
        params = self._get_post_params(post_id)
        self._enqueue_request('fetch_post', self._get_post_endpoint(post_id), params, tag=post_id)

    def _get_post_endpoint(self, post_id: str) -> str:
        """Return the API endpoint for fetching a single post by ID."""
        return ""

    def _get_post_params(self, post_id: str) -> dict:
        """Return params for fetching a single post."""
        return {}

    def _parse_post(self, data: Any) -> dict:
        """Parse API response into normalized post: {id, tags, tag_string, file_url, preview_url, rating, score, tags_by_category}"""
        return {}

    def _handle_fetch_post_response(self, post_id, response):
        try:
            if response.status_code == 200:
                data = response.json()
                post = self._parse_post(data)
                if post:
                    self.post_fetched.emit(self.source_name, post)
                else:
                    self.post_fetch_error.emit(self.source_name, f"Post {post_id} not found")
            else:
                self.post_fetch_error.emit(self.source_name, f"HTTP {response.status_code}")
        except Exception as e:
            self.post_fetch_error.emit(self.source_name, f"Error: {e}")
        self._process_queue()

    def _handle_preview_image(self, tag, index, response):
        try:
            if response.status_code == 200:
                from PyQt5.QtGui import QPixmap
                from PyQt5.QtCore import QByteArray
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray(response.content))
                if not pixmap.isNull():
                    self.preview_loaded.emit(self.source_name, tag, index, pixmap)
        except Exception:
            pass

    def clear_caches(self):
        self._tag_cache.clear()
        self._wiki_cache.clear()
        self._autocomplete_cache.clear()
