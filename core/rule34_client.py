# core/rule34_client.py
# Rule34 API client (Gelbooru-style dapi).

import logging
from typing import Any

from core.booru_client_base import BooruClientBase
from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

RULE34_BASE_URL = "https://rule34.xxx/index.php"
RULE34_RPS = 2

# Rule34 tag types (same as Gelbooru)
RULE34_CATEGORY_MAP = {
    'artist': 1,
    'copyright': 2,
    'character': 3,
    'general': 0,
    'meta': 4,
    'species': 5,
    'lore': 6,
}


class Rule34Client(BooruClientBase):
    """Rule34 API client.

    Uses index.php?page=dapi&s=tag|post&q=index&json=1
    Requires username + api_key (password hash) for access.
    """

    def __init__(self, settings: SettingsManager):
        super().__init__("Rule34", RULE34_BASE_URL, requests_per_sec=RULE34_RPS)
        self.settings = settings
        self._requires_auth = True
        self._user_id = ""
        self._api_key = ""
        self._reload_credentials()

    def _reload_credentials(self):
        self._user_id = self.settings.rule34_user_id or ""
        self._api_key = self.settings.rule34_api_key or ""
        logger.info(f"Rule34 credentials loaded for user_id: {self._user_id}")

    def _has_credentials(self) -> bool:
        return bool(self._user_id and self._api_key)

    def _get_cookies(self) -> str:
        return ""

    def _get_headers(self) -> dict:
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://rule34.xxx/',
            'Origin': 'https://rule34.xxx',
        }

    def _get_auth_params(self) -> tuple:
        if self._user_id and self._api_key:
            return None, {'api_key': self._api_key, 'user_id': self._user_id}
        return None, {}

    def _get_tag_search_endpoint(self) -> str:
        return ""

    def _get_tag_info_endpoint(self) -> str:
        return ""

    def _get_wiki_endpoint(self) -> str:
        return ""

    def _get_posts_endpoint(self) -> str:
        return ""

    def _get_tag_search_params(self, tag: str) -> dict:
        return {
            'page': 'dapi',
            's': 'tag',
            'q': 'index',
            'json': 1,
            'name': tag,
            'limit': 5,
        }

    def _get_autocomplete_params(self, query: str) -> dict:
        return {
            'page': 'dapi',
            's': 'tag',
            'q': 'index',
            'json': 1,
            'name_pattern': f'{query}%',
            'limit': 10,
        }

    def _get_wiki_params(self, tag: str) -> dict:
        return {
            'page': 'dapi',
            's': 'tag',
            'q': 'index',
            'json': 1,
            'name': tag,
        }

    def _get_posts_params(self, tag: str) -> dict:
        return {
            'page': 'dapi',
            's': 'post',
            'q': 'index',
            'json': 1,
            'tags': tag,
            'limit': 3,
        }

    def _parse_tag_search(self, data: Any, query: str) -> list:
        tags = []
        tag_list = data.get('tag', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for t in tag_list:
            name = t.get('name', '')
            post_count = t.get('post_count', t.get('count', 0))
            cat_str = t.get('type', 'general')
            category = RULE34_CATEGORY_MAP.get(cat_str, 0)
            tags.append({'name': name, 'category': category, 'post_count': post_count})
        return tags

    def _parse_tag_info(self, data: Any, tag: str) -> dict:
        tag_list = data.get('tag', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for t in tag_list:
            if t.get('name') == tag:
                cat_str = t.get('type', 'general')
                return {
                    'id': t.get('id'),
                    'name': t.get('name', tag),
                    'category': RULE34_CATEGORY_MAP.get(cat_str, 0),
                    'post_count': t.get('post_count', t.get('count', 0)),
                    'source': 'rule34',
                    'type': cat_str,
                }
        if tag_list:
            t = tag_list[0]
            cat_str = t.get('type', 'general')
            return {
                'id': t.get('id'),
                'name': t.get('name', tag),
                'category': RULE34_CATEGORY_MAP.get(cat_str, 0),
                'post_count': t.get('post_count', t.get('count', 0)),
                'source': 'rule34',
                'type': cat_str,
            }
        return {}

    def _parse_wiki(self, data: Any, tag: str) -> str:
        return ''

    def _parse_posts(self, data: Any, tag: str) -> list:
        posts = []
        post_list = data.get('post', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for p in post_list:
            posts.append({
                'id': p.get('id'),
                'preview_url': p.get('preview_url'),
                'file_url': p.get('file_url'),
                'large_url': p.get('sample_url', p.get('file_url')),
            })
        return posts

    def _get_post_params(self, post_id: str) -> dict:
        return {
            'page': 'dapi',
            's': 'post',
            'q': 'index',
            'json': 1,
            'id': post_id,
        }

    def _parse_post(self, data: Any) -> dict:
        post_list = data.get('post', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        if not post_list:
            return {}
        p = post_list[0] if isinstance(post_list, list) else post_list
        tags_str = p.get('tags', '')
        all_tags = tags_str.split() if tags_str else []
        tags_by_category = {'artist': [], 'copyright': [], 'character': [], 'general': [], 'meta': []}
        tags_by_category['general'] = all_tags
        return {
            'id': p.get('id'),
            'tags': all_tags,
            'tags_by_category': tags_by_category,
            'file_url': p.get('file_url'),
            'preview_url': p.get('preview_url'),
            'rating': p.get('rating', ''),
            'score': p.get('score', 0),
        }

    def reload_settings(self):
        self._reload_credentials()
        self.clear_caches()
