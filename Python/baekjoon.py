#2675
n = int(input())
for _ in range(n):
    r, s = input().split()
    r = int(r)
    result = ''.join(char * r for char in s)
    print(result)

#31403
A = int(input())
B = int(input())
C = int(input())
print(A+B-C)
Aa = str(A)
Bb = str(B)
ab = Aa + Bb
print(int(ab) - C)

T = int(input())
for _ in range(T):
    H, W, N = map(int, input().split())
    room = N // H + 1
    floor = N % H if N % H != 0 else H
    print(f"{floor:02d}{room:02d}")


#문제10809
#알파벳 소문자로만 이루어진 단어 S가 주어진다. 각각의 알파벳에 대해서, 단어에 포함되어 있는 경우에는 처음 등장하는 위치를, 
#포함되어 있지 않은 경우에는 -1을 출력하는 프로그램을 작성하시오.

#첫째 줄에 단어 S가 주어진다. 단어의 길이는 100을 넘지 않으며, 알파벳 소문자로만 이루어져 있다.

#각각의 알파벳에 대해서, a가 처음 등장하는 위치, b가 처음 등장하는 위치, ... z가 처음 등장하는 위치를 공백으로 구분해서 출력한다.

#만약, 어떤 알파벳이 단어에 포함되어 있지 않다면 -1을 출력한다. 단어의 첫 번째 글자는 0번째 위치이고, 두 번째 글자는 1번째 위치이다.

S = input("넣을게")
alphabet = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']

for i in range(len(alphabet)):
    if alphabet[i] in S:
        alphabet[i] = str(S.find(alphabet[i]))
    else:
        alphabet[i] = str(-1)

print(" ".join(alphabet))

#2884
# 45분 일찍 알람 설정하기
# 원래 설정되어 있는 알람을 45분 앞서는 시간으로 바꾸는 것이다.
# 현재 상근이가 설정한 알람 시각이 주어졌을 때, 이를 언제로 고쳐야 하는지 구하는 프로그램을 작성하시오.

# 첫째 줄에 두 정수 H와 M이 주어진다. (0 ≤ H ≤ 23, 0 ≤ M ≤ 59) 그리고 이것은 현재 상근이가 설정한 알람 시간 H시 M분을 의미한다.

# 입력 시간은 24시간 표현을 사용한다. 24시간 표현에서 하루의 시작은 0:0(자정)이고, 끝은 23:59(다음날 자정 1분 전)이다. 시간을 나타낼 때, 불필요한 0은 사용하지 않는다.

(H, M) = map(int, input().split())

def alarm(H, M):
    M -= 45
    if M < 0:
        H -= 1
        M += 60
        if H < 0:
            H += 24
    print(H, M)
alarm(H, M)


#4153 직각삼각형

while True:
    a,b,c = map(int, input().split())
    triangle = sorted([a,b,c])
    if triangle == [0,0,0]:
        break
    if triangle[2] ** 2 == triangle[1] ** 2 + triangle[0] ** 2:
        print('right')
    else:
        print('wrong')


# 2920 - 음계

a = ''.join(input().split())
list_a = [
    '12345678',
    '23456781',
    '34567812',
    '45678123',
    '56781234',
    '67812345',
    '78123456',
    '81234567'
]
list_d = [
    '87654321',
    '76543218',
    '65432187',
    '54321876',
    '43218765',
    '32187654',
    '21876543',
    '18765432'
]
if a in list_a:
    print('ascending')
elif a in list_d:
    print('descending')
else:
    print('mixed')
