"""Single-process Locust only: use run_load.py to prepare isolated sandbox data."""

import json
import os
import time
from collections import Counter, deque
from pathlib import Path

from gevent import sleep
from locust import HttpUser, between, events, task
from locust.exception import StopUser

accounts = deque()
outcomes = Counter()
started_at = 0.0
course_id = None


@events.test_start.add_listener
def start(environment, **kwargs):
    global started_at, course_id
    data = json.loads(Path(os.environ["LOAD_CREDENTIALS"]).read_text(encoding="utf-8"))
    accounts.clear()
    accounts.extend(data["accounts"])
    outcomes.clear()
    course_id = data["course_id"]
    started_at = time.monotonic()


@events.test_stop.add_listener
def stop(environment, **kwargs):
    Path(os.environ.get("LOAD_OUTCOMES", "results/local/outcomes.json")).write_text(
        json.dumps(dict(outcomes), indent=2), encoding="utf-8"
    )


class Student(HttpUser):
    abstract = True
    wait_time = between(0.3, 0.8)

    def on_start(self):
        if not accounts:
            raise StopUser()
        account = accounts.popleft()
        self.enrolled_once = False
        with self.client.post("/auth/token", data=account, catch_response=True) as response:
            if response.status_code != 200:
                response.failure("Login failed")
                raise StopUser()
            self.client.headers["Authorization"] = "Bearer " + response.json()["access_token"]

    def enroll(self):
        with self.client.post(
            f"/courses/{course_id}/enroll", name="/courses/[id]/enroll", catch_response=True
        ) as response:
            outcomes[str(response.status_code)] += 1
            if response.status_code == 409:
                detail = response.json().get("detail")
                if detail in {"Already enrolled", "Course is full"}:
                    outcomes[detail] += 1
                    response.success()  # A documented business refusal, counted separately.
                else:
                    response.failure("Unexpected conflict")
            elif response.status_code != 201:
                response.failure(f"Unexpected enrollment status {response.status_code}")
        self.enrolled_once = True

    def browse(self):
        self.client.get("/courses")

    def mine(self):
        self.client.get("/enrollments/me")

    def enrollment(self):
        if not self.enrolled_once:
            self.enroll()
        else:
            self.client.get("/users/me")


class NormalUser(Student):
    tasks = {Student.browse: 3, Student.mine: 1, Student.enrollment: 1}


class SpikeUser(Student):
    tasks = []
    wait_time = between(0.2, 0.4)

    @task
    def opening(self):
        # Each VUser reaches this gate before 15 seconds and waits for one shared instant.
        if not self.enrolled_once:
            remaining = started_at + 15 - time.monotonic()
            if remaining > 0:
                sleep(remaining)
            self.enroll()
        else:
            self.client.get("/courses")
            self.client.get("/enrollments/me")
