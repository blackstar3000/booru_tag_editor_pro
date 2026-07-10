import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# DEFAULT_CSV_PATH = r"F:\ComfyUI\ComfyUI\custom_nodes\comfyui-autocomplete-plus\data\danbooru_tags.csv"
DEFAULT_CSV_PATH = r"C:\Users\Kilo\Downloads\booru_tag_editor_pro\data\danbooru_tags.csv"


class DanbooruTagDB:
    def __init__(self, csv_path: Optional[str] = None):
        self._csv_path = csv_path or DEFAULT_CSV_PATH
        self._entries: List[Dict[str, Any]] = []
        self._loaded = False

    def load(self) -> bool:
        path = Path(self._csv_path)
        if not path.exists():
            logger.warning(f"Tag DB CSV not found: {self._csv_path}")
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tag = row.get('tag', '').strip()
                    if not tag:
                        continue
                    try:
                        category = int(row.get('category', 0))
                    except ValueError:
                        category = 0
                    try:
                        count = int(row.get('count', 0))
                    except ValueError:
                        count = 0
                    aliases_raw = row.get('alias', '').strip()
                    aliases_lower = []
                    if aliases_raw:
                        for alias in aliases_raw.split(','):
                            alias = alias.strip().strip('"\'')
                            if alias:
                                aliases_lower.append(alias.lower())
                    self._entries.append({
                        'name': tag,
                        'name_lower': tag.lower(),
                        'category': category,
                        'post_count': count,
                        'aliases_lower': aliases_lower,
                    })
            self._loaded = True
            logger.info(f"Loaded {len(self._entries)} tags from {self._csv_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load tag DB from {self._csv_path}: {e}")
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def count(self) -> int:
        return len(self._entries)

    def search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        if not self._loaded or not query:
            return []
        q = query.lower()
        results = []
        seen = set()
        for entry in self._entries:
            if q in entry['name_lower']:
                if entry['name'] not in seen:
                    results.append(entry)
                    seen.add(entry['name'])
            else:
                for alias in entry['aliases_lower']:
                    if q in alias:
                        if entry['name'] not in seen:
                            results.append(entry)
                            seen.add(entry['name'])
                        break
            if len(results) >= limit:
                break
        results.sort(key=lambda x: x['post_count'], reverse=True)
        return [
            {'name': r['name'], 'category': r['category'], 'post_count': r['post_count']}
            for r in results[:limit]
        ]
