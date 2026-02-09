from langchain_upstage import UpstageEmbeddings
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic
from langsmith import Client
from dotenv import load_dotenv

load_dotenv()

embedding = UpstageEmbeddings(model="solar-embedding-1-large")

# database = Chroma.from_documents(
#     documents=splits,
#     embedding=embedding,
#     collection_name='chroma-tax',
#     persist_directory='./by-article-upstage'
# )

database = Chroma(
  collection_name= 'chroma-tax',
  persist_directory= './by-article-upstage',
  embedding_function= embedding     
)

retriever = database.as_retriever(
    search_type= 'mmr',
    search_kwargs={
        'k': 20,
        'fetch_k': 50,
        'lambda_mult': 0.6
    }
)

client = Client()

# 비용의 80%는 Haiku가, 정확도의 80%는 Sonnet/Opus가!!

smart_llm = ChatAnthropic(
    model='claude-opus-4-5-20251101',
    temperature= 0
)

llm = ChatAnthropic(
    model='claude-sonnet-4-5-20250929',
    temperature= 0
)

small_llm = ChatAnthropic(
    model='claude-haiku-4-5-20251001',
    temperature= 0
)

