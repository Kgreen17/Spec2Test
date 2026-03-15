# Spec2Test AI - Confluence/Jira Link Support

A Python/React application that converts specifications to automated tests using AI. Now with support for **document uploads**, **Confluence page links**, and **Jira ticket links**.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [Using the Feature](#using-the-feature)
- [Architecture](#architecture)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Implementation Details](#implementation-details)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 14+
- npm

### Get Running in 5 Minutes

```bash
# 1. Install dependencies
pip install -r requirements.txt
cd frontend && npm install --legacy-peer-deps

# 2. Start Backend (Terminal 1)
python3 -m uvicorn backend.app:app --reload --port 8000

# 3. Start Frontend (Terminal 2)
cd frontend && npm run dev

# 4. Open Browser
http://localhost:3000
```

---

## ✨ Features

### Input Methods

**📤 Upload Document** (Existing)
- PDF files
- Word documents (.docx)
- Excel spreadsheets (.xlsx, .csv)
- Text files (.txt, .md)

**🔗 Paste Link** (NEW)
- **Confluence Pages** - Cloud & Server instances
- **Jira Tickets** - Cloud & Server instances
- Public and private instances with API token auth
- Automatic content extraction

### Platform Support

✅ Confluence Cloud (atlassian.net)
✅ Confluence Server (on-premises)
✅ Confluence Data Center
✅ Jira Cloud (atlassian.net)
✅ Jira Server (on-premises)
✅ Jira Data Center

### Output

- Automated test cases in Playwright format
- Allure test reports
- JSON test plans
- CI/CD integration ready

---

## 📦 Setup & Installation

### Backend Setup

```bash
cd /Users/kevingreen/PycharmProjects/Spec2Test

# Install Python dependencies
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend

# Install Node dependencies
npm install --legacy-peer-deps

# For production build
npm run build
```

### Optional: Private Instance Authentication

For private Confluence/Jira instances, set environment variables:

```bash
export CONFLUENCE_USER="your-email@company.com"
export CONFLUENCE_TOKEN="your-api-token"
```

Get API token: https://id.atlassian.com/manage/api-tokens

---

## 🏃 Running the Application

### Development Mode

**Terminal 1 - Backend:**
```bash
cd /Users/kevingreen/PycharmProjects/Spec2Test
python3 -m uvicorn backend.app:app --reload --port 8000
```

Wait for: `Application startup complete`

**Terminal 2 - Frontend:**
```bash
cd /Users/kevingreen/PycharmProjects/Spec2Test/frontend
npm run dev
```

Wait for: `compiled successfully`

**Browser:**
```
http://localhost:3000
```

### Production Mode

```bash
# Build frontend
cd frontend
npm run build

# Start backend
cd ..
python3 -m uvicorn backend.app:app --port 8000 --host 0.0.0.0

# Serve frontend
cd frontend
npm run start
```

---

## 💡 Using the Feature

### Upload a Document

1. Open http://localhost:3000
2. Click **"📤 Upload Document"** tab (default)
3. Drag and drop a file or click to select
4. Click **"Upload & Start Pipeline"**
5. Monitor progress in "Pipeline Jobs" panel

### Submit a Confluence Link

1. Open http://localhost:3000
2. Click **"🔗 Paste Link"** tab
3. Paste a Confluence URL:
   ```
   https://your-domain.atlassian.net/wiki/spaces/KEY/pages/12345
   ```
4. Click **"Submit & Start Pipeline"**
5. Watch job appear in "Pipeline Jobs" panel

### Submit a Jira Link

1. Open http://localhost:3000
2. Click **"🔗 Paste Link"** tab
3. Paste a Jira URL:
   ```
   https://your-domain.atlassian.net/browse/PROJECT-123
   ```
4. Click **"Submit & Start Pipeline"**
5. Watch job appear in "Pipeline Jobs" panel

---

## 🏗️ Architecture

### System Flow

```
User Input (File OR URL)
    ↓
FastAPI Backend (/api/upload)
    ↓
Doc Loader (Handles both files and URLs)
    ↓
Link Extractor (For URLs only)
├─ Confluence API v2
├─ Jira REST API v2
└─ HTML parsing fallback
    ↓
Content Extraction & Cleaning
    ↓
Pipeline Processing
├─ Chunking
├─ Embeddings
└─ Test Generation
    ↓
Reports & Artifacts
```

### Technology Stack

**Frontend:**
- React 18
- TypeScript
- Next.js
- Tailwind CSS
- Axios for HTTP requests

**Backend:**
- FastAPI (Python)
- Celery for async tasks (optional)
- Redis for caching (optional)

**AI/LLM:**
- LangChain
- LlamaIndex
- OpenAI embeddings (or local)
- GPT models for test generation

**Document Processing:**
- PyPDF2 for PDF extraction
- python-docx for Word documents
- pandas for spreadsheets
- BeautifulSoup4 for HTML parsing

**Testing:**
- Playwright for test execution
- Allure for test reporting
- pytest for unit tests

---

## 📡 API Documentation

### Upload Endpoint

**Endpoint:** `POST /api/upload`

#### File Upload (Multipart Form)

```bash
curl -F "file=@document.pdf" http://localhost:8000/api/upload
```

**Headers:**
```
Content-Type: multipart/form-data
```

#### Link Submission (JSON)

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.atlassian.net/wiki/spaces/KEY/pages/12345"}' \
  http://localhost:8000/api/upload
```

**Headers:**
```
Content-Type: application/json
```

#### Response

```json
{
  "job_id": "uuid-string",
  "status": "queued"
}
```

### Other Endpoints

**Health Check:**
```bash
GET http://localhost:8000/api/health
```

**List Jobs:**
```bash
GET http://localhost:8000/api/jobs
```

**Get Job Details:**
```bash
GET http://localhost:8000/api/jobs/{job_id}
```

**Get Job Status:**
```bash
GET http://localhost:8000/api/status/{job_id}
```

**Allure Report:**
```bash
GET http://localhost:8000/api/allure-report
```

---

## ⚙️ Configuration

### Environment Variables

**Optional:**
```bash
# For private Confluence/Jira instances
CONFLUENCE_USER="your-email@company.com"
CONFLUENCE_TOKEN="your-api-token"

# Debugging
DEBUG=1
```

### File Locations

- **Backend:** `/Users/kevingreen/PycharmProjects/Spec2Test/backend/`
- **Frontend:** `/Users/kevingreen/PycharmProjects/Spec2Test/frontend/`
- **Link Extractor:** `/Users/kevingreen/PycharmProjects/Spec2Test/pipeline/ingestion/link_extractor.py`
- **Doc Loader:** `/Users/kevingreen/PycharmProjects/Spec2Test/pipeline/ingestion/doc_loader.py`
- **Uploads:** `/Users/kevingreen/PycharmProjects/Spec2Test/uploads/`
- **Reports:** `/Users/kevingreen/PycharmProjects/Spec2Test/reports/`

---

## 🔧 Troubleshooting

### Port Already in Use

**Port 8000 (Backend):**
```bash
lsof -i :8000 -t | xargs kill -9
```

**Port 3000 (Frontend):**
```bash
lsof -i :3000 -t | xargs kill -9
```

### Frontend Not Showing "Paste Link" Button

1. Hard refresh browser: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows)
2. Clear browser cache: F12 → Application → Clear storage
3. Check frontend is running: `npm run dev` output should show "compiled successfully"
4. Restart frontend: Kill process and run `npm run dev` again

### Backend Connection Error

1. Verify backend is running: `curl http://localhost:8000/api/health`
2. Check port 8000 is not in use: `lsof -i :8000`
3. Restart backend: Kill process and run uvicorn command again
4. Check logs for errors in terminal

### Link Not Extracting Content

1. Verify URL format is correct (copy from browser address bar)
2. For private instances, set CONFLUENCE_USER and CONFLUENCE_TOKEN
3. Check user has permission to view the page/ticket
4. Verify network connectivity to Confluence/Jira server
5. Check browser console (F12) for error details

### npm Install Issues

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npm run dev
```

---

## 📁 Project Structure

```
Spec2Test/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── Dockerfile                         # Docker configuration
├── docker-compose.yml                 # Docker Compose setup
│
├── backend/                           # FastAPI backend
│   ├── app.py                         # Main API server
│   ├── tasks.py                       # Celery tasks
│   ├── schemas.py                     # Data models
│   └── celery_app.py                  # Celery configuration
│
├── frontend/                          # React/Next.js frontend
│   ├── pages/
│   │   ├── index.tsx                  # Main UI page with dual input
│   │   └── _app.tsx                   # App wrapper
│   ├── styles/                        # CSS styles
│   ├── package.json                   # Node dependencies
│   ├── next.config.js                 # Next.js config
│   ├── tsconfig.json                  # TypeScript config
│   └── tailwind.config.js             # Tailwind config
│
├── pipeline/                          # ML/AI pipeline
│   ├── ingestion/
│   │   ├── doc_loader.py              # Document loading (files & URLs)
│   │   ├── link_extractor.py          # Confluence/Jira extraction
│   │   ├── chunker.py                 # Text chunking
│   │   └── embedder.py                # Embedding generation
│   ├── rag/                           # RAG implementation
│   ├── test_generator/                # Test generation
│   ├── agents/                        # AI agents
│   └── openai_utils.py                # LLM utilities
│
├── allure-report/                     # Test reports
├── allure-results/                    # Raw test results
├── reports/                           # Job reports
├── uploads/                           # Uploaded files
├── logs/                              # Application logs
│
├── main.py                            # Main entry point
├── Makefile                           # Build commands
├── run.sh                             # Run script
└── restart.sh                         # Restart script
```

---

## 🔗 Implementation Details

### Frontend Implementation

**File:** `frontend/pages/index.tsx`

**State Variables:**
- `inputMode` - Toggle between 'file' and 'link'
- `file` - Uploaded file
- `link` - Pasted link URL
- `jobs` - List of processing jobs
- `uploading` - Upload status
- `message` - Success messages
- `error` - Error messages

**Features:**
- Dual-mode toggle buttons (Upload Document / Paste Link)
- Conditional file upload form
- Conditional URL input form
- Pipeline jobs list with status tracking
- Real-time feedback and error handling

### Backend Implementation

**File:** `backend/app.py`

**Endpoints:**
- `POST /api/upload` - Accept files (multipart) or links (JSON)
- `GET /api/jobs` - List all jobs
- `GET /api/jobs/{job_id}` - Get job details
- `GET /api/status/{job_id}` - Get job status
- `GET /api/health` - Health check
- `GET /api/allure-report` - Allure report status

**Processing:**
- Multipart form support for file uploads
- JSON support for URL submissions
- Celery task queuing for async processing
- Synchronous fallback option
- Comprehensive error handling and logging

### Link Extractor Module

**File:** `pipeline/ingestion/link_extractor.py`

**Features:**
- Confluence API v2 integration
- Jira REST API v2 integration
- HTML parsing fallback for content extraction
- Content cleaning and normalization
- Authentication support (API tokens)
- Error handling and logging
- 15-second timeout for HTTP requests

**Functions:**
- `fetch_link_content(url, auth)` - Main entry point
- `fetch_confluence_content(url, auth)` - Confluence API fetching
- `fetch_jira_content(url, auth)` - Jira API fetching
- `fetch_confluence_from_html(url, auth)` - HTML parsing fallback
- `clean_html_content(content)` - Content cleaning

### Document Loader Integration

**File:** `pipeline/ingestion/doc_loader.py`

**Updates:**
- Added support for URL input alongside file paths
- Integrated with link_extractor for URL processing
- Maintained backward compatibility with existing file loading
- Automatic detection of input type (file vs URL)

---

## 🎯 Supported URL Formats

### Confluence

**Cloud (atlassian.net):**
```
https://domain.atlassian.net/wiki/spaces/{SPACEKEY}/pages/{PAGEID}
https://domain.atlassian.net/wiki/spaces/{SPACEKEY}/pages/{PAGEID}/{PageTitle}
```

**Server/Data Center:**
```
https://confluence.domain.com/display/{SPACEKEY}/
https://confluence.domain.com/pages/viewpage.action?pageId={PAGEID}&spaceKey={SPACEKEY}
```

### Jira

**Cloud (atlassian.net):**
```
https://domain.atlassian.net/browse/{PROJECT-123}
https://domain.atlassian.net/jira/software/projects/{PROJECT}/issues/{PROJECT-123}
```

**Server/Data Center:**
```
https://jira.domain.com/browse/{PROJECT-123}
```

---

## 🔐 Security

- ✅ No hard-coded credentials
- ✅ Environment variable-based authentication
- ✅ URL validation and sanitization
- ✅ HTTP timeout protection (15 seconds)
- ✅ Safe HTML parsing (BeautifulSoup4)
- ✅ Input validation
- ✅ Error message sanitization

---

## 📊 Implementation Status

- ✅ Document upload support (existing functionality)
- ✅ Confluence link extraction (NEW)
- ✅ Jira ticket extraction (NEW)
- ✅ Public instance support
- ✅ Private instance support with API token auth
- ✅ Comprehensive error handling
- ✅ Production-ready code
- ✅ Zero breaking changes
- ✅ Fully backward compatible
- ✅ Comprehensive documentation

---

## 🚀 Deployment

### Development Deployment

Follow the [Quick Start](#quick-start) section above.

### Production Deployment

1. Build frontend:
   ```bash
   cd frontend
   npm run build
   ```

2. Set environment variables if needed (for private instances)

3. Start backend:
   ```bash
   python3 -m uvicorn backend.app:app --port 8000 --host 0.0.0.0
   ```

4. Serve frontend:
   ```bash
   cd frontend
   npm run start
   ```

### Docker Deployment

```bash
docker-compose up
```

---

## 📞 Support & Help

### Quick Troubleshooting

1. **Hard refresh browser:** Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. **Check backend:** `curl http://localhost:8000/api/health`
3. **Check frontend:** Open http://localhost:3000
4. **Enable debug:** `export DEBUG=1`
5. **Check logs:** Look at terminal output

### Common Issues

**"Failed to fetch" error:**
- Backend not running
- Port 8000 in use
- Frontend trying wrong URL

**"No Paste Link button":**
- Hard refresh browser (Cmd+Shift+R)
- Clear browser cache
- Frontend not compiled yet (wait for "compiled successfully")

**Link not extracting content:**
- URL format incorrect
- Missing authentication credentials (for private instances)
- User doesn't have access to page/ticket
- Network connectivity issues

---

## 📝 Notes

- The Confluence/Jira link feature is production-ready
- All code is tested and validated
- Backend and frontend are fully integrated
- No new dependencies added (uses existing packages)
- Fully backward compatible
- Zero breaking changes
- Can be deployed anytime

---

## 📄 Additional Resources

- FastAPI Docs: http://localhost:8000/docs
- OpenAI Embeddings: https://platform.openai.com
- Confluence API: https://developer.atlassian.com/cloud/confluence/
- Jira API: https://developer.atlassian.com/cloud/jira/
- LangChain: https://python.langchain.com
- Playwright: https://playwright.dev
- Allure Reports: https://docs.qameta.io/allure/

---

## 📅 Version History

**v1.1.0** (March 15, 2026)
- ✨ Added Confluence/Jira link support
- ✨ Added dual-mode UI (Upload Document / Paste Link)
- ✨ Added link_extractor module (352 lines)
- 🔧 Updated doc_loader for URL support
- 📚 Comprehensive documentation
- 🔐 Security validation and authentication support

**v1.0.0**
- Initial release with document upload support

---

## 👥 Author

Developed with ❤️ using Python, React, and AI

**Last Updated:** March 15, 2026
**Status:** Production Ready ✅

