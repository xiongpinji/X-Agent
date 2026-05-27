"""
文件转换器 - 支持多种文件格式转换
"""

import logging
from typing import Any, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class FileConverter:
    """文件转换器 - 支持多种文件格式转换"""

    def __init__(self):
        self._converters = {}
        self._initialize_converters()

    def _initialize_converters(self) -> None:
        """初始化转换器"""
        # 注册支持的转换
        self._converters["markdown_to_html"] = self._markdown_to_html
        self._converters["csv_to_json"] = self._csv_to_json
        self._converters["json_to_csv"] = self._json_to_csv
        self._converters["yaml_to_json"] = self._yaml_to_json
        self._converters["json_to_yaml"] = self._json_to_yaml

    async def convert(
        self,
        input_path: str,
        output_format: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        转换文件格式

        Args:
            input_path: 输入文件路径
            output_format: 输出格式
            **kwargs: 转换特定的参数

        Returns:
            Dict[str, Any]: 转换结果
        """
        try:
            path = Path(input_path)
            if not path.exists():
                return {"success": False, "error": f"File not found: {input_path}"}

            input_format = path.suffix.lower().lstrip(".")
            conversion_key = f"{input_format}_to_{output_format}"

            if conversion_key not in self._converters:
                return {
                    "success": False,
                    "error": f"Conversion not supported: {input_format} -> {output_format}",
                }

            converter = self._converters[conversion_key]
            return await converter(input_path, **kwargs)

        except Exception as e:
            logger.error(f"Error converting file: {e}")
            return {"success": False, "error": str(e)}

    async def _markdown_to_html(self, input_path: str, **kwargs) -> Dict[str, Any]:
        """Markdown转HTML"""
        try:
            import markdown

            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()

            html = markdown.markdown(content)

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(input_path)
                output_path = str(path.parent / f"{path.stem}.html")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

            return {"success": True, "data": output_path}

        except ImportError:
            return {"success": False, "error": "markdown library not installed"}
        except Exception as e:
            logger.error(f"Error converting markdown to html: {e}")
            return {"success": False, "error": str(e)}

    async def _csv_to_json(self, input_path: str, **kwargs) -> Dict[str, Any]:
        """CSV转JSON"""
        try:
            import csv
            import json

            data = []
            with open(input_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(input_path)
                output_path = str(path.parent / f"{path.stem}.json")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error converting csv to json: {e}")
            return {"success": False, "error": str(e)}

    async def _json_to_csv(self, input_path: str, **kwargs) -> Dict[str, Any]:
        """JSON转CSV"""
        try:
            import csv
            import json

            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                return {"success": False, "error": "JSON must be an array of objects"}

            if not data:
                return {"success": False, "error": "JSON array is empty"}

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(input_path)
                output_path = str(path.parent / f"{path.stem}.csv")

            fieldnames = list(data[0].keys())
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error converting json to csv: {e}")
            return {"success": False, "error": str(e)}

    async def _yaml_to_json(self, input_path: str, **kwargs) -> Dict[str, Any]:
        """YAML转JSON"""
        try:
            import json
            import yaml

            with open(input_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(input_path)
                output_path = str(path.parent / f"{path.stem}.json")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return {"success": True, "data": output_path}

        except ImportError:
            return {"success": False, "error": "PyYAML library not installed"}
        except Exception as e:
            logger.error(f"Error converting yaml to json: {e}")
            return {"success": False, "error": str(e)}

    async def _json_to_yaml(self, input_path: str, **kwargs) -> Dict[str, Any]:
        """JSON转YAML"""
        try:
            import json
            import yaml

            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(input_path)
                output_path = str(path.parent / f"{path.stem}.yaml")

            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            return {"success": True, "data": output_path}

        except ImportError:
            return {"success": False, "error": "PyYAML library not installed"}
        except Exception as e:
            logger.error(f"Error converting json to yaml: {e}")
            return {"success": False, "error": str(e)}
