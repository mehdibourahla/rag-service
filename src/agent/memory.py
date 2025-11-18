"""Conversation memory management with compression and summarization."""

import logging
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from src.core.config import settings

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Chat message."""
    role: str
    content: str


class ConversationSummary(BaseModel):
    """Compressed conversation summary."""
    summary: str = Field(description="Concise summary of conversation history")
    key_points: List[str] = Field(description="Important facts or decisions")


class ConversationMemory:
    """Manages conversation context with compression and recency-based prioritization."""

    def __init__(
        self,
        max_recent_messages: int = 10,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o-mini",
    ):
        """
        Initialize conversation memory.

        Args:
            max_recent_messages: Number of recent messages to keep verbatim
            api_key: OpenAI API key
            model_name: Model for summarization
        """
        self.max_recent_messages = max_recent_messages
        self.api_key = api_key or settings.openai_api_key
        self.model_name = model_name
        self.summary: Optional[ConversationSummary] = None

    def _get_client(self) -> OpenAI:
        """Get OpenAI client."""
        return OpenAI(api_key=self.api_key)

    def compress_history(self, messages: List[Message]) -> ConversationSummary:
        """
        Compress conversation history using LLM.

        Args:
            messages: Messages to compress

        Returns:
            Compressed summary
        """
        client = self._get_client()

        system_message = """Compress conversation history into a concise summary.
Focus on key facts, user preferences, and important context.
Preserve specific details that may be referenced later.
Keep original phrasing where possible to avoid hallucination."""

        conversation_text = "\n".join([f"{m.role}: {m.content}" for m in messages])

        try:
            completion = client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Compress this conversation:\n\n{conversation_text}"},
                ],
                response_format=ConversationSummary,
                temperature=0.3,
            )

            summary = completion.choices[0].message.parsed
            logger.info(f"Compressed {len(messages)} messages")
            return summary

        except Exception as e:
            logger.error(f"Error compressing history: {e}")
            return ConversationSummary(
                summary="Previous conversation context",
                key_points=[]
            )

    def manage_context(self, messages: List[Message]) -> List[Message]:
        """
        Manage conversation context with recency-based prioritization.

        Args:
            messages: Full message history

        Returns:
            Optimized message list with summary + recent messages
        """
        if len(messages) <= self.max_recent_messages:
            return messages

        older_messages = messages[:-self.max_recent_messages]
        recent_messages = messages[-self.max_recent_messages:]

        if not self.summary or len(older_messages) > 0:
            self.summary = self.compress_history(older_messages)

        summary_message = Message(
            role="system",
            content=f"Previous conversation summary:\n{self.summary.summary}\n\nKey points: {', '.join(self.summary.key_points)}"
        )

        return [summary_message] + recent_messages

    def extract_query_context(self, messages: List[Message], query: str) -> str:
        """
        Extract query-relevant context from conversation.

        Args:
            messages: Conversation messages
            query: Current query

        Returns:
            Relevant context string
        """
        if not messages or len(messages) <= 2:
            return query

        recent = messages[-5:] if len(messages) > 5 else messages
        context_parts = [f"{m.role}: {m.content}" for m in recent if m.role != "system"]

        return f"Conversation context:\n{chr(10).join(context_parts)}\n\nCurrent query: {query}"
