# 타입 힌팅용 - 
from typing import Union
# FastAPI 프레임워크 임포트
from fastapi import FastAPI

app = FastAPI()

# FastAPI 앱 인스턴스
@app.get("/")       # 데코레이터로 경로 정의 - http://localhost:8000/
def read_root():    #
    return {"Hello": "World"}


@app.get("/items/{item_id}")    # 경로 http://localhost:8000/items/{item_id}
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}