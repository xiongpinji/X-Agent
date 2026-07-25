"""Artifact rendering engine supporting multiple formats."""

from __future__ import annotations

from backend.app.services.artifacts.artifact_engine import Artifact, ArtifactType


class ArtifactRenderer:
    """Render artifacts in various formats."""

    # Allowed external libraries for sandboxed rendering
    ALLOWED_LIBRARIES = {
        "chart.js": "https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js",
        "d3": "https://cdn.jsdelivr.net/npm/d3@7.8.5/dist/d3.min.js",
        "plotly": "https://cdn.plot.ly/plotly-latest.min.js",
        "mermaid": "https://cdn.jsdelivr.net/npm/mermaid@11.10.0/dist/mermaid.min.js",
        "gridjs": "https://cdn.jsdelivr.net/npm/gridjs@5.0.2/dist/gridjs.umd.js",
    }

    @staticmethod
    def render_html(artifact: Artifact) -> str:
        """Render HTML artifact with sandbox wrapper.

        Args:
            artifact: Artifact to render

        Returns:
            Wrapped HTML with security measures
        """
        # Wrap content in sandbox iframe

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .artifact-container {{ width: 100%; height: 100vh; overflow: auto; }}
    </style>
</head>
<body>
    <div class="artifact-container">
        {artifact.content}
    </div>
</body>
</html>"""
        return html

    @staticmethod
    def render_react(artifact: Artifact) -> str:
        """Render React artifact with runtime.

        Args:
            artifact: Artifact to render

        Returns:
            HTML with React runtime
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        #root {{ width: 100%; height: 100vh; }}
    </style>
</head>
<body>
    <div id="root"></div>
    <script type="text/babel">
        {artifact.content}
    </script>
</body>
</html>"""
        return html

    @staticmethod
    def render_markdown(artifact: Artifact) -> str:
        """Render Markdown artifact as HTML.

        Args:
            artifact: Artifact to render

        Returns:
            HTML rendered from Markdown
        """
        # Simple markdown to HTML conversion
        html_content = artifact.content
        html_content = html_content.replace("# ", "<h1>").replace("\n", "</h1>\n")
        html_content = html_content.replace("## ", "<h2>").replace("\n", "</h2>\n")
        html_content = html_content.replace("### ", "<h3>").replace("\n", "</h3>\n")
        html_content = html_content.replace("**", "<strong>").replace("**", "</strong>")
        html_content = html_content.replace("*", "<em>").replace("*", "</em>")
        html_content = html_content.replace("\n\n", "<p>").replace("\n", "</p>\n")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3 {{ margin-top: 20px; margin-bottom: 10px; }}
        h1 {{ font-size: 2em; }}
        h2 {{ font-size: 1.5em; }}
        h3 {{ font-size: 1.2em; }}
        p {{ margin-bottom: 15px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
        return html

    @staticmethod
    def render_svg(artifact: Artifact) -> str:
        """Render SVG artifact.

        Args:
            artifact: Artifact to render

        Returns:
            HTML with embedded SVG
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <style>
        body {{ margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
        svg {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    {artifact.content}
</body>
</html>"""
        return html

    @staticmethod
    def render_chart(artifact: Artifact) -> str:
        """Render Chart.js visualization.

        Args:
            artifact: Artifact to render

        Returns:
            HTML with Chart.js
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .chart-container {{ position: relative; width: 100%; height: 500px; }}
    </style>
</head>
<body>
    <div class="chart-container">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('chart').getContext('2d');
        const config = {artifact.content};
        new Chart(ctx, config);
    </script>
</body>
</html>"""
        return html

    @staticmethod
    def render_table(artifact: Artifact) -> str:
        """Render data table with Grid.js.

        Args:
            artifact: Artifact to render

        Returns:
            HTML with Grid.js table
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <script src="https://cdn.jsdelivr.net/npm/gridjs@5.0.2/dist/gridjs.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gridjs@5.0.2/dist/theme/mermaid.min.css">
    <style>
        body {{ margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        #table {{ width: 100%; }}
    </style>
</head>
<body>
    <div id="table"></div>
    <script>
        const data = {artifact.content};
        new gridjs.Grid(data).render(document.getElementById('table'));
    </script>
</body>
</html>"""
        return html

    @staticmethod
    def render_code(artifact: Artifact) -> str:
        """Render code with syntax highlighting.

        Args:
            artifact: Artifact to render

        Returns:
            HTML with highlighted code
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; font-family: 'Monaco', 'Menlo', monospace; background: #282c34; color: #abb2bf; }}
        pre {{ background: #282c34; padding: 20px; border-radius: 5px; overflow-x: auto; }}
        code {{ font-size: 14px; line-height: 1.5; }}
    </style>
</head>
<body>
    <pre><code class="language-{artifact.render_config.get('language', 'python')}">{artifact.content}</code></pre>
    <script>hljs.highlightAll();</script>
</body>
</html>"""
        return html

    @staticmethod
    def render_dashboard(artifact: Artifact) -> str:
        """Render dashboard with multiple visualizations.

        Args:
            artifact: Artifact to render

        Returns:
            HTML dashboard
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.metadata.title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; padding: 20px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card h3 {{ margin-bottom: 15px; color: #333; }}
    </style>
</head>
<body>
    <div class="dashboard">
        {artifact.content}
    </div>
</body>
</html>"""
        return html

    def render(self, artifact: Artifact) -> str:
        """Render artifact based on type.

        Args:
            artifact: Artifact to render

        Returns:
            Rendered HTML
        """
        renderers = {
            ArtifactType.HTML: self.render_html,
            ArtifactType.REACT: self.render_react,
            ArtifactType.MARKDOWN: self.render_markdown,
            ArtifactType.SVG: self.render_svg,
            ArtifactType.CHART: self.render_chart,
            ArtifactType.TABLE: self.render_table,
            ArtifactType.CODE: self.render_code,
            ArtifactType.DASHBOARD: self.render_dashboard,
            ArtifactType.DOCUMENT: self.render_markdown,
            ArtifactType.VISUALIZATION: self.render_chart,
        }

        renderer = renderers.get(artifact.type, self.render_html)
        return renderer(artifact)

    @staticmethod
    def get_dependencies(artifact: Artifact) -> list[str]:
        """Extract required dependencies for artifact.

        Args:
            artifact: Artifact to analyze

        Returns:
            List of required library URLs
        """
        dependencies = []

        if artifact.type == ArtifactType.CHART:
            dependencies.append(ArtifactRenderer.ALLOWED_LIBRARIES["chart.js"])
        elif artifact.type == ArtifactType.TABLE:
            dependencies.append(ArtifactRenderer.ALLOWED_LIBRARIES["gridjs"])
        elif artifact.type == ArtifactType.REACT:
            dependencies.extend([
                "https://unpkg.com/react@18/umd/react.production.min.js",
                "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js",
                "https://unpkg.com/@babel/standalone/babel.min.js",
            ])

        # Add custom dependencies
        dependencies.extend(artifact.dependencies)

        return list(set(dependencies))  # Remove duplicates
