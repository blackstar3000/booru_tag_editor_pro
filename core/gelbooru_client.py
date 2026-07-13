# core/gelbooru_client.py
# Gelbooru API client.

import logging
from typing import Any, List, Dict

from core.booru_client_base import BooruClientBase, _normalize_tag
from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

# Gelbooru uses index.php?page=dapi with s=tag/s=post parameters
GELBOORU_BASE_URL = "https://gelbooru.com/index.php"
GELBOORU_RPS = 1


class GelbooruClient(BooruClientBase):
    """Gelbooru API client.

    Gelbooru uses index.php?page=dapi&s=tag|post&q=index&json=1
    Auth via api_key + user_id query params.
    Tag search uses name (exact) or name_pattern (wildcard with %).
    """

    def __init__(self, settings: SettingsManager):
        super().__init__("Gelbooru", GELBOORU_BASE_URL, requests_per_sec=GELBOORU_RPS)
        self.settings = settings
        self._requires_auth = True
        self._user_id = ""
        self._api_key = ""
        self._cookies = ""
        self._reload_credentials()

    def _reload_credentials(self):
        self._user_id = self.settings.gelbooru_user_id or ""
        self._api_key = self.settings.gelbooru_api_key or ""
        self._cookies = self.settings.gelbooru_cookies or ""
        logger.info(f"Gelbooru credentials loaded for user_id: {self._user_id}")

    def _has_credentials(self) -> bool:
        # Gelbooru requires numeric user_id + api_key
        if not self._user_id or not self._api_key:
            return False
        # Validate user_id is numeric
        try:
            int(self._user_id)
        except (ValueError, TypeError):
            logger.warning(f"Gelbooru user_id '{self._user_id}' is not numeric - skipping")
            return False
        return True

    def _get_cookies(self) -> str:
        return self._cookies

    def _get_headers(self) -> dict:
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://gelbooru.com/',
            'Origin': 'https://gelbooru.com',
        }

    def _get_auth_params(self) -> tuple:
        if self._user_id and self._api_key:
            return None, {'user_id': self._user_id, 'api_key': self._api_key}
        return None, {}

    def _get_tag_search_endpoint(self) -> str:
        # Gelbooru doesn't have a separate tag search endpoint via dapi,
        # we use the post search and extract tags, or use name_pattern
        return ""  # endpoint is part of params

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
            'name': _normalize_tag(tag),
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
            tags.append({'name': name, 'category': 0, 'post_count': post_count})
        return tags

    def _parse_tag_info(self, data: Any, tag: str) -> dict:
        tag_list = data.get('tag', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for t in tag_list:
            if t.get('name') == tag:
                return {
                    'id': t.get('id'),
                    'name': t.get('name', tag),
                    'category': 0,
                    'post_count': t.get('post_count', t.get('count', 0)),
                    'source': 'gelbooru',
                }
        if tag_list:
            t = tag_list[0]
            return {
                'id': t.get('id'),
                'name': t.get('name', tag),
                'category': 0,
                'post_count': t.get('post_count', t.get('count', 0)),
                'source': 'gelbooru',
            }
        return {}

    def _parse_wiki(self, data: Any, tag: str) -> str:
        # Gelbooru wiki is not easily accessible via dapi
        return ''

    def _parse_posts(self, data: Any, tag: str) -> list:
        posts = []
        post_list = data.get('post', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for p in post_list:
            tags_str = p.get('tags', '')
            all_tags = tags_str.split() if tags_str else []
            posts.append({
                'id': p.get('id'),
                'preview_url': p.get('preview_url', p.get('thumbnail_src')),
                'file_url': p.get('file_url'),
                'large_url': p.get('large_url', p.get('file_url')),
                'tags': all_tags,
                'rating': p.get('rating', ''),
                'score': p.get('score', 0),
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
            'preview_url': p.get('preview_url', p.get('thumbnail_src')),
            'rating': p.get('rating', ''),
            'score': p.get('score', 0),
        }

    def reload_settings(self):
        self._reload_credentials()
        self.clear_caches()
