"""K-IFRS 용어 정의 인덱스 로더.

terms_index.json을 로드하여 기준서별 용어정의 청크 매핑을 제공한다.
_fetch_definition_chunk() (standards_expander)와 fetch_term_definitions tool의
백엔드로 사용된다.
"""

import json
import os

# 용어 인덱스 캐시
_terms_index: dict | None = None
_INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "output", "terms_index.json"
)


def _load_terms_index(index_path: str | None = None) -> dict:
    """용어 인덱스를 로드하고 캐시한다."""
    global _terms_index
    if _terms_index is not None:
        return _terms_index

    path = index_path or _INDEX_PATH
    if not os.path.exists(path):
        _terms_index = {"standard_to_chunk": {}, "chunk_id_list": []}
        return _terms_index

    with open(path, "r", encoding="utf-8") as f:
        _terms_index = json.load(f)
    return _terms_index
