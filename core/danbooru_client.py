# core/danbooru_client.py
# Danbooru API client using the BooruClientBase abstraction.

import logging
from typing import Any

from core.booru_client_base import BooruClientBase
from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

DANBOORU_BASE_URL = "https://danbooru.donmai.us"
DANBOORU_RPS = 10

# Danbooru tag categories
DANBOORU_CATEGORY_MAP = {
    0: 0,  # general
    1: 1,  # artist
    3: 2,  # copyright -> tag group
    4: 3,  # character
    5: 4,  # species
    7: 5,  # meta
    8: 6,  # lore
}


class DanbooruClient(BooruClientBase):
    """Danbooru API client.

    Danbooru uses HTTP Basic Auth (login:api_key).
    Tags have numeric categories (0=general, 1=artist, 3=copyright, 4=character).
    """

    def __init__(self, settings: SettingsManager):
        super().__init__("Danbooru", DANBOORU_BASE_URL, requests_per_sec=DANBOORU_RPS)
        self.settings = settings
        self._requires_auth = True
        self._username = ""
        self._api_key = ""
        self._cookies = ""
        self._reload_credentials()

    def _reload_credentials(self):
        self._username = self.settings.danbooru_username or ""
        self._api_key = self.settings.danbooru_api_key or ""
        self._cookies = self.settings.danbooru_cookies or ""
        logger.info(f"Danbooru credentials loaded for user: {self._username}")

    def _has_credentials(self) -> bool:
        return bool(self._username and self._api_key)

    def _get_cookies(self) -> str:
        return self._cookies

    def _get_headers(self) -> dict:
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://danbooru.donmai.us/',
            'Origin': 'https://danbooru.donmai.us',
        }

    def _get_auth_params(self) -> tuple:
        if self._username and self._api_key:
            return (self._username, self._api_key), {}
        return None, {}

    def _get_tag_search_endpoint(self) -> str:
        return "tags.json"

    def _get_tag_info_endpoint(self) -> str:
        return "tags.json"

    def _get_wiki_endpoint(self) -> str:
        return "wiki_pages.json"

    def _get_posts_endpoint(self) -> str:
        return "posts.json"

    def _get_tag_search_params(self, tag: str) -> dict:
        return {'search[name]': tag}

    def _get_autocomplete_params(self, query: str) -> dict:
        return {'search[name_matches]': f'{query}*', 'limit': 10}

    def _get_wiki_params(self, tag: str) -> dict:
        return {'search[title]': tag}

    def _get_posts_params(self, tag: str) -> dict:
        return {'tags': tag, 'limit': 3}

    def _parse_tag_search(self, data: Any, query: str) -> list:
        tags = []
        tag_list = data if isinstance(data, list) else []
        for t in tag_list:
            name = t.get('name', '')
            post_count = t.get('post_count', 0)
            category = DANBOORU_CATEGORY_MAP.get(t.get('category', 0), 0)
            tags.append({'name': name, 'category': category, 'post_count': post_count})
        return tags

    def _parse_tag_info(self, data: Any, tag: str) -> dict:
        tag_list = data if isinstance(data, list) else []
        if tag_list:
            t = tag_list[0]
            return {
                'id': t.get('id'),
                'name': t.get('name', tag),
                'category': DANBOORU_CATEGORY_MAP.get(t.get('category', 0), 0),
                'post_count': t.get('post_count', 0),
                'source': 'danbooru',
            }
        return {}

    def _parse_wiki(self, data: Any, tag: str) -> str:
        if isinstance(data, list) and data:
            return data[0].get('body', '')
        return ''

    def _parse_posts(self, data: Any, tag: str) -> list:
        posts = []
        post_list = data if isinstance(data, list) else []
        for p in post_list:
            tags_str = p.get('tag_string', '')
            all_tags = tags_str.split() if tags_str else []
            posts.append({
                'id': p.get('id'),
                'preview_url': p.get('preview_file_url'),
                'file_url': p.get('file_url'),
                'large_url': p.get('large_file_url'),
                'tags': all_tags,
                'rating': p.get('rating', ''),
                'score': p.get('score', 0),
            })
        return posts

    def _get_post_endpoint(self, post_id: str) -> str:
        return f"posts/{post_id}.json"

    def _get_post_params(self, post_id: str) -> dict:
        return {}

    def _parse_post(self, data: Any) -> dict:
        if isinstance(data, dict) and 'post' in data:
            data = data['post']
        if not isinstance(data, dict):
            return {}
        tags_by_category = {
            'artist': (data.get('tag_string_artist') or '').split(),
            'copyright': (data.get('tag_string_copyright') or '').split(),
            'character': (data.get('tag_string_character') or '').split(),
            'general': (data.get('tag_string_general') or '').split(),
            'meta': (data.get('tag_string_meta') or '').split(),
        }
        all_tags = (data.get('tag_string') or '').split()
        if not all_tags:
            all_tags = [t for cats in tags_by_category.values() for t in cats]
        return {
            'id': data.get('id'),
            'tags': all_tags,
            'tags_by_category': tags_by_category,
            'file_url': data.get('file_url'),
            'preview_url': data.get('preview_file_url'),
            'rating': data.get('rating', ''),
            'score': data.get('score', 0),
        }

    def reload_settings(self):
        self._reload_credentials()
        self.clear_caches()
