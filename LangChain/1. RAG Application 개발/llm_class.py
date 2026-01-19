from langchain_upstage import UpstageEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, FewShotChatMessagePromptTemplate
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langsmith import traceable

from config import output_examples


class TaxChatbot:
    """세법 RAG 챗봇 클래스"""
    
    def __init__(
        self,
        model: str = 'claude-3-haiku-20240307',
        temperature: float = 0.05,
        top_p: float = 1,
        max_tokens: int = None,
        index_name: str = 'tax-index-upstage',
        k: int = 20,
        fetch_k: int = 100,
        dictionary: list = None
    ):
        """        
        Args:
            model: Claude 모델명
            temperature: 생성 온도
            top_p: top_p 샘플링
            max_tokens: 최대 토큰 수
            index_name: Pinecone 인덱스 이름
            k: 검색할 문서 수
            fetch_k: 후보 문서 수
            dictionary: 용어 변환 사전
        """
        # 설정 저장
        self.model = model
        self.temperature = temperature
        self.dictionary = dictionary or ['사람을 나타내는 표현 -> 거주자']
        
        # 세션 히스토리 저장소
        self.store = {}
        
        # 컴포넌트 초기화 (한 번만 생성)
        self.llm = self._create_llm(model, temperature, top_p, max_tokens)
        self.retriever = self._create_retriever(index_name, k, fetch_k)
        self.dictionary_chain = self._create_dictionary_chain()
        self.contextualize_chain = self._create_contextualize_chain()
        self.rag_prompt = self._create_tax_prompt()
        self.rag_chain = self._create_rag_chain()
    
    # ========== Private: 컴포넌트 생성 메서드 ==========
    
    def _create_llm(self, model, temperature, top_p, max_tokens):
        """LLM 인스턴스 생성"""
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens
        )
    
    def _create_retriever(self, index_name, k, fetch_k):
        """Retriever 생성"""
        embedding = UpstageEmbeddings(model='embedding-passage')
        database = PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embedding
        )
        return database.as_retriever(search_kwargs={'k': k, 'fetch_k': fetch_k})
    
    def _create_dictionary_chain(self):
        """용어 변환 체인"""
        keyword_prompt = ChatPromptTemplate.from_template(
            f'''
            사용자의 질문 중 우리의 사전을 참고하여 사용자의 질문 속 특정 어휘만을 수정해주세요.
            만일 변경할 필요가 없다고 판단된다면 입력된 질문을 그대로 반환해주세요.
            ---
            사전: {self.dictionary}
            질문: {{question}} '''
        )
        return keyword_prompt | self.llm | StrOutputParser()
    
    def _create_contextualize_chain(self):
        """질문 재작성 체인 생성"""
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", 
             """대화 기록과 최신 사용자 질문을 보고, 대화 기록 없이도 이해할 수 있는 독립적인 질문으로 재작성하세요.
             질문에 답하지 말고, 필요하면 재작성만 하고 필요 없으면 그대로 반환하세요."""),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        return contextualize_prompt | self.llm | StrOutputParser()
    
    def _create_tax_prompt(self):
        """세법 RAG 프롬프트 생성"""
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", "{input}"),
            ("ai", "{output}"),
        ])
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=output_examples,
        )
        
        return ChatPromptTemplate.from_messages([
            ("system", """당신은 대한민국 세법 전문가입니다. 
            다음의 Context를 바탕으로 사용자의 질문에 답변해주세요.
            
            [답변 작성 규칙]
            1. 질문에 대한 핵심 내용만 간결하게 요약해서 답변하세요.
            2. n단계 모형을 설명할 때는 1단계부터 n단계까지 번호를 매겨서 명확히 구분하세요.
            3. 각 단계 설명은 1~2문장으로 짧게 요약하세요.
            4. 문서를 꼼꼼히 확인하고 사실과 다른 내용은 지어내지 마세요.
            5. 답변을 제공할 때는 참고한 소득세법 조항 번호를 첨부하세요.
            
            Let's think step by step
            ---
            Context: {context}"""),
            few_shot_prompt,
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
    
    def _create_rag_chain(self):
        """RAG 체인 생성"""
        
        def contextualize_and_retrieve(input_dict):
            chat_history = input_dict.get("chat_history", [])
            user_input = input_dict["input"]
            
            if chat_history:
                contextualized_q = self.contextualize_chain.invoke({
                    "input": user_input,
                    "chat_history": chat_history
                })
            else:
                contextualized_q = user_input
            
            docs = self.retriever.invoke(contextualized_q)
            return self._format_docs(docs)
        
        # RAG 체인 조립
        rag_chain = (
            RunnablePassthrough.assign(
                context=RunnableLambda(contextualize_and_retrieve)
            )
            | self.rag_prompt
            | self.llm
            | StrOutputParser()
        )
        
        # 히스토리 래핑
        return RunnableWithMessageHistory(
            rag_chain,
            self._get_session_history,
            input_messages_key="input",
            output_messages_key="output",
            history_messages_key="chat_history",
        )
    
    # ========== Private: 유틸리티 메서드 ==========
    
    def _get_session_history(self, session_id: str):
        """세션 히스토리 반환"""
        if session_id not in self.store:
            self.store[session_id] = InMemoryChatMessageHistory()
        return self.store[session_id]
    
    def _format_docs(self, docs):
        """문서 포맷팅"""
        return "\n\n".join(doc.page_content for doc in docs)
    
    # ========== Public: 외부에서 호출하는 메서드 ==========
    
    @traceable
    def chat(self, user_message: str, session_id: str = "abc123"):
        """
        사용자 메시지에 대한 응답 생성 (스트리밍)
        
        Args:
            user_message: 사용자 질문
            session_id: 세션 ID
            
        Returns:
            스트리밍 응답 제너레이터
        """
        # 1. 용어 변환
        refined_question = self.dictionary_chain.invoke({"question": user_message})
        
        # 2. RAG + 히스토리 + Streaming
        return self.rag_chain.stream(
            {"input": refined_question},
            config={"configurable": {"session_id": session_id}}
        )
    
    @traceable
    def chat_sync(self, user_message: str, session_id: str = "abc123") -> str:
        """
        사용자 메시지에 대한 응답 생성 (동기)
        
        Args:
            user_message: 사용자 질문
            session_id: 세션 ID
            
        Returns:
            전체 응답 문자열
        """
        # 1. 용어 변환
        refined_question = self.dictionary_chain.invoke({"question": user_message})
        
        # 2. RAG + 히스토리
        return self.rag_chain.invoke(
            {"input": refined_question},
            config={"configurable": {"session_id": session_id}}
        )
    
    def clear_history(self, session_id: str = None):
        """
        세션 히스토리 삭제
        
        Args:
            session_id: 특정 세션 ID (None이면 전체 삭제)
        """
        if session_id:
            if session_id in self.store:
                del self.store[session_id]
        else:
            self.store.clear()