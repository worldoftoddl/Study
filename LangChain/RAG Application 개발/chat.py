# Streamlit은 사용자 상호작용이 있을 때마다 스크립트 전체를 다시 실행함.
# 메시지 전송할 때마다 터미널에 숫자가 뜨는 걸로 확인 할 수 있음
from dotenv import load_dotenv
load_dotenv()

from llm import get_ai_response      # 다른 파일에 있는건 함수에 대고 ctr + . 하면 import 단축키 나옴


import streamlit as st
st.set_page_config(page_title='소득세 챗봇', page_icon= '🤖')

st.title('🤖소득세 챗봇')
st.caption('소득세와 관련한 궁금증이 있으신가요?')

# st.session_state는 스크립트가 재실행되어도 초기화되지 않는 변수를 저장하는 딕셔너리
if 'message_list' not in st.session_state:    # 다음번 세션에는 초기화되지 않도록
    st.session_state.message_list = []      

for message in st.session_state.message_list:
  with st.chat_message(message['role']):
    st.write(message['content'])


# := 코끼리 연산자는 변수에 값을 할당하는 동시에 반환
# 값 할당과 조건 검사(사용자 질문 입력)를 한줄로 진행
if user_question := st.chat_input(placeholder='무엇이 궁금하신가요?'):  # 여기서 사용자 입력을 query로 받고,
    with st.chat_message('user'):
      st.write(user_question)
    st.session_state.message_list.append({'role': 'user', 'content': user_question})
    
    with st.chat_message('ai'):
        # st.write_stream()이 스트리밍 출력 후 전체 텍스트를 반환함
        ai_response = st.write_stream(get_ai_response(user_question))
    
    st.session_state.message_list.append({'role': 'ai', 'content': ai_response})

# 앞으로 해야 할 것들 정리

## Retrieval: 
# 조문 별 청킹 및 수식 설명 추가 
# 한번 불러온 청크들 가운데 관련성 있는 것들을 추리는 Chain 추가
# 조특법 및 국기법

# Generate 
# 온도나 P와 관련한 성능 테스트해보기
# Ollama 한국어 모델 적용해서 claude와 비슷한 성능 내보기

## BM25 - RAG 재생목록 첫 영상 참고