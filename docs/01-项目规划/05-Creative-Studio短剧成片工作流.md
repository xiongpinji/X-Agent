# X-Agent Creative Studio 短剧成片工作流待完成项目

## 项目定位

**项目名称：** X-Agent Creative Studio / 短剧工厂 Agent
**状态：** 待完成，建议列为高优先级商业化项目
**目标用户：** 短剧团队、短视频运营、MCN、内容工作室、电商内容团队、个人创作者
**核心目标：** 让用户输入一句话需求后，由 X-Agent 内置短剧制作人智能体自动生成可下载、可发布的短剧或短视频成品。

本项目不是简单的视频生成模型接入，也不是脚本生成器。它要体现 X-Agent 的内核优势：

```text
专业角色智能体
+ 子代理团队
+ 多模型路由
+ 专业知识包
+ 故事板优先工作流
+ 结构化中间产物
+ 自动质检与重试
+ 最终成品交付
```

普通智能体平台通常是“用户请求 -> 单个 Agent -> 文本输出”。X-Agent 应该交付“用户请求 -> 专业创作团队 -> 结构化生产流水线 -> 成品 MP4”。

## 为什么先做短剧方向

短剧和短视频是当前需求量最大、付费意愿明确、结果可感知的场景。用户不愿意只买“生成脚本”，真正的购买理由是：

```text
能不能稳定出成片
能不能减少人工编剧、分镜、配音、剪辑时间
能不能批量生成账号可发布素材
能不能把模型随机性变成可控生产流程
```

因此第一版不能停留在脚本、分镜或提示词层面，必须形成完整成品闭环。

## V1 商业交付目标

V1 名称建议：

```text
Creative Studio V1：一句话生成短剧成片
```

V1 最小可商用规格：

```text
输入：
- 一句话创作需求
- 短剧类型
- 目标平台
- 时长：30 秒 / 60 秒 / 90 秒
- 风格：都市、甜宠、逆袭、复仇、霸总、古风等
- 角色数量：1-3 个

输出：
- final.mp4
- cover.png
- script.md
- storyboard.json
- subtitles.srt
- voiceover.wav 或 voiceover.mp3
- publish_copy.md
- assets_manifest.json
```

V1 必须满足：

```text
- 竖屏 9:16
- 3-8 个镜头
- 自动字幕
- 自动配音
- 自动封面
- 自动剪辑合成
- 任务进度可见
- 失败镜头可单独重试
- 成品可下载
```

## 核心原则：故事板优先

短剧成片不能走“抽卡式生成”，不能直接把一句话丢给视频模型。正确路线是：

```text
用户需求
-> 爆款结构分析
-> 剧情大纲
-> 角色卡
-> 场景卡
-> 完整剧本
-> 镜头级故事板
-> 图片提示词
-> 视频提示词
-> 配音与字幕
-> 剪辑计划
-> 成片合成
```

故事板是整个工作流的核心契约。图片模型、视频模型、TTS、字幕、剪辑都应该从故事板读取结构化字段，而不是各自重新理解需求。

## 故事板 Schema 草案

每个镜头必须具备稳定、可验证的字段：

```json
{
  "shot_id": "S03",
  "duration_seconds": 4,
  "scene": "夜晚，高级公寓客厅",
  "characters": ["female_lead", "male_lead"],
  "plot_purpose": "男主发现女主真实身份，制造反转",
  "camera": {
    "shot_size": "medium close-up",
    "angle": "low angle",
    "movement": "slow push-in",
    "lens": "50mm cinematic",
    "focus": "rack focus from male lead to female lead",
    "composition": "female lead framed on right third, male lead blurred near doorway"
  },
  "lighting": {
    "style": "low-key cinematic lighting",
    "key_light": "soft warm practical lamp from camera left",
    "fill_light": "minimal cool fill",
    "back_light": "thin rim light separating hair and shoulder",
    "contrast": "high contrast",
    "color_temperature": "warm interior with cool moonlight accent",
    "mood": "luxury, suspense, emotional pressure"
  },
  "action": "女主转身，表情冷静，男主停在门口震惊。",
  "dialogue": "你以为我只是普通人？",
  "subtitle": "你以为我只是普通人？",
  "emotion": "冷静、压迫感、反转",
  "visual_prompt": "cinematic vertical short drama, luxury apartment at night...",
  "video_prompt": "slow push-in toward female lead, she turns back with calm expression...",
  "continuity": {
    "character_ref": "female_lead_v1",
    "scene_ref": "luxury_apartment_v1",
    "style_ref": "urban_drama_cinematic"
  },
  "negative_prompt": "deformed face, inconsistent outfit, extra fingers, low quality"
}
```

完整故事板还应包含：

```text
- project_id
- title
- genre
- platform
- target_duration_seconds
- aspect_ratio
- style_profile
- character_cards
- scene_cards
- shots
- subtitle_tracks
- audio_plan
- edit_plan
- quality_gates
```

## 内置角色智能体

新增内置角色：

```text
ShortDramaProducerAgent
短剧制作人智能体
```

职责：

```text
- 接收用户需求
- 识别短剧/短视频任务
- 选择短剧工作流模板
- 调度子代理团队
- 维护故事板状态
- 调用多模型路由
- 控制成本、超时、重试
- 聚合成品交付包
```

## 子代理团队

V1 建议内置以下子代理：

```text
1. 选题策划 Agent
   负责爆款方向、目标受众、平台风格、标题、前 3 秒钩子。

2. 编剧 Agent
   负责剧情结构、人物关系、冲突、反转、台词、结尾钩子。

3. 断句字幕 Agent
   负责口播节奏、断句、停顿、字幕 SRT、情绪标记。

4. 分镜导演 Agent
   负责镜头表、景别、运镜、镜头时长、镜头衔接、画面构图。

5. 摄影灯光 Agent
   负责镜头语言、机位、焦段、构图、光线、影调、色温、氛围。

6. 角色与美术 Agent
   负责角色卡、服装、妆造、场景卡、画面风格、封面视觉。

7. 图片生成 Agent
   调用图片生成模型生成角色图、场景图、关键帧、封面图。

8. 视频生成 Agent
   调用文生视频或图生视频模型生成镜头片段。

9. 配音 Agent
   调用 TTS 或数字人语音模型生成旁白、角色台词、音频文件。

10. 剪辑合成 Agent
   使用 FFmpeg 或 Remotion 合成镜头、配音、字幕、BGM、转场。

11. 质检 Agent
    检查剧情连贯性、角色一致性、字幕错字、时长、违规风险、缺失素材。
```

## 专业知识包

短剧智能体必须内置专业提示词和影视知识，不应完全依赖通用模型临场发挥。

### 剧本知识

```text
- 三幕式
- 钩子
- 冲突
- 爽点
- 悬念
- 反转
- 人设
- 情绪递进
- 结尾钩子
```

### 短剧类型知识

```text
- 霸总
- 甜宠
- 复仇
- 逆袭
- 豪门
- 都市
- 古风
- 赘婿
- 男频爽文
- 女频情感
```

### 镜头与运镜知识

```text
- 景别：远景、全景、中景、中近景、近景、特写、大特写、过肩镜头、双人镜头、主观镜头
- 机位：平视、俯拍、仰拍、鸟瞰、低机位、高机位、侧面、背面、正反打
- 运镜：推镜、拉镜、摇镜、移镜、跟拍、环绕、升降、横移、手持、稳定器、甩镜
- 焦点：浅景深、深焦、拉焦、跟焦、前景遮挡、焦点转移
- 镜头节奏：静态压迫、慢推制造悬念、快速切换制造冲突、长镜头增强沉浸
- 构图：三分法、中心构图、对称构图、框中框、留白、前景层次、引导线
- 情绪映射：低机位强化压迫感，俯拍强化弱势感，特写强化情绪爆点
```

### 光线与影调知识

```text
- 基础布光：主光、辅光、轮廓光、背景光、眼神光、实景光
- 光质：硬光、软光、漫反射、聚光、自然窗光、霓虹光、烛光、手机屏幕光
- 光位：顺光、侧光、逆光、顶光、底光、侧逆光、剪影
- 影调：高调、低调、高反差、低反差、明暗对比、黑位控制
- 色温：暖光、冷光、冷暖对比、日光、月光、钨丝灯、荧光灯
- 情绪风格：悬疑低调光、甜宠柔光、豪门冷暖对比、复仇强侧光、古风暖烛光
- 时间感：清晨柔光、正午硬光、黄昏金色光、夜晚低照度、雨夜霓虹
- 场景一致性：同一场景内保持主光方向、色温、反差和环境光逻辑一致
```

### 图片提示词知识

```text
- 角色一致性
- 固定服装
- 表情
- 光影
- 主光方向
- 色温
- 影调
- 构图
- 景别
- 机位
- 景深
- 电影感
- 竖屏比例
- 参考图约束
- negative prompt
```

### 视频提示词知识

```text
- 主体运动
- 运镜方向
- 景别变化
- 焦点变化
- 光线变化
- 动作连续性
- 镜头时长
- 情绪变化
- 场景稳定
- 避免画面漂移
- 避免角色外貌变化
```

### 剪辑知识

```text
- 3 秒钩子
- 5-8 秒情绪点
- 卡点字幕
- BGM 转折
- 反转点
- 转场节奏
- 封面标题强化
```

## 多模型路由

短剧工作流需要为每类任务选择合适模型：

```yaml
creative_video:
  planner:
    tasks: [brief, genre, hook, outline]
    model_class: strong_reasoning_text

  screenwriter:
    tasks: [script, dialogue, plot]
    model_class: strong_reasoning_text

  caption_splitter:
    tasks: [sentence_cut, subtitle, pacing]
    model_class: fast_text_or_short_video_text

  storyboard_director:
    tasks: [shot_list, camera, visual_continuity]
    model_class: strong_reasoning_text

  image_generator:
    tasks: [character_image, scene_image, cover_image, keyframe]
    model_class: image_generation

  video_generator:
    tasks: [text_to_video, image_to_video, shot_video]
    model_class: video_generation

  tts:
    tasks: [voiceover, dialogue_audio]
    model_class: tts

  renderer:
    tasks: [compose_mp4, burn_subtitles, mix_audio]
    engine: ffmpeg_or_remotion
```

模型可选范围：

```text
文本：GPT / Claude / DeepSeek / Qwen / Doubao
图片：Seedream / GPT Image / Flux / Midjourney 类服务
视频：Seedance / Kling / Runway / Pika / 本地视频模型
配音：火山 TTS / ElevenLabs / Azure TTS / 本地 TTS
合成：FFmpeg / Remotion
```

## Prompt Compiler

必须新增提示词编译器，而不是写一套固定提示词。

职责：

```text
统一故事板 Schema
-> 图片模型提示词
-> 视频模型提示词
-> TTS 提示词
-> 字幕提示词
-> 剪辑合成指令
```

原因：

```text
- 不同图片/视频模型对提示词格式敏感
- 统一故事板能保证剧情、角色、镜头的一致性
- 切换模型时只改 adapter，不改工作流
- 失败重试时可以只重编译单个镜头提示词
```

## 生成路线

V1 必须支持双路径，保证即使视频模型不可用也能出成品。

### 路径 A：视频模型增强成片

```text
故事板
-> 关键帧图片
-> 图生视频 / 文生视频
-> 音频与字幕
-> FFmpeg/Remotion 合成
-> final.mp4
```

### 路径 B：保底可发布成片

```text
故事板
-> 角色图 / 场景图 / 关键帧
-> 图片运镜模板
-> 配音
-> 字幕
-> BGM
-> FFmpeg/Remotion 合成
-> final.mp4
```

路径 B 动态效果较弱，但可以保证“第一版稳定出片”。

## 质量控制

V1 必须包含以下质量门：

```text
- 故事板字段完整性检查
- 角色一致性检查
- 场景一致性检查
- 镜头数量与时长检查
- 字幕与台词一致性检查
- 音频时长与视频时长对齐
- 缺失素材检查
- 违规内容初筛
- 单镜头失败重试
- 生成成本上限控制
```

## 实施路线

### Phase 0：需求与接口冻结

```text
- 确认 V1 只做竖屏短剧/短视频
- 确认默认输出 30/60/90 秒
- 确认故事板 Schema
- 确认模型供应商 adapter 边界
- 确认成品包目录结构
```

### Phase 1：短剧制作人 Agent 与故事板核心

```text
- 新增 ShortDramaProducerAgent
- 新增故事板 Pydantic 模型
- 新增短剧工作流模板
- 新增子代理角色定义
- 新增故事板生成与校验
```

### Phase 2：专业知识包与 Prompt Compiler

```text
- 新增剧本知识包
- 新增镜头/运镜知识包
- 新增图片提示词模板
- 新增视频提示词模板
- 新增模型 adapter prompt compiler
```

### Phase 3：素材生成

```text
- 图片生成 adapter
- TTS adapter
- 视频生成 adapter
- 失败重试与单镜头重跑
- assets_manifest.json
```

### Phase 4：剪辑合成

```text
- FFmpeg 或 Remotion 合成器
- 字幕 SRT 生成
- 音频混合
- 封面图生成
- final.mp4 输出
```

### Phase 5：产品化入口

```text
- Web UI 创建任务
- CLI 创建任务
- 任务进度
- 成品下载
- 历史项目复用
- 成本与耗时展示
```

### Phase 6：商业增强

```text
- 批量生成
- 多集连续短剧
- 爆款复刻
- 数字人
- 平台发布文案
- 合规审核
- 团队协作审批
```

## 验收标准

V1 完成时必须能通过以下验收：

```text
输入：
“做一个 60 秒都市反转短剧，女主被误认为普通员工，最后揭露她是集团继承人，抖音风格。”

系统输出：
- final.mp4 存在且可播放
- cover.png 存在
- storyboard.json 包含 3-8 个镜头
- subtitles.srt 与台词一致
- voiceover 文件存在
- script.md 包含完整剧情和台词
- publish_copy.md 包含标题、简介、标签
- assets_manifest.json 记录所有素材来源
```

质量要求：

```text
- 视频比例为 9:16
- 总时长误差不超过目标时长的 15%
- 每个镜头都有镜头目的、景别、运镜、台词或动作
- 失败镜头可单独重试
- 无模型密钥写入产物
- 所有外部模型调用有成本记录和错误记录
```

## 与 X-Agent 内核的关系

该项目不是孤立功能，而是 X-Agent 内核优势样板：

```text
短剧需求
-> 短剧制作人 Agent
-> 子代理团队
-> 多模型路由
-> 专业知识包
-> 故事板中间产物
-> 成品 MP4
```

同样模式后续可复制到：

```text
- 编程 Agent：需求 -> 架构 -> 代码 -> 测试 -> PR
- 电商 Agent：商品 -> 卖点 -> 图片 -> 视频 -> 详情页
- 教育 Agent：课程 -> 讲稿 -> PPT -> 视频 -> 题库
- 企业流程 Agent：表单 -> 审批 -> 数据 -> 报表 -> 自动执行
```

因此 Creative Studio 应作为 X-Agent “专业角色智能体 + 子代理团队 + 多模型路由 + 成品交付”的第一个商业样板工程。
