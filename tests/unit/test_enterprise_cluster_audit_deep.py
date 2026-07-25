"""Deep coverage tests for enterprise_cluster.py and enterprise_audit.py — all branches."""
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from backend.app.core.enterprise_cluster import (
    ClusterType, NodeRole, ClusterConfig, ClusterNode, ServiceDeployment,
    ServiceInstance, LoadBalancerConfig, ServiceRegistry, ConfigEntry,
    ConfigCenter, ClusterManager, TraceSpan, DistributedTracer,
)
from backend.app.core.enterprise_audit import (
    AuditEventType, AuditSeverity, AuditLogEntry, AuditLogFilter,
    AuditLogStore, AuditAnalyzer, DashboardMetrics, DashboardDataProvider,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ConfigCenter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfigCenter:
    def test_set_and_get_config(self):
        cc = ConfigCenter()
        entry = cc.set_config("db_host", "localhost")
        assert entry.key == "db_host"
        assert entry.value == "localhost"
        got = cc.get_config("db_host")
        assert got is not None
        assert got.value == "localhost"

    def test_get_config_missing(self):
        cc = ConfigCenter()
        assert cc.get_config("nonexistent") is None

    def test_set_config_with_cluster_and_namespace(self):
        cc = ConfigCenter()
        cc.set_config("key1", "val1", cluster_id="c1", namespace="ns1")
        assert cc.get_config("key1", cluster_id="c1", namespace="ns1") is not None
        assert cc.get_config("key1") is None  # different scope

    def test_delete_config_exists(self):
        cc = ConfigCenter()
        cc.set_config("k", "v")
        assert cc.delete_config("k") is True
        assert cc.get_config("k") is None

    def test_delete_config_not_exists(self):
        cc = ConfigCenter()
        assert cc.delete_config("nope") is False

    def test_get_config_history(self):
        cc = ConfigCenter()
        cc.set_config("k", "v1")
        cc.set_config("k", "v2")
        history = cc.get_config_history("k")
        assert len(history) == 2
        assert history[0].value == "v1"
        assert history[1].value == "v2"

    def test_get_config_history_empty(self):
        cc = ConfigCenter()
        assert cc.get_config_history("nope") == []

    def test_list_configs(self):
        cc = ConfigCenter()
        cc.set_config("a", "1")
        cc.set_config("b", "2")
        cc.set_config("c", "3", cluster_id="other")
        configs = cc.list_configs()
        assert len(configs) == 2  # only global:default scope

    def test_list_configs_with_cluster(self):
        cc = ConfigCenter()
        cc.set_config("x", "1", cluster_id="c1", namespace="ns")
        cc.set_config("y", "2", cluster_id="c1", namespace="ns")
        assert len(cc.list_configs(cluster_id="c1", namespace="ns")) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# ClusterManager TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestClusterManager:
    def _make_cluster(self, **kw):
        defaults = dict(cluster_name="test", cluster_type=ClusterType.KUBERNETES,
                        region="us-east-1", api_endpoint="https://k8s.local")
        defaults.update(kw)
        return ClusterConfig(**defaults)

    def test_register_and_get_cluster(self):
        mgr = ClusterManager()
        cfg = self._make_cluster()
        mgr.register_cluster(cfg)
        assert mgr.get_cluster(cfg.cluster_id) is cfg
        assert mgr.get_cluster("nope") is None

    def test_list_clusters(self):
        mgr = ClusterManager()
        mgr.register_cluster(self._make_cluster(cluster_name="A"))
        mgr.register_cluster(self._make_cluster(cluster_name="B"))
        assert len(mgr.list_clusters()) == 2

    def test_register_node_and_get_cluster_nodes(self):
        mgr = ClusterManager()
        cfg = self._make_cluster()
        mgr.register_cluster(cfg)
        node = ClusterNode(cluster_id=cfg.cluster_id, node_name="n1",
                           node_role=NodeRole.WORKER, ip_address="10.0.0.1")
        mgr.register_node(node)
        nodes = mgr.get_cluster_nodes(cfg.cluster_id)
        assert len(nodes) == 1
        assert mgr.get_cluster_nodes("other") == []

    def test_update_node_status(self):
        mgr = ClusterManager()
        node = ClusterNode(cluster_id="c1", node_name="n1",
                           node_role=NodeRole.MASTER, ip_address="10.0.0.2")
        mgr.register_node(node)
        updated = mgr.update_node_status(node.node_id, "not_ready")
        assert updated.status == "not_ready"
        assert mgr.update_node_status("nope", "ready") is None

    def test_deploy_service_and_get(self):
        mgr = ClusterManager()
        dep = ServiceDeployment(service_name="api", cluster_id="c1",
                                image="api:latest", port=8080, target_port=8080)
        mgr.deploy_service(dep)
        assert mgr.get_deployment(dep.deployment_id) is dep
        assert mgr.get_deployment("nope") is None

    def test_list_deployments(self):
        mgr = ClusterManager()
        mgr.deploy_service(ServiceDeployment(service_name="a", cluster_id="c1",
                                             image="a:1", port=80, target_port=80))
        mgr.deploy_service(ServiceDeployment(service_name="b", cluster_id="c2",
                                             image="b:1", port=80, target_port=80))
        assert len(mgr.list_deployments("c1")) == 1
        assert len(mgr.list_deployments("c2")) == 1

    def test_register_instance_and_get_deployment_instances(self):
        mgr = ClusterManager()
        inst = ServiceInstance(deployment_id="d1", pod_name="pod-0",
                               node_id="n1", ip_address="10.0.0.5", port=8080)
        mgr.register_instance(inst)
        assert len(mgr.get_deployment_instances("d1")) == 1
        assert len(mgr.get_deployment_instances("d2")) == 0

    def test_update_instance_status_running_sets_started_at(self):
        mgr = ClusterManager()
        inst = ServiceInstance(deployment_id="d1", pod_name="pod-0",
                               node_id="n1", ip_address="10.0.0.5", port=8080)
        mgr.register_instance(inst)
        assert inst.started_at is None
        updated = mgr.update_instance_status(inst.instance_id, "running", ready=True)
        assert updated.status == "running"
        assert updated.ready is True
        assert updated.started_at is not None

    def test_update_instance_status_running_already_started(self):
        mgr = ClusterManager()
        now = datetime.now(UTC)
        inst = ServiceInstance(deployment_id="d1", pod_name="pod-0",
                               node_id="n1", ip_address="10.0.0.5", port=8080,
                               started_at=now)
        mgr.register_instance(inst)
        updated = mgr.update_instance_status(inst.instance_id, "running", ready=True)
        assert updated.started_at == now  # not overwritten

    def test_update_instance_status_not_found(self):
        mgr = ClusterManager()
        assert mgr.update_instance_status("nope", "running") is None

    def test_register_and_discover_service(self):
        mgr = ClusterManager()
        reg = ServiceRegistry(service_name="svc", cluster_id="c1")
        mgr.register_service(reg)
        assert mgr.discover_service("svc", "c1") is reg
        assert mgr.discover_service("svc", "c2") is None
        assert mgr.discover_service("other", "c1") is None

    def test_get_healthy_instances_no_registry(self):
        mgr = ClusterManager()
        assert mgr.get_healthy_instances("nope", "c1") == []

    def test_get_healthy_instances_filters(self):
        mgr = ClusterManager()
        healthy = ServiceInstance(deployment_id="d1", pod_name="p1", node_id="n1",
                                  ip_address="10.0.0.1", port=80, status="running", ready=True)
        not_ready = ServiceInstance(deployment_id="d1", pod_name="p2", node_id="n1",
                                    ip_address="10.0.0.2", port=80, status="running", ready=False)
        failed = ServiceInstance(deployment_id="d1", pod_name="p3", node_id="n1",
                                 ip_address="10.0.0.3", port=80, status="failed", ready=True)
        reg = ServiceRegistry(service_name="svc", cluster_id="c1",
                              instances=[healthy, not_ready, failed])
        mgr.register_service(reg)
        result = mgr.get_healthy_instances("svc", "c1")
        assert len(result) == 1
        assert result[0].pod_name == "p1"

    def test_setup_and_get_load_balancer(self):
        mgr = ClusterManager()
        lb = LoadBalancerConfig(service_name="svc", cluster_id="c1")
        mgr.setup_load_balancer(lb)
        assert mgr.get_load_balancer(lb.lb_id) is lb
        assert mgr.get_load_balancer("nope") is None

    def test_select_instance_no_lb(self):
        mgr = ClusterManager()
        assert mgr.select_instance("nope", "svc", "c1") is None

    def test_select_instance_no_healthy(self):
        mgr = ClusterManager()
        lb = LoadBalancerConfig(service_name="svc", cluster_id="c1")
        mgr.setup_load_balancer(lb)
        assert mgr.select_instance(lb.lb_id, "svc", "c1") is None

    def test_select_instance_round_robin(self):
        mgr = ClusterManager()
        inst = ServiceInstance(deployment_id="d1", pod_name="p1", node_id="n1",
                               ip_address="10.0.0.1", port=80, status="running", ready=True)
        reg = ServiceRegistry(service_name="svc", cluster_id="c1", instances=[inst])
        mgr.register_service(reg)
        lb = LoadBalancerConfig(service_name="svc", cluster_id="c1", lb_type="round_robin")
        mgr.setup_load_balancer(lb)
        result = mgr.select_instance(lb.lb_id, "svc", "c1")
        assert result is inst

    def test_select_instance_least_connections(self):
        mgr = ClusterManager()
        inst = ServiceInstance(deployment_id="d1", pod_name="p1", node_id="n1",
                               ip_address="10.0.0.1", port=80, status="running", ready=True)
        reg = ServiceRegistry(service_name="svc", cluster_id="c1", instances=[inst])
        mgr.register_service(reg)
        lb = LoadBalancerConfig(service_name="svc", cluster_id="c1", lb_type="least_connections")
        mgr.setup_load_balancer(lb)
        result = mgr.select_instance(lb.lb_id, "svc", "c1")
        assert result is inst

    def test_select_instance_other_type(self):
        mgr = ClusterManager()
        inst = ServiceInstance(deployment_id="d1", pod_name="p1", node_id="n1",
                               ip_address="10.0.0.1", port=80, status="running", ready=True)
        reg = ServiceRegistry(service_name="svc", cluster_id="c1", instances=[inst])
        mgr.register_service(reg)
        lb = LoadBalancerConfig(service_name="svc", cluster_id="c1", lb_type="ip_hash")
        mgr.setup_load_balancer(lb)
        result = mgr.select_instance(lb.lb_id, "svc", "c1")
        assert result is inst

    def test_get_config_center(self):
        mgr = ClusterManager()
        cc = mgr.get_config_center()
        assert isinstance(cc, ConfigCenter)

    def test_get_cluster_health_empty(self):
        mgr = ClusterManager()
        health = mgr.get_cluster_health("c1")
        assert health["nodes"]["total"] == 0
        assert health["nodes"]["health_percentage"] == 0
        assert health["services"]["total_deployments"] == 0
        assert health["services"]["health_percentage"] == 0

    def test_get_cluster_health_with_data(self):
        mgr = ClusterManager()
        cfg = self._make_cluster()
        mgr.register_cluster(cfg)
        # Add nodes
        mgr.register_node(ClusterNode(cluster_id=cfg.cluster_id, node_name="n1",
                                      node_role=NodeRole.MASTER, ip_address="10.0.0.1", status="ready"))
        mgr.register_node(ClusterNode(cluster_id=cfg.cluster_id, node_name="n2",
                                      node_role=NodeRole.WORKER, ip_address="10.0.0.2", status="not_ready"))
        # Add deployment with healthy instance
        dep = ServiceDeployment(service_name="api", cluster_id=cfg.cluster_id,
                                image="api:1", port=80, target_port=80, replicas=2)
        mgr.deploy_service(dep)
        inst = ServiceInstance(deployment_id=dep.deployment_id, pod_name="p1",
                               node_id="n1", ip_address="10.0.1.1", port=80,
                               status="running", ready=True)
        reg = ServiceRegistry(service_name="api", cluster_id=cfg.cluster_id, instances=[inst])
        mgr.register_service(reg)

        health = mgr.get_cluster_health(cfg.cluster_id)
        assert health["nodes"]["total"] == 2
        assert health["nodes"]["ready"] == 1
        assert health["nodes"]["health_percentage"] == 50.0
        assert health["services"]["total_deployments"] == 1
        assert health["services"]["total_replicas"] == 2
        assert health["services"]["ready_replicas"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# DistributedTracer TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDistributedTracer:
    def test_start_trace(self):
        tracer = DistributedTracer()
        span = tracer.start_trace("t1", "op1", "svc1", "c1")
        assert span.trace_id == "t1"
        assert span.operation_name == "op1"
        assert len(tracer.get_trace("t1")) == 1

    def test_start_trace_multiple_spans(self):
        tracer = DistributedTracer()
        tracer.start_trace("t1", "op1", "svc1", "c1")
        tracer.start_trace("t1", "op2", "svc1", "c1")
        assert len(tracer.get_trace("t1")) == 2

    def test_end_span(self):
        tracer = DistributedTracer()
        span = tracer.start_trace("t1", "op1", "svc1", "c1")
        ended = tracer.end_span(span.span_id)
        assert ended is not None
        assert ended.end_time is not None
        assert ended.duration_ms >= 0
        assert ended.status == "ok"

    def test_end_span_with_error_status(self):
        tracer = DistributedTracer()
        span = tracer.start_trace("t1", "op1", "svc1", "c1")
        ended = tracer.end_span(span.span_id, status="error")
        assert ended.status == "error"

    def test_end_span_not_found(self):
        tracer = DistributedTracer()
        assert tracer.end_span("nope") is None

    def test_add_tag(self):
        tracer = DistributedTracer()
        span = tracer.start_trace("t1", "op1", "svc1", "c1")
        tracer.add_tag(span.span_id, "http.method", "GET")
        assert span.tags["http.method"] == "GET"

    def test_add_tag_not_found(self):
        tracer = DistributedTracer()
        tracer.add_tag("nope", "k", "v")  # no error

    def test_add_log(self):
        tracer = DistributedTracer()
        span = tracer.start_trace("t1", "op1", "svc1", "c1")
        tracer.add_log(span.span_id, "something happened", level="info")
        assert len(span.logs) == 1
        assert span.logs[0]["message"] == "something happened"
        assert span.logs[0]["level"] == "info"

    def test_add_log_not_found(self):
        tracer = DistributedTracer()
        tracer.add_log("nope", "msg")  # no error

    def test_get_trace_empty(self):
        tracer = DistributedTracer()
        assert tracer.get_trace("nope") == []


# ═══════════════════════════════════════════════════════════════════════════════
# AuditLogEntry TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogEntry:
    def test_compute_hash_no_previous(self):
        entry = AuditLogEntry(event_type=AuditEventType.LOGIN, tenant_id="t1", action="login")
        h = entry.compute_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # sha256 hex

    def test_compute_hash_with_previous(self):
        entry = AuditLogEntry(event_type=AuditEventType.LOGIN, tenant_id="t1", action="login")
        h1 = entry.compute_hash(None)
        h2 = entry.compute_hash("prev_hash")
        assert h1 != h2

    def test_compute_hash_deterministic(self):
        entry = AuditLogEntry(event_type=AuditEventType.LOGIN, tenant_id="t1", action="login")
        assert entry.compute_hash("x") == entry.compute_hash("x")


# ═══════════════════════════════════════════════════════════════════════════════
# AuditLogStore (enterprise_audit) TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogStoreDeep:
    def _make_entry(self, **kw):
        defaults = dict(event_type=AuditEventType.LOGIN, tenant_id="t1",
                        action="login", user_id="u1")
        defaults.update(kw)
        return AuditLogEntry(**defaults)

    def test_append_log_sets_hash(self):
        store = AuditLogStore()
        entry = self._make_entry()
        result = store.append_log(entry)
        assert result.hash is not None

    def test_append_log_chain_hash(self):
        store = AuditLogStore()
        e1 = store.append_log(self._make_entry())
        e2 = store.append_log(self._make_entry(action="logout"))
        # e2's hash should depend on e1's hash
        assert e2.hash != e1.hash

    def test_append_log_indexes_user(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(user_id="u1"))
        store.append_log(self._make_entry(user_id="u2"))
        summary = store.get_user_activity_summary("u1")
        assert summary["total_events"] == 1

    def test_append_log_no_user_id(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(user_id=None))
        # should not crash, no user index

    def test_append_log_indexes_resource(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(resource_id="r1"))
        trail = store.get_resource_audit_trail("r1")
        assert len(trail) == 1

    def test_append_log_no_resource_id(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(resource_id=None))
        # no crash

    def test_query_logs_basic(self):
        store = AuditLogStore()
        store.append_log(self._make_entry())
        f = AuditLogFilter(tenant_id="t1")
        logs, total = store.query_logs(f)
        assert total == 1
        assert len(logs) == 1

    def test_query_logs_empty_tenant(self):
        store = AuditLogStore()
        store.append_log(self._make_entry())
        f = AuditLogFilter(tenant_id="other")
        logs, total = store.query_logs(f)
        assert total == 0

    def test_query_logs_filter_user_id(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(user_id="u1"))
        store.append_log(self._make_entry(user_id="u2"))
        f = AuditLogFilter(tenant_id="t1", user_id="u1")
        logs, total = store.query_logs(f)
        assert total == 1

    def test_query_logs_filter_event_type(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(event_type=AuditEventType.LOGIN))
        store.append_log(self._make_entry(event_type=AuditEventType.LOGOUT))
        f = AuditLogFilter(tenant_id="t1", event_type=AuditEventType.LOGOUT)
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_filter_severity(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(severity=AuditSeverity.INFO))
        store.append_log(self._make_entry(severity=AuditSeverity.CRITICAL))
        f = AuditLogFilter(tenant_id="t1", severity=AuditSeverity.CRITICAL)
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_filter_resource_type(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(resource_type="user"))
        store.append_log(self._make_entry(resource_type="agent"))
        f = AuditLogFilter(tenant_id="t1", resource_type="agent")
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_filter_resource_id(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(resource_id="r1"))
        store.append_log(self._make_entry(resource_id="r2"))
        f = AuditLogFilter(tenant_id="t1", resource_id="r2")
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_filter_status(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(status="success"))
        store.append_log(self._make_entry(status="failure"))
        f = AuditLogFilter(tenant_id="t1", status="failure")
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_filter_time_range(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        old = now - timedelta(days=10)
        store.append_log(self._make_entry(timestamp=old))
        store.append_log(self._make_entry(timestamp=now))
        f = AuditLogFilter(tenant_id="t1", start_time=now - timedelta(hours=1))
        logs, _ = store.query_logs(f)
        assert len(logs) == 1
        f2 = AuditLogFilter(tenant_id="t1", end_time=now - timedelta(days=5))
        logs2, _ = store.query_logs(f2)
        assert len(logs2) == 1

    def test_query_logs_filter_tags(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(tags=["important"]))
        store.append_log(self._make_entry(tags=["trivial"]))
        f = AuditLogFilter(tenant_id="t1", tags=["important"])
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_filter_search_text(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(action="User Login"))
        store.append_log(self._make_entry(action="Data Export"))
        f = AuditLogFilter(tenant_id="t1", search_text="login")
        logs, _ = store.query_logs(f)
        assert len(logs) == 1

    def test_query_logs_pagination(self):
        store = AuditLogStore()
        for i in range(10):
            store.append_log(self._make_entry(action=f"action_{i}"))
        f = AuditLogFilter(tenant_id="t1", limit=3, offset=2)
        logs, total = store.query_logs(f)
        assert total == 10
        assert len(logs) == 3

    def test_get_log(self):
        store = AuditLogStore()
        entry = store.append_log(self._make_entry())
        assert store.get_log(entry.log_id) is entry
        assert store.get_log("nope") is None

    def test_verify_log_chain_valid(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(action="a1"))
        store.append_log(self._make_entry(action="a2"))
        assert store.verify_log_chain() is True

    def test_verify_log_chain_tampered(self):
        store = AuditLogStore()
        e1 = store.append_log(self._make_entry(action="a1"))
        store.append_log(self._make_entry(action="a2"))
        # Tamper with e1
        e1.action = "tampered"
        assert store.verify_log_chain() is False

    def test_verify_log_chain_with_start_id(self):
        store = AuditLogStore()
        e1 = store.append_log(self._make_entry(action="a1"))
        e2 = store.append_log(self._make_entry(action="a2"))
        # Starting from e2 - only verifies e2 with previous_hash=None
        # But e2 was computed with e1.hash as previous, so it will fail
        # unless we start from e1
        assert store.verify_log_chain(start_log_id=e1.log_id) is True

    def test_verify_log_chain_start_id_not_found(self):
        store = AuditLogStore()
        store.append_log(self._make_entry())
        assert store.verify_log_chain(start_log_id="nope") is False

    def test_get_user_activity_summary_no_logs(self):
        store = AuditLogStore()
        summary = store.get_user_activity_summary("nobody")
        assert summary["total_events"] == 0
        assert summary["first_event"] is None
        assert summary["last_event"] is None

    def test_get_user_activity_summary_with_logs(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(user_id="u1", event_type=AuditEventType.LOGIN))
        store.append_log(self._make_entry(user_id="u1", event_type=AuditEventType.LOGOUT))
        summary = store.get_user_activity_summary("u1")
        assert summary["total_events"] == 2
        assert summary["event_counts"]["login"] == 1
        assert summary["event_counts"]["logout"] == 1
        assert summary["first_event"] is not None

    def test_get_user_activity_summary_old_logs_excluded(self):
        store = AuditLogStore()
        old_time = datetime.now(UTC) - timedelta(days=30)
        store.append_log(self._make_entry(user_id="u1", timestamp=old_time))
        summary = store.get_user_activity_summary("u1", days=7)
        assert summary["total_events"] == 0

    def test_get_resource_audit_trail(self):
        store = AuditLogStore()
        store.append_log(self._make_entry(resource_id="r1", action="create"))
        store.append_log(self._make_entry(resource_id="r1", action="update"))
        store.append_log(self._make_entry(resource_id="r2", action="delete"))
        trail = store.get_resource_audit_trail("r1")
        assert len(trail) == 2

    def test_get_resource_audit_trail_empty(self):
        store = AuditLogStore()
        assert store.get_resource_audit_trail("nope") == []


# ═══════════════════════════════════════════════════════════════════════════════
# AuditAnalyzer TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditAnalyzer:
    def test_detect_suspicious_no_activity(self):
        store = AuditLogStore()
        analyzer = AuditAnalyzer(store)
        result = analyzer.detect_suspicious_activity("t1")
        assert result == []

    def test_detect_brute_force_warning(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        for _ in range(5):
            store.append_log(AuditLogEntry(
                event_type=AuditEventType.LOGIN_FAILED, tenant_id="t1",
                user_id="victim", action="login_failed", timestamp=now,
            ))
        analyzer = AuditAnalyzer(store)
        result = analyzer.detect_suspicious_activity("t1", threshold=5)
        assert len(result) == 1
        assert result[0]["type"] == "brute_force_attempt"
        assert result[0]["severity"] == "warning"

    def test_detect_brute_force_critical(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        for _ in range(10):
            store.append_log(AuditLogEntry(
                event_type=AuditEventType.LOGIN_FAILED, tenant_id="t1",
                user_id="victim", action="login_failed", timestamp=now,
            ))
        analyzer = AuditAnalyzer(store)
        result = analyzer.detect_suspicious_activity("t1", threshold=5)
        assert result[0]["severity"] == "critical"

    def test_detect_brute_force_no_user_id(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        for _ in range(6):
            store.append_log(AuditLogEntry(
                event_type=AuditEventType.LOGIN_FAILED, tenant_id="t1",
                user_id=None, action="login_failed", timestamp=now,
            ))
        analyzer = AuditAnalyzer(store)
        result = analyzer.detect_suspicious_activity("t1", threshold=5)
        # No user_id -> not grouped -> no brute force detected
        assert len(result) == 0

    def test_detect_unusual_access_pattern(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        # Add 101 entries for same user+resource_type
        entries = []
        for _ in range(101):
            e = AuditLogEntry(
                event_type=AuditEventType.RESOURCE_ACCESSED, tenant_id="t1",
                user_id="u1", action="access", resource_type="secret",
                timestamp=now,
            )
            store.append_log(e)
            entries.append(e)
        analyzer = AuditAnalyzer(store)
        # Patch query_logs to bypass the default limit=100 for RESOURCE_ACCESSED filter
        original_query = store.query_logs
        def unlimited_query(f):
            f.limit = 10000
            return original_query(f)
        with patch.object(store, "query_logs", side_effect=unlimited_query):
            result = analyzer.detect_suspicious_activity("t1")
        assert any(a["type"] == "unusual_access_pattern" for a in result)

    def test_generate_compliance_report(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.LOGIN, tenant_id="t1",
            action="login", severity=AuditSeverity.INFO, status="success",
            timestamp=now,
        ))
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.SECURITY_ALERT, tenant_id="t1",
            action="alert", severity=AuditSeverity.CRITICAL, status="failure",
            timestamp=now,
        ))
        analyzer = AuditAnalyzer(store)
        report = analyzer.generate_compliance_report(
            "t1", now - timedelta(hours=1), now + timedelta(hours=1))
        assert report["tenant_id"] == "t1"
        assert report["summary"]["total_events"] == 2
        assert report["security"]["critical_events"] == 1
        assert report["security"]["security_events"] == 1

    def test_generate_compliance_report_empty(self):
        store = AuditLogStore()
        analyzer = AuditAnalyzer(store)
        now = datetime.now(UTC)
        report = analyzer.generate_compliance_report(
            "t1", now - timedelta(hours=1), now)
        assert report["summary"]["total_events"] == 0

    def test_get_user_access_report(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.RESOURCE_ACCESSED, tenant_id="t1",
            user_id="u1", action="read", resource_type="doc", resource_id="d1",
            timestamp=now,
        ))
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.RESOURCE_UPDATED, tenant_id="t1",
            user_id="u1", action="write", resource_type="doc", resource_id="d1",
            timestamp=now,
        ))
        analyzer = AuditAnalyzer(store)
        report = analyzer.get_user_access_report("t1", "u1")
        assert report["total_events"] == 2
        assert report["resources_accessed"]["doc:d1"] == 2
        assert report["operations"]["read"] == 1
        assert report["operations"]["write"] == 1
        assert report["first_activity"] is not None

    def test_get_user_access_report_no_resources(self):
        store = AuditLogStore()
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.LOGIN, tenant_id="t1",
            user_id="u1", action="login",
            resource_type=None, resource_id=None,
        ))
        analyzer = AuditAnalyzer(store)
        report = analyzer.get_user_access_report("t1", "u1")
        assert report["resources_accessed"] == {}

    def test_get_user_access_report_empty(self):
        store = AuditLogStore()
        analyzer = AuditAnalyzer(store)
        report = analyzer.get_user_access_report("t1", "nobody")
        assert report["total_events"] == 0
        assert report["first_activity"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# DashboardDataProvider TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboardDataProvider:
    def test_get_dashboard_metrics_empty(self):
        store = AuditLogStore()
        analyzer = AuditAnalyzer(store)
        provider = DashboardDataProvider(store, analyzer)
        metrics = provider.get_dashboard_metrics("t1")
        assert metrics.total_events == 0
        assert metrics.success_rate == 0
        assert metrics.suspicious_activities == []

    def test_get_dashboard_metrics_with_data(self):
        store = AuditLogStore()
        now = datetime.now(UTC)
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.LOGIN, tenant_id="t1",
            user_id="u1", action="login", resource_id="r1",
            severity=AuditSeverity.INFO, status="success", timestamp=now,
        ))
        store.append_log(AuditLogEntry(
            event_type=AuditEventType.SECURITY_ALERT, tenant_id="t1",
            user_id="u2", action="alert", resource_id="r2",
            severity=AuditSeverity.CRITICAL, status="failure", timestamp=now,
        ))
        analyzer = AuditAnalyzer(store)
        provider = DashboardDataProvider(store, analyzer)
        metrics = provider.get_dashboard_metrics("t1")
        assert metrics.total_events == 2
        assert metrics.critical_events == 1
        assert metrics.error_events == 0
        assert metrics.success_rate == 50.0
        assert "login" in metrics.top_event_types
        assert "u1" in metrics.top_users
        assert "r1" in metrics.top_resources
        assert len(metrics.recent_events) == 2
