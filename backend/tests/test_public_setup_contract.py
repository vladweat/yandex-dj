"""Keep the documented host profile and Compose networking distinct."""

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def environment_value(path: Path, name: str) -> str:
    for line in path.read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{name} is missing from {path}")


class PublicSetupContractTests(unittest.TestCase):
    def test_env_example_uses_host_database_address(self) -> None:
        database_url = environment_value(
            REPOSITORY_ROOT / "backend" / ".env.example", "DATABASE_URL"
        )
        self.assertIn("@localhost:", database_url)

    def test_compose_overrides_database_address_for_api_container(self) -> None:
        compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text()
        self.assertIn(
            "DATABASE_URL: postgresql+asyncpg://prompt_dj:prompt_dj@db:5432/prompt_dj",
            compose,
        )

    def test_ci_generates_a_fresh_encryption_key(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("Fernet.generate_key()", workflow)

    def test_ci_grants_only_read_access_to_repository_contents(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("permissions:\n  contents: read", workflow)


if __name__ == "__main__":
    unittest.main()
