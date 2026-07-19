"""Phase 3 integration tests for MCP, Artifacts, and Search."""

import pytest
import tempfile
from pathlib import Path

from backend.app.core.mcp import MCPServer, MCPRequest, MCPResponse
from backend.app.core.artifacts import Artifact, ArtifactStorage, ArtifactRenderer
from backend.app.core.mcp.tools.file_tool import FileOperationTool
from backend.app.core.mcp.tools.search_tool import SearchOperationTool


class TestMCPIntegration:
    """Test MCP integration."""

    @pytest.mark.asyncio
    async def test_mcp_file_tool_integration(self):
        """Test MCP file tool integration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = MCPServer()
            file_tool = FileOperationTool(base_path=tmpdir)

            # Register file operations
            server.register_tool(
                "file_read",
                file_tool.read_file,
                description="Read file",
                input_schema={"path": "string"},
            )

            server.register_tool(
                "file_write",
                file_tool.write_file,
                description="Write file",
                input_schema={"path": "string", "content": "string"},
            )

            # Test write operation
            write_request = MCPRequest(
                type="request",
                method="tools/call",
                params={"tool": "file_write", "args": {"path": "test.txt", "content": "Hello"}},
            )

            write_response = await server.handle_request(write_request)
            assert write_response.type == "result"
            assert write_response.result["output"]["success"] is True

            # Test read operation
            read_request = MCPRequest(
                type="request",
                method="tools/call",
                params={"tool": "file_read", "args": {"path": "test.txt"}},
            )

            read_response = await server.handle_request(read_request)
            assert read_response.type == "result"
            assert "Hello" in read_response.result["output"]

    @pytest.mark.asyncio
    async def test_mcp_search_tool_integration(self):
        """Test MCP search tool integration."""
        server = MCPServer()
        search_tool = SearchOperationTool()

        server.register_tool(
            "search_web",
            search_tool.search_web,
            description="Search web",
            input_schema={"query": "string", "num_results": "integer"},
        )

        request = MCPRequest(
            type="request",
            method="tools/call",
            params={"tool": "search_web", "args": {"query": "test", "num_results": 5}},
        )

        response = await server.handle_request(request)
        assert response.type == "result"
        assert "query" in response.result["output"]


class TestArtifactIntegration:
    """Test artifact system integration."""

    @pytest.mark.asyncio
    async def test_artifact_creation_and_rendering(self):
        """Test artifact creation and rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)
            renderer = ArtifactRenderer()

            # Create HTML artifact
            artifact = Artifact(
                name="Test Report",
                type="html",
                content="<h1>Test Report</h1><p>This is a test.</p>",
            )

            artifact_id = await storage.save_artifact(artifact)
            loaded = await storage.load_artifact(artifact_id)

            # Render artifact
            html = await renderer.render(loaded)
            assert "<h1>Test Report</h1>" in html
            assert "This is a test." in html

    @pytest.mark.asyncio
    async def test_artifact_chart_rendering(self):
        """Test chart artifact rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)
            renderer = ArtifactRenderer()

            artifact = Artifact(
                name="Sales Chart",
                type="chart",
                content="{}",
                metadata={
                    "chart_type": "bar",
                    "data": {
                        "labels": ["Jan", "Feb", "Mar"],
                        "datasets": [{"label": "Sales", "data": [10, 20, 30]}],
                    },
                },
            )

            artifact_id = await storage.save_artifact(artifact)
            loaded = await storage.load_artifact(artifact_id)

            html = await renderer.render(loaded)
            assert "chart.js" in html.lower()
            assert "Sales Chart" in html

    @pytest.mark.asyncio
    async def test_artifact_table_rendering(self):
        """Test table artifact rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)
            renderer = ArtifactRenderer()

            artifact = Artifact(
                name="Data Table",
                type="table",
                content="{}",
                metadata={
                    "data": [
                        {"name": "Alice", "age": 30, "city": "NYC"},
                        {"name": "Bob", "age": 25, "city": "LA"},
                    ]
                },
            )

            artifact_id = await storage.save_artifact(artifact)
            loaded = await storage.load_artifact(artifact_id)

            html = await renderer.render(loaded)
            assert "<table>" in html
            assert "Alice" in html
            assert "Bob" in html
            assert "NYC" in html

    @pytest.mark.asyncio
    async def test_artifact_dashboard_rendering(self):
        """Test dashboard artifact rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)
            renderer = ArtifactRenderer()

            artifact = Artifact(
                name="Analytics Dashboard",
                type="dashboard",
                content="{}",
                description="Real-time analytics",
                metadata={
                    "data": {
                        "Users": "1,234",
                        "Revenue": "$45,678",
                        "Growth": "23%",
                    }
                },
            )

            artifact_id = await storage.save_artifact(artifact)
            loaded = await storage.load_artifact(artifact_id)

            html = await renderer.render(loaded)
            assert "dashboard" in html.lower()
            assert "Users" in html
            assert "1,234" in html
            assert "Revenue" in html

    @pytest.mark.asyncio
    async def test_artifact_filtering_and_search(self):
        """Test artifact filtering and search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)

            # Create various artifacts
            for i in range(3):
                artifact = Artifact(
                    name=f"Report {i}",
                    type="html",
                    content="<h1>Report</h1>",
                    tags=["report", "important"],
                )
                await storage.save_artifact(artifact)

            for i in range(2):
                artifact = Artifact(
                    name=f"Chart {i}",
                    type="chart",
                    content="{}",
                    tags=["chart"],
                )
                await storage.save_artifact(artifact)

            # Test filtering by type
            html_artifacts = await storage.list_artifacts(artifact_type="html")
            assert len(html_artifacts) == 3

            chart_artifacts = await storage.list_artifacts(artifact_type="chart")
            assert len(chart_artifacts) == 2

            # Test filtering by tags
            important = await storage.list_artifacts(tags=["important"])
            assert len(important) == 3

            # Test search
            results = await storage.search_artifacts("Report")
            assert len(results) == 3

            results = await storage.search_artifacts("Chart")
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_artifact_update_and_delete(self):
        """Test artifact update and delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)

            artifact = Artifact(
                name="Original",
                type="html",
                content="<h1>Original</h1>",
            )

            artifact_id = await storage.save_artifact(artifact)

            # Update artifact
            updated = await storage.update_artifact(
                artifact_id,
                {"name": "Updated", "content": "<h1>Updated</h1>"},
            )

            assert updated.name == "Updated"
            assert updated.content == "<h1>Updated</h1>"

            # Delete artifact
            deleted = await storage.delete_artifact(artifact_id)
            assert deleted is True

            loaded = await storage.load_artifact(artifact_id)
            assert loaded is None


class TestSearchIntegration:
    """Test search system integration."""

    @pytest.mark.asyncio
    async def test_search_tool_content_extraction(self):
        """Test search tool content extraction."""
        search_tool = SearchOperationTool()

        html = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <h1>Main Title</h1>
            <p>First paragraph with content.</p>
            <p>Second paragraph with more content.</p>
        </body>
        </html>
        """

        title = search_tool._extract_title(html)
        assert title == "Test Page"

        content = search_tool._extract_content(html)
        assert "First paragraph" in content
        assert "Second paragraph" in content

        metadata = search_tool._extract_metadata(html)
        assert metadata.get("description") == "Test description"

    @pytest.mark.asyncio
    async def test_mcp_with_artifacts(self):
        """Test MCP integration with artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = MCPServer()
            storage = ArtifactStorage(tmpdir)

            # Create an artifact
            artifact = Artifact(
                name="MCP Test",
                type="html",
                content="<h1>MCP Test</h1>",
            )

            artifact_id = await storage.save_artifact(artifact)

            # Register a tool that returns artifact info
            async def get_artifact_info(artifact_id: str):
                artifact = await storage.load_artifact(artifact_id)
                if artifact:
                    return {
                        "id": artifact.id,
                        "name": artifact.name,
                        "type": artifact.type,
                    }
                return None

            server.register_tool(
                "get_artifact",
                get_artifact_info,
                description="Get artifact info",
                input_schema={"artifact_id": "string"},
            )

            # Call the tool
            request = MCPRequest(
                type="request",
                method="tools/call",
                params={"tool": "get_artifact", "args": {"artifact_id": artifact_id}},
            )

            response = await server.handle_request(request)
            assert response.type == "result"
            assert response.result["output"]["name"] == "MCP Test"

    @pytest.mark.asyncio
    async def test_artifact_stats(self):
        """Test artifact statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArtifactStorage(tmpdir)

            # Create artifacts
            for i in range(3):
                artifact = Artifact(
                    name=f"HTML {i}",
                    type="html",
                    content="<h1>Test</h1>",
                )
                await storage.save_artifact(artifact)

            for i in range(2):
                artifact = Artifact(
                    name=f"Chart {i}",
                    type="chart",
                    content="{}",
                )
                await storage.save_artifact(artifact)

            stats = await storage.get_artifact_stats()
            assert stats["total_artifacts"] == 5
            assert stats["by_type"]["html"] == 3
            assert stats["by_type"]["chart"] == 2
