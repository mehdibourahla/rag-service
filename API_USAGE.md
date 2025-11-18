# Pingo Chatbot API - Usage Guide

Welcome to the Pingo multi-tenant AI chatbot platform! This guide will help you get started with integrating the chatbot into your application.

## Table of Contents

- [Getting Started](#getting-started)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Integration Examples](#integration-examples)
- [Multi-Tenancy](#multi-tenancy)
- [Error Handling](#error-handling)

---

## Getting Started

### 1. Create Your Tenant Account

```bash
curl -X POST https://api.pingo.ai/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "industry": "ecommerce",
    "contact_email": "admin@acme.com",
    "contact_name": "John Doe",
    "brand_name": "Acme Support",
    "brand_tone": "friendly"
  }'
```

**Response:**
```json
{
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Acme Corporation",
  "industry": "ecommerce",
  "status": "trial",
  "tier": "free",
  "contact_email": "admin@acme.com",
  "created_at": "2025-11-18T00:00:00Z",
  "settings": {
    "brand_name": "Acme Support",
    "brand_tone": "friendly",
    "primary_color": "#007bff",
    "default_language": "en"
  }
}
```

### 2. Generate an API Key

```bash
curl -X POST https://api.pingo.ai/api/v1/tenants/{tenant_id}/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Widget",
    "scopes": ["chat", "upload", "query"]
  }'
```

**Response:**
```json
{
  "key_id": "abc12345-...",
  "api_key": "pk_live_nR3bK8mP4vD9xF2yQ7sL1wA6jH5tC0uN",
  "prefix": "pk_live_nR3b",
  "warning": "Store this key securely. It will not be shown again."
}
```

**⚠️ Important:** Save this API key securely! It will not be shown again.

---

## Authentication

All API requests (except tenant creation) require authentication using the `X-API-Key` header:

```bash
curl -H "X-API-Key: pk_live_nR3bK8mP4vD9xF2yQ7sL1wA6jH5tC0uN" \
  https://api.pingo.ai/api/v1/sessions
```

---

## API Endpoints

### Health & Status

#### `GET /api/v1/health`
Check system health and statistics.

```bash
curl https://api.pingo.ai/api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T12:00:00Z",
  "storage": {
    "vector_store_count": 1523,
    "bm25_index_count": 1523
  },
  "database": {
    "total_tenants": 5,
    "active_tenants": 4,
    "total_sessions": 127,
    "total_messages": 843
  }
}
```

---

### Document Management

#### `POST /api/v1/documents/upload`
Upload and process a document for your chatbot's knowledge base.

```bash
curl -X POST https://api.pingo.ai/api/v1/documents/upload \
  -H "X-API-Key: pk_live_..." \
  -F "file=@support_guide.pdf"
```

**Response:**
```json
{
  "document_id": "789def01-...",
  "filename": "support_guide.pdf",
  "file_type": "pdf",
  "size_bytes": 245632,
  "status": "completed",
  "message": "Document processed successfully"
}
```

**Supported file types:** PDF, DOCX, TXT, JPG, PNG, HTML

#### `DELETE /api/v1/documents/{document_id}`
Delete a document and all its indexed content.

```bash
curl -X DELETE https://api.pingo.ai/api/v1/documents/{document_id} \
  -H "X-API-Key: pk_live_..."
```

---

### Chat Sessions

#### `POST /api/v1/sessions`
Create a new chat session.

```bash
curl -X POST https://api.pingo.ai/api/v1/sessions \
  -H "X-API-Key: pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "language": "en"
  }'
```

**Response:**
```json
{
  "session_id": "session_abc123",
  "tenant_id": "123e4567-...",
  "status": "active",
  "started_at": "2025-11-18T12:00:00Z",
  "message_count": 0
}
```

#### `GET /api/v1/sessions/{session_id}/history`
Retrieve complete conversation history.

```bash
curl https://api.pingo.ai/api/v1/sessions/{session_id}/history \
  -H "X-API-Key: pk_live_..."
```

#### `POST /api/v1/sessions/{session_id}/end`
End a chat session.

```bash
curl -X POST https://api.pingo.ai/api/v1/sessions/{session_id}/end \
  -H "X-API-Key: pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "end_reason": "user_ended"
  }'
```

---

### Chat & Query

#### `POST /api/v1/query`
Simple query endpoint (non-streaming).

```bash
curl -X POST https://api.pingo.ai/api/v1/query \
  -H "X-API-Key: pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I reset my password?",
    "top_k": 5
  }'
```

**Response:**
```json
{
  "query": "How do I reset my password?",
  "answer": "To reset your password, go to Settings > Security and click...",
  "chunks": [
    {
      "text": "Password reset instructions...",
      "score": 0.92,
      "metadata": {
        "source": "support_guide.pdf",
        "page_number": 5
      }
    }
  ],
  "processing_time": 1.23
}
```

#### `POST /api/v1/chat` (Streaming)
Streaming chat endpoint with AI SDK compatibility.

```bash
curl -X POST https://api.pingo.ai/api/v1/chat \
  -H "X-API-Key: pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "How do I reset my password?"}
    ],
    "session_id": "session_abc123"
  }'
```

**Streaming Response (Server-Sent Events):**
```
data: {"type":"text-start","id":"msg_123"}

data: {"type":"text-delta","id":"msg_123","delta":"To"}

data: {"type":"text-delta","id":"msg_123","delta":" reset"}

...

data: {"type":"source-document","sourceId":"chunk_456","title":"support_guide.pdf (Page 5) [92%]"}

data: {"type":"text-end","id":"msg_123"}

data: [DONE]
```

---

### Feedback

#### `POST /api/v1/messages/{message_id}/feedback`
Submit user feedback on a message.

```bash
curl -X POST https://api.pingo.ai/api/v1/messages/{message_id}/feedback \
  -H "X-API-Key: pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_type": "thumbs_up",
    "value": "1",
    "comment": "Very helpful!"
  }'
```

**Feedback types:** `thumbs_up`, `thumbs_down`, `rating` (1-5)

---

## Integration Examples

### JavaScript/TypeScript Widget

```typescript
// Initialize Pingo client
const pingo = new PingoClient({
  apiKey: 'pk_live_nR3bK8mP4vD9xF2yQ7sL1wA6jH5tC0uN',
  apiUrl: 'https://api.pingo.ai/api/v1'
});

// Create session
const session = await pingo.createSession({
  user_id: currentUser.id
});

// Send message with streaming
const response = await fetch('https://api.pingo.ai/api/v1/chat', {
  method: 'POST',
  headers: {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    messages: [
      { role: 'user', content: userMessage }
    ],
    session_id: session.session_id
  })
});

// Handle streaming response
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));

      if (data.type === 'text-delta') {
        appendToChat(data.delta);
      } else if (data.type === 'source-document') {
        addSource(data.title);
      }
    }
  }
}

// Submit feedback
await pingo.submitFeedback(messageId, {
  feedback_type: 'thumbs_up',
  value: '1'
});
```

### Python Client

```python
import requests
from typing import Iterator

class PingoClient:
    def __init__(self, api_key: str, base_url: str = "https://api.pingo.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}

    def upload_document(self, file_path: str):
        """Upload a document to the knowledge base."""
        with open(file_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/documents/upload",
                headers=self.headers,
                files={"file": f}
            )
        return response.json()

    def query(self, question: str, top_k: int = 5):
        """Simple query (non-streaming)."""
        response = requests.post(
            f"{self.base_url}/query",
            headers=self.headers,
            json={"query": question, "top_k": top_k}
        )
        return response.json()

    def chat_stream(self, messages: list, session_id: str = None) -> Iterator[dict]:
        """Streaming chat."""
        response = requests.post(
            f"{self.base_url}/chat",
            headers=self.headers,
            json={"messages": messages, "session_id": session_id},
            stream=True
        )

        for line in response.iter_lines():
            if line.startswith(b'data: '):
                data = line[6:].decode('utf-8')
                if data != '[DONE]':
                    yield json.loads(data)

# Usage
client = PingoClient(api_key="pk_live_...")

# Upload documents
client.upload_document("faq.pdf")

# Query
result = client.query("How do I cancel my order?")
print(result['answer'])

# Streaming chat
for event in client.chat_stream([
    {"role": "user", "content": "Hello!"}
]):
    if event['type'] == 'text-delta':
        print(event['delta'], end='', flush=True)
```

---

## Multi-Tenancy

The Pingo platform is fully multi-tenant:

- **Data Isolation:** Each tenant's data is completely isolated
- **Separate Knowledge Bases:** Documents are indexed per-tenant
- **API Keys:** Each tenant has their own API keys
- **Usage Tracking:** Per-tenant usage and analytics

### Tenant Management

#### Update Tenant Settings

```bash
curl -X PUT https://api.pingo.ai/api/v1/tenants/{tenant_id} \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "brand_name": "Acme AI Assistant",
      "brand_tone": "professional",
      "primary_color": "#1a73e8",
      "widget_greeting": "Hello! How can I assist you today?"
    }
  }'
```

#### List API Keys

```bash
curl https://api.pingo.ai/api/v1/tenants/{tenant_id}/api-keys
```

#### Revoke API Key

```bash
curl -X DELETE https://api.pingo.ai/api/v1/tenants/{tenant_id}/api-keys/{key_id}
```

---

## Error Handling

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `204` - No Content (successful deletion)
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (invalid/missing API key)
- `404` - Not Found
- `500` - Internal Server Error

### Error Response Format

```json
{
  "detail": "Invalid API key"
}
```

### Common Errors

**401 Unauthorized:**
```json
{
  "detail": "Missing authentication. Provide X-API-Key or Authorization header"
}
```

**404 Not Found:**
```json
{
  "detail": "Session abc123 not found"
}
```

---

## Rate Limits

Current limits (per tenant):
- **Queries:** 1000/day (configurable per tier)
- **Documents:** 100 total (configurable per tier)
- **File Size:** 10MB max (configurable per tier)

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1700265600
```

---

## Support

- **Documentation:** https://docs.pingo.ai
- **API Reference:** https://api.pingo.ai/api/docs
- **Email:** support@pingo.ai
- **GitHub:** https://github.com/pingo-ai/chatbot

---

## Next Steps

1. **Upload your first document** to build your knowledge base
2. **Test the chat endpoint** with sample questions
3. **Integrate the widget** into your website
4. **Monitor analytics** to track usage and improve responses
5. **Collect feedback** to optimize your chatbot

Happy building! 🚀
