from langchain_upstage import UpstageEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate


def get_ai_message(user_message):

    embedding = UpstageEmbeddings(model='embedding-passage')
    index_name = 'tax-index-upstage'
    database = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=embedding)

    llm = ChatAnthropic(
        model='claude-3-haiku-20240307',
        temperature=0.05,
        top_p=1
        # # max_tokens=,
        # # timeout=,
        # # max_retries=,
    )

    retriever = database.as_retriever(
        search_kwargs={'k': 20, 'fetch_k': 50}
    )
    
        
    # 사전 정의
    dictionary = ['사람을 나타내는 표현 -> 거주자']
    kward_prompt = ChatPromptTemplate.from_template(f'''                                              
        사용자의 질문 중 우리의 사전을 참고하여 사용자의 질문 속 특정 어휘만을 수정해주세요.
        만일 변경할 필요가 없다고 판단된다면 입력된 질문을 그대로 반환해주세요.
        ---
        사전: {dictionary}
        질문: {{question}} 
    ''')      
    
    # 용어 필터 chain 만들기
    dict_chain = kward_prompt | llm | StrOutputParser()

    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", """다음 context를 바탕으로 질문에 답하세요.
        당신은 대한민국 세법 전문가입니다. 다음 Context를 바탕으로 사용자의 질문에 대해 명확하고 정확하게 답변해주세요.
        
        [답변 작성 규칙]
        1. 질문에 대한 핵심 내용만 간결하게 요약해서 답변하세요.
        2. n단계 모형을 설명할 때는 1단계부터 n단계까지 번호를 매겨서 명확히 구분하세요.
        3. 각 단계 설명은 1~2문장으로 짧게 요약하세요.
        4. 문서를 꼼꼼히 확인하고 사실과 다른 내용은 지어내지 마세요.
        
        다음은 Few-shot 예시입니다. 
        question: 확신유형의 보증과 용역유형의 보증에 대해 설명해줘.
        answer: 확신유형의 보증은 수행의무로 회계처리하지 않고 용역유형의 보증은 수행의무로 회계처리한다.
        
        Let's think step by step
        
        \n\nContext: {context}"""),
        ("human", "{question}")
    ])

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    tax_qa_chain = (
        dict_chain |
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    )
    
    ai_message = tax_qa_chain.invoke({'question': user_message})
    return ai_message
