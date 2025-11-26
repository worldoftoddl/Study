'''
7장은 모듈을 배우는 장이다.
7-1에서는 파이썬 내장 모듈을 배우고
7-2에서는 외부 모듈을 배운다.
7-3에서는 스스로 모듈을 만드는 방법을 배울 수 있다.

지난 6장까지는 기본편으로, 파이썬 기본 문법을 배웠고,
7장부터는 고급편에 해당하는데, 모듈과 클래스를 배우게 된다.
지난 3주간 진도가 느렸는데, 내가 봐왔던 코드들과 괴리감이 들어서 흥미가 조금 떨어져서 그랬나 싶다.
기대된다!!!!
'''

## 7-1. 파이썬 내장 모듈
# 참고로 사용하는 모듈명과 동일한 이름으로 파일을 저장하면 TypeError가 발생한다.


# 1. math 모듈
import math
math.sin(1)     # 사인
math.cos(1)     # 코사인
math.tan(1)     # 탄젠트
math.floor(2.5) # 내림
math.ceil(2.5)  # 올림

## math. 을 찍는게 귀찮다면~

## 방법 1. from - import
from math import sin, cos, tan, floor, ceil
sin(1)
cos(1)
tan(1)
floor(1)
ceil(1)
# 이렇게 앞에 모듈명을 적지 않아도 된다!

# 혹은 이렇게
from math import *
# 이렇게 적으면 모든 변수와 함수를 가져와 쓰게 된다.
# 그러나 식별자가 충돌을 일으킬 수 있으므로 필요한 것만 검소하게 가져다 쓰자!!


## 방법 2. import - as
import math as m

m.sin(1)
m.cos(1)
m.tan(1)
m.floor(1)
m.ceil(1)
# 이렇게 자신이 원하는 글자로 모듈을 불러올 수 있다.






# 2. random 모듈
import random as rd

# random(): 0.0 <= x < 1 의 float를 return
print(rd.random())        

# uniform(min, max): 지정한 범위 사이의 float를 return
print(rd.uniform(10, 20))

# randrange(min, max): 지정한 범위 내의 int를 return
print(rd.randrange(10))
print(rd.randrange(10, 20))

# choice(list): 리스트 내 랜덤한 항목 return
dinner_choice = ['짜장', '짬뽕', '콩국수', '굶기']
print(rd.choice(dinner_choice))

# shuffle(list): 리스트 내 index를 랜덤하게 섞음
cosmos = [i for i in range(100)]
print(cosmos)

rd.shuffle(cosmos)
print(cosmos)       # 원본 리스트 자체를 바꿔버리는 함수이다.

# sample(list, k=int): 리스트 요소 중 랜덤하게 K개를 선택
print(rd.sample(dinner_choice, k=2))


# 저번에도 말했지만 사용할 함수만 import 하자!
from random import random, uniform, randrange






## 3. sys 모듈
'''
sys 모듈은 낯설어서 내가 이해한 바를 적어두도록 하겠다.
이 모듈은 시스템과 관련된 정보를 가지고 있는 모듈이며, 명령 매개변수를 받을 때 사용한다.
'''

import sys
print(sys.argv)     # [''] -> 뭔가 귀엽다

#시스템 정보 출력
print(sys.getwindowsversion)
print(sys.copyright)
print(sys.version)

# 프로그램 강제 종료(...)
sys.exit()      

# 파이썬 모듈 경로
print(sys.path)

# 메모리 관리 (byte 단위)
print(sys.getsizeof(dinner_choice))

# 기본 재귀 한도 확인
print(sys.getrecursionlimit())  # 보통 1000

# 재귀 한도 변경 (깊은 재귀가 필요시)
sys.setrecursionlimit(2000)






## 4. datetime 모듈
import datetime

now = datetime.datetime.now()

print(f"현재 {now.year}년 {now.month}월 {now.day}일 {now.hour}시 {now.minute}분 {now.second}초 입니다!!!")

## ㅋㅋㅋ혹은
print(now.strftime('현재 %Y년 %m월 %d일 %H시 %M분 %S초 입니다!!'))

## 호옥은~
print(now.strftime('현재 %Y{} %m{} %d{} %H{} %M{} %S{}입니다!!'.format(*'년월일시분초')))

# timedelta(): 특정 시점에서 전, 후의 시간을 더하는 함수 (그러나 연 단위 이동 불가)
after = now + datetime.timedelta(weeks = 1, days = 1)
print(now)
print(after)    ## 8일 뒤로 이동했다.

# replace(): 특정 시점으로 바꾸는 기능이다. 연단위 이동이 가능하다
after2 = now.replace(year=(now.year + 1), month=(now.month + 2))
print(now)
print(after2)



## 5. time모듈
'''
time 모듈도 날짜와 관련된 처리를 할 수 있지만 그런 처리는 datetime모듈로 하고,
이 모듈은 코드 사이에 지연시간을 설정해서 오류를 방지하는 역할로 많이 쓰인다.
'''

import time
print('그대로 멈춰라!')
time.sleep(5)
print('땡!!!!')
# 크롤링이나 스크래핑시에 데이터 로드 지연시간을 기다리기 위해 삽입하는 코드이다.



## 2025년 8월 21일 화이팅입니다!!

# 6. urllib 모듈
'''
urllib 모듈은 URL을 다루는 모듈로, 웹에서 데이터를 가져오거나 전송할 때 사용된다.
'''

from urllib import request

target = request.urlopen('https://www.naver.com')   # 네이버 url을 open
output = target.read()                              # urlopen() 함수로 URL을 열고, read() 함수로 HTML 코드를 읽어온다.
print(output)                                       # 네이버 홈페이지의 HTML 코드가 출력된다.

'''
urllib 모듈은 웹 크롤링이나 스크래핑에 많이 사용된다.
그러나 이 모듈은 간단한 웹 크롤링에는 적합하지만,
복잡한 웹 페이지나 동적 페이지를 다루기에는 한계가 있다.
'''



## 7. os 모듈
'''
운영체제와 관련된 모듈이다.
폴더 생성 또는 폴더 내의 파일 목록을 보는 등의 작업을 수행할 수 있다.
'''

import os

# os관련 기본 정보 출력
print("현재 운영체계:", os.name)
print("현재 폴더:", os.getcwd())
print("현재 폴더 내부 요소:", os.listdir())

# 폴더 생성 및 제거
os.mkdir("직박구리")
os.rmdir("직박구리")    # 빈 폴더일 경우에만 제거 가능

# 파일 생성 및 이름 변경
with open("Chapter100.py", "w") as file:
    file.write("Hello World!")
os.rename("Chapter100.py", "Chapter101.py")

# 파일 삭제 - remove와 unlink는 이름만 다르고 같은 함수임
os.remove("Chapter101.py")      
os.unlink("Chapter101.py")

# 시스템 명령어 실행
os.system('dir')





### 외부 모듈
'''
크롤링이나 스크래핑 할 당시 보았던 모듈들을 받아 사용하는 방법이다.
NumPy나 Django, Flask, ㅠeautifulSoup 등등... 
각각의 모듈만으로 여지껏의 공부량을 상회하는 양이므로 다음에 빅분기나 AICE 과정에서 사용해보도록 하자!
'''
