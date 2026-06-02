"""
视觉问答处理器 - 回答关于图像的问题
"""

import logging
from typing import Any, Dict, List, Optional
import time

logger = logging.getLogger(__name__)


class VQAProcessor:
    """视觉问答处理器"""

    def __init__(self):
        self._blip_available = False
        self._clip_available = False
        self._initialize_models()

    def _initialize_models(self) -> None:
        """初始化模型"""
        try:
            from transformers import BlipProcessor, BlipForQuestionAnswering
            self._blip_available = True
        except ImportError:
            logger.warning("transformers not installed, BLIP VQA disabled")

        try:
            import clip
            self._clip_available = True
        except ImportError:
            logger.warning("clip not installed, CLIP VQA disabled")

    async def answer_question(
        self,
        image_path: str,
        question: str,
        **kwargs
    ) -> Dict[str, Any]:
        """回答关于图像的问题"""
        start_time = time.time()

        try:
            if self._blip_available:
                return await self._answer_with_blip(image_path, question, **kwargs)
            elif self._clip_available:
                return await self._answer_with_clip(image_path, question, **kwargs)
            else:
                return {
                    "success": False,
                    "error": "No VQA models available",
                }

        except Exception as e:
            logger.error(f"VQA error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def _answer_with_blip(
        self,
        image_path: str,
        question: str,
        **kwargs
    ) -> Dict[str, Any]:
        """使用BLIP回答问题"""
        if not self._blip_available:
            return {"success": False, "error": "BLIP not installed"}

        try:
            from transformers import BlipProcessor, BlipForQuestionAnswering
            from PIL import Image
            import torch

            processor = BlipProcessor.from_pretrained("Salesforce/blip-vqa-base")
            model = BlipForQuestionAnswering.from_pretrained("Salesforce/blip-vqa-base")

            image = Image.open(image_path).convert("RGB")
            inputs = processor(image, question, return_tensors="pt")

            with torch.no_grad():
                out = model.generate(**inputs)

            answer = processor.decode(out[0], skip_special_tokens=True)

            return {
                "success": True,
                "data": {
                    "question": question,
                    "answer": answer,
                    "model": "blip-vqa",
                },
            }

        except Exception as e:
            logger.error(f"BLIP VQA error: {e}")
            return {"success": False, "error": str(e)}

    async def _answer_with_clip(
        self,
        image_path: str,
        question: str,
        **kwargs
    ) -> Dict[str, Any]:
        """使用CLIP回答问题（基于分类）"""
        if not self._clip_available:
            return {"success": False, "error": "CLIP not installed"}

        try:
            import clip
            import torch
            from PIL import Image

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)

            image = Image.open(image_path).convert("RGB")
            image_input = preprocess(image).unsqueeze(0).to(device)

            # 生成可能的答案
            possible_answers = self._generate_possible_answers(question)
            text_inputs = clip.tokenize(possible_answers).to(device)

            with torch.no_grad():
                image_features = model.encode_image(image_input)
                text_features = model.encode_text(text_inputs)
                logits_per_image = image_features @ text_features.T
                probs = logits_per_image.softmax(dim=-1).cpu().numpy()

            answer_scores = {
                answer: float(prob)
                for answer, prob in zip(possible_answers, probs[0])
            }

            best_answer = max(answer_scores, key=answer_scores.get)

            return {
                "success": True,
                "data": {
                    "question": question,
                    "answer": best_answer,
                    "confidence": answer_scores[best_answer],
                    "all_scores": answer_scores,
                    "model": "clip-vqa",
                },
            }

        except Exception as e:
            logger.error(f"CLIP VQA error: {e}")
            return {"success": False, "error": str(e)}

    async def batch_answer_questions(
        self,
        image_path: str,
        questions: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """批量回答问题"""
        try:
            answers = []
            for question in questions:
                result = await self.answer_question(image_path, question, **kwargs)
                if result["success"]:
                    answers.append({
                        "question": question,
                        "answer": result["data"]["answer"],
                    })
                else:
                    answers.append({
                        "question": question,
                        "error": result["error"],
                    })

            return {
                "success": True,
                "data": {
                    "answers": answers,
                    "total_questions": len(questions),
                    "successful": sum(1 for a in answers if "answer" in a),
                },
            }

        except Exception as e:
            logger.error(f"Batch VQA error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _generate_possible_answers(question: str) -> List[str]:
        """根据问题生成可能的答案"""
        question_lower = question.lower()

        # 颜色问题
        if "color" in question_lower or "what color" in question_lower:
            return ["red", "blue", "green", "yellow", "black", "white", "gray", "brown"]

        # 数量问题
        elif "how many" in question_lower or "count" in question_lower:
            return ["0", "1", "2", "3", "4", "5", "many", "several"]

        # 是否问题
        elif "is there" in question_lower or "are there" in question_lower:
            return ["yes", "no"]

        # 位置问题
        elif "where" in question_lower or "position" in question_lower:
            return ["left", "right", "center", "top", "bottom", "middle"]

        # 活动问题
        elif "doing" in question_lower or "activity" in question_lower:
            return ["sitting", "standing", "running", "walking", "playing", "eating", "sleeping"]

        # 默认答案
        else:
            return ["yes", "no", "maybe", "unknown"]

    async def analyze_question_type(
        self,
        question: str,
        **kwargs
    ) -> Dict[str, Any]:
        """分析问题类型"""
        question_lower = question.lower()

        question_type = "general"
        if "what" in question_lower:
            question_type = "what"
        elif "where" in question_lower:
            question_type = "where"
        elif "how many" in question_lower or "count" in question_lower:
            question_type = "count"
        elif "is" in question_lower or "are" in question_lower:
            question_type = "yes_no"
        elif "why" in question_lower:
            question_type = "why"
        elif "how" in question_lower:
            question_type = "how"

        return {
            "success": True,
            "data": {
                "question": question,
                "question_type": question_type,
            },
        }
