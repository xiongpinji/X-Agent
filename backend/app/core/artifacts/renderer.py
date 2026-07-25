"""Artifact rendering engine."""

from __future__ import annotations

import json
from typing import Any

from backend.app.core.artifacts.storage import Artifact


class ArtifactRenderer:
    """Artifact rendering engine."""

    async def render_html(self, artifact: Artifact, data: dict[str, Any] | None = None) -> str:
        """Render HTML artifact.

        Args:
            artifact: Artifact to render
            data: Data for template rendering

        Returns:
            Rendered HTML
        """
        if artifact.type != "html":
            raise ValueError(f"Expected html artifact, got {artifact.type}")

        # For now, return content as-is
        # In production, use Jinja2 or similar for template rendering
        return artifact.content

    async def render_chart(self, artifact: Artifact, data: list[dict[str, Any]] | None = None) -> str:
        """Render chart artifact.

        Args:
            artifact: Artifact to render
            data: Chart data

        Returns:
            Rendered chart HTML
        """
        if artifact.type != "chart":
            raise ValueError(f"Expected chart artifact, got {artifact.type}")

        chart_type = artifact.metadata.get("chart_type", "bar")
        chart_data = data or artifact.metadata.get("data", [])

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{artifact.name}</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                canvas {{ max-width: 100%; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{artifact.name}</h1>
                <canvas id="chart"></canvas>
            </div>
            <script>
                const ctx = document.getElementById('chart').getContext('2d');
                const chartData = {json.dumps(chart_data)};
                new Chart(ctx, {{
                    type: '{chart_type}',
                    data: chartData,
                    options: {{
                        responsive: true,
                        plugins: {{
                            title: {{
                                display: true,
                                text: '{artifact.name}'
                            }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        return html

    async def render_table(self, artifact: Artifact, data: list[dict[str, Any]] | None = None) -> str:
        """Render table artifact.

        Args:
            artifact: Artifact to render
            data: Table data

        Returns:
            Rendered table HTML
        """
        if artifact.type != "table":
            raise ValueError(f"Expected table artifact, got {artifact.type}")

        table_data = data or artifact.metadata.get("data", [])

        # Generate table HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{artifact.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{artifact.name}</h1>
                <table>
        """

        if table_data:
            # Get column names from first row
            columns = list(table_data[0].keys())

            # Add header
            html += "<thead><tr>"
            for col in columns:
                html += f"<th>{col}</th>"
            html += "</tr></thead>"

            # Add rows
            html += "<tbody>"
            for row in table_data:
                html += "<tr>"
                for col in columns:
                    html += f"<td>{row.get(col, '')}</td>"
                html += "</tr>"
            html += "</tbody>"

        html += """
                </table>
            </div>
        </body>
        </html>
        """
        return html

    async def render_dashboard(self, artifact: Artifact, data: dict[str, Any] | None = None) -> str:
        """Render dashboard artifact.

        Args:
            artifact: Artifact to render
            data: Dashboard data

        Returns:
            Rendered dashboard HTML
        """
        if artifact.type != "dashboard":
            raise ValueError(f"Expected dashboard artifact, got {artifact.type}")

        dashboard_data = data or artifact.metadata.get("data", {})

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{artifact.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .dashboard {{ max-width: 1400px; margin: 0 auto; }}
                .dashboard-header {{ background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .dashboard-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                .card {{ background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .card-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .card-value {{ font-size: 32px; font-weight: bold; color: #2196F3; }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <div class="dashboard-header">
                    <h1>{artifact.name}</h1>
                    <p>{artifact.description}</p>
                </div>
                <div class="dashboard-grid">
        """

        # Add cards for each metric
        for key, value in dashboard_data.items():
            html += f"""
                    <div class="card">
                        <div class="card-title">{key}</div>
                        <div class="card-value">{value}</div>
                    </div>
            """

        html += """
                </div>
            </div>
        </body>
        </html>
        """
        return html

    async def render(self, artifact: Artifact, data: dict[str, Any] | None = None) -> str:
        """Render artifact based on type.

        Args:
            artifact: Artifact to render
            data: Data for rendering

        Returns:
            Rendered artifact
        """
        if artifact.type == "html":
            return await self.render_html(artifact, data)
        elif artifact.type == "chart":
            return await self.render_chart(artifact, data.get("chart_data") if data else None)
        elif artifact.type == "table":
            return await self.render_table(artifact, data.get("table_data") if data else None)
        elif artifact.type == "dashboard":
            return await self.render_dashboard(artifact, data)
        else:
            raise ValueError(f"Unknown artifact type: {artifact.type}")
