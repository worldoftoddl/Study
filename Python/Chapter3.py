#2025년 8월 5일 화이팅입니다!!!

#and
print(True and True)
print(True and False)
print(False and True)
print(False and False)

# or
print(True or True)
print(True or False)
print(False or True)
print(False or False)

# not
print(not True)
print(not False)    


#if문
number = float(input("숫자를 입력하세요: "))
if number > 0:
    print("양수입니다.")
elif number < 0:
    print("음수입니다.")
else:
    print("0입니다.")

#개발중~ or 동작 없음 : pass
if number > 0:
    pass #개발중
else:
    pass #개발중

#혹은 NotImplementedError
if number > 0:
    raise NotImplementedError("이 기능은 아직 구현되지 않았습니다.") #pass와 같이 코드 진행은 되지만, 구현되지 않은 부분에서 에러가 발생해 알림

#날짜, 시간
import datetime
now = datetime.datetime.now()
print("현재 날짜와 시간:", now) #현재 날짜와 시간: 2025-08-05 12:40:58.995805
print(now.year)  # 현재 연도
print(now.month)  # 현재 월
print(now.day)  # 현재 일
print(now.hour)  # 현재 시
print(now.minute)  # 현재 분
print(now.second)  # 현재 초

print("지금은 {}년 {}월 {}일 {}시 {}분 {}초 입니다.".format(
    now.year, now.month, now.day, now.hour, now.minute, now.second
))
#지금은 2025년 8월 5일 12시 40분 58초 입니다.

print(f"지금은 {now.year}년 {now.month}월 {now.day}일 {now.hour}시 {now.minute}분 {now.second}초 입니다.")


#도전문제 1
#"안녕", "안녕하세요"에는 "안녕하세요"라고, "지금 몇 시야?", "지금 몇 시에요?"에는 지금 시간을, 그 외의 경우엔 입력을 그대로 출력하는 프로그램을 작성하세요.
txt = input("입력하세요: ")
if "안녕" in txt:
    print("안녕하세요")
elif "몇 시" in txt:
    import datetime
    now = datetime.datetime.now()
    print(f"현재 시각은 {now.hour}시 입니다.")
else:
    print(txt)
## 항상 or 구문 사용시에 주의할 것. A == b or c or c or ~ 과 같은 구조에서 첫 번째 이후의 or뒤의 값들은 모두 True로 평가되어 A == b만 확인하게 됨. 
# 따라서 A == b or A == c or A == d or ~와 같이 작성해야 함.
 
#도전문제 2
#사용자에게서 숫자를 입력받아 해당 숫자가 2, 3, 4, 5의 배수인지 판단하는 프로그램을 작성하시오.
num = int(input("숫자를 입력하세요: "))
if num % 2 == 0:
    print(f"{num}은(는) 2의 배수입니다.")
else:
    print(f"{num}은(는) 2의 배수가 아닙니다.")
if num % 3 == 0:
    print(f"{num}은(는) 3의 배수입니다.")
else:
    print(f"{num}은(는) 3의 배수가 아닙니다.")
if num % 4 == 0:
    print(f"{num}은(는) 4의 배수입니다.")
else:
    print(f"{num}은(는) 4의 배수가 아닙니다.")
if num % 5 == 0:
    print(f"{num}은(는) 5의 배수입니다.")
else:
    print(f"{num}은(는) 5의 배수가 아닙니다.")  
