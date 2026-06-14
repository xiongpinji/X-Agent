"""Database Seed Script — populate demo/test data for X-Agent.

Usage:
    python scripts/seed_data.py [--mode demo|test|minimal]

Modes:
    minimal: 1 admin user + 1 API key (for first-time setup)
    demo: Full demo dataset for presentations (3 users, 5 runs, 10 events, 2 workflows)
    test: Randomized data for load testing (100 users, 500 runs)

Example:
    python scripts/seed_data.py --mode demo
    python scripts/seed_data.py --mode minimal
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timedelta
from typing import Optional
import random
import string

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Import models from backend
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.models import (
    Base,
    User,
    APIKey,
    AgentRun,
    AuditLog,
    Workflow,
    WorkflowStep,
)


class SeedDataGenerator:
    """Generate and populate seed data into database."""

    def __init__(self, db_url: str, mode: str = "demo"):
        """Initialize seed generator.
        
        Args:
            db_url: Database URL (e.g., postgresql+asyncpg://user:pass@localhost/xagent)
            mode: Seed mode - minimal, demo, or test
        """
        self.db_url = db_url
        self.mode = mode
        self.engine = None
        self.async_session = None

    async def connect(self):
        """Connect to database."""
        # Use NullPool for simplicity in seed script
        self.engine = create_async_engine(
            self.db_url,
            echo=False,
            poolclass=NullPool,
        )
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def disconnect(self):
        """Disconnect from database."""
        if self.engine:
            await self.engine.dispose()

    async def create_tables(self):
        """Create all tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    def _generate_api_key(prefix: str = "sk") -> str:
        """Generate a realistic API key."""
        random_part = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        return f"{prefix}_{random_part}"

    async def seed_minimal(self):
        """Seed minimal dataset (first-time setup)."""
        async with self.async_session() as session:
            # Admin user
            admin = User(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@xagent.local",
                full_name="Administrator",
                password_hash="$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMUe",  # password: admin
                is_active=True,
                is_superuser=True,
                created_at=datetime.utcnow(),
            )
            session.add(admin)

            # API key for admin
            api_key = APIKey(
                id=str(uuid.uuid4()),
                user_id=admin.id,
                name="Initial Admin Key",
                key=self._generate_api_key(),
                is_active=True,
                last_used_at=None,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365),
            )
            session.add(api_key)

            await session.commit()
            print("✓ Minimal seed completed (1 admin, 1 API key)")

    async def seed_demo(self):
        """Seed demo dataset for presentations."""
        async with self.async_session() as session:
            # Create 3 demo users
            users = []
            user_configs = [
                ("admin", "admin@xagent.local", "Administrator", True, True),
                ("developer", "dev@xagent.local", "Developer User", True, False),
                ("viewer", "viewer@xagent.local", "Viewer User", True, False),
            ]

            for username, email, full_name, is_active, is_superuser in user_configs:
                user = User(
                    id=str(uuid.uuid4()),
                    username=username,
                    email=email,
                    full_name=full_name,
                    password_hash="$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMUe",  # password
                    is_active=is_active,
                    is_superuser=is_superuser,
                    created_at=datetime.utcnow() - timedelta(days=30),
                )
                session.add(user)
                users.append(user)

            await session.flush()

            # Create API keys for each user
            for user in users:
                for i in range(2):
                    api_key = APIKey(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        name=f"{user.username} key {i+1}",
                        key=self._generate_api_key(),
                        is_active=True,
                        last_used_at=datetime.utcnow() - timedelta(days=random.randint(0, 7)),
                        created_at=datetime.utcnow() - timedelta(days=random.randint(7, 30)),
                        expires_at=datetime.utcnow() + timedelta(days=365),
                    )
                    session.add(api_key)

            await session.flush()

            # Create 5 sample agent runs
            run_statuses = ["completed", "failed", "pending", "running", "completed"]
            run_descriptions = [
                "Analyze code repository for security issues",
                "Generate API documentation",
                "Refactor legacy module",
                "Create database migration",
                "Review pull request changes",
            ]

            for i, (status, description) in enumerate(zip(run_statuses, run_descriptions)):
                started_at = datetime.utcnow() - timedelta(days=random.randint(1, 14))
                
                run = AgentRun(
                    id=str(uuid.uuid4()),
                    user_id=users[i % len(users)].id,
                    name=f"Run #{i+1}: {description}",
                    prompt=f"Please {description.lower()}",
                    status=status,
                    started_at=started_at,
                    completed_at=started_at + timedelta(hours=random.randint(1, 8)) if status != "running" else None,
                    result={
                        "status": status,
                        "output": f"Generated result for: {description}",
                        "metrics": {
                            "issues_found": random.randint(0, 50),
                            "duration_seconds": random.randint(60, 3600),
                        }
                    },
                    created_at=started_at,
                )
                session.add(run)

            await session.flush()

            # Create 10 audit events
            audit_actions = [
                "user.login", "user.logout", "api_key.created", "api_key.used",
                "run.started", "run.completed", "workflow.created", "workflow.executed",
                "user.updated", "settings.changed"
            ]

            for i in range(10):
                audit = AuditLog(
                    id=str(uuid.uuid4()),
                    user_id=users[i % len(users)].id,
                    action=audit_actions[i % len(audit_actions)],
                    resource_type="agent" if i % 3 == 0 else "user",
                    resource_id=str(uuid.uuid4()),
                    details={
                        "ip_address": f"192.168.1.{random.randint(1, 255)}",
                        "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
                        "status": "success" if i % 4 != 0 else "failed",
                    },
                    created_at=datetime.utcnow() - timedelta(hours=random.randint(0, 168)),
                )
                session.add(audit)

            await session.flush()

            # Create 2 workflows
            workflows = []
            workflow_configs = [
                ("Code Review Pipeline", "Automated code review for pull requests"),
                ("Security Audit", "Weekly security audit of repositories"),
            ]

            for name, description in workflow_configs:
                workflow = Workflow(
                    id=str(uuid.uuid4()),
                    user_id=users[0].id,
                    name=name,
                    description=description,
                    config={
                        "trigger": "webhook",
                        "enabled": True,
                        "schedule": "0 */4 * * *" if "Weekly" in name else None,
                    },
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(7, 30)),
                )
                session.add(workflow)
                workflows.append(workflow)

            await session.flush()

            # Add steps to workflows
            step_configs = [
                ("analyze", "Analyze repository"),
                ("report", "Generate report"),
                ("notify", "Send notifications"),
            ]

            for workflow in workflows:
                for step_order, (step_id, step_name) in enumerate(step_configs, 1):
                    step = WorkflowStep(
                        id=str(uuid.uuid4()),
                        workflow_id=workflow.id,
                        step_id=step_id,
                        name=step_name,
                        type="action",
                        config={"timeout": 300, "retries": 2},
                        order=step_order,
                    )
                    session.add(step)

            await session.commit()
            print("✓ Demo seed completed (3 users, 6 API keys, 5 runs, 10 audits, 2 workflows with 6 steps)")

    async def seed_test(self):
        """Seed test dataset for load testing."""
        async with self.async_session() as session:
            print("Generating test seed data...")
            
            # Create 100 test users
            users = []
            for i in range(100):
                user = User(
                    id=str(uuid.uuid4()),
                    username=f"testuser_{i:03d}",
                    email=f"test{i:03d}@xagent.local",
                    full_name=f"Test User {i}",
                    password_hash="$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMUe",
                    is_active=random.choice([True, True, True, False]),  # 75% active
                    is_superuser=False,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                )
                session.add(user)
                users.append(user)
                
                if (i + 1) % 20 == 0:
                    print(f"  Created {i+1}/100 users")

            await session.flush()

            # Create API keys (2 per user)
            print("Creating API keys...")
            for i, user in enumerate(users):
                for j in range(2):
                    api_key = APIKey(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        name=f"key_{i:03d}_{j}",
                        key=self._generate_api_key(),
                        is_active=random.choice([True, True, False]),
                        last_used_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)) if random.random() > 0.3 else None,
                        created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                        expires_at=datetime.utcnow() + timedelta(days=random.randint(30, 365)),
                    )
                    session.add(api_key)

            await session.flush()

            # Create 500 agent runs
            print("Creating 500 agent runs...")
            statuses = ["completed", "failed", "pending", "running"]
            for i in range(500):
                status = random.choice(statuses)
                started_at = datetime.utcnow() - timedelta(days=random.randint(1, 60))
                
                run = AgentRun(
                    id=str(uuid.uuid4()),
                    user_id=random.choice(users).id,
                    name=f"Test Run {i:04d}",
                    prompt=f"Task description {i}",
                    status=status,
                    started_at=started_at,
                    completed_at=started_at + timedelta(minutes=random.randint(5, 120)) if status in ["completed", "failed"] else None,
                    result={
                        "status": status,
                        "output": f"Result for test run {i}",
                        "metrics": {
                            "tokens_used": random.randint(100, 5000),
                            "duration_seconds": random.randint(10, 3600),
                        }
                    },
                    created_at=started_at,
                )
                session.add(run)
                
                if (i + 1) % 100 == 0:
                    print(f"  Created {i+1}/500 runs")

            await session.flush()

            # Create audit logs (random sampling)
            print("Creating audit logs...")
            for i in range(200):
                audit = AuditLog(
                    id=str(uuid.uuid4()),
                    user_id=random.choice(users).id,
                    action=random.choice(["user.login", "user.logout", "api_key.used", "run.started", "run.completed"]),
                    resource_type=random.choice(["agent", "user", "workflow"]),
                    resource_id=str(uuid.uuid4()),
                    details={
                        "ip_address": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                        "status": "success" if random.random() > 0.1 else "failed",
                    },
                    created_at=datetime.utcnow() - timedelta(hours=random.randint(0, 1440)),
                )
                session.add(audit)

            await session.commit()
            print("✓ Test seed completed (100 users, 200 API keys, 500 runs, 200 audits)")

    async def seed(self):
        """Execute seeding based on mode."""
        await self.connect()
        await self.create_tables()
        
        if self.mode == "minimal":
            await self.seed_minimal()
        elif self.mode == "demo":
            await self.seed_demo()
        elif self.mode == "test":
            await self.seed_test()
        else:
            raise ValueError(f"Unknown seed mode: {self.mode}")
        
        await self.disconnect()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed X-Agent database with demo/test data"
    )
    parser.add_argument(
        "--mode",
        choices=["minimal", "demo", "test"],
        default="demo",
        help="Seed mode (default: demo)",
    )
    parser.add_argument(
        "--db-url",
        default="postgresql+asyncpg://xagent:xagent@localhost/xagent",
        help="Database URL",
    )

    args = parser.parse_args()

    generator = SeedDataGenerator(args.db_url, args.mode)
    await generator.seed()
    print(f"\n✓ Database seeded successfully with '{args.mode}' mode")


if __name__ == "__main__":
    asyncio.run(main())
