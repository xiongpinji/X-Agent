"""Skill CLI - Command-line interface for skill management"""

from __future__ import annotations

import asyncio
import json
import sys

from .skills_executor import get_skill_executor
from .skills_loader import get_skill_loader
from .skills_marketplace import get_skill_marketplace
from .skills_registry import get_skill_registry


class SkillCLI:
    """Command-line interface for skill management"""

    def __init__(self):
        self.loader = get_skill_loader()
        self.registry = get_skill_registry()
        self.executor = get_skill_executor()
        self.marketplace = get_skill_marketplace()

    async def list_skills(self, installed_only: bool = False) -> None:
        """List available skills"""
        if installed_only:
            skills = self.loader.list_loaded_skills()
            print(f"\nLoaded Skills ({len(skills)}):")
            for skill_name in skills:
                metadata = self.loader.get_skill_metadata(skill_name)
                if metadata:
                    print(f"  - {metadata.name} v{metadata.version}")
                    print(f"    Description: {metadata.description}")
                    print(f"    Capabilities: {', '.join(c.value for c in metadata.capabilities)}")
        else:
            skills = self.registry.list_skills()
            print(f"\nAvailable Skills ({len(skills)}):")
            for metadata in skills:
                rating = self.registry.get_skill_rating(metadata.skill_id)
                print(f"  - {metadata.name} v{metadata.version}")
                print(f"    Description: {metadata.description}")
                print(f"    Author: {metadata.author}")
                if rating:
                    print(f"    Rating: {rating.average_rating:.1f}/5.0 ({rating.total_ratings} ratings)")
                    print(f"    Downloads: {rating.download_count}")

    async def search_skills(self, query: str) -> None:
        """Search for skills"""
        results = self.registry.search_skills(query)
        print(f"\nSearch Results for '{query}' ({len(results)}):")
        for result in results:
            print(f"  - {result.name} v{result.version}")
            print(f"    Description: {result.description}")
            print(f"    Rating: {result.rating:.1f}/5.0")
            print(f"    Downloads: {result.download_count}")

    async def show_skill_info(self, skill_id: str) -> None:
        """Show detailed skill information"""
        metadata = self.registry.get_skill(skill_id)
        if not metadata:
            print(f"Skill not found: {skill_id}")
            return

        rating = self.registry.get_skill_rating(skill_id)
        installation = self.marketplace.get_installation(skill_id)

        print(f"\nSkill: {metadata.name}")
        print(f"ID: {metadata.skill_id}")
        print(f"Version: {metadata.version}")
        print(f"Author: {metadata.author}")
        print(f"License: {metadata.license}")
        print(f"Description: {metadata.description}")
        print(f"Risk Level: {metadata.risk_level.value}")
        print(f"Timeout: {metadata.timeout_seconds}s")
        print(f"Max Memory: {metadata.max_memory_mb}MB")
        print(f"Capabilities: {', '.join(c.value for c in metadata.capabilities)}")
        print(f"Tags: {', '.join(metadata.tags)}")

        if rating:
            print(f"\nRating: {rating.average_rating:.1f}/5.0 ({rating.total_ratings} ratings)")
            print(f"Downloads: {rating.download_count}")

        if installation:
            print("\nInstalled: Yes")
            print(f"Install Path: {installation.install_path}")
            print(f"Installed At: {installation.installed_at}")
        else:
            print("\nInstalled: No")

    async def install_skill(self, skill_id: str, user_id: str = "") -> None:
        """Install a skill"""
        print(f"Installing skill: {skill_id}...")
        success, error = await self.marketplace.install_skill(skill_id, user_id=user_id)

        if success:
            print(f"Successfully installed skill: {skill_id}")
        else:
            print(f"Failed to install skill: {error}")

    async def uninstall_skill(self, skill_id: str) -> None:
        """Uninstall a skill"""
        print(f"Uninstalling skill: {skill_id}...")
        success, error = await self.marketplace.uninstall_skill(skill_id)

        if success:
            print(f"Successfully uninstalled skill: {skill_id}")
        else:
            print(f"Failed to uninstall skill: {error}")

    async def load_skill(self, skill_module_path: str, skill_name: str) -> None:
        """Load a skill from a module"""
        print(f"Loading skill: {skill_name}...")
        success, error = await self.loader.load_skill(skill_module_path, skill_name)

        if success:
            print(f"Successfully loaded skill: {skill_name}")
        else:
            print(f"Failed to load skill: {error}")

    async def execute_skill(
        self,
        skill_name: str,
        input_file: str | None = None,
        user_id: str = "",
    ) -> None:
        """Execute a skill"""
        # Load input data
        input_data = {}
        if input_file:
            with open(input_file) as f:
                input_data = json.load(f)

        print(f"Executing skill: {skill_name}...")
        result = await self.executor.execute_skill(
            skill_name=skill_name,
            input_data=input_data,
            user_id=user_id,
        )

        if result.success:
            print("Execution successful!")
            print(f"Output: {json.dumps(result.data, indent=2, default=str)}")
            print(f"Execution time: {result.execution_time_ms:.2f}ms")
        else:
            print(f"Execution failed: {result.error}")

    async def list_installed(self) -> None:
        """List installed skills"""
        installations = self.marketplace.list_installations()
        print(f"\nInstalled Skills ({len(installations)}):")
        for installation in installations:
            print(f"  - {installation.skill_id} v{installation.version}")
            print(f"    Installed at: {installation.installed_at}")
            print(f"    Path: {installation.install_path}")

    async def check_updates(self) -> None:
        """Check for available updates"""
        updates = await self.marketplace.check_updates()
        if not updates:
            print("All skills are up to date!")
            return

        print(f"\nAvailable Updates ({len(updates)}):")
        for skill_id, current_version, new_version in updates:
            print(f"  - {skill_id}: {current_version} -> {new_version}")

    async def show_stats(self) -> None:
        """Show marketplace statistics"""
        stats = self.marketplace.get_marketplace_stats()
        registry_stats = self.registry.get_statistics()

        print("\nMarketplace Statistics:")
        print(f"  Total Packages: {stats['total_packages']}")
        print(f"  Total Installed: {stats['total_installed']}")
        print(f"  Total Size: {stats['total_size_mb']:.2f}MB")

        print("\nRegistry Statistics:")
        print(f"  Total Skills: {registry_stats['total_skills']}")
        print(f"  Total Downloads: {registry_stats['total_downloads']}")
        print(f"  Average Rating: {registry_stats['average_rating']:.2f}/5.0")
        print(f"  Capabilities: {registry_stats['capabilities_count']}")
        print(f"  Tags: {registry_stats['tags_count']}")

    async def show_help(self) -> None:
        """Show help message"""
        help_text = """
X-Agent Skill CLI

Usage: xagent-skill <command> [options]

Commands:
  list                    List all available skills
  list-installed          List installed skills
  search <query>          Search for skills
  info <skill_id>         Show skill information
  install <skill_id>      Install a skill
  uninstall <skill_id>    Uninstall a skill
  load <path> <name>      Load a skill from a module
  execute <name>          Execute a skill
  updates                 Check for available updates
  stats                   Show marketplace statistics
  help                    Show this help message

Examples:
  xagent-skill list
  xagent-skill search document
  xagent-skill info word-processor
  xagent-skill install word-processor
  xagent-skill execute word-processor --input input.json
"""
        print(help_text)


async def main():
    """Main CLI entry point"""
    cli = SkillCLI()

    if len(sys.argv) < 2:
        await cli.show_help()
        return

    command = sys.argv[1]

    try:
        if command == "list":
            await cli.list_skills()
        elif command == "list-installed":
            await cli.list_skills(installed_only=True)
        elif command == "search" and len(sys.argv) > 2:
            await cli.search_skills(sys.argv[2])
        elif command == "info" and len(sys.argv) > 2:
            await cli.show_skill_info(sys.argv[2])
        elif command == "install" and len(sys.argv) > 2:
            await cli.install_skill(sys.argv[2])
        elif command == "uninstall" and len(sys.argv) > 2:
            await cli.uninstall_skill(sys.argv[2])
        elif command == "load" and len(sys.argv) > 3:
            await cli.load_skill(sys.argv[2], sys.argv[3])
        elif command == "execute" and len(sys.argv) > 2:
            input_file = None
            if "--input" in sys.argv:
                idx = sys.argv.index("--input")
                if idx + 1 < len(sys.argv):
                    input_file = sys.argv[idx + 1]
            await cli.execute_skill(sys.argv[2], input_file)
        elif command == "updates":
            await cli.check_updates()
        elif command == "stats":
            await cli.show_stats()
        elif command == "help":
            await cli.show_help()
        else:
            print(f"Unknown command: {command}")
            await cli.show_help()

    except Exception as e:
        print(f"Error: {e!s}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
