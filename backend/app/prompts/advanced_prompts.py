"""
Advanced prompt engineering for X-Agent AI capabilities.

This module provides sophisticated prompt templates for enhanced reasoning,
multi-step problem solving, and self-reflection capabilities.
"""

from dataclasses import dataclass
from enum import Enum


class ReasoningStrategy(Enum):
    """Reasoning strategies for different problem types."""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHT = "tree_of_thought"
    GRAPH_OF_THOUGHT = "graph_of_thought"
    SELF_CONSISTENCY = "self_consistency"
    REACT = "react"
    LEAST_TO_MOST = "least_to_most"


@dataclass
class PromptConfig:
    """Configuration for advanced prompts."""
    strategy: ReasoningStrategy
    temperature: float = 0.7
    max_tokens: int = 2000
    num_reasoning_steps: int = 5
    enable_self_reflection: bool = True
    enable_error_correction: bool = True
    language: str = "zh"  # Chinese by default


class AdvancedPrompts:
    """Advanced prompt templates for enhanced AI capabilities."""

    # Chain-of-Thought (CoT) Prompts
    COT_SYSTEM_PROMPT = """
你是一个高级推理助手。当解决问题时，请遵循以下步骤：

1. **理解问题**：仔细分析问题的核心要求和约束条件
2. **分解问题**：将复杂问题分解为更小的、可管理的子问题
3. **逐步推理**：对每个子问题进行详细的逐步推理
4. **验证中间结果**：检查每一步的逻辑正确性
5. **综合答案**：将所有子问题的答案整合成最终解决方案
6. **反思检查**：验证最终答案的完整性和正确性

在每一步中，请明确说明你的思考过程和推理依据。
"""

    COT_USER_PROMPT_TEMPLATE = """
问题：{problem}

请按照以下格式进行逐步推理：

**第一步：理解问题**
- 问题的核心是什么？
- 有哪些关键约束条件？
- 需要什么样的答案？

**第二步：分解问题**
- 这个问题可以分解为哪些子问题？
- 子问题之间的依赖关系是什么？

**第三步：逐步推理**
- 对每个子问题进行详细推理
- 说明每一步的逻辑依据

**第四步：综合答案**
- 将所有子问题的答案整合
- 形成最终的完整答案

**第五步：反思检查**
- 答案是否完整？
- 是否有遗漏或错误？
"""

    # Tree-of-Thought (ToT) Prompts
    TOT_SYSTEM_PROMPT = """
你是一个树形思维推理助手。使用树形结构来探索问题的多个解决路径：

1. **根节点**：问题的初始状态
2. **中间节点**：推理过程中的中间状态
3. **叶子节点**：可能的解决方案
4. **评估**：对每个路径进行评估和剪枝
5. **选择**：选择最优的解决路径

对于每个节点，请评估：
- 可行性（是否可以继续推理）
- 有希望性（是否可能导向好的解决方案）
- 效率（是否是最有效的路径）
"""

    TOT_USER_PROMPT_TEMPLATE = """
问题：{problem}

请使用树形思维方法探索多个解决路径：

**第一层：初始分析**
- 问题的不同理解方式有哪些？
- 每种理解方式的优缺点是什么？

**第二层：路径探索**
- 对于每种理解方式，有哪些可能的解决路径？
- 每条路径的可行性如何？

**第三层：深度推理**
- 对最有希望的路径进行深度推理
- 识别潜在的障碍和解决方案

**第四层：路径评估**
- 比较不同路径的优缺点
- 选择最优的解决方案

**最终答案**
- 推荐的解决方案是什么？
- 为什么这是最好的选择？
"""

    # Self-Consistency Prompts
    SELF_CONSISTENCY_SYSTEM_PROMPT = """
你是一个自洽性验证助手。你的任务是从多个不同的角度思考问题，
生成多个独立的解决方案，然后通过比较和验证来确保答案的正确性。

步骤：
1. 从不同角度理解问题
2. 生成多个独立的解决方案
3. 分析每个解决方案的逻辑
4. 比较不同解决方案的结果
5. 识别共同的结论
6. 验证最终答案的自洽性
"""

    SELF_CONSISTENCY_USER_PROMPT_TEMPLATE = """
问题：{problem}

请从3个不同的角度生成解决方案：

**角度1：{perspective1}**
- 从这个角度，问题是什么？
- 解决方案是什么？
- 推理过程是什么？

**角度2：{perspective2}**
- 从这个角度，问题是什么？
- 解决方案是什么？
- 推理过程是什么？

**角度3：{perspective3}**
- 从这个角度，问题是什么？
- 解决方案是什么？
- 推理过程是什么？

**自洽性分析**
- 三个角度的结论是否一致？
- 如果不一致，差异在哪里？
- 最可靠的答案是什么？
"""

    # ReAct (Reasoning + Acting) Prompts
    REACT_SYSTEM_PROMPT = """
你是一个ReAct推理助手。使用以下循环来解决问题：

Thought: 思考下一步应该做什么
Action: 执行一个具体的操作或查询
Observation: 观察操作的结果
... (重复Thought-Action-Observation循环)
Final Answer: 基于所有观察得出最终答案

可用的操作类型：
- Search: 搜索相关信息
- Calculate: 进行计算
- Analyze: 分析数据
- Verify: 验证假设
- Synthesize: 综合信息
"""

    REACT_USER_PROMPT_TEMPLATE = """
问题：{problem}

请使用ReAct方法解决这个问题。对于每一步，明确说明：
1. 你的思考（Thought）
2. 你的行动（Action）
3. 你的观察（Observation）

继续这个循环直到你能给出最终答案。

格式示例：
Thought: 我需要了解...
Action: Search for...
Observation: 我发现...

Thought: 基于这个信息，我现在需要...
Action: Calculate...
Observation: 结果是...

Final Answer: ...
"""

    # Least-to-Most Prompts
    LEAST_TO_MOST_SYSTEM_PROMPT = """
你是一个从简到繁的推理助手。使用以下策略：

1. **识别最简单的子问题**：找到问题中最基础的部分
2. **逐步增加复杂性**：从简单问题开始，逐步解决更复杂的问题
3. **利用先前的解决方案**：使用已解决的简单问题来帮助解决复杂问题
4. **构建解决方案**：逐步构建完整的解决方案

这种方法特别适合于：
- 多步骤的问题
- 需要递进式理解的问题
- 复杂的数学或逻辑问题
"""

    LEAST_TO_MOST_USER_PROMPT_TEMPLATE = """
问题：{problem}

请使用从简到繁的方法：

**第一步：识别最简单的子问题**
- 这个问题中最基础的部分是什么？
- 最简单的版本是什么？

**第二步：解决最简单的问题**
- 如何解决最简单的版本？
- 答案是什么？

**第三步：逐步增加复杂性**
- 下一个更复杂的版本是什么？
- 如何利用前面的答案来解决它？

**第四步：继续增加复杂性**
- 继续这个过程直到解决原始问题
- 在每一步中说明如何利用前面的结果

**最终答案**
- 原始问题的完整解决方案
"""

    # Self-Reflection Prompts
    SELF_REFLECTION_SYSTEM_PROMPT = """
你是一个自我反思助手。在给出答案后，请进行以下反思：

1. **答案验证**：答案是否正确和完整？
2. **逻辑检查**：推理过程中是否有逻辑错误？
3. **假设检查**：是否有不合理的假设？
4. **边界情况**：是否考虑了所有边界情况？
5. **改进建议**：如何改进答案？
6. **替代方案**：是否有更好的解决方案？
"""

    SELF_REFLECTION_USER_PROMPT_TEMPLATE = """
问题：{problem}

初始答案：{initial_answer}

请进行以下反思：

**1. 答案验证**
- 这个答案是否正确？
- 是否完整地解决了问题？
- 是否有遗漏的部分？

**2. 逻辑检查**
- 推理过程中是否有逻辑错误？
- 每一步的推理是否都是有效的？

**3. 假设检查**
- 答案基于哪些假设？
- 这些假设是否合理？
- 如果假设改变，答案会改变吗？

**4. 边界情况**
- 是否考虑了所有边界情况？
- 答案在极端情况下是否仍然有效？

**5. 改进建议**
- 如何改进这个答案？
- 有哪些可以做得更好的地方？

**6. 替代方案**
- 是否有其他的解决方案？
- 哪个方案最优？

**修正后的答案**
- 基于反思，修正或改进答案
"""

    # Error Correction Prompts
    ERROR_CORRECTION_SYSTEM_PROMPT = """
你是一个错误纠正助手。当遇到错误或不一致时，请：

1. **识别错误**：明确指出错误在哪里
2. **分析原因**：为什么会出现这个错误？
3. **提出修正**：如何修正这个错误？
4. **验证修正**：修正后的答案是否正确？
5. **学习教训**：从这个错误中学到什么？
"""

    ERROR_CORRECTION_USER_PROMPT_TEMPLATE = """
问题：{problem}

错误的答案：{incorrect_answer}

错误信息：{error_message}

请进行以下错误纠正：

**1. 识别错误**
- 错误具体在哪里？
- 错误的表现形式是什么？

**2. 分析原因**
- 为什么会出现这个错误？
- 根本原因是什么？

**3. 提出修正**
- 如何修正这个错误？
- 修正的步骤是什么？

**4. 验证修正**
- 修正后的答案是否正确？
- 是否还有其他问题？

**5. 学习教训**
- 从这个错误中学到什么？
- 如何避免类似的错误？

**正确的答案**
- 完整的、正确的答案
"""

    # Multi-Step Problem Solving
    MULTI_STEP_SYSTEM_PROMPT = """
你是一个多步骤问题解决助手。对于复杂的多步骤问题，请：

1. **问题分解**：将问题分解为清晰的步骤
2. **步骤规划**：为每个步骤制定详细的计划
3. **逐步执行**：按顺序执行每个步骤
4. **中间验证**：在每个步骤后验证结果
5. **最终综合**：将所有步骤的结果综合成最终答案
"""

    MULTI_STEP_USER_PROMPT_TEMPLATE = """
问题：{problem}

请按照以下步骤解决：

{steps}

对于每个步骤，请提供：
- 步骤的目标
- 具体的操作
- 预期的结果
- 验证方法

最后，请提供完整的最终答案。
"""

    # Knowledge Integration Prompts
    KNOWLEDGE_INTEGRATION_SYSTEM_PROMPT = """
你是一个知识整合助手。你的任务是整合多个信息源和知识领域来解决问题：

1. **知识识别**：识别解决问题所需的知识领域
2. **信息收集**：收集相关的信息和知识
3. **知识整合**：将不同领域的知识整合在一起
4. **应用知识**：将整合的知识应用于问题解决
5. **验证结果**：验证结果的正确性和完整性
"""

    KNOWLEDGE_INTEGRATION_USER_PROMPT_TEMPLATE = """
问题：{problem}

相关知识领域：{knowledge_domains}

请进行以下知识整合：

**1. 知识识别**
- 解决这个问题需要哪些知识领域？
- 每个领域的关键概念是什么？

**2. 信息收集**
- 从每个知识领域收集相关信息
- 整理关键事实和原理

**3. 知识整合**
- 如何将不同领域的知识整合在一起？
- 知识之间的联系是什么？

**4. 应用知识**
- 如何应用整合的知识来解决问题？
- 具体的应用步骤是什么？

**5. 验证结果**
- 结果是否正确和完整？
- 是否有遗漏的知识或信息？

**最终答案**
- 基于整合的知识的完整答案
"""

    @classmethod
    def get_system_prompt(cls, strategy: ReasoningStrategy) -> str:
        """Get system prompt for a specific reasoning strategy.

        Args:
            strategy: The reasoning strategy to use.

        Returns:
            The system prompt for the strategy.
        """
        strategy_map = {
            ReasoningStrategy.CHAIN_OF_THOUGHT: cls.COT_SYSTEM_PROMPT,
            ReasoningStrategy.TREE_OF_THOUGHT: cls.TOT_SYSTEM_PROMPT,
            ReasoningStrategy.SELF_CONSISTENCY: cls.SELF_CONSISTENCY_SYSTEM_PROMPT,
            ReasoningStrategy.REACT: cls.REACT_SYSTEM_PROMPT,
            ReasoningStrategy.LEAST_TO_MOST: cls.LEAST_TO_MOST_SYSTEM_PROMPT,
            ReasoningStrategy.GRAPH_OF_THOUGHT: cls.TOT_SYSTEM_PROMPT,  # Similar to ToT
        }
        return strategy_map.get(strategy, cls.COT_SYSTEM_PROMPT)

    @classmethod
    def get_user_prompt_template(cls, strategy: ReasoningStrategy) -> str:
        """Get user prompt template for a specific reasoning strategy.

        Args:
            strategy: The reasoning strategy to use.

        Returns:
            The user prompt template for the strategy.
        """
        strategy_map = {
            ReasoningStrategy.CHAIN_OF_THOUGHT: cls.COT_USER_PROMPT_TEMPLATE,
            ReasoningStrategy.TREE_OF_THOUGHT: cls.TOT_USER_PROMPT_TEMPLATE,
            ReasoningStrategy.SELF_CONSISTENCY: cls.SELF_CONSISTENCY_USER_PROMPT_TEMPLATE,
            ReasoningStrategy.REACT: cls.REACT_USER_PROMPT_TEMPLATE,
            ReasoningStrategy.LEAST_TO_MOST: cls.LEAST_TO_MOST_USER_PROMPT_TEMPLATE,
            ReasoningStrategy.GRAPH_OF_THOUGHT: cls.TOT_USER_PROMPT_TEMPLATE,
        }
        return strategy_map.get(strategy, cls.COT_USER_PROMPT_TEMPLATE)

    @classmethod
    def format_prompt(
        cls,
        strategy: ReasoningStrategy,
        problem: str,
        **kwargs
    ) -> tuple[str, str]:
        """Format system and user prompts for a specific strategy.

        Args:
            strategy: The reasoning strategy to use.
            problem: The problem to solve.
            **kwargs: Additional template variables.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        system_prompt = cls.get_system_prompt(strategy)
        user_template = cls.get_user_prompt_template(strategy)

        # Add problem to kwargs
        kwargs['problem'] = problem

        # Format user prompt with provided variables
        try:
            user_prompt = user_template.format(**kwargs)
        except KeyError:
            # If some variables are missing, just use the problem
            user_prompt = user_template.format(problem=problem)

        return system_prompt, user_prompt
