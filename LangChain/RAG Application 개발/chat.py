# Streamlit은 사용자 상호작용이 있을 때마다 스크립트 전체를 다시 실행함.
# 메시지 전송할 때마다 터미널에 숫자가 뜨는 걸로 확인 할 수 있음
from dotenv import load_dotenv
from llm import get_ai_message      # 다른 파일에 있는건 함수에 대고 ctr + . 하면 import 단축키 나옴

load_dotenv()


import streamlit as st
st.set_page_config(page_title='소득세 챗봇', page_icon= '🤖')

st.title('🤖소득세 챗봇')
st.caption('    소득세와 관련한 궁금증이 있으신가요?')

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

    with st.spinner('챗봇이 고민하는 중입니다'):
      ai_message = get_ai_message(user_question)
      with st.chat_message('ai'):   # ai message를 받아 이 부분에 넣어주면 됨
        st.write(ai_message)
      st.session_state.message_list.append({'role': 'ai', 'content': ai_message})

