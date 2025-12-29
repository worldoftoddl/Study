import streamlit as st
import torch
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenVINOEmbeddings
from optimum.intel import OVModelForCausalLM
from transformers import AutoTokenizer, pipeline, StoppingCriteria, StoppingCriteriaList
from langchain_community.llms import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 페이지 설정
st.set_page_config(page_title="K-IFRS 회계 챗봇", page_icon="💰")
st.title("💰 K-IFRS 수익기준서 챗봇") # 웹페이지 본문 최상단 제목

# 1. 모델 및 벡터 DB 로드
#@st.cache_resource # 결과값을 메모리에 저장해두고, 다음번에는 다시 실행하지 않고 저장된 값을 사용

# 리소스 로딩 함수 정의
def load_resources():
    print("리소스 로딩 시작...")
    
    # 임베딩 모델 로드
    embedding_model_id = "BAAI/bge-m3"
    embeddings = OpenVINOEmbeddings(
        model_name_or_path=embedding_model_id,
        model_kwargs={"device": "GPU"}, 
        encode_kwargs={"normalize_embeddings": True}
    )

    # 벡터 DB 로드
    vectorstore = FAISS.load_local(
        "./my_vector_db", 
        embeddings, 
        allow_dangerous_deserialization=True # 로컬 파일을 신뢰
    )
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 4})

    # LLM & 토크나이저 로드
    model_path = "./my_llm_model" # 저장했던 폴더 경로
    
    ov_model = OVModelForCausalLM.from_pretrained(
        model_path,
        device="GPU",
        ov_config={"PERFORMANCE_HINT": "LATENCY"}
        # 이미 export=True로 저장했으므로 로드만 하면 됨
    )
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    print("리소스 로딩 완료!")
    return retriever, ov_model, tokenizer

# 리소스 로드 실행(예외처리)
try:
    # 위에서 만든 함수를 실행해 객체들을 변수에 담음
    retriever, ov_model, tokenizer = load_resources()
except Exception as e:
    st.error(f"모델을 불러오는 중 오류가 발생했습니다. 경로를 확인해주세요: {e}")
    st.stop()

# 2. 파이프라인 및 체인 설정
class StopOnTokens(StoppingCriteria):
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        stop_ids = [
            tokenizer.convert_tokens_to_ids("<|eot_id|>"),
            tokenizer.convert_tokens_to_ids("assistant"),
            tokenizer.convert_tokens_to_ids("user")
        ]
        for stop_id in stop_ids:
            if input_ids[0][-1] == stop_id:
                return True
        return False

# 파이프라인 생성 (모델 객체는 캐싱됨)
pipe = pipeline(
    "text-generation",
    model=ov_model,
    tokenizer=tokenizer,
    max_new_tokens=4096,
    do_sample=True,
    temperature=0.1,
    top_p=0.9,
    repetition_penalty=1.0,
    return_full_text=False,
    stopping_criteria=StoppingCriteriaList([StopOnTokens()])
)

llm = HuggingFacePipeline(pipeline=pipe)

# 프롬프트 템플릿 (기존 코드 유지)
llama_template = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

당신은 K-IFRS 회계 기준 전문가입니다. 다음 [참조 문서]를 바탕으로 사용자의 질문에 대해 명확하고 정확하게 답변해주세요.

[답변 작성 규칙]
1. 질문에 대한 핵심 내용만 간결하게 요약해서 답변하세요.
2. 불필요한 배경 설명은 제외하세요.
3. n단계 모형을 설명할 때는 번호를 매겨 구분하세요.
4. 문서를 꼼꼼히 확인하고 사실과 다른 내용은 지어내지 마세요.

Let's think step by step<|eot_id|><|start_header_id|>user<|end_header_id|>

[참조 문서]
{context}

[질문]
{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

prompt = PromptTemplate.from_template(llama_template)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# 체인 구성
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 3. Streamlit 채팅 인터페이스 구현

# 세션 상태 초기화 (대화 기록 저장)
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 내용 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if query := st.chat_input("수익기준서의 내용에 대해 궁금한 점을 물어보세요."):
    # 사용자 메시지 표시 및 저장
    with st.chat_message("user"): # 사용자용 말풍선
        st.markdown(query) # 방금 입력한 질문을 화면에 보여줌
    st.session_state.messages.append({"role": "user", "content": query}) # 질문 내용을 세션 저장소(기록)에 추가

    # 답변 생성
    with st.chat_message("assistant"): # AI용 말풍선
        message_placeholder = st.empty() # 답변이 들어갈 빈 공간을 미리 확보
        full_response = ""
        
        with st.spinner("문서를 검색하고 답변을 생성 중입니다..."): # 답변이 나올 때까지 로딩 표시
            try:
                response = rag_chain.invoke(query)
                
                # 답변 정제
                if "assistant" in response:
                    response = response.split("assistant")[-1].strip()
                
                full_response = response
                message_placeholder.markdown(full_response)
            except Exception as e:
                full_response = f"오류가 발생했습니다: {str(e)}"
                message_placeholder.error(full_response)

    # 답변 저장
    st.session_state.messages.append({"role": "assistant", "content": full_response})