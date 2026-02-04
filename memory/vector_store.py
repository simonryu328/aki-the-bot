"""
Vector store using Pinecone for semantic memory search.
Production-grade implementation with error handling, retry logic, and structured logging.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException
from openai import OpenAI, OpenAIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import settings
from core import get_logger, VectorStoreException, EmbeddingError, VectorStoreConnectionError

logger = get_logger(__name__)


class VectorStore:
    """
    Pinecone vector store for semantic memory search.

    Features:
    - Automatic retry with exponential backoff
    - Proper error handling and logging
    - User-isolated namespaces
    - Efficient embedding generation
    """

    def __init__(self):
        """Initialize Pinecone client and index with error handling."""
        try:
            if not settings.PINECONE_API_KEY:
                logger.warning("PINECONE_API_KEY not set, vector store disabled")
                raise VectorStoreConnectionError("Pinecone API key not configured")

            # Initialize Pinecone
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)

            # Initialize OpenAI for embeddings
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Index configuration
            self.index_name = "ai-companion-memories"
            self.dimension = 1536  # text-embedding-3-small dimension
            self.embedding_model = "text-embedding-3-small"

            # Create index if it doesn't exist
            self._ensure_index_exists()

            # Connect to index
            self.index = self.pc.Index(self.index_name)

            logger.info("Vector store initialized", index=self.index_name)

        except PineconeException as e:
            logger.error("Failed to initialize Pinecone", error=str(e))
            raise VectorStoreConnectionError(str(e))
        except OpenAIError as e:
            logger.error("Failed to initialize OpenAI client", error=str(e))
            raise VectorStoreConnectionError(str(e))

    def _ensure_index_exists(self) -> None:
        """Create Pinecone index if it doesn't exist."""
        try:
            existing_indexes = [index.name for index in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                logger.info("Creating Pinecone index", index=self.index_name)
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                logger.info("Pinecone index created successfully")

        except PineconeException as e:
            logger.error("Failed to ensure index exists", error=str(e))
            raise VectorStoreConnectionError(f"Failed to create/check index: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((OpenAIError, PineconeException)),
    )
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI with retry logic.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails after retries
        """
        try:
            # Truncate text if too long (OpenAI has token limits)
            max_chars = 8000  # ~2000 tokens
            if len(text) > max_chars:
                text = text[:max_chars]
                logger.debug("Truncated text for embedding", original_length=len(text))

            response = self.openai_client.embeddings.create(
                model=self.embedding_model, input=text
            )
            embedding = response.data[0].embedding

            logger.debug("Generated embedding", text_length=len(text), dimension=len(embedding))
            return embedding

        except OpenAIError as e:
            logger.error("Failed to generate embedding", error=str(e), text_length=len(text))
            raise EmbeddingError(text_length=len(text), details=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(PineconeException),
    )
    def add_memory(
        self,
        user_id: int,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a memory to the vector store with retry logic.

        Args:
            user_id: User ID
            text: Text to store and embed
            metadata: Additional metadata (timestamp, message_type, importance)

        Returns:
            ID of the stored memory

        Raises:
            VectorStoreException: If storage fails after retries
        """
        try:
            # Generate unique ID
            memory_id = f"user_{user_id}_{datetime.utcnow().timestamp()}"

            # Prepare metadata
            meta = metadata or {}
            meta["user_id"] = user_id
            meta["timestamp"] = datetime.utcnow().isoformat()
            meta["text"] = text[:1000]  # Store truncated text in metadata for retrieval

            # Get embedding
            embedding = self._get_embedding(text)

            # Upsert to Pinecone
            self.index.upsert(
                vectors=[(memory_id, embedding, meta)], namespace=f"user_{user_id}"
            )

            logger.debug("Added memory", user_id=user_id, memory_id=memory_id, text_length=len(text))
            return memory_id

        except PineconeException as e:
            logger.error("Failed to add memory", user_id=user_id, error=str(e))
            raise VectorStoreException(f"Failed to add memory: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((OpenAIError, PineconeException)),
    )
    def search_memories(
        self,
        user_id: int,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories using semantic similarity.

        Args:
            user_id: User ID to search memories for
            query: Search query text
            k: Number of results to return
            filter_metadata: Optional metadata filters

        Returns:
            List of dicts with keys: id, text, metadata, score

        Raises:
            VectorStoreException: If search fails after retries
        """
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)

            # Build filter
            filter_dict = filter_metadata or {}

            # Query Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=k,
                namespace=f"user_{user_id}",
                filter=filter_dict if filter_dict else None,
                include_metadata=True,
            )

            # Format results
            memories = []
            for match in results.matches:
                memory = {
                    "id": match.id,
                    "text": match.metadata.get("text", ""),
                    "metadata": match.metadata,
                    "score": match.score,
                }
                memories.append(memory)

            logger.debug("Found memories", user_id=user_id, count=len(memories), query_length=len(query))
            return memories

        except (OpenAIError, PineconeException) as e:
            logger.error("Failed to search memories", user_id=user_id, error=str(e))
            raise VectorStoreException(f"Failed to search memories: {e}")

    def get_user_memory_count(self, user_id: int) -> int:
        """
        Get count of memories for a user.

        Args:
            user_id: User ID

        Returns:
            Number of memories stored
        """
        try:
            stats = self.index.describe_index_stats()
            namespace_stats = stats.namespaces.get(f"user_{user_id}", None)
            count = namespace_stats.vector_count if namespace_stats else 0
            logger.debug("Retrieved memory count", user_id=user_id, count=count)
            return count

        except PineconeException as e:
            logger.error("Failed to get memory count", user_id=user_id, error=str(e))
            return 0  # Return 0 on error rather than raising

    def delete_user_memories(self, user_id: int) -> None:
        """
        Delete all memories for a user.

        Args:
            user_id: User ID

        Raises:
            VectorStoreException: If deletion fails
        """
        try:
            # Delete entire namespace
            self.index.delete(delete_all=True, namespace=f"user_{user_id}")
            logger.info("Deleted all memories", user_id=user_id)

        except PineconeException as e:
            logger.error("Failed to delete memories", user_id=user_id, error=str(e))
            raise VectorStoreException(f"Failed to delete memories: {e}")

    def add_conversation_chunk(
        self,
        user_id: int,
        messages: List[Dict[str, str]],
        importance: int = 5,
    ) -> str:
        """
        Add a conversation chunk to the vector store.

        Args:
            user_id: User ID
            messages: List of message dicts with 'role' and 'content'
            importance: Importance score (0-10)

        Returns:
            ID of the stored conversation chunk
        """
        # Format conversation chunk as text
        conversation_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in messages]
        )

        # Add to vector store
        return self.add_memory(
            user_id=user_id,
            text=conversation_text,
            metadata={
                "message_type": "conversation",
                "importance": importance,
                "message_count": len(messages),
            },
        )


# Singleton instance - will raise exception if initialization fails
try:
    vector_store = VectorStore()
except VectorStoreConnectionError as e:
    logger.warning("Vector store initialization failed, running without semantic search", error=str(e))
    vector_store = None  # type: ignore
