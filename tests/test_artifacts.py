"""Artifact system tests."""

import pytest
import tempfile
from pathlib import Path

from backend.app.core.artifacts import Artifact, ArtifactStorage, ArtifactRenderer


@pytest.fixture
def temp_storage():
    """Create temporary storage for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ArtifactStorage(tmpdir)


@pytest.mark.asyncio
async def test_artifact_creation():
    """Test artifact creation."""
    artifact = Artifact(
        name="Test Artifact",
        type="html",
        content="<h1>Test</h1>",
    )

    assert artifact.name == "Test Artifact"
    assert artifact.type == "html"
    assert artifact.id is not None


@pytest.mark.asyncio
async def test_save_and_load_artifact(temp_storage):
    """Test saving and loading artifact."""
    artifact = Artifact(
        name="Test",
        type="html",
        content="<h1>Test</h1>",
        tags=["test"],
    )

    artifact_id = await temp_storage.save_artifact(artifact)
    assert artifact_id == artifact.id

    loaded = await temp_storage.load_artifact(artifact_id)
    assert loaded is not None
    assert loaded.name == "Test"
    assert loaded.type == "html"


@pytest.mark.asyncio
async def test_delete_artifact(temp_storage):
    """Test deleting artifact."""
    artifact = Artifact(
        name="Test",
        type="html",
        content="<h1>Test</h1>",
    )

    artifact_id = await temp_storage.save_artifact(artifact)
    deleted = await temp_storage.delete_artifact(artifact_id)
    assert deleted is True

    loaded = await temp_storage.load_artifact(artifact_id)
    assert loaded is None


@pytest.mark.asyncio
async def test_list_artifacts(temp_storage):
    """Test listing artifacts."""
    for i in range(5):
        artifact = Artifact(
            name=f"Artifact {i}",
            type="html" if i % 2 == 0 else "chart",
            content="<h1>Test</h1>",
        )
        await temp_storage.save_artifact(artifact)

    artifacts = await temp_storage.list_artifacts()
    assert len(artifacts) == 5


@pytest.mark.asyncio
async def test_filter_by_type(temp_storage):
    """Test filtering artifacts by type."""
    for i in range(3):
        artifact = Artifact(
            name=f"HTML {i}",
            type="html",
            content="<h1>Test</h1>",
        )
        await temp_storage.save_artifact(artifact)

    for i in range(2):
        artifact = Artifact(
            name=f"Chart {i}",
            type="chart",
            content="{}",
        )
        await temp_storage.save_artifact(artifact)

    html_artifacts = await temp_storage.list_artifacts(artifact_type="html")
    assert len(html_artifacts) == 3

    chart_artifacts = await temp_storage.list_artifacts(artifact_type="chart")
    assert len(chart_artifacts) == 2


@pytest.mark.asyncio
async def test_filter_by_tags(temp_storage):
    """Test filtering artifacts by tags."""
    artifact1 = Artifact(
        name="Tagged 1",
        type="html",
        content="<h1>Test</h1>",
        tags=["important", "test"],
    )
    await temp_storage.save_artifact(artifact1)

    artifact2 = Artifact(
        name="Tagged 2",
        type="html",
        content="<h1>Test</h1>",
        tags=["important"],
    )
    await temp_storage.save_artifact(artifact2)

    artifact3 = Artifact(
        name="Untagged",
        type="html",
        content="<h1>Test</h1>",
    )
    await temp_storage.save_artifact(artifact3)

    important = await temp_storage.list_artifacts(tags=["important"])
    assert len(important) == 2


@pytest.mark.asyncio
async def test_search_artifacts(temp_storage):
    """Test searching artifacts."""
    artifact1 = Artifact(
        name="Python Tutorial",
        type="html",
        content="<h1>Python</h1>",
        description="Learn Python programming",
    )
    await temp_storage.save_artifact(artifact1)

    artifact2 = Artifact(
        name="JavaScript Guide",
        type="html",
        content="<h1>JavaScript</h1>",
        description="Learn JavaScript",
    )
    await temp_storage.save_artifact(artifact2)

    results = await temp_storage.search_artifacts("Python")
    assert len(results) == 1
    assert results[0].name == "Python Tutorial"


@pytest.mark.asyncio
async def test_update_artifact(temp_storage):
    """Test updating artifact."""
    artifact = Artifact(
        name="Original",
        type="html",
        content="<h1>Original</h1>",
    )

    artifact_id = await temp_storage.save_artifact(artifact)

    updated = await temp_storage.update_artifact(
        artifact_id,
        {"name": "Updated", "content": "<h1>Updated</h1>"},
    )

    assert updated is not None
    assert updated.name == "Updated"
    assert updated.content == "<h1>Updated</h1>"


@pytest.mark.asyncio
async def test_artifact_stats(temp_storage):
    """Test artifact statistics."""
    for i in range(3):
        artifact = Artifact(
            name=f"HTML {i}",
            type="html",
            content="<h1>Test</h1>",
        )
        await temp_storage.save_artifact(artifact)

    for i in range(2):
        artifact = Artifact(
            name=f"Chart {i}",
            type="chart",
            content="{}",
        )
        await temp_storage.save_artifact(artifact)

    stats = await temp_storage.get_artifact_stats()
    assert stats["total_artifacts"] == 5
    assert stats["by_type"]["html"] == 3
    assert stats["by_type"]["chart"] == 2


@pytest.mark.asyncio
async def test_render_html_artifact():
    """Test rendering HTML artifact."""
    renderer = ArtifactRenderer()
    artifact = Artifact(
        name="Test",
        type="html",
        content="<h1>Hello</h1>",
    )

    html = await renderer.render_html(artifact)
    assert "<h1>Hello</h1>" in html


@pytest.mark.asyncio
async def test_render_chart_artifact():
    """Test rendering chart artifact."""
    renderer = ArtifactRenderer()
    artifact = Artifact(
        name="Test Chart",
        type="chart",
        content="{}",
        metadata={"chart_type": "bar"},
    )

    html = await renderer.render_chart(artifact)
    assert "chart.js" in html.lower()
    assert "Test Chart" in html


@pytest.mark.asyncio
async def test_render_table_artifact():
    """Test rendering table artifact."""
    renderer = ArtifactRenderer()
    artifact = Artifact(
        name="Test Table",
        type="table",
        content="{}",
        metadata={
            "data": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25},
            ]
        },
    )

    html = await renderer.render_table(artifact)
    assert "<table>" in html
    assert "Alice" in html
    assert "Bob" in html


@pytest.mark.asyncio
async def test_render_dashboard_artifact():
    """Test rendering dashboard artifact."""
    renderer = ArtifactRenderer()
    artifact = Artifact(
        name="Test Dashboard",
        type="dashboard",
        content="{}",
        metadata={
            "data": {
                "Users": 1000,
                "Revenue": 50000,
                "Growth": "25%",
            }
        },
    )

    html = await renderer.render_dashboard(artifact)
    assert "dashboard" in html.lower()
    assert "Users" in html
    assert "1000" in html
