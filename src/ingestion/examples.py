"""
Usage Examples for Document Ingestion & Chunking Module

Real-world scenarios demonstrating the ingestion pipeline.
"""

import logging
from src.ingestion import (
    ingest_document,
    batch_ingest_documents,
    IngestionError,
    IngestionRequest,
)

# Configure logging to see module activity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ============================================================================
# Example 1: Basic Single Document Ingestion
# ============================================================================

def example_basic_ingestion():
    """
    Simplest use case: ingest a single PDF document.
    """
    print("\n" + "="*70)
    print("Example 1: Basic Single Document Ingestion")
    print("="*70)
    
    try:
        # Ingest contract
        chunks = ingest_document(
            file_path="/data/contracts/employment_agreement.pdf",
            user_id="attorney_001"
        )
        
        print(f"✓ Successfully ingested document")
        print(f"  Chunks extracted: {len(chunks)}")
        print(f"  Total tokens: {sum(c.token_count for c in chunks)}")
        
        # Display first chunk
        first_chunk = chunks[0]
        print(f"\nFirst chunk metadata:")
        print(f"  ID: {first_chunk.id}")
        print(f"  Page: {first_chunk.page_number}")
        print(f"  Section: {first_chunk.section}")
        print(f"  Tokens: {first_chunk.token_count}")
        print(f"  Text preview: {first_chunk.text[:100]}...")
        
    except IngestionError as e:
        print(f"✗ Ingestion failed: {e}")


# ============================================================================
# Example 2: Multi-format Batch Processing
# ============================================================================

def example_batch_ingestion():
    """
    Ingest multiple documents in different formats (PDF, DOCX, TXT).
    Non-blocking for failures: processes all files even if some fail.
    """
    print("\n" + "="*70)
    print("Example 2: Multi-format Batch Ingestion")
    print("="*70)
    
    documents = [
        "/data/contracts/nda.pdf",           # PDF
        "/data/templates/agreement.docx",    # DOCX
        "/data/notes/case_summary.txt"       # TXT
    ]
    
    # Ingest all documents
    results = batch_ingest_documents(
        file_paths=documents,
        user_id="paralegal_002",
        jurisdiction="California"
    )
    
    # Summarize results
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    print(f"\nBatch ingestion complete:")
    print(f"  Successful: {len(successful)}/{len(results)}")
    print(f"  Failed: {len(failed)}/{len(results)}")
    
    total_chunks = sum(r.chunk_count for r in successful)
    total_tokens = sum(r.total_tokens for r in successful)
    
    print(f"  Total chunks: {total_chunks}")
    print(f"  Total tokens: {total_tokens}")
    
    # Show individual results
    for result in results:
        if result.success:
            print(f"\n✓ {result.doc_id}")
            print(f"  Chunks: {result.chunk_count}")
            print(f"  Tokens: {result.total_tokens}")
        else:
            print(f"\n✗ Failed: {result.error}")


# ============================================================================
# Example 3: Custom Chunking Parameters
# ============================================================================

def example_custom_chunking():
    """
    Ingest document with custom chunk size and overlap.
    Useful for different use cases:
    - Smaller chunks (500 tokens): For fine-grained retrieval
    - Larger chunks (1000+ tokens): For broader context
    """
    print("\n" + "="*70)
    print("Example 3: Custom Chunking Parameters")
    print("="*70)
    
    # Case 1: Fine-grained chunking (shorter chunks, less overlap)
    print("\nCase A: Fine-grained chunking (500 tokens, 100 overlap)")
    chunks_fine = ingest_document(
        file_path="/data/long_contract.pdf",
        user_id="user_001",
        chunk_size_tokens=500,      # Smaller chunks
        chunk_overlap_tokens=100,   # Less overlap
    )
    print(f"  Chunks: {len(chunks_fine)}")
    print(f"  Avg chunk size: {sum(c.token_count for c in chunks_fine) // len(chunks_fine)} tokens")
    
    # Case 2: Broad context chunking (larger chunks, more overlap)
    print("\nCase B: Broad context (1000+ tokens, 250 overlap)")
    chunks_broad = ingest_document(
        file_path="/data/long_contract.pdf",
        user_id="user_001",
        chunk_size_tokens=1000,     # Larger chunks
        chunk_overlap_tokens=250,   # More overlap
    )
    print(f"  Chunks: {len(chunks_broad)}")
    print(f"  Avg chunk size: {sum(c.token_count for c in chunks_broad) // len(chunks_broad)} tokens")


# ============================================================================
# Example 4: Scanned PDF with OCR
# ============================================================================

def example_ocr_handling():
    """
    Ingest a scanned PDF (image-based).
    Module automatically detects sparse pages and applies OCR.
    """
    print("\n" + "="*70)
    print("Example 4: Scanned PDF with OCR Fallback")
    print("="*70)
    
    try:
        chunks = ingest_document(
            file_path="/data/scanned_documents/old_contract.pdf",
            user_id="user_003",
            enable_ocr=True  # Enable OCR for scanned pages
        )
        
        # Check which chunks used OCR
        ocr_chunks = [c for c in chunks if c.has_ocr]
        native_chunks = [c for c in chunks if not c.has_ocr]
        
        print(f"Processed scanned PDF:")
        print(f"  Total chunks: {len(chunks)}")
        print(f"  Native text: {len(native_chunks)} chunks")
        print(f"  OCR-extracted: {len(ocr_chunks)} chunks")
        
        if ocr_chunks:
            print(f"\nOCR chunks:")
            for chunk in ocr_chunks[:3]:
                print(f"  - Chunk {chunk.chunk_index} (page {chunk.page_number})")
        
    except IngestionError as e:
        print(f"✗ OCR processing failed: {e}")
        print("  Ensure tesseract-ocr is installed:")
        print("    Linux: sudo apt-get install tesseract-ocr")
        print("    macOS: brew install tesseract")
        print("    Windows: Download from GitHub (see README)")


# ============================================================================
# Example 5: Jurisdiction-aware Processing
# ============================================================================

def example_jurisdiction_metadata():
    """
    Ingest documents with jurisdiction information.
    Useful for legal systems with jurisdiction-specific handling.
    """
    print("\n" + "="*70)
    print("Example 5: Jurisdiction-aware Metadata")
    print("="*70)
    
    # Process documents from different jurisdictions
    jurisdictions = {
        "/data/contracts/ca_agreement.pdf": "California",
        "/data/contracts/ny_agreement.pdf": "New York",
        "/data/contracts/tx_agreement.pdf": "Texas",
        "/data/contracts/federal_agreement.pdf": "Federal",
    }
    
    for file_path, jurisdiction in jurisdictions.items():
        try:
            chunks = ingest_document(
                file_path=file_path,
                user_id="legal_team",
                jurisdiction=jurisdiction,
            )
            
            # Verify jurisdiction in chunks
            assert all(c.jurisdiction == jurisdiction for c in chunks)
            
            print(f"✓ {jurisdiction}: {len(chunks)} chunks")
            
        except (IngestionError, FileNotFoundError):
            print(f"✗ {jurisdiction}: Not found (skipping)")


# ============================================================================
# Example 6: Custom Metadata Tagging
# ============================================================================

def example_custom_metadata():
    """
    Ingest document with custom metadata for application context.
    Useful for tracking document source, case ID, etc.
    """
    print("\n" + "="*70)
    print("Example 6: Custom Metadata Tagging")
    print("="*70)
    
    chunks = ingest_document(
        file_path="/data/cases/2026_001_complaint.pdf",
        user_id="attorney_004",
        jurisdiction="California",
        custom_metadata={
            "case_id": "2026_001",
            "case_type": "Contract Dispute",
            "department": "Litigation",
            "year_filed": 2026,
            "opposing_counsel": "Smith & Associates",
            "priority": "High",
        }
    )
    
    print(f"Ingested case document with custom metadata:")
    print(f"  Chunks: {len(chunks)}")
    
    first_chunk = chunks[0]
    print(f"\nChunk metadata:")
    print(f"  Doc ID: {first_chunk.doc_id}")
    print(f"  uploaded: {first_chunk.upload_timestamp}")
    print(f"  User: {first_chunk.user_id}")
    print(f"  Jurisdiction: {first_chunk.jurisdiction}")
    
    # Custom metadata stored in request but accessible through context
    print(f"\nNote: Custom metadata can be tracked via:")
    print(f"  - doc_id: All chunks of same document share doc_id")
    print(f"  - user_id: Chunks linked to uploading user")
    print(f"  - upload_timestamp: Batch ingestion timestamp")


# ============================================================================
# Example 7: Error Handling and Recovery
# ============================================================================

def example_error_handling():
    """
    Demonstrate error handling for various failure scenarios.
    """
    print("\n" + "="*70)
    print("Example 7: Error Handling & Recovery")
    print("="*70)
    
    test_cases = [
        ("/nonexistent/file.pdf", "Non-existent file"),
        ("/data/empty.txt", "Empty file"),
        ("/data/corrupt.pdf", "Corrupted PDF"),
        ("/data/file.exe", "Unsupported file type"),
        ("/data/image.jpg", "Image file (unsupported)"),
    ]
    
    for file_path, description in test_cases:
        print(f"\nTesting: {description}")
        try:
            chunks = ingest_document(file_path, "user_test")
            print(f"  ✓ Unexpectedly succeeded")
        except FileNotFoundError as e:
            print(f"  ✗ File error: {str(e)[:50]}...")
        except IngestionError as e:
            print(f"  ✗ Ingestion error: {str(e)[:50]}...")
        except Exception as e:
            print(f"  ✗ Unexpected error: {type(e).__name__}: {str(e)[:50]}...")


# ============================================================================
# Example 8: Chunk Serialization and Export
# ============================================================================

def example_chunk_export():
    """
    Export chunks to JSON for downstream processing (embedding, storage).
    """
    print("\n" + "="*70)
    print("Example 8: Chunk Serialization & Export")
    print("="*70)
    
    chunks = ingest_document(
        file_path="/data/sample.pdf",
        user_id="user_005"
    )
    
    # Export to JSON (per-chunk)
    print(f"Exporting {len(chunks)} chunks...")
    
    json_chunks = [chunk.model_dump_json() for chunk in chunks]
    print(f"  ✓ Serialized to JSON")
    
    # Example: Send to embedding service
    print(f"\nExample: Sending to embedding service")
    for i, chunk in enumerate(chunks[:3]):
        print(f"  {i+1}. {chunk.doc_name} [{chunk.chunk_index}]")
        print(f"     Text: {chunk.text[:60]}...")
        print(f"     Tokens: {chunk.token_count}")
        print(f"     Ready for embedding: {len(chunk.text) > 0}")


# ============================================================================
# Example 9: Large Document Processing (Performance)
# ============================================================================

def example_large_document():
    """
    Ingest a very large document and monitor performance.
    """
    print("\n" + "="*70)
    print("Example 9: Large Document Processing")
    print("="*70)
    
    try:
        import time
        
        start = time.time()
        chunks = ingest_document(
            file_path="/data/large_regulations.pdf",  # 500+ pages
            user_id="user_006",
        )
        elapsed = time.time() - start
        
        total_tokens = sum(c.token_count for c in chunks)
        avg_chunk = total_tokens / len(chunks) if chunks else 0
        
        print(f"Large document processing:")
        print(f"  Pages: {chunks[0].page_number if chunks and chunks[-1].page_number else '?'}")
        print(f"  Chunks: {len(chunks)}")
        print(f"  Total tokens: {total_tokens}")
        print(f"  Avg tokens/chunk: {avg_chunk:.0f}")
        print(f"  Processing time: {elapsed:.2f}s")
        print(f"  Throughput: {total_tokens/elapsed:.0f} tokens/sec")
        
    except (IngestionError, FileNotFoundError):
        print("  Large test file not available (skipping)")


# ============================================================================
# Main: Run All Examples
# ============================================================================

if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# Document Ingestion & Chunking Module — Usage Examples")
    print("#"*70)
    
    examples = [
        ("Basic Ingestion", example_basic_ingestion),
        ("Batch Processing", example_batch_ingestion),
        ("Custom Chunking", example_custom_chunking),
        ("OCR Handling", example_ocr_handling),
        ("Jurisdiction Metadata", example_jurisdiction_metadata),
        ("Custom Metadata", example_custom_metadata),
        ("Error Handling", example_error_handling),
        ("Chunk Export", example_chunk_export),
        ("Large Documents", example_large_document),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    # Run a specific example by uncommenting:
    # example_basic_ingestion()
    # example_batch_ingestion()
    # example_custom_chunking()
    # example_ocr_handling()
    # example_jurisdiction_metadata()
    # example_custom_metadata()
    # example_error_handling()
    # example_chunk_export()
    # example_large_document()
    
    # Or run all (uncomment):
    # for name, example_func in examples:
    #     try:
    #         example_func()
    #     except Exception as e:
    #         print(f"\nError in {name}: {e}")
