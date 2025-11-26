#2025년 8월 10일 화이팅입니다!!

def three_hello():
    print("안녕하세요")
    print("안녕하세요")
    print("안녕하세요")

three_hello()


def print_n_times(value, n=3):  # 가변 매개변수인 n이 기본으로 3으로 설정되어있다. 
    for i in range(n):          # 마치 print()함수가 end = "\n" 인것과 마찬가지이다.
        print(value)            # 여기서 일반 매개변수인 value는 절대 n 뒤에 위치하게 정의하지 못한다

print_n_times("안녕하세요", n=5)


#예제
def f(x):
    return 2*x+1
print(f(10))

def f(x):
    return x**2+x*2+1
print(f(10))

scores = [85, 92, 78, 96, 88]
*others, highest = sorted(scores)
print(highest)

def mul(*values):
    answer = 1
    for i in values:
        answer *= i
    return answer
print(mul(5, 7, 9, 10))

def factorial(x):       ## 반복문이 아닌 재귀함수를 이용한 팩토리얼 계산
    if x == 0:
        return 1
    else:
        return x * factorial(x-1)
print(factorial(3))     ## 재귀함수는 컴퓨팅 자원을 많이 소모한다는 이야기가 있다.


##재귀함수를 이용해 도출한 피보나치 수열 (재귀함수의 위험성)
counter = 0

def fib(n):
    print(f"fibonacci_{n}를 구합니다")
    global counter                      ## 함수 내부에서 원래 불가능한 외부 값 참조를 위해 사용하는 global 함수.
    counter += 1
    if n == 1:
        return 1
    if n == 2:
        return 1
    else:
        return fib(n-2) + fib(n-1)

fib(35)
print("---")
print(f"피보나치 35을 구하는데 사용된 계산 횟수는 {counter}회 입니다.")
## 피보나치 35의 경우에는 18454929번 계산함. 
## 재귀 함수는 한번 구한 값도 반복해서 다시 계산하기 때문

## 이를 위해 메모화(memoization)을 활용하는 것임
## 다시 말해 한번 계산한 값은 다시 계산하지 않게 만들기 위함임.

counter = 0

dictionary = {
    1 : 1,
    2 : 1
}

def fib(n):
    global counter
    counter += 1
    if n in dictionary:
        return dictionary[n]
    else:
        output = fib(n-2) + fib(n-1)
        dictionary[n] = output
        return output

print(fib(35))
print(f"fib 35를 구하기 위한 계산 횟수는 {counter}회 입니다.")

## 메모화 이전 계산횟수 : 18454929
## 메모화 이후 계산횟수 : 67회




## 2025년 8월 12일 화이팅입니다!!

#리스트 평탄화 재귀함수
def flatten(data):
    output = []
    for i in data:
        if type(i) == list:
            output += i
        else:
            output.append(i)
    return output

example = [[1,2,3],[4,5],6,7,[8,9,0]]
print(flatten(example))

example2 = [[1,2,3],[4,5],6,7,[8,[9,0]]]
print(flatten(example2))


def flatten2(data):
    output = []
    for i in data:
        if type(i) == list:
            output += flatten(i)
        else:
            output.append(i)
    return output

example2 = [[1,2,3],[4,5],6,7,[8,[9,0]]]
print(flatten2(example2))

example3 = [[1,[2,3]],[4,5],6,[7,[8,[9,0]]]]
print(flatten2(example3))
# 결국 1차원에서 2차원 평탄화가 된 부분이다.
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
##예제
#최대 10명이 앉을 수 있는 테이블과 100명의 사람이 있다고 할 때, 100명의 사람들이 나눠 앉을 수 있는 경우의 수를 구하는 프로그램을 작성하시오.

min_share = 2
max_share = 10
people = 100
memo = {}

def prob(remain, sit):
    key = (remain, sit)
    # 종료 조건
    if key in memo:
        return memo[key]
    if remain < 0:
        return 0    # 무효이므로 0을 반환
    if remain == 0: 
        return 1    # 유효하므로 1을 반환
    #재귀 처리
    count = 0
    for i in range(sit, max_share + 1):
        count += prob(remain -i, i)
    # 메모화 처리
    memo[key] = count
    # 종료
    return count

print(prob(people, min_share))

## 정확히 이해하지 못한 개념이므로 다시 와서 풀어봐야 함



## 2025년 8월 13일 화이팅입니다!!

#튜플에 관하여
tuple_a = (10, 20, 30, 40)
print(type(tuple_a))
print(tuple_a[0:2])

tuple_b = 10, 20, 30, 40    ## 이런 방식으로도 튜플을 선언할 수 있다.
print(type(tuple_b))
print(tuple_b[0:2])

x, y, z = 10, 20, 30    ## 이런 방식으로 생성되는 자료 또한 튜플이다.

print(x,y)
x, y = y, x
print(x,y)  ## 변수 값 교환이 이렇게 편리하게 이루어질 수 있다.

## 또한 튜플은 함수에서 값 반환에도 이용된다.
def x():
    return 10, 20
print(x())
print(type(x()))    # <class 'tuple'>

# 이전에 이용한 enumerate()함수도 튜플을 반환하는 형태의 함수이다.
for i,j in enumerate([1,2,3,4,5,6,7]):
    print(f"{i}번째 요소는 {j}입니다")
    print(i,j)


## callback_function : 매개변수로 함수를 대입하는 방식
def tentimes(func, n):
    for i in range(n):
        func()

def sayhello():
    print("Hello World!")

print(tentimes(sayhello, 10))


## callback_function의 대표적 예시 - map()과 filter()

# map(함수, 리스트) - map의 매개변수에 int가 callback_function으로 기능함
a,b = map(int, input().split())     # input()을 split()하여 만든 문자열 리스트에 int()함수를 적용함
print(a,b)

def square(x, y=2):
    return x ** y

result_a = list(map(square, [1,2,3,4,5]))       ## 중요!! 제너레이터이므로 list()함수로 묶어줘야함
print(result_a)                                 ## 여기서 square의 매개변수를 전달하고 싶다?? -> 이따 배울 lambda를 쓰는거임!!

# filter(함수, 리스트) -> 리스트 컴프리헨션에 비해 메모리 소모가 적고, 함수 재활용이 가능하다
def under_3(x):
    return x<3

abc = list(filter(under_3, [1,2,3,4,5,6,7]))        ## 중요!! 제너레이터이므로 list()함수로 묶어줘야함
print(abc)



### lambda 매개변수 : return 값 - def와 return을 작성하지 않고 간편하게 선언하는 함수 (코드 가독성 개선)

def square(x, y=2):
    return x ** y

result_a = list(map(lambda x: square(x, y=3), [1,2,3,4,5]))       ## lambda로 특정 매개변수를 전달할 수 있음
print(result_a) 



def under_3(x):
    return x<3

abc = list(filter(lambda x: x<3, [1,2,3,4,5,6,7]))                ## 이 경우 under_3를 선언할 필요가 없는 것
print(abc)




### 파일 관련 함수
## open('파일 경로', '모드 설정 - write, append, read')
file = open('test.txt', 'w', encoding='utf-8')      ## encoding='utf-8'은 시스템 의존을 피하기 위함

file.write("Hello World!")

file.close()            ## close() 괄호 까먹었더라~


## with : open() ~~~후에 close()를 자동으로 해주는 구문
with open('test.txt', 'r', encoding='utf-8') as file:
    content = file.read()               ## 구문이 끝나는 지점에서 자동으로 file.close()

print(content)



## 2025년 8월 15일 광복절 화이팅입니다!!

#파일 작성하기
import random
korean = list("가나다라마바사아자차카타파하")

with open("info.txt" , "w", encoding='utf-8') as file:
    for i in range(50):
        name = random.choice(korean) + random.choice(korean)
        weight = random.randint(40, 100)
        height = random.randint(140,200)
        
        file.write(f"{name}, {weight}, {height}\n")


with open("info.txt" , "r", encoding='utf-8') as file:
    for line in file:
        (name, weight, height) = line.strip().split(", ")       ## 원본 파일이 ", "로 구성되었기 때문. 그냥 쉼표를 안쓰고 split() 으로 자르자

        if (not name) or (not weight) or (not height):
            continue

        bmi = int(weight) / ((int(height) / 100) ** 2)
        result = ""
        if bmi >= 25:
            result = "과체중"
        elif bmi >= 18.5:
            result = "정상 체중"
        else:
            result = "저체중"
        
        print('\n'.join([
            "이름 : {}",
            "몸무게 : {}",
            "키 : {}",
            "BMI : {}",
            "결과 : {}"
            ]).format(name, weight, height, bmi, result))
        print()
        
        
## 2025년 8월 17일 화이팅입니다!!

#예제
books = [{
    "제목": "혼자 공부하는 파이썬",
    "가격": 18000
}, {
    "제목": "혼자 공부하는 머신러닝",
    "가격": 26000
},{
    "제목": "혼자 공부하는 SQL",
    "가격": 15000
},{
    "제목": "혼자 공부하는 자바스크립트",
    "가격": 36000
}]

# 딕셔너리 내부의 key 메서드를 이용해 최소, 최대 가격의 책을 도출하는 프로그램
def price(book):
    return book["가격"]

print("# 가장 저렴한 책")
print(min(books, key = price))

print("# 가장 비싼 책")
print(max(books, key = price))

# 람다를 사용하면
print("# 가장 저렴한 책")
print(min(books, key = lambda x: x["가격"]))

print("# 가장 비싼 책")
print(max(books, key = lambda x: x["가격"]))


## 예제 2
numbers = [1,2,3,4,5,6]
print("::".join(map(str, numbers)))     # join은 문자열을 합쳐주는 기능이기 때문!


## 예제 3
numbers = [i for i in range(1, 11)]

# 홀수만 추출
print(list(filter(lambda x: x % 2 == 1, numbers)))
# 짝수만 추출 
print(list(filter(lambda x: x%2==0, numbers)))
# 제곱수가 50 미만 추출하기
print(list(filter(lambda x: x ** 2 < 50, numbers)))
