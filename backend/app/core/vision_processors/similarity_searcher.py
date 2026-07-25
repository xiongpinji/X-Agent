"""
图像相似度搜索处理器 - 查找相似图像
"""

import logging
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class SimilaritySearcher:
    """图像相似度搜索器"""

    def __init__(self):
        self._clip_available = False
        self._embeddings_cache = {}
        self._initialize_models()

    def _initialize_models(self) -> None:
        """初始化模型"""
        try:
            import clip  # noqa: F401
            self._clip_available = True
        except ImportError:
            logger.warning("clip not installed, similarity search disabled")

    async def compute_embedding(
        self,
        image_path: str,
        **kwargs
    ) -> dict[str, Any]:
        """计算图像嵌入"""
        start_time = time.time()

        try:
            if not self._clip_available:
                return {"success": False, "error": "CLIP not installed"}

            import clip
            import torch
            from PIL import Image

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)

            image = Image.open(image_path).convert("RGB")
            image_input = preprocess(image).unsqueeze(0).to(device)

            with torch.no_grad():
                image_features = model.encode_image(image_input)
                image_features /= image_features.norm(dim=-1, keepdim=True)

            embedding = image_features.cpu().numpy().flatten().tolist()
            self._embeddings_cache[image_path] = embedding

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "data": {
                    "embedding": embedding,
                    "embedding_dim": len(embedding),
                    "latency_ms": latency_ms,
                },
            }

        except Exception as e:
            logger.error(f"Embedding computation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def find_similar_images(
        self,
        query_image_path: str,
        candidate_image_paths: list[str],
        top_k: int = 5,
        threshold: float = 0.5,
        **kwargs
    ) -> dict[str, Any]:
        """查找相似图像"""
        start_time = time.time()

        try:
            # 计算查询图像的嵌入
            query_result = await self.compute_embedding(query_image_path)
            if not query_result["success"]:
                return query_result

            query_embedding = np.array(query_result["data"]["embedding"])

            # 计算候选图像的相似度
            similarities = []
            for candidate_path in candidate_image_paths:
                candidate_result = await self.compute_embedding(candidate_path)
                if candidate_result["success"]:
                    candidate_embedding = np.array(candidate_result["data"]["embedding"])
                    similarity = float(np.dot(query_embedding, candidate_embedding))

                    if similarity >= threshold:
                        similarities.append({
                            "image_path": candidate_path,
                            "similarity": similarity,
                        })

            # 按相似度排序
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            top_results = similarities[:top_k]

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "data": {
                    "query_image": query_image_path,
                    "similar_images": top_results,
                    "total_candidates": len(candidate_image_paths),
                    "matches_found": len(similarities),
                    "latency_ms": latency_ms,
                },
            }

        except Exception as e:
            logger.error(f"Similarity search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def compute_similarity_matrix(
        self,
        image_paths: list[str],
        **kwargs
    ) -> dict[str, Any]:
        """计算相似度矩阵"""
        start_time = time.time()

        try:
            n = len(image_paths)
            similarity_matrix = np.zeros((n, n))

            # 计算所有图像的嵌入
            embeddings = []
            for path in image_paths:
                result = await self.compute_embedding(path)
                if result["success"]:
                    embeddings.append(np.array(result["data"]["embedding"]))
                else:
                    embeddings.append(None)

            # 计算相似度矩阵
            for i in range(n):
                for j in range(n):
                    if embeddings[i] is not None and embeddings[j] is not None:
                        similarity = float(np.dot(embeddings[i], embeddings[j]))
                        similarity_matrix[i, j] = similarity

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "data": {
                    "similarity_matrix": similarity_matrix.tolist(),
                    "image_paths": image_paths,
                    "matrix_size": n,
                    "latency_ms": latency_ms,
                },
            }

        except Exception as e:
            logger.error(f"Similarity matrix computation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def cluster_similar_images(
        self,
        image_paths: list[str],
        threshold: float = 0.7,
        **kwargs
    ) -> dict[str, Any]:
        """聚类相似图像"""
        start_time = time.time()

        try:
            # 计算相似度矩阵
            matrix_result = await self.compute_similarity_matrix(image_paths)
            if not matrix_result["success"]:
                return matrix_result

            similarity_matrix = np.array(matrix_result["data"]["similarity_matrix"])

            # 简单的聚类算法
            clusters = []
            visited = set()

            for i in range(len(image_paths)):
                if i in visited:
                    continue

                cluster = [image_paths[i]]
                visited.add(i)

                for j in range(i + 1, len(image_paths)):
                    if j not in visited and similarity_matrix[i, j] >= threshold:
                        cluster.append(image_paths[j])
                        visited.add(j)

                clusters.append(cluster)

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "data": {
                    "clusters": clusters,
                    "cluster_count": len(clusters),
                    "threshold": threshold,
                    "latency_ms": latency_ms,
                },
            }

        except Exception as e:
            logger.error(f"Image clustering error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def search_by_text(
        self,
        text_query: str,
        image_paths: list[str],
        top_k: int = 5,
        **kwargs
    ) -> dict[str, Any]:
        """通过文本查询搜索图像"""
        start_time = time.time()

        try:
            if not self._clip_available:
                return {"success": False, "error": "CLIP not installed"}

            import clip
            import torch
            from PIL import Image

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)

            # 编码文本查询
            text_input = clip.tokenize([text_query]).to(device)
            with torch.no_grad():
                text_features = model.encode_text(text_input)
                text_features /= text_features.norm(dim=-1, keepdim=True)

            text_embedding = text_features.cpu().numpy().flatten()

            # 计算与所有图像的相似度
            similarities = []
            for image_path in image_paths:
                image = Image.open(image_path).convert("RGB")
                image_input = preprocess(image).unsqueeze(0).to(device)

                with torch.no_grad():
                    image_features = model.encode_image(image_input)
                    image_features /= image_features.norm(dim=-1, keepdim=True)

                similarity = float(np.dot(text_embedding, image_features.cpu().numpy().flatten()))
                similarities.append({
                    "image_path": image_path,
                    "similarity": similarity,
                })

            # 排序并返回top-k
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            top_results = similarities[:top_k]

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "data": {
                    "text_query": text_query,
                    "results": top_results,
                    "total_images": len(image_paths),
                    "latency_ms": latency_ms,
                },
            }

        except Exception as e:
            logger.error(f"Text-based image search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    def clear_cache(self) -> None:
        """清除嵌入缓存"""
        self._embeddings_cache.clear()
        logger.info("Embedding cache cleared")
