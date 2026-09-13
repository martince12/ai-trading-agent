# AI Trading Agent — Tech Stack

**Status:** Phase 0 — Final Technology Decisions
**Initial Market:** US Stocks
**Architecture:** Hybrid Spring Boot + Python AI Service

---

## 1. Core Backend

### Java

The core backend will be implemented in Java.

Java is used for the application and trading-control layer.

### Spring Boot

Spring Boot will be responsible for:

* REST API
* users
* authentication
* portfolio management
* trading logic
* risk management
* paper trading
* notifications
* application settings
* communication with the Python AI layer

The Spring Boot application will use a modular monolith architecture with clearly separated internal modules.

---

## 2. AI / ML Service

### Python

Python will be used for all AI, ML, NLP and analytical functionality.

The Python service will be structured into internal modules rather than being implemented as multiple independent servers from the beginning.

Planned modules include:

* market analysis
* news processing
* NLP
* machine learning
* LLM integration
* decision agent
* scheduling
* event monitoring

---

## 3. Python API Framework

### FastAPI

FastAPI will expose the Python AI functionality through REST APIs.

It will be used for communication between:

```text
Spring Boot
     ↕
   REST API
     ↕
Python FastAPI
```

The Python AI layer will also run its own scheduled and event-driven analysis processes independently of Spring Boot.

---

## 4. Spring Boot ↔ Python Communication

### REST API

The initial communication protocol between Spring Boot and Python will be REST.

Normal AI flow:

```text
Python AI Agent
      ↓
Finds trading opportunity
      ↓
Creates Trade Proposal
      ↓
REST API
      ↓
Spring Boot
      ↓
Risk Validation
      ↓
User Approval / Trading Engine
```

A dedicated message broker is not required for the initial version.

The architecture should allow asynchronous communication to be introduced later if necessary.

---

## 5. Machine Learning Stack

The initial machine-learning stack will use:

* NumPy
* pandas
* scikit-learn
* XGBoost

### Initial Model Strategy

The project should begin with simple and measurable baseline models.

Planned progression:

```text
Historical Data
      ↓
pandas / NumPy
      ↓
Feature Engineering
      ↓
Baseline Model
      ↓
XGBoost
      ↓
Evaluation
```

Initial models may include:

* Logistic Regression
* Random Forest
* XGBoost

The goal is to compare more advanced models against simple baselines rather than assuming that a more complex model is automatically better.

---

## 6. Deep Learning

### PyTorch

PyTorch will not be required for the first ML implementation.

It is reserved for later experimentation with:

* neural networks
* advanced time-series models
* transformers
* custom deep-learning architectures

PyTorch should only be introduced when there is a clear reason to use deep learning.

---

## 7. LLM Integration

The initial version will use a cloud-hosted LLM API.

Local LLM models are outside the scope of V1.

### Provider Abstraction

The AI layer should not be tightly coupled to one specific LLM provider.

A provider abstraction should be introduced so the Decision Agent depends on a generic interface rather than a specific model.

Conceptually:

```text
Decision Agent
      ↓
LLM Provider Interface
      ↓
Cloud LLM Provider
```

Future implementations may support:

* alternative cloud providers
* multiple models
* local models
* specialized financial models

The exact provider and model should remain configurable.

---

## 8. Application Database

### PostgreSQL

PostgreSQL will be the primary relational database.

It will store operational application data such as:

* users
* portfolios
* positions
* orders
* trades
* risk settings
* notifications
* application settings

PostgreSQL is selected because the trading domain contains strong relationships and requires reliable transactional behavior.

---

## 9. Analytics Database

The analytics layer will initially also use PostgreSQL, logically separated from the application database.

It will store data such as:

* AI analyses
* ML predictions
* NLP results
* news analysis
* historical model results
* trading-decision history
* analytical metadata

PostgreSQL `JSONB` may be used for flexible AI and analytical outputs.

Future analytics storage may include specialized technologies if the data volume becomes large enough to justify them.

Possible future options include:

* TimescaleDB
* ClickHouse
* object storage

These are not required for V1.

---

## 10. Redis

### Redis

Redis will be used as a fast temporary data and caching layer.

Potential uses include:

* caching market data
* caching recent analysis
* temporary application state
* rate limiting
* distributed locking
* background-job coordination

Redis is not the source of truth for persistent trading or user data.

---

## 11. Background Processing

The Python AI layer will run scheduled and event-driven background jobs.

Initial scheduled cycle:

```text
Every 30–60 minutes
        ↓
Collect Market Data
        ↓
Collect News
        ↓
Filter Relevant Information
        ↓
Run Analysis
        ↓
ML / NLP / LLM
        ↓
Decision
```

Urgent events may trigger immediate analysis.

Examples include:

* breaking financial news
* earnings announcements
* major economic events
* significant price movements
* abnormal volatility

A dedicated message broker is not required initially.

Future versions may introduce:

* job queues
* dedicated workers
* RabbitMQ
* other queue technologies

Kafka is not required for V1.

---

## 12. Containerization

### Docker

Docker will be used to containerize the main system components.

Initial containers:

* Spring Boot Core Backend
* Python FastAPI AI Service
* PostgreSQL
* Redis

---

## 13. Local Orchestration

### Docker Compose

Docker Compose will be used for local development.

The development environment should eventually be startable with:

```bash
docker compose up
```

Conceptually:

```text
Docker Compose
│
├── Spring Boot
├── Python FastAPI
├── PostgreSQL
└── Redis
```

Kubernetes is not required for the initial project.

---

## 14. Testing — Java

The Java testing stack will use:

### JUnit 5

Used for:

* unit tests
* service tests
* business-logic tests

### Mockito

Used for:

* mocking dependencies
* isolated service testing

### Spring Boot Test

Used for:

* integration testing
* REST API testing
* repository testing
* Spring context testing

---

## 15. Testing — Python

### pytest

pytest will be the primary testing framework for the Python AI service.

It will be used for:

* unit tests
* data-processing tests
* NLP tests
* ML-pipeline tests
* API tests
* Decision Agent tests

### pytest-asyncio

May be introduced when asynchronous Python functionality requires dedicated testing.

---

## 16. API Development and Manual Testing

### Postman

Postman will be used during development for manual API testing.

It will help test:

* Spring Boot endpoints
* Python FastAPI endpoints
* Spring ↔ Python communication
* trade proposal flows
* risk-engine endpoints

Automated tests should still be preferred for repeatable validation.

---

## 17. Python Code Quality

### Ruff

Ruff will be used for Python linting and code-quality checks.

### Black

Black will be used for consistent Python code formatting.

---

## 18. Version Control

### Git

Git will be used for source-control management.

### GitHub

GitHub will be used for:

* repository hosting
* version history
* documentation
* collaboration
* issues
* future CI/CD

---

## 19. CI/CD

### GitHub Actions

GitHub Actions is planned for later phases.

Potential responsibilities include:

* Java tests
* Python tests
* linting
* build verification
* Docker image builds
* deployment automation

CI/CD is not required to complete the first development phases.

---

## 20. Secrets and Configuration

Environment-specific configuration should not be hard-coded.

The project will use environment variables for values such as:

* API keys
* database credentials
* Redis configuration
* LLM credentials
* external data-provider credentials

Local development may use `.env` files.

`.env` files containing secrets must never be committed to Git.

---

## 21. Future Mobile Application

The mobile application is outside the current implementation scope.

The planned direction is:

### React Native

React Native may be used later to build a shared Android and iOS application.

The mobile app will communicate only with the Spring Boot backend.

It will not communicate directly with the Python AI service.

Conceptually:

```text
Mobile App
    ↓
Spring Boot
    ↓
Core System / AI Integration
```

---

## 22. Tech Stack Summary

| Area                    | Technology                         |
| ----------------------- | ---------------------------------- |
| Core Backend            | Java                               |
| Backend Framework       | Spring Boot                        |
| AI / ML Language        | Python                             |
| Python API              | FastAPI                            |
| Communication           | REST                               |
| ML Data Processing      | NumPy, pandas                      |
| ML Frameworks           | scikit-learn, XGBoost              |
| Deep Learning Later     | PyTorch                            |
| LLM                     | Cloud LLM API                      |
| LLM Architecture        | Provider abstraction               |
| Application Database    | PostgreSQL                         |
| Analytics Database      | PostgreSQL                         |
| Flexible Analytics Data | PostgreSQL JSONB                   |
| Cache / Temporary State | Redis                              |
| Background Processing   | Python scheduled/event-driven jobs |
| Message Broker          | Not required for V1                |
| Containers              | Docker                             |
| Local Orchestration     | Docker Compose                     |
| Java Testing            | JUnit 5, Mockito, Spring Boot Test |
| Python Testing          | pytest                             |
| API Testing             | Postman                            |
| Python Linting          | Ruff                               |
| Python Formatting       | Black                              |
| Version Control         | Git                                |
| Repository Hosting      | GitHub                             |
| CI/CD Later             | GitHub Actions                     |
| Mobile Later            | React Native                       |

---

## 23. Technologies Intentionally Not Required for V1

The following technologies are intentionally excluded from the initial version unless a concrete need appears:

* Kubernetes
* Kafka
* multiple AI microservices
* local LLM infrastructure
* GPU servers
* dedicated analytical databases
* real broker integration
* complex distributed message systems

The project should introduce new infrastructure only when it solves a real technical requirement.

---

## 24. Engineering Principle

The technology stack should remain as simple as possible while supporting the system's real requirements.

The project should prioritize:

* clean architecture
* modularity
* testability
* maintainability
* measurable AI performance
* reliable risk controls
* future scalability

Technology should be added because the system needs it, not simply because it makes the architecture appear more complex.
