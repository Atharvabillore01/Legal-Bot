# FastAPI Layer & Multi-User Auth Specification

**Legal RAG System | Module 5**

Professional API layer with JWT authentication, multi-user document isolation, rate limiting, and audit logging.

**Version**: 1.0.0  
**Author**: API Architecture Team  
**Date**: 2024-01-15  
**Status**: Final Specification

---

## Table of Contents

1. [Overview & Design Goals](#overview--design-goals)
2. [Architecture Diagram](#architecture-diagram)
3. [Authentication & JWT](#authentication--jwt)
4. [API Endpoints](#api-endpoints)
5. [Pydantic Request/Response Models](#pydantic-requestresponse-models)
6. [Error Response Format](#error-response-format)
7. [Rate Limiting Strategy](#rate-limiting-strategy)
8. [Multi-User Isolation](#multi-user-isolation)
9. [Audit Logging](#audit-logging)
10. [Security Rules & Constraints](#security-rules--constraints)
11. [Database Schema](#database-schema)
12. [Middleware Design](#middleware-design)
13. [Full JSON Examples](#full-json-examples)
14. [Authentication Flow Diagram](#authentication-flow-diagram)
15. [Deployment Configuration](#deployment-configuration)
16. [Performance & SLAs](#performance--slas)

---

## 1. Overview & Design Goals

### Purpose

Provide a secure, multi-tenant REST API for a legal document RAG system. Enable users to:
- Upload and ingest legal documents (PDF, DOCX, TXT)
- Query documents with AI-powered semantic search
- Retrieve paginated, cited answers with confidence scores
- View audit trails of their activities
- Manage document lifecycle (upload, delete)

### Design Principles

1. **Stateless** - All requests self-contained, no session state
2. **Multi-tenant** - Complete isolation between users, enforced at every layer
3. **Secure** - JWT with expiring tokens, HTTPS enforcement, rate limiting
4. **Auditable** - All queries and document operations logged
5. **Performant** - Sub-1s response times for most operations
6. **Resilient** - Graceful error handling, exponential backoff for retries

### Technology Stack

- **Framework**: FastAPI v0.104+ (async Python web framework)
- **Authentication**: PyJWT for JWT token creation/verification
- **Database**: PostgreSQL for metadata, audit logs, users
- **Redis**: Rate limiting and token blacklist (optional)
- **Async**: asyncio + aiofiles for non-blocking I/O
- **Validation**: Pydantic v2 for request/response schemas
- **Logging**: Python logging with structured JSON output

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATIONS                      │
│                    (Desktop, Web, Mobile)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LOAD BALANCER / GATEWAY                     │
│              (Optional: Cloud CDN, Rate Limiting)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/2
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI APPLICATION                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            MIDDLEWARE STACK                             │   │
│  │  ✓ CORS Handling                                        │   │
│  │  ✓ JWT Verification                                    │   │
│  │  ✓ Rate Limiting (Redis)                               │   │
│  │  ✓ Request Logging                                     │   │
│  │  ✓ Error Handling                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                      │
│        ┌──────────────────┼──────────────────┐                 │
│        ▼                  ▼                  ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   /ingest    │  │   /query     │  │ /audit-log   │        │
│  │   Endpoint   │  │  Endpoint    │  │  Endpoint    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│        │                  │                  │                 │
│        └──────────────────┼──────────────────┘                 │
│                           │                                      │
│                  ┌────────▼────────┐                           │
│                  │  SERVICE LAYER  │                           │
│                  │                 │                           │
│                  │ ✓ Ingestion     │                           │
│                  │ ✓ Retrieval     │                           │
│                  │ ✓ LLM Query     │                           │
│                  │ ✓ Document Mgmt │                           │
│                  └────────┬────────┘                           │
│                           │                                      │
└───────────────────────────┼──────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
    ┌─────────┐         ┌─────────┐      ┌────────┐
    │PostgreSQL│        │  Redis  │      │  S3 /  │
    │(Metadata,│        │(Tokens, │      │ Storage│
    │ Users,   │        │ Rate    │      │        │
    │ Audit)   │        │ Limits) │      │        │
    └─────────┘        └─────────┘      └────────┘
         ▼                  ▼
    ┌─────────────────────────────┐
    │   MODULES 1-4 BACKEND       │
    │ (Ingestion → LLM Response)  │
    └─────────────────────────────┘
```

---

## 3. Authentication & JWT

### JWT Token Structure

#### Access Token (24-hour expiry)

```json
{
  "sub": "user_123",
  "user_id": "user_123",
  "email": "user@example.com",
  "iat": 1705276800,
  "exp": 1705363200,
  "token_type": "access"
}
```

#### Refresh Token (7-day expiry)

```json
{
  "sub": "user_123",
  "user_id": "user_123",
  "iat": 1705276800,
  "exp": 1705881600,
  "token_type": "refresh",
  "jti": "unique-token-id-uuid"
}
```

### Token Generation & Verification

#### Token Claims

| Claim | Type | Description | Example |
|-------|------|-------------|---------|
| `sub` | str | Subject (user identifier) | `user_123` |
| `user_id` | str | User UUID | `user_123` |
| `email` | str | User email address | `user@example.com` |
| `iat` | int | Issued at (Unix timestamp) | `1705276800` |
| `exp` | int | Expiration (Unix timestamp) | `1705363200` |
| `token_type` | str | `access` or `refresh` | `access` |
| `jti` | str | JWT ID (refresh only) | `uuid-string` |

#### Key Parameters

```
ACCESS_TOKEN_EXPIRY = 24 * 60 * 60  # 24 hours (86400 seconds)
REFRESH_TOKEN_EXPIRY = 7 * 24 * 60 * 60  # 7 days (604800 seconds)
JWT_ALGORITHM = "HS256"  # HMAC with SHA-256
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Must be ≥32 bytes
JWT_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY")  # Separate key
```

### Token Lifecycle

1. **Login**: User provides username/password → validate → generate access + refresh tokens
2. **Access**: Include access token in `Authorization: Bearer <token>` header
3. **Refresh**: Access token expires → client submits refresh token → receive new access token
4. **Logout**: Add refresh token to blacklist (Redis set, expires at token expiry time)
5. **Revoke**: Admin can revoke all tokens for a user (clear all JTI entries)

### Middleware: JWT Verification

```python
async def verify_jwt_middleware(request: Request, call_next):
    """
    Extract, verify, and inject JWT into request context.
    
    Flow:
    1. Extract token from Authorization header
    2. Verify signature using JWT_SECRET_KEY
    3. Check expiration
    4. Check blacklist (Redis)
    5. Inject user_id into request.state
    6. Continue to route handler
    
    Error Cases:
    - Missing header → 401 Unauthorized
    - Invalid signature → 401 Unauthorized
    - Expired token → 401 Unauthorized
    - Blacklisted token → 401 Unauthorized
    """
    pass
```

---

## 4. API Endpoints

### Endpoint Summary Table

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|-----------|
| **POST** | `/auth/login` | Login, get access + refresh tokens | No | 10/min |
| **POST** | `/auth/refresh` | Refresh access token | Refresh token | 10/min |
| **POST** | `/auth/logout` | Logout, blacklist refresh token | Yes | Unlimited |
| **POST** | `/ingest` | Upload and ingest document | Yes | 20/hour |
| **GET** | `/query` | Submit query, get cited answer | Yes | 100/hour |
| **GET** | `/audit-log` | Retrieve paginated audit log | Yes | 30/hour |
| **GET** | `/users/{user_id}/documents` | List user's documents | Yes | 20/hour |
| **DELETE** | `/users/{user_id}/documents/{doc_id}` | Delete document | Yes | 50/hour |
| **GET** | `/health` | Health check | No | Unlimited |

### Endpoint Details

#### 1. POST /auth/login

**Purpose**: Authenticate user and issue tokens

**Request Schema**:
```json
{
  "email": "user@example.com",
  "password": "secure_password_123"
}
```

**Response Schema (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "user_id": "user_123",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

**Error Codes**:
- `400 Bad Request` - Invalid email/password format
- `401 Unauthorized` - Invalid credentials
- `429 Too Many Requests` - Rate limit exceeded (10/min)

**Implementation Notes**:
- Hash passwords with bcrypt (cost=12)
- Store password hash only (never plain text)
- Check account is active/not suspended
- Log successful login with timestamp

---

#### 2. POST /auth/refresh

**Purpose**: Issue new access token using refresh token

**Request Schema**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response Schema (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Error Codes**:
- `401 Unauthorized` - Invalid/expired refresh token
- `401 Unauthorized` - Token blacklisted (user logged out)
- `429 Too Many Requests` - Rate limit exceeded

**Implementation Notes**:
- Check refresh token hasn't been blacklisted
- Verify signature against REFRESH_SECRET_KEY
- Issue NEW access token (don't return old one)
- Log token refresh for audit trail

---

#### 3. POST /auth/logout

**Purpose**: Invalidate tokens (blacklist them)

**Request Schema**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response Schema (200 OK)**:
```json
{
  "message": "Successfully logged out",
  "timestamp": "2024-01-15T10:30:45Z"
}
```

**Error Codes**:
- `401 Unauthorized` - No valid access token in header
- `400 Bad Request` - Missing refresh token in body

**Implementation Notes**:
- Add both access + refresh tokens to blacklist (Redis)
- Blacklist entries expire after token expiry (automatic cleanup)
- Log logout event with user_id and timestamp

---

#### 4. POST /ingest

**Purpose**: Upload and ingest a legal document

**Request Schema** (multipart/form-data):
```
file: <binary PDF/DOCX/TXT>
doc_name: "indemnity_agreement.pdf" (optional, defaults to filename)
jurisdiction: "NY" (optional)
```

**Response Schema (202 Accepted)**:
```json
{
  "request_id": "ingest_req_xyz123",
  "doc_id": "doc_550e8400",
  "doc_name": "indemnity_agreement.pdf",
  "status": "processing",
  "chunks_count": 27,
  "estimated_completion_time_seconds": 45,
  "message": "Document ingestion started. Query status with request_id."
}
```

**Error Codes**:
- `400 Bad Request` - No file provided, or invalid file format
- `413 Payload Too Large` - File exceeds 100MB limit
- `401 Unauthorized` - Invalid/missing access token
- `429 Too Many Requests` - Rate limit exceeded (20/hour per user)

**Implementation Notes**:
- Store file in S3/object storage with user_id prefix: `s3://documents/{user_id}/{doc_id}/original.pdf`
- Generate unique doc_id (UUID)
- Queue ingestion task to async worker (Module 1)
- Return 202 immediately (asynchronous processing)
- Store metadata in PostgreSQL (`documents` table)
- Log ingestion request with user_id, doc_name, file size

**Asynchronous Processing**:
```
User submits file
    ↓
FastAPI validates + stores in S3 + returns 202 + request_id
    ↓
Background worker (Module 1) reads from S3, ingests chunks, embeds (Module 2)
    ↓
Worker updates document status to 'ready' in PostgreSQL
    ↓
User can now query (status check endpoint via request_id)
```

---

#### 5. GET /query

**Purpose**: Submit legal question, retrieve cited answer

**Query Parameters**:
- `query` (required): User's legal question (string, max 2000 chars)
- `k` (optional): Number of chunks to retrieve (default: 7, max: 50)
- `jurisdiction` (optional): Filter by jurisdiction (e.g., "NY")
- `doc_name` (optional): Filter by document name

**Example Request**:
```
GET /query?query=What%20is%20the%20liability%20cap?&k=5&jurisdiction=NY
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response Schema (200 OK)**:
```json
{
  "query_id": "query_550e8400",
  "query": "What is the liability cap?",
  "answer": "The liability cap is USD 5,000,000 per occurrence (Source: indemnity_agreement.pdf, p.7).",
  "citations": [
    {
      "chunk_id": "chunk_15",
      "source_doc": "indemnity_agreement.pdf",
      "page_number": 7,
      "text_excerpt": "The liability cap in Section 10 is USD 5,000,000 per occurrence.",
      "character_offset": {"start": 234, "end": 289},
      "jurisdiction": "NY",
      "section": "Limitations of Liability"
    },
    {
      "chunk_id": "chunk_23",
      "source_doc": "indemnity_agreement.pdf",
      "page_number": 12,
      "text_excerpt": "Total liability shall not exceed USD 5,000,000 annually.",
      "character_offset": {"start": 456, "end": 512},
      "jurisdiction": "NY",
      "section": "General Provisions"
    }
  ],
  "confidence": {
    "score": 0.92,
    "level": "HIGH",
    "interpretation": "High confidence - answer is well-supported by sources"
  },
  "timing": {
    "search_time_ms": 245,
    "llm_time_ms": 1320,
    "total_time_ms": 1565
  },
  "metadata": {
    "chunks_searched": 27,
    "chunks_used": 2,
    "model": "gpt-4o",
    "timestamp": "2024-01-15T10:30:45Z"
  }
}
```

**Error Codes**:
- `400 Bad Request` - Missing query parameter or query too long
- `401 Unauthorized` - Invalid/missing access token
- `404 Not Found` - User has no documents (empty FAISS index)
- `422 Unprocessable Entity` - Invalid filter options (jurisdiction, etc.)
- `429 Too Many Requests` - Rate limit exceeded (100/hour per user)
- `503 Service Unavailable` - Modules 2-4 unavailable

**Implementation Notes**:
- All queries isolated to user's FAISS index (user_id-specific)
- Apply jurisdiction/doc_name filters before retrieval
- Measure timing for search + LLM separately
- Log query with user_id, timestamp, confidence level
- Store query in audit_log table
- Return confidence level (LOW/MEDIUM/HIGH) from Module 4

---

#### 6. GET /audit-log

**Purpose**: Retrieve paginated audit log filtered by date, document, query

**Query Parameters**:
- `page` (optional): Page number (default: 1, min: 1)
- `page_size` (optional): Results per page (default: 20, max: 100)
- `start_date` (optional): ISO 8601 date (e.g., 2024-01-01)
- `end_date` (optional): ISO 8601 date (e.g., 2024-01-31)
- `action_type` (optional): Filter by action (ingest, query, delete)
- `doc_name` (optional): Filter by document name
- `status` (optional): Filter by status (success, error)

**Example Request**:
```
GET /audit-log?page=1&page_size=20&action_type=query&start_date=2024-01-01&end_date=2024-01-15
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response Schema (200 OK)**:
```json
{
  "page": 1,
  "page_size": 20,
  "total_count": 147,
  "total_pages": 8,
  "records": [
    {
      "log_id": "log_550e8400",
      "user_id": "user_123",
      "action_type": "query",
      "action_description": "Legal query submitted",
      "doc_name": "indemnity_agreement.pdf",
      "query_text": "What is the liability cap?",
      "status": "success",
      "confidence_level": "HIGH",
      "response_time_ms": 1565,
      "error_message": null,
      "timestamp": "2024-01-15T10:30:45Z",
      "ip_address": "203.0.113.42",
      "request_id": "query_550e8400"
    },
    {
      "log_id": "log_550e8401",
      "user_id": "user_123",
      "action_type": "ingest",
      "action_description": "Document uploaded and ingested",
      "doc_name": "payment_terms.pdf",
      "query_text": null,
      "status": "success",
      "confidence_level": null,
      "response_time_ms": 24530,
      "error_message": null,
      "timestamp": "2024-01-15T09:15:20Z",
      "ip_address": "203.0.113.42",
      "request_id": "ingest_req_xyz123"
    },
    {
      "log_id": "log_550e8402",
      "user_id": "user_123",
      "action_type": "query",
      "action_description": "Legal query submitted",
      "doc_name": null,
      "query_text": "Payment terms?",
      "status": "error",
      "confidence_level": null,
      "response_time_ms": 45,
      "error_message": "No documents available for query",
      "timestamp": "2024-01-15T08:00:30Z",
      "ip_address": "203.0.113.42",
      "request_id": "query_550e8402"
    }
  ],
  "filters_applied": {
    "action_type": "query",
    "start_date": "2024-01-01",
    "end_date": "2024-01-15"
  }
}
```

**Error Codes**:
- `400 Bad Request` - Invalid date format or page number
- `401 Unauthorized` - Invalid/missing access token
- `422 Unprocessable Entity` - Invalid action_type or status

**Implementation Notes**:
- Users can only see their own audit logs (enforced in WHERE clause)
- Default sort: descending by timestamp (newest first)
- No personally identifiable information (PII) logged except email
- Query text truncated to 500 chars for storage
- IP address logged for security audit
- Action types: ingest, query, delete, login, logout
- Statuses: success, error, in_progress

---

#### 7. GET /users/{user_id}/documents

**Purpose**: List user's ingested documents with metadata

**Path Parameters**:
- `user_id` (required): User UUID

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 20, max: 100)
- `status` (optional): Filter by status (processing, ready, error)
- `sort_by` (optional): Sort field (name, upload_date, size)

**Example Request**:
```
GET /users/user_123/documents?page=1&page_size=20&status=ready
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response Schema (200 OK)**:
```json
{
  "page": 1,
  "page_size": 20,
  "total_count": 5,
  "total_pages": 1,
  "documents": [
    {
      "doc_id": "doc_550e8400",
      "doc_name": "indemnity_agreement.pdf",
      "doc_type": "PDF",
      "jurisdiction": "NY",
      "upload_timestamp": "2024-01-10T14:30:00Z",
      "ingestion_timestamp": "2024-01-10T14:31:30Z",
      "status": "ready",
      "file_size_bytes": 1245632,
      "chunks_count": 27,
      "error_message": null
    },
    {
      "doc_id": "doc_550e8401",
      "doc_name": "payment_terms.pdf",
      "doc_type": "PDF",
      "jurisdiction": "CA",
      "upload_timestamp": "2024-01-09T10:15:00Z",
      "ingestion_timestamp": "2024-01-09T10:16:45Z",
      "status": "ready",
      "file_size_bytes": 856921,
      "chunks_count": 19,
      "error_message": null
    },
    {
      "doc_id": "doc_550e8402",
      "doc_name": "terms_of_service.docx",
      "doc_type": "DOCX",
      "jurisdiction": "TX",
      "upload_timestamp": "2024-01-08T09:00:00Z",
      "ingestion_timestamp": "2024-01-08T09:02:20Z",
      "status": "ready",
      "file_size_bytes": 524288,
      "chunks_count": 12,
      "error_message": null
    }
  ]
}
```

**Error Codes**:
- `401 Unauthorized` - Invalid/missing access token
- `403 Forbidden` - Trying to access another user's documents
- `404 Not Found` - User ID does not exist
- `400 Bad Request` - Invalid pagination parameters

**Implementation Notes**:
- Enforce user isolation: user_id from JWT must match path param
- Only return documents owned by authenticated user
- Status values: processing, ready, error
- Calculate total_size_bytes across all documents
- Return S3 object URLs (signed URLs, 1-hour expiry)

---

#### 8. DELETE /users/{user_id}/documents/{doc_id}

**Purpose**: Delete document and remove FAISS vectors

**Path Parameters**:
- `user_id` (required): User UUID
- `doc_id` (required): Document UUID

**Request Schema**: (empty body)

**Response Schema (200 OK)**:
```json
{
  "message": "Document successfully deleted",
  "doc_id": "doc_550e8400",
  "doc_name": "indemnity_agreement.pdf",
  "removed_chunks_count": 27,
  "timestamp": "2024-01-15T10:35:00Z"
}
```

**Error Codes**:
- `401 Unauthorized` - Invalid/missing access token
- `403 Forbidden` - Trying to delete another user's document
- `404 Not Found` - Document does not exist
- `409 Conflict` - Document currently being processed (retry after)

**Implementation Notes**:
- Enforce user isolation: user_id from JWT must match path param
- Delete document metadata from PostgreSQL (documents table)
- Delete document file from S3 (async background task)
- Call Module 2 to remove FAISS vectors (user_id-specific index)
- Log deletion with user_id and doc_id
- Audit trail entry created immediately
- Cannot delete documents in "processing" state

---

#### 9. GET /health

**Purpose**: Health check for load balancers / monitoring

**Request**: (no parameters)

**Response Schema (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:35:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "services": {
    "database": "connected",
    "redis": "connected",
    "module_1": "available",
    "module_2": "available",
    "module_3": "available",
    "module_4": "available"
  }
}
```

**Response Schema (503 Service Unavailable)**:
```json
{
  "status": "unhealthy",
  "timestamp": "2024-01-15T10:35:00Z",
  "version": "1.0.0",
  "issue": "Database connection failed",
  "services": {
    "database": "disconnected",
    "redis": "connected",
    "module_1": "unavailable",
    "module_2": "available",
    "module_3": "available",
    "module_4": "available"
  }
}
```

**Implementation Notes**:
- No authentication required
- Check database connectivity
- Check Redis connectivity
- Check internal service health (Modules 1-4)
- Return current uptime
- Used by Kubernetes liveness/readiness probes

---

## 5. Pydantic Request/Response Models

### Authentication Models

```python
class LoginRequest(BaseModel):
    """Login request with email and password."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=256, description="Password")

class TokenResponse(BaseModel):
    """Token response with access and refresh tokens."""
    access_token: str = Field(..., description="Access token (24h expiry)")
    refresh_token: str = Field(..., description="Refresh token (7d expiry)")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry (seconds)")

class UserResponse(BaseModel):
    """User profile in token response."""
    user_id: str = Field(..., description="User UUID")
    email: EmailStr = Field(..., description="User email")
    name: str = Field(..., description="User full name")

class LoginResponse(BaseModel):
    """Complete login response."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse

class RefreshRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., description="Refresh token")

class LogoutRequest(BaseModel):
    """Logout request."""
    refresh_token: str = Field(..., description="Refresh token to blacklist")

class LogoutResponse(BaseModel):
    """Logout response."""
    message: str = Field(..., description="Logout confirmation")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Document & Query Models

```python
class IngestRequest(BaseModel):
    """Document ingestion request (multipart/form-data)."""
    file: UploadFile = Field(..., description="Document file (PDF/DOCX/TXT)")
    doc_name: Optional[str] = Field(None, max_length=255, description="Document name")
    jurisdiction: Optional[str] = Field(None, max_length=50, description="Jurisdiction")

class IngestResponse(BaseModel):
    """Document ingestion response."""
    request_id: str = Field(..., description="Ingest request ID")
    doc_id: str = Field(..., description="Document ID")
    doc_name: str = Field(..., description="Document name")
    status: str = Field(..., description="Status: processing, ready, error")
    chunks_count: int = Field(..., ge=1, description="Number of chunks")
    estimated_completion_time_seconds: int = Field(..., ge=1)
    message: str = Field(..., description="Status message")

class CitationResponse(BaseModel):
    """Citation object."""
    chunk_id: str = Field(..., description="Chunk reference ID")
    source_doc: str = Field(..., description="Source document name")
    page_number: int = Field(..., ge=1, description="Page number")
    text_excerpt: str = Field(..., max_length=500, description="Cited text")
    character_offset: Dict[str, int] = Field(..., description={"start": int, "end": int})
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction")
    section: Optional[str] = Field(None, description="Document section")

class ConfidenceResponse(BaseModel):
    """Confidence information."""
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence [0,1]")
    level: str = Field(..., description="LOW, MEDIUM, or HIGH")
    interpretation: str = Field(..., description="Human-readable interpretation")

class TimingResponse(BaseModel):
    """Response timing breakdown."""
    search_time_ms: float = Field(..., ge=0, description="Retrieval time")
    llm_time_ms: float = Field(..., ge=0, description="LLM call time")
    total_time_ms: float = Field(..., ge=0, description="Total time")

class QueryResponse(BaseModel):
    """Query response with cited answer."""
    query_id: str = Field(..., description="Query ID")
    query: str = Field(..., description="User's question")
    answer: str = Field(..., description="LLM-generated answer")
    citations: List[CitationResponse] = Field(..., description="Source citations")
    confidence: ConfidenceResponse = Field(..., description="Confidence information")
    timing: TimingResponse = Field(..., description="Timing breakdown")
    metadata: Dict[str, Any] = Field(..., description="Additional metadata")

class DocumentResponse(BaseModel):
    """Document metadata."""
    doc_id: str = Field(..., description="Document ID")
    doc_name: str = Field(..., description="Document name")
    doc_type: str = Field(..., description="PDF, DOCX, or TXT")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction")
    upload_timestamp: datetime = Field(..., description="Upload timestamp")
    ingestion_timestamp: Optional[datetime] = Field(None, description="Ingestion completion time")
    status: str = Field(..., description="processing, ready, or error")
    file_size_bytes: int = Field(..., ge=0, description="File size")
    chunks_count: int = Field(..., ge=0, description="Number of chunks")
    error_message: Optional[str] = Field(None, description="Error details if status=error")

class DocumentListResponse(BaseModel):
    """Paginated document list."""
    page: int = Field(..., ge=1, description="Current page")
    page_size: int = Field(..., ge=1, le=100, description="Results per page")
    total_count: int = Field(..., ge=0, description="Total documents")
    total_pages: int = Field(..., ge=1, description="Total pages")
    documents: List[DocumentResponse] = Field(..., description="Documents on this page")

class AuditLogRecord(BaseModel):
    """Single audit log entry."""
    log_id: str = Field(..., description="Log entry ID")
    user_id: str = Field(..., description="User UUID")
    action_type: str = Field(..., description="ingest, query, delete, login, logout")
    action_description: str = Field(..., description="Human-readable action")
    doc_name: Optional[str] = Field(None, description="Document name")
    query_text: Optional[str] = Field(None, max_length=500, description="Query (truncated)")
    status: str = Field(..., description="success or error")
    confidence_level: Optional[str] = Field(None, description="HIGH, MEDIUM, LOW")
    response_time_ms: int = Field(..., ge=0, description="Response time")
    error_message: Optional[str] = Field(None, description="Error details if status=error")
    timestamp: datetime = Field(..., description="Timestamp")
    ip_address: str = Field(..., description="Client IP address")
    request_id: str = Field(..., description="Request/trace ID")

class AuditLogResponse(BaseModel):
    """Paginated audit log."""
    page: int = Field(..., ge=1, description="Current page")
    page_size: int = Field(..., ge=1, le=100, description="Results per page")
    total_count: int = Field(..., ge=0, description="Total entries")
    total_pages: int = Field(..., ge=1, description="Total pages")
    records: List[AuditLogRecord] = Field(..., description="Audit log entries")
    filters_applied: Dict[str, Any] = Field(..., description="Active filters")
```

---

## 6. Error Response Format

### Standard Error Response

All errors use this format:

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Invalid or expired access token",
    "details": {
      "expected": "valid JWT token",
      "actual": "expired token"
    }
  },
  "request_id": "req_550e8400",
  "timestamp": "2024-01-15T10:35:00Z",
  "path": "/query",
  "method": "GET"
}
```

### Pydantic Model

```python
class ErrorDetail(BaseModel):
    """Error details."""
    code: str = Field(..., description="Error code (machine-readable)")
    message: str = Field(..., description="Error message (human-readable)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: ErrorDetail = Field(..., description="Error information")
    request_id: str = Field(..., description="Request trace ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    path: str = Field(..., description="API path")
    method: str = Field(..., description="HTTP method")
```

### Error Code Reference

| Code | HTTP | Description | Recovery |
|------|------|-------------|----------|
| `INVALID_TOKEN` | 401 | Token missing, invalid, or expired | Login again, use refresh token |
| `EXPIRED_TOKEN` | 401 | Access token expired | Use refresh token to get new access token |
| `BLACKLISTED_TOKEN` | 401 | Token was blacklisted (user logged out) | Login again |
| `INVALID_CREDENTIALS` | 401 | Email or password incorrect | Check credentials and retry |
| `ACCOUNT_DISABLED` | 403 | User account is suspended | Contact support |
| `PERMISSION_DENIED` | 403 | Accessing another user's resources | Use correct user_id |
| `NOT_FOUND` | 404 | Resource not found | Check ID and retry |
| `INVALID_REQUEST` | 400 | Request validation failed | Check request schema |
| `FILE_TOO_LARGE` | 413 | File exceeds max size (100MB) | Upload smaller file |
| `UNSUPPORTED_FILE_TYPE` | 400 | File type not supported (need PDF/DOCX/TXT) | Upload PDF, DOCX, or TXT |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Wait and retry (exponential backoff) |
| `SERVICE_UNAVAILABLE` | 503 | Backend modules not responding | Retry after delay |
| `INTERNAL_ERROR` | 500 | Unexpected server error | Contact support, reference request_id |

---

## 7. Rate Limiting Strategy

### Per-Endpoint Limits

| Endpoint | Limit | Window | Description |
|----------|-------|--------|-------------|
| `/auth/login` | 10 | 1 minute | Prevent brute force attacks |
| `/auth/refresh` | 10 | 1 minute | Prevent token abuse |
| `/ingest` | 20 | 1 hour | Prevent storage exhaustion |
| `/query` | 100 | 1 hour | Main limit for queries |
| `/audit-log` | 30 | 1 hour | Prevent log spam |
| `/users/{user_id}/documents` | 20 | 1 hour | Prevent enumeration |
| `DELETE /documents/{doc_id}` | 50 | 1 hour | Prevent mass deletion |

### Implementation Strategy

#### Redis-Based Rate Limiter

```python
async def rate_limit_middleware(request: Request, user_id: Optional[str], endpoint: str):
    """
    Rate limit enforcement using Redis.
    
    Key format: rate_limit:{endpoint}:{user_id}:{window_start}
    
    Flow:
    1. Get current timestamp
    2. Calculate window start (rounded to minute/hour)
    3. Generate Redis key
    4. Increment counter (INCR with TTL)
    5. Check if counter exceeds limit
    6. Return 429 if exceeded, or add Rate-Limit headers
    
    Headers:
    - X-RateLimit-Limit: Per-endpoint limit
    - X-RateLimit-Remaining: Requests remaining in window
    - X-RateLimit-Reset: Unix timestamp when window resets
    """
    pass
```

#### Rate Limit Response Headers

Every response includes:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705318800
```

#### 429 Response on Limit Exceeded

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. You've exceeded the rate limit of 100 queries per hour.",
    "details": {
      "limit": 100,
      "window": "1 hour",
      "reset_timestamp": "2024-01-15T11:30:00Z",
      "retry_after_seconds": 3600
    }
  },
  "request_id": "req_550e8400",
  "timestamp": "2024-01-15T10:35:00Z",
  "path": "/query",
  "method": "GET"
}
```

#### Client Retry Strategy

Clients should:
1. Extract `Retry-After` header (or calculate from `X-RateLimit-Reset`)
2. Wait the specified duration
3. Retry request
4. Exponential backoff: wait = initial_wait * (2 ^ attempt)

---

## 8. Multi-User Isolation

### Isolation Principles

1. **At API Layer**: Users can only access their own data (enforced via JWT)
2. **At Database Layer**: Queries filtered by user_id (WHERE user_id = $1)
3. **At Storage Layer**: S3 objects prefixed by user_id (s3://documents/{user_id}/...)
4. **At Vector Store Layer**: FAISS index per user (module_2/indexes/{user_id}/...)

### Access Control Enforcement

#### User Identification

Every request passes through JWT middleware:

```python
@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    """Extract user_id from JWT token and inject into request.state"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        request.state.user_id = user_id
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={"error": "Invalid token"})
    
    return await call_next(request)
```

#### Path Parameter Validation

For endpoints with `/users/{user_id}/...`:

```python
@app.get("/users/{user_id}/documents")
async def list_documents(
    user_id: str,
    request: Request
):
    """Enforce that user_id from path matches JWT user_id"""
    if user_id != request.state.user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own resources"
        )
    
    # Query documents for this user
    documents = await db.query(
        "SELECT * FROM documents WHERE user_id = $1",
        user_id
    )
    return documents
```

#### Database Query Isolation

All queries include `WHERE user_id = $1` filter:

```python
# Always include user_id filter
async def get_documents(user_id: str):
    query = """
    SELECT * FROM documents 
    WHERE user_id = $1
    ORDER BY upload_timestamp DESC
    """
    return await db.fetch(query, user_id)

async def get_audit_log(user_id: str, limit: int = 20):
    query = """
    SELECT * FROM audit_logs 
    WHERE user_id = $1
    ORDER BY timestamp DESC
    LIMIT $2
    """
    return await db.fetch(query, user_id, limit)
```

#### S3 Object Isolation

Documents stored with user_id prefix:

```
s3://documents/user_123/doc_550e8400/original.pdf
s3://documents/user_456/doc_550e8401/original.pdf
```

Signed URLs require valid user_id + doc_id match:

```python
def generate_signed_url(user_id: str, doc_id: str, expiry_hours: int = 1):
    """Generate S3 signed URL with user_id validation"""
    key = f"documents/{user_id}/{doc_id}/original.pdf"
    
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': 'documents', 'Key': key},
        ExpiresIn=expiry_hours * 3600
    )
    return url
```

#### Vector Store Isolation

Module 2 maintains per-user FAISS indices:

```
/indexes/user_123/index.faiss
/indexes/user_123/metadata.json
/indexes/user_456/index.faiss
/indexes/user_456/metadata.json
```

All queries pass user_id to Module 2:

```python
# Module 4 (LLM) calls Module 2 with user_id
async def query_llm(
    user_id: str,
    query: str,
    k: int = 7
):
    # Module 3 retrieves from user's FAISS index
    chunks, scores = await retrieve_and_rerank(
        user_id=user_id,
        query=query,
        k=k
    )
    return chunks, scores
```

### Isolation Test Cases

| Scenario | Outcome | Test |
|----------|---------|------|
| User A queries documents | ✓ Returns User A's chunks | JWT user_id == path user_id |
| User A tries to access User B's documents | ✗ 403 Forbidden | JWT user_id != path user_id |
| User A deletes their document | ✓ Document removed from User A's index | user_id filter in DELETE query |
| User B queries after User A deletes doc | ✓ No document returned (it's in User A's index only) | Separate FAISS indices |

---

## 9. Audit Logging

### Audit Log Table Schema

```sql
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    request_id UUID NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    action_description VARCHAR(255),
    doc_id UUID,
    doc_name VARCHAR(255),
    query_text VARCHAR(500),
    status VARCHAR(50) NOT NULL,  -- success, error, in_progress
    confidence_level VARCHAR(50),  -- HIGH, MEDIUM, LOW
    response_time_ms INTEGER,
    error_message TEXT,
    ip_address VARCHAR(45),  -- IPv4 or IPv6
    user_agent VARCHAR(255),
    timestamp TIMESTAMP NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_user_timestamp (user_id, timestamp),
    INDEX idx_action_type (action_type),
    INDEX idx_timestamp (timestamp)
);
```

### Logged Actions

| Action | Trigger | Logged Fields | Sensitive? |
|--------|---------|---------------|-----------|
| `login` | Successful login | user_id, ip, user_agent, timestamp | No |
| `login_failed` | Failed login attempt | email, ip, reason, timestamp | Partial (no password) |
| `logout` | User logout | user_id, ip, timestamp | No |
| `ingest` | Document uploaded | user_id, doc_id, doc_name, file_size, chunks_count, time | No |
| `ingest_failed` | Ingestion error | user_id, doc_id, error_message | Yes (contains error) |
| `query` | Query submitted | user_id, query_text (truncated), confidence, response_time, citations_count | Partial (query text) |
| `query_failed` | Query error | user_id, query_text, error_message | Partial |
| `delete` | Document deleted | user_id, doc_id, doc_name | No |
| `token_refresh` | Access token refreshed | user_id, ip, timestamp | No |

### Logging Implementation

```python
async def log_action(
    user_id: str,
    request_id: str,
    action_type: str,
    status: str,
    response_time_ms: int,
    **details  # action-specific fields
):
    """
    Log action to audit_logs table.
    
    Called after every request completes.
    Fields:
    - For ingest: doc_id, doc_name, file_size, chunks_count
    - For query: query_text, confidence_level, citations_count
    - For delete: doc_id, doc_name
    - For errors: error_message, error_code
    """
    log_entry = {
        "log_id": str(uuid.uuid4()),
        "user_id": user_id,
        "request_id": request_id,
        "action_type": action_type,
        "status": status,
        "response_time_ms": response_time_ms,
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "timestamp": datetime.utcnow(),
        **details
    }
    
    await db.execute(
        "INSERT INTO audit_logs VALUES ($1, $2, ...)",
        *log_entry.values()
    )
```

### Log Retention Policy

```
Active logs: All logs (kept in audit_logs table)
Archived logs: Daily exports to cold storage (S3)
Retention: 7 years (compliance requirement)
Access: Users can retrieve their own logs via /audit-log endpoint
Admin access: Full audit table accessible to admins (separate DB user)
```

---

## 10. Security Rules & Constraints

### Authentication Security

1. **Passwords**:
   - Minimum 8 characters
   - Hash with bcrypt (cost=12)
   - Never store plain text
   - Never transmit in logs or audit trails

2. **Tokens**:
   - Access token: 24-hour expiry
   - Refresh token: 7-day expiry
   - Both signed with HS256
   - Include `jti` (JWT ID) in refresh tokens for revocation
   - Blacklist on logout (Redis, expires at token expiry)

3. **HTTPS Enforcement**:
   - All endpoints require HTTPS
   - Redirect HTTP to HTTPS
   - HSTS header: `max-age=31536000; includeSubDomains`
   - Certificate pinning (optional, for mobile)

### Data Security

1. **At Rest**:
   - Database encrypted (TDE)
   - S3 objects encrypted (AES-256)
   - PII fields encrypted in database

2. **In Transit**:
   - TLS 1.2+ only
   - AEAD cipher suites only
   - No compression (CRIME mitigation)

3. **Access Control**:
   - JWT token required for all sensitive endpoints
   - User isolation enforced at every layer
   - No user can access another user's data
   - Admin-only endpoints require separate permission claims

### Input Validation

1. **File Uploads**:
   - Maximum size: 100MB
   - Allowed types: PDF, DOCX, TXT only
   - Scan for viruses (ClamAV, optional)
   - Store in isolated S3 bucket

2. **Query Strings**:
   - Maximum length: 2000 characters
   - No SQL injection (parameterized queries)
   - No XSS (HTML escape before storing)
   - Validate enum fields (jurisdiction, action_type, etc.)

3. **Pydantic Validation**:
   - All request bodies validated against Pydantic schemas
   - Type checking on all fields
   - Custom validators for business logic
   - Return 422 on validation failure

### Rate Limiting & DDoS

1. **Per-Endpoint Limits**:
   - Login: 10/minute (prevent brute force)
   - Query: 100/hour (prevent resource exhaustion)
   - Other endpoints: per-endpoint limits (see Rate Limiting section)

2. **IP-Based**: Optional additional limit per IP (to catch DDoS)
   - 10,000 requests/hour per IP from any endpoint
   - Can be disabled for trusted IPs

3. **Token Blacklist**:
   - Leaked tokens can be blacklisted immediately
   - Blacklist stored in Redis with TTL matching token expiry
   - Check blacklist on every authenticated request

### Error Message Security

1. **Information Leakage**: Avoid exposing internal details
   - ✓ "Invalid credentials"
   - ✗ "User user@example.com not found"
   - ✓ "Document not found"
   - ✗ "Document doc_123 not found for user_456"

2. **Stack Traces**: Never return stack traces to clients
   - Log full errors server-side
   - Return generic error message to client with request_id
   - Admin can look up request_id in logs

---

## 11. Database Schema

### Users Table

```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    account_tier VARCHAR(50) DEFAULT 'free',  -- free, pro, enterprise
    
    INDEX idx_email (email)
);
```

### Documents Table

```sql
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    doc_name VARCHAR(255) NOT NULL,
    doc_type VARCHAR(20),  -- PDF, DOCX, TXT
    jurisdiction VARCHAR(50),
    file_size_bytes BIGINT,
    s3_key VARCHAR(500),
    status VARCHAR(50) NOT NULL,  -- processing, ready, error
    chunks_count INTEGER,
    error_message TEXT,
    upload_timestamp TIMESTAMP NOT NULL,
    ingestion_timestamp TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_upload_timestamp (upload_timestamp)
);
```

### Audit Logs Table

(See section 9 above)

### Token Blacklist (Redis)

```
Key format: token_blacklist:{jti}
Value: user_id
TTL: matching token expiry time
```

---

## 12. Middleware Design

### Middleware Stack (Execution Order)

1. **CORS Middleware** - Allow cross-origin requests from approved domains
2. **Request ID Middleware** - Generate unique request_id for tracing
3. **JWT Middleware** - Extract, verify, inject user_id
4. **Rate Limit Middleware** - Check rate limit, return 429 if exceeded
5. **Request Logging Middleware** - Log request start
6. **Exception Handler** - Catch exceptions, return proper error responses
7. **Response Logging Middleware** - Log request end + response

### CORS Configuration

```python
CORSMiddleware(
    app,
    allow_origins=[
        "https://example.com",
        "https://app.example.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
    max_age=3600  # 1 hour
)
```

### Request ID Generation

```python
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate unique request_id for tracing"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

### Exception Handling Middleware

```python
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Convert exceptions to proper error responses"""
    
    # Known exceptions (HTTPException, ValidationError)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.detail.get("code", "HTTP_ERROR"),
                    "message": exc.detail.get("message", str(exc.detail))
                },
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path),
                "method": request.method
            }
        )
    
    # Unknown exceptions (log full error, return generic response)
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        exc_info=exc
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please contact support."
            },
            "request_id": request.state.request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

---

## 13. Full JSON Examples

### Example 1: Login Flow

**Request**:
```http
POST /auth/login HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsInVzZXJfaWQiOiJ1c2VyXzEyMyIsImVtYWlsIjoidXNlckBleGFtcGxlLmNvbSIsImlhdCI6MTcwNTI3NjgwMCwiZXhwIjoxNzA1MzYzMjAwLCJ0b2tlbl90eXBlIjoiYWNjZXNzIn0.abcdef123456",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsInVzZXJfaWQiOiJ1c2VyXzEyMyIsImlhdCI6MTcwNTI3NjgwMCwiZXhwIjogMTcwNTg4MTYwMCwidG9rZW5fdHlwZSI6InJlZnJlc2giLCJqdGkiOiJ1dWlkLXN0cmluZyJ9.ghijkl789012",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "user_id": "user_123",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### Example 2: Upload Document

**Request**:
```http
POST /ingest HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: multipart/form-data

--boundary123
Content-Disposition: form-data; name="file"; filename="indemnity.pdf"
Content-Type: application/pdf

[binary PDF content]
--boundary123
Content-Disposition: form-data; name="doc_name"

indemnity_agreement.pdf
--boundary123
Content-Disposition: form-data; name="jurisdiction"

NY
--boundary123--
```

**Response (202 Accepted)**:
```json
{
  "request_id": "ingest_req_abc123",
  "doc_id": "doc_550e8400",
  "doc_name": "indemnity_agreement.pdf",
  "status": "processing",
  "chunks_count": 27,
  "estimated_completion_time_seconds": 45,
  "message": "Document ingestion started. Query status with request_id."
}
```

### Example 3: Query Document

**Request**:
```http
GET /query?query=What%20is%20the%20liability%20cap?&k=5&jurisdiction=NY HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK)**:
```json
{
  "query_id": "query_550e8400",
  "query": "What is the liability cap?",
  "answer": "The liability cap is USD 5,000,000 per occurrence (Source: indemnity_agreement.pdf, p.7).",
  "citations": [
    {
      "chunk_id": "chunk_15",
      "source_doc": "indemnity_agreement.pdf",
      "page_number": 7,
      "text_excerpt": "The liability cap in Section 10 is USD 5,000,000 per occurrence.",
      "character_offset": {
        "start": 234,
        "end": 289
      },
      "jurisdiction": "NY",
      "section": "Limitations of Liability"
    }
  ],
  "confidence": {
    "score": 0.92,
    "level": "HIGH",
    "interpretation": "High confidence - answer is well-supported by sources"
  },
  "timing": {
    "search_time_ms": 245,
    "llm_time_ms": 1320,
    "total_time_ms": 1565
  },
  "metadata": {
    "chunks_searched": 27,
    "chunks_used": 1,
    "model": "gpt-4o",
    "timestamp": "2024-01-15T10:30:45Z"
  }
}
```

### Example 4: Audit Log Query

**Request**:
```http
GET /audit-log?page=1&page_size=20&action_type=query&start_date=2024-01-01&end_date=2024-01-15 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK)**:
```json
{
  "page": 1,
  "page_size": 20,
  "total_count": 147,
  "total_pages": 8,
  "records": [
    {
      "log_id": "log_550e8400",
      "user_id": "user_123",
      "action_type": "query",
      "action_description": "Legal query submitted",
      "doc_name": "indemnity_agreement.pdf",
      "query_text": "What is the liability cap?",
      "status": "success",
      "confidence_level": "HIGH",
      "response_time_ms": 1565,
      "error_message": null,
      "timestamp": "2024-01-15T10:30:45Z",
      "ip_address": "203.0.113.42",
      "request_id": "query_550e8400"
    }
  ],
  "filters_applied": {
    "action_type": "query",
    "start_date": "2024-01-01",
    "end_date": "2024-01-15"
  }
}
```

---

## 14. Authentication Flow Diagram

```
┌─────────────┐
│   CLIENT    │
└──────┬──────┘
       │
       │ 1. POST /auth/login
       │    {email, password}
       ▼
   ┌────────────────────────────────────┐
   │ 2. FastAPI validates credentials   │
   │    - Hash password with bcrypt     │
   │    - Compare with stored hash      │
   │    - Check account is active       │
   └────────────┬───────────────────────┘
                │
         ┌──────┴──────┐
         │             │
    ✓ Valid        ✗ Invalid
         │             │
         ▼             ▼
    ┌────────┐    ┌──────────┐
    │Generate│    │401 Unauth│
    │Tokens  │    └──────────┘
    └────┬───┘
         │ 3. Generate Access Token (24h)
         │    {sub, user_id, email, iat, exp}
         │    Signed with JWT_SECRET_KEY
         │
         │ 4. Generate Refresh Token (7d)
         │    {sub, user_id, iat, exp, jti}
         │    Signed with JWT_REFRESH_KEY
         │
         ▼
    ┌──────────────────────────────┐
    │ 5. Return tokens to client   │
    │    {access_token,            │
    │     refresh_token,           │
    │     expires_in: 86400}       │
    └──────────┬───────────────────┘
               │
               │ 6. Client stores tokens
               │    (access in memory, refresh in secure storage)
               │
               ▼
    ┌──────────────────────────────┐
    │ User makes authenticated req │
    │ GET /query                   │
    │ Header: Authorization:       │
    │   Bearer {access_token}      │
    └──────────┬───────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │ 7. JWT Middleware verifies token │
    │    - Decode with JWT_SECRET_KEY  │
    │    - Check signature             │
    │    - Check expiration            │
    │    - Check blacklist (Redis)     │
    └────────────┬─────────────────────┘
                 │
          ┌──────┴──────┐
          │             │
      ✓ Valid      ✗ Invalid/Expired
          │             │
          ▼             ▼
    ┌─────────┐    ┌──────────────┐
    │Extract  │    │Check if token│
    │user_id  │    │is expired?   │
    │Inject   │    └──────┬───────┘
    │into     │           │
    │request. │      ┌────┴─────┐
    │state    │    ✓ Expired  ✗ Nope
    └────┬────┘      │         │
         │           ▼         ▼
         │      ┌─────────┐ ┌──────────┐
         │      │Return   │ │Return    │
         │      │401 Exp  │ │401 Inv   │
         │      │ired     │ │alid      │
         │      └─────────┘ └──────────┘
         │
         │ 8. Call route handler with user_id
         │
         ▼
    ┌──────────────┐
    │ /query route │
    │ handler      │
    │ (uses        │
    │ user_id from │
    │ request.     │
    │ state)       │
    └──────┬───────┘
           │
           │ 9. Query user's isolated
           │    FAISS index
           │
           ▼
    ┌──────────────────┐
    │ Module 3,4: Ret  │
    │ cited answer     │
    └──────┬───────────┘
           │
           ▼
    ┌──────────────────┐
    │ Return 200 OK    │
    │ with answer +    │
    │ citations +      │
    │ confidence       │
    └──────┬───────────┘
           │
           │ 10. Client receives response
           │
    ┌──────┴──────┐
    │             │
    ▼ After       ▼ After
 expires in   expires in
  ~20 hours   ~6 days
    │             │
    ▼             ▼
┌──────────┐  ┌─────────────┐
│Generate  │  │POST /auth/  │
│new       │  │refresh      │
│access    │  │{refresh_    │
│token via │  │token}       │
│POST /    │  └──────┬──────┘
│auth/     │         │
│refresh   │         ▼
│          │  ┌──────────────┐
└──────────┘  │Return new    │
              │access_token  │
              │Valid for 24h │
              └──────────────┘
```

**Key Points**:
1. **Initial Login**: Email + password → access + refresh tokens
2. **Token Usage**: Include access_token in Authorization header
3. **Token Expiry**: 24-hour access tokens prevent long-term damage from leaks
4. **Refresh Flow**: When access token expires, use refresh token to get new access token
5. **Logout**: Blacklist both tokens immediately
6. **Isolation**: user_id extracted from token, used to filter all database queries

---

## 15. Deployment Configuration

### Environment Variables

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=INFO

# JWT Configuration
JWT_SECRET_KEY=<generate-32-byte-random-key>  # openssl rand -hex 16
JWT_REFRESH_SECRET_KEY=<generate-32-byte-random-key>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRY=86400  # 24 hours
REFRESH_TOKEN_EXPIRY=604800  # 7 days

# Database
DATABASE_URL=postgresql://user:password@host:5432/legalbot_db
DATABASE_POOL_SIZE=20
DATABASE_POOL_TIMEOUT=30

# Redis (Rate Limiting + Token Blacklist)
REDIS_URL=redis://host:6379/0
REDIS_SSL=true

# AWS S3 (Document Storage)
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
S3_BUCKET=documents
S3_REGION=us-east-1

# Allowed Origins (CORS)
CORS_ORIGINS=https://example.com,https://app.example.com

# Rate Limiting
RATE_LIMIT_LOGIN=10:1m
RATE_LIMIT_QUERY=100:1h
RATE_LIMIT_INGEST=20:1h

# Internal Modules (Modules 1-4)
MODULE_1_HOST=localhost:8001
MODULE_2_HOST=localhost:8002
MODULE_3_HOST=localhost:8003
MODULE_4_HOST=localhost:8004
MODULE_TIMEOUT_SECONDS=30
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legalbot-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: legalbot-api
  template:
    metadata:
      labels:
        app: legalbot-api
    spec:
      containers:
      - name: api
        image: legalbot-api:1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

---

## 16. Performance & SLAs

### Response Time Targets

| Endpoint | Target | P99 | Notes |
|----------|--------|-----|-------|
| `/auth/login` | <200ms | <500ms | Database lookup + bcrypt hash |
| `/auth/refresh` | <50ms | <100ms | JWT verification only |
| `/ingest` | <500ms | <1000ms | File upload + S3 storage (async) |
| `/query` | <2s | <5s | Modules 2-4 ( retrieval + LLM) |
| `/audit-log` | <500ms | <1000ms | Database query + pagination |
| `/users/{user_id}/documents` | <300ms | <500ms | Database query |
| `DELETE /documents/{doc_id}` | <1s | <3s | Document deletion + FAISS cleanup |
| `/health` | <100ms | <200ms | Simple status check |

### Throughput Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent Users | 1,000+ | Connection pooling + async |
| Queries/Hour | 100,000+ | 100 per user × 1,000 users |
| Ingest/Hour | 20,000 | 20 per user × 1,000 users (async) |
| Error Rate | <0.1% | Retries, circuit breakers |

### Availability

- **Uptime SLA**: 99.9% (43.2 minutes downtime/month)
- **RTO** (Recovery Time Objective): <1 minute
- **RPO** (Recovery Point Objective): 0 (no data loss)

### Scaling Strategy

1. **Horizontal**: Multiple API instances behind load balancer
2. **Database**: Read replicas for audit log queries
3. **Cache**: Redis for rate limiting, token blacklist
4. **Async**: Background workers for document ingestion
5. **CDN**: CloudFront for static content

---

## Summary

This specification defines a production-ready API layer for the legal RAG system with:

✅ Comprehensive endpoint definitions (POST, GET, DELETE)  
✅ JWT authentication with access/refresh tokens and blacklisting  
✅ Multi-user isolation enforced at API, database, and storage layers  
✅ Rate limiting per endpoint (10-100 requests/hour depending on action)  
✅ Audit logging for all user actions  
✅ Error handling with machine + human-readable messages  
✅ Complete Pydantic models for request/response validation  
✅ Security best practices (HTTPS, password hashing, input validation)  
✅ Full JSON examples for every endpoint  
✅ ASCII authentication flow diagram  
✅ Database schema for users, documents, audit logs  
✅ Middleware stack design  
✅ Deployment configuration (Docker, Kubernetes)  
✅ Performance SLAs and scaling strategy  

---

**Next Steps**:
1. Implement FastAPI application with endpoints
2. Set up PostgreSQL and Redis
3. Create Pydantic models and middleware
4. Implement JWT token generation/verification
5. Deploy with Docker/Kubernetes
