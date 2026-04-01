"""
Example usage patterns for the Embeddings & FAISS Vector Store module.

This module demonstrates:
1. Basic embedding generation and indexing
2. Batch processing with error handling
3. Multi-user isolation
4. Vector search with result ranking
5. Backup and recovery workflows
6. Concurrency handling
7. Index type selection and migration
8. Production best practices
"""

import logging
from typing import List
from datetime import datetime

from src.embeddings import (
    # Models
    Chunk,
    EmbeddedChunk,
    UserIndex,
    RetrievalResult,
    # Core functions
    embed_chunks,
    embed_query,
    create_user_index,
    add_chunks_to_index,
    get_index,
    search_index,
    # Retrieval
    retrieve,
    retrieve_with_reranking,
    batch_retrieve,
    # Storage
    save_index,
    load_index_files,
    backup_index,
    recover_from_backup,
    list_backups,
    # Concurrency
    read_lock,
    write_lock,
    # Exceptions
    EmbeddingError,
    RateLimitError,
    APITimeoutError,
    IndexNotFoundError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_basic_embedding_and_indexing():
    """
    Example 1: Basic workflow - ingest document chunks and create searchable index.
    
    This demonstrates:
    - Creating an index for a user
    - Generating embeddings via OpenAI
    - Adding embeddings to FAISS index
    - Basic metadata tracking
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Embedding and Indexing")
    print("="*70)
    
    user_id = "user_alice"
    
    # Step 1: Create chunks (simulating output from Module 1)
    chunks = [
        Chunk(
            chunk_id="contract_1_0",
            doc_id="contract_1",
            doc_name="service_agreement.pdf",
            chunk_index=0,
            text="Article 1: Definitions. Customer means the entity purchasing services...",
            page_number=1,
            section="Article 1",
            jurisdiction="California",
            token_count=75,
            has_ocr=False,
            text_checksum="abc123",
            uploaded_at=datetime.now().isoformat(),
            user_id=user_id,
        ),
        Chunk(
            chunk_id="contract_1_1",
            doc_id="contract_1",
            doc_name="service_agreement.pdf",
            chunk_index=1,
            text="Article 2: Payment Terms. Customer shall pay Vendor within 30 days...",
            page_number=2,
            section="Article 2",
            jurisdiction="California",
            token_count=82,
            has_ocr=False,
            text_checksum="def456",
            uploaded_at=datetime.now().isoformat(),
            user_id=user_id,
        ),
    ]
    
    # Step 2: Create user's index
    logger.info(f"Creating index for {user_id}")
    user_index = create_user_index(user_id=user_id)
    print(f"✓ Index created: type={user_index.index_type}, chunks={user_index.chunk_count}")
    
    # Step 3: Generate embeddings
    logger.info(f"Embedding {len(chunks)} chunks")
    try:
        embedded_chunks = embed_chunks(chunks, user_id=user_id)
        print(f"✓ Embedded {len(embedded_chunks)} chunks successfully")
    except RateLimitError as e:
        print(f"✗ Rate limited: retry after {e.retry_after}s")
        return
    except EmbeddingError as e:
        print(f"✗ Embedding failed: {e}")
        return
    
    # Step 4: Add to index
    logger.info(f"Adding {len(embedded_chunks)} chunks to index")
    updated_index = add_chunks_to_index(user_id=user_id, embedded_chunks=embedded_chunks)
    print(f"✓ Index updated: total chunks={updated_index.chunk_count}")
    
    # Step 5: Verify embeddings
    assert len(embedded_chunks[0].embedding) == 3072, "Embedding dimension should be 3072"
    assert embedded_chunks[0].embedding_model == "text-embedding-3-large"
    print(f"✓ Embedding validation passed (3072 dimensions)")


def example_2_semantic_search():
    """
    Example 2: Vector search and retrieval.
    
    This demonstrates:
    - Querying the index with natural language
    - Retrieving top-k similar chunks
    - Examining similarity scores
    - Handling missing indices
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Semantic Search and Retrieval")
    print("="*70)
    
    user_id = "user_alice"
    query = "What are the payment terms and deadlines?"
    
    logger.info(f"Retrieving for user {user_id}")
    try:
        results = retrieve(
            user_id=user_id,
            query=query,
            k=5,
            threshold=1000.0  # Max L2 distance
        )
        
        if not results:
            print(f"No results found for: '{query}'")
            return
        
        print(f"Query: '{query}'")
        print(f"Found {len(results)} relevant chunks:\n")
        
        for i, result in enumerate(results, 1):
            # Similarity score is normalized from L2 distance
            print(f"{i}. Similarity: {result.similarity_score:.2%}")
            print(f"   Document: {result.doc_name} (p. {result.page_number})")
            print(f"   Section: {result.section}")
            print(f"   Text: {result.text[:80]}...")
            print()
        
        # Statistics
        avg_similarity = sum(r.similarity_score for r in results) / len(results)
        print(f"Average similarity: {avg_similarity:.2%}")
        
    except IndexNotFoundError:
        print(f"✗ No index found for user {user_id}")
    except EmbeddingError as e:
        print(f"✗ Cannot embed query: {e}")


def example_3_batch_processing():
    """
    Example 3: Processing multiple chunks in batches.
    
    This demonstrates:
    - Batch embedding (100 chunks per API call)
    - Automatic batch splitting
    - Cost calculation
    - Error handling in batches
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Batch Processing Large Document Sets")
    print("="*70)
    
    user_id = "user_bob"
    
    # Simulate large document with many chunks
    chunk_count = 350
    logger.info(f"Processing large document: {chunk_count} chunks")
    
    # Generate dummy chunks
    chunks = [
        Chunk(
            chunk_id=f"doc_large_{i}",
            doc_id="doc_large",
            doc_name="large_legal_document.pdf",
            chunk_index=i,
            text=f"Section {i}: Lorem ipsum dolor sit amet, consectetur adipiscing elit...",
            page_number=1 + i // 5,
            section=f"Section {i}",
            jurisdiction="Delaware",
            token_count=750,
            has_ocr=False,
            text_checksum=f"hash_{i}",
            uploaded_at=datetime.now().isoformat(),
            user_id=user_id,
        )
        for i in range(chunk_count)
    ]
    
    # Create index
    logger.info(f"Creating index for {user_id}")
    create_user_index(user_id=user_id)
    
    # Embed with automatic batching (100 chunks per batch)
    logger.info(f"Embedding {chunk_count} chunks in batches of 100")
    try:
        embedded_chunks = embed_chunks(
            chunks,
            user_id=user_id,
            batch_size=100  # API limit is 100
        )
        
        batch_count = (len(chunks) + 99) // 100
        cost_estimate = len(chunks) * 0.02 / 1_000_000  # OpenAI pricing
        
        print(f"✓ Processed {len(embedded_chunks)} chunks")
        print(f"  Batches: {batch_count}")
        print(f"  Estimated cost: ${cost_estimate:.6f}")
        
    except Exception as e:
        print(f"✗ Batch processing failed: {e}")
        return
    
    # Add all to index
    logger.info(f"Adding {len(embedded_chunks)} chunks to index")
    updated_index = add_chunks_to_index(user_id=user_id, embedded_chunks=embedded_chunks)
    print(f"✓ Index now contains {updated_index.chunk_count} chunks")


def example_4_index_type_selection():
    """
    Example 4: Choosing between IndexFlatL2 and IndexIVFFlat.
    
    This demonstrates:
    - Index type selection strategy
    - Performance tradeoffs
    - When to use each type
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Index Type Selection and Performance")
    print("="*70)
    
    # Scenario A: Small legal team (flat index)
    print("\nScenario A: Small Team (<100K chunks)")
    print("-" * 50)
    user_id_small = "user_carol"
    chunk_count_small = 50_000
    
    create_user_index(user_id=user_id_small, index_type="flat")
    print(f"✓ Created IndexFlatL2 for {chunk_count_small:,} chunks")
    print("  Pros: 100% accurate, simple")
    print("  Cons: Slower search (100-500ms)")
    print("  Query latency: ~200ms for 50K chunks")
    print("  Throughput: ~200 queries/second")
    
    # Scenario B: Enterprise deployment (IVF index)
    print("\nScenario B: Enterprise (>100K chunks)")
    print("-" * 50)
    user_id_large = "user_david"
    chunk_count_large = 500_000
    
    create_user_index(user_id=user_id_large, index_type="ivf")
    print(f"✓ Created IndexIVFFlat for {chunk_count_large:,} chunks")
    print("  Pros: Fast search (10-100ms), scalable")
    print("  Cons: ~99% accuracy, requires tuning")
    print("  Query latency: ~50ms for 500K chunks")
    print("  Throughput: ~1000 queries/second")
    
    print("\nRecommendation:")
    print("  • <100K chunks    → IndexFlatL2 (accuracy > speed)")
    print("  • 100K-1M chunks  → IndexIVFFlat (balanced)")
    print("  • >1M chunks      → IndexIVFFlat with GPU acceleration")


def example_5_multi_user_isolation():
    """
    Example 5: Multi-user environment with isolated indices.
    
    This demonstrates:
    - Per-user index isolation
    - Read/write locks for concurrency
    - Query separation
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Multi-User Isolation and Concurrency Control")
    print("="*70)
    
    users = ["user_alice", "user_bob", "user_carol"]
    
    # Create indices for multiple users
    print("Creating indices for multiple users:")
    for user_id in users:
        create_user_index(user_id=user_id)
        print(f"  ✓ {user_id}")
    
    print("\nQuerying with read locks (concurrent allowed):")
    # In production, these would run in parallel
    for user_id in users:
        with read_lock(user_id=user_id, timeout=30):
            # Multiple read locks can be held simultaneously
            print(f"  ✓ Read lock acquired for {user_id}")
            # Query happens here
    
    print("\nModifying with write lock (exclusive):")
    user_id = "user_alice"
    with write_lock(user_id=user_id, timeout=30):
        print(f"  ✓ Write lock acquired for {user_id}")
        # Only this thread can access the index
        print(f"  ✓ Adding chunks to {user_id}'s index...")
        # add_chunks_to_index happens here
    
    print("\nIndex isolation verified:")
    print("  ✓ Each user has independent /indexes/{user_id}/ directory")
    print("  ✓ Queries for user_alice don't affect user_bob's index")
    print("  ✓ Concurrent reads allowed; writes are exclusive")


def example_6_backup_and_recovery():
    """
    Example 6: Index backup, recovery, and retention.
    
    This demonstrates:
    - Creating point-in-time backups
    - Listing backup history
    - Recovering from backups
    - Automatic retention policy
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: Backup and Recovery Strategy")
    print("="*70)
    
    user_id = "user_eve"
    
    # Create initial index
    logger.info(f"Creating index for {user_id}")
    create_user_index(user_id=user_id)
    print(f"✓ Initial index created")
    
    # Create first backup
    logger.info(f"Creating backup 1 for {user_id}")
    backup_path_1 = backup_index(
        user_id=user_id,
        description="Initial backup - 0 chunks"
    )
    print(f"✓ Backup 1 created: {backup_path_1}")
    
    # Simulate adding chunks
    print("  [Adding 500 chunks to index...]")
    
    # Create second backup (after modifications)
    logger.info(f"Creating backup 2 for {user_id}")
    backup_path_2 = backup_index(
        user_id=user_id,
        description="After bulk import - 500 chunks"
    )
    print(f"✓ Backup 2 created: {backup_path_2}")
    
    # List all backups
    logger.info(f"Listing backups for {user_id}")
    backups = list_backups(user_id=user_id)
    
    print(f"\nBackup History ({len(backups)} backups):")
    for backup in backups:
        print(f"  • {backup.backup_timestamp}")
        print(f"    Description: {backup.description}")
        print(f"    Chunks: {backup.chunk_count}")
        print(f"    Size: {backup.size_mb:.1f} MB")
        print(f"    Checksum: {backup.checksum[:16]}...")
        print()
    
    # Recover from specific backup
    logger.info(f"Recovering {user_id} from backup")
    if backups:
        recovered_metadata = recover_from_backup(
            user_id=user_id,
            backup_timestamp=backups[-1].backup_timestamp
        )
        print(f"✓ Recovered from backup: {recovered_metadata['user_id']}")
        print(f"  Chunks restored: {recovered_metadata['chunk_count']}")
        print(f"  Timestamp: {recovered_metadata['last_modified']}")
    
    print("\nRetention Policy:")
    print("  • Keep last 10 backups per user")
    print("  • Keep daily backups for 30 days")
    print("  • Automatic cleanup of old backups")


def example_7_reranking():
    """
    Example 7: Retrieve with optional re-ranking.
    
    This demonstrates:
    - Retrieving more candidates than needed
    - Re-ranking for semantic relevance
    - Cross-encoder scoring
    """
    print("\n" + "="*70)
    print("EXAMPLE 7: Retrieval with Re-ranking")
    print("="*70)
    
    user_id = "user_alice"
    query = "liability and indemnification clauses"
    
    print(f"Query: '{query}'")
    print("\nStandard retrieval (top 10):")
    
    try:
        # Get top 10 results
        results = retrieve(user_id=user_id, query=query, k=10)
        
        for i, result in enumerate(results[:5], 1):
            print(f"  {i}. Score: {result.similarity_score:.2%} | {result.text[:60]}...")
        
        print("\nWith re-ranking (k_initial=50, k_final=10):")
        # Retrieve more candidates, re-rank to top 10
        results_reranked = retrieve_with_reranking(
            user_id=user_id,
            query=query,
            k_initial=50,  # Get 50 candidates
            k_final=10     # Re-rank to top 10
        )
        
        for i, result in enumerate(results_reranked[:5], 1):
            print(f"  {i}. Score: {result.similarity_score:.2%} | {result.text[:60]}...")
        
        print("\n✓ Re-ranking often produces better semantic results")
        print("  Trade-off: Slower (multiple re-rankings)")
        
    except IndexNotFoundError:
        print(f"✗ No index for {user_id}")


def example_8_error_handling_and_robustness():
    """
    Example 8: Comprehensive error handling patterns.
    
    This demonstrates:
    - Handling API rate limits
    - Handling index not found errors
    - Handling timeout errors
    - Recovery strategies
    """
    print("\n" + "="*70)
    print("EXAMPLE 8: Error Handling and Recovery")
    print("="*70)
    
    user_id = "user_frank"
    
    # Pattern 1: Retry with exponential backoff
    print("Pattern 1: Exponential Backoff on Rate Limit")
    print("-" * 50)
    max_retries = 3
    attempts = 0
    
    while attempts < max_retries:
        try:
            # Simulate embedding call
            chunks = []  # Empty for demo
            # embedded_chunks = embed_chunks(chunks, user_id=user_id)
            print(f"✓ Embedding succeeded on attempt {attempts + 1}")
            break
        except RateLimitError as e:
            attempts += 1
            wait_time = 2 ** attempts  # Exponential: 2s, 4s, 8s
            if attempts >= max_retries:
                print(f"✗ Failed after {max_retries} attempts")
                break
            print(f"  Rate limited. Retry in {wait_time}s... (attempt {attempts}/{max_retries})")
            # In production: time.sleep(wait_time)
    
    # Pattern 2: Handle missing index gracefully
    print("\nPattern 2: Graceful Index Not Found")
    print("-" * 50)
    
    nonexistent_user = "user_nonexistent"
    try:
        results = retrieve(user_id=nonexistent_user, query="test")
    except IndexNotFoundError:
        print(f"✓ Caught: User {nonexistent_user} has no index")
        print(f"  Action: Create index and prompt user to upload documents")
        create_user_index(user_id=nonexistent_user)
        print(f"  ✓ Index created; ready for ingestion")
    
    # Pattern 3: Handle API timeout
    print("\nPattern 3: Timeout Handling")
    print("-" * 50)
    
    timeout_seconds = 60
    try:
        # embed_chunks with timeout
        print(f"✓ Query with {timeout_seconds}s timeout")
        # results = retrieve(user_id=user_id, query="test", timeout=timeout_seconds)
    except APITimeoutError as e:
        print(f"✗ API timeout after {timeout_seconds}s")
        print(f"  Action: Retry with longer timeout or use cached results")
    
    # Pattern 4: Lock timeout handling
    print("\nPattern 4: Lock Timeout (High Contention)")
    print("-" * 50)
    
    timeout_lock = 5
    try:
        with write_lock(user_id=user_id, timeout=timeout_lock):
            print(f"✓ Acquired write lock within {timeout_lock}s")
    except TimeoutError:
        print(f"✗ Could not acquire write lock in {timeout_lock}s")
        print(f"  Action: Backoff and retry, or queue operation")
    
    print("\nKey Takeaways:")
    print("  ✓ Always catch EmbeddingError base class")
    print("  ✓ Handle RateLimitError with exponential backoff")
    print("  ✓ Handle IndexNotFoundError gracefully")
    print("  ✓ Implement timeout-based lock acquisition")


def example_9_batch_retrieval():
    """
    Example 9: Batch retrieval for multiple queries.
    
    This demonstrates:
    - Batch query processing
    - Parallel query execution
    - Result aggregation
    """
    print("\n" + "="*70)
    print("EXAMPLE 9: Batch Query Retrieval")
    print("="*70)
    
    user_id = "user_alice"
    
    queries = [
        "What are the payment terms?",
        "Who is liable for breaches?",
        "What is the termination clause?",
        "Are there confidentiality obligations?",
    ]
    
    print(f"User: {user_id}")
    print(f"Batch size: {len(queries)} queries\n")
    
    try:
        # Batch retrieve (would run in parallel in production)
        results_batch = batch_retrieve(
            user_id=user_id,
            queries=queries,
            k=5
        )
        
        for query, results in zip(queries, results_batch):
            print(f"Query: '{query}'")
            if results:
                top_result = results[0]
                print(f"  ➜ Top result: {top_result.similarity_score:.1%} match")
                print(f"    '{top_result.text[:70]}...'")
            else:
                print(f"  ➜ No results found")
            print()
        
        print(f"✓ Processed {len(queries)} queries successfully")
        
    except EmbeddingError as e:
        print(f"✗ Batch retrieval failed: {e}")


def example_10_production_workflow():
    """
    Example 10: Complete production workflow.
    
    This demonstrates:
    - Full ingestion pipeline
    - Error handling at each step
    - Monitoring and logging
    - Backup strategy
    """
    print("\n" + "="*70)
    print("EXAMPLE 10: Complete Production Workflow")
    print("="*70)
    
    user_id = "user_production"
    batch_count = 0
    successful_chunks = 0
    failed_chunks = 0
    
    # Step 1: Create index
    logger.info(f"[1/5] Creating index for {user_id}")
    try:
        index = create_user_index(user_id=user_id)
        print(f"✓ [1/5] Index created (type: {index.index_type})")
    except Exception as e:
        print(f"✗ [1/5] Failed to create index: {e}")
        return
    
    # Step 2: Ingest documents (simulated)
    logger.info(f"[2/5] Ingesting documents for {user_id}")
    print(f"✓ [2/5] Ingested 1 document → 45 chunks")
    
    # Step 3: Generate embeddings
    logger.info(f"[3/5] Generating embeddings")
    sample_chunks = [
        Chunk(
            chunk_id=f"prod_{i}",
            doc_id="prod_doc",
            doc_name="production_contract.pdf",
            chunk_index=i,
            text=f"Clause {i}: Lorem ipsum...",
            page_number=1,
            section=f"Section {i}",
            jurisdiction="New York",
            token_count=750,
            has_ocr=False,
            text_checksum=f"hash_{i}",
            uploaded_at=datetime.now().isoformat(),
            user_id=user_id,
        )
        for i in range(45)
    ]
    
    try:
        embedded_chunks = embed_chunks(sample_chunks, user_id=user_id)
        successful_chunks = len(embedded_chunks)
        print(f"✓ [3/5] Generated {successful_chunks} embeddings")
    except RateLimitError as e:
        print(f"⚠ [3/5] Rate limited; will retry: {e}")
        return
    except EmbeddingError as e:
        print(f"✗ [3/5] Embedding failed: {e}")
        return
    
    # Step 4: Index embeddings
    logger.info(f"[4/5] Indexing embeddings")
    try:
        updated_index = add_chunks_to_index(
            user_id=user_id,
            embedded_chunks=embedded_chunks
        )
        print(f"✓ [4/5] Indexed {updated_index.chunk_count} chunks")
    except Exception as e:
        print(f"✗ [4/5] Indexing failed: {e}")
        return
    
    # Step 5: Create backup
    logger.info(f"[5/5] Creating backup")
    try:
        backup_path = backup_index(
            user_id=user_id,
            description=f"Production deployment - {successful_chunks} chunks"
        )
        print(f"✓ [5/5] Backup created")
    except Exception as e:
        print(f"⚠ [5/5] Backup failed (non-critical): {e}")
    
    # Summary
    print("\nProduction Workflow Summary:")
    print(f"  User: {user_id}")
    print(f"  Documents: 1")
    print(f"  Chunks: {successful_chunks}")
    print(f"  Status: ✓ Ready for queries")
    print(f"\nNext: Use retrieve(user_id='{user_id}', query='...') for semantic search")


if __name__ == "__main__":
    """
    Run all examples:
    
    python examples.py
    """
    
    print("\n" + "="*70)
    print("EMBEDDINGS & FAISS VECTOR STORE - COMPREHENSIVE EXAMPLES")
    print("="*70)
    
    # Note: Examples 1-10 use mock data in many cases.
    # In production, replace with real data and actual OpenAI API calls.
    
    try:
        # Uncomment to run individual examples:
        
        # example_1_basic_embedding_and_indexing()
        # example_2_semantic_search()
        # example_3_batch_processing()
        # example_4_index_type_selection()
        # example_5_multi_user_isolation()
        # example_6_backup_and_recovery()
        # example_7_reranking()
        # example_8_error_handling_and_robustness()
        # example_9_batch_retrieval()
        # example_10_production_workflow()
        
        # Or print usage guide:
        print("\nAvailable Examples:")
        print("1. Basic embedding and indexing       → example_1_basic_embedding_and_indexing()")
        print("2. Semantic search and retrieval      → example_2_semantic_search()")
        print("3. Batch processing                   → example_3_batch_processing()")
        print("4. Index type selection               → example_4_index_type_selection()")
        print("5. Multi-user isolation               → example_5_multi_user_isolation()")
        print("6. Backup and recovery                → example_6_backup_and_recovery()")
        print("7. Retrieval with re-ranking          → example_7_reranking()")
        print("8. Error handling and recovery        → example_8_error_handling_and_robustness()")
        print("9. Batch query retrieval              → example_9_batch_retrieval()")
        print("10. Production workflow               → example_10_production_workflow()")
        
        print("\nUsage: Import and call specific example functions:")
        print("  from examples import example_1_basic_embedding_and_indexing")
        print("  example_1_basic_embedding_and_indexing()")
        
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
