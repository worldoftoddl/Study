//이것은 한줄 주석입니다

/*
이
것
은
여
러
줄
주
석
입
니
다
*/

//변수 선언 let
let esspressoPrice = 3000;
let latteP = 4300
let mochaP = 3000

console. log(esspressoPrice*3 + latteP + mochaP)

let esspresso=10;
let milk=170;
let chocolateSyrup=50;
let whippedCream=60;

console.log(esspresso);
console.log(milk);
console.log(chocolateSyrup);
console.log(whippedCream);

// 함수 선언
// function 함수이름(파라미터) {명령; 명령;};  --> 이 형식으로 작성

function greetings() {
  console. log('Hi');
  console. log('안녕')
}

greetings();


function printCorus() {
  console. log('東海 물과 白頭山이')
  console. log('말으고 달토록')
  console. log('하나님이 保護하사')
  console. log('우리 大韓 萬歲')
} 

printCorus();


function teraToGiga(x) {
  console. log(x + 'TB는')
  console. log(x * 1024 + 'GB 입니다')
};

function teraToMega(y) {
  console. log(y + 'TB는')
  console. log(y * 1024*1024 + 'MB 입니다')
};  

teraToGiga(4);
teraToMega(4);


function printSum(a,b) {
  console.log(a+b)
};

printSum(10,20);


function bmiCalculator(name, w, h) {
  console.log(name + '님의 체질량지수는 ' + w * 10000 / (h * h))
};

bmiCalculator('홀쭉이', w=43.52, h=160);
bmiCalculator('코린이', w=61.25, h=175);
bmiCalculator('통통이', w=77.76, h=180);