"""Tools for agent execution."""

import logging
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from src.core.config import settings

logger = logging.getLogger(__name__)


class QueryExpansion(BaseModel):
    """Expanded query with variations."""

    original_query: str
    expanded_queries: List[str] = Field(
        description="List of reformulated/expanded queries"
    )
    reasoning: str = Field(description="Why these expansions were chosen")


class QueryDecomposition(BaseModel):
    """Decomposed complex query into sub-queries."""

    original_query: str
    sub_queries: List[str] = Field(description="List of simpler sub-queries")
    synthesis_strategy: str = Field(
        description="How to combine answers from sub-queries"
    )


class AgentTools:
    """Tools for agent execution and reflection."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or settings.openai_api_key
        self.model_name = model_name

    def _get_client(self) -> OpenAI:
        """Get OpenAI client."""
        return OpenAI(api_key=self.api_key)

    def expand_query(self, query: str) -> QueryExpansion:
        """
        Expand query with variations, synonyms, and reformulations.

        Args:
            query: Original query

        Returns:
            QueryExpansion with variations
        """
        client = self._get_client()

        system_message = """You are an expert at query expansion for information retrieval.

Generate 3-5 alternative phrasings of the query that:
1. Use synonyms and related terms
2. Add specificity or context
3. Rephrase from different angles
4. Cover potential variations in how the information might appear in documents

Keep the core intent but vary the expression."""

        user_prompt = f'Expand this query: "{query}"'

        logger.info(f"Expanding query: {query[:50]}...")

        try:
            completion = client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=QueryExpansion,
                temperature=0.5,
            )

            expansion = completion.choices[0].message.parsed
            logger.info(
                f"Generated {len(expansion.expanded_queries)} query variations"
            )
            return expansion

        except Exception as e:
            logger.error(f"Error expanding query: {e}")
            return QueryExpansion(
                original_query=query,
                expanded_queries=[query],
                reasoning=f"Fallback: {str(e)}",
            )

    def decompose_query(self, query: str) -> QueryDecomposition:
        """
        Decompose complex query into simpler sub-queries.

        Args:
            query: Complex query

        Returns:
            QueryDecomposition with sub-queries
        """
        client = self._get_client()

        system_message = """You are an expert at breaking down complex questions.

Analyze the query and:
1. Identify if it contains multiple questions or aspects
2. Break it into 2-4 simpler, focused sub-queries
3. Explain how to synthesize answers from sub-queries

If the query is already simple, just return it as a single sub-query."""

        user_prompt = f'Decompose this query: "{query}"'

        logger.info(f"Decomposing query: {query[:50]}...")

        try:
            completion = client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=QueryDecomposition,
                temperature=0.3,
            )

            decomposition = completion.choices[0].message.parsed
            logger.info(
                f"Decomposed into {len(decomposition.sub_queries)} sub-queries"
            )
            return decomposition

        except Exception as e:
            logger.error(f"Error decomposing query: {e}")
            return QueryDecomposition(
                original_query=query,
                sub_queries=[query],
                synthesis_strategy=f"Fallback: {str(e)}",
            )

