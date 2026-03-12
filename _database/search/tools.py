"""K-IFRS Agentic RAG Tool 정의 및 실행기.

LLM이 선택적으로 호출하는 3개 tool의 스키마와 executor를 제공한다.
- fetch_paragraphs: 특정 문단을 chunk_id로 직접 조회
- find_referencing_chunks: 특정 기준서를 참조하는 청크를 역방향 검색
- explore_related_standards: 기준서 참조 그래프를 탐색하여 관련 기준서 발견
"""

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from search.config import CHILD_COLLECTION, chunk_id_to_int
from search.standards_expander import reverse_lookup_chunks, _fetch_definition_chunk
from search.standards_graph import get_neighbors, get_display_id

# ── Tool 스키마 (Anthropic tool_use 형식) ─────────────

TOOL_SCHEMAS = [
    {
        "name": "fetch_paragraphs",
        "description": (
            "K-IFRS 기준서의 특정 문단 내용을 가져옵니다. "
            "컨텍스트 본문에 '(문단 XX 참조)', '문단 XX에 따르면' 등의 표현이 있고 "
            "해당 내용이 정확한 답변에 필요하다고 판단될 때만 호출하세요. "
            "불필요한 경우 호출하지 마세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "references": {
                    "type": "array",
                    "description": "가져올 문단 목록",
                    "items": {
                        "type": "object",
                        "properties": {
                            "standard_id": {
                                "type": "string",
                                "description": (
                                    "기준서 ID. 반드시 'K-IFRS XXXX' 형식 "
                                    "(예: 'K-IFRS 1116')"
                                ),
                            },
                            "section_type": {
                                "type": "string",
                                "enum": ["main", "ag", "bc", "ie"],
                                "description": (
                                    "본문=main, 적용지침=ag, 결론근거=bc, 사례=ie. "
                                    "명시 없으면 main"
                                ),
                            },
                            "para_number": {
                                "type": "string",
                                "description": (
                                    "문단 번호. 본문: '26', 적용지침: 'AG12', "
                                    "결론근거: 'BC3'"
                                ),
                            },
                        },
                        "required": ["standard_id", "para_number"],
                    },
                }
            },
            "required": ["references"],
        },
    },
    {
        "name": "find_referencing_chunks",
        "description": (
            "특정 기준서를 참조하는 다른 기준서의 문단을 검색합니다. "
            "예: '제1109호를 참조하는 다른 기준서 문단이 있는가?' 같은 "
            "역방향 참조 관계를 파악할 때 호출하세요. "
            "단일 기준서 내용만으로 답변 가능하면 호출하지 마세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "standard_numbers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "검색 대상 기준서 번호 리스트. "
                        "예: ['1109', '1115']. 'K-IFRS' 접두사 없이 숫자만."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "최대 반환 문서 수 (기본값: 5)",
                    "default": 5,
                },
            },
            "required": ["standard_numbers"],
        },
    },
    {
        "name": "explore_related_standards",
        "description": (
            "기준서 참조 그래프를 탐색하여 관련 기준서를 발견합니다. "
            "특정 기준서와 직접/간접적으로 연결된 기준서를 찾고, "
            "해당 기준서의 핵심 내용(용어정의)을 반환합니다. "
            "비교 분석이나 넓은 맥락이 필요할 때 호출하세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "standard_number": {
                    "type": "string",
                    "description": (
                        "탐색 기준 기준서 번호. "
                        "예: '1115'. 'K-IFRS' 접두사 없이 숫자만."
                    ),
                },
                "hops": {
                    "type": "integer",
                    "description": (
                        "그래프 탐색 깊이. "
                        "1=직접 참조, 2=간접 참조까지 (기본값: 1)"
                    ),
                    "default": 1,
                },
                "max_results": {
                    "type": "integer",
                    "description": "최대 반환 기준서 수 (기본값: 3)",
                    "default": 3,
                },
            },
            "required": ["standard_number"],
        },
    },
]


# ── Tool Executors ────────────────────────────────────

def _build_chunk_id(
    standard_id: str, section_type: str, para_number: str,
) -> str:
    """'K-IFRS 1116', 'main', '26' -> 'KIFRS1116_main_26'."""
    prefix = standard_id.replace("K-IFRS ", "KIFRS").replace(" ", "")
    return f"{prefix}_{section_type}_{para_number}"


def execute_fetch_paragraphs(
    args: dict,
    client: QdrantClient,
    fetched_ids: set[str],
) -> tuple[list[Document], str]:
    """fetch_paragraphs tool 실행: 지정된 문단을 Qdrant에서 직접 조회."""
    refs = args.get("references", [])
    new_docs: list[Document] = []
    results_text: list[str] = []

    for ref in refs:
        section_type = ref.get("section_type", "main")
        para_number = str(ref["para_number"])
        chunk_id = _build_chunk_id(ref["standard_id"], section_type, para_number)

        if chunk_id in fetched_ids:
            results_text.append(f"[{chunk_id}] 이미 컨텍스트에 포함됨")
            continue

        try:
            points, _ = client.scroll(
                collection_name=CHILD_COLLECTION,
                scroll_filter=Filter(must=[
                    FieldCondition(
                        key="chunk_id", match=MatchValue(value=chunk_id),
                    )
                ]),
                limit=1,
                with_payload=True,
            )
            if points:
                p = points[0].payload
                new_docs.append(Document(
                    page_content=p.get("content", ""),
                    metadata={
                        "chunk_id": p.get("chunk_id", ""),
                        "parent_id": p.get("parent_id", ""),
                        "standard_id": p.get("standard_id", ""),
                        "section_type": p.get("section_type", ""),
                        "para_number": p.get("para_number"),
                        "cross_refs": p.get("cross_refs", []),
                        "has_table": p.get("has_table", False),
                        "has_example": p.get("has_example", False),
                        "fetched_by_tool": True,
                    },
                ))
                fetched_ids.add(chunk_id)
                results_text.append(f"[{chunk_id}] 조회 성공")
            else:
                results_text.append(f"[{chunk_id}] 해당 문단 없음")
        except Exception as e:
            results_text.append(f"[{chunk_id}] 조회 실패: {e}")

    return new_docs, "\n".join(results_text) or "참조 없음"


def execute_find_referencing_chunks(
    args: dict,
    client: QdrantClient,
    fetched_ids: set[str],
    query_vector: list[float] | None = None,
) -> tuple[list[Document], str]:
    """find_referencing_chunks tool 실행: 역방향 검색."""
    std_numbers = args.get("standard_numbers", [])
    max_results = args.get("max_results", 5)

    if not std_numbers:
        return [], "기준서 번호가 지정되지 않았습니다."

    docs = reverse_lookup_chunks(
        standard_numbers=std_numbers,
        client=client,
        query_vector=query_vector,
        max_results=max_results,
    )

    # 중복 제거 + fetched_ids 갱신
    new_docs: list[Document] = []
    for doc in docs:
        cid = doc.metadata.get("chunk_id", "")
        if cid not in fetched_ids:
            doc.metadata["fetched_by_tool"] = True
            new_docs.append(doc)
            fetched_ids.add(cid)

    display_stds = ", ".join(f"제{n}호" for n in std_numbers)
    if new_docs:
        lines = [f"{display_stds}를 참조하는 문단 {len(new_docs)}건 조회:"]
        for d in new_docs:
            m = d.metadata
            lines.append(
                f"  - {m.get('standard_id')} | "
                f"{m.get('section_type')} | 문단 {m.get('para_number')}"
            )
        return new_docs, "\n".join(lines)
    else:
        return [], f"{display_stds}를 참조하는 문단을 찾지 못했습니다."


def execute_explore_related_standards(
    args: dict,
    client: QdrantClient,
    fetched_ids: set[str],
) -> tuple[list[Document], str]:
    """explore_related_standards tool 실행: 그래프 탐색 + 용어정의 fetch."""
    std_number = args.get("standard_number", "")
    hops = args.get("hops", 1)
    max_results = args.get("max_results", 3)

    if not std_number:
        return [], "기준서 번호가 지정되지 않았습니다."

    neighbors = get_neighbors(std_number, hops=hops)
    if not neighbors:
        display = get_display_id(std_number)
        return [], f"{display}의 관련 기준서를 찾지 못했습니다."

    # 가중치 순 정렬
    sorted_neighbors = sorted(neighbors.keys(), key=lambda s: -neighbors[s])

    new_docs: list[Document] = []
    neighbor_info: list[str] = []

    for nbr in sorted_neighbors:
        if len(new_docs) >= max_results:
            break

        display_id = get_display_id(nbr)
        weight = neighbors[nbr]
        neighbor_info.append(f"  - {display_id} (연결 강도: {weight:.1f})")

        defn_doc = _fetch_definition_chunk(nbr, client)
        if defn_doc:
            cid = defn_doc.metadata.get("chunk_id", "")
            if cid not in fetched_ids:
                defn_doc.metadata["fetched_by_tool"] = True
                defn_doc.metadata["fetched_by_graph"] = True
                defn_doc.metadata["graph_hop"] = hops
                new_docs.append(defn_doc)
                fetched_ids.add(cid)

    source_display = get_display_id(std_number)
    lines = [f"{source_display} 관련 기준서 ({len(neighbor_info)}건):"]
    lines.extend(neighbor_info)
    if new_docs:
        lines.append(f"용어정의 {len(new_docs)}건 추가됨")

    return new_docs, "\n".join(lines)


# ── 통합 디스패처 ─────────────────────────────────────

def dispatch_tool(
    tool_name: str,
    args: dict,
    client: QdrantClient,
    fetched_ids: set[str],
    query_vector: list[float] | None = None,
) -> tuple[list[Document], str]:
    """tool_name에 따라 적절한 executor를 호출한다.

    Args:
        tool_name: LLM이 호출한 tool 이름.
        args: tool 인자 dict.
        client: Qdrant 클라이언트.
        fetched_ids: 이미 fetch된 chunk_id 집합 (중복 방지, in-place 갱신).
        query_vector: 역방향 검색에서 벡터 유사도 정렬에 사용할 쿼리 벡터.

    Returns:
        (new_docs, result_text) 튜플.
    """
    if tool_name == "fetch_paragraphs":
        return execute_fetch_paragraphs(args, client, fetched_ids)

    if tool_name == "find_referencing_chunks":
        return execute_find_referencing_chunks(
            args, client, fetched_ids, query_vector,
        )

    if tool_name == "explore_related_standards":
        return execute_explore_related_standards(args, client, fetched_ids)

    return [], f"알 수 없는 tool: {tool_name}"
