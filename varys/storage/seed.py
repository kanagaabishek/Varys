"""Deterministic seed scenario generator for Varys (Scenarios A & B)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from varys.storage.database import (
    BuildRecord,
    CommitRecord,
    JobRecord,
    TestResultRecord,
    VarysDatabase,
)


def seed_scenario_a(db: VarysDatabase) -> None:
    """Seeds Scenario A: payment-pipeline with flaky DatabaseConnectionTest triggered by commit db7a19f."""
    job_name = "payment-pipeline"
    db.insert_job(
        JobRecord(
            name=job_name,
            description="Main checkout and transaction processing pipeline",
            repository_url="https://github.com/corp/payment-service",
        )
    )

    base_time = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)

    # DatabaseConnectionTest results for builds #201 to #230
    # True = PASS, False = FAIL
    db_test_status = {
        # Baseline healthy (#201 - #215)
        **{b: True for b in range(201, 216)},
        # Trigger commit (#216)
        216: True,
        # Flaky period (#217 - #230)
        217: False,
        218: True,
        219: True,
        220: False,
        221: True,
        222: False,
        223: True,
        224: True,
        225: False,
        226: True,
        227: True,
        228: False,
        229: True,
        230: False,
    }

    routine_messages = [
        ("feat(pay): add idempotency header check", ["src/main/java/io/jenkins/payment/IdempotencyFilter.java"]),
        ("refactor(api): clean up refund DTO validation", ["src/main/java/io/jenkins/payment/dto/RefundRequest.java"]),
        ("fix(auth): update token expiration buffer", ["src/main/java/io/jenkins/payment/auth/TokenProvider.java"]),
        ("perf(cache): optimize payment gateway client pooling", ["src/main/java/io/jenkins/payment/client/GatewayClient.java"]),
        ("chore: upgrade jackson to 2.15.2", ["pom.xml"]),
        ("feat(webhook): add stripe signature verification", ["src/main/java/io/jenkins/payment/webhook/StripeHandler.java"]),
        ("test: add edge cases for partial refunds", ["src/test/java/io/jenkins/payment/refund/RefundEdgeTest.java"]),
        ("fix: handle null order metadata gracefully", ["src/main/java/io/jenkins/payment/service/PaymentService.java"]),
    ]

    for b_num in range(201, 231):
        timestamp_str = (base_time + timedelta(hours=(b_num - 201) * 4)).isoformat()

        # 1. Commit definition
        if b_num == 216:
            commit_hash = "db7a19f"
            author = "alex.dev@corp.com"
            message = "chore(db): update hikari connection pool timeout and idle limits"
            files_changed = ["src/main/resources/application-db.yml"]
            diff_summary = "1 file changed, 4 insertions(+), 2 deletions(-)"
        else:
            commit_hash = f"e{b_num:03d}a{b_num % 10}c"
            author = "dev-team@corp.com"
            msg_tuple = routine_messages[(b_num - 201) % len(routine_messages)]
            message = msg_tuple[0]
            files_changed = msg_tuple[1]
            diff_summary = f"{len(files_changed)} file(s) changed, 12 insertions(+), 3 deletions(-)"

        db.insert_commit(
            CommitRecord(
                commit_hash=commit_hash,
                job_name=job_name,
                author=author,
                message=message,
                files_changed=files_changed,
                diff_summary=diff_summary,
                timestamp=timestamp_str,
            )
        )

        # 2. Build definition
        db_passed = db_test_status[b_num]
        if db_passed:
            build_result = "SUCCESS"
            duration_sec = 425.0 + (b_num % 7) * 4.0
        else:
            build_result = "FAILURE"
            duration_sec = 475.0 + (b_num % 5) * 3.0

        db.insert_build(
            BuildRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                result=build_result,
                duration_sec=duration_sec,
                timestamp=timestamp_str,
                commit_hash=commit_hash,
            )
        )

        # 3. Test results definition (4 tests per build)
        # Always passing tests
        db.insert_test_result(
            TestResultRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                test_name="PaymentIntegrationTest",
                suite_name="io.jenkins.payment.integration",
                status="PASSED",
                duration_sec=1.2,
            )
        )
        db.insert_test_result(
            TestResultRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                test_name="RefundIntegrationTest",
                suite_name="io.jenkins.payment.refund",
                status="PASSED",
                duration_sec=1.1,
            )
        )
        db.insert_test_result(
            TestResultRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                test_name="AuthTokenTest",
                suite_name="io.jenkins.payment.auth",
                status="PASSED",
                duration_sec=0.8,
            )
        )

        # DatabaseConnectionTest
        if db_passed:
            db.insert_test_result(
                TestResultRecord(
                    id=None,
                    job_name=job_name,
                    build_number=b_num,
                    test_name="DatabaseConnectionTest",
                    suite_name="io.jenkins.payment.db",
                    status="PASSED",
                    duration_sec=1.0,
                )
            )
        else:
            db.insert_test_result(
                TestResultRecord(
                    id=None,
                    job_name=job_name,
                    build_number=b_num,
                    test_name="DatabaseConnectionTest",
                    suite_name="io.jenkins.payment.db",
                    status="FAILED",
                    duration_sec=5.1,
                    error_message="SocketTimeoutException: Connection acquisition timeout after 5000ms",
                    stack_trace=(
                        "com.zaxxer.hikari.pool.HikariPool$PoolInitializationException: "
                        "SocketTimeoutException: Connection acquisition timeout after 5000ms\n"
                        "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:182)\n"
                        "\tat io.jenkins.payment.db.DatabaseConnectionTest.testConnectionAcquisition(DatabaseConnectionTest.java:45)"
                    ),
                )
            )


def seed_scenario_b(db: VarysDatabase) -> None:
    """Seeds Scenario B: order-service-build with build duration regression triggered by commit a1f89c0."""
    job_name = "order-service-build"
    db.insert_job(
        JobRecord(
            name=job_name,
            description="Order lifecycle and fulfillment service build & packaging",
            repository_url="https://github.com/corp/order-service",
        )
    )

    base_time = datetime(2026, 9, 22, 8, 0, 0, tzinfo=timezone.utc)

    routine_messages = [
        ("feat(order): add cart item validation", ["src/main/java/io/jenkins/order/CartValidator.java"]),
        ("fix: handling zero quantity orders", ["src/main/java/io/jenkins/order/OrderService.java"]),
        ("refactor: clean up fulfillment event publishers", ["src/main/java/io/jenkins/order/events/OrderPublisher.java"]),
        ("test: add inventory lock timeout tests", ["src/test/java/io/jenkins/order/InventoryLockTest.java"]),
    ]

    for b_num in range(101, 126):
        timestamp_str = (base_time + timedelta(hours=(b_num - 101) * 3)).isoformat()

        # 1. Commit definition
        if b_num == 110:
            commit_hash = "a1f89c0"
            author = "ci-ops@corp.com"
            message = "build(gradle): add full container image scan step to pipeline"
            files_changed = ["Jenkinsfile", "build.gradle.kts"]
            diff_summary = "2 files changed, 28 insertions(+), 2 deletions(-)"
        else:
            commit_hash = f"c{b_num:03d}f{b_num % 10}b"
            author = "order-devs@corp.com"
            msg_tuple = routine_messages[(b_num - 101) % len(routine_messages)]
            message = msg_tuple[0]
            files_changed = msg_tuple[1]
            diff_summary = f"{len(files_changed)} file(s) changed, 8 insertions(+), 1 deletion(-)"

        db.insert_commit(
            CommitRecord(
                commit_hash=commit_hash,
                job_name=job_name,
                author=author,
                message=message,
                files_changed=files_changed,
                diff_summary=diff_summary,
                timestamp=timestamp_str,
            )
        )

        # 2. Build duration progression
        if b_num < 110:
            duration_sec = 245.0 + (b_num % 5) * 3.0
        elif b_num == 110:
            duration_sec = 780.0
        else:
            duration_sec = 950.0 + (b_num - 110) * 8.5

        db.insert_build(
            BuildRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                result="SUCCESS",
                duration_sec=duration_sec,
                timestamp=timestamp_str,
                commit_hash=commit_hash,
            )
        )

        # 3. Test results (all pass fast)
        db.insert_test_result(
            TestResultRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                test_name="OrderFlowTest",
                suite_name="io.jenkins.order.flow",
                status="PASSED",
                duration_sec=22.5,
            )
        )
        db.insert_test_result(
            TestResultRecord(
                id=None,
                job_name=job_name,
                build_number=b_num,
                test_name="InventorySyncTest",
                suite_name="io.jenkins.order.inventory",
                status="PASSED",
                duration_sec=21.0,
            )
        )


def seed_all(db_path: str | Path = "varys.db", reset: bool = True) -> VarysDatabase:
    """Initializes and seeds all test scenarios into SQLite."""
    db = VarysDatabase(db_path)
    if reset:
        db.reset_database()
    seed_scenario_a(db)
    seed_scenario_b(db)
    return db


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Varys SQLite test scenarios.")
    parser.add_argument("--db-path", default="varys.db", help="Path to SQLite database file")
    parser.add_argument(
        "--reset",
        action="store_true",
        default=True,
        help="Reset and recreate tables before seeding (default: True)",
    )
    args = parser.parse_args()

    print(f"Seeding scenarios into {args.db_path}...")
    db = seed_all(db_path=args.db_path, reset=args.reset)
    jobs = db.get_all_jobs()
    print(f"Successfully seeded {len(jobs)} jobs: {[j['name'] for j in jobs]}")


if __name__ == "__main__":
    main()
