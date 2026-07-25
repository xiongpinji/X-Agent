"""Seed demo data for customer demonstrations.

Usage:
    python scripts/seed_demo.py [--reset]

Creates:
    - 3 demo agents (code assistant, data analyst, web researcher)
    - 2 demo workflows (daily report, code review pipeline)
    - 5 demo goals
    - Sample memories
    - Demo tenant with quota

Options:
    --reset     Clear existing demo data before seeding
    --api       Seed via HTTP API (requires running server on localhost:8000)
    --port N    Server port (default: 8000)
"""

import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEMO_DIR = PROJECT_ROOT / "data" / "demo"
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Demo data definitions (fallback if JSON files missing)
# ---------------------------------------------------------------------------

DEMO_AGENTS = [
    {
        "name": "Code Assistant",
        "description": "帮助编写、审查和重构代码的智能助手",
        "role": "assistant",
        "title": "高级代码助手",
        "capabilities": ["code_generation", "code_review", "refactoring", "debugging"],
        "model": "gpt-4o-mini",
        "memory_scope": {
            "persona": "你是一位经验丰富的全栈工程师，擅长 Python、TypeScript、Go 等语言",
            "workflow_name": "code_assistant",
        },
    },
    {
        "name": "Data Analyst",
        "description": "分析数据、生成报告和可视化图表",
        "role": "assistant",
        "title": "数据分析专家",
        "capabilities": ["data_analysis", "visualization", "reporting", "sql_query"],
        "model": "gpt-4o-mini",
        "memory_scope": {
            "persona": "你是一位数据分析师，擅长使用 Python pandas/matplotlib 进行数据分析和可视化",
            "workflow_name": "data_analyst",
        },
    },
    {
        "name": "Web Researcher",
        "description": "搜索网络信息、汇总研究结果",
        "role": "assistant",
        "title": "网络研究员",
        "capabilities": ["web_search", "summarization", "citation", "fact_checking"],
        "model": "gpt-4o-mini",
        "memory_scope": {
            "persona": "你是一位研究分析师，擅长从多个来源收集和综合信息",
            "workflow_name": "web_researcher",
        },
    },
]

DEMO_WORKFLOWS = [
    {
        "name": "Daily Report Generator",
        "description": "每日自动收集数据、分析趋势并生成报告的工作流",
        "nodes": [
            {"id": "collect_data", "type": "tool", "config": {"tool_name": "data_collector", "sources": ["database", "api_metrics", "user_activity"]}},
            {"id": "analyze", "type": "agent", "config": {"agent_type": "data_analyst", "task": "分析收集到的数据，识别关键趋势和异常"}},
            {"id": "generate_report", "type": "agent", "config": {"agent_type": "report_writer", "task": "根据分析结果生成结构化的每日报告"}},
            {"id": "output", "type": "output", "config": {"format": "markdown", "destination": "reports/daily"}},
        ],
        "edges": [
            {"source": "collect_data", "target": "analyze"},
            {"source": "analyze", "target": "generate_report"},
            {"source": "generate_report", "target": "output"},
        ],
    },
    {
        "name": "Code Review Pipeline",
        "description": "自动化代码审查流水线：静态分析 → AI 审查 → 人工审批",
        "nodes": [
            {"id": "input_code", "type": "input", "config": {"description": "待审查的代码变更 (diff 或 PR 链接)"}},
            {"id": "static_analysis", "type": "tool", "config": {"tool_name": "linter", "rules": ["ruff", "mypy", "bandit"]}},
            {"id": "ai_review", "type": "agent", "config": {"agent_type": "code_reviewer", "task": "审查代码质量、安全性、性能，给出改进建议"}},
            {"id": "quality_gate", "type": "condition", "config": {"left": "${static_analysis.exit_code}", "operator": "equals", "right": "0"}},
            {"id": "approval", "type": "approval", "config": {"approvers": ["tech_lead"], "timeout_hours": 24}},
            {"id": "output_pass", "type": "output", "config": {"status": "approved", "format": "json"}},
            {"id": "output_fail", "type": "output", "config": {"status": "rejected", "format": "json"}},
        ],
        "edges": [
            {"source": "input_code", "target": "static_analysis"},
            {"source": "static_analysis", "target": "ai_review"},
            {"source": "ai_review", "target": "quality_gate"},
            {"source": "quality_gate", "target": "approval", "condition": "true"},
            {"source": "quality_gate", "target": "output_fail", "condition": "false"},
            {"source": "approval", "target": "output_pass"},
        ],
    },
]

DEMO_GOALS = [
    {
        "objective": "完成用户认证模块重构，支持 OIDC 和 SAML 协议",
        "status": "active",
        "checkpoints": [
            {"label": "OIDC discovery endpoint 配置完成", "done": True},
            {"label": "SAML metadata 交换实现", "done": True},
            {"label": "Token 刷新机制", "done": False},
            {"label": "集成测试通过", "done": False},
        ],
    },
    {
        "objective": "将 API 响应时间 P99 降低到 200ms 以内",
        "status": "active",
        "checkpoints": [
            {"label": "性能基线测量", "done": True},
            {"label": "数据库查询优化", "done": True},
            {"label": "缓存层引入", "done": False},
            {"label": "负载测试验证", "done": False},
        ],
    },
    {
        "objective": "构建自动化 CI/CD 流水线，实现每日自动部署",
        "status": "active",
        "checkpoints": [
            {"label": "GitHub Actions 工作流配置", "done": True},
            {"label": "Docker 镜像自动构建", "done": True},
            {"label": "Staging 环境自动部署", "done": True},
            {"label": "Production 蓝绿部署", "done": False},
        ],
    },
    {
        "objective": "实现多租户数据隔离和配额管理",
        "status": "completed",
        "checkpoints": [
            {"label": "租户模型设计", "done": True},
            {"label": "数据隔离中间件", "done": True},
            {"label": "配额限制实现", "done": True},
            {"label": "计费集成", "done": True},
        ],
    },
    {
        "objective": "完成产品文档国际化 (中/英/日)",
        "status": "active",
        "checkpoints": [
            {"label": "i18n 框架搭建", "done": True},
            {"label": "中文文档完善", "done": True},
            {"label": "英文文档翻译", "done": False},
            {"label": "日文文档翻译", "done": False},
        ],
    },
]

DEMO_MEMORIES = [
    {"content": "用户偏好使用 Python 3.11+，代码风格遵循 PEP 8", "layer": 1, "tags": ["preference", "python"]},
    {"content": "项目使用 FastAPI + PostgreSQL 技术栈", "layer": 2, "tags": ["architecture", "tech_stack"]},
    {"content": "团队采用 Trunk-Based Development，主分支为 main", "layer": 2, "tags": ["workflow", "git"]},
    {"content": "上次会话讨论了性能优化方案，决定引入 Redis 缓存层", "layer": 3, "tags": ["session", "performance"]},
    {"content": "客户要求所有 API 响应时间 < 200ms (P99)", "layer": 1, "tags": ["requirement", "sla"]},
]

DEMO_TENANT = {
    "name": "Demo Corp",
    "plan": "professional",
    "quota": {
        "max_agents": 10,
        "max_workflows": 20,
        "max_runs_per_day": 1000,
        "max_memory_entries": 50000,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(filename: str, fallback: list | dict) -> list | dict:
    """Load demo data from JSON file, fall back to built-in definitions."""
    path = DEMO_DIR / filename
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return fallback


def _print_header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def _print_ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _print_skip(msg: str) -> None:
    print(f"  [SKIP] {msg}")


def _print_info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# Direct seeding (no server required)
# ---------------------------------------------------------------------------


def seed_direct(reset: bool = False) -> None:
    """Seed demo data directly into data stores (file-based, no server needed)."""
    _print_header("X-Agent Demo Data Seeder (direct mode)")

    # --- Ensure demo data directory ---
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    # --- Write/refresh demo JSON files ---
    agents = _load_json("agents.json", DEMO_AGENTS)
    workflows = _load_json("workflows.json", DEMO_WORKFLOWS)
    goals = _load_json("goals.json", DEMO_GOALS)

    # Always persist canonical copies
    for fname, data in [("agents.json", agents), ("workflows.json", workflows), ("goals.json", goals)]:
        path = DEMO_DIR / fname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _print_ok(f"Demo data file: data/demo/{fname}")

    # --- Seed workflows into data/workflows.json ---
    _print_header("Seeding Workflows")
    wf_store_path = DATA_DIR / "workflows.json"
    existing_wfs: dict = {}
    if wf_store_path.exists() and not reset:
        try:
            with open(wf_store_path, encoding="utf-8") as f:
                existing_wfs = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_wfs = {}

    if reset:
        # Remove demo workflows (identified by name)
        demo_names = {w["name"] for w in workflows}
        if isinstance(existing_wfs, dict):
            definitions = existing_wfs.get("definitions", {})
            definitions = {k: v for k, v in definitions.items() if v.get("name") not in demo_names}
            existing_wfs["definitions"] = definitions
        else:
            existing_wfs = {}

    # Add demo workflows
    if isinstance(existing_wfs, dict):
        definitions = existing_wfs.setdefault("definitions", {})
    else:
        definitions = {}
        existing_wfs = {"definitions": definitions}

    for wf in workflows:
        wf_id = f"demo-{uuid4().hex[:8]}"
        # Check if already exists by name
        existing_id = next(
            (k for k, v in definitions.items() if v.get("name") == wf["name"]),
            None,
        )
        if existing_id and not reset:
            _print_skip(f"Workflow '{wf['name']}' already exists (id={existing_id})")
            continue
        wf_id = existing_id or wf_id
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        definitions[wf_id] = {
            "id": wf_id,
            "name": wf["name"],
            "description": wf["description"],
            "nodes": wf["nodes"],
            "edges": wf["edges"],
            "created_at": now,
            "updated_at": now,
        }
        _print_ok(f"Workflow '{wf['name']}' (id={wf_id})")

    with open(wf_store_path, "w", encoding="utf-8") as f:
        json.dump(existing_wfs, f, ensure_ascii=False, indent=2)
    _print_info(f"Workflow store: {wf_store_path}")

    # --- Seed memories into data/memory.jsonl ---
    _print_header("Seeding Memories")
    mem_path = DATA_DIR / "memory.jsonl"
    if reset and mem_path.exists():
        # Keep non-demo memories (those without demo_tenant marker)
        kept = []
        with open(mem_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("tenant_id") != "demo-tenant":
                        kept.append(line)
                except json.JSONDecodeError:
                    kept.append(line)
        with open(mem_path, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n" if kept else "")

    with open(mem_path, "a", encoding="utf-8") as f:
        for mem in DEMO_MEMORIES:
            entry = {
                "id": str(uuid4()),
                "tenant_id": "demo-tenant",
                "agent_id": "demo-agent",
                "content": mem["content"],
                "layer": mem["layer"],
                "tags": mem["tags"],
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _print_ok(f"Seeded {len(DEMO_MEMORIES)} memory entries")

    # --- Seed goals (write to demo dir; goals API is in-memory) ---
    _print_header("Seeding Goals")
    goals_out = []
    for g in goals:
        goal_entry = {
            "id": f"goal-{uuid4().hex[:12]}",
            "objective": g["objective"],
            "status": g["status"],
            "checkpoints": g.get("checkpoints", []),
            "created_at": time.time(),
        }
        goals_out.append(goal_entry)
        _print_ok(f"Goal: {g['objective'][:40]}...")

    goals_seed_path = DEMO_DIR / "goals_seeded.json"
    with open(goals_seed_path, "w", encoding="utf-8") as f:
        json.dump(goals_out, f, ensure_ascii=False, indent=2)
    _print_info(f"Goals saved to: data/demo/goals_seeded.json")

    # --- Demo tenant info ---
    _print_header("Demo Tenant")
    tenant_path = DEMO_DIR / "tenant.json"
    tenant_data = {
        **DEMO_TENANT,
        "id": "demo-tenant",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(tenant_path, "w", encoding="utf-8") as f:
        json.dump(tenant_data, f, ensure_ascii=False, indent=2)
    _print_ok(f"Tenant: {DEMO_TENANT['name']} (plan={DEMO_TENANT['plan']})")
    _print_info(f"Tenant config: data/demo/tenant.json")

    # --- Summary ---
    _print_header("Seed Complete!")
    print(f"""
  Demo data summary:
    Agents:    {len(agents)} (Code Assistant, Data Analyst, Web Researcher)
    Workflows: {len(workflows)} (Daily Report, Code Review Pipeline)
    Goals:     {len(goals)} objectives with checkpoints
    Memories:  {len(DEMO_MEMORIES)} sample entries
    Tenant:    {DEMO_TENANT['name']} ({DEMO_TENANT['plan']} plan)

  Data locations:
    data/demo/agents.json       - Agent definitions
    data/demo/workflows.json    - Workflow definitions
    data/demo/goals.json        - Goal templates
    data/demo/goals_seeded.json - Seeded goals with IDs
    data/demo/tenant.json       - Demo tenant config
    data/workflows.json         - Live workflow store
    data/memory.jsonl           - Live memory store

  Next steps:
    1. Start the server:  uvicorn backend.app.main:app --reload --port 8000
    2. Or use quickstart: python scripts/quickstart.py
    3. Open browser:      http://localhost:8000
""")


# ---------------------------------------------------------------------------
# API seeding (requires running server)
# ---------------------------------------------------------------------------


def seed_via_api(port: int = 8000, reset: bool = False) -> None:
    """Seed demo data via HTTP API calls to a running server."""
    import urllib.error
    import urllib.request

    base_url = f"http://localhost:{port}"
    _print_header(f"X-Agent Demo Data Seeder (API mode → {base_url})")

    def api_post(path: str, payload: dict) -> dict | None:
        url = f"{base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"  [ERROR] {path} → HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
            return None
        except urllib.error.URLError as e:
            print(f"  [ERROR] Cannot connect to {base_url}: {e.reason}")
            print("  [INFO] Falling back to direct mode...")
            seed_direct(reset=reset)
            return None

    # Health check
    try:
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise ConnectionError()
    except Exception:
        print(f"  [ERROR] Server not reachable at {base_url}")
        print("  [INFO] Falling back to direct mode...")
        seed_direct(reset=reset)
        return

    _print_ok("Server is healthy")

    # Seed workflows
    _print_header("Seeding Workflows via API")
    workflows = _load_json("workflows.json", DEMO_WORKFLOWS)
    for wf in workflows:
        result = api_post("/api/v1/workflows", {
            "name": wf["name"],
            "description": wf["description"],
            "nodes": wf["nodes"],
            "edges": wf["edges"],
        })
        if result:
            _print_ok(f"Workflow '{wf['name']}' created (id={result.get('id', '?')})")

    # Seed goals
    _print_header("Seeding Goals via API")
    goals = _load_json("goals.json", DEMO_GOALS)
    for g in goals:
        result = api_post("/api/v1/goals", {"objective": g["objective"]})
        if result:
            _print_ok(f"Goal: {g['objective'][:40]}... (id={result.get('id', '?')})")

    _print_header("API Seed Complete!")
    print(f"\n  Open http://localhost:{port} to explore the demo data.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed X-Agent demo data for customer demonstrations")
    parser.add_argument("--reset", action="store_true", help="Clear existing demo data before seeding")
    parser.add_argument("--api", action="store_true", help="Seed via HTTP API (requires running server)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    if args.api:
        seed_via_api(port=args.port, reset=args.reset)
    else:
        seed_direct(reset=args.reset)


if __name__ == "__main__":
    main()
