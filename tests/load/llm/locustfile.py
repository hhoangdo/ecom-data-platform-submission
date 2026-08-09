"""Future deployed retrieval shape; static Topic 15 contracts never run it live."""

from locust import HttpUser, between, task


FUTURE_HTML = "evidence/04_2_llm_design/load/locust.html"
FUTURE_CSV = "evidence/04_2_llm_design/load/locust_stats"


class RetrievalUser(HttpUser):
    """Exercise success, abstention, and dependency-error retrieval responses."""

    fixed_count = 1
    wait_time = between(1, 1)

    @task
    def success(self) -> None:
        with self.client.post("/v1/retrieval/search", json={"query": "returns", "top_k": 4}, name="success", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("success path did not return 200")

    @task
    def abstention(self) -> None:
        with self.client.post("/v1/retrieval/search", json={"query": "unknown policy", "top_k": 4}, name="abstention", catch_response=True) as response:
            if response.status_code != 200 or not response.json().get("abstained"):
                response.failure("abstention path contract failed")

    @task
    def error(self) -> None:
        with self.client.post("/v1/retrieval/search", json={"query": "timeout", "top_k": 4}, name="error", catch_response=True) as response:
            if response.status_code not in {503, 504}:
                response.failure("error path did not fail explicitly")
