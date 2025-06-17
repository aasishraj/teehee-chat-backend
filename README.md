# Teehee Chat Backend

A multi-LLM chatbot backend with streaming support. This platform enables users to interact with multiple LLM inference providers (OpenAI, Anthropic, Mistral) through a unified chatbot interface.

## Features

- **Multi-Provider Support**: Connect to OpenAI, Anthropic, and Mistral APIs
- **Real-time Streaming**: WebSocket-based streaming with fallback support
- **User Authentication**: JWT-based auth with SSO support
- **Encrypted API Keys**: Secure storage of user API keys
- **Chat Management**: Create, manage, and branch conversations
- **Message Threading**: Support for conversation branching and message editing

## Technology Stack

- **Backend Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Package Manager**: UV
- **Containerization**: Docker + Docker Compose
- **Streaming**: WebSocket with SSE fallback
- **Encryption**: AES encryption for API keys
- **Authentication**: JWT tokens with bcrypt password hashing

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── api/                 # API route handlers
│   │   ├── auth.py         # Authentication endpoints
│   │   ├── chats.py        # Chat session management
│   │   ├── messages.py     # Message operations
│   │   ├── keys.py         # API key management
│   │   ├── stream.py       # WebSocket streaming
│   │   └── models.py       # System information
│   ├── core/               # Core configuration
│   │   ├── config.py       # Application settings
│   │   └── security.py     # Authentication & encryption
│   ├── db/                 # Database layer
│   │   ├── database.py     # Database connection
│   │   ├── models.py       # SQLAlchemy models
│   │   └── schemas.py      # Pydantic schemas
│   ├── services/           # External service clients
│   │   └── provider_clients.py  # LLM provider clients
│   └── utils/              # Utility functions
│       └── streaming.py    # Streaming utilities
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository
2. Copy environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

4. The API will be available at `http://localhost:8000`
5. API documentation at `http://localhost:8000/docs`

### Local Development

1. Install UV (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies:
   ```bash
   uv pip install -e .
   ```

3. Set up PostgreSQL and update DATABASE_URL in your environment

4. Run the application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatdb

# Security
SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEY=your-encryption-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]

# App
APP_NAME=Teehee Chat Backend
DEBUG=false

# Optional Provider API Keys (users can provide their own)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
MISTRAL_API_KEY=

# Streaming
MAX_TOKENS=4096
STREAM_TIMEOUT=300
```

## API Endpoints

### Authentication
- `POST /auth/signup` - Create account
- `POST /auth/signin` - Email + password login
- `POST /auth/sso` - Handle SSO login/signup
- `GET /auth/session` - Get current session info
- `POST /auth/logout` - Logout

### API Keys
- `GET /user/keys` - List user's provider keys
- `POST /user/keys` - Add a new provider key
- `DELETE /user/keys/{key_id}` - Delete a provider key

### Chats
- `GET /chats` - List user's chat sessions
- `POST /chats` - Create a new chat session
- `GET /chats/{chat_id}` - Get chat session and messages
- `DELETE /chats/{chat_id}` - Delete a chat session

### Messages
- `GET /chats/{chat_id}/messages` - List messages in a session
- `POST /chats/{chat_id}/messages` - Submit a new message
- `PATCH /messages/{message_id}` - Edit message

### Streaming
- `WebSocket /stream/{chat_id}` - WebSocket connection for streaming
- `POST /stream/{message_id}/abort` - Abort stream
- `POST /stream/{message_id}/continue` - Continue incomplete stream

### System
- `GET /models` - List supported models
- `GET /providers` - List supported providers
- `GET /health` - Health check

## WebSocket Protocol

Connect to `/stream/{chat_id}` with a JWT token as query parameter.

### Sending Messages
```json
{
  "type": "stream_message",
  "content": "Your message here",
  "provider": "openai",
  "model": "gpt-3.5-turbo",
  "parent_message_id": "uuid-optional"
}
```

### Receiving Responses
```json
{
  "type": "stream_start",
  "message_id": "uuid",
  "status": "streaming"
}

{
  "type": "token",
  "message_id": "uuid", 
  "token": "Hello",
  "content": "Hello"
}

{
  "type": "stream_complete",
  "message_id": "uuid",
  "status": "complete",
  "content": "Full response"
}
```

## Supported Providers

### OpenAI
- GPT-4 Turbo Preview
- GPT-4
- GPT-3.5 Turbo
- GPT-3.5 Turbo 16K

### Anthropic
- Claude 3 Opus
- Claude 3 Sonnet
- Claude 3 Haiku
- Claude 2.1
- Claude 2.0

### Mistral
- Mistral Large
- Mistral Medium
- Mistral Small
- Open Mixtral 8x7B
- Open Mistral 7B

## Database Schema

### Users
- id (UUID, PK)
- email (unique)
- sso_id (nullable)
- password_hash
- created_at

### Provider Keys
- id (UUID, PK)
- user_id (FK)
- provider_name
- encrypted_api_key
- created_at

### Chat Sessions
- id (UUID, PK)
- user_id (FK)
- root_message_id (nullable)
- created_at
- name/title

### Messages
- id (UUID, PK)
- chat_session_id (FK)
- parent_message_id (nullable)
- role (user/assistant)
- content (JSONB)
- timestamp
- is_partial (bool)
- model
- provider

## Security

- HTTPS enforced in production
- Passwords hashed with bcrypt
- API keys encrypted with Fernet
- JWT tokens for session management
- Input validation with Pydantic

## Development

### Running Tests
```bash
uv pip install -e .[dev]
pytest
```

### Code Formatting
```bash
black .
isort .
```

### Type Checking
```bash
mypy .
```

## Deployment

1. Set production environment variables
2. Use the included Dockerfile
3. Deploy with docker-compose or your preferred orchestration platform
4. Set up a reverse proxy (nginx/caddy) for HTTPS

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.
