# support-resolution-system
# 🤖 Automated Customer Support Resolution System

An AI-powered backend system that automatically classifies, resolves, and escalates customer support tickets using **FastAPI**, **Python**, and **NLP**, while safely routing uncertain cases to human agents.

---

## 📌 Overview

Customer support teams handle a large number of repetitive issues such as login problems, payment failures, and account-related queries.  
This system automates **first-level support resolution** using AI while ensuring safety through confidence-based decision making.

The system is designed with **clean architecture**, **modularity**, and **real-world scalability** in mind.

---

## 👥 Team

| Member | Role |
|------|-----|
| **Om Yadav** | Backend architecture, APIs, database, authentication |
| **Prajwal** | AI / NLP logic, similarity search, decision engine |

---

## 🧠 Key Features

- Create and manage support tickets
- Intent classification using NLP
- Similarity search with past resolved tickets
- Automated response generation
- Confidence-based auto-resolution vs escalation
- User feedback collection
- Admin-level system metrics
- JWT-based authentication

---

## 🏗️ Architecture

Client
↓
FastAPI (API Layer)
↓
Service Layer (AI & Decision Logic)
↓
Data Layer (SQLAlchemy ORM)
↓
Database

yaml
Copy code

### Design Principles
- Separation of concerns
- API-first backend
- AI logic isolated from control flow
- Safe automation with escalation fallback

---

## 🛠️ Tech Stack

### Backend
- Python 3.10+
- FastAPI
- Uvicorn

### Database
- SQLAlchemy ORM
- SQLite (development)
- PostgreSQL (production-ready)

### AI / NLP
- Rule-based intent classification (MVP)
- TF-IDF similarity search
- Extensible to spaCy / OpenAI / LLMs

### Security
- JWT authentication
- Password hashing with bcrypt

---

## 📁 Project Structure

The project follows a clean, layered architecture where each layer has a
single responsibility.

app/
├── main.py # Application entry point
│
├── api/ # HTTP API layer (FastAPI routes)
│ ├── auth.py # Authentication endpoints
│ ├── tickets.py # Ticket lifecycle APIs
│ ├── feedback.py # Feedback submission APIs
│ └── admin.py # Admin & metrics APIs
│
├── core/ # Core application utilities
│ ├── config.py # Environment & app configuration
│ └── security.py # JWT & password utilities
│
├── db/ # Database configuration
│ └── session.py # SQLAlchemy engine & session
│
├── models/ # Database models (ORM)
│ ├── user.py
│ ├── ticket.py
│ └── feedback.py
│
├── schemas/ # Pydantic schemas (API contracts)
│ ├── user.py
│ ├── ticket.py
│ └── feedback.py
│
├── services/ # Business & AI logic (no FastAPI here)
│ ├── classifier.py # Intent classification
│ ├── similarity.py # Similar ticket search
│ ├── resolver.py # Response generation
│ └── decision.py # Auto-resolve vs escalation logic
│
tests/ # Unit & integration tests
workers/ # Background jobs (future use)


### Architecture Rule
- **API layer** → orchestrates requests
- **Service layer** → contains AI & business logic
- **Models** → define database structure
- **Schemas** → define request/response contracts


---

## 🔄 Ticket Lifecycle

OPEN
↓
Intent Classification
↓
Similarity Matching
↓
Decision Engine
↓
AUTO_RESOLVED ──► Feedback
↓
ESCALATED ──► Human Agent

yaml
Copy code

---

## 📦 API Endpoints

### Authentication
| Method | Endpoint | Description |
|------|---------|------------|
| POST | `/auth/login` | Authenticate and get JWT token |

### Tickets
| Method | Endpoint | Description |
|------|---------|------------|
| POST | `/tickets` | Create a new support ticket |
| GET | `/tickets/{id}` | Fetch ticket details |
| POST | `/tickets/{id}/resolve` | Trigger automated resolution |

### Feedback
| Method | Endpoint | Description |
|------|---------|------------|
| POST | `/feedback/{ticket_id}` | Submit feedback |

### Admin
| Method | Endpoint | Description |
|------|---------|------------|
| GET | `/admin/metrics` | System metrics |

---

## 🧠 AI Decision Logic

### Intent Output Example
```json
{
  "intent": "login_issue",
  "confidence": 0.82
}
Resolution Rules
Confidence Score	Action
≥ 0.75	Auto Resolve
< 0.75	Escalate to Human

This ensures safe and conservative automation.

🚀 Getting Started
Clone the Repository
bash
Copy code
git clone https://github.com/<your-username>/support-resolution-system.git
cd support-resolution-system
Create Virtual Environment
bash
Copy code
python -m venv venv
venv\Scripts\activate   # Windows
Install Dependencies
bash
Copy code
pip install -r requirements.txt
Environment Variables
Create a .env file:

env
Copy code
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./support.db
Run the Server
bash
Copy code
uvicorn app.main:app --reload
Swagger UI:

arduino
Copy code
http://127.0.0.1:8000/docs
🧪 Testing
Unit tests for AI services

API endpoint tests

Mocked AI responses

Edge-case testing for confidence thresholds

📈 Future Enhancements
Vector databases (FAISS)

Background workers (Celery)

LLM-based responses

Multi-language support

Voice-based ticket input

Continuous learning from feedback

💼 Resume Highlight
Built an AI-powered automated customer support resolution backend using FastAPI and Python, implementing intent classification, similarity search, confidence-based decision logic, and safe human escalation workflows.

📜 License
MIT License