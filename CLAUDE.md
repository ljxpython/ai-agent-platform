# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication Guidelines

**重要**: 在与开发者交流时，请使用中文进行所有对话和解释。这是一个中文开发团队的项目，使用中文能够确保更好的沟通效果和理解。代码注释、文档和变量命名可以保持英文，但所有的交流、解释、建议都应该用中文表达。

## Project Overview

AITestLab is an AI-driven testing platform that combines multiple AI agents for test automation. It's a full-stack application with Python FastAPI backend and React TypeScript frontend.

**Key Technologies:**
- Backend: Python 3.12+, FastAPI, Tortoise ORM, AutoGen 0.5.7, LlamaIndex, Milvus
- Frontend: React 18, TypeScript, Ant Design Pro, Vite
- AI: Multiple LLM models (DeepSeek, Qwen-VL, UI-TARS), multi-agent collaboration
- Database: SQLite/MySQL/PostgreSQL support, vector database (Milvus)
- Tools: Poetry, Aerich migrations, pytest

## Common Development Commands

### Environment Setup
```bash
# Install all dependencies
make install

# Install backend only
make install-backend

# Install frontend only
make install-frontend
```

### Development Server
```bash
# Start all services
make start

# Start backend only (runs on port 8000)
make start-backend

# Start frontend only (runs on port 3000)
make start-frontend

# Stop all services
make stop
```

### Code Quality
```bash
# Backend linting and formatting
poetry run black backend/ --check
poetry run isort backend/ --check-only

# Frontend linting
cd frontend && npm run lint

# Run all tests
make test

# Run tests with coverage
make test-coverage
```

### Database Management
```bash
# Initialize database
make init-db

# Create migration
make makemigrations

# Apply migrations
make migrate

# Reset database
make reset-db
```

### Common Poetry Commands
```bash
# Add dependency
make add-dep DEP=package_name

# Add dev dependency
make add-dev-dep DEP=package_name

# Remove dependency
make remove-dep DEP=package_name

# Show dependencies
make poetry-show

# Update dependencies
make poetry-update
```

## Architecture Overview

### Backend Architecture (FastAPI)

The backend follows a layered architecture with clear separation of concerns:

```
backend/
├── __init__.py          # Factory pattern app creation
├── main.py              # Application entry point
├── api/v1/              # API route handlers
├── controllers/         # Business logic controllers
├── services/            # Service layer (business modules)
│   ├── ai_chat/         # AI conversation module
│   ├── testcase/        # Test case generation module
│   ├── ui_testing/      # UI testing agents (Midscene)
│   ├── rag/             # RAG knowledge base system
│   ├── auth/            # Authentication & authorization
│   └── document/        # Document processing
├── models/              # Database models (Tortoise ORM)
├── ai_core/             # AI framework (AutoGen integration)
├── rag_core/            # RAG system core
├── api_core/            # API utilities (CRUD, responses, etc.)
└── conf/                # Configuration management
```

**Key Components:**
- **AI Core Framework**: Multi-agent orchestration with AutoGen 0.5.7
- **RAG System**: LlamaIndex + Milvus for knowledge retrieval
- **Service Layer**: Business logic organized by domain
- **API Core**: Reusable utilities for CRUD operations and responses

### Frontend Architecture (React)

```
frontend/src/
├── App.tsx              # Root component
├── main.tsx             # Application entry
├── pages/               # Page components
│   ├── ChatPage.tsx     # AI chat interface
│   ├── TestCasePage.tsx # Test case generation
│   └── HomePage.tsx     # Dashboard
├── components/          # Reusable UI components
├── services/            # API integration layer
├── hooks/               # Custom React hooks
├── types/               # TypeScript type definitions
└── utils/               # Utility functions
```

### AI Agent Architecture

The platform uses multiple specialized AI agents:

1. **AI Chat Module**: General-purpose conversation agents
2. **Test Case Generation**: Requirement analysis → Test case creation → Quality review
3. **UI Testing (Midscene)**: UI analysis → Interaction design → Script generation
4. **RAG Integration**: Knowledge-enhanced responses across all modules

## Key Design Patterns

### Backend Patterns

1. **Factory Pattern**: App creation in `backend/__init__.py`
2. **Service Layer Pattern**: Business logic in `services/` modules
3. **Repository Pattern**: Data access through Tortoise ORM models
4. **Dependency Injection**: FastAPI dependencies for auth/permissions

### AI Framework Patterns

1. **Agent Factory**: Create and manage AI agents through `ai_core/factory.py`
2. **Runtime Management**: Agent lifecycle in `ai_core/runtime.py`
3. **Message Queue**: Async communication in `ai_core/message_queue.py`
4. **Memory Management**: Conversation context in `ai_core/memory.py`

## Development Guidelines

### Adding New Features

1. **Backend Service**: Create in `services/` following existing patterns
2. **API Endpoints**: Add routes in `api/v1/` with proper validation
3. **Database Models**: Define in `models/` with Tortoise ORM
4. **AI Agents**: Use `ai_core` framework for agent development
5. **Frontend Pages**: Add in `pages/` with TypeScript interfaces

### Code Conventions

**Python (Backend):**
- Use Black for formatting (line length: 88)
- Use isort for import organization
- Follow PEP 8 naming conventions
- Add type hints for all functions
- Use async/await for database operations

**TypeScript (Frontend):**
- Use PascalCase for components
- Use camelCase for variables/functions
- Define interfaces for all data structures
- Use React hooks for state management

### Testing Strategy

**Backend Testing:**
- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- E2E tests in `tests/e2e/`
- Use pytest with async support
- Mock external services (AI APIs, databases)

**Frontend Testing:**
- Component tests with React Testing Library
- Integration tests for API calls
- E2E tests with Playwright (in `uitest/`)

## Configuration Management

### Environment Configuration

Configuration is managed through `backend/conf/settings.yaml`:



### Key Configuration Files

- `backend/conf/settings.yaml`: Main application config
- `pyproject.toml`: Python dependencies and tool configuration
- `frontend/package.json`: Frontend dependencies and scripts
- `Makefile`: Development commands and automation

## Database Schema

### Core Models

**Users & Auth:**
- `User`: User accounts and profiles
- `Role`: Role-based permissions
- `Department`: Organizational structure

**AI Modules:**
- `Chat`: AI conversation records
- `Testcase`: Generated test cases
- `Project`: Test projects and organization
- `UiTask`: UI testing tasks and results

**System:**
- `RagFile`: RAG document management
- `MidsceneTask`: UI automation tasks

### Database Migration

Uses Aerich for migrations:
```bash
# Configure in pyproject.toml
[tool.aerich]
tortoise_orm = "backend.api_core.database.TORTOISE_ORM"
location = "./migrations"
```

## API Patterns

### Standard Response Format

```python
from backend.api_core.response import success_response, error_response

# Success response
return success_response(
    data=result_data,
    message="Operation successful"
)

# Error response
return error_response(
    message="Error description",
    error_code="SPECIFIC_ERROR_CODE"
)
```

### Authentication & Authorization
### SSE (Server-Sent Events) for Streaming

```python
from fastapi.responses import StreamingResponse
from backend.ai_core import get_streaming_sse_messages_from_queue

async def stream_ai_response(conversation_id: str):
    async def generate():
        async for message in get_streaming_sse_messages_from_queue(conversation_id):
            yield f"data: {message}\n\n"

    return StreamingResponse(generate(), media_type="text/plain")
```

## AI Development Patterns

### Creating AI Agents

```python
from backend.ai_core import create_assistant_agent, get_default_client

# Create an assistant agent
agent = await create_assistant_agent(
    name="test_assistant",
    system_message="You are a testing expert",
    conversation_id="conv_123",
    auto_memory=True,
    auto_context=True
)
```

### Multi-Agent Collaboration

```python
from autogen_agentchat.teams import RoundRobinGroupChat

# Create team of agents
team = RoundRobinGroupChat([agent1, agent2, agent3])
result = await team.run(task="Generate test cases")
```

### RAG Integration

```python
from backend.rag_core import RAGSystem

async with RAGSystem() as rag:
    # Add documents
    await rag.add_document(
        content="Test documentation content",
        metadata={"category": "testing"},
        collection_name="testcase_knowledge"
    )

    # Query with context
    result = await rag.query(
        query="How to write unit tests?",
        collection_name="testcase_knowledge"
    )
```

## Performance Considerations

### Backend Optimizations

1. **Database**: Use async Tortoise ORM with connection pooling
2. **Caching**: Implement Redis caching for frequently accessed data
3. **AI Requests**: Batch AI API calls when possible
4. **Memory**: Use streaming for large responses
5. **Concurrency**: Leverage FastAPI's async capabilities

### Frontend Optimizations

1. **Code Splitting**: Use React.lazy() for large components
2. **API Caching**: Implement query caching with React Query
3. **Bundle Size**: Analyze and optimize with Vite bundle analyzer
4. **SSE Handling**: Efficiently handle streaming data updates

## Security Guidelines

### Backend Security

1. **Authentication**: JWT tokens with proper expiration
2. **Authorization**: Role-based access control (RBAC)
3. **Input Validation**: Pydantic models for all inputs
4. **SQL Injection**: Use ORM parameterized queries
5. **API Keys**: Never commit secrets, use environment variables

### Frontend Security

1. **XSS Prevention**: Sanitize user inputs
2. **CSRF Protection**: Implement CSRF tokens
3. **Secure Storage**: Use secure storage for sensitive data
4. **API Communication**: HTTPS only in production

## Troubleshooting

### Common Issues

**Backend Startup:**
- Check database connection settings
- Verify AI model API keys are configured
- Ensure required services (Milvus, Ollama) are running

**Frontend Build:**
- Clear node_modules and reinstall dependencies
- Check TypeScript errors in development mode
- Verify API endpoint URLs are correct

**AI Agents:**
- Validate model configurations in settings.yaml
- Check API key permissions and quotas
- Monitor agent memory usage and cleanup

### Debugging Commands

```bash
# View logs
make logs

# Clean and restart
make stop && make start

```

### Log Locations

- Backend: `backend.log`, `logs/app.log`, `logs/error.log`
- Frontend: `frontend.log`
- AI Core: Uses loguru for structured logging
- Database: Tortoise ORM query logging (when enabled)

## Documentation References

- **AI Core Framework**: `backend/ai_core/docs/` - Complete AI development guide
- **RAG System**: `backend/rag_core/docs/` - Knowledge base system documentation
- **API Documentation**: Available at `http://localhost:8000/docs` when running
- **Project Documentation**: `docs/` directory with architecture and guides
- **Makefile Help**: Run `make help` for all available commands

## Integration Points

### External Services

1. **AI Models**: DeepSeek, Qwen-VL, UI-TARS APIs
2. **Vector Database**: Milvus for RAG embeddings
3. **Embedding Service**: Ollama for text embeddings
4. **Database**: MySQL/PostgreSQL for production, SQLite for development

### API Integration

The platform exposes RESTful APIs with OpenAPI documentation:
- Authentication: `/api/auth/`
- AI Chat: `/api/chat/`
- Test Cases: `/api/testcase/`
- RAG System: `/api/rag/`
- UI Testing: `/api/midscene/`

### Frontend-Backend Communication

- REST API calls for standard operations
- SSE for real-time AI response streaming
- WebSocket support planned for future features

This architecture supports both development and production deployment while maintaining clean separation of concerns and scalability.
