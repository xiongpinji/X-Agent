# 数据分析助手 / Data Analysis Assistant

**版本**: 1.0.0
**作者**: X-Agent Team
**描述**: 基于 Python 标准库的 CSV 数据画像分析：列类型识别、数值统计、文本频次分布。
**关键词**: 数据, 分析, 统计, 报表
**能力**: 数据清洗, 统计分析, 报表生成
**图标**: 📊

## 这个技能是干什么的？

对 CSV 数据做确定性统计画像（纯标准库 `csv`/`statistics` 实现，无网络依赖）：

- **列类型识别**：某列 80% 以上非空值可解析为数字 → 数值列，否则为文本列
- **数值列统计**：count / min / max / mean / median / stdev / sum
- **文本列统计**：去重计数 + 出现频次 Top 5
- **空值统计**：每列 empty / non_empty 计数

## 适合谁用？

- 数据分析师：快速摸清一份 CSV 的基本面貌
- 业务人员：理解数据含义
- 学生：完成数据作业

## 怎么用？

输入参数（`csv_text` 与 `file_path` 二选一）：

- `csv_text` (string)：CSV 文本内容
- `file_path` (string)：CSV 文件路径（需 UTF-8 可读）
- `has_header` (boolean, 默认 true)：首行是否为表头

输出：`row_count`、`column_count`、每列 `profiles`（类型 + 统计）、`truncated`
（超过 100,000 行时会截断并显式标记）。

## 使用示例

```
输入：city,sales 两列的销售 CSV
输出：
- city (text)：distinct=3，top_values=[北京×2, 上海×1, 广州×1]
- sales (numeric)：count=4, min=80, max=200, mean=137.5, ...
```

## 能力边界（重要）

- **不生成图表**：本技能无绘图依赖，只输出结构化统计数据；
  图表需由可视化工具另行生成。
- **不做趋势预测**：仅描述性统计，不做任何预测建模。
- 仅支持 CSV 格式输入；Excel 等其他格式请先转换。
