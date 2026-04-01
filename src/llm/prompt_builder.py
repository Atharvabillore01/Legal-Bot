"""
src/llm/prompt_builder.py

Prompt construction and token budget allocation for LLM queries.

Functions orchestrate the assembly of prompts from system message, context chunks,
user query, and instructions. Handles token counting, budget allocation, and
progressive chunk removal if context exceeds limits.

Key Functions:
    - build_system_prompt: Generate system message
    - build_context_prompt: Format chunks into context section
    - build_instruction_prompt: Generate instruction message
    - construct_full_prompt: Assemble complete prompt
    - allocate_token_budget: Calculate token allocation across components
"""

import logging
import tiktoken
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .models import QueryResponse
from .exceptions import (
    PromptError,
    PromptTemplateError,
    TokenError,
    TokenCountError,
    TokenBudgetExceededError,
    TokenAllocationError,
    TokenizerInitError
)
from .constants import (
    SYSTEM_PROMPT,
    INSTRUCTION_PROMPT,
    CHUNK_PREFIX,
    QUERY_PREFIX,
    TOKEN_BUDGET_SYSTEM,
    TOKEN_BUDGET_CONTEXT,
    TOKEN_BUDGET_QUERY,
    TOKEN_BUDGET_RESPONSE,
    MAX_CONTEXT_TOKENS,
    DEBUG_PROMPT_BUILDING
)

logger = logging.getLogger(__name__)


def _get_tokenizer():
    """
    Initialize and return tiktoken encoder for GPT-3.5-turbo.
    
    Returns:
        tiktoken.Encoding: Tokenizer instance
    
    Raises:
        TokenizerInitError: If tiktoken cannot be initialized
    """
    try:
        return tiktoken.get_encoding("cl100k_base")  # gpt-3.5-turbo and gpt-4o encoding
    except Exception as e:
        raise TokenizerInitError(
            f"Failed to initialize tokenizer: {str(e)}",
            error_code="TOKENIZER_001"
        )


# Module-level tokenizer instance (cached)
_TOKENIZER = None


def _ensure_tokenizer():
    """Initialize tokenizer if not already done."""
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = _get_tokenizer()


def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.
    
    Args:
        text (str): Text to count tokens for
    
    Returns:
        int: Number of tokens
    
    Raises:
        TokenCountError: If token counting fails
    """
    if not text:
        return 0
    
    try:
        _ensure_tokenizer()
        return len(_TOKENIZER.encode(text))
    except Exception as e:
        raise TokenCountError(
            f"Failed to count tokens: {str(e)}",
            text_length=len(text)
        )


def build_system_prompt() -> str:
    """
    Generate the system prompt message.
    
    The system prompt defines the AI's role, constraints, and behavior.
    It should emphasize:
    - Answer only from provided context
    - Never speculate
    - Cite all claims
    - Acknowledge uncertainty
    
    Returns:
        str: System prompt message
    
    Example:
        >>> prompt = build_system_prompt()
        >>> assert "professional legal assistant" in prompt.lower()
    """
    return SYSTEM_PROMPT


def build_context_prompt(chunks: List[Dict], start_number: int = 1) -> str:
    """
    Format retrieved chunks into context section of prompt.
    
    Each chunk is prefixed with metadata (source, page, jurisdiction).
    Chunks are numbered sequentially for reference.
    
    Args:
        chunks (List[Dict]): Retrieved chunks from Module 3
            Each chunk must have: text, doc_name, page_number, jurisdiction
        start_number (int): Starting chunk number (default: 1)
    
    Returns:
        str: Formatted context section
    
    Raises:
        PromptError: If chunks are malformed or missing required fields
    
    Example:
        >>> chunks = [
        ...     {"text": "Liability cap is $5M", "doc_name": "contract.pdf", 
        ...      "page_number": 7, "jurisdiction": "NY"}
        ... ]
        >>> context = build_context_prompt(chunks)
        >>> assert "CHUNK 1" in context
        >>> assert "contract.pdf" in context
    """
    if not chunks:
        return "CONTEXT:\n(No relevant context available)\n"
    
    context_parts = ["CONTEXT:"]
    
    for i, chunk in enumerate(chunks, start=start_number):
        # Validate minimum required fields
        for field in ['text', 'doc_name']:
            if not chunk.get(field):
                raise PromptTemplateError(
                    f"Chunk missing required field: {field}",
                    missing_fields=[field]
                )
        
        # Build chunk header with metadata
        chunk_header = CHUNK_PREFIX.format(
            chunk_number=i,
            chunk_id=chunk.get('chunk_id', f'chunk_{i}'),
            doc_name=chunk['doc_name'],
            page_number=chunk.get('page_number') or 'N/A',
            jurisdiction=chunk.get('jurisdiction') or 'N/A'
        )
        
        # Add chunk to context
        context_parts.append(f"\n{chunk_header}")
        context_parts.append(chunk['text'])
    
    return "\n".join(context_parts) + "\n"


def build_instruction_prompt(confidence_score: float) -> str:
    """
    Generate the instruction prompt (appended after context).
    
    Instructions clarify citation requirements, confidence notation,
    and response format expectations.
    
    Args:
        confidence_score (float): Confidence score [0, 1] to include in instructions
    
    Returns:
        str: Instruction prompt with confidence notation
    
    Example:
        >>> instr = build_instruction_prompt(0.92)
        >>> assert "0.92" in instr
    """
    return INSTRUCTION_PROMPT.format(
        doc_name="{doc_name}",
        page_number="{page_number}",
        chunk_id="{chunk_id}",
        confidence_score=f"{confidence_score:.2f}"
    )


def construct_full_prompt(
    system: str,
    context: str,
    query: str,
    instructions: str
) -> str:
    """
    Assemble complete prompt from components.
    
    Structure:
        SYSTEM: {system_prompt}
        
        {context_section}
        
        USER QUERY: {user_query}
        
        {instructions}
    
    Args:
        system (str): System prompt message
        context (str): Formatted context chunks
        query (str): User question
        instructions (str): Instruction message
    
    Returns:
        str: Complete prompt ready for LLM
    
    Raises:
        PromptError: If any component is missing or invalid
    
    Example:
        >>> full = construct_full_prompt(system, context, "What is X?", instructions)
        >>> assert "USER QUERY" in full
    """
    if not all([system, context, query, instructions]):
        raise PromptTemplateError("All prompt components are required")
    
    prompt_parts = [
        f"SYSTEM: {system}",
        "",
        context,
        f"{QUERY_PREFIX}: {query}",
        "",
        instructions
    ]
    
    return "\n".join(prompt_parts)


def allocate_token_budget(
    chunks: List[Dict],
    query: str,
    max_context_tokens: int = MAX_CONTEXT_TOKENS
) -> Dict[str, int]:
    """
    Calculate token allocation across prompt components.
    
    Allocates tokens as:
    - System: 10% (~12.8K tokens)
    - Context: 70% (~89.6K tokens)
    - Query: 5% (~6.4K tokens)
    - Response: 15% (~19.2K tokens, reserved)
    
    If total exceeds budget, progressively removes least-relevant chunks.
    
    Args:
        chunks (List[Dict]): Retrieved chunks to include
        query (str): User question
        max_context_tokens (int): Maximum context length (default: 128K)
    
    Returns:
        Dict[str, int]: Token allocation with keys:
            - 'system_tokens': Allocated for system prompt
            - 'context_tokens': Allocated for chunks
            - 'query_tokens': Allocated for user query
            - 'response_tokens': Reserved for response
            - 'total_tokens': Sum of above
            - 'chunks_to_include': Number of chunks that fit
    
    Raises:
        TokenBudgetExceededError: If even 1 chunk + query exceeds budget
        TokenAllocationError: If allocation calculation fails
    
    Example:
        >>> chunks = [{"text": "Sample content...", ...} for _ in range(10)]
        >>> query = "What is the liability cap?"
        >>> allocation = allocate_token_budget(chunks, query)
        >>> assert allocation['chunks_to_include'] <= len(chunks)
    """
    try:
        # Count tokens for fixed components
        system_prompt = build_system_prompt()
        system_tokens = count_tokens(system_prompt)
        
        query_tokens = count_tokens(query)
        
        # Calculate available tokens for context
        # Reserved: system + response buffer
        reserved_tokens = system_tokens + TOKEN_BUDGET_RESPONSE
        available_for_context = max_context_tokens - reserved_tokens
        
        if available_for_context < 500:
            raise TokenBudgetExceededError(
                f"Insufficient tokens for context ({available_for_context} available, need 500 minimum)",
                requested_tokens=reserved_tokens,
                max_tokens=max_context_tokens
            )
        
        # Add chunks until context budget exhausted
        chunks_included = 0
        context_tokens_used = 0
        
        for chunk in chunks:
            chunk_text = str(chunk.get('text', ''))
            chunk_header = CHUNK_PREFIX.format(
                chunk_number=chunks_included + 1,
                chunk_id=chunk.get('chunk_id', f'chunk_{chunks_included + 1}'),
                doc_name=chunk.get('doc_name', ''),
                page_number=chunk.get('page_number') or 'N/A',
                jurisdiction=chunk.get('jurisdiction') or 'N/A'
            )
            
            chunk_total_tokens = count_tokens(chunk_header + "\n" + chunk_text)
            
            if context_tokens_used + chunk_total_tokens <= available_for_context:
                context_tokens_used += chunk_total_tokens
                chunks_included += 1
            else:
                # Budget exhausted, stop adding chunks
                break
        
        if chunks_included == 0:
            raise TokenBudgetExceededError(
                "Even single chunk exceeds remaining token budget",
                requested_tokens=count_tokens(chunks[0]['text']) if chunks else 100,
                max_tokens=available_for_context
            )
        
        allocation = {
            'system_tokens': system_tokens,
            'context_tokens': context_tokens_used,
            'query_tokens': query_tokens,
            'response_tokens': TOKEN_BUDGET_RESPONSE,
            'total_tokens': system_tokens + context_tokens_used + query_tokens + TOKEN_BUDGET_RESPONSE,
            'chunks_to_include': chunks_included,
            'remaining_tokens': max_context_tokens - (system_tokens + context_tokens_used + query_tokens + TOKEN_BUDGET_RESPONSE)
        }
        
        if DEBUG_PROMPT_BUILDING:
            logger.info(f"Token allocation: {allocation}")
        
        return allocation
    
    except (TokenCountError, TokenBudgetExceededError):
        raise
    except Exception as e:
        raise TokenAllocationError(
            f"Failed to allocate token budget: {str(e)}"
        )


def prepare_prompt_for_llm(
    chunks: List[Dict],
    query: str,
    confidence_score: float = 0.5
) -> Tuple[str, Dict[str, int]]:
    """
    Prepare complete prompt and token allocation for LLM call.
    
    Orchestrates the full prompt construction pipeline:
    1. Allocate token budget
    2. Build system prompt
    3. Format context chunks
    4. Build instructions
    5. Assemble complete prompt
    
    Args:
        chunks (List[Dict]): Retrieved chunks from retrieval module
        query (str): User question
        confidence_score (float): Estimated confidence for instructions (default: 0.5)
    
    Returns:
        Tuple[str, Dict]: (complete_prompt, token_allocation)
    
    Raises:
        PromptError: If prompt construction fails
        TokenError: If token allocation fails
    
    Example:
        >>> chunks = [{...}, {...}]
        >>> query = "What are the payment terms?"
        >>> prompt, allocation = prepare_prompt_for_llm(chunks, query, 0.85)
        >>> assert len(prompt) > 100
        >>> assert allocation['chunks_to_include'] > 0
    """
    # Allocate tokens (may reduce chunks if needed)
    allocation = allocate_token_budget(chunks, query)
    
    # Trim chunks to fit budget
    chunks_to_use = chunks[:allocation['chunks_to_include']]
    
    # Build prompt components
    system = build_system_prompt()
    context = build_context_prompt(chunks_to_use)
    instructions = build_instruction_prompt(confidence_score)
    
    # Assemble full prompt
    full_prompt = construct_full_prompt(system, context, query, instructions)
    
    if DEBUG_PROMPT_BUILDING:
        logger.debug(f"Prompt length: {len(full_prompt)} chars, {count_tokens(full_prompt)} tokens")
    
    return full_prompt, allocation
