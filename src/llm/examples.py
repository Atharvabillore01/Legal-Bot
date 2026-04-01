"""
Example usage patterns for the LLM Interface & Prompt Builder module.

This module demonstrates 10 common workflows:
1. Basic semantic query
2. Query with confidence scoring
3. Handling low confidence
4. Citation extraction and validation
5. Custom token budget allocation
6. Contradiction handling
7. Batch queries
8. Error handling and recovery
9. Citation mapping
10. Production workflow with full integration
"""

from datetime import datetime, timedelta
from typing import List, Dict

# Import main functions
from src.llm import (
    query_llm_simple,
    LLMQueryEngine,
    prepare_prompt_for_llm,
    count_tokens,
    build_citation_objects,
    parse_citations,
    calculate_query_confidence,
    classify_confidence_level,
    normalize_l2_distance,
    EmptyContextError,
    TokenBudgetExceededError,
    RateLimitError,
)


# ============================================================================
# EXAMPLE 1: Basic Semantic Query
# ============================================================================

def example_1_basic_query():
    """
    Simplest use case: Query with retrieved chunks.
    
    Flow:
    - Provide chunks from Module 3 retrieval
    - Provide metadata lookup
    - Get structured response with answer + citations
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Semantic Query")
    print("="*70)
    
    # Retrieved chunks from Module 3 retrieval & reranking
    chunks = [
        {
            "text": "The liability cap in Section 10 is USD 5,000,000 per occurrence.",
            "doc_name": "indemnity_agreement.pdf",
            "page_number": 7,
            "jurisdiction": "NY",
            "section": "Limitation of Liability"
        },
        {
            "text": "No claims shall be made after the date specified in Section 15(c), which is 30 days after completion.",
            "doc_name": "indemnity_agreement.pdf",
            "page_number": 12,
            "jurisdiction": "NY",
            "section": "Claims Procedures"
        }
    ]
    
    # Metadata for citation mapping
    metadata = {
        "chunk_0": {
            "doc_name": "indemnity_agreement.pdf",
            "page_number": 7,
            "jurisdiction": "NY",
            "section": "Limitation of Liability"
        },
        "chunk_1": {
            "doc_name": "indemnity_agreement.pdf",
            "page_number": 12,
            "jurisdiction": "NY",
            "section": "Claims Procedures"
        }
    }
    
    # Query using simple wrapper
    try:
        response = query_llm_simple(
            chunks=chunks,
            query="What is the liability cap and claim deadline?",
            chunk_metadata=metadata
        )
        
        print(f"\nQuery: {response.query}")
        print(f"\\nAnswer: {response.answer}")
        print(f"\nConfidence: {response.confidence_level} ({response.confidence_score:.2f})")
        print(f"Citations: {len(response.citations)}")
        print(f"Time: {response.total_time_ms():.0f}ms")
        
        return response
    except Exception as e:
        print(f"Error: {e}")


# ============================================================================
# EXAMPLE 2: Query with Confidence Scoring
# ============================================================================

def example_2_confidence_scoring():
    """
    Include normalized similarity scores for confidence calculation.
    
    Flow:
    - Normalize L2 distances to [0, 1]
    - Pass chunk scores to LLM engine
    - Get confidence with multi-factor adjustments
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Query with Confidence Scoring")
    print("="*70)
    
    chunks = [
        {
            "text": "The liability cap is USD 5,000,000 per occurrence.",
            "doc_name": "contract.pdf",
            "page_number": 7,
            "jurisdiction": "NY"
        },
        {
            "text": "Total liability shall not exceed $5M annually.",
            "doc_name": "contract.pdf",
            "page_number": 8,
            "jurisdiction": "NY"
        }
    ]
    
    metadata = {
        "chunk_0": {"doc_name": "contract.pdf", "page_number": 7, "jurisdiction": "NY"},
        "chunk_1": {"doc_name": "contract.pdf", "page_number": 8, "jurisdiction": "NY"}
    }
    
    # L2 distances from FAISS retrieval (example)
    l2_distances = [0.15, 0.32]  # Normalized to [0,1] by normalize_l2_distance
    chunk_scores = [normalize_l2_distance(d) for d in l2_distances]
    print(f"L2 distances: {l2_distances}")
    print(f"Normalized scores: {[f'{s:.3f}' for s in chunk_scores]}")
    
    try:
        engine = LLMQueryEngine()
        response = engine.query_llm(
            chunks=chunks,
            query="What is the liability cap?",
            chunk_metadata=metadata,
            chunk_scores=chunk_scores,
            contradiction_count=0,
            user_id="user_001"
        )
        
        print(f"\nAnswer: {response.answer}")
        print(f"Confidence Score: {response.confidence_score:.3f}")
        print(f"Confidence Level: {response.confidence_level}")
        print(f"Search Time: {response.search_time_ms:.0f}ms")
        print(f"LLM Time: {response.llm_time_ms:.0f}ms")
        
        return response
    except Exception as e:
        print(f"Error: {e}")


# ============================================================================
# EXAMPLE 3: Handling Low Confidence
# ============================================================================

def example_3_low_confidence():
    """
    Handle responses with low confidence scores.
    
    Scenarios:
    - Few chunks (<3)
    - Low similarity scores
    - Multiple contradictions
    - Old sources
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Handling Low Confidence")
    print("="*70)
    
    # Single chunk with low confidence score
    chunks = [
        {
            "text": "There may be provisions regarding liability caps.",
            "doc_name": "policy_doc.pdf",
            "page_number": 42,
            "jurisdiction": "Unknown"
        }
    ]
    
    metadata = {
        "chunk_0": {"doc_name": "policy_doc.pdf", "page_number": 42, "jurisdiction": "Unknown"}
    }
    
    # Low confidence scores
    chunk_scores = [0.25]  # Low match score
    
    try:
        engine = LLMQueryEngine()
        response = engine.query_llm(
            chunks=chunks,
            query="What is the precision liability cap amount?",
            chunk_metadata=metadata,
            chunk_scores=chunk_scores,
            contradiction_count=2  # Multiple contradictions
        )
        
        print(f"\nAnswer: {response.answer}")
        print(f"\\nConfidence: {response.confidence_level} ({response.confidence_score:.2f})")
        
        if response.confidence_level == "LOW":
            print("⚠️  WARNING: Low confidence response - review source documents")
        
        return response
    except Exception as e:
        print(f"Error: {e}")


# ============================================================================
# EXAMPLE 4: Citation Extraction and Validation
# ============================================================================

def example_4_citation_handling():
    """
    Extract, parse, and validate citations from LLM response.
    
    Flow:
    - Build citation objects from [[CITE:...]] markers
    - Map chunk_ids to source metadata
    - Validate citations appear in original chunks
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Citation Extraction and Validation")
    print("="*70)
    
    # Simulated LLM response with citation markers
    response_text = """
    According to the agreement, the liability cap is USD 5,000,000 [[CITE:chunk_15]].
    This applies per occurrence as specified in Section 10 [[CITE:chunk_15]].
    The cap is binding on both parties [[CITE:chunk_23]].
    """
    
    # Metadata for citation mapping
    metadata = {
        "chunk_15": {
            "doc_name": "indemnity_agreement.pdf",
            "page_number": 7,
            "jurisdiction": "NY",
            "section": "Limitation of Liability",
            "text": "The liability cap in Section 10 is USD 5,000,000 per occurrence..."
        },
        "chunk_23": {
            "doc_name": "indemnity_agreement.pdf",
            "page_number": 12,
            "jurisdiction": "NY",
            "section": "Operative Terms",
            "text": "The cap is binding on both parties as stated herein..."
        }
    }
    
    # Extract citations
    citation_ids = parse_citations(response_text)
    print(f"Extracted citation IDs: {citation_ids}")
    
    # Build Citation objects
    citations = build_citation_objects(response_text, metadata)
    print(f"\nCitations found: {len(citations)}")
    
    for i, citation in enumerate(citations, 1):
        print(f"\n  Citation {i}:")
        print(f"    Chunk ID: {citation.chunk_id}")
        print(f"    Source: {citation.source_doc}, p.{citation.page_number}")
        print(f"    Text: \"{citation.text_excerpt}\"")
        print(f"    Offset: chars {citation.character_offset_start}-{citation.character_offset_end}")
        print(f"    Jurisdiction: {citation.jurisdiction}")
        print(f"    Section: {citation.section}")


# ============================================================================
# EXAMPLE 5: Token Budget Allocation
# ============================================================================

def example_5_token_allocation():
    """
    Demonstrate token budget calculation and allocation.
    
    Shows:
    - How many tokens each component uses
    - How many chunks fit
    - What happens when budget is exceeded
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Token Budget Allocation")
    print("="*70)
    
    # Sample chunks with varying sizes
    chunks = [
        {
            "text": "The liability cap is USD 5,000,000 per occurrence. Combined liability of both parties shall not exceed this amount. This includes all types of damages.",
            "doc_name": "contract1.pdf",
            "page_number": 7,
            "jurisdiction": "NY"
        },
        {
            "text": "Indemnification obligations are limited to direct damages. Consequential and incidental damages are excluded.",
            "doc_name": "contract2.pdf",
            "page_number": 15,
            "jurisdiction": "CA"
        },
        {
            "text": "Section 10: Damages and Limitations\n\n10.1 Direct Damages\n10.2 Excluded Damages\n10.3 Limitation Period",
            "doc_name": "contract3.pdf",
            "page_number": 9,
            "jurisdiction": "TX"
        }
    ]
    
    query = "What are the liability caps and damage limitations?"
    
    # Allocate token budget
    allocation = prepare_prompt_for_llm(chunks, query, confidence_score=0.75)
    prompt, token_allocation = allocation
    
    print(f"\nQuery: \"{query}\"")
    print(f"Query tokens: {token_allocation['query_tokens']}")
    print(f"\nChunks provided: {len(chunks)}")
    print(f"Chunks included: {token_allocation['chunks_to_include']}")
    
    print(f"\nToken Allocation:")
    print(f"  System: {token_allocation['system_tokens']:,} tokens")
    print(f"  Context: {token_allocation['context_tokens']:,} tokens")
    print(f"  Query: {token_allocation['query_tokens']:,} tokens")
    print(f"  Response: {token_allocation['response_tokens']:,} tokens")
    print(f"  Total: {token_allocation['total_tokens']:,} tokens")
    print(f"  Remaining: {token_allocation['remaining_tokens']:,} tokens")
    print(f"\nBudget: {token_allocation['total_tokens']:,} / 128,000 ({token_allocation['total_tokens']/1280:.1f}%)")


# ============================================================================
# EXAMPLE 6: Handling Contradictions
# ============================================================================

def example_6_contradictions():
    """
    Show how contradictions affect confidence scoring.
    
    Scenarios:
    - No contradictions: confidence unaffected
    - 1 contradiction: confidence × 0.95
    - 2+ contradictions: further penalties applied
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: Contradiction Handling")
    print("="*70)
    
    chunks = [
        {
            "text": "The liability cap is USD 5,000,000 per occurrence.",
            "doc_name": "agreement_v1.pdf",
            "page_number": 7,
            "jurisdiction": "NY"
        },
        {
            "text": "Total liability shall not exceed USD 3,000,000 annually.",
            "doc_name": "agreement_v2.pdf",
            "page_number": 10,
            "jurisdiction": "NY"
        }
    ]
    
    metadata = {
        "chunk_0": {"doc_name": "agreement_v1.pdf", "page_number": 7, "jurisdiction": "NY"},
        "chunk_1": {"doc_name": "agreement_v2.pdf", "page_number": 10, "jurisdiction": "NY"}
    }
    
    chunk_scores = [0.92, 0.88]
    
    # Test with different contradiction counts
    for contradiction_count in [0, 1, 2]:
        confidence = calculate_query_confidence(
            chunk_scores=chunk_scores,
            contradiction_count=contradiction_count
        )
        
        level = classify_confidence_level(confidence)
        print(f"\nContradictions: {contradiction_count}")
        print(f"  Confidence: {confidence:.3f}")
        print(f"  Level: {level}")
        if contradiction_count > 0:
            print(f"  Penalty: {(1 - (0.95 ** contradiction_count)) * 100:.1f}%")


# ============================================================================
# EXAMPLE 7: Batch Queries
# ============================================================================

def example_7_batch_queries():
    """
    Process multiple queries in sequence.
    
    Shows:
    - Handling multiple user questions
    - Reusing metadata lookup
    - Tracking results
    """
    print("\n" + "="*70)
    print("EXAMPLE 7: Batch Queries")
    print("="*70)
    
    # Shared metadata across all queries
    all_chunks = [
        {
            "text": "The liability cap is USD 5,000,000.",
            "doc_name": "contract.pdf",
            "page_number": 7,
            "jurisdiction": "NY"
        },
        {
            "text": "Payment terms: Net 30 days from invoice date.",
            "doc_name": "contract.pdf",
            "page_number": 12,
            "jurisdiction": "NY"
        },
        {
            "text": "Termination requires 90 days written notice.",
            "doc_name": "contract.pdf",
            "page_number": 18,
            "jurisdiction": "NY"
        }
    ]
    
    metadata = {
        f"chunk_{i}": {"doc_name": "contract.pdf", "page_number": [7, 12, 18][i], "jurisdiction": "NY"}
        for i in range(len(all_chunks))
    }
    
    # Batch of queries
    queries = [
        "What is the liability cap?",
        "What are the payment terms?",
        "How can the contract be terminated?"
    ]
    
    results = []
    
    try:
        engine = LLMQueryEngine()
        
        for i, query in enumerate(queries, 1):
            print(f"\nQuery {i}: {query}")
            
            response = engine.query_llm(
                chunks=all_chunks,
                query=query,
                chunk_metadata=metadata,
                user_id="batch_user"
            )
            
            results.append(response)
            print(f"  ✓ Confidence: {response.confidence_level}")
            print(f"  ✓ Citations: {len(response.citations)}")
    
    except Exception as e:
        print(f"Error in batch processing: {e}")
    
    # Summary
    print(f"\n\nBatch Summary:")
    print(f"  Queries processed: {len(results)}")
    print(f"  Total time: {sum(r.total_time_ms() for r in results):.0f}ms")
    print(f"  Avg time per query: {sum(r.total_time_ms() for r in results)/len(results):.0f}ms")


# ============================================================================
# EXAMPLE 8: Error Handling and Recovery
# ============================================================================

def example_8_error_handling():
    """
    Demonstrate error handling and recovery strategies.
    
    Handles:
    - Empty context (no chunks)
    - Token budget exceeded
    - Rate limiting (with automatic retry)
    - API errors
    """
    print("\n" + "="*70)
    print("EXAMPLE 8: Error Handling and Recovery")
    print("="*70)
    
    # Scenario 1: Empty context
    print("\nScenario 1: Empty context")
    try:
        engine = LLMQueryEngine()
        response = engine.query_llm(
            chunks=[],  # Empty!
            query="What is the liability cap?",
            chunk_metadata={}
        )
    except EmptyContextError as e:
        print(f"  ✓ Caught: {e}")
    
    # Scenario 2: Token budget exceeded (single massive chunk)
    print("\nScenario 2: Token budget exceeded")
    try:
        huge_chunk = {
            "text": "X" * 500000,  # 500K tokens > budget
            "doc_name": "huge.pdf",
            "page_number": 1,
            "jurisdiction": "NY"
        }
        
        engine = LLMQueryEngine()
        response = engine.query_llm(
            chunks=[huge_chunk],
            query="What is the cap?",
            chunk_metadata={"chunk_0": {"doc_name": "huge.pdf", "page_number": 1}}
        )
    except TokenBudgetExceededError as e:
        print(f"  ✓ Caught: {e}")
    
    # Scenario 3: Rate limiting (automatic retry would happen)
    print("\nScenario 3: API rate limiting")
    print("  Note: Module automatically retries with exponential backoff")
    print("  - Initial wait: 2 seconds")
    print("  - Backoff multiplier: 2x")
    print("  - Max retries: 3")
    print("  - Max wait: 32 seconds")


# ============================================================================
# EXAMPLE 9: Production Workflow
# ============================================================================

def example_9_production_workflow():
    """
    Complete production workflow integrating Modules 3 and 4.
    
    End-to-end: Retrieval → LLM → Response Generation
    """
    print("\n" + "="*70)
    print("EXAMPLE 9: Production Workflow")
    print("="*70)
    
    # Step 1: Receive query from user
    user_id = "user_123"
    user_query = "What is the liability cap and payment terms?"
    
    print(f"\nUser: {user_query}")
    
    # Step 2: Retrieve and rerank chunks (Module 3 output simulated)
    print("\n[Module 3] Retrieving and reranking...")
    retrieved_chunks = [
        {
            "text": "The liability cap is USD 5,000,000 per occurrence.",
            "doc_name": "indemnity.pdf",
            "page_number": 7,
            "jurisdiction": "NY",
            "section": "Liability"
        },
        {
            "text": "Payment terms: Net 30 days from invoice.",
            "doc_name": "terms.pdf",
            "page_number": 5,
            "jurisdiction": "NY",
            "section": "Payment"
        }
    ]
    
    # Extract metadata
    metadata = {
        f"chunk_{i}": {
            "doc_name": chunk['doc_name'],
            "page_number": chunk['page_number'],
            "jurisdiction": chunk['jurisdiction'],
            "section": chunk['section']
        }
        for i, chunk in enumerate(retrieved_chunks)
    }
    
    # Simulated L2 distances from FAISS
    l2_distances = [0.15, 0.22]
    chunk_scores = [normalize_l2_distance(d) for d in l2_distances]
    
    print(f"Retrieved: {len(retrieved_chunks)} chunks")
    print(f"Scores: {[f'{s:.3f}' for s in chunk_scores]}")
    
    # Step 3: Query LLM (Module 4)
    print("\n[Module 4] Querying LLM...")
    
    try:
        engine = LLMQueryEngine()
        response = engine.query_llm(
            chunks=retrieved_chunks,
            query=user_query,
            chunk_metadata=metadata,
            chunk_scores=chunk_scores,
            contradiction_count=0,
            user_id=user_id
        )
        
        # Step 4: Return structured response
        print("\n[Response] Generated")
        print(f"Answer: {response.answer[:200]}...")
        print(f"Confidence: {response.confidence_level} ({response.confidence_score:.2f})")
        print(f"Citations: {len(response.citations)}")
        print(f"Total time: {response.total_time_ms():.0f}ms")
        
        # Step 5: Render citations for frontend
        print("\n[Citations]")
        for citation in response.citations:
            print(f"  - {citation.source_doc}, p.{citation.page_number}: {citation.text_excerpt[:50]}...")
        
        # Step 6: Log audit trail
        print(f"\n[Audit]")
        print(f"  User: {response.user_id}")
        print(f"  Query: {response.query}")
        print(f"  Timestamp: {response.created_at}")
        print(f"  Model: {response.model}")
        print(f"  Search time: {response.search_time_ms:.0f}ms")
        print(f"  LLM time: {response.llm_time_ms:.0f}ms")
        
    except Exception as e:
        print(f"Error: {e}")


# ============================================================================
# EXAMPLE 10: Advanced Confidence Analysis
# ============================================================================

def example_10_advanced_confidence():
    """
    Detailed confidence scoring with multiple factors.
    
    Demonstrates:
    - Multi-factor adjustments
    - Source authority impact
    - Source recency impact
    """
    print("\n" + "="*70)
    print("EXAMPLE 10: Advanced Confidence Analysis")
    print("="*70)
    
    # Chunks with metadata for confidence adjustments
    chunk_scores = [0.92, 0.87]
    authority_levels = ["binding", "precedent"]
    
    # Recent and old sources
    now = datetime.now()
    published_dates = [
        now - timedelta(days=30),      # Recent
        now - timedelta(days=365*6)    # 6 years old
    ]
    
    print(f"\nChunk Scores: {chunk_scores}")
    print(f"Authority Levels: {authority_levels}")
    print(f"Published Dates:")
    for i, date in enumerate(published_dates, 1):
        age_days = (now - date).days
        print(f"  Chunk {i}: {date.date()} ({age_days} days old)")
    
    # Calculate with different contradiction counts
    print("\n" + "-"*50)
    for contradiction_count in [0, 1, 2]:
        # Calculate confidence with all factors
        confidence = calculate_query_confidence(
            chunk_scores=chunk_scores,
            contradiction_count=contradiction_count,
            authority_levels=authority_levels,
            published_dates=published_dates
        )
        
        level = classify_confidence_level(confidence)
        
        print(f"\nContradictions: {contradiction_count}")
        print(f"  Final Confidence: {confidence:.4f}")
        print(f"  Level: {level}")
        print(f"  Interpretation: {confidence:.0%} confident in this answer")
        
        # Breakdown of adjustments
        if contradiction_count > 0:
            contradiction_penalty = 0.95 ** contradiction_count
            print(f"  Contradiction Penalty: ×{contradiction_penalty:.4f} ({(1-contradiction_penalty)*100:.1f}% reduction)")
        
        # Authority adjustment
        low_authority_count = 0  # All are binding/precedent
        if low_authority_count > 0:
            print(f"  Authority Penalty: ×{0.85**low_authority_count:.4f}")
        else:
            print(f"  Authority Penalty: None (all reliable sources)")
        
        # Recency adjustment
        old_source_count = sum(1 for d in published_dates if (now - d).days > 365*5)
        if old_source_count > 0:
            print(f"  Recency Penalty: ×{0.90**old_source_count:.4f} ({old_source_count} old source(s))")


# ============================================================================
# MAIN: Run All Examples
# ============================================================================

if __name__ == "__main__":
    print("#" * 70)
    print("# LLM Interface & Prompt Builder - Example Workflows")
    print("#" * 70)
    
    # Note: Examples 1 and 2 require OpenAI API key
    # Set: export OPENAI_API_KEY="sk-..."
    
    try:
        # Basic examples (no API calls)
        example_5_token_allocation()
        example_6_contradictions()
        example_4_citation_handling()
        example_8_error_handling()
        example_10_advanced_confidence()
        
        # API-dependent examples (uncomment if API key set)
        # example_1_basic_query()
        # example_2_confidence_scoring()
        # example_3_low_confidence()
        # example_7_batch_queries()
        # example_9_production_workflow()
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "#" * 70)
    print("# Examples Complete")
    print("#" * 70)
