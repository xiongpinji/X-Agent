"""High Availability (HA) deployment module.

Implements:
- Multi-region deployment
- Automatic failover
- Load balancing
- Health checks
- Disaster recovery
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RegionName(StrEnum):
    """AWS/Cloud regions."""
    US_EAST_1 = "us-east-1"
    US_WEST_2 = "us-west-2"
    EU_WEST_1 = "eu-west-1"
    AP_SOUTHEAST_1 = "ap-southeast-1"
    AP_NORTHEAST_1 = "ap-northeast-1"


class HealthStatus(StrEnum):
    """Health status of a node."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class FailoverStrategy(StrEnum):
    """Failover strategies."""
    ACTIVE_PASSIVE = "active_passive"
    ACTIVE_ACTIVE = "active_active"
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"


class LoadBalancingAlgorithm(StrEnum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    IP_HASH = "ip_hash"
    RANDOM = "random"
    WEIGHTED = "weighted"


class HealthCheckType(StrEnum):
    """Health check types."""
    HTTP = "http"
    TCP = "tcp"
    PING = "ping"
    CUSTOM = "custom"


class Node(BaseModel):
    """Deployment node."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    region: RegionName
    endpoint: str
    port: int = 8000
    weight: int = 1  # For weighted load balancing
    status: HealthStatus = HealthStatus.UNKNOWN
    last_health_check: datetime | None = None
    consecutive_failures: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthCheck(BaseModel):
    """Health check configuration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    node_id: str
    check_type: HealthCheckType
    endpoint: str = "/health"
    interval_seconds: int = 30
    timeout_seconds: int = 5
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    last_check_at: datetime | None = None
    last_result: bool | None = None


class HealthCheckResult(BaseModel):
    """Result of a health check."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    health_check_id: str
    node_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    success: bool
    response_time_ms: int = 0
    status_code: int | None = None
    error_message: str | None = None


class Failover(BaseModel):
    """Failover event."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    from_node_id: str
    to_node_id: str
    reason: str
    duration_seconds: int = 0
    success: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoadBalancer(BaseModel):
    """Load balancer configuration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    algorithm: LoadBalancingAlgorithm
    strategy: FailoverStrategy
    nodes: list[str] = Field(default_factory=list)  # Node IDs
    active_node_id: str | None = None
    session_persistence: bool = False
    session_timeout_seconds: int = 3600
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DisasterRecoveryPlan(BaseModel):
    """Disaster recovery plan."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    rto_minutes: int  # Recovery Time Objective
    rpo_minutes: int  # Recovery Point Objective
    backup_regions: list[RegionName] = Field(default_factory=list)
    backup_frequency_hours: int = 1
    retention_days: int = 30
    last_test_at: datetime | None = None
    last_recovery_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HighAvailabilityEngine:
    """High availability engine."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.health_checks: dict[str, HealthCheck] = {}
        self.health_check_results: list[HealthCheckResult] = []
        self.load_balancers: dict[str, LoadBalancer] = {}
        self.failovers: list[Failover] = []
        self.dr_plans: dict[str, DisasterRecoveryPlan] = {}

    def register_node(self, name: str, region: RegionName, endpoint: str,
                     port: int = 8000, weight: int = 1) -> Node:
        """Register a deployment node."""
        node = Node(
            name=name,
            region=region,
            endpoint=endpoint,
            port=port,
            weight=weight
        )
        self.nodes[node.id] = node
        return node

    def create_health_check(self, node_id: str, check_type: HealthCheckType,
                           endpoint: str = "/health",
                           interval_seconds: int = 30) -> HealthCheck:
        """Create health check for node."""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")

        health_check = HealthCheck(
            node_id=node_id,
            check_type=check_type,
            endpoint=endpoint,
            interval_seconds=interval_seconds
        )
        self.health_checks[health_check.id] = health_check
        return health_check

    def record_health_check_result(self, health_check_id: str, success: bool,
                                  response_time_ms: int = 0,
                                  status_code: int | None = None,
                                  error_message: str | None = None) -> HealthCheckResult:
        """Record health check result."""
        if health_check_id not in self.health_checks:
            raise ValueError(f"Health check {health_check_id} not found")

        health_check = self.health_checks[health_check_id]
        node = self.nodes[health_check.node_id]

        result = HealthCheckResult(
            health_check_id=health_check_id,
            node_id=health_check.node_id,
            success=success,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message
        )
        self.health_check_results.append(result)

        # Update health check
        health_check.last_check_at = datetime.now(UTC)
        health_check.last_result = success

        # Update node status
        if success:
            node.consecutive_failures = 0
            if node.status != HealthStatus.HEALTHY:
                node.status = HealthStatus.HEALTHY
        else:
            node.consecutive_failures += 1
            if node.consecutive_failures >= health_check.unhealthy_threshold:
                node.status = HealthStatus.UNHEALTHY
            else:
                node.status = HealthStatus.DEGRADED

        node.last_health_check = datetime.now(UTC)
        return result

    def create_load_balancer(self, name: str, algorithm: LoadBalancingAlgorithm,
                            strategy: FailoverStrategy,
                            node_ids: list[str]) -> LoadBalancer:
        """Create load balancer."""
        for node_id in node_ids:
            if node_id not in self.nodes:
                raise ValueError(f"Node {node_id} not found")

        lb = LoadBalancer(
            name=name,
            algorithm=algorithm,
            strategy=strategy,
            nodes=node_ids,
            active_node_id=node_ids[0] if node_ids else None
        )
        self.load_balancers[lb.id] = lb
        return lb

    def select_node(self, lb_id: str, client_ip: str | None = None) -> str | None:
        """Select node for request using load balancing algorithm."""
        if lb_id not in self.load_balancers:
            raise ValueError(f"Load balancer {lb_id} not found")

        lb = self.load_balancers[lb_id]
        healthy_nodes = [
            nid for nid in lb.nodes
            if self.nodes[nid].status == HealthStatus.HEALTHY
        ]

        if not healthy_nodes:
            return None

        if lb.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            # Simple round-robin (in production, use state)
            return healthy_nodes[0]

        elif lb.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            # Return node with least connections (simplified)
            return min(healthy_nodes, key=lambda nid: self.nodes[nid].metadata.get("connections", 0))

        elif lb.algorithm == LoadBalancingAlgorithm.IP_HASH:
            if client_ip:
                hash_val = hash(client_ip)
                return healthy_nodes[hash_val % len(healthy_nodes)]
            return healthy_nodes[0]

        elif lb.algorithm == LoadBalancingAlgorithm.WEIGHTED:
            total_weight = sum(self.nodes[nid].weight for nid in healthy_nodes)
            if total_weight == 0:
                return healthy_nodes[0]
            import random
            choice = random.uniform(0, total_weight)
            current = 0
            for node_id in healthy_nodes:
                current += self.nodes[node_id].weight
                if choice <= current:
                    return node_id
            return healthy_nodes[-1]

        return healthy_nodes[0]

    def trigger_failover(self, from_node_id: str, to_node_id: str,
                        reason: str) -> Failover:
        """Trigger failover from one node to another."""
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            raise ValueError("Invalid node IDs")

        failover = Failover(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            reason=reason
        )
        self.failovers.append(failover)

        # Update load balancers
        for lb in self.load_balancers.values():
            if from_node_id in lb.nodes and lb.active_node_id == from_node_id:
                lb.active_node_id = to_node_id

        return failover

    def create_dr_plan(self, name: str, rto_minutes: int, rpo_minutes: int,
                      backup_regions: list[RegionName],
                      backup_frequency_hours: int = 1,
                      retention_days: int = 30) -> DisasterRecoveryPlan:
        """Create disaster recovery plan."""
        plan = DisasterRecoveryPlan(
            name=name,
            rto_minutes=rto_minutes,
            rpo_minutes=rpo_minutes,
            backup_regions=backup_regions,
            backup_frequency_hours=backup_frequency_hours,
            retention_days=retention_days
        )
        self.dr_plans[plan.id] = plan
        return plan

    def get_node_status_summary(self) -> dict[str, int]:
        """Get summary of node statuses."""
        summary = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0
        }
        for node in self.nodes.values():
            if node.status == HealthStatus.HEALTHY:
                summary["healthy"] += 1
            elif node.status == HealthStatus.DEGRADED:
                summary["degraded"] += 1
            elif node.status == HealthStatus.UNHEALTHY:
                summary["unhealthy"] += 1
            else:
                summary["unknown"] += 1
        return summary

    def get_failover_history(self, days: int = 30) -> list[Failover]:
        """Get failover history."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return [f for f in self.failovers if f.timestamp >= cutoff]

    def get_nodes_by_region(self, region: RegionName) -> list[Node]:
        """Get all nodes in a region."""
        return [n for n in self.nodes.values() if n.region == region]

    def get_health_check_history(self, node_id: str, hours: int = 24) -> list[HealthCheckResult]:
        """Get health check history for node."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        return [r for r in self.health_check_results
                if r.node_id == node_id and r.timestamp >= cutoff]

    def calculate_availability(self, node_id: str, hours: int = 24) -> float:
        """Calculate availability percentage for node."""
        history = self.get_health_check_history(node_id, hours)
        if not history:
            return 0.0
        successful = sum(1 for r in history if r.success)
        return (successful / len(history)) * 100

    def get_region_availability(self, region: RegionName, hours: int = 24) -> float:
        """Calculate availability for region."""
        nodes = self.get_nodes_by_region(region)
        if not nodes:
            return 0.0
        availabilities = [self.calculate_availability(n.id, hours) for n in nodes]
        return sum(availabilities) / len(availabilities)
