# AI Trading Agent — System Architecture

**Status:** Phase 0 — Architecture Definition  
**Version:** 1.0  
**Initial Market:** US Stocks  
**Initial Assets:** AAPL, NVDA, MSFT, AMZN, GOOGL

---

## 1. Architecture Overview

The system is designed as an AI-powered trading platform that continuously operates in the background.

The AI layer independently collects market and news information, analyzes it using traditional algorithms, NLP, ML models and LLM-based reasoning, and produces a trade proposal when the final confidence reaches the configured threshold.

The core backend is responsible for users, portfolios, risk management, trading execution, notifications and application-facing APIs.

The initial architecture uses:

- **Spring Boot** for the core backend.
- **Python + FastAPI** for the AI layer.
- **REST API** for communication between Spring Boot and Python.
- **Modular architecture** inside both applications.
- Separate logical storage for application/user data and analytics data.
- Paper trading for the initial implementation.

---

## 2. High-Level Architecture

```text
                         EXTERNAL DATA SOURCES
                    ┌────────────┴────────────┐
                    │                         │
               Market APIs                News APIs
                    │                         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    PYTHON AI LAYER      │
                    │                         │
                    │  Scheduler              │
                    │  Event Monitor          │
                    │  Data Collection        │
                    │  News / NLP             │
                    │  Market Analysis        │
                    │  ML Models              │
                    │  LLM                    │
                    │  Decision Agent         │
                    └────────────┬────────────┘
                                 │
                         Confidence >= 70%
                                 │
                                 ▼
                         TRADE PROPOSAL
                                 │
                              REST API
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     SPRING BOOT         │
                    │      CORE BACKEND       │
                    │                         │
                    │  Users                  │
                    │  Portfolio              │
                    │  Risk Engine            │
                    │  Trading Engine         │
                    │  Notifications          │
                    │  Application API        │
                    └────────────┬────────────┘
                                 │
                          User Approval
                                 │
                                 ▼
                         Paper Trading
                                 │
                                 ▼
                           DATABASES
```

---

## 3. Architectural Principle

The system separates **AI decision-making** from **application and trading control**.

### Python AI Layer

Responsible for:

- collecting information
- analyzing market conditions
- analyzing news
- NLP
- ML predictions
- LLM reasoning
- generating trade proposals

### Spring Boot Core

Responsible for:

- users
- authentication
- portfolio
- risk rules
- trade management
- paper trading
- notifications
- application APIs
- enforcing hard safety limits

The AI layer does **not** directly execute trades.

---

# 4. Python AI Layer

The Python application will be a single FastAPI service containing multiple internal modules.

```text
python-ai/
├── news/
├── nlp/
├── market_analysis/
├── ml/
├── llm/
├── decision/
├── scheduler/
└── event_monitor/
```

This is intentionally modular rather than creating multiple Python servers from the beginning.

Individual modules can later be extracted into independent services if the system grows.

---

## 4.1 Scheduler

The scheduler activates regular analysis cycles.

Initial target:

- market/news scan approximately every 30–60 minutes
- configurable in the future

Example:

```text
Scheduler
    ↓
Collect latest data
    ↓
Run analysis pipeline
```

The scheduler does not directly execute trades.

---

## 4.2 Event Monitor

The event monitor handles important events that should trigger analysis immediately rather than waiting for the next scheduled cycle.

Examples:

- breaking financial news
- major company announcements
- earnings events
- significant market movements
- abnormal volatility
- major economic events
- portfolio-related events

Example:

```text
Important Event
      ↓
Event Monitor
      ↓
Immediate AI Analysis
```

---

# 5. Market Data Module

The Market Data Module obtains market information from external providers.

Initial assets:

- AAPL
- NVDA
- MSFT
- AMZN
- GOOGL

The module should hide provider-specific implementation from the rest of the system.

Conceptually:

```text
External Market API
        ↓
Market Data Module
        ↓
Standardized Market Data
```

Other modules should not depend directly on the external provider.

---

# 6. News Module

The News Module collects and processes financial news.

Pipeline:

```text
News Sources
    ↓
News Collector
    ↓
Deduplication
    ↓
Relevance Filtering
    ↓
News Analysis
    ↓
Structured News Information
```

The system should avoid sending every available article directly to an LLM.

Only relevant information should reach deeper analysis stages.

---

# 7. NLP / News Analysis

NLP is used to extract useful information from financial news.

Potential outputs include:

- sentiment
- affected company/asset
- event type
- importance
- market impact
- relevant entities

Example:

```text
Asset: NVDA
Event: Earnings
Sentiment: Bullish
Importance: 0.91
```

NLP and LLM processing will be separated from the final trading decision.

---

# 8. Market Analysis Module

The Market Analysis Module evaluates market conditions using quantitative methods.

Potential analysis:

- price movement
- trend
- technical indicators
- volume
- volatility
- momentum
- market regime
- support/resistance
- risk/reward conditions

The module produces structured analysis that can later be consumed by the ML and Decision layers.

---

# 9. Machine Learning Module

The ML module is separate from the LLM.

Conceptual pipeline:

```text
Historical Market Data
        ↓
Feature Engineering
        ↓
ML Model
        ↓
Prediction
```

Example output:

```text
Asset: NVDA
Predicted Movement: +2.8%
Prediction Confidence: 0.76
```

The ML model does not directly decide BUY/SELL.

Its output is one input into the final decision process.

---

# 10. LLM / Decision Agent

The Decision Agent combines information from the other analysis components.

Inputs may include:

- market analysis
- technical analysis
- news analysis
- NLP results
- ML prediction
- current market conditions
- portfolio information
- active positions
- user configuration
- risk information

The Decision Agent produces:

- BUY
- SELL
- HOLD
- NO TRADE

It also produces:

- confidence
- reasoning
- proposed entry
- stop-loss
- take-profit
- relevant supporting factors
- risk observations

Example:

```text
Decision: BUY
Confidence: 82%

Reason:
Positive news, bullish market trend and
favorable technical conditions create a
potentially attractive setup.
```

The Decision Agent creates a **trade proposal**, not a directly executable trade.

---

# 11. Confidence Threshold

The initial system uses a configurable confidence threshold.

Initial target:

```text
Confidence >= 70%
        ↓
Trade Proposal
```

If confidence is below the threshold:

```text
Confidence < 70%
        ↓
NO TRADE
```

The threshold may later become configurable or adaptive.

---

# 12. Trade Proposal Flow

The AI layer independently searches for opportunities.

It does not wait for Spring Boot to tell it which asset to analyze.

Normal flow:

```text
Python Agent
     ↓
Collect Market Data
     ↓
Collect News
     ↓
Analyze
     ↓
ML + NLP + LLM
     ↓
Final Confidence
     ↓
Confidence >= Threshold?
     │
     ├── NO → Nothing happens
     │
     └── YES
            ↓
      Trade Proposal
            ↓
       REST API
            ↓
       Spring Boot
```

Example proposal:

```text
{
    symbol: "NVDA",
    action: "BUY",
    confidence: 0.82,
    suggestedEntry: "...",
    suggestedStopLoss: "...",
    suggestedTakeProfit: "...",
    reasoning: "..."
}
```

The exact API contract will be defined during implementation.

---

# 13. Spring Boot Core Backend

Spring Boot is responsible for the application and trading-control layer.

Conceptual modules:

```text
spring-backend/
├── users/
├── portfolio/
├── risk/
├── trading/
├── notifications/
├── api/
└── integration/
```

---

## 13.1 User Module

Responsible for:

- users
- authentication
- user settings
- risk preferences
- account configuration

---

## 13.2 Portfolio Module

Responsible for:

- available capital
- positions
- portfolio value
- exposure
- profit/loss
- portfolio history

Example:

```text
Initial Capital: $10,000

Cash: $6,400
NVDA: $1,500
AAPL: $1,000
MSFT: $1,100
```

The initial simulation capital is $10,000, while the production system should support arbitrary user-defined capital.

---

# 14. Risk Engine

The Risk Engine is an independent safety layer.

The AI does not have authority to bypass it.

The Risk Engine evaluates:

- risk per trade
- position size
- portfolio exposure
- daily loss limits
- user risk profile
- volatility
- active positions
- hard trading limits

Initial user risk options:

```text
1% → Low Risk
3% → Medium Risk
5% → High Risk
```

These settings should be configurable by the user.

---

## 14.1 Risk Decision

```text
AI Trade Proposal
        ↓
Risk Engine
        ↓
    ┌───┴────┐
    ↓        ↓
 APPROVED   BLOCKED
    ↓        ↓
 Trading    Reason
```

A blocked trade should provide a reason.

---

# 15. Daily Trading Limit

The system should support daily trading/loss limits.

When the configured daily limit is reached:

```text
Daily Limit Reached
        ↓
Stop automatic trading
        ↓
Notify User
```

The user may receive an option to manually override/re-enable trading according to the configured rules.

---

# 16. Trading Engine

The Trading Engine is responsible for executing approved trades.

Initial implementation:

```text
AI Proposal
     ↓
Risk Engine
     ↓
User Approval
     ↓
Paper Trading Engine
```

The paper trading engine should simulate:

- order creation
- order execution/fill
- positions
- closing positions
- profit/loss
- portfolio updates

Real broker integration is a future extension.

---

# 17. Manual Approval

Initial trading mode is manual.

Flow:

```text
AI finds opportunity
        ↓
Trade Proposal
        ↓
Notification
        ↓
User reviews analysis
        ↓
APPROVE / REJECT
        ↓
Risk Engine
        ↓
Paper Trade
```

The notification should provide access to the complete analysis, not only the BUY/SELL signal.

The system should also display:

- confidence
- expected percentages
- potential profit/loss
- risk information
- reasoning
- relevant news

---

# 18. Future Auto-Trading

Auto-trading is planned as a future capability.

Even in auto-trading mode:

```text
AI
 ↓
Trade Proposal
 ↓
Risk Engine
 ↓
Hard Limits
 ↓
Trading Engine
```

The AI should never bypass the Risk Engine.

---

# 19. HOLD / STOP Logic

The agent should be capable of monitoring active trades.

If new information appears after a trade is opened:

```text
New Event
    ↓
Re-analysis
    ↓
HOLD / CONTINUE
or
STOP / EXIT
```

For example:

- positive new information may support continuing a position
- negative information may suggest stopping
- changing market conditions may change the expected outcome

The exact rules will be refined during implementation and testing.

---

# 20. Notification Module

Notifications communicate important events to the user.

Examples:

```text
New Trade Opportunity
Trade Approved
Trade Rejected
Trade Closed
Daily Risk Limit Reached
Important Market Event
Active Trade Requires Attention
```

The mobile application will consume these notifications in a later phase.

---

# 21. Database Architecture

The system should avoid putting every type of data into one undifferentiated storage structure.

Initial logical separation:

```text
                 DATABASE LAYER
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
 Application Database         Analytics Database
          │                         │
          │                         │
 Users                         AI analyses
 Portfolio                     ML predictions
 Positions                     NLP results
 Trades                        News analysis
 Risk settings                 Historical analysis
 Notifications                 Model outputs
```

### Application Database

Source of truth for operational/application data.

### Analytics Database

Optimized for analytical and AI-related historical data.

Additional storage for raw market/news data may be introduced later if required.

The exact database technologies will be selected during the Tech Stack phase.

---

# 22. Communication Architecture

The main communication between Spring Boot and Python is REST-based.

```text
Spring Boot
     ↕
   REST API
     ↕
Python FastAPI
```

However, the direction of normal AI operation is important.

The Python AI Agent independently searches and analyzes data.

When it finds a sufficiently strong opportunity:

```text
Python
   ↓
Trade Proposal
   ↓
REST API
   ↓
Spring Boot
```

Spring Boot does not normally tell Python:

```text
"Analyze NVDA now."
```

Instead, Python runs its own scheduled/event-driven analysis.

---

# 23. Synchronous vs Asynchronous Processing

The architecture supports a hybrid approach.

### Synchronous REST

Useful for short operations that require an immediate response.

```text
Client
  ↓
Spring Boot
  ↓
Python
  ↓
Response
```

### Asynchronous Processing

Useful for long-running background analysis.

```text
Scheduler/Event
      ↓
Analysis Job
      ↓
Worker
      ↓
Python AI
      ↓
Result
```

The initial implementation does not need a complex message queue immediately.

The system should be designed so asynchronous job processing can be introduced when required.

---

# 24. Background Agent Architecture

The background agent is the central concept of the application.

### Scheduled Analysis

```text
Every 30–60 minutes
        ↓
Market + News collection
        ↓
Analysis
        ↓
Decision
```

### Event-Driven Analysis

```text
Important Event
       ↓
Event Monitor
       ↓
Immediate Analysis
       ↓
Decision
```

The two mechanisms coexist.

```text
                 AI AGENT
                    │
          ┌─────────┴─────────┐
          ↓                   ↓
    Scheduled Cycle      Event Trigger
          │                   │
          └─────────┬─────────┘
                    ↓
              AI Analysis
                    ↓
               Decision
```

---

# 25. Mobile Application

The mobile application is not part of the initial architecture implementation.

It will later act primarily as the user interface.

```text
Mobile App
     ↓
Spring Boot API
     ↓
Core System
```

The AI agent itself runs independently of the mobile application.

Therefore:

```text
User closes mobile app
        ↓
AI continues operating
        ↓
Important event/trade
        ↓
Notification
        ↓
User opens app
```

This preserves the original goal of the project: **the value of the application is the AI working in the background.**

---

# 26. Observability and Auditability

Because this is a financial decision-making system, the system should keep enough information to understand why a decision happened.

For important decisions we should be able to answer:

- What market data was available?
- Which news was analyzed?
- What sentiment was detected?
- What did the ML model predict?
- What confidence did the AI produce?
- Why did the Decision Agent choose BUY/SELL/HOLD?
- Why did the Risk Engine approve or block the trade?
- What happened after the trade?

This will require:

- structured logging
- error tracking
- metrics
- trade history
- AI decision records
- audit trail

Exact tooling will be decided during the Tech Stack phase.

---

# 27. Scalability Strategy

The initial architecture intentionally avoids unnecessary microservice complexity.

Current approach:

```text
Spring Boot
  └── Modular Core

Python FastAPI
  └── Modular AI Layer
```

Future extraction is possible:

```text
Current:
Python AI Service
├── NLP
├── ML
├── LLM
└── Decision

Future:
NLP Service
ML Service
LLM Service
Decision Service
```

A module should only become a separate service when there is a real reason to do so, such as:

- independent scaling
- different infrastructure requirements
- performance needs
- deployment independence
- team ownership
- reliability isolation

---

# 28. Key Architectural Decisions

| Decision | Current Choice |
|---|---|
| Initial Market | US Stocks |
| Backend | Spring Boot |
| AI/ML Layer | Python |
| Python API | FastAPI |
| Spring ↔ Python | REST |
| AI Architecture | Modular |
| Core Architecture | Modular Monolith |
| Background Processing | Scheduled + Event Driven |
| Normal AI Scan | ~30–60 minutes |
| Urgent Events | Immediate Analysis |
| Initial Confidence Threshold | >= 70% |
| Initial Trading | Manual Approval |
| Initial Trading Environment | Paper Trading |
| Initial Test Capital | $10,000 |
| Risk Profiles | 1%, 3%, 5% |
| Database Strategy | Application + Analytics separation |
| Mobile App | Future phase |
| Real Broker Trading | Future phase |

---

# 29. Architecture Evolution

The architecture is expected to evolve.

### V1

```text
Spring Boot
     ↕
REST
     ↕
Python FastAPI
```

with modular components.

### Future

```text
Spring Boot Core
       │
       ├── AI Services
       ├── Message Queue
       ├── Workers
       ├── Analytics Infrastructure
       └── Broker Integrations
```

The goal is to avoid premature complexity while keeping clean boundaries that allow future scaling.

---

# 30. Current Scope

This architecture document defines the logical architecture for Phase 0.

The following are intentionally left for later phases:

- exact database technology
- exact database schema
- exact market-data providers
- exact news providers
- LLM provider/model
- ML algorithms
- queue technology
- deployment infrastructure
- cloud provider
- authentication implementation
- mobile framework
- real broker integration
- production security configuration

These decisions will be documented separately when their respective phases begin.
