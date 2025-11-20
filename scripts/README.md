# Scripts

Utility scripts for testing and development.

## test_all_endpoints.py

**Comprehensive end-to-end API testing script** that tests all endpoints in their proper flow sequence.

### What it tests:

**Complete RAG Pipeline Flow:**
1. ✅ Health check endpoint
2. ✅ Tenant creation and retrieval
3. ✅ Document upload
4. ✅ Background job status monitoring
5. ✅ Query endpoint (retrieval)
6. ✅ Chat endpoint with streaming responses
7. ✅ Chat endpoint with non-streaming responses

**Key Features:**
- Tests endpoints in realistic usage order
- Waits for background job completion
- Tests both streaming and non-streaming chat
- Color-coded output with detailed logging
- Automatic test document generation
- Comprehensive test summary and statistics
- CI/CD friendly with proper exit codes

### Prerequisites:

```bash
# Install required dependencies
pip install requests

# Or with poetry
poetry add --group dev requests
```

### Usage:

```bash
# Test against local server (default: http://localhost:8001)
python scripts/test_all_endpoints.py

# Test against different URL
python scripts/test_all_endpoints.py --base-url http://api.example.com:8001

# Use existing API key
python scripts/test_all_endpoints.py --api-key your-api-key-here

# Specify custom tenant name
python scripts/test_all_endpoints.py --tenant-name my-test-tenant

# Upload specific document
python scripts/test_all_endpoints.py --document /path/to/your/document.pdf

# Specify output file for JSON results (default: test_results.json)
python scripts/test_all_endpoints.py --output test_results_$(date +%Y%m%d_%H%M%S).json

# Make it executable and run directly
chmod +x scripts/test_all_endpoints.py
./scripts/test_all_endpoints.py
```

### Example Output:

```
============================================================
    COMPREHENSIVE API ENDPOINT TESTING
============================================================
Base URL: http://localhost:8001
Started: 2024-01-15 10:30:00

============================================================
1. Health Check
============================================================
✓ PASS | GET /health
      Status: healthy

============================================================
2. Tenant Operations
============================================================
✓ PASS | POST /api/v1/tenants
      Created tenant: 123e4567-e89b-12d3-a456-426614174000
✓ PASS | GET /api/v1/tenants/{id}
      Retrieved tenant: test-tenant-1705315800

============================================================
3. Document Upload
============================================================
✓ PASS | POST /api/v1/documents/upload
      Document uploaded, job_id: 456e7890-e89b-12d3-a456-426614174001

============================================================
4. Job Status Monitoring
============================================================
      Job status: pending (0%)
      Job status: processing (10%)
      Job status: processing (90%)
      Job status: completed (100%)
✓ PASS | GET /api/v1/jobs/{id}
      Job completed successfully in 8.2s

============================================================
5. Query Endpoint
============================================================
✓ PASS | POST /api/v1/query
      Query returned 5 results

============================================================
6. Chat Endpoint (Streaming)
============================================================
      Streaming response:
The Pingo chatbot uses a multi-tenant RAG architecture with vector search, BM25 indexing, and hybrid retrieval capabilities...
✓ PASS | POST /api/v1/chat
      Received 87 chunks with 3 sources

============================================================
7. Chat Endpoint (Non-Streaming)
============================================================
      Response:
The system architecture consists of multiple components including...
✓ PASS | POST /api/v1/chat (non-streaming)
      Received answer with 3 sources

============================================================
Test Summary
============================================================

Total Tests: 9
Passed: 9
Failed: 0

Success Rate: 100.0%
```

### Integration with CI/CD:

```yaml
# .github/workflows/integration-test.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: sleep 10

      - name: Run comprehensive tests
        run: python scripts/test_all_endpoints.py

      - name: Cleanup
        run: docker-compose down
```

### Command-line Options:

| Option | Description | Default |
|--------|-------------|---------|
| `--base-url` | Base URL of the API | `http://localhost:8001` |
| `--api-key` | API key for authentication | Auto-generated |
| `--tenant-name` | Tenant name to use | Auto-generated with timestamp |
| `--document` | Path to document to upload | Creates test document automatically |
| `--output` | Path to save JSON results | `test_results.json` |

### Exported JSON Results

The test automatically exports detailed results to a JSON file containing:

- **Test Run Metadata**: Base URL, start/end times, duration, tenant ID
- **Summary Statistics**: Total tests, passed, failed, success rate
- **Individual Test Results**: Each test includes:
  - Test name and endpoint
  - Pass/fail status
  - Descriptive message
  - Full API response details
  - Timestamp

**Example JSON structure:**
```json
{
  "test_run": {
    "base_url": "http://localhost:8001",
    "start_time": "2025-11-20T20:27:12.719371",
    "end_time": "2025-11-20T20:27:46.563373",
    "duration_seconds": 33.844002,
    "tenant_id": "852943ce-62cb-4ed0-8c17-8611ccbb0940"
  },
  "summary": {
    "total_tests": 9,
    "passed": 9,
    "failed": 0,
    "success_rate": 100.0
  },
  "tests": [...]
}
```

### Troubleshooting:

**Connection refused:**
```bash
# Make sure all services are running
docker-compose up -d

# Check API health
curl http://localhost:8001/health
```

**Job processing timeout:**
```bash
# Check worker is running
docker ps | grep pingo-worker

# Check worker logs
docker logs pingo-worker

# Start worker if not running
docker-compose up -d worker
```

**No results from query:**
```bash
# Verify document was processed
curl -H "X-Tenant-ID: your-tenant-id" http://localhost:8001/api/v1/jobs/{job-id}

# Check Qdrant collection
docker exec -it pingo-qdrant qdrant-cli collection list
```

**Import errors:**
```bash
# Install missing dependencies
pip install requests
```

---

## test_tenant_endpoints.py

Comprehensive test script for tenant management API endpoints.

### What it tests:

**Tenant Management:**
- ✅ Create tenant with realistic data
- ✅ Get tenant by ID
- ✅ List all tenants (with pagination)
- ✅ Update tenant (name, tier, settings)
- ✅ Delete tenant (soft delete)

**API Key Management:**
- ✅ Create API key with scopes and expiration
- ✅ Create multiple API keys for same tenant
- ✅ List all API keys for a tenant
- ✅ Revoke API key

**Statistics:**
- ✅ Get tenant usage statistics

**Error Handling:**
- ✅ Non-existent tenant (404)
- ✅ Invalid email format (400)
- ✅ Missing required fields (422)
- ✅ Update non-existent tenant (404)

### Prerequisites:

```bash
# Install requests library (if not already installed)
poetry add --group dev requests

# Or with pip
pip install requests
```

### Usage:

```bash
# Test against local server (must be running)
python scripts/test_tenant_endpoints.py

# Test against different host
python scripts/test_tenant_endpoints.py --host http://api.example.com

# Skip deletion at the end (keep test tenant)
python scripts/test_tenant_endpoints.py --skip-delete

# Make it executable and run directly
chmod +x scripts/test_tenant_endpoints.py
./scripts/test_tenant_endpoints.py
```

### Example Output:

```
================================================================================
Starting Tenant API Test Suite
================================================================================

TEST: Health Check

Request: GET http://localhost:8001/health
✓ API is healthy

================================================================================
Testing Tenant Lifecycle
================================================================================

TEST: Create Tenant

Request: POST http://localhost:8001/api/v1/tenants
Body:
{
  "name": "Acme Corporation",
  "industry": "ecommerce",
  "contact_email": "admin@acme-corp.com",
  ...
}

Status: 201
✓ Status code: 201 (expected)

Response:
{
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Acme Corporation",
  "tier": "free",
  ...
}

✓ Tenant created with ID: 123e4567-e89b-12d3-a456-426614174000

...

================================================================================
Test Summary
================================================================================
Total Tests: 15
Passed: 15
Failed: 0
Success Rate: 100.0%

✓ All tests passed!
```

### Features:

- **Color-coded output**: Green for success, red for errors, yellow for warnings
- **Detailed logging**: Shows request/response for each API call
- **Realistic test data**: Uses production-like data for tenants and API keys
- **Comprehensive coverage**: Tests happy path, edge cases, and error scenarios
- **Reusable**: Can be integrated into CI/CD pipeline
- **Exit codes**: Returns 0 on success, 1 on failure (CI-friendly)

### Integration with CI/CD:

```yaml
# .github/workflows/test.yml
- name: Test Tenant API
  run: |
    poetry run python main.py &
    sleep 5
    poetry run python scripts/test_tenant_endpoints.py
    kill %1
```

### Extending the script:

To add more tests, simply add new methods to the `TenantAPITester` class:

```python
def test_my_new_endpoint(self) -> bool:
    """Test description."""
    self.print_test("My New Test")

    response = self.make_request("GET", "/my-endpoint")

    if response:
        self.print_success("Test passed")
        return True
    return False
```

Then add it to `run_all_tests()`:

```python
tests.append(("My New Test", self.test_my_new_endpoint))
```

### Troubleshooting:

**Connection refused:**
```bash
# Make sure API server is running
poetry run python main.py

# Check if services are up
docker-compose up -d
```

**Import errors:**
```bash
# Install requests
poetry add --group dev requests
```

**All tests fail:**
```bash
# Check API health manually
curl http://localhost:8001/health

# Check database is migrated
poetry run alembic upgrade head
```
