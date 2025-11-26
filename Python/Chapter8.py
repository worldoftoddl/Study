## 2025년 8월 22일 화이팅입니다!!
'''
오늘 배울 내용은 클래스이다.
파이썬 처음 배울 때 아직은 배울 필요가 없다고 하셔서 등한시했던 부분이다.
이게 나중 가서는 내 발등을 찍었지만 말이다.

다시 배우게 되어서 기쁘고 오늘 공부를 마지막으로 AICE공부로 넘어가게 된다.
기쁘다!!!
'''

## 클래스 만들기

# 1. 생성자와 매개변수
class FishShapedBun:            # 클래스 이름이며 생성자(constructor)라고 부름
    def __init__(self, ):       # 첫번째 매개변수는 반드시 self여야 한다. (자기 자신을 가르키는 딕셔너리)
        pass                    # self 내의 속성과 기능에 접근시에는 self.<식별자> 형태로 접근한다.


# 2 
class Student:             
    def __init__(self, name, korean, english, math):
        self.name = name
        self.korean = korean
        self.english = english          # 인스턴스 변수 초기화.
        self.math = math                # self.<식별자>로 클래스 내 변수를 메서드와 매칭시켜주는 작업이다.
                                        # 참고로 여기서 self.__name = name 이렇게 쓰면 클래스 바깥에서 사용 불가능한 프라이빗 변수가 된다.

    def get_sum(self):
        return (self.korean + self.english + self.math)
    
    def get_average(self):
        return self.get_sum() / 3
    
    def to_string(self):
        return f"{self.name}\t{self.get_sum()}\t{self.get_average()}"

students = [
    Student("도지훈", 97, 88, 68),
    Student("신원석", 100, 100, 100),
    Student("윤석용", 100, 92, 55),
    Student("구건모", 40, 30, 60)
]
'''
함수를 이용하지 않고 class를 통해
학생 리스트 dictionary를 선언하는 코드
'''

# Student 인스턴스 속성에 접근하는 방법
students[0].name

# 학생을 한명씩 반복
print(f"이름\t총점\t평균")
for i in students:
    print(i.to_string())

# 인스턴스(붕어빵)이 특정 class(붕어빵 틀)에서 나온 건지(상속 관계) 확인하는 함수
isinstance(students[0], Student)

type(Student) # class type이래~

## isinstance() 활용 예시
class Boy:
    def giggle(self):
        print('hhhhh')

class Girl:
    def jiggle(self):
        print('kkkkk')

classroom = [Boy(), Girl(), Boy(), Boy(), Girl()]

for i in classroom:
    if isinstance(i, Boy):
        i.giggle()
    elif isinstance(i, Girl):
        i.jiggle()
    else:
        print('WTF')
# 이런 식으로 class별 분류를 통한 조건문을 걸 수 있음


'''
__init__에서 
'''

## 상속
'''
여러 개의 클래스를 선언하고 관리할 때 어떠한 공통의 포맷이 있을 것이다.
그런 경우 그 공통된 요소들을 각각의 class에 모두 적을 것이 아니라 
부모 class를 선언하여 자녀 class에 상속해줘 코드 작성을 편리하게 할 수 있다.
또한 코드 수정시에도 부모 class만 건들면 되는 것이니
여간 편한 기능이 아니다!!!

이어지는 코드는 클래스 상속의 전형적인 예시이니
그대로 외워도 되는 코드이다.
'''


# 부모 클래스 선언
class Parent:
    def __init__(self):
        self.value = 'Test'
        print("Parent 클래스의 __init__메서드")
    def test(self):
        print("Parent 클래스의 test메서드")

# 상속받을 자녀 클래스 선언
class Child(Parent):                                ## 여기서 Child(Parent)로 상속을 선언
    def __init__(self):
        super().__init__()                          ## super()로 __init__ 메서드를 호출함.
        print("Child 클래스의 __init__메서드")


## 클래스를 함수라고 생각한 나으 어리석은 코드 -> 객체를 두번 생성함
Child().test()          # 첫번째 Child 객체
print(Child().value)    # 두번째 Child 객체 속 value 호출

## 클래스는 붕어빵 기계라는 점을 인지한 코드
child = Child()         # 첫번째 Child 객체를 할당함
child.test()
print(child.value)      # 그 객체를 계속 사용함


## 예외 클래스 - 부모의 성질을 바꿔서 상속하고자 할 때
class CustomException(Exception):       # Exception 클래스를 상속함
    def __init__(self, *args):
        super().__init__(*args)

raise CustomException("내가 만든 에러 발생!!")

## 혹은 재정의 가능 (Exception 클래스에 __str__가 있음 그래서 위 코드가 기능함)
class CustomException2(Exception):       # Exception 클래스를 상속함
    def __init__(self, *args):
        super().__init__(*args)
    
    def __str__(self):
        return "내가 만든 에러 발생!!"

raise CustomException2

## 혹은 새로운 함수를 정의하여 클래스를 상속할 수도 있음
class CustomException3(Exception):       # Exception 클래스를 상속함
    def __init__(self, *args, message, value):
        super().__init__(*args)
        self.message = message
        self.value = value
    def __str__(self):
        return self.message
    
    def print(self):
        print("-----오류 정보-----")
        print("메시지:", self.message)
        print("값:", self.value)

try:
    raise CustomException3(message = "별 의미 없음", value = 52221)     ## *args 뒤의 매개변수는 반드시 키워드로 전달해야함!
except CustomException3 as e:                  ## 키워드로 전달하기 싫으면 __init__의 매개변수를 self, message, value 이렇게
    e.print()

## 상속 다음의 개념: 구성 (Composition)
