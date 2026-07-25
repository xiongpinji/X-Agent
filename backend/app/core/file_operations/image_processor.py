"""
图像处理器 - 处理图像的调整、转换和滤镜
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ImageProcessor:
    """图像处理器 - 支持多种图像操作"""

    def __init__(self):
        self._pil_available = False
        self._cv2_available = False
        self._initialize_libraries()

    def _initialize_libraries(self) -> None:
        """初始化图像处理库"""
        try:
            from PIL import Image  # noqa: F401
            self._pil_available = True
        except ImportError:
            logger.warning("Pillow not installed, basic image support disabled")

        try:
            import cv2  # noqa: F401
            self._cv2_available = True
        except ImportError:
            logger.warning("OpenCV not installed, advanced image support disabled")

    async def process(
        self,
        image_path: str,
        operation: str,
        **kwargs
    ) -> dict[str, Any]:
        """
        处理图像

        Args:
            image_path: 图像文件路径
            operation: 操作类型
            **kwargs: 操作特定的参数

        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            path = Path(image_path)
            if not path.exists():
                return {"success": False, "error": f"File not found: {image_path}"}

            if operation == "resize":
                return await self._resize(image_path, **kwargs)
            elif operation == "convert_format":
                return await self._convert_format(image_path, **kwargs)
            elif operation == "apply_filter":
                return await self._apply_filter(image_path, **kwargs)
            elif operation == "get_info":
                return await self._get_info(image_path)
            elif operation == "crop":
                return await self._crop(image_path, **kwargs)
            elif operation == "rotate":
                return await self._rotate(image_path, **kwargs)
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {"success": False, "error": str(e)}

    async def _resize(
        self,
        image_path: str,
        width: int,
        height: int,
        **kwargs
    ) -> dict[str, Any]:
        """调整图像大小"""
        if not self._pil_available:
            return {"success": False, "error": "Pillow not installed"}

        try:
            from PIL import Image

            img = Image.open(image_path)
            img = img.resize((width, height), Image.Resampling.LANCZOS)

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(image_path)
                output_path = str(path.parent / f"{path.stem}_resized{path.suffix}")

            img.save(output_path)
            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return {"success": False, "error": str(e)}

    async def _convert_format(
        self,
        image_path: str,
        target_format: str,
        **kwargs
    ) -> dict[str, Any]:
        """转换图像格式"""
        if not self._pil_available:
            return {"success": False, "error": "Pillow not installed"}

        try:
            from PIL import Image

            img = Image.open(image_path)

            # 处理格式
            target_format = target_format.lower().lstrip(".")
            if target_format == "jpg":
                target_format = "jpeg"

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(image_path)
                output_path = str(path.parent / f"{path.stem}.{target_format}")

            # 转换RGBA到RGB（如果需要）
            if target_format == "jpeg" and img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                rgb_img.save(output_path, target_format.upper())
            else:
                img.save(output_path, target_format.upper())

            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error converting image format: {e}")
            return {"success": False, "error": str(e)}

    async def _apply_filter(
        self,
        image_path: str,
        filter_type: str,
        **kwargs
    ) -> dict[str, Any]:
        """应用图像滤镜"""
        if not self._pil_available:
            return {"success": False, "error": "Pillow not installed"}

        try:
            from PIL import Image, ImageFilter, ImageOps

            img = Image.open(image_path)

            if filter_type == "grayscale":
                img = ImageOps.grayscale(img)
            elif filter_type == "blur":
                radius = kwargs.get("radius", 5)
                img = img.filter(ImageFilter.GaussianBlur(radius=radius))
            elif filter_type == "sharpen":
                img = img.filter(ImageFilter.SHARPEN)
            elif filter_type == "edge":
                img = img.filter(ImageFilter.FIND_EDGES)
            elif filter_type == "invert":
                img = ImageOps.invert(img.convert("RGB"))
            else:
                return {"success": False, "error": f"Unknown filter: {filter_type}"}

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(image_path)
                output_path = str(path.parent / f"{path.stem}_{filter_type}{path.suffix}")

            img.save(output_path)
            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error applying filter: {e}")
            return {"success": False, "error": str(e)}

    async def _get_info(self, image_path: str) -> dict[str, Any]:
        """获取图像信息"""
        if not self._pil_available:
            return {"success": False, "error": "Pillow not installed"}

        try:
            from PIL import Image

            img = Image.open(image_path)
            info = {
                "width": img.width,
                "height": img.height,
                "format": img.format,
                "mode": img.mode,
                "size_bytes": Path(image_path).stat().st_size,
            }
            return {"success": True, "data": info}

        except Exception as e:
            logger.error(f"Error getting image info: {e}")
            return {"success": False, "error": str(e)}

    async def _crop(
        self,
        image_path: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
        **kwargs
    ) -> dict[str, Any]:
        """裁剪图像"""
        if not self._pil_available:
            return {"success": False, "error": "Pillow not installed"}

        try:
            from PIL import Image

            img = Image.open(image_path)
            img = img.crop((left, top, right, bottom))

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(image_path)
                output_path = str(path.parent / f"{path.stem}_cropped{path.suffix}")

            img.save(output_path)
            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error cropping image: {e}")
            return {"success": False, "error": str(e)}

    async def _rotate(
        self,
        image_path: str,
        angle: float,
        **kwargs
    ) -> dict[str, Any]:
        """旋转图像"""
        if not self._pil_available:
            return {"success": False, "error": "Pillow not installed"}

        try:
            from PIL import Image

            img = Image.open(image_path)
            img = img.rotate(angle, expand=True)

            output_path = kwargs.get("output_path")
            if not output_path:
                path = Path(image_path)
                output_path = str(path.parent / f"{path.stem}_rotated{path.suffix}")

            img.save(output_path)
            return {"success": True, "data": output_path}

        except Exception as e:
            logger.error(f"Error rotating image: {e}")
            return {"success": False, "error": str(e)}
