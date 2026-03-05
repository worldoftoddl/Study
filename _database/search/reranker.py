"""
K-IFRS Reranker — Strategy Pattern

로컬(무료) 또는 Cohere API(유료) reranker를 환경변수로 전환 가능.

환경변수:
    RERANKER_TYPE=local     # dragonkue/bge-reranker-v2-m3-ko (기본값)
    RERANKER_TYPE=cohere    # Cohere Rerank API (COHERE_API_KEY 필요)
"""

import math
import os
from abc import ABC, abstractmethod

from langchain_core.documents import Document


class BaseReranker(ABC):
    """Reranker 추상 베이스 클래스."""

    @abstractmethod
    def rerank(
        self, query: str, documents: list[Document], top_n: int = 5
    ) -> list[Document]:
        """문서를 쿼리 관련도 순으로 재정렬한다.

        Args:
            query: 검색 쿼리 문자열.
            documents: 재정렬할 LangChain Document 리스트.
            top_n: 반환할 상위 문서 수.

        Returns:
            관련도 순으로 정렬된 list[Document]. 각 문서의
            metadata["rerank_score"]에 정규화된 점수(0~1)가 포함된다.
        """
        ...


class LocalReranker(BaseReranker):
    """dragonkue/bge-reranker-v2-m3-ko 기반 로컬 cross-encoder reranker."""

    def __init__(self, model_name: str = "dragonkue/bge-reranker-v2-m3-ko"):
        from FlagEmbedding import FlagReranker

        self.model = FlagReranker(model_name, use_fp16=True)
        self.model_name = model_name

    def rerank(
        self, query: str, documents: list[Document], top_n: int = 5
    ) -> list[Document]:
        if not documents:
            return []

        pairs = [[query, doc.page_content] for doc in documents]
        raw_scores = self.model.compute_score(pairs)

        # compute_score는 단일 pair일 때 float, 복수일 때 list 반환
        if isinstance(raw_scores, (int, float)):
            raw_scores = [raw_scores]

        # Sigmoid 정규화: raw logit → [0, 1]
        scored_docs = []
        for doc, raw_score in zip(documents, raw_scores):
            normalized = 1 / (1 + math.exp(-raw_score))
            new_doc = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "rerank_score": round(normalized, 6)},
            )
            scored_docs.append(new_doc)

        scored_docs.sort(key=lambda d: d.metadata["rerank_score"], reverse=True)
        return scored_docs[:top_n]


class CohereReranker(BaseReranker):
    """Cohere Rerank API 기반 reranker."""

    def __init__(
        self,
        model: str = "rerank-multilingual-v3.0",
        api_key: str | None = None,
    ):
        import cohere

        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        self.client = cohere.ClientV2(api_key=self.api_key)
        self.model = model

    def rerank(
        self, query: str, documents: list[Document], top_n: int = 5
    ) -> list[Document]:
        if not documents:
            return []

        doc_texts = [doc.page_content for doc in documents]
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=doc_texts,
            top_n=top_n,
        )

        reranked: list[Document] = []
        for result in response.results:
            original_doc = documents[result.index]
            new_doc = Document(
                page_content=original_doc.page_content,
                metadata={
                    **original_doc.metadata,
                    "rerank_score": round(result.relevance_score, 6),
                },
            )
            reranked.append(new_doc)

        return reranked


def get_reranker(reranker_type: str | None = None) -> BaseReranker:
    """Reranker 팩토리 함수.

    Args:
        reranker_type: "local" 또는 "cohere". 미지정 시 RERANKER_TYPE 환경변수 사용.
    """
    rtype = (reranker_type or os.getenv("RERANKER_TYPE", "local")).lower()

    if rtype == "local":
        return LocalReranker()
    elif rtype == "cohere":
        return CohereReranker()
    else:
        raise ValueError(
            f"알 수 없는 reranker 타입: '{rtype}'. 'local' 또는 'cohere'를 사용하세요."
        )
