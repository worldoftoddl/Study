## 2025년 8월 19일 화이팅입니다!!

# 오류가 발생하는 두가지 상황

# 1. 코드를 실행하기 이전에 발생 (SyntaxError - 구문오류)
# 2. 코드를 실행하는 도중에 발생 (RuntimeError - 예외)


## 두번째 예외를 처리하기 위한 조치 - 예외처리
user_input = input("반지름 입력")

if user_input.isdigit():

    num_input = int(user_input)
    print(f"원의 반지름: {num_input}")
    print(f"원의 둘레: {num_input * 2 * 3.14}")
    print(f"원의 넓이: {num_input ** 2 * 3.14}")

#여기가 예외처리
else:
    print("정수를 입력해 주십시오")


## 모든 경우의 수를 if else로 나누기 힘든 경우 ->
## try, except 구문!!!

# try:
    # 예외 발생 가능한 구문
# except:
    # 예외 발생시 실행할 구문

try:
    num_input = int(input("정수만 입력해 주십시오"))
    print(f"원의 반지름: {num_input}")
    print(f"원의 둘레: {num_input * 2 * 3.14}")
    print(f"원의 넓이: {num_input ** 2 * 3.14}")
except:
    print("오류가 발생했습니다!")

## 강제 종료를 막는 코드
try:
    num_input = int(input("정수만 입력해 주십시오"))
    print(f"원의 반지름: {num_input}")
    print(f"원의 둘레: {num_input * 2 * 3.14}")
    print(f"원의 넓이: {num_input ** 2 * 3.14}")
except:
    pass

list_a = [1,2,3,"사",5,6,"八"]
list_num = []
for i in list_a:    
    try:
        list_num.append(float(i))
    except:
        pass
print(list_num)


## try except 이후 
# else - 예외 가능성 코드를 try except로, 나머지 구문은 else에 넣는다고 보면 됨
# finally - 두 경우 모두에 마지막으로 실행할 코드 close() 등의 파일처리가 자리하는 부분 (반복문이나 함수 내에서 try 구문 사용시)

# try:
    # 예외발생 가능 구문
# except:
    # 예외 발생시 구문
# else:
    # 예외 발생하지 않았을 시 구문

try:
    num_input = int(input("반지름을 입력해주십시오"))
except:
    print("정수가 입력되지 않았습니다")
else:
    print(f"원의 반지름: {num_input}")
    print(f"원의 둘레: {num_input * 2 * 3.14}")
    print(f"원의 넓이: {num_input ** 2 * 3.14}")
finally:
    print("프로그램을 마칩니다.")




## 2025년 8월20일 화이팅입니다!!!

## 모든 예외를 칭할 때: Exception
try:
    # 정수로 변환
    num_input = int(input("정수만 입력해 주십시오"))
    # 각 값을 출력
    print(f"원의 반지름: {num_input}")
    print(f"원의 둘레: {num_input * 2 * 3.14}")
    print(f"원의 넓이: {num_input ** 2 * 3.14}")
except Exception as ex:
    print("예외가 발생했습니다!")
    print("예외의 타입:", type(ex))
    print("예외:", ex)

'''
정수만 입력해 주십시오
싫은데?

예외가 발생했습니다!
예외의 타입: <class 'ValueError'>
예외: invalid literal for int() with base 10: '싫은데?'
'''
# 예외가 발생했을 때 프로그램을 종료시키지 않고 예외를 표시해주는 모습!!


## 예외 객체별로 나누어 코딩을 하고자 할 때
lst = [1,2,3,4,5,6,7,8,9]

try:
    num_input = int(input("정수 입력"))
    print(f"{num_input}번째 요소: {lst[num_input]}")
except ValueError as exception:
    print("정수 입력이라니까?")
    print("너가 한 짓을 봐:", exception)
except IndexError as exception:
    print("리스트 인덱스를 벗어났어")
    print("봐봐:",exception)

'''
그러나 이렇게 경우의 수를 나누어도 예외는 발생 가능하다.
'''

lst = [1,2,3,4,5,6,7,8,9]

try:
    num_input = int(input("정수 입력"))
    print(f"{num_input}번째 요소: {lst[num_input]}")
    예외.나와주세요()                                     ## 의도적으로 예외 발생시킴 (NameError)
except ValueError as exception:
    print("정수 입력이라니까?")
    print("너가 한 짓을 봐:", exception)
except IndexError as exception:
    print("리스트 인덱스를 벗어났어")
    print("봐봐:",exception)


'''
그럴 때 마지막에 Exception을 이용해 미처 잡지 못한 에러들을 커버해
프로그램이 방지되는 것을 막을 수 있음
'''

try:
    num_input = int(input("정수 입력"))
    print(f"{num_input}번째 요소: {lst[num_input]}")
    예외.나와주세요()                                     ## 의도적으로 발생시킨 예외
except ValueError as exception:
    print("정수 입력이라니까?")
    print("너가 한 짓을 봐:", exception)
except IndexError as exception:
    print("리스트 인덱스를 벗어났어")
    print("봐봐:",exception)
except Exception as exception:
    print("파악하지 못한 예외가 발생했습니다")
    print("예외:", exception)


'''
물론 모든 예외를 예측하는 것이 쉬운 일은 아니고
또한 치명적인 상황에서도 종료되지 않는 프로그램은 그것대로 문제이다.

다음으로는 프로그램 개발 과정에서 미완성임을 나타내기 위하 예외를 발생시키는
raise 키워드를 사용해 보자.
'''

try:
    num_input = int(input("정수 입력"))
    print(f"{num_input}번째 요소: {lst[num_input]}")
except ValueError as exception:
    print("정수 입력이라니까?")
    print("네가 한 짓을 봐:", exception)
except IndexError as exception:
    print("리스트 인덱스를 벗어났어")
    print("봐봐:",exception)
except Exception as exception:
    print("파악하지 못한 예외가 발생했습니다")
    print("예외:", exception)
## 이 지점에서 개발이 완료되지 않았음을 보여줌
raise NotImplementedError

