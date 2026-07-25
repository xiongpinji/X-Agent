# -*- coding: utf-8 -*-
"""P1-21 文档收敛迁移脚本 (dry-run / execute)。
用法: python _doc_migration_build.py [execute]
"""
import os, sys, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
MAP = {}  # src (repo-relative, /) -> dst (repo-relative, /)

def m(src, dst):
    assert src not in MAP, f"dup src {src}"
    MAP[src] = dst

# ============ 根目录 *.md ============
KEEP_ROOT = {
    "README.md", "CHANGELOG.md", "ROADMAP.md", "CONTRIBUTING.md",
    "CONTRIBUTING_EN.md", "LICENSE", "CODE_OF_CONDUCT.md", "SUPPORT.md",
    "PULL_REQUEST_TEMPLATE.md", "CLAUDE.md", "plan.md",
}
# --- concepts ---
m("项目总览与开发指南.md", "docs/concepts/项目总览与开发指南.md")
m("ARCHITECTURE_OPTIMIZATION.md", "docs/concepts/architecture/ARCHITECTURE_OPTIMIZATION.md")
m("CONCURRENCY_ARCHITECTURE.md", "docs/concepts/architecture/CONCURRENCY_ARCHITECTURE.md")
m("PARALLEL_AGENTS_README.md", "docs/concepts/architecture/PARALLEL_AGENTS_README.md")
m("PARALLEL_TOOLS_INTEGRATION.md", "docs/concepts/architecture/PARALLEL_TOOLS_INTEGRATION.md")
m("PARALLEL_TOOLS_README.md", "docs/concepts/architecture/PARALLEL_TOOLS_README.md")
m("COMPETITIVE_GAP_ANALYSIS_2026.md", "docs/concepts/planning/COMPETITIVE_GAP_ANALYSIS_2026.md")
m("BROWSER_AUTOMATION_README.md", "docs/concepts/features/BROWSER_AUTOMATION_README.md")
m("CACHE_IMPLEMENTATION.md", "docs/concepts/features/CACHE_IMPLEMENTATION.md")
m("CONFIG_SYSTEM_README.md", "docs/concepts/features/CONFIG_SYSTEM_README.md")
m("CONTEXT_MANAGEMENT_FILES.md", "docs/concepts/features/CONTEXT_MANAGEMENT_FILES.md")
m("FILESYSTEM_README.md", "docs/concepts/features/FILESYSTEM_README.md")
m("HYBRID_MEMORY_IMPLEMENTATION.md", "docs/concepts/features/HYBRID_MEMORY_IMPLEMENTATION.md")
m("MEMORY_DEDUPLICATION_IMPLEMENTATION.md", "docs/concepts/features/MEMORY_DEDUPLICATION_IMPLEMENTATION.md")
m("MEMORY_FUSION_README.md", "docs/concepts/features/MEMORY_FUSION_README.md")
m("SKILLS_SYSTEM_README.md", "docs/concepts/features/SKILLS_SYSTEM_README.md")
m("WORKFLOW_IMPLEMENTATION.md", "docs/concepts/features/WORKFLOW_IMPLEMENTATION.md")
m("X_AGENT_STANDARD_UPGRADE.md", "docs/concepts/features/X_AGENT_STANDARD_UPGRADE.md")
m("X-Agent标准升级文档.md", "docs/concepts/features/X-Agent标准升级文档.md")
m("FEATURE_ENHANCEMENTS.md", "docs/concepts/features/FEATURE_ENHANCEMENTS.md")
# --- operations ---
m("INSTALL.md", "docs/operations/setup/INSTALL.md")
m("QUICKSTART.md", "docs/operations/setup/QUICKSTART.md")
m("QUICK_START.md", "docs/operations/setup/QUICK_START.md")
m("DEPLOYMENT.md", "docs/operations/deployment/DEPLOYMENT.md")
m("DISASTER_RECOVERY.md", "docs/operations/deployment/DISASTER_RECOVERY.md")
m("ROLLBACK_PROCEDURE.md", "docs/operations/deployment/ROLLBACK_PROCEDURE.md")
m("UPGRADE_PLAN.md", "docs/operations/deployment/UPGRADE_PLAN.md")
m("RELEASE_READINESS.md", "docs/operations/deployment/RELEASE_READINESS.md")
m("PERFORMANCE_BENCHMARK_REPORT.md", "docs/operations/monitoring/PERFORMANCE_BENCHMARK_REPORT.md")
m("PERFORMANCE_INDEX.md", "docs/operations/monitoring/PERFORMANCE_INDEX.md")
m("PERFORMANCE_OPTIMIZATION_README.md", "docs/operations/monitoring/PERFORMANCE_OPTIMIZATION_README.md")
m("PERFORMANCE_OPTIMIZATION_REPORT.md", "docs/operations/monitoring/PERFORMANCE_OPTIMIZATION_REPORT.md")
m("PERFORMANCE_QUICK_REFERENCE.md", "docs/operations/monitoring/PERFORMANCE_QUICK_REFERENCE.md")
# --- admin ---
m("SECURITY_DECISIONS.md", "docs/admin/security/SECURITY_DECISIONS.md")
# --- developer/api ---
m("API_ENDPOINTS_DOCUMENTATION.md", "docs/developer/api/API_ENDPOINTS_DOCUMENTATION.md")
m("API_QUICK_REFERENCE.md", "docs/developer/api/API_QUICK_REFERENCE.md")
m("PHASE3_API_DOCUMENTATION.md", "docs/developer/api/PHASE3_API_DOCUMENTATION.md")
m("INTEGRATION_DOCS_README.md", "docs/developer/api/INTEGRATION_DOCS_README.md")
# --- developer/reference ---
m("BROWSER_QUICK_REFERENCE.md", "docs/developer/reference/BROWSER_QUICK_REFERENCE.md")
m("CACHE_QUICK_REFERENCE.md", "docs/developer/reference/CACHE_QUICK_REFERENCE.md")
m("ERROR_HANDLING_QUICK_REFERENCE.md", "docs/developer/reference/ERROR_HANDLING_QUICK_REFERENCE.md")
m("FILESYSTEM_QUICK_REFERENCE.md", "docs/developer/reference/FILESYSTEM_QUICK_REFERENCE.md")
m("HYBRID_MEMORY_QUICK_REFERENCE.md", "docs/developer/reference/HYBRID_MEMORY_QUICK_REFERENCE.md")
m("QUICK_REFERENCE.md", "docs/developer/reference/QUICK_REFERENCE.md")
# --- developer/tutorials ---
m("CONCURRENCY_QUICKSTART.md", "docs/developer/tutorials/CONCURRENCY_QUICKSTART.md")
# --- developer/reports ---
for f in [
    "ARCHITECTURE_OPTIMIZATION_COMPLETION_REPORT.md", "CONCURRENCY_IMPLEMENTATION_REPORT.md",
    "CONTEXT_MANAGEMENT_IMPLEMENTATION_REPORT.md", "COVERAGE_ANALYSIS.md",
    "COVERAGE_IMPROVEMENT_REPORT.md", "DELIVERABLES.md", "ERROR_HANDLING_FILE_MANIFEST.md",
    "FEATURE_COMPLETION_REPORT.md", "FILESYSTEM_COMPLETION_REPORT.md", "FILE_MANIFEST.md",
    "IMPLEMENTATION_REPORT.md", "INTEGRATION_TEST_REPORT.md", "ISSUES_AND_IMPROVEMENTS.md",
    "MEMORY_DEDUPLICATION_FINAL_REPORT.md", "MEMORY_FUSION_DELIVERABLES.md",
    "MULTI_AGENT_COMPLETION_REPORT.md", "PHASE1_ALIGNMENT_REPORT.md", "PHASE2_ALIGNMENT_REPORT.md",
    "PHASE2_ARCHITECTURE_OPTIMIZATION_REPORT.md", "PHASE3_ALIGNMENT_COMPLETION_REPORT.md",
    "PHASE3_ALIGNMENT_REPORT.md", "PHASE3_COMPLETION_REPORT.md", "PHASE3_DELIVERABLES.md",
    "PHASE3_FEATURE_ENHANCEMENT_REPORT.md", "PLUGIN_SYSTEM_IMPLEMENTATION_REPORT.md",
    "PROMPT_PLATFORM_REPORT.md", "QUALITY_IMPROVEMENT_REPORT.md", "REFACTORING_DELIVERY_REPORT.md",
    "TEST_COVERAGE_IMPROVEMENT_REPORT.md", "TEST_COVERAGE_QUICK_REFERENCE.md",
    "VERIFICATION_REPORT.md", "test-coverage-report.md",
]:
    m(f, f"docs/developer/reports/{f}")
m("PROJECT_COMPLETION_REPORT.md", "docs/developer/reports/PROJECT_COMPLETION_REPORT_ROOT.md")

# ============ docs/ 根级文件 ============
D = "docs/"
# --- concepts/architecture ---
for f in ["ARCHITECTURE.md", "ARCHITECTURE_DESIGN.md", "ECOSYSTEM_ARCHITECTURE.md",
          "DATABASE.md", "DI_CONTAINER_IMPLEMENTATION_SUMMARY.md",
          "DI_CONTAINER_MIGRATION_GUIDE.md", "GATEWAY_MODE.md", "CAPABILITY_ROUTER_REFACTORING.md"]:
    m(D+f, f"docs/concepts/architecture/{f}")
# --- concepts/ root ---
m(D+"PROJECT_SUMMARY.md", "docs/concepts/PROJECT_SUMMARY.md")
# --- concepts/features ---
for f in ["ADVANCED_FEATURES.md", "advanced-features-guide.md", "AI_CAPABILITIES.md",
          "MULTIMODAL_CAPABILITIES.md", "BROWSER_AUTOMATION_GUIDE.md", "APPROVAL_GUIDE.md",
          "LLM_FRAMEWORK.md", "memory_v2_complete_guide.md", "FEEDBACK_SYSTEM_README.md",
          "FEEDBACK_COLLECTION_SYSTEM.md", "SANDBOX_POOLING_INTEGRATION.md",
          "STREAMING_INTEGRATION_GUIDE.md", "STREAMING_EXAMPLES.md", "UX_IMPROVEMENTS_USAGE_GUIDE.md"]:
    m(D+f, f"docs/concepts/features/{f}")
# --- concepts/planning ---
for f in ["IDE_EXTENSION_ROADMAP.md", "INTEGRATION_PLAN.md"]:
    m(D+f, f"docs/concepts/planning/{f}")
# --- operations/setup ---
for f in ["INSTALL_QUICKSTART.md", "QUICK_START_GUIDE.md", "ENVIRONMENT.md",
          "CONFIG_MANAGEMENT.md", "CONFIG_MIGRATION.md", "CONFIG_BEST_PRACTICES.md"]:
    m(D+f, f"docs/operations/setup/{f}")
m(D+"QUICKSTART.md", "docs/operations/setup/QUICKSTART_DOCS.md")
# --- operations/deployment ---
for f in ["DEPLOYMENT_GUIDE.md", "COMMERCIAL_DEPLOYMENT_RUNBOOK.md", "PHASE_55_DEPLOYMENT.md",
          "RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md", "RC_RELEASE_DIFF_REVIEW.md", "RC_STAGING_MANIFEST.md",
          "CAPACITY_PLANNING_AND_RELEASE.md", "CI_CD_MONITORING_SETUP.md", "CI_CD_MONITORING_COMPLETION.md",
          "GITHUB_SECRETS.md", "UPGRADE.md", "FEEDBACK_DEPLOYMENT.md", "SKILL_MARKET_DEPLOYMENT.md"]:
    m(D+f, f"docs/operations/deployment/{f}")
m(D+"DEPLOYMENT.md", "docs/operations/deployment/DEPLOYMENT_DETAILED.md")
# --- operations/monitoring ---
for f in ["MONITORING.md", "PERFORMANCE.md", "PERFORMANCE_OPTIMIZATION_GUIDE.md"]:
    m(D+f, f"docs/operations/monitoring/{f}")
m(D+"OPERATIONS.md", "docs/operations/OPERATIONS.md")
# --- operations/support ---
for f in ["FAQ.md", "FAQ_EN.md", "COMPREHENSIVE_FAQ.md", "TROUBLESHOOTING.md",
          "TROUBLESHOOTING_GUIDE.md", "COMPREHENSIVE_TROUBLESHOOTING.md",
          "CUSTOMER_SUPPORT_FAQ.md", "CUSTOMER_SUPPORT_PROCESS.md", "CUSTOMER_SUPPORT_SLA.md",
          "CUSTOMER_SUPPORT_SYSTEM_SUMMARY.md", "CUSTOMER_SUPPORT_TRAINING.md"]:
    m(D+f, f"docs/operations/support/{f}")
# --- admin ---
m(D+"SECURITY_GUIDE.md", "docs/admin/security/SECURITY_GUIDE.md")
m(D+"X-Agent-审计与整改报告.md", "docs/admin/audit/X-Agent-审计与整改报告.md")
for f in ["ENTERPRISE_ACCEPTANCE_CHECKLIST.md", "ENTERPRISE_DELIVERY_SUMMARY.md",
          "ENTERPRISE_FEATURES.md", "ENTERPRISE_IM_INTEGRATION.md", "ENTERPRISE_IM_QUICK_START.md",
          "ENTERPRISE_INTEGRATION_GUIDE.md", "ENTERPRISE_QUICKSTART.md",
          "企业功能交付物清单.md", "企业功能完整索引.md", "企业功能设计文档.md",
          "企业版定价策略.md", "企业版客户演示材料.md",
          "partner_portal_overview.md", "partner_support_system.md"]:
    m(D+f, f"docs/admin/enterprise/{f}")
# --- developer/api ---
for f in ["API.md", "API_CHANGELOG.md", "API_COMPLETE_REFERENCE.md", "API_DOCUMENTATION_INDEX.md",
          "API_DOCUMENTATION_INDEX_COMPLETE.md", "API_DOCUMENTATION_SUMMARY.md", "API_ERROR_CODES.md",
          "API_EXAMPLES.md", "API_FULL_REFERENCE.md", "API_GUIDE.md", "API_INTEGRATION_GUIDE.md",
          "API_INTEGRATION_GUIDE_NEW.md", "API_QUICKSTART.md", "API_REFERENCE.md",
          "FEEDBACK_API.md", "UX_IMPROVEMENTS_API.md", "WEB_SEARCH_ARTIFACTS_API.md",
          "partner_api_reference.md", "partner_integration_guide.md", "INTEGRATIONS.md",
          "INTEGRATION_GUIDE.md", "THIRD_PARTY_INTEGRATION.md", "LLM_INTEGRATION.md",
          "openapi.json", "X-Agent.postman_collection.json"]:
    m(D+f, f"docs/developer/api/{f}")
m(D+"API_QUICK_REFERENCE.md", "docs/developer/api/API_QUICK_REFERENCE_V2.md")
# --- developer/sdk ---
for f in ["SDK_GUIDE.md", "sdk_examples.md", "CLI_GUIDE.md", "EXAMPLES.md",
          "EXAMPLES_AND_TEMPLATES.md", "EXAMPLES_TEMPLATES.md"]:
    m(D+f, f"docs/developer/sdk/{f}")
# --- developer/plugins ---
for f in ["PLUGINS.md", "PLUGIN_DEVELOPMENT_GUIDE.md", "PLUGIN_MARKETPLACE_FRONTEND.md",
          "PLUGIN_MARKETPLACE_GUIDE.md", "PLUGIN_MARKETPLACE_OPERATIONS.md", "PLUGIN_REVIEW_CHECKLIST.md",
          "PLUGIN_SYSTEM_GUIDE.md", "plugin_api_reference.md", "plugin_testing_guide.md",
          "MCP_API_REFERENCE.md", "MCP_CONFIGURATION_GUIDE.md", "MCP_INTEGRATION_GUIDE.md",
          "MCP_PLUGIN_API_REFERENCE.md", "MCP_PLUGIN_DEVELOPER_GUIDE.md", "MCP_PLUGIN_EXAMPLES.md",
          "MCP_PLUGIN_MANIFEST_SPEC.md", "MCP_PLUGIN_REVIEW_STANDARDS.md", "MCP_PLUGIN_USER_GUIDE.md",
          "MCP_TROUBLESHOOTING.md", "SKILL_CURATOR_MVP.md", "SKILL_MARKET_ADVANCED_API.md",
          "SKILL_MARKET_ADVANCED_GUIDE.md", "SKILL_MARKET_GUIDE.md", "HOOKS_GUIDE.md"]:
    m(D+f, f"docs/developer/plugins/{f}")
m("PLUGIN_SYSTEM_QUICK_REFERENCE.md", "docs/developer/plugins/PLUGIN_SYSTEM_QUICK_REFERENCE.md")
# --- developer/contributing ---
for f in ["OPEN_SOURCE_CONTRIBUTION.md", "COMMUNITY_BUILDING_PLAN.md", "git-workflow.md",
          "i18n_guide.md", "TESTING_CASES_AND_SCENARIOS.md", "TESTING_ENVIRONMENT_SETUP.md",
          "EXAMPLE_CODE_MAINTENANCE.md", "ISSUE_TRACKING_SYSTEM_CONFIG.md"]:
    m(D+f, f"docs/developer/contributing/{f}")
m(D+"CONTRIBUTING.md", "docs/developer/contributing/CONTRIBUTING_DOCS.md")
# --- developer/tutorials ---
for f in ["USER_GUIDE_AND_TUTORIALS.md", "USER_GUIDE_EN.md", "USER_MANUAL.md",
          "USER_TRAINING_PLAN.md", "TEACHING_RESOURCES_INDEX.md", "RECIPES.md",
          "SANDBOX_POOLING_QUICK_START.md", "CODE_CAPABILITIES_COMPARISON.md",
          "CODE_CAPABILITIES_EXAMPLES.md", "CODE_CAPABILITIES_GUIDE.md", "CODE_GENERATION_QUALITY.md"]:
    m(D+f, f"docs/developer/tutorials/{f}")
# --- developer/best-practices ---
m(D+"BEST_PRACTICES_GUIDE.md", "docs/developer/best-practices/BEST_PRACTICES_GUIDE.md")
# --- developer/ 根 ---
m(D+"DEVELOPER_GUIDE.md", "docs/developer/DEVELOPER_GUIDE.md")
# --- developer/reports ---
for f in ["AGENT_11_COMPLETION_SUMMARY.md", "AGENT_12_COMPLETION_REPORT.md", "AGENT_12_FINAL_SUMMARY.md",
          "AGENT_17_COMPLETION_REPORT.md", "AGENT_22_DELIVERY_SUMMARY.md", "AGENT_23_COMPLETION_SUMMARY.md",
          "AGENT_27_COMPLETION.md", "agent16_completion_report.md", "BETA_TESTING_COMPLETION_REPORT.md",
          "BETA_TESTING_PLAN.md", "BETA_TESTING_SCHEDULE.md", "DOCUMENTATION_COMPLETION_FINAL_REPORT.md",
          "DOCUMENTATION_COMPLETION_REPORT.md", "DOCUMENTATION_COMPLETION_REPORT_FINAL.md",
          "DOCUMENTATION_INDEX.md", "DOCUMENTATION_INDEX_COMPLETE.md", "DOCUMENTATION_NAVIGATION_INDEX.md",
          "DOCUMENTATION_SUMMARY.md", "DOCUMENTATION_SYSTEM_COMPLETE.md", "INDEX.md",
          "KNOWLEDGE_BASE_INDEX.md", "ECOSYSTEM_DOCUMENTATION_INDEX.md", "ECOSYSTEM_BUILDING_SUMMARY.md",
          "IMPLEMENTATION_CHECKLIST.md", "CODEX_HERMES_GAP_CLOSURE_REPORT.md", "API_GENERATION_REPORT.md",
          "CONFIG_IMPLEMENTATION_SUMMARY.md", "FEEDBACK_ACCEPTANCE_REPORT.md", "FEEDBACK_COMPLETION_SUMMARY.md",
          "MCP_IMPLEMENTATION_STATUS.md", "MULTIMODAL_ACCURACY_REPORT.md", "MULTIMODAL_PERFORMANCE_REPORT.md",
          "SANDBOX_POOLING_DELIVERY_SUMMARY.md", "SANDBOX_POOLING_PERFORMANCE_REPORT.md",
          "SKILL_MARKET_COMPLETION_REPORT.md", "STREAMING_TECHNICAL_REPORT.md", "TRAINING_DELIVERY_REPORT.md",
          "UX_IMPROVEMENTS_SUMMARY.md", "文档改进工作总结报告.md", "企业功能开发完成报告.md",
          "PROJECT_COMPLETION_REPORT.md", "QUICK_REFERENCE.md"]:
    m(D+f, f"docs/developer/reports/{f}")
# docs/QUICK_REFERENCE.md -> reports? 不, 去 reference 卷, 与根 QUICK_REFERENCE 重名故改名
MAP["docs/QUICK_REFERENCE.md"] = "docs/developer/reference/QUICK_REFERENCE_FULL.md"

# ============ docs/ 子目录(整目录移动, 展开为文件级映射在 execute 时处理) ============
DIR_MAP = {
    "docs/01-项目规划": "docs/concepts/planning/01-项目规划",
    "docs/02-技术设计": "docs/concepts/design/02-技术设计",
    "docs/best-practices": "docs/developer/best-practices/best-practices",
    "docs/case-studies": "docs/concepts/case-studies",
    "docs/diagrams": "docs/concepts/diagrams",
    "docs/enterprise": "docs/admin/enterprise/enterprise",
    "docs/faq": "docs/operations/support/faq",
    "docs/specs": "docs/developer/specs",
    "docs/superpowers": "docs/concepts/planning/superpowers",
    "docs/training-materials": "docs/developer/tutorials/training-materials",
    "docs/troubleshooting": "docs/operations/support/troubleshooting",
    "docs/tutorials": "docs/developer/tutorials/tutorials",
    "docs/user-guide": "docs/developer/tutorials/user-guide",
    "docs/video-scripts": "docs/developer/tutorials/video-scripts",
    "docs/video-tutorials": "docs/developer/tutorials/video-tutorials",
}

# ============ backend/docs/ ============
BD = "backend/docs/"
for f in ["SSO_COMPLETION_SUMMARY.md", "SSO_CONFIGURATION.md", "SSO_DEPLOYMENT_OPERATIONS.md",
          "SSO_INTEGRATION_GUIDE.md", "SSO_README.md", "SSO_SECURITY_TEST_REPORT.md"]:
    m(BD+f, f"docs/admin/sso/{f}")
for f in ["SUBSCRIPTION_API.md", "SUBSCRIPTION_INTEGRATION.md", "SUBSCRIPTION_OPERATIONS.md",
          "SUBSCRIPTION_README.md", "SUBSCRIPTION_TEST_REPORT.md"]:
    m(BD+f, f"docs/admin/subscription/{f}")
for f in ["CONTEXT_COMPACTOR_OPTIMIZATION.md", "OPTIMIZATION_SUMMARY.md", "PERFORMANCE_REPORT.md"]:
    m(BD+f, f"docs/developer/reports/backend/{f}")

# ============ 执行 ============
def expand_dir_map():
    """展开目录映射为文件级映射"""
    out = {}
    for sd, dd in DIR_MAP.items():
        ap = os.path.join(ROOT, sd)
        for dp, _, fns in os.walk(ap):
            for fn in fns:
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, ROOT).replace("\\", "/")
                sub = os.path.relpath(full, ap).replace("\\", "/")
                out[rel] = f"{dd}/{sub}"
    return out

def main():
    execute = len(sys.argv) > 1 and sys.argv[1] == "execute"
    fmap = dict(MAP)
    fmap.update(expand_dir_map())

    # 1) 源存在性 & 目标冲突检查
    missing, collide = [], []
    for s, d in sorted(fmap.items()):
        if not os.path.exists(os.path.join(ROOT, s)):
            missing.append(s)
        if os.path.exists(os.path.join(ROOT, d)):
            collide.append(d)
    # 2) 未映射检查: 根 *.md 与 docs/ 下所有文件、backend/docs 下所有文件
    mapped_src = set(fmap)
    unmapped = []
    for fn in os.listdir(ROOT):
        if fn.endswith(".md") and fn not in KEEP_ROOT and fn not in mapped_src:
            unmapped.append(fn)
    for dp, _, fns in os.walk(os.path.join(ROOT, "docs")):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), ROOT).replace("\\", "/")
            if rel in ("docs/README.md", "docs/README_EN.md"):
                continue
            if rel not in mapped_src:
                unmapped.append(rel)
    for dp, _, fns in os.walk(os.path.join(ROOT, "backend", "docs")):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), ROOT).replace("\\", "/")
            if rel not in mapped_src:
                unmapped.append(rel)

    print(f"映射总数: {len(fmap)}")
    print(f"源缺失: {missing}")
    print(f"目标冲突: {collide}")
    print(f"未映射: {unmapped}")
    if missing or collide or unmapped:
        print("!! 存在问题, 不执行")
        return

    if execute:
        # 保存映射供链接修复使用
        import json
        with open(os.path.join(ROOT, "_doc_move_map.json"), "w", encoding="utf-8") as fh:
            json.dump(fmap, fh, ensure_ascii=False, indent=1)
        for s, d in sorted(fmap.items()):
            os.makedirs(os.path.dirname(os.path.join(ROOT, d)), exist_ok=True)
            shutil.move(os.path.join(ROOT, s), os.path.join(ROOT, d))
        # 清理空目录
        for sd in list(DIR_MAP) + ["backend/docs", "docs/01-项目规划", "docs/02-技术设计"]:
            ap = os.path.join(ROOT, sd)
            if os.path.isdir(ap):
                try:
                    os.removedirs(ap)
                except OSError:
                    pass
        print(f"已移动 {len(fmap)} 个文件")
    else:
        print("DRY-RUN 通过, 可加 execute 执行")

if __name__ == "__main__":
    main()
