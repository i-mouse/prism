import asyncio

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from fastembed import TextEmbedding
from dotenv import load_dotenv
import os
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter
load_dotenv()

class RAGService:
    def __init__(self):

        url = os.getenv("QDRANT_HTTPURI")
        api_key = os.getenv("QDRANT_APIKEY")
        self.client = AsyncQdrantClient(url=url,api_key=api_key)
        self.collection_name = "prism_docs"
        print(f"Qdrant initiated")

        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        print(f"Embedding model initiated")

    @classmethod
    async def create(cls) -> "RAGService":
        """Async factory - construction plus the async collection-ensure step
        that __init__ can't await. All call sites (main.py, agent_service.py)
        must go through this instead of RAGService() directly, so a future
        third construction site can't silently skip create_collection()."""
        instance = cls()
        await instance.create_collection()
        return instance

    async def create_collection(self):
        if not await self.client.collection_exists(self.collection_name):
            print(f"Creating collection : ")

            vector_params = models.VectorParams(size=384,distance=models.Distance.COSINE)

            await self.client.create_collection(collection_name=self.collection_name,vectors_config=vector_params)
            print(f"collection created")
        else:
            print(f"Collection already exists")

    async def add_document_to_qdrant(self, filename: str, doctext: str, file_id: str) -> int:

        # Delete any existing vectors for this file before inserting new ones.
        # Combined with deterministic uuid5 chunk IDs, this makes the operation
        # fully idempotent: re-processing the same file_id is safe.
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="file_id", match=MatchValue(value=file_id))]
            )
        )
        print(f"[{filename}] Deleted existing Qdrant points for file_id={file_id}")

        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", r"(?<=\. )", " ", ""],
            chunk_size = 1200,
            chunk_overlap=200,
            length_function=len
        )

        chunks = text_splitter.split_text(doctext)
        print(f"[{filename}] Split into {len(chunks)} semantic chunks.")

        embeddings = list(self.embedding_model.embed(chunks))
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            points.append(models.PointStruct(
               id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_id}:{i}")),
               vector=vector,
               payload={
                   "filename": filename,
                   "text": chunk,
                   "chunk_index": i,
                   "file_id": file_id,   # enables filtered delete on retry
               }
            ))

        await self.client.upsert(collection_name=self.collection_name,points=points)
        print(f"Saved vector into qdrant")
        return len(chunks)

    async def search_db(self, user_query, limit:int = 3, file_id: str | None = None):
        query_vector = list(self.embedding_model.embed(user_query))[0]
        query_filter = None
        if file_id is not None:
            query_filter = Filter(must=[FieldCondition(key="file_id", match=MatchValue(value=file_id))])
        hits = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
        )
        return hits.points



if __name__ == "__main__":
    async def _main():
        rag = await RAGService.create()
        await rag.search_db(user_query="whats the problem with this contract?",limit=3)

    asyncio.run(_main())
