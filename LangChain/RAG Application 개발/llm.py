from langchain_upstage import UpstageEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, FewShotChatMessagePromptTemplate
from langchain_core.chat_history import InMemoryChatMessageHistory          # 추가
from langchain_core.runnables.history import RunnableWithMessageHistory     # 추가
from config import output_examples



# 세션별 히스토리 저장소
store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


def get_claude(model='claude-3-haiku-20240307', temperature=0.05, top_p=1, max_tokens=None):
    claude = ChatAnthropic(
        model= model,
        temperature= temperature,
        top_p= top_p,
        max_tokens= max_tokens
        # timeout=,
        # max_retries=,
        )
    return claude
  

def get_dictionary_chain(llm=None, dictionary=None):
    if llm is None:
        llm = get_claude()
    if dictionary is None:
        dictionary = ['사람을 나타내는 표현 -> 거주자']
    
    keyword_prompt = ChatPromptTemplate.from_template(
      f'''
      사용자의 질문 중 우리의 사전을 참고하여 사용자의 질문 속 특정 어휘만을 수정해주세요.
      만일 변경할 필요가 없다고 판단된다면 입력된 질문을 그대로 반환해주세요.
      ---
      사전: {dictionary}
      질문: {{question}} '''
    )      
    
    # 용어 필터 chain 만들기
    dict_chain = keyword_prompt | llm | StrOutputParser()
    return dict_chain


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def get_retriever(index_name=None, embedding=None, k=20, fetch_k=100):
    if index_name is None:
        index_name = 'tax-index-upstage'
    if embedding is None:
        embedding = UpstageEmbeddings(model='embedding-passage')

    database = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=embedding)
    retriever = database.as_retriever(search_kwargs={'k': k, 'fetch_k': fetch_k})
    return retriever


# 히스토리 기반 질문 재작성 체인
def get_contextualize_chain(llm=None):
    if llm is None:
        llm = get_claude()
    
    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system", 
         """대화 기록과 최신 사용자 질문을 보고, 대화 기록 없이도 이해할 수 있는 독립적인 질문으로 재작성하세요.
         질문에 답하지 말고, 필요하면 재작성만 하고 필요 없으면 그대로 반환하세요."""),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    contextualize_chain = contextualize_prompt | llm | StrOutputParser()
    return contextualize_chain


# Few-shot 추가 필요
def get_tax_prompt():

    example_prompt = ChatPromptTemplate.from_messages(
        [
            ("human", "{input}"),
            ("ai", "{output}"),
        ]
    )
    few_shot_prompt = FewShotChatMessagePromptTemplate(
        example_prompt=example_prompt,
        examples=output_examples,
    )
    
    rag_prompt = ChatPromptTemplate.from_messages([
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
    return rag_prompt


def get_rag_chain(llm=None, retriever=None, contextualize_chain=None, rag_prompt=None):
    if llm is None:
        llm = get_claude()
    if retriever is None:
        retriever = get_retriever()
    if contextualize_chain is None:
        contextualize_chain = get_contextualize_chain(llm)
    if rag_prompt is None:
        rag_prompt = get_tax_prompt()
    
    def contextualize_and_retrieve(input_dict):
        # 히스토리가 있으면 질문 재작성, 없으면 그대로
        chat_history = input_dict.get("chat_history", [])
        user_input = input_dict["input"]
        
        if chat_history:
            contextualized_q = contextualize_chain.invoke({
                "input": user_input,
                "chat_history": chat_history
            })
        else:
            contextualized_q = user_input
        
        # 재작성된 질문으로 검색
        docs = retriever.invoke(contextualized_q)
        return format_docs(docs)
    
    # RAG 체인 조립
    rag_chain = (
        RunnablePassthrough.assign(
            context=RunnableLambda(contextualize_and_retrieve)
        )
        | rag_prompt
        | llm
        | StrOutputParser()
    )
    
    # 히스토리 래핑
    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        output_messages_key="output",
        history_messages_key="chat_history",
    )
    
    return conversational_rag_chain

def get_ai_response(user_message, session_id="abc123"):
    # 1. 용어 변환
    dictionary_chain = get_dictionary_chain()
    refined_question = dictionary_chain.invoke({"question": user_message})
    
    # 2. RAG + 히스토리 + Streaming
    rag_chain = get_rag_chain()
    ai_response = rag_chain.stream(
        {"input": refined_question},
        config={"configurable": {"session_id": session_id}}
    )
    
    return ai_response