import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal, engine, Base
import models

async def seed_data():
    # Automatically verify and create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Seeding database...")
    async with AsyncSessionLocal() as session:
        # Check if organization already exists
        result = await session.execute(select(models.Organization).where(models.Organization.id == "org_seed"))
        org = result.scalar_one_or_none()
        if org:
            print("Database already seeded.")
            return

        # 1. Create Organization
        org = models.Organization(
            id="org_seed",
            name="Seed Organization"
        )
        session.add(org)

        # 2. Create Team
        team = models.Team(
            id="team_seed",
            organization_id="org_seed",
            name="Seed Engineering Team"
        )
        session.add(team)

        # 3. Create Simulated Users & Memberships
        simulated_users = [
            ("usr_seed", "seed_user@example.com", "Seed Owner", "OWNER"),
            ("usr_admin", "admin_user@example.com", "Admin User", "ADMIN"),
            ("usr_reviewer", "reviewer_user@example.com", "Security Reviewer", "REVIEWER"),
            ("usr_engineer", "engineer_user@example.com", "Software Engineer", "ENGINEER"),
            ("usr_viewer", "viewer_user@example.com", "ReadOnly Viewer", "VIEWER")
        ]

        for uid, email, name, role in simulated_users:
            res = await session.execute(select(models.User).where((models.User.id == uid) | (models.User.email == email)))
            user = res.scalar_one_or_none()
            if not user:
                user = models.User(id=uid, email=email, name=name)
                session.add(user)
                await session.flush()

            # Create membership
            mem_res = await session.execute(
                select(models.Membership)
                .where(models.Membership.organization_id == "org_seed")
                .where(models.Membership.user_id == user.id)
            )
            membership = mem_res.scalar_one_or_none()
            if not membership:
                membership = models.Membership(
                    id=f"mem_{uid}",
                    organization_id="org_seed",
                    user_id=user.id,
                    team_id="team_seed",
                    role=role
                )
                session.add(membership)

        # 5. Create Projects
        project = models.Project(
            id="proj_seed",
            organization_id="org_seed",
            name="API Gateway & Core Services",
            repository="seed-org/seed-repo"
        )
        project_payments = models.Project(
            id="proj_payments",
            organization_id="org_seed",
            name="Payment & Checkout Service",
            repository="seed-org/payment-service"
        )
        session.add_all([project, project_payments])

        # 6. Create Repositories
        repository = models.Repository(
            id="repo_seed",
            organization_id="org_seed",
            project_id="proj_seed",
            name="seed-org/seed-repo",
            url="https://github.com/seed-org/seed-repo"
        )
        repository_payments = models.Repository(
            id="repo_payments",
            organization_id="org_seed",
            project_id="proj_payments",
            name="seed-org/payment-service",
            url="https://github.com/seed-org/payment-service"
        )
        session.add_all([repository, repository_payments])

        # 7. Create Project Policies
        policy = models.ProjectPolicy(
            id="pol_seed",
            organization_id="org_seed",
            project_id="proj_seed",
            auto_merge_threshold=0.90,
            mandatory_review_threshold=0.70,
            restricted_files=["auth.py", "verification.py", "secrets.py"]
        )
        policy_payments = models.ProjectPolicy(
            id="pol_payments",
            organization_id="org_seed",
            project_id="proj_payments",
            auto_merge_threshold=0.90,
            mandatory_review_threshold=0.70,
            restricted_files=["stripe_keys.py", "ledger_lock.py"]
        )
        session.add_all([policy, policy_payments])

        # 8. Create Environments
        env = models.Environment(
            id="env_seed",
            organization_id="org_seed",
            project_id="proj_seed",
            name="production",
            config={"debug": False}
        )
        env_payments = models.Environment(
            id="env_payments",
            organization_id="org_seed",
            project_id="proj_payments",
            name="production",
            config={"debug": False}
        )
        session.add_all([env, env_payments])

        await session.commit()
        print("Database seeded successfully with dual seed repositories!")

if __name__ == "__main__":
    asyncio.run(seed_data())
