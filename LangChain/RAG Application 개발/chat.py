print(1)
import streamlit as st
st.set_page_config(page_title='소득세 챗봇', page_icon= '🤖')

st.title('🤖소득세 챗봇')
st.caption('소득세와 관련한 궁금증이 있으신가요?')

print(2)
# Session State also supports attribute based syntax
if 'message_list' not in st.session_state:
    st.session_state.message_list = []

print(3)
print(f'before == {st.session_state.message_list}')

for message in st.session_state.message_list:
  with st.chat_message(message['role']):
    st.write(message['content'])

# := 코끼리 연산자는 변수에 값을 할당하는 동시에 반환
# 값 할당과 조건 검사를 한줄로 진행할 수 있어 편함
if user_question := st.chat_input(placeholder='무엇이 궁금하신가요?'):
  with st.chat_message('user'):
    st.write(user_question)
  st.session_state.message_list.append({'role': 'user', 'content': user_question})

print(f'after == {st.session_state.message_list}')
print(4)