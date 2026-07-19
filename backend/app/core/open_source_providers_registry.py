from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord


class PackageRegistryOpenSourceProvider:
    def __init__(self, name: str = "package-registry") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        urls = [f"https://pypi.org/pypi/{query}/json", "https://pypi.org/pypi/openai/json", "https://pypi.org/pypi/playwright/json"]
        results: list[OpenSourceCandidateRecord] = []
        for url in urls:
            if len(results) >= limit:
                break
            try:
                response = requests.get(url, timeout=8)
                if response.status_code != 200:
                    continue
                payload = response.json()
                info = payload.get("info", {}) if isinstance(payload, dict) else {}
                name = str(info.get("name") or query or "package")
                summary = str(info.get("summary") or "")
                version = str(info.get("version") or "")
                if query and query.lower() not in (name.lower() + " " + summary.lower()):
                    continue
                results.append(OpenSourceCandidateRecord(name=name, source=self.name, url=f"https://pypi.org/project/{name}/", license=str(info.get("license") or ""), summary=summary, score=0.68, reasons=["package registry result"], tags=["package", "python", version] if version else ["package", "python"], metadata={"provider": self.name, "provider_kind": "package-registry", "version": version, "requires_python": info.get("requires_python"), "home_page": info.get("home_page"), "project_urls": info.get("project_urls", {})}))
            except Exception:
                continue
        return results


class NpmRegistryOpenSourceProvider:
    def __init__(self, name: str = "npm-registry") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        q = query.lower().strip()
        names = [query, f"@types/{query}", "playwright", "react"]
        results: list[OpenSourceCandidateRecord] = []
        for pkg in names:
            if len(results) >= limit:
                break
            try:
                response = requests.get(f"https://registry.npmjs.org/{pkg}", timeout=8)
                if response.status_code != 200:
                    continue
                payload = response.json()
                if not isinstance(payload, dict):
                    continue
                name = str(payload.get("name") or pkg)
                latest = (payload.get("dist-tags") or {}).get("latest") if isinstance(payload.get("dist-tags"), dict) else None
                versions = payload.get("versions") or {}
                latest_info = versions.get(latest, {}) if isinstance(versions, dict) and latest else {}
                description = str(payload.get("description") or latest_info.get("description") or "")
                if q and q not in (name.lower() + " " + description.lower()):
                    continue
                maintainers = payload.get("maintainers") or []
                publishers = [m.get("name") for m in maintainers if isinstance(m, dict) and m.get("name")]
                time_info = payload.get("time") or {}
                results.append(OpenSourceCandidateRecord(name=name, source=self.name, url=f"https://www.npmjs.com/package/{name}", license=str(payload.get("license") or latest_info.get("license") or ""), summary=description, score=min(1.0, 0.66 + (0.01 if latest else 0.0)), reasons=["npm registry result"], tags=["npm", "javascript", str(latest or "")], metadata={"provider": self.name, "provider_kind": "npm-registry", "latest_version": latest, "publishers": publishers, "created_at": str(time_info.get("created") or ""), "modified_at": str(time_info.get("modified") or ""), "keywords": payload.get("keywords", [])}))
            except Exception:
                continue
        return results


class MavenCentralOpenSourceProvider:
    def __init__(self, name: str = "maven-central") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        q = query.strip() or "agent"
        params = {"q": q, "rows": max(1, min(limit, 20)), "wt": "json", "sort": "score desc"}
        try:
            response = requests.get("https://search.maven.org/solrsearch/select", params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        docs = payload.get("response", {}).get("docs", []) if isinstance(payload, dict) else []
        results: list[OpenSourceCandidateRecord] = []
        for doc in docs[:limit]:
            if not isinstance(doc, dict):
                continue
            group_id = str(doc.get("g") or "")
            artifact_id = str(doc.get("a") or "")
            version = str(doc.get("latestVersion") or doc.get("v") or "")
            packaging = str(doc.get("p") or "jar")
            id_text = f"{group_id}:{artifact_id}".strip(":")
            if q.lower() not in (id_text.lower() + " " + str(doc.get("id") or "").lower()):
                continue
            results.append(OpenSourceCandidateRecord(name=id_text or artifact_id or q, source=self.name, url=f"https://search.maven.org/artifact/{group_id}/{artifact_id}", summary=f"Maven artifact {id_text} {version}".strip(), score=0.7, reasons=["maven central result"], tags=["java", "maven", packaging], metadata={"provider": self.name, "provider_kind": "maven-central", "group_id": group_id, "artifact_id": artifact_id, "version": version, "packaging": packaging, "timestamp": doc.get("timestamp")}))
        return results


class CratesIoOpenSourceProvider:
    def __init__(self, name: str = "crates-io") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        q = query.strip() or "agent"
        try:
            response = requests.get("https://crates.io/api/v1/crates", params={"q": q, "per_page": max(1, min(limit, 20))}, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        crates = payload.get("crates", []) if isinstance(payload, dict) else []
        results: list[OpenSourceCandidateRecord] = []
        for crate in crates[:limit]:
            if not isinstance(crate, dict):
                continue
            name = str(crate.get("id") or "")
            desc = str(crate.get("description") or "")
            if q.lower() not in (name.lower() + " " + desc.lower()):
                continue
            results.append(OpenSourceCandidateRecord(name=name, source=self.name, url=f"https://crates.io/crates/{name}", license=str(crate.get("license") or ""), summary=desc, score=0.69, reasons=["crates.io result"], tags=["rust", "cargo"], metadata={"provider": self.name, "provider_kind": "crates-io", "max_version": crate.get("max_version"), "downloads": crate.get("downloads"), "updated_at": crate.get("updated_at")}))
        return results


class RubyGemsOpenSourceProvider:
    def __init__(self, name: str = "rubygems") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        q = query.strip() or "agent"
        try:
            response = requests.get("https://rubygems.org/api/v1/search.json", params={"query": q}, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        gems = payload if isinstance(payload, list) else []
        results: list[OpenSourceCandidateRecord] = []
        for gem in gems[:limit]:
            if not isinstance(gem, dict):
                continue
            name = str(gem.get("name") or "")
            info = str(gem.get("info") or "")
            if q.lower() not in (name.lower() + " " + info.lower()):
                continue
            results.append(OpenSourceCandidateRecord(name=name, source=self.name, url=f"https://rubygems.org/gems/{name}", license="", summary=info, score=0.67, reasons=["rubygems result"], tags=["ruby", "gem"], metadata={"provider": self.name, "provider_kind": "rubygems", "version": gem.get("version"), "downloads": gem.get("downloads"), "authors": gem.get("authors")}))
        return results


class GoPkgOpenSourceProvider:
    def __init__(self, name: str = "go-pkg") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        q = query.strip() or "agent"
        try:
            response = requests.get("https://pkg.go.dev/search", params={"q": q}, timeout=8)
            response.raise_for_status()
            text = response.text
        except Exception:
            return []
        lines = [line.strip() for line in text.splitlines() if q.lower() in line.lower()]
        results: list[OpenSourceCandidateRecord] = []
        for idx, line in enumerate(lines[:limit]):
            if not line:
                continue
            results.append(OpenSourceCandidateRecord(name=f"go-pkg-{idx+1}", source=self.name, url="https://pkg.go.dev/search", summary=line[:200], score=0.64, reasons=["go package search result"], tags=["go", "pkg"], metadata={"provider": self.name, "provider_kind": "go-pkg", "query": q, "line_index": idx}))
        return results
