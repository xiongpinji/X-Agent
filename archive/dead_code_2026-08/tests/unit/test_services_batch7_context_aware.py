"""归档自 tests/unit/test_services_batch7.py（2026-08-04 死代码收敛）

测试对象 context_aware 已归档至 archive/dead_code_2026-08/backend/app/core/。
（归档态不可运行，仅作测试对象记录）
"""

class TestProjectStructure:
    def test_structure_creation(self):
        from backend.app.core.context_aware import ProjectStructure
        ps = ProjectStructure(
            root="/project",
            name="MyProject",
            language="python",
        )
        assert ps.root == "/project"
        assert ps.language == "python"

    def test_structure_to_dict(self):
        from backend.app.core.context_aware import ProjectStructure
        ps = ProjectStructure(root="/p", name="P", language="python")
        d = ps.to_dict()
        assert d["root"] == "/p"
        assert d["language"] == "python"


class TestArchitecturePattern:
    def test_pattern_creation(self):
        from backend.app.core.context_aware import ArchitecturePattern
        ap = ArchitecturePattern(name="MVC", confidence=0.9)
        assert ap.name == "MVC"
        assert ap.confidence == 0.9

    def test_pattern_to_dict(self):
        from backend.app.core.context_aware import ArchitecturePattern
        ap = ArchitecturePattern(name="Layered", confidence=0.8, layers=["ui", "service", "data"])
        d = ap.to_dict()
        assert d["name"] == "Layered"
        assert len(d["layers"]) == 3


class TestCodeConvention:
    def test_convention_creation(self):
        from backend.app.core.context_aware import CodeConvention
        cc = CodeConvention(
            name="snake_case",
            category="naming",
            pattern=r"^[a-z_]+$",
        )
        assert cc.name == "snake_case"
        assert cc.enforcement_level == "recommended"

    def test_convention_to_dict(self):
        from backend.app.core.context_aware import CodeConvention
        cc = CodeConvention(name="test", category="testing", pattern="test_*")
        d = cc.to_dict()
        assert d["category"] == "testing"


class TestProjectContext:
    def test_context_creation(self):
        from backend.app.core.context_aware import ProjectContext, ProjectStructure
        ps = ProjectStructure(root="/p", name="P", language="python")
        ctx = ProjectContext(project_structure=ps)
        assert ctx.project_structure == ps
        assert ctx.context_id is not None

    def test_context_to_dict(self):
        from backend.app.core.context_aware import ProjectContext, ProjectStructure
        ps = ProjectStructure(root="/p", name="P", language="python")
        ctx = ProjectContext(project_structure=ps)
        d = ctx.to_dict()
        assert "project_structure" in d
        assert "context_id" in d


class TestProjectStructureAnalyzer:
    def test_analyzer_exists(self):
        from backend.app.core.context_aware import ProjectStructureAnalyzer
        assert ProjectStructureAnalyzer is not None


class TestContextAwareEngine:
    def test_engine_creation(self):
        from backend.app.core.context_aware import ContextAwareEngine
        engine = ContextAwareEngine()
        assert engine is not None


# ═══════════════════════════════════════════════════════════════════════════════
# I18N MODULE
# ═══════════════════════════════════════════════════════════════════════════════

