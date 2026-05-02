# AutoDocumentation Engine - High Level Design (HLD)
## Simplified Direct Generation Model

**Project**: AI-Powered Code-to-Documentation Platform  
**Version**: 2.0 (Simplified)  
**Date**: May 2026  
**Audience**: System Architects, Tech Leads, Senior Engineers

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Architecture Overview](#architecture-overview)
4. [Key Components](#key-components)
5. [Data Flow](#data-flow)
6. [Technology Stack](#technology-stack)
7. [Scalability & Performance](#scalability--performance)
8. [Security Considerations](#security-considerations)
9. [Deployment Strategy](#deployment-strategy)

---

## Executive Summary

**AutoDocumentation Engine** is a streamlined AI platform that automatically generates professional documentation directly from GitHub repositories. Users provide a repository URL, and the system analyzes the code using five specialized LLM agents to produce comprehensive documentation in multiple formats.

### Key Value Propositions
- **Instant Documentation**: Get complete docs in < 5 minutes
- **No Setup Required**: Just provide GitHub URL, get documentation
- **High Quality**: RAG-backed generation prevents hallucinations
- **Multiple Formats**: Markdown, HTML, PDF, OpenAPI all at once
- **Enterprise Ready**: Handles large codebases efficiently

### Scope

| In Scope | Out of Scope |
|----------|-------------|
| Direct GitHub repo analysis | Webhooks or automation |
| Python, JavaScript, Java, Go | Feedback storage/learning |
| Markdown, HTML, PDF, OpenAPI | Dashboard or history |
| RAG-based context retrieval | Documentation regeneration |
| Single API call to generate docs | Memory/preference learning |
| Output download/display | Multi-team management |

---

## System Overview

### Problem Statement
Developers need to generate comprehensive documentation quickly without maintaining outdated docs. They want to give a repo URL and get complete documentation immediately.

### Solution Architecture
Simple, efficient pipeline:
1. User provides GitHub repo URL via API
2. System clones and analyzes the repository
3. Five specialized agents analyze different aspects in parallel
4. Final synthesis combines all outputs
5. Return documentation in multiple formats

### High-Level Process Flow

```
User Input (GitHub URL)
        ↓
Validate & Clone Repository
        ↓
Parse Code (Extract Structure)
        ↓
5 Agents Analyze in Parallel
        ↓
Synthesize Results
        ↓
Generate Multiple Formats
        ↓
Return Documentation
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                                 │
├──────────────┬──────────────────────────────────────────────────┤
│  REST API    │  Web UI (Simple Form)                            │
│  /generate   │  GitHub URL input → Download Docs               │
└──────┬───────┴──────────────────────────────────────────────────┘
       │
       └─────────────────────────┐
                                 │
        ┌────────────────────────▼──────────────────┐
        │   FASTAPI CORE SERVICE LAYER              │
        │                                           │
        │  POST /api/generate                       │
        │  - Accept GitHub URL                      │
        │  - Queue job                              │
        │  - Return job ID                          │
        │                                           │
        │  GET /api/status/{job_id}                 │
        │  - Check generation progress              │
        │                                           │
        │  GET /api/download/{job_id}               │
        │  - Download documentation                 │
        └────────────┬─────────────────────────────┘
                     │
        ┌────────────▼──────────────────────────────────────────┐
        │   REQUEST PROCESSOR & QUEUE MANAGER                  │
        │  (Celery for async job processing)                   │
        │                                                       │
        │  - Queue incoming generation requests                │
        │  - Manage job lifecycle (queued → processing → done)  │
        │  - Handle timeouts and failures                       │
        └────────────┬──────────────────────────────────────────┘
                     │
        ┌────────────▼──────────────────────────────────────────┐
        │         REPOSITORY MANAGER                           │
        │                                                       │
        │  - Clone GitHub repository                           │
        │  - Detect language & framework                       │
        │  - Extract code files                                │
        │  - Clean up (delete after processing)                │
        └────────────┬──────────────────────────────────────────┘
                     │
        ┌────────────▼──────────────────────────────────────────┐
        │    ORCHESTRATION LAYER (LangGraph)                   │
        │                                                       │
        │  ┌──────────────┬──────────────────────────────────┐  │
        │  │ Code Analyzer│ Architecture Detective          │  │
        │  │   Agent      │      Agent                      │  │
        │  └────────┬─────┴────────┬──────────────────────────┘  │
        │           │              │                            │
        │  ┌────────▼──────────────▼──────────────────────────┐  │
        │  │   API Documentation    │  Examples Generator    │  │
        │  │      Agent             │      Agent             │  │
        │  └───────────┬────────────┬────────────────────────┘  │
        │              │            │                           │
        │  ┌───────────▼────────────▼──────────────────────────┐ │
        │  │  Consistency Validator Agent                     │ │
        │  │  (Quality & Standards Check)                     │ │
        │  └──────────────┬─────────────────────────────────┘  │
        │                 │                                     │
        │  ┌──────────────▼──────────────────────────────────┐  │
        │  │   Final Synthesizer Agent                      │  │
        │  │   (Combine & format outputs)                   │  │
        │  └──────────────┬──────────────────────────────────┘  │
        └─────────────────┼──────────────────────────────────────┘
                          │
        ┌─────────────────▼──────────────────────────────────┐
        │    INTELLIGENT SYSTEMS LAYER                      │
        │                                                   │
        │  ┌──────────────────────────────────────────────┐ │
        │  │  RAG Module (Context Retrieval)              │ │
        │  │  - Vector Store (Pinecone)                   │ │
        │  │  - Code Embeddings                           │ │
        │  │  - Semantic search & retrieval               │ │
        │  └──────────────────────────────────────────────┘ │
        │                                                   │
        │  ┌──────────────────────────────────────────────┐ │
        │  │  LLM Interface Layer                         │ │
        │  │  - Claude/GPT-4 API calls                   │ │
        │  │  - Prompt engineering                       │ │
        │  │  - Token optimization                       │ │
        │  └──────────────────────────────────────────────┘ │
        └─────────────────┬──────────────────────────────────┘
                          │
        ┌─────────────────▼──────────────────────────────────┐
        │     TEMPORARY DATA LAYER                          │
        │                                                   │
        │  ┌──────────┬──────────┬──────────────────────┐  │
        │  │In-Memory │ Temp File│ Redis Cache         │  │
        │  │ Storage  │ Storage  │(Job Status & Output)│  │
        │  └──────────┴──────────┴──────────────────────┘  │
        │  (All data deleted after user downloads)         │
        └─────────────────┬──────────────────────────────────┘
                          │
        ┌─────────────────▼──────────────────────────────────┐
        │      OUTPUT GENERATION LAYER                      │
        │                                                   │
        │  ┌──────────┬──────────┬──────────┬────────────┐  │
        │  │Markdown  │  HTML    │   PDF    │  OpenAPI   │  │
        │  │Generator │Generator │Generator │  Generator │  │
        │  └──────────┴──────────┴──────────┴────────────┘  │
        └─────────────────┬──────────────────────────────────┘
                          │
        ┌─────────────────▼──────────────────────────────────┐
        │     FILE DELIVERY LAYER                           │
        │                                                   │
        │  - Return via API (streaming)                    │
        │  - Generate download links                       │
        │  - Package as ZIP                                │
        └─────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. **FastAPI Core Service**
**Responsibility**: HTTP request handling, job management, API responses  
**Key Endpoints**:
- `POST /api/generate` - Trigger doc generation from GitHub URL
- `GET /api/status/{job_id}` - Check generation progress
- `GET /api/download/{job_id}` - Download generated documentation
- `GET /api/formats/{job_id}` - List available formats

**Technologies**: FastAPI, Pydantic, Python 3.11+

### 2. **Repository Manager**
**Responsibility**: Clone, analyze, and clean up GitHub repositories  
**Operations**:
- Clone from GitHub (with authentication)
- Detect programming language
- Extract file structure
- Identify frameworks (FastAPI, Flask, Django, etc.)
- Clean up after processing

**Technologies**: GitPython, subprocess, temp file management

### 3. **LangGraph Orchestration Engine**
**Responsibility**: Multi-agent workflow coordination  
**Components**:
- State machine for workflow execution
- Node definitions (5 agents)
- Edge routing (parallel execution)
- Error handling & fallbacks

**Technologies**: LangGraph, LangChain

### 4. **RAG Module (Context Retrieval)**
**Responsibility**: Semantic search for code patterns and documentation context  
**Features**:
- Vector embeddings for code snippets
- Similarity search for relevant patterns
- Public documentation retrieval

**Technologies**: LangChain, Pinecone, OpenAI Embeddings

### 5. **Code Parsing & Analysis Engine**
**Responsibility**: Extract structure from source code  
**Supports**:
- Python (ast module)
- JavaScript/TypeScript (babel-parser)
- Java (javaparser)
- Go (go/parser)

**Technologies**: Language-specific parsers

### 6. **Output Generation Layer**
**Responsibility**: Convert documentation to multiple formats  
**Formats**:
- Markdown (README)
- HTML (standalone viewing)
- PDF (distribution)
- OpenAPI/Swagger (API tools)

**Technologies**: Jinja2, weasyprint, python-docx

### 7. **Job Queue Manager**
**Responsibility**: Async job processing and progress tracking  
**Features**:
- Queue incoming requests
- Track job status
- Manage timeouts
- Clean up completed jobs

**Technologies**: Celery, Redis, RQ

### 8. **Temporary Data Store**
**Responsibility**: Store intermediate results (deleted after download)  
**Storage**:
- Redis: Job metadata and status
- Temp files: Generated documentation
- In-memory: Processing state

**Technologies**: Redis, File system, Python collections

---

## Data Flow

### Main Flow: GitHub URL → Documentation

```
1. USER SUBMITS REQUEST
   ┌─────────────────────────────────┐
   │ POST /api/generate              │
   │ {                               │
   │   "repo_url": "https://..."     │
   │   "formats": ["md", "html"]     │
   │ }                               │
   └──────────────┬──────────────────┘
                  │
   2. VALIDATION & QUEUING
   ┌──────────────▼──────────────────┐
   │ - Validate GitHub URL           │
   │ - Generate job_id               │
   │ - Queue to Celery               │
   │ - Return job_id to user         │
   └──────────────┬──────────────────┘
                  │
   3. ASYNC PROCESSING STARTS
   ┌──────────────▼──────────────────────────────────┐
   │ STEP 1: CLONE REPOSITORY                        │
   │ ├─ Clone from GitHub                            │
   │ ├─ Detect language (Python/JS/Java/Go)         │
   │ ├─ Extract .gitignore patterns                 │
   │ └─ Prepare for analysis                        │
   └──────────────┬──────────────────────────────────┘
                  │
   ┌──────────────▼──────────────────────────────────┐
   │ STEP 2: INITIAL CODE ANALYSIS                   │
   │ ├─ Parse code (AST)                             │
   │ ├─ Extract functions, classes, methods          │
   │ ├─ Calculate complexity metrics                 │
   │ ├─ Identify undocumented components             │
   │ └─ Map dependencies                             │
   └──────────────┬──────────────────────────────────┘
                  │
   ┌──────────────▼──────────────────────────────────┐
   │ STEP 3: PARALLEL AGENT ANALYSIS                 │
   │                                                 │
   │ ┌─────────────────────────────────────────────┐ │
   │ │ Agent 1: Code Analyzer                     │ │
   │ │ ├─ Detailed function documentation         │ │
   │ │ ├─ Class hierarchies                       │ │
   │ │ ├─ Module organization                     │ │
   │ │ └─ Generate: Overview & API section        │ │
   │ └─────────────────────────────────────────────┘ │
   │                                                 │
   │ ┌─────────────────────────────────────────────┐ │
   │ │ Agent 2: Architecture Detective             │ │
   │ │ ├─ Identify system design                   │ │
   │ │ ├─ Extract design patterns                  │ │
   │ │ ├─ Map component relationships              │ │
   │ │ └─ Generate: Architecture section           │ │
   │ └─────────────────────────────────────────────┘ │
   │                                                 │
   │ ┌─────────────────────────────────────────────┐ │
   │ │ Agent 3: API Documentation Agent            │ │
   │ │ ├─ Extract REST/GraphQL endpoints           │ │
   │ │ ├─ Generate OpenAPI schema                  │ │
   │ │ ├─ Create request/response examples         │ │
   │ │ └─ Generate: API Reference section          │ │
   │ └─────────────────────────────────────────────┘ │
   │                                                 │
   │ ┌─────────────────────────────────────────────┐ │
   │ │ Agent 4: Examples Synthesizer                │ │
   │ │ ├─ Find code examples from repo             │ │
   │ │ ├─ RAG: Retrieve similar patterns           │ │
   │ │ ├─ Generate usage examples                  │ │
   │ │ └─ Generate: Quick Start & Examples section │ │
   │ └─────────────────────────────────────────────┘ │
   │                                                 │
   │ ┌─────────────────────────────────────────────┐ │
   │ │ Agent 5: Consistency Validator               │ │
   │ │ ├─ Validate completeness                    │ │
   │ │ ├─ Cross-reference sections                 │ │
   │ │ ├─ Quality scoring                          │ │
   │ │ └─ Flag issues                              │ │
   │ └─────────────────────────────────────────────┘ │
   └──────────────┬──────────────────────────────────┘
                  │
   ┌──────────────▼──────────────────────────────────┐
   │ STEP 4: SYNTHESIS & FORMATTING                  │
   │ ├─ Combine all agent outputs                   │
   │ ├─ Resolve conflicts                           │
   │ ├─ Generate table of contents                  │
   │ ├─ Cross-link sections                         │
   │ └─ Format as structured content                │
   └──────────────┬──────────────────────────────────┘
                  │
   ┌──────────────▼──────────────────────────────────┐
   │ STEP 5: GENERATE MULTIPLE FORMATS               │
   │                                                 │
   │ ├─ Markdown Generator                          │
   │ │  ├─ Create README.md                         │
   │ │  ├─ Format code blocks                       │
   │ │  └─ Add metadata                             │
   │ │                                              │
   │ ├─ HTML Generator                              │
   │ │  ├─ Apply CSS styling                        │
   │ │  ├─ Generate navigation                      │
   │ │  └─ Create index.html                        │
   │ │                                              │
   │ ├─ PDF Generator                               │
   │ │  ├─ Format for printing                      │
   │ │  ├─ Add page numbers                         │
   │ │  └─ Generate TOC                             │
   │ │                                              │
   │ └─ OpenAPI Generator                           │
   │    ├─ Extract API specs                        │
   │    ├─ Generate schema.json                     │
   │    └─ Create swagger.yaml                      │
   └──────────────┬──────────────────────────────────┘
                  │
   ┌──────────────▼──────────────────────────────────┐
   │ STEP 6: PREPARE DELIVERY                        │
   │ ├─ Package all formats                         │
   │ ├─ Create ZIP file                             │
   │ ├─ Generate download links                     │
   │ ├─ Upload to temp storage                      │
   │ └─ Update job status                           │
   └──────────────┬──────────────────────────────────┘
                  │
4. USER POLLS STATUS & DOWNLOADS
   ┌──────────────▼──────────────────┐
   │ GET /api/status/{job_id}        │
   │ → Returns: "completed"          │
   │                                 │
   │ GET /api/download/{job_id}      │
   │ → Returns: Documentation files  │
   └─────────────────────────────────┘

5. CLEANUP
   ┌─────────────────────────────────────────┐
   │ - Delete cloned repository              │
   │ - Remove temp files (after 24 hours)    │
   │ - Clear Redis entries                   │
   │ - Mark job as archived                  │
   └─────────────────────────────────────────┘
```

---

## Technology Stack

### Core Framework
- **FastAPI** - REST API, async support, automatic OpenAPI docs
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation

### AI/ML Components
- **LangChain** - LLM framework, RAG, prompt management
- **LangGraph** - Multi-agent orchestration and workflow
- **OpenAI/Anthropic APIs** - LLM inference (GPT-4, Claude)

### Code Analysis
- **ast** (Python) - Abstract Syntax Tree parsing
- **babel-parser** (JavaScript/TypeScript)
- **javaparser** (Java)
- **go/parser** (Go)

### Repository Management
- **GitPython** - GitHub API interaction
- **subprocess** - Shell command execution
- **tempfile** - Temporary file handling

### Task Queue & Async Processing
- **Celery** - Distributed task processing
- **Redis** - Message broker and result backend

### Vector Database & RAG
- **Pinecone** - Vector database for embeddings
- **OpenAI Embeddings** - Text-to-vector conversion

### Document Generation
- **Jinja2** - Template rendering
- **weasyprint** - HTML to PDF conversion
- **markdown** - Markdown processing
- **PyYAML** - YAML/OpenAPI handling

### Utilities
- **python-dotenv** - Configuration management
- **requests** - HTTP client
- **aiohttp** - Async HTTP requests

### Testing & Quality
- **pytest** - Unit testing
- **pytest-asyncio** - Async test support
- **black** - Code formatting
- **pylint** - Code linting

### DevOps & Deployment
- **Docker** - Containerization
- **Docker Compose** - Local development
- **AWS S3** - File storage (optional)
- **GitHub Actions** - CI/CD

---

## Scalability & Performance

### Performance Targets

| Metric | Target | Implementation |
|--------|--------|-----------------|
| API Response Time | < 2 seconds | Queue job, return ID immediately |
| Doc Generation Time | < 5 minutes (avg) | Parallel agent execution |
| Code Parsing | < 30 seconds | Optimized AST parsing |
| LLM Calls | Parallel | 5 agents call LLM simultaneously |
| Concurrent Requests | 100+ | Load balanced FastAPI instances |
| Memory Per Job | < 500MB | Streaming file handling |
| Disk Per Job | < 100MB | Cleanup after processing |

### Horizontal Scaling Strategy

**Stateless Services**:
- FastAPI instances run behind load balancer (Nginx)
- Scale instances based on CPU/memory usage
- No session state stored on instances

**Async Processing**:
- Celery workers process jobs independently
- Multiple workers on multiple machines
- Redis for job queue and status tracking

**Resource Optimization**:
- Stream large files instead of loading in memory
- Delete repositories immediately after analysis
- Clean up temp files after download
- Compress output formats (especially HTML)

### Caching Strategy

```
Redis Cache Structure:
- job:{job_id}:status → "processing" / "completed"
- job:{job_id}:progress → 45
- job:{job_id}:output → Compressed documentation
- job:{job_id}:expires_at → Timestamp for TTL

TTL: 24 hours
Cleanup: Automatic via Redis TTL
```

---

## Security Considerations

### Authentication & Authorization

```
API Access:
- Optional API key for higher limits
- Rate limiting: 10 requests/hour/IP (without key)
- 100 requests/hour (with API key)

GitHub Integration:
- OAuth token (user-provided)
- Public repos don't need authentication
- Private repos require GitHub token
- Tokens never logged or stored
```

### Data Security

```
In Transit:
- TLS 1.3 for all communication
- HTTPS only endpoints
- Secure GitHub token handling

At Rest:
- Temp files in /tmp (system cleanup)
- No persistent storage of docs
- Memory cleared after job completion
- Redis data encrypted at rest (optional)

Secret Management:
- Environment variables for API keys
- GitHub tokens provided by users
- No hardcoded secrets
```

### Repository Analysis Safety

```
Risks Mitigated:
- Malicious code execution: No code execution, only parsing
- Resource exhaustion: Timeout limits (5 minutes)
- Private code exposure: Temp files deleted immediately
- Large repo handling: Stream processing instead of loading all

Limits:
- Max repo size: 500MB
- Max files to analyze: 10,000
- Max execution time: 5 minutes
- Memory limit per job: 1GB
```

---

## Deployment Strategy

### Development Environment

```yaml
Docker Compose Setup:
- FastAPI container
- Redis container
- Celery worker container (optional)
```

### Production Environment

```
Cloud Deployment (AWS/GCP/Azure):
- FastAPI on ECS/EKS
- Redis ElastiCache
- Celery workers on EC2 instances
- S3 for temporary file storage (optional)

Load Balancing:
- Application Load Balancer (ALB)
- Auto-scaling groups
- Health checks every 30 seconds

Monitoring:
- CloudWatch metrics
- Error tracking (Sentry)
- Request logging
```

### CI/CD Pipeline

```
GitHub Actions:
1. Code push to main
2. Run tests (pytest)
3. Run linting (black, pylint)
4. Build Docker image
5. Push to ECR
6. Deploy to staging
7. Run smoke tests
8. Manual approval
9. Deploy to production
```

---

## Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| Availability | 99.5% uptime | Best effort, simple service |
| API Latency | < 2 seconds | Immediate response |
| Gen Time | < 5 minutes | 95th percentile |
| Throughput | 50 concurrent jobs | Per worker |
| Scalability | 10x growth possible | Stateless design |
| Cleanup | Automatic 24h TTL | Redis auto-expire |
| Backup | Not required | No persistent data |
| Recovery | Restart workers | Stateless recovery |

---

## Key Differences from Original Design

| Aspect | Original | Simplified |
|--------|----------|-----------|
| **Input** | Multiple options | GitHub URL only |
| **Webhooks** | ✅ GitHub webhooks | ❌ Removed |
| **Dashboard** | ✅ Full dashboard | ❌ Removed |
| **Storage** | ✅ PostgreSQL + MongoDB | ❌ Redis only (temp) |
| **Memory Learning** | ✅ Team memory system | ❌ Removed |
| **Feedback** | ✅ Feedback storage | ❌ Removed |
| **Regeneration** | ✅ Supported | ❌ Not needed |
| **Data Retention** | ✅ Long-term | ❌ 24 hours max |
| **Complexity** | High | Simple & Direct |

---

## Phase-wise Rollout

### Phase 1: MVP (Week 1-2)
- ✅ FastAPI core service
- ✅ Repository cloning
- ✅ Basic code analysis
- ✅ Single agent for doc generation
- ✅ Markdown output

### Phase 2: Multi-Agent (Week 3-4)
- ✅ LangGraph orchestration (5 agents)
- ✅ RAG integration
- ✅ Multiple output formats
- ✅ Async job processing

### Phase 3: Polish (Week 5-6)
- ✅ Error handling & retry logic
- ✅ Performance optimization
- ✅ Security hardening
- ✅ Web UI for testing

### Phase 4: Production (Week 7-8)
- ✅ Load testing
- ✅ Monitoring & logging
- ✅ Deployment automation
- ✅ Documentation

---

## Success Metrics

```
User-Focused:
- Average generation time
- Successful generation rate (%)
- Documentation quality score (avg)
- User satisfaction (1-5 scale)

Technical:
- API uptime (%)
- Average response time
- Error rate (%)
- Worker utilization (%)

Operational:
- Cost per generation
- Worker efficiency
- Memory efficiency
- Cleanup effectiveness
```

---

## Conclusion

The simplified AutoDocumentation Engine is a focused, efficient solution that:

✅ **Eliminates complexity** - No webhooks, dashboards, or persistent storage  
✅ **Maximizes speed** - Direct URL input to documentation output  
✅ **Maintains quality** - RAG-backed multi-agent generation  
✅ **Scales easily** - Stateless, async-first architecture  
✅ **Keeps costs low** - Automatic cleanup, temporary storage only  

Perfect for:
- Quick documentation generation
- Portfolio demonstration
- MVP-stage product
- Simple, focused use case

---

## Appendix: API Examples

### Generate Documentation
```bash
POST /api/generate
{
  "repo_url": "https://github.com/user/my-project.git",
  "formats": ["markdown", "html", "pdf"]
}

Response (202 Accepted):
{
  "job_id": "doc_123abc",
  "status": "queued",
  "estimated_time_seconds": 180
}
```

### Check Status
```bash
GET /api/status/doc_123abc

Response:
{
  "job_id": "doc_123abc",
  "status": "in_progress",
  "progress": 65,
  "current_stage": "examples_generation"
}
```

### Download Documentation
```bash
GET /api/download/doc_123abc

Response: ZIP file with all formats
```
