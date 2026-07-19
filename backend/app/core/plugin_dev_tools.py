"""Plugin Development Tools - Scaffolding, testing, packaging, publishing"""

from __future__ import annotations

import json
import logging
import subprocess
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ==================== Plugin Scaffolding ====================

class PluginScaffold:
    """Generate plugin project structure"""

    PLUGIN_MANIFEST_TEMPLATE = {
        "name": "{plugin_name}",
        "version": "0.1.0",
        "author": "{author}",
        "description": "{description}",
        "license": "MIT",
        "keywords": [],
        "categories": ["{category}"],
        "capabilities": [],
        "permissions": [],
        "dependencies": {},
        "entry_point": "main.py",
        "icon_url": "",
        "screenshots": [],
        "documentation_url": "",
        "support_url": "",
    }

    PLUGIN_MAIN_TEMPLATE = '''"""
{plugin_name} - {description}

Author: {author}
Version: 0.1.0
"""

from typing import Any, Dict


class {plugin_class}:
    """Main plugin class"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize plugin with configuration"""
        self.config = config
        self.name = "{plugin_name}"
        self.version = "0.1.0"

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plugin action"""
        if action == "hello":
            return {{"message": f"Hello from {self.name}!"}}
        else:
            raise ValueError(f"Unknown action: {{action}}")

    def get_capabilities(self) -> list[str]:
        """Get plugin capabilities"""
        return ["hello"]

    def validate_config(self) -> bool:
        """Validate plugin configuration"""
        return True


# Plugin instance
plugin = None


def initialize(config: Dict[str, Any]) -> None:
    """Initialize plugin"""
    global plugin
    plugin = {plugin_class}(config)


def execute(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute plugin action"""
    if plugin is None:
        raise RuntimeError("Plugin not initialized")
    return plugin.execute(action, params)
'''

    PLUGIN_TEST_TEMPLATE = '''"""
Tests for {plugin_name}
"""

import pytest
from main import {plugin_class}


@pytest.fixture
def plugin():
    """Create plugin instance"""
    config = {{"debug": True}}
    return {plugin_class}(config)


def test_plugin_initialization(plugin):
    """Test plugin initialization"""
    assert plugin.name == "{plugin_name}"
    assert plugin.version == "0.1.0"


def test_plugin_capabilities(plugin):
    """Test plugin capabilities"""
    capabilities = plugin.get_capabilities()
    assert "hello" in capabilities


def test_plugin_execute(plugin):
    """Test plugin execution"""
    result = plugin.execute("hello", {{}})
    assert "message" in result
    assert "{plugin_name}" in result["message"]


def test_plugin_config_validation(plugin):
    """Test plugin configuration validation"""
    assert plugin.validate_config() is True
'''

    PLUGIN_README_TEMPLATE = '''# {plugin_name}

{description}

## Installation

```bash
xagent plugin install {plugin_id}
```

## Usage

```python
from xagent import PluginManager

pm = PluginManager()
plugin = pm.load_plugin("{plugin_id}")
result = plugin.execute("hello", {{}})
print(result)
```

## Configuration

Configure the plugin in your `config.json`:

```json
{{
  "plugins": {{
    "{plugin_id}": {{
      "enabled": true,
      "config": {{}}
    }}
  }}
}}
```

## Development

### Setup

```bash
pip install -r requirements-dev.txt
```

### Testing

```bash
pytest tests/
```

### Building

```bash
xagent plugin build
```

## License

{license}

## Author

{author}
'''

    REQUIREMENTS_TEMPLATE = '''# Plugin dependencies
pytest>=7.0.0
pytest-cov>=4.0.0
'''

    @staticmethod
    def generate(
        plugin_name: str,
        author: str,
        description: str,
        category: str = "development",
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Generate plugin scaffold"""
        if output_dir is None:
            output_dir = Path(f"./{plugin_name}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Create directories
        (output_dir / "tests").mkdir(exist_ok=True)
        (output_dir / "docs").mkdir(exist_ok=True)

        # Generate manifest
        manifest = PluginScaffold.PLUGIN_MANIFEST_TEMPLATE.copy()
        manifest["name"] = plugin_name
        manifest["author"] = author
        manifest["description"] = description
        manifest["categories"] = [category]

        with open(output_dir / "plugin.json", "w") as f:
            json.dump(manifest, f, indent=2)

        # Generate main plugin file
        plugin_class = "".join(word.capitalize() for word in plugin_name.split("_"))
        main_code = PluginScaffold.PLUGIN_MAIN_TEMPLATE.format(
            plugin_name=plugin_name,
            plugin_class=plugin_class,
            description=description,
            author=author,
        )
        with open(output_dir / "main.py", "w") as f:
            f.write(main_code)

        # Generate test file
        test_code = PluginScaffold.PLUGIN_TEST_TEMPLATE.format(
            plugin_name=plugin_name,
            plugin_class=plugin_class,
        )
        with open(output_dir / "tests" / "test_main.py", "w") as f:
            f.write(test_code)

        # Generate README
        readme = PluginScaffold.PLUGIN_README_TEMPLATE.format(
            plugin_name=plugin_name,
            plugin_id=plugin_name.lower().replace("_", "-"),
            description=description,
            author=author,
            license="MIT",
        )
        with open(output_dir / "README.md", "w") as f:
            f.write(readme)

        # Generate requirements
        with open(output_dir / "requirements-dev.txt", "w") as f:
            f.write(PluginScaffold.REQUIREMENTS_TEMPLATE)

        # Generate .gitignore
        gitignore = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.coverage
htmlcov/
.venv/
venv/
"""
        with open(output_dir / ".gitignore", "w") as f:
            f.write(gitignore)

        logger.info(f"Plugin scaffold generated at {output_dir}")
        return output_dir


# ==================== Plugin Packaging ====================

class PluginPackager:
    """Package plugin for distribution"""

    @staticmethod
    def build(plugin_dir: Path) -> Path:
        """Build plugin package"""
        plugin_dir = Path(plugin_dir)

        # Load manifest
        manifest_file = plugin_dir / "plugin.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"plugin.json not found in {plugin_dir}")

        with open(manifest_file) as f:
            manifest = json.load(f)

        plugin_name = manifest["name"]
        version = manifest["version"]

        # Create build directory
        build_dir = plugin_dir / "build"
        build_dir.mkdir(exist_ok=True)

        # Package name
        package_name = f"{plugin_name}-{version}.xplugin"
        package_path = build_dir / package_name

        # Create zip archive
        import zipfile

        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in plugin_dir.rglob("*"):
                if file_path.is_file() and ".git" not in str(file_path) and "build" not in str(file_path):
                    arcname = file_path.relative_to(plugin_dir)
                    zf.write(file_path, arcname)

        logger.info(f"Plugin packaged: {package_path}")
        return package_path

    @staticmethod
    def calculate_hash(package_path: Path) -> str:
        """Calculate SHA256 hash of package"""
        sha256_hash = hashlib.sha256()
        with open(package_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def get_package_info(package_path: Path) -> dict[str, Any]:
        """Get package information"""
        package_path = Path(package_path)
        size = package_path.stat().st_size
        hash_value = PluginPackager.calculate_hash(package_path)

        return {
            "filename": package_path.name,
            "size": size,
            "hash": hash_value,
            "created_at": datetime.now(UTC).isoformat(),
        }


# ==================== Plugin Testing ====================

class PluginTester:
    """Test plugin locally"""

    @staticmethod
    def run_tests(plugin_dir: Path) -> dict[str, Any]:
        """Run plugin tests"""
        plugin_dir = Path(plugin_dir)

        try:
            result = subprocess.run(
                ["pytest", "tests/", "-v", "--tb=short"],
                cwd=plugin_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Test execution timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    def check_code_quality(plugin_dir: Path) -> dict[str, Any]:
        """Check code quality"""
        plugin_dir = Path(plugin_dir)

        issues = []

        # Check for main.py
        if not (plugin_dir / "main.py").exists():
            issues.append("main.py not found")

        # Check for plugin.json
        if not (plugin_dir / "plugin.json").exists():
            issues.append("plugin.json not found")

        # Check for README
        if not (plugin_dir / "README.md").exists():
            issues.append("README.md not found")

        # Check for tests
        if not (plugin_dir / "tests").exists():
            issues.append("tests directory not found")

        return {
            "quality_score": max(0, 100 - len(issues) * 20),
            "issues": issues,
        }


# ==================== Plugin Publishing ====================

class PluginPublisher:
    """Publish plugin to marketplace"""

    @staticmethod
    def prepare_for_publishing(plugin_dir: Path) -> dict[str, Any]:
        """Prepare plugin for publishing"""
        plugin_dir = Path(plugin_dir)

        # Load manifest
        with open(plugin_dir / "plugin.json") as f:
            manifest = json.load(f)

        # Build package
        package_path = PluginPackager.build(plugin_dir)

        # Get package info
        package_info = PluginPackager.get_package_info(package_path)

        # Check code quality
        quality = PluginTester.check_code_quality(plugin_dir)

        return {
            "manifest": manifest,
            "package": package_info,
            "quality": quality,
            "ready": quality["quality_score"] >= 80,
        }

    @staticmethod
    def create_publish_request(
        plugin_dir: Path,
        category: str,
    ) -> dict[str, Any]:
        """Create publish request"""
        plugin_dir = Path(plugin_dir)

        # Load manifest
        with open(plugin_dir / "plugin.json") as f:
            manifest = json.load(f)

        # Build package
        package_path = PluginPackager.build(plugin_dir)
        package_info = PluginPackager.get_package_info(package_path)

        return {
            "manifest": manifest,
            "category": category,
            "package": package_info,
            "package_path": str(package_path),
        }


# ==================== Plugin Documentation ====================

class PluginDocGenerator:
    """Generate plugin documentation"""

    @staticmethod
    def generate_api_docs(plugin_dir: Path) -> str:
        """Generate API documentation"""
        plugin_dir = Path(plugin_dir)

        # Load manifest
        with open(plugin_dir / "plugin.json") as f:
            manifest = json.load(f)

        docs = f"""# {manifest['name']} API Documentation

## Overview

{manifest.get('description', 'No description')}

## Capabilities

"""
        for cap in manifest.get("capabilities", []):
            docs += f"- {cap}\n"

        docs += "\n## Permissions\n\n"
        for perm in manifest.get("permissions", []):
            docs += f"- {perm}\n"

        docs += "\n## Dependencies\n\n"
        for dep, version in manifest.get("dependencies", {}).items():
            docs += f"- {dep} ({version})\n"

        return docs

    @staticmethod
    def generate_user_guide(plugin_dir: Path) -> str:
        """Generate user guide"""
        plugin_dir = Path(plugin_dir)

        # Load README if exists
        readme_path = plugin_dir / "README.md"
        if readme_path.exists():
            with open(readme_path) as f:
                return f.read()

        return "No user guide available"
