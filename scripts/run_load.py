"""Real HTTP load and CPU/RAM collection; never run against production."""

import argparse
import csv
import json
import os
import platform
import secrets
import subprocess
import sys
import time
from getpass import getpass
from pathlib import Path

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]


def memory_bytes(value):
    number, unit = value.strip().split() if " " in value.strip() else (None, None)
    if number is not None:
        return float(number) * {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}[unit]
    for unit, factor in [("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024), ("B", 1)]:
        if value.endswith(unit):
            return float(value[: -len(unit)]) * factor
    raise ValueError(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["normal", "spike"])
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--pid", type=int, help="Native API PID; otherwise use Docker stats")
    parser.add_argument("--db-pid", type=int, help="Native PostgreSQL parent PID")
    parser.add_argument("--output", default="results/local")
    args = parser.parse_args()
    os.chdir(ROOT)
    output = Path(args.output) / (args.profile + "_" + time.strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True)
    users, spawn, duration = (10, 2, 60) if args.profile == "normal" else (50, 10, 60)
    capacity = users if args.profile == "normal" else 10
    with httpx.Client(base_url=args.host, timeout=30) as client:
        health = client.get("/health")
        health.raise_for_status()
        if health.json().get("environment") != "sandbox":
            raise SystemExit("Only sandbox is allowed")
        username = input("Sandbox administrator username: ")
        password = getpass("Administrator password: ")
        login = client.post("/auth/token", data={"username": username, "password": password})
        login.raise_for_status()
        auth = {"Authorization": "Bearer " + login.json()["access_token"]}
        run_id = secrets.token_hex(4)
        course = client.post(
            "/admin/courses",
            headers=auth,
            json={"title": f"Load {args.profile} {run_id}", "capacity": capacity},
        )
        course.raise_for_status()
        course_id = course.json()["id"]
        accounts = []
        for i in range(users):
            account = {"username": f"load_{run_id}_{i}", "password": secrets.token_urlsafe(20)}
            client.post("/auth/register", json=account).raise_for_status()
            accounts.append(account)
    credentials = output / "credentials.json"
    credentials.write_text(
        json.dumps({"accounts": accounts, "course_id": course_id}), encoding="utf-8"
    )
    env = os.environ.copy()
    env["LOAD_CREDENTIALS"] = str(credentials.resolve())
    env["LOAD_OUTCOMES"] = str((output / "outcomes.json").resolve())
    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "load/locustfile.py",
        "NormalUser" if args.profile == "normal" else "SpikeUser",
        "--headless",
        "--host",
        args.host,
        "-u",
        str(users),
        "-r",
        str(spawn),
        "-t",
        f"{duration}s",
        "--csv",
        str(output / "load"),
        "--csv-full-history",
        "--html",
        str(output / "locust.html"),
    ]
    metadata = {
        "profile": args.profile,
        "vusers": users,
        "spawn_per_second": spawn,
        "ramp_seconds": users / spawn,
        "duration_seconds": duration,
        "opening_seconds": 15 if args.profile == "spike" else None,
        "capacity": capacity,
        "course_id": course_id,
        "host": args.host,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": psutil.cpu_count(),
        "resource_errors": [],
        "measurement": "native process RSS" if args.pid else "docker stats working set",
    }
    processes = {}
    if args.pid:
        for name, pid in [("api", args.pid), ("postgres", args.db_pid)]:
            if pid:
                for process in [psutil.Process(pid), *psutil.Process(pid).children(recursive=True)]:
                    processes[(name, process.pid)] = process
                    process.cpu_percent()
    process = None
    try:
        with (
            (output / "locust.log").open("w", encoding="utf-8") as log,
            (output / "resources.csv").open("w", newline="", encoding="utf-8") as resource_file,
        ):
            writer = csv.writer(resource_file)
            writer.writerow(["elapsed_seconds", "service", "cpu_percent", "ram_bytes"])
            started = time.monotonic()
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            while process.poll() is None:
                elapsed = time.monotonic() - started
                try:
                    if args.pid:
                        totals = {}
                        for (name, _), item in processes.items():
                            if item.is_running():
                                values = totals.setdefault(name, [0, 0])
                                values[0] += item.cpu_percent()
                                values[1] += item.memory_info().rss
                        for name, values in totals.items():
                            writer.writerow([elapsed, name, *values])
                    else:
                        for name in ["api", "db"]:
                            container = subprocess.check_output(
                                ["docker", "compose", "ps", "-q", name], text=True, timeout=10
                            ).strip()
                            if not container:
                                raise RuntimeError(f"No running Compose {name}")
                            raw = subprocess.check_output(
                                [
                                    "docker",
                                    "stats",
                                    "--no-stream",
                                    "--format",
                                    "{{json .}}",
                                    container,
                                ],
                                text=True,
                                timeout=10,
                            )
                            row = json.loads(raw)
                            writer.writerow(
                                [
                                    elapsed,
                                    name,
                                    float(row["CPUPerc"].strip("%")),
                                    memory_bytes(row["MemUsage"].split("/")[0].strip()),
                                ]
                            )
                except (
                    OSError,
                    subprocess.SubprocessError,
                    ValueError,
                    RuntimeError,
                    psutil.Error,
                ) as exc:
                    message = str(exc)
                    if message not in metadata["resource_errors"]:
                        metadata["resource_errors"].append(message)
                resource_file.flush()
                time.sleep(1)
            metadata["locust_exit_code"] = process.returncode
        with httpx.Client(base_url=args.host, timeout=30) as client:
            response = client.get("/courses")
            response.raise_for_status()
            final = next(c for c in response.json() if c["id"] == course_id)
            metadata["remaining_seats"] = final["available_seats"]
            metadata["capacity_invariant_ok"] = 0 <= final["available_seats"] <= capacity
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        subprocess.run([sys.executable, "scripts/summarize_load.py", str(output)], check=True)
        print(f"Results: {output}")
        if process.returncode or not metadata["capacity_invariant_ok"]:
            raise SystemExit("Load check failed; inspect results")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        credentials.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
