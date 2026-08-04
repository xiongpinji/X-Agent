"""归档自 tests/test_multi_agent_plugin_audit.py（2026-08-04 第三波决策：市场类归档）
测试对象 plugin_market 已归档（归档态不可运行）。
"""

class TestPluginPublishPipeline:
    def setup_method(self):
        self.service = PluginMarketService()

    def _make_manifest(self, name="Test Plugin") -> PluginManifest:
        return PluginManifest(name=name, description="A test plugin", author="tester")

    def test_submit_plugin(self):
        listing = self.service.submit_plugin(self._make_manifest())
        assert listing.status == PluginStatus.PENDING_REVIEW
        assert listing.plugin_id

    def test_review_approve(self):
        listing = self.service.submit_plugin(self._make_manifest())
        assert self.service.review_plugin(listing.plugin_id, "admin", "approve")
        updated = self.service.get_plugin(listing.plugin_id)
        assert updated.status == PluginStatus.APPROVED

    def test_review_reject(self):
        listing = self.service.submit_plugin(self._make_manifest())
        assert self.service.review_plugin(listing.plugin_id, "admin", "reject", "不安全")
        updated = self.service.get_plugin(listing.plugin_id)
        assert updated.status == PluginStatus.REJECTED

    def test_publish_requires_approval(self):
        listing = self.service.submit_plugin(self._make_manifest())
        assert not self.service.publish_plugin(listing.plugin_id)  # 未审核
        self.service.review_plugin(listing.plugin_id, "admin", "approve")
        assert self.service.publish_plugin(listing.plugin_id)
        updated = self.service.get_plugin(listing.plugin_id)
        assert updated.status == PluginStatus.PUBLISHED


class TestPluginDiscovery:
    def setup_method(self):
        self.service = PluginMarketService()
        # 发布几个插件
        for name, cat in [("Code Helper", "development"), ("Data Tool", "data"), ("Code Analyzer", "development")]:
            listing = self.service.submit_plugin(
                PluginManifest(name=name, description=f"{name} desc", category=PluginCategory(cat))
            )
            self.service.review_plugin(listing.plugin_id, "admin", "approve")
            self.service.publish_plugin(listing.plugin_id)

    def test_search_all(self):
        results = self.service.search()
        assert len(results) == 3

    def test_search_by_keyword(self):
        results = self.service.search(query="code")
        assert len(results) == 2

    def test_search_by_category(self):
        results = self.service.search(category="data")
        assert len(results) == 1


class TestPluginInstallLifecycle:
    def setup_method(self):
        self.service = PluginMarketService()
        listing = self.service.submit_plugin(PluginManifest(name="Install Test"))
        self.service.review_plugin(listing.plugin_id, "admin", "approve")
        self.service.publish_plugin(listing.plugin_id)
        self.plugin_id = listing.plugin_id

    def test_install(self):
        result = self.service.install(self.plugin_id)
        assert result.success
        listing = self.service.get_plugin(self.plugin_id)
        assert listing.is_installed

    def test_install_not_published(self):
        listing = self.service.submit_plugin(PluginManifest(name="Unpublished"))
        result = self.service.install(listing.plugin_id)
        assert not result.success

    def test_uninstall(self):
        self.service.install(self.plugin_id)
        assert self.service.uninstall(self.plugin_id)
        listing = self.service.get_plugin(self.plugin_id)
        assert not listing.is_installed


class TestPluginRatingAndRisk:
    def setup_method(self):
        self.service = PluginMarketService()

    def test_rate_plugin(self):
        listing = self.service.submit_plugin(PluginManifest(name="Rate Me"))
        self.service.review_plugin(listing.plugin_id, "admin", "approve")
        self.service.publish_plugin(listing.plugin_id)
        assert self.service.rate_plugin(listing.plugin_id, "user1", 5, "很好")
        assert self.service.rate_plugin(listing.plugin_id, "user2", 3, "一般")
        updated = self.service.get_plugin(listing.plugin_id)
        assert updated.rating == 4.0
        assert updated.rating_count == 2

    def test_risk_score_low(self):
        manifest = PluginManifest(name="Safe", permissions=[])
        assessment = self.service.compute_risk_score(manifest)
        assert assessment.risk_level == RiskLevel.LOW

    def test_risk_score_high(self):
        manifest = PluginManifest(
            name="Risky",
            permissions=["read", "write", "execute", "admin"],
            requires_network=True,
            requires_filesystem=True,
            dependencies=["dep1", "dep2"],
        )
        assessment = self.service.compute_risk_score(manifest)
        assert assessment.risk_level == RiskLevel.CRITICAL
        assert assessment.risk_score >= 80


# ─── P2-12: 企业审计 ──────────────────────────────────────────────────────────


