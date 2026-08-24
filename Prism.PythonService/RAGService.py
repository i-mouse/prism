from qdrant_client import QdrantClient ,models
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
        self.client = QdrantClient(url=url,api_key=api_key)
        self.collection_name = "prism_docs"
        print(f"Qdrant initiated")

        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        print(f"Embedding model initiated")

        self.create_collection()

    def create_collection(self):
        if not self.client.collection_exists(self.collection_name):
            print(f"Creating collection : ")

            vector_params = models.VectorParams(size=384,distance=models.Distance.COSINE)

            self.client.create_collection(collection_name=self.collection_name,vectors_config=vector_params)
            print(f"collection created")
        else:
            print(f"Collection already exists")

    def add_document_to_qdrant(self, filename: str, doctext: str, file_id: str) -> int:

        # Delete any existing vectors for this file before inserting new ones.
        # Combined with deterministic uuid5 chunk IDs, this makes the operation
        # fully idempotent: re-processing the same file_id is safe.
        self.client.delete(
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

        self.client.upsert(collection_name=self.collection_name,points=points)
        print(f"Saved vector into qdrant")
        return len(chunks)

    def search_db(self, user_query, limit:int = 3):
        query_vector = list(self.embedding_model.embed(user_query))[0]
        hits = self.client.query_points(collection_name = self.collection_name,query=query_vector,limit = limit)
        return hits.points    



if __name__ == "__main__":
    rag = RAGService()
    rag.search_db(user_query="whats the problem with this contract?",limit=3)