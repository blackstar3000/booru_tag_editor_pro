# core/yandere_client.py
# yande.re / Konachan API client (shared API format).

import logging
from typing import Any, List, Dict

from core.booru_client_base import BooruClientBase
from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

YANDERE_BASE_URL = "https://yande.re"
KONACHAN_BASE_URL = "https://konachan.com"
YANDERE_RPS = 1

# yandere/konachan tag types
YANDERE_CATEGORY_MAP = {
    'artist': 1,
    'copyright': 2,
    'character': 3,
    'general': 0,
    'meta': 4,
    'species': 5,
    'lore': 6,
}


class YandereClient(BooruClientBase):
    """yande.re API client."""

    def __init__(self, settings: SettingsManager):
        super().__init__("yande.re", YANDERE_BASE_URL, requests_per_sec=YANDERE_RPS)
        self.settings = settings
        self._requires_auth = False
        self._api_key = ""
        self._cookies = ""
        self._reload_credentials()

    def _reload_credentials(self):
        self._api_key = self.settings.yandere_api_key or ""
        self._cookies = self.settings.yandere_cookies or ""
        logger.info("yande.re credentials loaded")

    def _has_credentials(self) -> bool:
        return True  # yande.re allows anonymous access

    def _get_cookies(self) -> str:
        return self._cookies

    def _get_headers(self) -> dict:
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://yande.re/',
            'Origin': 'https://yande.re',
        }

    def _get_auth_params(self) -> tuple:
        if self._api_key:
            return None, {'api_key': self._api_key}
        return None, {}

    def _get_tag_search_endpoint(self) -> str:
        return "tag.json"

    def _get_tag_info_endpoint(self) -> str:
        return "tag.json"

    def _get_wiki_endpoint(self) -> str:
        return "wiki.json"

    def _get_posts_endpoint(self) -> str:
        return "post.json"

    def _get_tag_search_params(self, tag: str) -> dict:
        return {'name': tag, 'order': 'name', 'limit': 10}

    def _get_autocomplete_params(self, query: str) -> dict:
        return {'name': f'{query}*', 'order': 'count', 'limit': 10}

    def _get_wiki_params(self, tag: str) -> dict:
        return {'title': tag}

    def _get_posts_params(self, tag: str) -> dict:
        return {'tags': tag, 'limit': 3}

    def _parse_tag_search(self, data: Any, query: str) -> list:
        tags = []
        tag_list = data if isinstance(data, list) else []
        for t in tag_list:
            name = t.get('name', '')
            post_count = t.get('count', t.get('post_count', 0))
            cat_str = t.get('type', 'general')
            category = YANDERE_CATEGORY_MAP.get(cat_str, 0)
            tags.append({'name': name, 'category': category, 'post_count': post_count})
        return tags

    def _parse_tag_info(self, data: Any, tag: str) -> dict:
        tag_list = data if isinstance(data, list) else []
        for t in tag_list:
            if t.get('name') == tag:
                cat_str = t.get('type', 'general')
                return {
                    'id': t.get('id'),
                    'name': t.get('name', tag),
                    'category': YANDERE_CATEGORY_MAP.get(cat_str, 0),
                    'post_count': t.get('count', t.get('post_count', 0)),
                    'source': 'yande.re',
                    'type': cat_str,
                }
        if tag_list:
            t = tag_list[0]
            cat_str = t.get('type', 'general')
            return {
                'id': t.get('id'),
                'name': t.get('name', tag),
                'category': YANDERE_CATEGORY_MAP.get(cat_str, 0),
                'post_count': t.get('count', t.get('post_count', 0)),
                'source': 'yande.re',
                'type': cat_str,
            }
        return {}

    def _parse_wiki(self, data: Any, tag: str) -> str:
        if isinstance(data, list) and data:
            return data[0].get('body', data[0].get('content', ''))
        return ''

    def _parse_posts(self, data: Any, tag: str) -> list:
        posts = []
        post_list = data if isinstance(data, list) else []
        for p in post_list:
            sample_urls = p.get('sample_url', '')
            preview_url = p.get('preview_url', p.get('thumb_url'))
            file_url = p.get('file_url', p.get('jpeg_url'))
            posts.append({
                'id': p.get('id'),
                'preview_url': preview_url,
                'file_url': file_url,
                'large_url': sample_urls or file_url,
            })
        return posts

    def _get_post_endpoint(self, post_id: str) -> str:
        return "post.json"

    def _get_post_params(self, post_id: str) -> dict:
        return {'post_id': post_id}

    def _parse_post(self, data: Any) -> dict:
        post_list = data if isinstance(data, list) else []
        if not post_list:
            return {}
        p = post_list[0]
        tags_str = p.get('tags', '')
        all_tags = tags_str.split() if tags_str else []
        tags_by_category = {'artist': [], 'copyright': [], 'character': [], 'general': [], 'meta': []}
        for tag_str in all_tags:
            tags_by_category['general'].append(tag_str)
        return {
            'id': p.get('id'),
            'tags': all_tags,
            'tags_by_category': tags_by_category,
            'file_url': p.get('file_url', p.get('jpeg_url')),
            'preview_url': p.get('preview_url', p.get('thumb_url')),
            'rating': p.get('rating', ''),
            'score': p.get('score', 0),
        }

    def reload_settings(self):
        self._reload_credentials()
        self.clear_caches()


class KonachanClient(YandereClient):
    """Konachan API client (shares yande.re API format)."""

    def __init__(self, settings: SettingsManager):
        super().__init__(settings)
        self.source_name = "Konachan"
        self.base_url = KONACHAN_BASE_URL
        self._requires_auth = False
        self._reload_credentials()

    def _get_headers(self) -> dict:
        headers = super()._get_headers()
        headers['Referer'] = 'https://konachan.com/'
        headers['Origin'] = 'https://konachan.com'
        return headers

    def _has_credentials(self) -> bool:
        return True  # Konachan allows anonymous access
