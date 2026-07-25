"""
对象检测处理器 - 检测和定位图像中的对象
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    """检测到的对象"""
    label: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)
    area: float = 0.0


class ObjectDetector:
    """对象检测器 - 支持多种检测模型"""

    def __init__(self, model: str = "yolov8"):
        self.model = model
        self._yolo_available = False
        self._rcnn_available = False
        self._initialize_models()

    def _initialize_models(self) -> None:
        """初始化检测模型"""
        try:
            import ultralytics  # noqa: F401
            self._yolo_available = True
        except ImportError:
            logger.warning("ultralytics not installed, YOLOv8 disabled")

        try:
            import torchvision  # noqa: F401
            self._rcnn_available = True
        except ImportError:
            logger.warning("torchvision not installed, Faster R-CNN disabled")

    async def detect_objects(
        self,
        image_path: str,
        confidence_threshold: float = 0.5,
        **kwargs
    ) -> dict[str, Any]:
        """检测对象"""
        start_time = time.time()

        try:
            if self.model == "yolov8":
                return await self._detect_with_yolo(image_path, confidence_threshold, **kwargs)
            elif self.model == "faster_rcnn":
                return await self._detect_with_rcnn(image_path, confidence_threshold, **kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unknown detection model: {self.model}",
                }

        except Exception as e:
            logger.error(f"Object detection error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def _detect_with_yolo(
        self,
        image_path: str,
        confidence_threshold: float,
        **kwargs
    ) -> dict[str, Any]:
        """使用YOLOv8检测对象"""
        if not self._yolo_available:
            return {"success": False, "error": "YOLOv8 not installed"}

        try:
            from ultralytics import YOLO

            model = YOLO("yolov8n.pt")
            results = model(image_path, conf=confidence_threshold)

            detections = []
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    label = result.names[class_id]

                    detections.append({
                        "label": label,
                        "confidence": confidence,
                        "bbox": [x1, y1, x2, y2],
                        "area": (x2 - x1) * (y2 - y1),
                    })

            # 按置信度排序
            detections.sort(key=lambda x: x["confidence"], reverse=True)

            return {
                "success": True,
                "data": {
                    "detections": detections,
                    "object_count": len(detections),
                    "top_objects": detections[:5],
                },
            }

        except Exception as e:
            logger.error(f"YOLOv8 detection error: {e}")
            return {"success": False, "error": str(e)}

    async def _detect_with_rcnn(
        self,
        image_path: str,
        confidence_threshold: float,
        **kwargs
    ) -> dict[str, Any]:
        """使用Faster R-CNN检测对象"""
        if not self._rcnn_available:
            return {"success": False, "error": "Faster R-CNN not installed"}

        try:
            import torch
            import torchvision
            from PIL import Image

            model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
                pretrained=True
            )
            model.eval()

            image = Image.open(image_path).convert("RGB")
            image_tensor = torchvision.transforms.functional.to_tensor(image)

            with torch.no_grad():
                predictions = model([image_tensor])

            detections = []
            for _i, (box, score, label) in enumerate(
                zip(
                    predictions[0]["boxes"],
                    predictions[0]["scores"],
                    predictions[0]["labels"], strict=False,
                )
            ):
                if score >= confidence_threshold:
                    x1, y1, x2, y2 = box.tolist()
                    detections.append({
                        "label": f"object_{label.item()}",
                        "confidence": float(score),
                        "bbox": [x1, y1, x2, y2],
                        "area": (x2 - x1) * (y2 - y1),
                    })

            detections.sort(key=lambda x: x["confidence"], reverse=True)

            return {
                "success": True,
                "data": {
                    "detections": detections,
                    "object_count": len(detections),
                    "top_objects": detections[:5],
                },
            }

        except Exception as e:
            logger.error(f"Faster R-CNN detection error: {e}")
            return {"success": False, "error": str(e)}

    async def detect_specific_objects(
        self,
        image_path: str,
        target_labels: list[str],
        **kwargs
    ) -> dict[str, Any]:
        """检测特定类型的对象"""
        result = await self.detect_objects(image_path, **kwargs)

        if not result["success"]:
            return result

        detections = result["data"]["detections"]
        filtered = [d for d in detections if d["label"] in target_labels]

        return {
            "success": True,
            "data": {
                "detections": filtered,
                "object_count": len(filtered),
                "target_labels": target_labels,
            },
        }

    async def get_object_statistics(
        self,
        image_path: str,
        **kwargs
    ) -> dict[str, Any]:
        """获取对象统计信息"""
        result = await self.detect_objects(image_path, **kwargs)

        if not result["success"]:
            return result

        detections = result["data"]["detections"]

        # 统计标签
        label_counts = {}
        label_confidences = {}
        for det in detections:
            label = det["label"]
            label_counts[label] = label_counts.get(label, 0) + 1
            if label not in label_confidences:
                label_confidences[label] = []
            label_confidences[label].append(det["confidence"])

        # 计算平均置信度
        avg_confidences = {
            label: sum(confs) / len(confs)
            for label, confs in label_confidences.items()
        }

        return {
            "success": True,
            "data": {
                "total_objects": len(detections),
                "unique_labels": len(label_counts),
                "label_counts": label_counts,
                "average_confidences": avg_confidences,
                "detections": detections,
            },
        }
