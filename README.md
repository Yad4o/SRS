# 🤖 Automated Customer Support Resolution System

> **AI-Powered Backend for Intelligent Ticket Classification & Resolution**

An enterprise-grade backend system that automatically classifies, resolves, and escalates customer support tickets using **FastAPI**, **Python**, and **Advanced NLP**, while ensuring safety through confidence-based decision making and human oversight.

---

## 📋 Table of Contents

- [🎯 Overview](#-overview)
- [✨ Key Features](#-key-features)
- [🏗️ System Architecture](#️-system-architecture)
- [🛠️ Technology Stack](#️-technology-stack)
- [⚙️ Background Workers](#️-background-workers)
- [📁 Project Structure](#-project-structure)
- [🔄 Ticket Lifecycle](#-ticket-lifecycle)
- [🧠 AI Pipeline](#-ai-pipeline)
- [🔐 Security Design](#-security-design)
- [📊 API Documentation](#-api-documentation)
- [🚀 Getting Started](#-getting-started)
- [🧪 Testing](#-testing)
- [🗃️ Database Migrations (Alembic)](#️-database-migrations-alembic)
- [👥 Development Team](#-development-team)
- [📜 License](#-license)

---

## 🎯 Overview

Customer support teams face overwhelming volumes of repetitive issues—login problems, payment failures, account queries—that consume valuable human agent time. This system automates **first-level support resolution** using cutting-edge AI while maintaining **100% safety** through confidence-based decision making.

### 🎯 Core Mission
- **Reduce repetitive workload** by 70-80%
- **Improve response times** from hours to seconds
- **Maintain human control** through conservative AI decisions
- **Ensure consistent quality** through proven solution reuse

### 🎯 Design Philosophy
- **Safety First**: Every automation decision is validated
- **Human-in-the-Loop**: Uncertain cases always escalate to agents
- **Clean Architecture**: Modular, testable, and maintainable code
- **Enterprise Ready**: Scalable, secure, and production-grade

---

## ✨ Key Features

### 🎫 Ticket Management
- **Intelligent Creation**: Automatic intent classification and confidence scoring
- **Smart Routing**: Confidence-based auto-resolution vs human escalation
- **Status Tracking**: Complete lifecycle from open to closed
- **Historical Analysis**: Learn from past resolutions

### 🧠 AI-Powered Automation
- **Intent Classification**: Advanced NLP for accurate issue categorization
- **Similarity Search**: Find and reuse proven solutions from past tickets
- **Response Generation**: Context-aware, safe, and helpful replies
- **Decision Engine**: Conservative confidence thresholds ensure safety

### 🔐 Security & Authentication
- **JWT-Based Auth**: Stateless, secure token authentication
- **Role-Based Access**: User, Agent, and Admin role hierarchy
- **Password Security**: bcrypt hashing with salt
- **API Protection**: Secure endpoints with proper authorization

### 📊 Monitoring & Analytics
- **Admin Dashboard**: System metrics and performance insights
- **Feedback Collection**: Quality measurement and improvement data
- **Escalation Tracking**: Monitor AI confidence and decision patterns
- **Performance Metrics**: Response times and resolution rates

---

## 🏗️ System Architecture

### 🏛️ Layered Architecture Design

```
┌─────────────────────────────────────────┐
│         Client Applications        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           FastAPI API Layer             │
│  • Request Validation & Response        │
│  • Authentication & Authorization       │
│  • Orchestration & Error Handling       │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Service Layer (AI Core)         │
│  • Intent Classification                │
│  • Similarity Search & Matching         │
│  • Response Generation                  │
│  • Decision Engine (Safety Gate)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           Data Layer (ORM)              │
│  • SQLAlchemy Models                    │
│  • Database Session Management          │
│  • Data Validation & Transformation     │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│            Database Layer               │
│  • SQLite (Development)                 │
│  • PostgreSQL / Neon (Production)       │
└─────────────────────────────────────────┘
```

### 🎯 Design Principles

- **Separation of Concerns**: Each layer has single, clear responsibility
- **API-First Backend**: Clean RESTful APIs with proper validation
- **AI Logic Isolation**: Business logic separate from HTTP handling
- **Safe Automation**: Conservative decision making with human fallback
- **Testability**: Every component designed for comprehensive testing

---

## 🛠️ Technology Stack

### 🚀 Backend Framework
- **Python 3.10+**: Modern Python with type hints
- **FastAPI**: High-performance async web framework
- **Uvicorn**: ASGI server for production deployment
- **Pydantic**: Data validation and serialization

### 🗄️ Database & ORM
- **SQLAlchemy**: Powerful ORM with relationship management
- **SQLite**: Lightweight database for development
- **PostgreSQL / Neon**: Enterprise-grade database for production
- **Alembic**: Database migration management

### 🧠 AI & NLP Stack
- **Rule-based Classification**: Fast, deterministic intent recognition
- **TF-IDF Vectorization**: Text similarity and matching
- **Cosine Similarity**: Mathematical similarity scoring
- **Extensible Design**: Ready for spaCy, OpenAI, or custom models

### 🔐 Security & Authentication
- **JWT (JSON Web Tokens)**: Stateless authentication
- **bcrypt**: Industry-standard password hashing
- **python-jose**: JWT token creation and validation
- **Role-Based Access Control**: Granular permission management

### 🧪 Testing & Quality
- **pytest**: Comprehensive testing framework
- **pytest-asyncio**: Async testing support
- **Mocking**: Deterministic AI response testing
- **Coverage**: Code quality measurement

---

## ⚙️ Background Workers

| Worker | Purpose | Command |
|--------|---------|---------|
| `cleanup.py` | Archive old tickets, remove orphaned feedback | `python workers/cleanup.py --days 90` |
| `embedding_builder.py` | Precompute TF-IDF vectors for similarity speedup | `python workers/embedding_builder.py` |
| `feedback_analyzer.py` | Aggregate feedback + quality scores per intent | `python workers/feedback_analyzer.py` |
| `metrics_collector.py` | System-wide stats snapshot | `python workers/metrics_collector.py` |

Add `--dry-run` to `cleanup.py` to preview changes without applying them.

---

## 📁 Project Structure

```
SRS/
├── 📄 README1.md                          # This comprehensive documentation
├── 📄 requirements.txt                     # Python dependencies
├── 📄 .env.example                        # Environment variables template
├── 📄 .gitignore                          # Git ignore patterns
├── 📄 alembic.ini                         # Alembic configuration
│
├── 📁 app/                                # Main application code
│   ├── 📄 main.py                         # FastAPI application entry point
│   │
│   ├── 📁 api/                            # HTTP API layer
│   │   ├── 📄 auth.py                     # Authentication endpoints
│   │   ├── 📄 tickets.py                  # Ticket lifecycle APIs
│   │   ├── 📄 feedback.py                 # Feedback submission APIs
│   │   └── 📄 admin.py                    # Admin & metrics APIs
│   │
│   ├── 📁 core/                           # Core application utilities
│   │   ├── 📄 config.py                   # Environment & app configuration
│   │   └── 📄 security.py                 # JWT & password utilities
│   │
│   ├── 📁 db/                             # Database configuration
│   │   └── 📄 session.py                  # SQLAlchemy engine & session
│   │
│   ├── 📁 models/                         # Database models (ORM)
│   │   ├── 📄 user.py                     # User entity and relationships
│   │   ├── 📄 ticket.py                   # Ticket entity and lifecycle
│   │   └── 📄 feedback.py                 # Feedback entity
│   │
│   ├── 📁 schemas/                        # Pydantic schemas (API contracts)
│   │   ├── 📄 user.py                     # User request/response schemas
│   │   ├── 📄 ticket.py                   # Ticket request/response schemas
│   │   └── 📄 feedback.py                 # Feedback request/response schemas
│   │
│   └── 📁 services/                       # Business & AI logic
│       ├── 📄 classifier.py               # Intent classification service
│       ├── 📄 similarity.py               # Similar ticket search service
│       ├── 📄 resolver.py                 # Response generation service
│       └── 📄 decision.py                 # Auto-resolve vs escalation logic
│
├── 📁 tests/                              # Comprehensive test suite
│   ├── 📁 unit/                           # Unit tests for individual components
│   ├── 📁 integration/                    # Integration tests for API endpoints
│   └── 📁 conftest.py                     # Pytest configuration and fixtures
│
├── 📁 workers/                            # Background job processing
│   ├── 📄 cleanup.py
│   ├── 📄 embedding_builder.py
│   ├── 📄 feedback_analyzer.py
│   └── 📄 metrics_collector.py
│
├── 📁 migrations/                         # Manual migration scripts
├── 📁 alembic/                            # Alembic auto-migrations (Phase 5+)
│
├── 📁 docs/                               # Documentation and specifications
│   ├── 📁 specification/                  # Technical specifications
│   └── 📁 tasks/                          # Development phases and tasks
│
└── 📁 scripts/                            # Deployment and utility scripts
```

### 🏛️ Architecture Rules

- **API Layer** (`app/api/`): HTTP handling and orchestration only
- **Service Layer** (`app/services/`): AI and business logic, no HTTP
- **Models** (`app/models/`): Database schema definition only
- **Schemas** (`app/schemas/`): Request/response validation only
- **Core** (`app/core/`): Shared utilities and configuration

---

## 🔄 Ticket Lifecycle

### 🎯 Complete Automation Flow

```
🎫 Ticket Created (OPEN)
         │
         ▼
🧠 Intent Classification
   • Analyze message content
   • Extract intent and confidence
         │
         ▼
🔍 Similarity Search
   • Find matching resolved tickets
   • Calculate similarity scores
         │
         ▼
⚖️ Decision Engine
   • Evaluate confidence threshold
   • Make safety-first decision
                 │
    ┌────────────┴───────────────┐
    │                            │
    ▼                            ▼
✅ AUTO_RESOLVE           ❌ ESCALATE
(Confidence ≥ 0.75)     (Confidence < 0.75)
    │                            │
    ▼                            ▼
💬 Generate Response    👤 Assign Human Agent
    │                            │
    ▼                            ▼
📝 Update Status        🔧 Manual Resolution
    │                            │
    ▼                            ▼
⭐ Collect Feedback       ✅ Close Ticket
```

### 🎯 Decision Rules

| Confidence Score | Action | Rationale |
|------------------|--------|-----------|
| **≥ 0.75** | **Auto-Resolve** | High confidence in AI prediction |
| **< 0.75** | **Escalate** | Conservative approach ensures safety |
| **Invalid/Missing** | **Escalate** | Default to human oversight |

### 🎯 Status Transitions

- **OPEN** → **AUTO_RESOLVED**: Successful AI automation
- **OPEN** → **ESCALATED**: Low confidence or AI failure
- **AUTO_RESOLVED** → **CLOSED**: After feedback collection
- **ESCALATED** → **CLOSED**: After human agent resolution

---

## 🧠 AI Pipeline

### 🎯 Intent Classification

**Purpose**: Understand what the user wants help with.

**Input**: Raw ticket message (e.g., "I can't login to my account")

**Output**:
```json
{
  "intent": "login_issue",
  "confidence": 0.92,
  "sub_intent": "password_reset"
}
```

**Supported Intents**:
- `login_issue`: Authentication and access problems
- `payment_issue`: Billing and transaction problems
- `account_issue`: Profile and account management
- `technical_issue`: System errors and bugs
- `feature_request`: New functionality requests
- `general_query`: General information requests
- `unknown`: Unclear or ambiguous requests

### 🏷️ Sub-Intent Classification

Each intent is further classified into a sub-intent that routes to a specific response template:

| Intent | Sub-intents |
|--------|-------------|
| login_issue | password_reset, account_locked, wrong_credentials |
| payment_issue | duplicate_charge, payment_declined, billing_question |
| account_issue | delete_account, update_info |
| technical_issue | crash_error, performance |
| feature_request | new_feature, improvement |
| general_query | how_to, pricing_plan |

### 🔍 Similarity Search

**Purpose**: Find proven solutions from past resolved tickets.

**Process**:
1. **Vectorize** new ticket message using TF-IDF
2. **Compare** against all resolved tickets
3. **Score** similarity using cosine similarity
4. **Return** best match above threshold (≥ 0.7)

**Output**:
```json
{
  "matched_text": "I cannot login to my account",
  "similarity_score": 0.81,
  "solution": "Please try resetting your password..."
}
```

### 💬 Response Generation

**Priority Order**:
1. **Reuse similar solution** if `quality_score ≥ 0.6` (source: `"similarity"`)
2. **OpenAI gpt-4o-mini** if key present (source: `"openai"`)
3. **Intent + sub-intent specific template** (source: `"template"`)
4. **Generic fallback** (source: `"fallback"`)

**Example Response**:
```
"It looks like you're having trouble logging in. 
Please try resetting your password using the 
'Forgot Password' option on the login page."
```

### ⚖️ Decision Engine

**Purpose**: Safety gate for automation decisions.

**Logic**:
```python
def decide_resolution(confidence: float) -> str:
    if confidence >= 0.75:
        return "AUTO_RESOLVE"
    else:
        return "ESCALATE"
```

**Safety Features**:
- **Conservative Threshold**: 0.75 ensures high confidence
- **Validation**: Invalid confidence → ESCALATE
- **Default Safe**: Any ambiguity → ESCALATE

---

## 🔐 Security Design

### 🔑 Authentication System

- **JWT Tokens**: Stateless, secure authentication
- **Token Payload**: User ID, role, expiration time
- **Secure Storage**: Tokens never stored server-side
- **Expiration**: Configurable token lifetime

### 🔒 Password Security

- **bcrypt Hashing**: Industry-standard password protection
- **Salt Generation**: Unique salt per password
- **No Plain Text**: Passwords never stored or logged
- **Secure Verification**: Hash comparison only

### 👥 Role-Based Access Control

| Role | Permissions | Use Case |
|------|-------------|----------|
| **user** | Create tickets, submit feedback | End customers |
| **agent** | + Assign escalated tickets to self, close tickets | Support agents |
| **admin** | + System metrics, all tickets | System administrators |

### 🛡️ AI Safety Controls

- **No Blind Trust**: AI predictions always validated
- **Conservative Decisions**: Escalate on uncertainty
- **No Direct System Changes**: AI outputs reviewed first
- **Fail-Safe Default**: AI failures → human escalation

---

## 📊 API Documentation

### 🔐 Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/auth/login` | User login and token issuance | ❌ |
| `POST` | `/auth/register` | New user registration | ❌ |

### 🎫 Ticket Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/tickets` | Create new support ticket | ✅ |
| `GET` | `/tickets` | List user tickets | ✅ |
| `GET` | `/tickets/{id}` | Get ticket details | ✅ |
| `POST` | `/tickets/{id}/assign` | Assign escalated ticket to self | Agent/Admin |
| `POST` | `/tickets/{id}/close` | Close a ticket | Agent/Admin |

### 👷 Worker Endpoints (non-production only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/demo/analytics` | Live system analytics |
| `GET` | `/demo/tickets` | All tickets data |
| `GET` | `/demo/users` | All users data |

These routes are only mounted when `ENV != production`.

### ⭐ Feedback Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/feedback` | Submit ticket feedback | ✅ |
| `GET` | `/feedback/{ticket_id}` | Get ticket feedback | ✅ |

### 📊 Admin Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/admin/metrics` | System performance metrics | 🔒 Admin |
| `GET` | `/admin/tickets` | List all system tickets | 🔒 Admin |

### 📝 Request/Response Examples

**Create Ticket**:
```json
POST /tickets
{
  "message": "I can't login to my account"
}

Response:
{
  "id": 123,
  "message": "I can't login to my account",
  "intent": "login_issue",
  "sub_intent": "password_reset",
  "confidence": 0.92,
  "status": "auto_resolved",
  "response": "Please try resetting your password...",
  "response_source": "similarity",
  "quality_score": null,
  "user_id": 1,
  "assigned_agent_id": null,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**User Login**:
```json
POST /auth/login
{
  "email": "user@example.com",
  "password": "securepassword"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

---

## 🚀 Getting Started

### 🔑 Key Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | — | JWT signing key (min 32 chars) |
| `DATABASE_URL` | ✅ | — | SQLite or PostgreSQL connection string |
| `OPENAI_API_KEY` | ❌ | None | Enables OpenAI response generation |
| `REDIS_URL` | ❌ | None | Enables similarity search caching |
| `CONFIDENCE_THRESHOLD_AUTO_RESOLVE` | ❌ | 0.75 | Min confidence to auto-resolve |
| `RATE_LIMIT_PER_MINUTE` | ❌ | 60 | POST /tickets rate limit per IP |

### 📋 Prerequisites

- **Python 3.10+**: Modern Python with type hints support
- **Git**: Version control for cloning repository
- **Virtual Environment**: Isolated Python environment (recommended)

### 🔧 Installation Steps

#### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yad4o/SRS.git
cd SRS
```

#### 2️⃣ Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate
```

#### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4️⃣ Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# SECRET_KEY=your-super-secret-key-here
# DATABASE_URL=sqlite:///./support.db
# CONFIDENCE_THRESHOLD_AUTO_RESOLVE=0.75
```

#### 5️⃣ Initialize Database
```bash
uvicorn app.main:app --reload
# Tables are auto-created on first startup via init_db()
```

#### 6️⃣ Start the Server
```bash
# Development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 🌐 Access Points

- **API Documentation**: http://127.0.0.1:8000/docs
- **Interactive Docs**: http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health
- **Root Endpoint**: http://127.0.0.1:8000/

### 🧪 Quick Test

```bash
# Test health endpoint
curl http://127.0.0.1:8000/health

# Expected response
{"status": "healthy", "timestamp": "2024-01-15T10:30:00Z"}
```

---

## 🧪 Testing

### 🎯 Testing Strategy

Our comprehensive testing approach ensures reliability, safety, and confidence in AI automation:

#### 🧪 Unit Tests
- **AI Services**: Test classification, similarity, and decision logic
- **Business Logic**: Validate response generation and safety rules
- **Utilities**: Test security functions and configuration
- **Edge Cases**: Boundary conditions and error scenarios

#### 🔗 Integration Tests
- **API Endpoints**: Full request/response cycles
- **Database Operations**: CRUD operations and relationships
- **Authentication**: Login, registration, and authorization
- **Ticket Lifecycle**: End-to-end automation flows

#### 🎭 Mocking Strategy
- **AI Responses**: Deterministic test outcomes
- **External Services**: No dependency on external APIs
- **Database**: In-memory SQLite for fast tests
- **Time**: Fixed timestamps for predictable results

### 🏃 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_classifier.py

# Run with verbose output
pytest -v

# Run integration tests only
pytest tests/integration/
```

### 📊 Test Coverage

- **Target Coverage**: 90%+ code coverage
- **Critical Paths**: 100% coverage for AI decision logic
- **Error Handling**: All error scenarios tested
- **Security**: Authentication and authorization fully tested

---

## 🗃️ Database Migrations (Alembic)

```bash
# Apply all migrations (first time or after pulling new changes)
alembic upgrade head

# Create a new migration after changing a model
alembic revision --autogenerate -m "description"

# Check current migration state
alembic current
```

For production, switch to Neon PostgreSQL: set `DATABASE_URL=postgresql://...` in `.env` and run `alembic upgrade head`.

---

## 👥 Development Team

### 🎯 Core Contributors

| Name | Role | Expertise | Responsibilities |
|------|------|-----------|------------------|
| **Om Yadav** | **AI/ML & Backend Engineer** | Machine Learning, System Design, APIs, Security | Model Integration, Backend Architecture, Authentication, Database Design, Documentation |
| **Prajwal** | **AI/ML & Backend Engineer** | NLP, Machine Learning, Decision Systems, APIs | Intent Classification, Similarity Search, Model Development, Backend Logic, API Integration |

### 🤝 Collaboration Model

- **Clean Architecture**: Modular design for parallel development
- **API Contracts**: Clear interfaces between components
- **Documentation**: Comprehensive technical specifications
- **Code Reviews**: Quality assurance and knowledge sharing

### 📧 Contact & Support

- **Project Repository**: https://github.com/yad4o/SRS
- **Documentation**: Comprehensive technical specs in `/docs/`
- **Issues**: Bug reports and feature requests via GitHub Issues
- **Discussions**: Community support and questions

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### 🎯 License Summary

- ✅ **Commercial Use**: Use in commercial projects
- ✅ **Modification**: Modify and distribute changes
- ✅ **Distribution**: Share with others
- ✅ **Private Use**: Use without disclosure
- ❌ **Liability**: No warranty or liability

---

## 🎯 Conclusion

The **Automated Customer Support Resolution System** represents a sophisticated approach to AI-assisted customer support that prioritizes:

- **🛡️ Safety**: Conservative decision making with human oversight
- **🏗️ Architecture**: Clean, modular, and maintainable design
- **🚀 Performance**: Fast, scalable, and production-ready
- **🧠 Intelligence**: Smart automation with proven reliability

This system demonstrates professional-grade backend development, responsible AI integration, and enterprise-ready system design—making it ideal for:

- **📁 Portfolio Projects**: Showcase advanced technical skills
- **💼 Technical Interviews**: Demonstrate system design expertise
- **🏢 Real-world Applications**: Production-ready support automation
- **👥 Team Collaboration**: Clear architecture for parallel development

**The future of customer support is here—intelligent, efficient, and always human-centered.** 🚀

---

<div align="center">

**⭐ Star this repository if you find it helpful!**

**🔄 Fork and contribute to make it even better!**

**📧 Questions? Open an issue or start a discussion!**

</div>
