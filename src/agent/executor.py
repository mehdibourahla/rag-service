"""Agent executor with ReAct pattern and self-correction."""

import logging
from typing import List, Tuple

from src.agent.planner import Agent, Plan
from src.agent.tools import AgentTools
from src.models.schemas import RetrievedChunk
from src.retrieval.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of agent execution."""

    def __init__(
        self,
        success: bool,
        response: str,
        chunks: List[RetrievedChunk],
        steps: List[dict],
        final_plan: Plan,
    ):
        self.success = success
        self.response = response
        self.chunks = chunks
        self.steps = steps  # Trace of all actions taken
        self.final_plan = final_plan


class AgentExecutor:
    """
    Executes agent plans with retry logic.

    Implements simplified retrieval with query expansion on failure:
    1. Plan the action (classify intent)
    2. Retrieve documents
    3. If no results, expand query and retry
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        max_retries: int = 1,  # Single retry with query expansion
    ):
        """
        Initialize executor.

        Args:
            retriever: Hybrid retriever instance
            max_retries: Maximum retry attempts with query expansion (default: 1)
        """
        self.retriever = retriever
        self.max_retries = max_retries
        self.agent = Agent()
        self.tools = AgentTools()

    def execute(
        self, query: str, top_k: int = 5
    ) -> Tuple[List[RetrievedChunk], List[dict], Plan]:
        """
        Execute query with optional retry on failure.

        Args:
            query: User query
            top_k: Number of chunks to retrieve

        Returns:
            Tuple of (chunks, execution_steps, final_plan)
        """
        steps = []

        # Step 1: Initial Planning
        logger.info(f"=== Starting execution for: {query[:50]}... ===")
        plan = self.agent.plan(query=query)

        steps.append(
            {
                "step": "plan",
                "action": plan.action.value,
                "needs_retrieval": plan.needs_retrieval,
                "reasoning": plan.reasoning,
            }
        )

        # If no retrieval needed, return early
        if not plan.needs_retrieval:
            logger.info("No retrieval needed, returning early")
            return [], steps, plan

        # Step 2: Retrieve with optional retry
        for attempt in range(1, self.max_retries + 2):  # +2 for initial attempt + retries
            current_query = query

            logger.info(f"--- Attempt {attempt}/{self.max_retries + 1} ---")

            # Retrieve chunks
            chunks = self.retriever.retrieve(query=current_query, top_k=top_k)

            steps.append(
                {
                    "step": "retrieve",
                    "attempt": attempt,
                    "query": current_query,
                    "num_chunks": len(chunks),
                }
            )

            # If we got results, return them
            if chunks:
                logger.info(f"Retrieved {len(chunks)} chunks, proceeding")
                return chunks, steps, plan

            # No results - try query expansion on retries
            if attempt <= self.max_retries:
                logger.warning(f"No chunks retrieved on attempt {attempt}, expanding query")
                expansion = self.tools.expand_query(query)

                # Use different expansion on each retry
                idx = min(attempt - 1, len(expansion.expanded_queries) - 1)
                current_query = expansion.expanded_queries[idx]

                steps.append(
                    {
                        "step": "expand",
                        "new_query": current_query,
                        "all_expansions": expansion.expanded_queries,
                        "reasoning": expansion.reasoning,
                    }
                )

                logger.info(f"Trying expanded query: {current_query}")

                # Re-retrieve with expanded query
                chunks = self.retriever.retrieve(query=current_query, top_k=top_k)

                steps.append(
                    {
                        "step": "retrieve",
                        "attempt": attempt,
                        "query": current_query,
                        "num_chunks": len(chunks),
                    }
                )

                if chunks:
                    logger.info(f"Expanded query retrieved {len(chunks)} chunks")
                    return chunks, steps, plan

        # Give up after retries
        logger.warning("No chunks found after all retries")
        return [], steps, plan
