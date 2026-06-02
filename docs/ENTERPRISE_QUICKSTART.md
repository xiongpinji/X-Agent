# X-Agent 企业级功能快速入门指南

## 快速开始

### 1. 初始化企业功能

```python
from backend.app.core.enterprise_features import EnterpriseFeatures

# 创建企业功能实例
ef = EnterpriseFeatures()

# 设置标准企业角色
roles = ef.setup_enterprise_roles()
print(f"已创建 {len(roles)} 个企业角色")
```

### 2. 设置RBAC

```python
# 获取Admin角色
admin_role = roles["admin"]

# 分配角色给用户
assignment = ef.rbac.assign_role(
    user_id="alice@company.com",
    role_id=admin_role.id,
    assigned_by="system"
)

# 检查权限
allowed, reason = ef.rbac.check_permission(
    user_id="alice@company.com",
    resource_type=ResourceType.POLICY,
    action=PermissionAction.CREATE,
    resource_attributes={"id": "policy1"}
)

if allowed:
    print("权限已授予")
else:
    print(f"权限被拒绝: {reason}")
```

### 3. 数据治理

```python
# 注册数据
data_record = ef.data_governance.register_data(
    name="customer_database",
    classification=DataClassification.CONFIDENTIAL,
    owner_id="alice@company.com",
    retention_days=365
)

# 检测敏感信息
content = "Customer: John Doe, Email: john@example.com, SSN: 123-45-6789"
detected = ef.data_governance.detect_sensitive_data(data_record.id, content)
print(f"检测到 {len(detected)} 种敏感数据类型")

# 掩码敏感信息
masked = ef.data_governance.mask_sensitive_data(content)
print(f"掩码后: {masked}")

# 检查合规性
result = ef.data_governance.check_compliance(
    data_record.id,
    ComplianceFramework.GDPR
)
print(f"GDPR合规: {result.passed}")
```

### 4. 高可用部署

```python
# 注册节点
node1 = ef.high_availability.register_node(
    name="api-server-1",
    region=RegionName.US_EAST_1,
    endpoint="10.0.0.1",
    port=8000
)

node2 = ef.high_availability.register_node(
    name="api-server-2",
    region=RegionName.US_WEST_2,
    endpoint="10.0.0.2",
    port=8000
)

# 创建健康检查
hc = ef.high_availability.create_health_check(
    node_id=node1.id,
    check_type=HealthCheckType.HTTP,
    endpoint="/health"
)

# 记录健康检查结果
ef.high_availability.record_health_check_result(
    health_check_id=hc.id,
    success=True,
    response_time_ms=45
)

# 创建负载均衡器
lb = ef.high_availability.create_load_balancer(
    name="api-lb",
    algorithm=LoadBalancingAlgorithm.WEIGHTED,
    strategy=FailoverStrategy.ACTIVE_ACTIVE,
    node_ids=[node1.id, node2.id]
)

# 选择节点
selected_node = ef.high_availability.select_node(lb.id)
print(f"选择节点: {selected_node}")
```

### 5. 备份和恢复

```python
# 创建备份计划
schedule = ef.backup_recovery.create_backup_schedule(
    name="daily_backup",
    source_id="database_prod",
    backup_type=BackupType.FULL,
    frequency_hours=24,
    retention_days=30,
    storage_type=BackupStorageType.S3,
    storage_location="s3://backups/prod"
)

# 创建备份
backup = ef.backup_recovery.create_backup(
    name="backup_2026_05_29",
    backup_type=BackupType.FULL,
    source_id="database_prod",
    storage_type=BackupStorageType.S3,
    storage_location="s3://backups/prod/backup_2026_05_29"
)

# 执行备份
ef.backup_recovery.start_backup(backup.id)
ef.backup_recovery.complete_backup(
    backup_id=backup.id,
    size_bytes=1073741824,
    compressed_size_bytes=536870912,
    checksum="abc123"
)

# 验证备份
verification = ef.backup_recovery.verify_backup(backup.id)
print(f"备份验证: {'通过' if verification.success else '失败'}")

# 获取统计信息
stats = ef.backup_recovery.get_backup_statistics()
print(f"总备份数: {stats['total_backups']}")
print(f"压缩比: {stats['compression_ratio']:.2%}")
```

### 6. 合规性报告

```python
# 初始化GDPR合规性
ef.compliance.initialize_gdpr_compliance("org_001")

# 更新合规性状态
ef.compliance.update_gdpr_compliance(
    "org_001",
    dpo_appointed=True,
    privacy_policy_updated=True,
    dpia_completed=True,
    data_retention_policy=True,
    right_to_access_implemented=True,
    right_to_erasure_implemented=True,
    consent_management_implemented=True,
    breach_notification_process=True
)

# 创建数据主体请求
dsr = ef.compliance.create_data_subject_request(
    request_type="access",
    subject_id="subject_001"
)
print(f"数据主体请求已创建，截止日期: {dsr.due_date}")

# 生成合规性报告
report = ef.compliance.generate_compliance_report(
    organization_id="org_001",
    framework=ComplianceFramework.GDPR,
    period_days=90
)
print(f"合规性评分: {report.compliance_score}")
print(f"发现数: {len(report.findings)}")

# 获取合规性仪表板
dashboard = ef.compliance.get_compliance_dashboard("org_001")
print(f"GDPR状态: {dashboard['gdpr']['status']}")
```

### 7. 系统监控

```python
# 获取企业状态
status = ef.get_enterprise_status()
print(f"RBAC角色数: {status['rbac']['total_roles']}")
print(f"HA节点数: {status['high_availability']['total_nodes']}")
print(f"备份数: {status['backup_recovery']['total_backups']}")

# 执行健康检查
health = ef.health_check()
print(f"系统状态: {health['status']}")
for component, info in health['components'].items():
    print(f"  {component}: {info['status']}")

# 生成企业报告
report = ef.generate_enterprise_report()
print(f"报告生成时间: {report['generated_at']}")
```

## 常见任务

### 任务1: 为新员工设置权限

```python
# 1. 创建自定义角色
editor_role = ef.rbac.create_role(
    name="Editor",
    description="Can edit workflows and data"
)

# 2. 添加权限
perm = Permission(
    resource_type=ResourceType.WORKFLOW,
    action=PermissionAction.UPDATE
)
ef.rbac.add_permission_to_role(editor_role.id, perm)

# 3. 分配角色给员工
ef.rbac.assign_role(
    user_id="bob@company.com",
    role_id=editor_role.id,
    assigned_by="alice@company.com",
    expires_at=datetime.now(UTC) + timedelta(days=90)
)

# 4. 验证权限
allowed, _ = ef.rbac.check_permission(
    user_id="bob@company.com",
    resource_type=ResourceType.WORKFLOW,
    action=PermissionAction.UPDATE,
    resource_attributes={"id": "wf1"}
)
print(f"员工权限设置: {'成功' if allowed else '失败'}")
```

### 任务2: 保护敏感数据

```python
# 1. 注册敏感数据
sensitive_data = ef.data_governance.register_data(
    name="medical_records",
    classification=DataClassification.RESTRICTED,
    owner_id="alice@company.com",
    compliance_frameworks=[ComplianceFramework.HIPAA]
)

# 2. 加密数据
ef.data_governance.encrypt_data(
    data_id=sensitive_data.id,
    encryption_key_id="key_hipaa_001"
)

# 3. 检测敏感信息
content = "Patient: John Doe, MRN: 123456789, DOB: 01/01/1980"
detected = ef.data_governance.detect_sensitive_data(
    sensitive_data.id,
    content
)

# 4. 检查HIPAA合规性
result = ef.data_governance.check_compliance(
    sensitive_data.id,
    ComplianceFramework.HIPAA
)
print(f"HIPAA合规: {result.passed}")
```

### 任务3: 设置灾难恢复

```python
# 1. 创建灾难恢复计划
dr_plan = ef.high_availability.create_dr_plan(
    name="Primary DR Plan",
    rto_minutes=15,
    rpo_minutes=5,
    backup_regions=[RegionName.EU_WEST_1],
    backup_frequency_hours=1
)

# 2. 创建备份计划
backup_schedule = ef.backup_recovery.create_backup_schedule(
    name="hourly_backup",
    source_id="database_prod",
    backup_type=BackupType.INCREMENTAL,
    frequency_hours=1,
    retention_days=30,
    storage_type=BackupStorageType.GLACIER,
    storage_location="s3://backups/glacier"
)

# 3. 创建恢复点
backup = ef.backup_recovery.create_backup(
    name="backup_2026_05_29_12_00",
    backup_type=BackupType.INCREMENTAL,
    source_id="database_prod",
    storage_type=BackupStorageType.GLACIER,
    storage_location="s3://backups/glacier/backup_2026_05_29_12_00"
)
ef.backup_recovery.complete_backup(backup.id, 536870912, 268435456, "xyz789")

recovery_point = ef.backup_recovery.create_recovery_point(
    backup_id=backup.id,
    rto_minutes=15,
    rpo_minutes=5
)

# 4. 测试恢复
recovery_job = ef.backup_recovery.start_recovery(
    backup_id=backup.id,
    target_location="database_restore_test"
)
ef.backup_recovery.complete_recovery(recovery_job.id, 536870912)
print(f"恢复测试: 成功")
```

### 任务4: 生成合规性报告

```python
# 1. 初始化所有合规框架
ef.compliance.initialize_gdpr_compliance("org_001")
ef.compliance.initialize_hipaa_compliance("org_001")
ef.compliance.initialize_soc2_compliance("org_001")

# 2. 更新合规性状态
ef.compliance.update_gdpr_compliance(
    "org_001",
    dpo_appointed=True,
    privacy_policy_updated=True,
    dpia_completed=True,
    data_retention_policy=True,
    right_to_access_implemented=True,
    right_to_erasure_implemented=True,
    right_to_rectification_implemented=True,
    data_portability_implemented=True,
    consent_management_implemented=True,
    breach_notification_process=True
)

# 3. 生成报告
gdpr_report = ef.compliance.generate_compliance_report(
    organization_id="org_001",
    framework=ComplianceFramework.GDPR,
    period_days=90
)

hipaa_report = ef.compliance.generate_compliance_report(
    organization_id="org_001",
    framework=ComplianceFramework.HIPAA,
    period_days=90
)

# 4. 导出报告
gdpr_export = ef.compliance.export_compliance_report(gdpr_report.id)
print(f"GDPR报告评分: {gdpr_export['compliance_score']}")
print(f"HIPAA报告评分: {hipaa_report.compliance_score}")
```

## 性能优化建议

1. **RBAC优化**
   - 使用角色继承减少权限重复
   - 定期清理过期的角色分配
   - 缓存权限检查结果

2. **数据治理优化**
   - 批量检测敏感信息
   - 使用异步处理大型数据集
   - 定期清理过期数据

3. **高可用优化**
   - 使用加权负载均衡
   - 定期测试故障转移
   - 监控节点健康状态

4. **备份优化**
   - 使用增量备份减少存储
   - 定期验证备份完整性
   - 测试恢复过程

5. **合规性优化**
   - 自动化合规性检查
   - 定期审计日志
   - 持续监控合规性状态

## 故障排除

### 问题: 权限检查失败

**解决方案**:
1. 验证用户是否被分配了角色
2. 检查角色是否包含所需权限
3. 查看审计日志了解拒绝原因

### 问题: 备份失败

**解决方案**:
1. 检查存储位置是否可访问
2. 验证加密密钥是否可用
3. 检查磁盘空间
4. 查看备份日志

### 问题: 高可用故障

**解决方案**:
1. 检查节点健康状态
2. 验证网络连接
3. 检查负载均衡器配置
4. 查看故障转移日志

## 更多资源

- 完整文档: `docs/ENTERPRISE_FEATURES.md`
- API参考: `backend/app/api/enterprise_features.py`
- 测试用例: `tests/test_enterprise_features.py`
- 核心模块:
  - `backend/app/core/advanced_rbac.py`
  - `backend/app/core/data_governance.py`
  - `backend/app/core/high_availability.py`
  - `backend/app/core/backup_recovery.py`
  - `backend/app/core/compliance_reporting.py`
