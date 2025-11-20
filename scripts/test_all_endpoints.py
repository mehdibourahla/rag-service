#!/usr/bin/env python3
"""
Comprehensive API Endpoint Testing Script

Tests all endpoints in their proper flow:
1. Health check
2. Tenant operations
3. Document upload
4. Job status monitoring
5. Query endpoint
6. Chat endpoint with streaming
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class APITester:
    """Comprehensive API endpoint tester."""

    def __init__(self, base_url: str = "http://localhost:8001", api_key: Optional[str] = None, output_file: Optional[str] = None):
        """
        Initialize API tester.

        Args:
            base_url: Base URL of the API
            api_key: Optional API key for authentication
            output_file: Optional path to save test results JSON
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.output_file = output_file or "test_results.json"
        self.session = self._create_session()
        self.tenant_id = None
        self.test_results = []
        self.start_time = None

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _get_headers(self, content_type: str = "application/json") -> dict:
        """Get request headers with optional API key."""
        headers = {"Content-Type": content_type}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        return headers

    def _log_test(self, name: str, passed: bool, message: str = "", details: dict = None):
        """Log test result."""
        status = f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}" if passed else f"{Colors.FAIL}✗ FAIL{Colors.ENDC}"
        print(f"{status} | {name}")
        if message:
            print(f"      {message}")
        if details:
            print(f"      Details: {json.dumps(details, indent=2)}")

        self.test_results.append({
            "name": name,
            "passed": passed,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_health_check(self) -> bool:
        """Test health check endpoint."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}1. Health Check{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        try:
            response = self.session.get(f"{self.base_url}/api/v1/health")

            if response.status_code == 200:
                data = response.json()
                self._log_test(
                    "GET /api/v1/health",
                    True,
                    f"Status: {data.get('status', 'unknown')}",
                    data
                )
                return True
            else:
                self._log_test(
                    "GET /api/v1/health",
                    False,
                    f"Status code: {response.status_code}"
                )
                return False
        except Exception as e:
            self._log_test("GET /api/v1/health", False, f"Error: {str(e)}")
            return False

    def test_tenant_operations(self, tenant_name: str = "test-tenant") -> bool:
        """Test tenant creation and retrieval."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}2. Tenant Operations{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        success = True

        # Create tenant
        try:
            payload = {
                "name": tenant_name,
                "industry": "technology",
                "contact_email": f"{tenant_name}@example.com"
            }
            response = self.session.post(
                f"{self.base_url}/api/v1/tenants",
                headers=self._get_headers(),
                json=payload
            )

            if response.status_code in [200, 201]:
                data = response.json()
                self.tenant_id = data.get("tenant_id") or data.get("id")
                self.api_key = data.get("api_key")
                self._log_test(
                    "POST /api/v1/tenants",
                    True,
                    f"Created tenant: {self.tenant_id}",
                    {"tenant_id": self.tenant_id, "tier": data.get("tier")}
                )
            else:
                self._log_test(
                    "POST /api/v1/tenants",
                    False,
                    f"Status code: {response.status_code}, Body: {response.text}"
                )
                success = False
        except Exception as e:
            self._log_test("POST /api/v1/tenants", False, f"Error: {str(e)}")
            success = False

        # Get tenant details
        if self.tenant_id:
            try:
                response = self.session.get(
                    f"{self.base_url}/api/v1/tenants/{self.tenant_id}",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    self._log_test(
                        "GET /api/v1/tenants/{id}",
                        True,
                        f"Retrieved tenant: {data.get('name')}",
                        data
                    )
                else:
                    self._log_test(
                        "GET /api/v1/tenants/{id}",
                        False,
                        f"Status code: {response.status_code}"
                    )
                    success = False
            except Exception as e:
                self._log_test("GET /api/v1/tenants/{id}", False, f"Error: {str(e)}")
                success = False

        # Create API key for the tenant
        if self.tenant_id and not self.api_key:
            try:
                payload = {
                    "name": "test-api-key",
                    "scopes": ["read", "write"],
                    "expires_in_days": 30
                }
                response = self.session.post(
                    f"{self.base_url}/api/v1/tenants/{self.tenant_id}/api-keys",
                    headers=self._get_headers(),
                    json=payload
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    self.api_key = data.get("api_key")
                    self._log_test(
                        "POST /api/v1/tenants/{id}/api-keys",
                        True,
                        f"Created API key: {data.get('prefix')}...",
                        {"key_id": data.get("key_id"), "prefix": data.get("prefix")}
                    )
                else:
                    self._log_test(
                        "POST /api/v1/tenants/{id}/api-keys",
                        False,
                        f"Status code: {response.status_code}, Body: {response.text}"
                    )
                    success = False
            except Exception as e:
                self._log_test("POST /api/v1/tenants/{id}/api-keys", False, f"Error: {str(e)}")
                success = False

        return success

    def test_document_upload(self, file_path: Optional[str] = None) -> Optional[str]:
        """Test document upload endpoint."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}3. Document Upload{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        if not self.tenant_id:
            self._log_test("POST /api/v1/documents/upload", False, "No tenant_id available")
            return None

        # Create test file if not provided
        if not file_path:
            test_content = """
            Test Document for RAG System

            This is a comprehensive test document for the Pingo RAG chatbot system.

            Section 1: System Architecture
            The Pingo chatbot uses a multi-tenant RAG architecture with vector search,
            BM25 indexing, and hybrid retrieval capabilities.

            Section 2: Features
            Key features include:
            - Multi-tenant isolation
            - Background job processing with RQ
            - Redis caching for embeddings
            - Qdrant vector store
            - OpenAI embeddings and chat completions
            - Streaming responses

            Section 3: Testing
            This document is used to verify end-to-end functionality of the system.
            """

            test_file_path = Path("/tmp/test_document.txt")
            test_file_path.write_text(test_content)
            file_path = str(test_file_path)

        try:
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f, 'text/plain')}
                headers = {"X-API-Key": self.api_key} if self.api_key else {}
                if self.tenant_id:
                    headers["X-Tenant-ID"] = self.tenant_id

                response = self.session.post(
                    f"{self.base_url}/api/v1/documents/upload",
                    headers=headers,
                    files=files
                )

            if response.status_code == 200:
                data = response.json()
                job_id = data.get("job_id")
                self._log_test(
                    "POST /api/v1/documents/upload",
                    True,
                    f"Document uploaded, job_id: {job_id}",
                    data
                )
                return job_id
            else:
                self._log_test(
                    "POST /api/v1/documents/upload",
                    False,
                    f"Status code: {response.status_code}, Body: {response.text}"
                )
                return None
        except Exception as e:
            self._log_test("POST /api/v1/documents/upload", False, f"Error: {str(e)}")
            return None

    def test_job_status(self, job_id: str, max_wait: int = 60) -> bool:
        """Test job status endpoint and wait for completion."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}4. Job Status Monitoring{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        if not job_id:
            self._log_test("GET /api/v1/jobs/{id}", False, "No job_id available")
            return False

        start_time = time.time()
        last_status = None

        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(
                    f"{self.base_url}/api/v1/jobs/{job_id}",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    # Log status change
                    if status != last_status:
                        progress = data.get("progress") or 0
                        print(f"      Job status: {status} ({progress*100:.0f}%)")
                        last_status = status

                    if status == "completed":
                        self._log_test(
                            "GET /api/v1/jobs/{id}",
                            True,
                            f"Job completed successfully in {time.time() - start_time:.1f}s",
                            data
                        )
                        return True
                    elif status == "failed":
                        self._log_test(
                            "GET /api/v1/jobs/{id}",
                            False,
                            f"Job failed: {data.get('error_message', 'Unknown error')}",
                            data
                        )
                        return False

                    # Wait before next check
                    time.sleep(2)
                else:
                    self._log_test(
                        "GET /api/v1/jobs/{id}",
                        False,
                        f"Status code: {response.status_code}"
                    )
                    return False
            except Exception as e:
                self._log_test("GET /api/v1/jobs/{id}", False, f"Error: {str(e)}")
                return False

        self._log_test(
            "GET /api/v1/jobs/{id}",
            False,
            f"Job did not complete within {max_wait}s (last status: {last_status})"
        )
        return False

    def test_query_endpoint(self, query: str = "What are the key features of the system?") -> bool:
        """Test query endpoint."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}5. Query Endpoint{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        if not self.tenant_id:
            self._log_test("POST /api/v1/query", False, "No tenant_id available")
            return False

        try:
            payload = {
                "query": query,
                "top_k": 5
            }
            response = self.session.post(
                f"{self.base_url}/api/v1/query",
                headers=self._get_headers(),
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                self._log_test(
                    "POST /api/v1/query",
                    True,
                    f"Query returned {len(results)} results",
                    {
                        "query": query,
                        "result_count": len(results),
                        "full_response": data,
                        "results": results
                    }
                )
                return True
            else:
                self._log_test(
                    "POST /api/v1/query",
                    False,
                    f"Status code: {response.status_code}, Body: {response.text}"
                )
                return False
        except Exception as e:
            self._log_test("POST /api/v1/query", False, f"Error: {str(e)}")
            return False

    def test_chat_endpoint(self, message: str = "What is the Pingo chatbot system?") -> bool:
        """Test chat endpoint with streaming."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}6. Chat Endpoint (Streaming){Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        if not self.tenant_id:
            self._log_test("POST /api/v1/chat", False, "No tenant_id available")
            return False

        try:
            payload = {
                "messages": [{"role": "user", "content": message}],
                "stream": True
            }
            response = self.session.post(
                f"{self.base_url}/api/v1/chat",
                headers=self._get_headers(),
                json=payload,
                stream=True
            )

            if response.status_code == 200:
                print(f"      {Colors.OKCYAN}Streaming response:{Colors.ENDC}")

                chunks_received = 0
                full_response = ""
                sources = []

                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # Remove 'data: ' prefix
                            try:
                                chunk_data = json.loads(data_str)
                                chunk_type = chunk_data.get("type")

                                if chunk_type == "text-delta":
                                    delta = chunk_data.get("delta", "")
                                    full_response += delta
                                    print(delta, end='', flush=True)
                                    chunks_received += 1
                                elif chunk_type == "sources":
                                    sources = chunk_data.get("sources", [])
                            except json.JSONDecodeError:
                                continue

                print()  # New line after streaming

                self._log_test(
                    "POST /api/v1/chat",
                    True,
                    f"Received {chunks_received} chunks with {len(sources)} sources",
                    {
                        "message": message,
                        "chunks_received": chunks_received,
                        "response_length": len(full_response),
                        "sources_count": len(sources),
                        "full_response": full_response,
                        "sources": sources
                    }
                )
                return True
            else:
                self._log_test(
                    "POST /api/v1/chat",
                    False,
                    f"Status code: {response.status_code}, Body: {response.text}"
                )
                return False
        except Exception as e:
            self._log_test("POST /api/v1/chat", False, f"Error: {str(e)}")
            return False

    def test_chat_non_streaming(self, message: str = "What is the system architecture?") -> bool:
        """Test chat endpoint with different message (still uses streaming)."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}7. Chat Endpoint (Second Query){Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        if not self.tenant_id:
            self._log_test("POST /api/v1/chat (second query)", False, "No tenant_id available")
            return False

        try:
            payload = {
                "messages": [{"role": "user", "content": message}]
            }
            response = self.session.post(
                f"{self.base_url}/api/v1/chat",
                headers=self._get_headers(),
                json=payload,
                stream=True
            )

            if response.status_code == 200:
                print(f"      {Colors.OKCYAN}Response preview:{Colors.ENDC}")

                chunks_received = 0
                full_response = ""
                preview_chars = 150

                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            try:
                                chunk_data = json.loads(data_str)
                                chunk_type = chunk_data.get("type")

                                if chunk_type == "text-delta":
                                    delta = chunk_data.get("delta", "")
                                    full_response += delta
                                    if len(full_response) <= preview_chars:
                                        print(delta, end='', flush=True)
                                    chunks_received += 1
                            except json.JSONDecodeError:
                                continue

                if len(full_response) > preview_chars:
                    print("...")
                else:
                    print()

                self._log_test(
                    "POST /api/v1/chat (second query)",
                    True,
                    f"Received {chunks_received} chunks",
                    {
                        "message": message,
                        "chunks_received": chunks_received,
                        "response_length": len(full_response),
                        "full_response": full_response
                    }
                )
                return True
            else:
                self._log_test(
                    "POST /api/v1/chat (second query)",
                    False,
                    f"Status code: {response.status_code}, Body: {response.text}"
                )
                return False
        except Exception as e:
            self._log_test("POST /api/v1/chat (second query)", False, f"Error: {str(e)}")
            return False

    def export_results(self):
        """Export test results to JSON file."""
        try:
            total = len(self.test_results)
            passed = sum(1 for r in self.test_results if r["passed"])
            failed = total - passed
            success_rate = (passed / total * 100) if total > 0 else 0

            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds() if self.start_time else 0

            export_data = {
                "test_run": {
                    "base_url": self.base_url,
                    "start_time": self.start_time.isoformat() if self.start_time else None,
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration,
                    "tenant_id": self.tenant_id,
                },
                "summary": {
                    "total_tests": total,
                    "passed": passed,
                    "failed": failed,
                    "success_rate": success_rate,
                },
                "tests": self.test_results,
            }

            with open(self.output_file, 'w') as f:
                json.dump(export_data, f, indent=2)

            print(f"\n{Colors.OKCYAN}Results exported to: {self.output_file}{Colors.ENDC}")
            return True
        except Exception as e:
            print(f"\n{Colors.WARNING}Failed to export results: {e}{Colors.ENDC}")
            return False

    def print_summary(self):
        """Print test summary."""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}Test Summary{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed

        print(f"\nTotal Tests: {total}")
        print(f"{Colors.OKGREEN}Passed: {passed}{Colors.ENDC}")
        if failed > 0:
            print(f"{Colors.FAIL}Failed: {failed}{Colors.ENDC}")

        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")

        if failed > 0:
            print(f"\n{Colors.WARNING}Failed Tests:{Colors.ENDC}")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['name']}: {result['message']}")

    def run_all_tests(self, tenant_name: str = None, document_path: str = None):
        """Run all tests in sequence."""
        self.start_time = datetime.now()

        print(f"\n{Colors.BOLD}{Colors.OKBLUE}")
        print("=" * 60)
        print("    COMPREHENSIVE API ENDPOINT TESTING")
        print("=" * 60)
        print(f"{Colors.ENDC}")
        print(f"Base URL: {self.base_url}")
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. Health check
        self.test_health_check()

        # 2. Tenant operations
        tenant_name = tenant_name or f"test-tenant-{int(time.time())}"
        if not self.test_tenant_operations(tenant_name):
            print(f"\n{Colors.FAIL}Tenant operations failed. Stopping tests.{Colors.ENDC}")
            self.print_summary()
            return

        # 3. Document upload
        job_id = self.test_document_upload(document_path)
        if not job_id:
            print(f"\n{Colors.FAIL}Document upload failed. Stopping tests.{Colors.ENDC}")
            self.print_summary()
            return

        # 4. Job status monitoring
        if not self.test_job_status(job_id):
            print(f"\n{Colors.FAIL}Job processing failed. Continuing with remaining tests.{Colors.ENDC}")

        # 5. Query endpoint
        self.test_query_endpoint()

        # 6. Chat endpoint (streaming)
        self.test_chat_endpoint()

        # 7. Chat endpoint (non-streaming)
        self.test_chat_non_streaming()

        # Print summary
        self.print_summary()

        # Export results to JSON
        self.export_results()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive API endpoint testing script"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Base URL of the API (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication (optional)"
    )
    parser.add_argument(
        "--tenant-name",
        help="Tenant name to use (default: auto-generated)"
    )
    parser.add_argument(
        "--document",
        help="Path to document to upload (default: creates test document)"
    )
    parser.add_argument(
        "--output",
        default="test_results.json",
        help="Path to save test results JSON (default: test_results.json)"
    )

    args = parser.parse_args()

    tester = APITester(base_url=args.base_url, api_key=args.api_key, output_file=args.output)
    tester.run_all_tests(tenant_name=args.tenant_name, document_path=args.document)


if __name__ == "__main__":
    main()
