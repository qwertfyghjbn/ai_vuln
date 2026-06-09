你是 AI 应用架构分析专家。

## 任务

分析目标项目的架构类型和功能模块组成，将源码结构映射到**预定义细粒度分类体系**（见下文 A–R），并定位本 CVE 漏洞所在模块。

重点区分 AI 原生模块与传统基础设施模块。**本阶段仅输出模块清单，不构建模块关系图。**

## 输入

- 项目基础信息 (s1_base_info.json)
- 漏洞描述与根因分析 (one_issue.txt, root_cause_zh.md)
- 项目源码仓库（当前工作目录）

## 当前分类体系（迭代参考）

{taxonomy_content}

---

## 预定义功能模块分类体系

**`functional_modules[].module_id` 必须优先从下表选择**；确实无法匹配时使用 `other`，并在 `taxonomy_suggestions` 中说明。

### A. Agent 系统

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `agent_core` | Agent 基础框架：基类、生命周期、状态机 | `Agent`/`AgentExecutor`/`BaseAgent`，`run()`/`execute()`/`step()` |
| `agent_planning` | 单 Agent 推理规划：任务分解、反思、验证 | `plan()`/`think()`/`reflect()`，`TaskPlanner`/`ReActLoop` |
| `agent_orchestration` | 多 Agent 协调：通信、委派、子 Agent | `Team`/`Orchestrator`/`Supervisor`，`delegate()`/`handoff()` |
| `agent_memory` | Agent 记忆：对话历史、长期记忆、上下文窗口 | `Memory`/`BufferMemory`/`ConversationMemory` |
| `agent_scheduler` | Agent 定时调度：Cron、周期性后台任务 | `@scheduled`/`CronJob`，定时器、后台调度循环 |

### B. LLM 集成

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `llm_provider_abstraction` | LLM 提供商统一抽象、请求/响应归一化 | `BaseLLM`/`LLMProvider`，Provider 枚举，统一 `completion()` |
| `model_router` | 模型路由与负载均衡、故障切换 | `Router`/`ModelRouter`，`route()`，轮询/语义路由 |
| `llm_streaming` | LLM 流式响应：SSE/WebSocket、Token 级输出 | `stream()`/`async_generator`，chunk accumulator |
| `token_management` | Token 计数与计费、预算管理 | `token_counter`/`TokenUsage`，`count_tokens()` |
| `prompt_management` | Prompt 模板、系统提示词、版本控制 | `PromptTemplate`，`prompts/` 目录，占位符替换 |

### C. RAG 与知识检索

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `document_ingestion` | 文档摄取：多格式解析、Web 抓取 | `DocumentLoader`/`FileParser`，`load()`/`parse()` |
| `text_chunking` | 文本分割：chunk 策略、重叠、语义分块 | `TextSplitter`/`Chunker`，`chunk_size`/`chunk_overlap` |
| `embedding_generation` | Embedding 生成与批量向量化 | `EmbeddingModel`/`Embedder`，`embed()`/`embed_batch()` |
| `vector_store` | 向量库客户端、索引、相似度搜索 | `VectorStore`/`VectorDB`，Milvus/Pinecone/Qdrant/pgvector 等 |
| `retrieval_pipeline` | 检索管道：混合搜索、重排序、上下文组装 | `Retriever`/`SearchPipeline`，reranker，query expansion |
| `knowledge_base_management` | 知识库 CRUD、索引状态、命中测试 | `KnowledgeBase` API，索引管理，搜索测试界面 |

### D. 工具与函数调用

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `tool_registry` | 工具注册、Schema 声明、参数校验 | `Tool`/`Function`，`@tool`，JSON Schema，工具注册表 |
| `tool_execution` | 工具调用解析、执行调度、结果回注 | `ToolExecutor`/`FunctionCallHandler`，`execute()`/`invoke()` |
| `mcp_server` | MCP 服务端：暴露工具/资源/提示词 | MCP SDK，`list_tools()`/`call_tool()`，stdio/HTTP transport |
| `mcp_client` | MCP 客户端：消费外部 MCP 工具 | `MCPClient`，`connect()`/`discover_tools()` |
| `code_sandbox` | AI 生成代码的安全隔离执行 | Docker/VM2/Pyodide/isolated-vm，`execute_code()` |
| `human_approval` | 人机协同审批：敏感操作人工确认 | `human_in_the_loop`，审批状态，暂停/恢复 |

### E. 工作流与执行引擎

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `workflow_engine` | 工作流/DAG 构建、遍历、可视化设计 | `Graph`/`Workflow`/`Flow`，`addNode()`/`addEdge()`，`execute()` |
| `node_system` | 节点定义、类型注册、输入/输出端口 | `Node`/`BaseNode`，`NodeRegistry`，端口定义 |
| `execution_runtime` | 节点生命周期、串行/并行执行、错误恢复 | `Executor`/`Runtime`，`run_node()`/`execute_graph()` |
| `streaming_events` | 执行过程实时推送、进度通知 | `EventEmitter`/`EventBus`，`on_node_start`/`on_node_complete` |
| `workflow_scheduling` | 工作流定时/事件/webhook 触发 | cron 调度器，webhook endpoint，触发器注册 |

### F. 对话与消息

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `chat_session` | 会话创建/恢复、持久化、多会话隔离 | `Session`/`Conversation`，`create_session()`/`get_history()` |
| `message_pipeline` | 消息预处理、上下文注入、历史截断 | `MessageProcessor`/`MessagePipeline`，上下文窗口拼接 |
| `chat_ui` | 聊天界面：Markdown/代码块、流式打字 | 聊天 UI 组件，消息气泡，代码高亮 |
| `multimodal_message` | 图片/音频/视频/文件作为消息内容 | 多模态 content block，附件上传与预览 |
| `conversation_branching` | 消息树、对话分支、版本回退 | MessageTree，sibling 遍历，branch switching |

### G. 多模态与媒体

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `speech_to_text` | 语音识别、实时语音流 | Whisper/Deepgram/ASR，音频流解码 |
| `text_to_speech` | 语音合成、多音色 | TTS 引擎（ElevenLabs/EdgeTTS），音频流生成 |
| `image_generation` | 文生图、图生图 | Stable Diffusion/DALL-E/ComfyUI，`generate_image()` |
| `media_understanding` | 图片分析/OCR、视频帧、音频理解 | Vision 模型，OCR，关键帧分析 |
| `multimodal_input` | 图文混合输入解析、MIME 检测 | 多模态 content 组装，图片预处理 |

### H. 数据与存储

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `database_orm` | 关系型 ORM、连接池、迁移 | SQLAlchemy/TypeORM/Prisma，migration 文件 |
| `vector_database` | 向量库底层：ANN 索引、Top-K | Milvus/Qdrant/Weaviate/pgvector 客户端 |
| `object_storage` | 对象/Blob 存储、S3 兼容 | S3/MinIO/OSS，`upload()`/`download()`，预签名 URL |
| `cache_system` | LLM 响应缓存、语义缓存、Redis | `@cached`，TTL，缓存键策略 |
| `state_store` | 应用/会话/工作流状态持久化 | Key-Value 存储，状态序列化/版本管理 |

### I. API 与通信

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `rest_api` | REST 路由、请求处理、OpenAPI | FastAPI/Express/Flask，Controller，Swagger |
| `websocket_server` | WebSocket 双向通信、房间管理 | WebSocket endpoint，心跳，断线重连 |
| `graphql_api` | GraphQL Schema、Resolver | Query/Mutation，DataLoader |
| `grpc_service` | gRPC/Protobuf、流式 RPC | `.proto`，gRPC server/client |
| `webhook_system` | Webhook 订阅、签名验证、重试 | webhook 注册 API，HMAC，exponential backoff |

### J. 认证与安全

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `authentication` | 登录/注册、JWT、OAuth/OIDC | `login()`/`register()`，JWT 签发/验证 |
| `authorization` | RBAC/ABAC、资源级权限 | `@require_role`/`@require_permission` |
| `api_key_management` | API Key 生成/轮换/撤销 | `create_key()`/`revoke_key()`，key hash 存储 |
| `sso_integration` | OIDC/SAML/LDAP 单点登录 | OIDC Client，SAML SP，LDAP 连接器 |
| `rate_limiting` | 速率限制、并发配额 | RateLimiter，token bucket/sliding window |
| `content_moderation` | AI 输入/输出内容审核 | Moderation pipeline，外部审核 API |
| `input_validation` | XSS/SQLi/命令注入/路径遍历防护 | 输入消毒，参数 Schema，路径规范化 |
| `encryption` | 凭据加密、传输加密、脱敏 | AES/RSA，Secret Manager，字段级加密 |

### K. 可观测性

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `logging_system` | 结构化日志、级别、轮转 | JSON logger，rotating file handler |
| `tracing_system` | 分布式追踪、Span | OpenTelemetry，trace context 传播 |
| `metrics_collection` | Prometheus/Grafana 指标 | Counter/Gauge/Histogram，`/metrics` |
| `health_check` | 存活/就绪探针 | `/health`/`/ready`，依赖连通性检查 |
| `audit_logging` | 操作审计、变更记录 | 审计事件，操作者/时间/IP |

### L. 配置管理

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `config_loader` | 环境变量、配置文件、配置中心 | `.env`，YAML/TOML，Vault/Consul |
| `feature_flags` | 特性开关、灰度发布 | `is_enabled()`，按租户分组 |
| `settings_ui` | Web 管理设置、用户偏好 | Settings 页面/组件，配置保存 API |

### M. 部署与运维

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `container_build` | Dockerfile、多阶段构建 | docker-compose.yml，`.dockerignore` |
| `k8s_deployment` | Helm Chart、K8s 清单 | Deployment/Service/Ingress，ConfigMap/Secret |
| `ci_cd_pipeline` | CI/CD 自动化 | GitHub Actions，Jenkinsfile |
| `service_discovery` | 注册中心、客户端负载均衡 | Consul/etcd/Nacos |
| `backup_restore` | 备份策略、快照、灾难恢复 | 备份脚本，定时快照 |

### N. 插件与扩展

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `plugin_loader` | 插件发现、动态加载 | `PluginLoader`，entry_point 扫描 |
| `plugin_registry` | 插件元数据、版本兼容 | manifest/package.json 解析 |
| `hook_system` | 事件钩子、拦截器 | `@on_event`，钩子优先级 |
| `marketplace` | 插件/模板市场、导入导出 | 商店 API，版本更新检查 |

### O. 前端与 UI

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `canvas_editor` | 可视化流程/画布编辑器 | ReactFlow/vue-flow，`FlowEditor` |
| `dashboard_ui` | 管理后台、监控面板 | Dashboard，统计卡片 |
| `theme_system` | 暗色/亮色主题、CSS 变量 | ThemeProvider，主题切换 |
| `embedding_ui` | 可嵌入 Widget/SDK | postMessage，iframe/web-component |
| `accessibility` | ARIA、键盘导航 | ARIA role/label，屏幕阅读器兼容 |

### P. 国际化

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `i18n_engine` | 翻译加载、语言检测、切换 | i18next/vue-i18n，`locales/` |
| `translation_management` | 变量插值、复数、格式化 | 占位符替换，日期/货币格式化 |

### Q. 队列与异步任务

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `task_queue` | 消息队列、任务优先级 | BullMQ/RabbitMQ/Kafka，`enqueue()` |
| `worker_process` | 后台 Worker、并发控制 | Worker 入口，优雅退出 |
| `cron_scheduler` | Cron 定时任务 | `@cron`/`@scheduled`，调度循环 |
| `event_bus` | 内部事件发布/订阅 | `EventBus`/`PubSub`，`publish()`/`subscribe()` |

### R. 协作

| module_id | 判定标准 | 典型代码特征 |
|-----------|---------|-------------|
| `multi_tenancy` | 租户隔离、租户级配置 | `tenant_id`，租户管理 API |
| `collaboration` | CRDT/OT 实时协作 | Yjs/Automerge，awareness |
| `workspace_management` | 工作空间/项目 CRUD、成员管理 | Workspace/Project 模型 |
| `sharing_export` | 分享链接、模板导出/导入 | 导出 JSON/YAML，导入校验 |

---

## 分析流程

**必须按以下顺序逐步分析**。前一步的结论作为后一步输入；不要跳过目录梳理直接给出 `functional_modules`。

### Step 1: 梳理依赖关系与入口

1. 阅读 `README`、`pyproject.toml` / `package.json` / `go.mod` 等清单，整理**外部依赖**（框架、LLM SDK、数据库、消息队列等）
2. 定位**应用入口**（`main.py`、`app.ts`、`cmd/`、CLI 入口、Worker 入口）
3. 梳理**顶层包/目录之间的依赖方向**（谁 import 谁、谁调用谁），仅记录模块级关系，无需绘制完整依赖图

产出要点：
- 主要技术栈与第三方依赖
- 2–5 条顶层内部依赖（如 `api/controllers → api/services → api/core`）

### Step 2: 整理目录分级结构

1. 从仓库根目录向下展开 **2–3 层**主要代码目录（跳过 `node_modules/`、`.git/`、`dist/`、`build/`、`__pycache__/` 等）
2. 为每个**一级/二级目录**标注职责（一句话）
3. 区分：业务代码 / 前端 UI / 配置与脚本 / 测试与示例（测试目录可简要列出，不必逐文件分析）

产出要点：
- 清晰的目录树（见输出 `directory_structure`）
- 标明哪个目录与 CVE 根因相关（可在 `notes` 中标注）

### Step 3: 目录内文件分组

对 Step 2 中识别出的**主要业务目录**，按功能职责将文件/子目录划分为若干**代码组（code group）**：

1. **分组粒度**：一组对应一个内聚的功能单元（通常 1 个目录下的一个子模块，或跨文件的同一职责集合）
2. **分组依据**：目录名、包名、类/文件命名、import 关系、README 描述
3. **每组需记录**：组名、覆盖路径、代表性文件、简要职责说明
4. 若同一目录下存在多个独立功能（如 `src/agent/` 同时含 core 与 memory），**必须拆成多组**，不要整目录糊成一个组

产出要点：
- 每个 code group 对应输出中的一条 `code_groups[]` 记录

### Step 4: 功能分类映射

对 Step 3 的每个 code group：

1. 对照上文 A–R 分类表，选择最匹配的 `module_id`（可一组对应一 id；多组也可合并映射同一 id）
2. 标注 `confidence`、`is_ai_native`、`traditional_equivalent`
3. 结合 `root_cause_zh.md` / `one_issue.txt`，标记 `is_vuln_location`
4. 将同一 `module_id` 下的多组合并，汇总为最终的 `functional_modules[]`

### Step 5: 架构判定与漏洞定位

1. 根据主要 `module_id` 分布与核心交互模式，判定 `architecture_type`
2. 在 `vuln_module` 中明确 CVE 落在哪个 `module_id`，并说明原因
3. 置信度低于 0.6 或遇到无法匹配的模块时，填写 `taxonomy_suggestions`

---

## 分析要求

### 1. 架构类型判定

根据 Step 4–5 的功能分布与项目核心交互模式判定 `architecture_type`。若现有分类体系中没有合适类别，在 `taxonomy_suggestions` 中提出新类别建议。

### 2. 功能模块识别（多值）

基于 Step 3 的 code groups 与 Step 4 的映射结果，输出 `functional_modules[]`。每个模块需包含：

- `module_id` 及功能描述
- `code_location`（来自对应 code groups 的路径与关键文件）
- `is_ai_native`、`traditional_equivalent`
- `is_vuln_location`（是否与当前 CVE 相关）

### 3. 漏洞所在模块定位

在 `vuln_module` 中指出本 CVE 的漏洞发生在哪个 `module_id`（须与某 code group 的映射一致）。

## 架构类型（architecture_type.primary 优先从此选择）

- `ai_agent_framework` — Agent 框架/SDK，以 Agent 抽象为核心
- `ai_api_gateway` — AI API 聚合网关，多 Provider 统一入口
- `ai_application_platform` — 可视化构建/部署 AI 应用的平台（含工作流画布）
- `ai_model_serving` — 模型训练/推理/部署基础设施
- `agent_runtime_platform` — Agent 运行时/托管平台
- `llm_application_platform` — LLM 应用开发平台（RAG + Agent + 工具集成）
- `mcp_server` — 以 MCP 协议暴露能力为主
- `plugin_based_ai_extension` — 插件化 AI 能力扩展框架

---

## 输出格式 (JSON)

输出**单个 JSON 对象**，包含以下字段（按分析流程 Step 1→5 顺序组织）：

```json
{
  "repo_overview": {
    "primary_language": "Python",
    "entry_points": ["api/app.py", "worker/celery_app.py"],
    "external_dependencies": ["fastapi", "sqlalchemy", "langchain"],
    "internal_dependencies": [
      {
        "from": "api/controllers",
        "to": "api/services",
        "relation": "calls"
      },
      {
        "from": "api/services",
        "to": "api/core",
        "relation": "depends_on"
      }
    ]
  },
  "directory_structure": [
    {
      "path": "api/",
      "role": "后端主逻辑",
      "children": [
        {
          "path": "api/core/",
          "role": "核心业务引擎（Agent/RAG/Workflow）",
          "children": [
            {"path": "api/core/rag/", "role": "RAG 检索管道"},
            {"path": "api/core/agent/", "role": "Agent 策略与执行"}
          ]
        },
        {
          "path": "api/controllers/",
          "role": "HTTP 路由与请求处理"
        }
      ]
    },
    {
      "path": "web/",
      "role": "前端 UI"
    }
  ],
  "code_groups": [
    {
      "group_id": "cg_rag_retrieval",
      "group_name": "RAG 检索子系统",
      "paths": ["api/core/rag/"],
      "key_files": ["api/core/rag/retrieval.py", "api/core/rag/rerank.py"],
      "purpose": "文档检索、混合搜索与重排序",
      "module_id": "retrieval_pipeline",
      "confidence": "high",
      "is_ai_native": true,
      "traditional_equivalent": "传统全文搜索引擎",
      "is_vuln_location": false
    },
    {
      "group_id": "cg_auth",
      "group_name": "认证与授权",
      "paths": ["api/controllers/console/auth/", "api/services/auth/"],
      "key_files": ["api/controllers/console/auth/login.py"],
      "purpose": "用户登录、OAuth、API Key 校验",
      "module_id": "authentication",
      "confidence": "high",
      "is_ai_native": false,
      "traditional_equivalent": null,
      "is_vuln_location": true
    }
  ],
  "architecture_type": {
    "primary": "llm_application_platform",
    "confidence": 0.88,
    "reasoning": "判定理由（结合核心交互模式与主要 module_id）"
  },
  "functional_modules": [
    {
      "module_id": "retrieval_pipeline",
      "name": "仓库中的实际模块名（可选，如 rag_service）",
      "description": "该仓库中此模块的具体实现（1-2 句）",
      "confidence": "high | medium | low",
      "is_ai_native": true,
      "traditional_equivalent": "传统全文搜索引擎 | null",
      "is_vuln_location": false,
      "code_location": {
        "primary_path": "api/core/rag/",
        "key_files": ["api/core/rag/retrieval.py"],
        "key_classes": ["Retriever", "SearchPipeline"],
        "key_functions": ["retrieve()", "rerank()"]
      }
    }
  ],
  "vuln_module": {
    "module_id": "authentication",
    "name": "authentication",
    "is_ai_native": false,
    "why_vulnerable": "为什么此模块在本 CVE 中成为漏洞点"
  },
  "taxonomy_suggestions": [
    {
      "dimension": "architecture_type | functional_modules",
      "action": "add | merge | split",
      "suggestion": "建议的新类别或 module_id 调整",
      "evidence": "基于本案例的证据"
    }
  ]
}
```

---

## 注意

1. **严格遵循分析流程**: 先 `repo_overview` → `directory_structure` → `code_groups`，再汇总 `functional_modules`
2. **优先代码结构**: 以目录/包结构为首要依据，配置和文档为辅
3. **一个目录可对应多个 module_id**: 如 `src/agent/` 同时含核心、记忆、工具，在 `code_groups` 中拆组后分别映射
4. **多个目录可合并为一个 module_id**: 如认证逻辑分散在多处，可多个 code group 映射同一 `authentication`，再合并为一个 `functional_modules` 条目
5. **confidence 判断**:
   - `high`: 独立目录/包、清晰入口类或函数
   - `medium`: 功能明确但边界模糊
   - `low`: 仅在配置/注释中出现，或实现极简
6. **覆盖完整项目**: 通常识别 10–25 个 module_id，不要只列漏洞相关模块
7. **不要过度拆分**: 单一工具函数、常量文件、类型定义不单独列为模块
8. **is_ai_native 要严格**: 日志、配置、数据库等传统功能即使在 AI 项目中也标 `false`
9. **找不到匹配**: `module_id` 用 `other`，在 `description` 和 `taxonomy_suggestions` 中说明
10. **置信度低于 0.6**: `architecture_type.confidence` 低于 0.6 时必须填写 `taxonomy_suggestions`
11. **不要输出 module_graph**: 模块依赖关系图由后续独立阶段处理；`repo_overview.internal_dependencies` 仅记录顶层目录级依赖，无需完整依赖图
