from dotenv import load_dotenv
load_dotenv()

# from llm import get_ai_response
from llm_class import TaxChatbot

import streamlit as st

# 페이지 설정
st.set_page_config(
    page_title='소득세 챗봇',
    page_icon='🤖',
    layout='centered'
)

# 커스텀 CSS - Claude 스타일 다크 테마
st.markdown("""
<style>
    /* 전체 배경 */
    .stApp {
        background-color: #2b2b2b;
    }
    
    /* 메인 컨테이너 */
    .main .block-container {
        max-width: 800px;
        padding-top: 2rem;
    }
    
    /* 타이틀 */
    h1 {
        color: #e0e0e0;
        text-align: center;
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    /* 캡션 */
    .stCaption {
        text-align: center;
        color: #888;
    }
    
    /* 채팅 메시지 컨테이너 */
    .stChatMessage {
        background-color: #363636;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    /* 사용자 메시지 */
    [data-testid="stChatMessageContent-user"] {
        background-color: #424242;
    }
    
    /* AI 메시지 */
    [data-testid="stChatMessageContent-assistant"] {
        background-color: #363636;
    }
    
    /* 입력창 */
    .stChatInput > div {
        background-color: #363636;
        border-color: #4a4a4a;
        border-radius: 12px;
    }
    
    /* 텍스트 색상 */
    .stMarkdown, .stText, p {
        color: #e0e0e0;
    }
    
    /* 스크롤바 */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #2b2b2b;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #4a4a4a;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# 헤더
st.title('🤖 소득세 챗봇')
st.caption('소득세와 관련한 궁금증을 물어보세요')

# 세션 초기화
if 'message_list' not in st.session_state:
    st.session_state.message_list = []

if "chatbot" not in st.session_state:
    st.session_state.chatbot = TaxChatbot()

# 대화 기록 표시
for message in st.session_state.message_list:
    role = 'assistant' if message['role'] == 'ai' else message['role']
    with st.chat_message(role):
        st.markdown(message['content'])

# 입력 처리
if user_question := st.chat_input(placeholder='무엇이 궁금하신가요?'):
    with st.chat_message('user'):
        st.markdown(user_question)
    st.session_state.message_list.append({'role': 'user', 'content': user_question})
    
    with st.chat_message('assistant'):
        ai_response = st.write_stream(st.session_state.chatbot.chat(user_question, session_id= 'user123'))
    
    st.session_state.message_list.append({'role': 'ai', 'content': ai_response})


# ##############################################
# TODO정리

## Retrieval: 
# 조문 별 청킹 및 수식 설명 추가 
# 한번 불러온 청크들 가운데 관련성 있는 것들을 추리는 Chain 추가
# 조특법 및 국기법
# 환각 여부를 판단하기 위한 인용 출처 표기

# Generate 
# 온도나 P와 관련한 성능 테스트해보기
# GPU 이용한 Ollama 한국어 모델 적용해서 claude와 비슷한 성능 내보기

## BM25 - RAG 재생목록 첫 영상 참고

# upstage의 solar-legal 모델 사용해보기
# Intellicon KOALLA: 언어 적응형 AI 사용해보기

# 편(Pyeon) - 장(Jang) - 절(Jeol) - 관(Gwan) - 조(Jo) - 항(Hang) - 호(Ho) - 목(Mok)의 구조를 데이터베이스 구조에 반영하기
#    파싱 알고리즘: 정규표현식(Regex)과 계층적 파서(Hierarchical Parser)를 결합하여, 
#                   문서 내에서 "제1조(목적)"과 같은 헤더를 식별하고, 해당 조항에 속하는 항, 호, 목을 트리 구조(Tree Structure)로 추출해야 한다.
#    메타데이터 상속: 하위 단위(예: 호)를 벡터화할 때, 상위 단위(조, 항)의 텍스트와 제목을 메타데이터로 함께 임베딩해야 한다. 
#                    그렇지 않으면 "1. 징역 5년에 처한다"라는 텍스트만으로는 이것이 어떤 범죄에 대한 처벌인지 알 수 없다.

# 판결문이나 계약서는 PDF 형식으로 제공되는 경우가 많으며, 다단 편집이나 표(Table)가 포함되어 있다. Upstage의 'Document Parse'와 같은 고급 OCR 및 레이아웃 분석 도구는 이러한 비정형 문서를 구조화된 마크다운(Markdown)이나 HTML로 변환하는 데 탁월하다.1   


# https://gemini.google.com/share/3a867158fc77