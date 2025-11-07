"""Agent executor with ReAct pattern and self-correction."""

import logging
from typing import List, Optional, Tuple

from src.agent.planner import ActionType, Agent, Plan
from src.agent.tools import AgentTools, QualityEvaluation
from src.models.schemas import RetrievedChunk
from src.retrieval import HybridRetriever

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
    Executes agent plans with reflection and self-correction.

    Implements ReAct pattern:
    1. Reason: Plan the action
    2. Act: Execute retrieval/generation
    3. Observe: Evaluate quality
    4. Reflect: Decide whether to retry with adjustments
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        max_iterations: int = 2,  # Reduced from 3
        quality_threshold: float = 0.5,  # Lowered threshold
        enable_reflection: bool = True,  # Can be disabled for speed
    ):
        """
        Initialize executor.

        Args:
            retriever: Hybrid retriever instance
            max_iterations: Maximum retry attempts (default: 2)
            quality_threshold: Minimum quality score to proceed (default: 0.5)
            enable_reflection: Whether to use quality evaluation (default: True)
        """
        self.retriever = retriever
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.enable_reflection = enable_reflection
        self.agent = Agent()
        self.tools = AgentTools()

    def execute(
        self, query: str, top_k: int = 5
    ) -> Tuple[List[RetrievedChunk], List[dict], Plan]:
        """
        Execute query with reflection and self-correction.

        Args:
            query: User query
            top_k: Number of chunks to retrieve

        Returns:
            Tuple of (chunks, execution_steps, final_plan)
        """
        steps = []
        current_query = query

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

        # Step 2: Skip decomposition for now (can add back if needed)
        # Decomposition adds an extra LLM call - only use for very complex queries
        # if self._is_complex_query(query):
        #     decomposition = self.tools.decompose_query(query)
        #     current_query = decomposition.sub_queries[0]

        # Step 3: Iterative Retrieval with Self-Correction
        for attempt in range(1, self.max_iterations + 1):
            logger.info(f"--- Attempt {attempt}/{self.max_iterations} ---")

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

            if not chunks:
                logger.warning(f"No chunks retrieved on attempt {attempt}")

                # Try query expansion if first attempt
                if attempt == 1:
                    expansion = self.tools.expand_query(query)
                    current_query = expansion.expanded_queries[0]

                    steps.append(
                        {
                            "step": "expand",
                            "expanded_queries": expansion.expanded_queries,
                            "reasoning": expansion.reasoning,
                        }
                    )

                    logger.info(f"Trying expanded query: {current_query}")
                    continue
                else:
                    # Give up after retries
                    logger.warning("No chunks found after retries")
                    return [], steps, plan

            # Evaluate quality only if reflection is enabled
            if self.enable_reflection:
                chunk_texts = [chunk.text for chunk in chunks]
                evaluation = self.tools.evaluate_quality(
                    query=query, retrieved_chunks=chunk_texts, attempt=attempt
                )

                steps.append(
                    {
                        "step": "evaluate",
                        "attempt": attempt,
                        "score": evaluation.score,
                        "is_adequate": evaluation.is_adequate,
                        "suggested_action": evaluation.suggested_action,
                    }
                )

                # Check if results are good enough
                if evaluation.score >= self.quality_threshold or evaluation.is_adequate:
                    logger.info(
                        f"Quality acceptable (score: {evaluation.score:.2f}), proceeding"
                    )
                    return chunks, steps, plan

                # Reflect and adjust strategy
                logger.info(
                    f"Quality insufficient (score: {evaluation.score:.2f}), "
                    f"action: {evaluation.suggested_action}"
                )
                should_retry = evaluation.suggested_action in ["reformulate", "expand"]
            else:
                # No reflection - accept results on first successful retrieval
                logger.info(f"Reflection disabled, accepting {len(chunks)} chunks")
                return chunks, steps, plan

            if should_retry and attempt < self.max_iterations:
                # Try expanding the query
                expansion = self.tools.expand_query(query)
                # Use a different expansion on each attempt
                idx = min(attempt - 1, len(expansion.expanded_queries) - 1)
                current_query = expansion.expanded_queries[idx]

                steps.append(
                    {
                        "step": "reformulate",
                        "new_query": current_query,
                        "reason": "Quality too low, trying different phrasing",
                    }
                )

                logger.info(f"Reformulated query: {current_query}")

            elif evaluation.suggested_action == "expand" and attempt < self.max_iterations:
                expansion = self.tools.expand_query(query)
                # Combine original + expansion for broader search
                current_query = f"{query} OR {expansion.expanded_queries[0]}"

                steps.append(
                    {"step": "expand_search", "combined_query": current_query}
                )

                logger.info(f"Expanded search: {current_query[:100]}...")

            else:
                # Proceed with what we have
                logger.info("Max iterations reached or no better strategy, proceeding")
                return chunks, steps, plan

        # Return best effort after max iterations
        logger.info("Completed max iterations")
        return chunks, steps, plan

    def _is_complex_query(self, query: str) -> bool:
        """
        Heuristic to detect complex queries.

        Args:
            query: Query string

        Returns:
            True if query appears complex
        """
        # Check for multiple questions or conjunctions
        markers = ["and", "or", "also", "?", "additionally", "furthermore"]
        word_count = len(query.split())

        has_multiple_markers = sum(1 for m in markers if m in query.lower()) >= 2
        is_long = word_count > 15

        return has_multiple_markers or is_long
