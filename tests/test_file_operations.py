"""
文件操作测试
"""

import pytest
import tempfile
from pathlib import Path
from backend.app.core.file_operations import (
    DocumentProcessor,
    ImageProcessor,
    FileConverter,
)


class TestDocumentProcessor:
    """文档处理器测试"""

    @pytest.fixture
    def processor(self):
        return DocumentProcessor()

    @pytest.mark.asyncio
    async def test_process_nonexistent_file(self, processor):
        """测试处理不存在的文件"""
        result = await processor.process("/nonexistent/file.docx", "extract_text")
        assert not result["success"]
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unsupported_format(self, processor):
        """测试不支持的格式"""
        with tempfile.NamedTemporaryFile(suffix=".xyz") as f:
            result = await processor.process(f.name, "extract_text")
            assert not result["success"]
            assert "unsupported" in result["error"].lower()


class TestImageProcessor:
    """图像处理器测试"""

    @pytest.fixture
    def processor(self):
        return ImageProcessor()

    @pytest.mark.asyncio
    async def test_process_nonexistent_image(self, processor):
        """测试处理不存在的图像"""
        result = await processor.process("/nonexistent/image.jpg", "get_info")
        assert not result["success"]
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_operation(self, processor):
        """测试未知操作"""
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            result = await processor.process(f.name, "unknown_op")
            assert not result["success"]
            assert "unknown" in result["error"].lower()


class TestFileConverter:
    """文件转换器测试"""

    @pytest.fixture
    def converter(self):
        return FileConverter()

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        """测试转换不存在的文件"""
        result = await converter.convert("/nonexistent/file.csv", "json")
        assert not result["success"]
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unsupported_conversion(self, converter):
        """测试不支持的转换"""
        with tempfile.NamedTemporaryFile(suffix=".xyz") as f:
            result = await converter.convert(f.name, "json")
            assert not result["success"]
            assert "not supported" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_csv_to_json_conversion(self, converter):
        """测试CSV到JSON的转换"""
        try:
            import csv
            import json

            # 创建测试CSV文件
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".csv",
                delete=False,
                newline="",
            ) as f:
                csv_path = f.name
                writer = csv.DictWriter(f, fieldnames=["name", "age"])
                writer.writeheader()
                writer.writerow({"name": "Alice", "age": "30"})
                writer.writerow({"name": "Bob", "age": "25"})

            try:
                # 转换文件
                with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                    json_path = f.name

                result = await converter.convert(
                    csv_path,
                    "json",
                    output_path=json_path,
                )

                assert result["success"]
                assert Path(json_path).exists()

                # 验证转换结果
                with open(json_path) as f:
                    data = json.load(f)
                    assert len(data) == 2
                    assert data[0]["name"] == "Alice"

            finally:
                Path(csv_path).unlink(missing_ok=True)
                Path(json_path).unlink(missing_ok=True)

        except ImportError:
            pytest.skip("Required libraries not installed")
