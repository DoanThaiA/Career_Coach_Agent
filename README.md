# ThaiDQ Agent 🤖

A robust, multi-agent AI system built with FastAPI, LangChain, and LangGraph. The project is designed to facilitate automated interviews and evaluations using a collection of specialized AI agents.

## 🌟 Key Features

- **Multi-Agent Architecture**: Built on top of LangGraph for complex agent workflows.
  - `Interview Agent`: Handles interactive, intelligent interviewing.
  - `Evaluation Agent`: Evaluates responses and provides objective assessments.
- **FastAPI Integration**: High-performance, asynchronous REST API to interface with the agents.
- **Document Processing**: Ability to read and process PDF (`PyMuPDF`) and Word documents (`python-docx`).
- **Observability**: Integrated with [Langfuse](https://langfuse.com/) for LLM tracing and analytics.
- **Robust Infrastructure**: Includes Redis, RabbitMQ, MongoDB, and Qdrant (Vector Database) for data storage, message queuing, and state management.

## 🛠️ Technology Stack

- **Core**: Python 3.12+, FastAPI, Uvicorn
- **AI/LLM**: LangChain, LangGraph, OpenAI, Sentence-Transformers
- **Databases & Queues**: MongoDB (Motor), Redis, RabbitMQ, Qdrant
- **Observability**: Langfuse
- **Testing**: Pytest, Pytest-asyncio
- **Dependency Management**: `uv` / `pyproject.toml`

## 🚀 Getting Started

### 1. Prerequisites

Make sure you have Docker, Docker Compose, and Python 3.12+ installed.

### 2. Infrastructure Setup

Start the required backing services (MongoDB, Redis, RabbitMQ, Qdrant, and Langfuse) using Docker Compose:

```bash
docker-compose up -d
```

### 3. Environment Variables

Create a `.env` file in the root directory based on the configuration variables needed (e.g., OpenAI API Key, MongoDB URI, Langfuse credentials). 

### 4. Installation

Install the dependencies. The project uses standard Python packaging (`pyproject.toml`), but if you are using `uv`:

```bash
uv sync
```

Alternatively, with `pip`:
```bash
pip install -e .
```

### 5. Running the Application

Start the FastAPI development server:

```bash
python main.py
```

The API will be available at `http://localhost:8000`. You can access the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

## 📁 Project Structure

```text
.
├── docker-compose.yml      # Infrastructure services definition
├── main.py                 # FastAPI application entry point
├── pyproject.toml          # Project dependencies and configuration
├── README.md               # Project documentation
├── src/                    # Source code
│   ├── agents/             # LangGraph agent definitions
│   │   ├── evaluation_agent/
│   │   └── interview_agent/
│   ├── api/                # FastAPI routes, schemas, and app configuration
│   └── ...                 # Core logic, services, utilities
└── tests/                  # Pytest test suites
```

## 🧪 Testing

Run the test suite using pytest:

```bash
pytest
```
