# Spec2Test Application Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SPEC2TEST APPLICATION ARCHITECTURE                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PRESENTATION LAYER (Frontend)                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                          Next.js React Frontend (Port 3000)                                        │  │
│  │  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │  │
│  │  │  Upload Modal  │  │  Link Input     │  │  Pipeline Jobs   │  │  View Reports    │              │  │
│  │  │  - Drag & Drop │  │  - Confluence   │  │  - Job List      │  │  - Allure Report │              │  │
│  │  │  - File Select │  │  - Jira         │  │  - Job Status    │  │  - Test Cases    │              │  │
│  │  │  - PDF, DOCX   │  │  - Paste URL    │  │  - Artifacts     │  │  - Download      │              │  │
│  │  └────────────────┘  └─────────────────┘  └──────────────────┘  └──────────────────┘              │  │
│  │       │                     │                      │                     │                           │  │
│  │       └─────────────────────┴──────────────────────┴─────────────────────┘                           │  │
│  │                            HTTP/REST API Calls                                                      │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    API LAYER (Backend)                                                  │
│                          FastAPI Server (Port 8000)                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │  │
│  │  │ /api/upload  │  │ /api/jobs    │  │ /api/link    │  │ /api/health  │  │ /api/report  │        │  │
│  │  │  - File Recv │  │  - Get List  │  │  - Fetch URL │  │  - Status    │  │  - View HTML │        │  │
│  │  │  - Validate  │  │  - Get One   │  │  - Extract   │  │  - Heartbeat │  │  - Download  │        │  │
│  │  │  - Queue Job │  │  - Status    │  │  - Queue Job │  │              │  │              │        │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │  │
│  │         │                │                │                │                │                      │  │
│  │         └────────────────┴────────────────┴────────────────┴────────────────┘                      │  │
│  │                      Request Routing & Validation                                                  │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PROCESSING LAYER (Celery Workers)                                       │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                        Task Queue & Distributed Processing                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │  │  │
│  │  │ │ Document        │  │ Embedding        │  │ Test Planning    │  │ Test Execution   │      │  │  │
│  │  │ │ Processing      │  │ Generation       │  │ & Generation     │  │ (Playwright)     │      │  │  │
│  │  │ │ ┌─────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │      │  │  │
│  │  │ │ │ 1. Load Doc │ │  │ │ OpenAI API   │ │  │ │ LLM Planner  │ │  │ │ Playwright   │ │      │  │  │
│  │  │ │ │ 2. Extract  │ │  │ │ Batch        │ │  │ │ (GPT-4)      │ │  │ │ Browser      │ │      │  │  │
│  │  │ │ │ 3. Chunk    │ │  │ │ Embedding    │ │  │ │ Generate     │ │  │ │ Execution    │ │      │  │  │
│  │  │ │ │ 4. Clean    │ │  │ │ Vectors      │ │  │ │ Test Cases   │ │  │ │ Test Suite   │ │      │  │  │
│  │  │ │ └─────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │      │  │  │
│  │  │ └─────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘      │  │  │
│  │  │        │                    │                      │                    │                   │  │  │
│  │  │        └────────────────────┴──────────────────────┴────────────────────┘                   │  │  │
│  │  │          Celery Task Chain Execution (Sequential/Parallel)                                  │  │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                        ▼                                                           │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                         Report Generation                                                   │  │  │
│  │  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐                  │  │  │
│  │  │  │ Allure Results      │  │ JSON Test Plan      │  │ Embeddings Storage  │                  │  │  │
│  │  │  │ - Test Metadata     │  │ - Test Cases        │  │ - Vector Database   │                  │  │  │
│  │  │  │ - Attachments       │  │ - Assertions        │  │ - Semantic Search   │                  │  │  │
│  │  │  │ - Screenshots       │  │ - Scenarios         │  │ - Retrieval Index   │                  │  │  │
│  │  │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘                  │  │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 STORAGE & DATA LAYER                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │  │
│  │  │ File System      │  │ Redis Cache      │  │ Job Database     │  │ Vector Store     │         │  │
│  │  │ - uploads/       │  │ - Session Data   │  │ - Job Metadata   │  │ - Embeddings     │         │  │
│  │  │ - reports/       │  │ - Task Queue     │  │ - Status Tracking│  │ - Similarity     │         │  │
│  │  │ - logs/          │  │ - Job Progress   │  │ - Artifacts Paths│  │ - Retrieval      │         │  │
│  │  │ - allure-results/│  │                  │  │                  │  │                  │         │  │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘         │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              INFRASTRUCTURE & DEPLOYMENT                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                 Docker Compose Stack                                              │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │  │
│  │  │ Frontend         │  │ Backend API      │  │ Celery Workers   │  │ Redis            │         │  │
│  │  │ - Next.js App    │  │ - FastAPI        │  │ - Task Processing│  │ - Message Broker │         │  │
│  │  │ - Nginx Proxy    │  │ - Uvicorn Server │  │ - Distributed    │  │ - Caching        │         │  │
│  │  │ - Port 3000      │  │ - Port 8000      │  │ - Scalable       │  │ - Port 6379      │         │  │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘         │  │
│  │         │                     │                       │                     │                    │  │
│  │         └─────────────────────┼───────────────────────┼─────────────────────┘                    │  │
│  │                               │ Docker Network       │                                           │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐                            │  │
│  │  │                  Environment Configuration                       │                            │  │
│  │  │  - OpenAI API Keys  - Database Credentials  - Service URLs      │                            │  │
│  │  │  - Feature Flags    - Logging Levels         - Timeouts         │                            │  │
│  │  └──────────────────────────────────────────────────────────────────┘                            │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Flow Diagram

```
                          USER INTERACTION FLOW
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
            ┌───────▼────────┐          ┌────────▼────────┐
            │ Upload Document│          │  Paste Link     │
            │ (PDF, DOCX)    │          │ (Confluence)    │
            └────────┬────────┘          └────────┬────────┘
                     │                           │
                     └───────────┬───────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  API Receives Request   │
                    │  /api/upload or /api/link
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Create Job Record       │
                    │ Store Job Metadata      │
                    │ Queue Celery Task       │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
    ┌───▼──────┐          ┌─────▼──────┐         ┌──────▼───┐
    │Extract   │          │Fetch/Extract│        │Validate  │
    │Content   │          │from URL     │        │Content   │
    │from File │          │(Confluence) │        │Type      │
    └───┬──────┘          └─────┬──────┘         └──────┬───┘
        │                       │                      │
        └───────────┬───────────┴──────────────────────┘
                    │
        ┌───────────▼────────────┐
        │  DOCUMENT PROCESSING   │  (Step 1)
        │  - Split into chunks   │
        │  - Clean text          │
        │  - Preserve structure  │
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
        │ EMBEDDING GENERATION   │  (Step 2)
        │ - OpenAI Embedding API │
        │ - Batch Processing     │
        │ - Store Vectors        │
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
        │  TEST PLAN GENERATION  │  (Step 3)
        │ - Query Embeddings     │
        │ - LLM (GPT-4) Analysis │
        │ - Generate Test Cases  │
        │ - Create Test Plan JSON│
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
        │ TEST EXECUTION         │  (Step 4)
        │ - Playwright Browser   │
        │ - Execute Tests        │
        │ - Capture Results      │
        │ - Generate Screenshots │
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
        │ REPORT GENERATION      │  (Step 5)
        │ - Allure Report        │
        │ - Test Results JSON    │
        │ - HTML Report          │
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
        │ STORE ARTIFACTS        │
        │ - Save to reports/     │
        │ - Update Job Status    │
        │ - Notify Frontend      │
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
        │  Frontend Updates      │
        │ - Fetch Job Status     │
        │ - Display Report Link  │
        │ - Show Test Cases      │
        └───────────────────────┘
```

---

## Technology Stack

### Frontend
- **Framework**: Next.js (React)
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **UI Components**: React Hooks, Conditional Rendering
- **Features**: File Upload, URL Input, Job Polling, Report Viewing

### Backend
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn
- **Task Queue**: Celery
- **Message Broker**: Redis
- **APIs**: OpenAI Embeddings, Playwright, Allure

### Data Processing
- **Document Processing**: PyPDF2, python-docx, pandas
- **Chunking**: Character-based splitting
- **Embeddings**: OpenAI API
- **Vector Storage**: Local JSON/database
- **Web Scraping**: Requests, BeautifulSoup4

### Testing & Reporting
- **Test Execution**: Playwright
- **Test Planning**: LLM-based (GPT-4)
- **Reporting**: Allure Reports
- **Result Format**: JSON, HTML, Markdown

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Docker Compose
- **File Storage**: Local filesystem
- **Cache/Queue**: Redis
- **Logging**: Python logging module

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  PDF Files   │  │ DOCX Files   │  │ Confluence   │              │
│  │              │  │              │  │ Jira URLs    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└──────────────┬──────────────────────────────────────────────────────┘
               │
        ┌──────▼────────┐
        │ Upload to API │
        └──────┬────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Extract Raw Content                  │
        │ (Text, images, tables, metadata)    │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Chunk Content                        │
        │ (Character-based: ~1000 chars)      │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Generate Embeddings                  │
        │ (OpenAI text-embedding-ada-002)     │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Store Embeddings + Metadata          │
        │ (Vectors, chunk text, source info)  │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Query Relevant Chunks (RAG)          │
        │ (Semantic search, similarity)       │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ LLM-Based Test Planning              │
        │ (GPT-4 generates test scenarios)    │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Generate Test Cases (JSON)           │
        │ (Test name, steps, assertions)      │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Execute Tests with Playwright        │
        │ (Browser automation, screenshots)   │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Generate Allure Report               │
        │ (Test results, metrics, artifacts)  │
        └──────┬──────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │ Store Artifacts in reports/          │
        │ (JSON, HTML, screenshots)           │
        └──────────────────────────────────────┘
```

---

## Scalability & Performance Considerations

### Horizontal Scaling
- **Multiple Celery Workers**: Process multiple documents in parallel
- **Redis Cluster**: Distribute cache and message queue
- **Load Balancer**: Distribute frontend/backend requests

### Performance Optimization
- **Embedding Caching**: Avoid re-embedding similar documents
- **Async Processing**: Non-blocking API responses
- **Batch Embedding**: Process multiple chunks at once
- **Report Caching**: Store generated reports for reuse

### High Availability
- **Job Persistence**: Store job metadata in database
- **Automatic Retries**: Celery task retry mechanisms
- **Error Handling**: Graceful degradation on service failures
- **Health Checks**: API health endpoint monitoring

---

## Security Considerations

- **API Authentication**: Future: JWT tokens, API keys
- **File Validation**: Whitelist file types, scan for malware
- **Input Sanitization**: Clean URLs, prevent injection attacks
- **Environment Variables**: Secure API key management (.env)
- **CORS Configuration**: Restrict cross-origin requests
- **Rate Limiting**: Prevent abuse and DoS attacks

---

## Future Enhancements

1. **Database Integration**: PostgreSQL for persistent job storage
2. **Authentication Layer**: User accounts, project isolation
3. **Advanced UI Dashboard**: Real-time job monitoring, analytics
4. **Custom LLM Models**: On-premise LLM instead of OpenAI
5. **Test Integration**: Jira board integration, automated updates
6. **Email Notifications**: Report delivery via email
7. **Webhooks**: Callback URLs for external systems
8. **Caching Strategy**: Redis for embeddings and results
9. **Monitoring & Logging**: Prometheus, ELK stack integration
10. **API Documentation**: OpenAPI/Swagger integration

---

## Deployment Guide

### Local Development
```bash
docker-compose up -d
# Services: Frontend (3000), Backend (8000), Redis (6379)
```

### Production Ready
- Use managed Redis (AWS ElastiCache)
- Use managed PostgreSQL database
- Deploy with Kubernetes for scaling
- Use CloudFront CDN for static assets
- Implement auto-scaling policies

---

## Environment Variables Configuration

```
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://...
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=50MB
CHUNK_SIZE=1000
EMBEDDING_BATCH_SIZE=100
```

---

## API Endpoints Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health` | Service health check |
| POST | `/api/upload` | Upload document file |
| POST | `/api/link` | Submit link (Confluence/Jira) |
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/{job_id}` | Get job details |
| GET | `/api/report/{job_id}` | Get report HTML |
| GET | `/api/testcases/{job_id}` | Get test cases |
| DELETE | `/api/jobs/{job_id}` | Delete job |

---

*Last Updated: 2025*
*For the full implementation details, refer to the README.md and documentation in the docs/ folder.*

