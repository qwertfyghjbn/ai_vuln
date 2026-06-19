# AI-VulnAtlas 基于 SDK Agent 的两人分工单

基于当前仓库实际任务数据生成。

- 统计时间：2026-06-19
- 统计口径：使用 [task_loader.py](../task_loader.py) 从 `vuln-analyzed-0605.xlsx` 实际加载任务
- 总任务数：3365
- 总项目数：185
- 分工目标：按 **task 数尽量均衡** 切分为 2 组，同时遵守“按 `project` 分工、同一项目不拆给两人”的约束
- 运行模式：`--analysis-mode agent --agent-backend claude_agent_sdk`

本次切分结果：

- A 组：1683 条任务，91 个项目
- B 组：1682 条任务，94 个项目

---

## 1. 执行原则

必须遵守：

1. 每个人使用 **独立 workspace**
2. 每个人只处理自己负责的 `project`
3. 不允许两个人同时处理同一个 `project`
4. 不允许两个人在同一个工作目录同时执行 `python3 main.py run`
5. 每个 workspace 只启动 **一个** 长时间运行的 `run` 进程，充分利用项目内部的 `--max-workers`
6. 每个人先做小批量 SDK 冒烟，再扩大到全量
7. 每个人本地批量跑完后都执行：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

8. 最终总统计以合并后的总目录再次执行 `rebuild-summary` 为准

---

## 2. 并行使用策略

本项目当前已经支持：

- `--project-list`
- `--max-workers`
- 同 `project` 串行、不同 `project` 并行

因此两人协作的推荐方式不是“每个人再手动拆很多小命令”，而是：

1. 每人负责一组固定 `project`
2. 每个 workspace 内只跑一个主命令
3. 主命令通过 `--project-list` 锁定自己负责的项目
4. 主命令通过 `--max-workers` 自动并行不同项目的任务

### 推荐并行参数

建议分两阶段：

### 阶段 1：冒烟

```bash
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project-list <PROJECT_LIST> --max-workers 2 --max 10
```

目的：

1. 验证 SDK backend 当前环境可用
2. 验证 step 文件能真实写出
3. 验证 `agent_trace`、`summary`、`audit-output` 不出现系统性问题

### 阶段 2：批量

推荐默认值：

```bash
--max-workers 6
```

如果机器资源、Anthropic 额度或 SDK 稳定性不足，则降级为：

```bash
--max-workers 4
```

不建议一开始就高于 6，因为：

1. SDK backend 本身仍有较高外部依赖
2. 真实瓶颈通常是远程推理与仓库 I/O，不是本地 CPU
3. 两个人同时运行时，总并发会放大到 8 到 12 个 worker

---

## 3. Workspace 约定

建议目录：

- A：`/home/lqs/ai_vuln_sdk_worker_a`
- B：`/home/lqs/ai_vuln_sdk_worker_b`

每个人执行前，确保自己的目录中已具备：

1. 当前代码
2. `vuln-analyzed-0605.xlsx`
3. `ai-vulns-timeline.zip` 或 `data/ai-vulns-timeline/`
4. 正确的 `.env`
5. 可用的 SDK backend 依赖与认证环境

建议执行一次最小检查：

```bash
python3 - <<'PY'
import importlib.util
print("claude_agent_sdk:", bool(importlib.util.find_spec("claude_agent_sdk")))
PY
```

---

## 4. 统一执行模板

每个人都按同样流程执行，只是 `--project-list` 不同。

### 4.1 预检查

```bash
python3 main.py preflight
```

### 4.2 SDK 冒烟

```bash
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project-list <PROJECT_LIST> --max-workers 2 --max 10
python3 main.py rebuild-summary
python3 main.py audit-output
```

### 4.3 全量批量

```bash
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project-list <PROJECT_LIST> --max-workers 6
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

### 4.4 强制重跑

```bash
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project-list <PROJECT_LIST> --max-workers 6 --force
```

### 4.5 单条补跑

```bash
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project <PROJECT> --id <ID> --force
```

---

## 5. A 组分工单

- 负责人：A
- Workspace：`/home/lqs/ai_vuln_sdk_worker_a`
- 任务数：1683
- 项目数：91
- 推荐并行参数：`--max-workers 6`

### A 组项目清单

| Project | Tasks |
|---|---:|
| openclaw_openclaw | 971 |
| mlflow_mlflow | 59 |
| gradio-app_gradio | 57 |
| langchain-ai_langchain | 47 |
| jeecgboot_JeecgBoot | 41 |
| Budibase_budibase | 31 |
| anthropics_claude-code | 27 |
| Significant-Gravitas_AutoGPT | 26 |
| ollama_ollama | 24 |
| mindsdb_mindsdb | 23 |
| danny-avila_LibreChat | 22 |
| argoproj_argo-workflows | 20 |
| TransformerOptimus_SuperAGI | 17 |
| cvat-ai_cvat | 17 |
| chartbrew_chartbrew | 15 |
| bentoml_BentoML | 14 |
| casdoor_casdoor | 13 |
| nltk_nltk | 13 |
| gitroomhq_postiz-app | 12 |
| oobabooga_textgen | 12 |
| Tencent_WeKnora | 11 |
| dataease_SQLBot | 10 |
| ray-project_ray | 10 |
| QuantumNous_new-api | 9 |
| ChatGPTNextWeb_NextChat | 8 |
| PrefectHQ_fastmcp | 8 |
| jupyterhub_jupyterhub | 8 |
| mlaify_OpenSift | 7 |
| pinchtab_pinchtab | 7 |
| eosphoros-ai_DB-GPT | 6 |
| langfuse_langfuse | 6 |
| qhkm_zeptoclaw | 6 |
| windmill-labs_windmill | 6 |
| cube-js_cube | 5 |
| kestra-io_kestra | 5 |
| nanbingxyz_5ire | 5 |
| succinctlabs_sp1 | 5 |
| Bytedesk_bytedesk | 4 |
| Flux159_mcp-server-kubernetes | 4 |
| HKUDS_nanobot | 4 |
| elinsky_execution-system-mcp | 4 |
| langchain-ai_langsmith-sdk | 4 |
| promtengineer_localgpt | 4 |
| zhayujie_CowAgent | 4 |
| HBAI-Ltd_Toonflow-app | 3 |
| NVIDIA-Merlin_Transformers4Rec | 3 |
| alexei-led_aws-mcp-server | 3 |
| langchain-ai_langchainjs | 3 |
| openai_codex | 3 |
| CodeWithCJ_SparkyFitness | 2 |
| Comfy-Org_ComfyUI-Manager | 2 |
| Mindinventory_MindSQL | 2 |
| SepineTam_stata-mcp | 2 |
| Upsonic_Upsonic | 2 |
| aliasrobotics_cai | 2 |
| docker_model-runner | 2 |
| efforthye_fast-filesystem-mcp | 2 |
| github_copilot-cli | 2 |
| lintsinghua_DeepAudit | 2 |
| marimo-team_marimo | 2 |
| mobile-next_mobile-mcp | 2 |
| neo4j-contrib_mcp-neo4j | 2 |
| sooperset_mcp-atlassian | 2 |
| unstructured-IO_unstructured | 2 |
| 0xKoda_WireMCP | 1 |
| DayuanJiang_next-ai-draw-io | 1 |
| Deepractice_PromptX | 1 |
| Josh-XT_AGiXT | 1 |
| OpenHands_OpenHands | 1 |
| Tencent-Hunyuan_Hunyuan3D-1 | 1 |
| Tencent-Hunyuan_HunyuanVideo | 1 |
| Tencent_AI-Infra-Guard | 1 |
| Tencent_MimicMotion | 1 |
| VectorSpaceLab_OmniGen2 | 1 |
| agent0ai_agent-zero | 1 |
| agentgateway_agentgateway | 1 |
| aws-solutions_qnabot-on-aws | 1 |
| chatboxai_chatbox | 1 |
| cisco-ai-defense_skill-scanner | 1 |
| cocoindex-io_cocoindex | 1 |
| crawlchat_crawlchat | 1 |
| google_sentencepiece | 1 |
| hyperterse_hyperterse | 1 |
| kubeai-project_kubeai | 1 |
| langchain-ai_langgraphjs | 1 |
| modelcontextprotocol_ruby-sdk | 1 |
| openlit_openlit | 1 |
| pgvector_pgvector | 1 |
| rowboatlabs_rowboat | 1 |
| smythOS_sre | 1 |
| yangjian102621_geekai | 1 |

### A 组 `--project-list`

```text
openclaw_openclaw,mlflow_mlflow,gradio-app_gradio,langchain-ai_langchain,jeecgboot_JeecgBoot,Budibase_budibase,anthropics_claude-code,Significant-Gravitas_AutoGPT,ollama_ollama,mindsdb_mindsdb,danny-avila_LibreChat,argoproj_argo-workflows,TransformerOptimus_SuperAGI,cvat-ai_cvat,chartbrew_chartbrew,bentoml_BentoML,casdoor_casdoor,nltk_nltk,gitroomhq_postiz-app,oobabooga_textgen,Tencent_WeKnora,dataease_SQLBot,ray-project_ray,QuantumNous_new-api,ChatGPTNextWeb_NextChat,PrefectHQ_fastmcp,jupyterhub_jupyterhub,mlaify_OpenSift,pinchtab_pinchtab,eosphoros-ai_DB-GPT,langfuse_langfuse,qhkm_zeptoclaw,windmill-labs_windmill,cube-js_cube,kestra-io_kestra,nanbingxyz_5ire,succinctlabs_sp1,Bytedesk_bytedesk,Flux159_mcp-server-kubernetes,HKUDS_nanobot,elinsky_execution-system-mcp,langchain-ai_langsmith-sdk,promtengineer_localgpt,zhayujie_CowAgent,HBAI-Ltd_Toonflow-app,NVIDIA-Merlin_Transformers4Rec,alexei-led_aws-mcp-server,langchain-ai_langchainjs,openai_codex,CodeWithCJ_SparkyFitness,Comfy-Org_ComfyUI-Manager,Mindinventory_MindSQL,SepineTam_stata-mcp,Upsonic_Upsonic,aliasrobotics_cai,docker_model-runner,efforthye_fast-filesystem-mcp,github_copilot-cli,lintsinghua_DeepAudit,marimo-team_marimo,mobile-next_mobile-mcp,neo4j-contrib_mcp-neo4j,sooperset_mcp-atlassian,unstructured-IO_unstructured,0xKoda_WireMCP,DayuanJiang_next-ai-draw-io,Deepractice_PromptX,Josh-XT_AGiXT,OpenHands_OpenHands,Tencent-Hunyuan_Hunyuan3D-1,Tencent-Hunyuan_HunyuanVideo,Tencent_AI-Infra-Guard,Tencent_MimicMotion,VectorSpaceLab_OmniGen2,agent0ai_agent-zero,agentgateway_agentgateway,aws-solutions_qnabot-on-aws,chatboxai_chatbox,cisco-ai-defense_skill-scanner,cocoindex-io_cocoindex,crawlchat_crawlchat,google_sentencepiece,hyperterse_hyperterse,kubeai-project_kubeai,langchain-ai_langgraphjs,modelcontextprotocol_ruby-sdk,openlit_openlit,pgvector_pgvector,rowboatlabs_rowboat,smythOS_sre,yangjian102621_geekai
```

### A 组执行命令

```bash
cd /home/lqs/ai_vuln_sdk_worker_a
python3 main.py preflight
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project-list openclaw_openclaw,mlflow_mlflow,gradio-app_gradio,langchain-ai_langchain,jeecgboot_JeecgBoot,Budibase_budibase,anthropics_claude-code,Significant-Gravitas_AutoGPT,ollama_ollama,mindsdb_mindsdb,danny-avila_LibreChat,argoproj_argo-workflows,TransformerOptimus_SuperAGI,cvat-ai_cvat,chartbrew_chartbrew,bentoml_BentoML,casdoor_casdoor,nltk_nltk,gitroomhq_postiz-app,oobabooga_textgen,Tencent_WeKnora,dataease_SQLBot,ray-project_ray,QuantumNous_new-api,ChatGPTNextWeb_NextChat,PrefectHQ_fastmcp,jupyterhub_jupyterhub,mlaify_OpenSift,pinchtab_pinchtab,eosphoros-ai_DB-GPT,langfuse_langfuse,qhkm_zeptoclaw,windmill-labs_windmill,cube-js_cube,kestra-io_kestra,nanbingxyz_5ire,succinctlabs_sp1,Bytedesk_bytedesk,Flux159_mcp-server-kubernetes,HKUDS_nanobot,elinsky_execution-system-mcp,langchain-ai_langsmith-sdk,promtengineer_localgpt,zhayujie_CowAgent,HBAI-Ltd_Toonflow-app,NVIDIA-Merlin_Transformers4Rec,alexei-led_aws-mcp-server,langchain-ai_langchainjs,openai_codex,CodeWithCJ_SparkyFitness,Comfy-Org_ComfyUI-Manager,Mindinventory_MindSQL,SepineTam_stata-mcp,Upsonic_Upsonic,aliasrobotics_cai,docker_model-runner,efforthye_fast-filesystem-mcp,github_copilot-cli,lintsinghua_DeepAudit,marimo-team_marimo,mobile-next_mobile-mcp,neo4j-contrib_mcp-neo4j,sooperset_mcp-atlassian,unstructured-IO_unstructured,0xKoda_WireMCP,DayuanJiang_next-ai-draw-io,Deepractice_PromptX,Josh-XT_AGiXT,OpenHands_OpenHands,Tencent-Hunyuan_Hunyuan3D-1,Tencent-Hunyuan_HunyuanVideo,Tencent_AI-Infra-Guard,Tencent_MimicMotion,VectorSpaceLab_OmniGen2,agent0ai_agent-zero,agentgateway_agentgateway,aws-solutions_qnabot-on-aws,chatboxai_chatbox,cisco-ai-defense_skill-scanner,cocoindex-io_cocoindex,crawlchat_crawlchat,google_sentencepiece,hyperterse_hyperterse,kubeai-project_kubeai,langchain-ai_langgraphjs,modelcontextprotocol_ruby-sdk,openlit_openlit,pgvector_pgvector,rowboatlabs_rowboat,smythOS_sre,yangjian102621_geekai --max-workers 6
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

---

## 6. B 组分工单

- 负责人：B
- Workspace：`/home/lqs/ai_vuln_sdk_worker_b`
- 任务数：1682
- 项目数：94
- 推荐并行参数：`--max-workers 6`

### B 组项目清单

| Project | Tasks |
|---|---:|
| tensorflow_tensorflow | 431 |
| discourse_discourse | 268 |
| FlowiseAI_Flowise | 92 |
| n8n-io_n8n | 87 |
| MervinPraison_PraisonAI | 84 |
| open-webui_open-webui | 81 |
| RocketChat_Rocket.Chat | 54 |
| vllm-project_vllm | 45 |
| langflow-ai_langflow | 37 |
| langgenius_dify | 28 |
| Oneflow-Inc_oneflow | 26 |
| outline_outline | 26 |
| Mintplex-Labs_anything-llm | 23 |
| labring_FastGPT | 23 |
| openfga_openfga | 23 |
| ggml-org_llama.cpp | 19 |
| huggingface_transformers | 18 |
| vanna-ai_vanna | 17 |
| keras-team_keras | 15 |
| Foundationagents_MetaGPT | 13 |
| HumanSignal_label-studio | 13 |
| lobehub_lobehub | 13 |
| SillyTavern_SillyTavern | 12 |
| infiniflow_ragflow | 12 |
| BerriAI_litellm | 11 |
| flipped-aurora_gin-vue-admin | 11 |
| AstrBotDevs_AstrBot | 9 |
| HKUDS_OpenHarness | 9 |
| czlonkowski_n8n-mcp | 9 |
| binary-husky_gpt_academic | 8 |
| samsung_ONE | 8 |
| nocobase_nocobase | 7 |
| InternLM_lmdeploy | 6 |
| OpenBMB_XAgent | 6 |
| langchain-ai_langgraph | 6 |
| nhost_nhost | 6 |
| sgl-project_sglang | 6 |
| ParisNeo_lollms | 5 |
| f_prompts.chat | 5 |
| mesop-dev_mesop | 5 |
| qdrant_qdrant | 5 |
| volcengine_OpenViking | 5 |
| Giskard-AI_giskard-oss | 4 |
| crewAIInc_crewAI | 4 |
| huggingface_smolagents | 4 |
| letta-ai_letta | 4 |
| streamlit_streamlit | 4 |
| Chainlit_chainlit | 3 |
| Gitlawb_openclaude | 3 |
| HKUDS_LightRAG | 3 |
| agno-agi_agno | 3 |
| bytedance_deer-flow | 3 |
| milvus-io_milvus | 3 |
| wevm_mppx | 3 |
| FedML-AI_FedML | 2 |
| ParisNeo_lollms-webui | 2 |
| Tencent_TFace | 2 |
| Vexa-ai_vexa | 2 |
| coze-dev_coze-studio | 2 |
| doobidoo_mcp-memory-service | 2 |
| eigent-ai_eigent | 2 |
| griptape-ai_griptape | 2 |
| lm-sys_FastChat | 2 |
| microsoft_semantic-kernel | 2 |
| modelcontextprotocol_java-sdk | 2 |
| run-llama_llama_index | 2 |
| toeverything_AFFiNE | 2 |
| zhongyu09_openchatbi | 2 |
| BigSweetPotatoStudio_HyperChat | 1 |
| DeDeveloper23_codebase-mcp | 1 |
| GLips_Figma-Context-MCP | 1 |
| MontFerret_ferret | 1 |
| SylphxAI_filesystem-mcp | 1 |
| Tencent-Hunyuan_HunyuanDiT | 1 |
| TencentCloudBase_CloudBase-MCP | 1 |
| Tencent_MedicalNet | 1 |
| Tencent_PatrickStar | 1 |
| aegra_aegra | 1 |
| agentfront_frontmcp | 1 |
| apconw_Aix-DB | 1 |
| bagofwords1_bagofwords | 1 |
| chattermate_chattermate.chat | 1 |
| cloudflare_agents | 1 |
| cohere-ai_cohere-terrarium | 1 |
| getzep_graphiti | 1 |
| gunthercox_ChatterBot | 1 |
| jackwrichards_FastlyMCP | 1 |
| langchain-ai_helm | 1 |
| londonaicentre_FLIP | 1 |
| openakita_openakita | 1 |
| pab1it0_adx-mcp-server | 1 |
| pipeshub-ai_pipeshub-ai | 1 |
| smn2gnt_MCP-Salesforce | 1 |
| sonirico_mcp-shell | 1 |

### B 组 `--project-list`

```text
tensorflow_tensorflow,discourse_discourse,FlowiseAI_Flowise,n8n-io_n8n,MervinPraison_PraisonAI,open-webui_open-webui,RocketChat_Rocket.Chat,vllm-project_vllm,langflow-ai_langflow,langgenius_dify,Oneflow-Inc_oneflow,outline_outline,Mintplex-Labs_anything-llm,labring_FastGPT,openfga_openfga,ggml-org_llama.cpp,huggingface_transformers,vanna-ai_vanna,keras-team_keras,Foundationagents_MetaGPT,HumanSignal_label-studio,lobehub_lobehub,SillyTavern_SillyTavern,infiniflow_ragflow,BerriAI_litellm,flipped-aurora_gin-vue-admin,AstrBotDevs_AstrBot,HKUDS_OpenHarness,czlonkowski_n8n-mcp,binary-husky_gpt_academic,samsung_ONE,nocobase_nocobase,InternLM_lmdeploy,OpenBMB_XAgent,langchain-ai_langgraph,nhost_nhost,sgl-project_sglang,ParisNeo_lollms,f_prompts.chat,mesop-dev_mesop,qdrant_qdrant,volcengine_OpenViking,Giskard-AI_giskard-oss,crewAIInc_crewAI,huggingface_smolagents,letta-ai_letta,streamlit_streamlit,Chainlit_chainlit,Gitlawb_openclaude,HKUDS_LightRAG,agno-agi_agno,bytedance_deer-flow,milvus-io_milvus,wevm_mppx,FedML-AI_FedML,ParisNeo_lollms-webui,Tencent_TFace,Vexa-ai_vexa,coze-dev_coze-studio,doobidoo_mcp-memory-service,eigent-ai_eigent,griptape-ai_griptape,lm-sys_FastChat,microsoft_semantic-kernel,modelcontextprotocol_java-sdk,run-llama_llama_index,toeverything_AFFiNE,zhongyu09_openchatbi,BigSweetPotatoStudio_HyperChat,DeDeveloper23_codebase-mcp,GLips_Figma-Context-MCP,MontFerret_ferret,SylphxAI_filesystem-mcp,Tencent-Hunyuan_HunyuanDiT,TencentCloudBase_CloudBase-MCP,Tencent_MedicalNet,Tencent_PatrickStar,aegra_aegra,agentfront_frontmcp,apconw_Aix-DB,bagofwords1_bagofwords,chattermate_chattermate.chat,cloudflare_agents,cohere-ai_cohere-terrarium,getzep_graphiti,gunthercox_ChatterBot,jackwrichards_FastlyMCP,langchain-ai_helm,londonaicentre_FLIP,openakita_openakita,pab1it0_adx-mcp-server,pipeshub-ai_pipeshub-ai,smn2gnt_MCP-Salesforce,sonirico_mcp-shell
```

### B 组执行命令

```bash
cd /home/lqs/ai_vuln_sdk_worker_b
python3 main.py preflight
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk --project-list tensorflow_tensorflow,discourse_discourse,FlowiseAI_Flowise,n8n-io_n8n,MervinPraison_PraisonAI,open-webui_open-webui,RocketChat_Rocket.Chat,vllm-project_vllm,langflow-ai_langflow,langgenius_dify,Oneflow-Inc_oneflow,outline_outline,Mintplex-Labs_anything-llm,labring_FastGPT,openfga_openfga,ggml-org_llama.cpp,huggingface_transformers,vanna-ai_vanna,keras-team_keras,Foundationagents_MetaGPT,HumanSignal_label-studio,lobehub_lobehub,SillyTavern_SillyTavern,infiniflow_ragflow,BerriAI_litellm,flipped-aurora_gin-vue-admin,AstrBotDevs_AstrBot,HKUDS_OpenHarness,czlonkowski_n8n-mcp,binary-husky_gpt_academic,samsung_ONE,nocobase_nocobase,InternLM_lmdeploy,OpenBMB_XAgent,langchain-ai_langgraph,nhost_nhost,sgl-project_sglang,ParisNeo_lollms,f_prompts.chat,mesop-dev_mesop,qdrant_qdrant,volcengine_OpenViking,Giskard-AI_giskard-oss,crewAIInc_crewAI,huggingface_smolagents,letta-ai_letta,streamlit_streamlit,Chainlit_chainlit,Gitlawb_openclaude,HKUDS_LightRAG,agno-agi_agno,bytedance_deer-flow,milvus-io_milvus,wevm_mppx,FedML-AI_FedML,ParisNeo_lollms-webui,Tencent_TFace,Vexa-ai_vexa,coze-dev_coze-studio,doobidoo_mcp-memory-service,eigent-ai_eigent,griptape-ai_griptape,lm-sys_FastChat,microsoft_semantic-kernel,modelcontextprotocol_java-sdk,run-llama_llama_index,toeverything_AFFiNE,zhongyu09_openchatbi,BigSweetPotatoStudio_HyperChat,DeDeveloper23_codebase-mcp,GLips_Figma-Context-MCP,MontFerret_ferret,SylphxAI_filesystem-mcp,Tencent-Hunyuan_HunyuanDiT,TencentCloudBase_CloudBase-MCP,Tencent_MedicalNet,Tencent_PatrickStar,aegra_aegra,agentfront_frontmcp,apconw_Aix-DB,bagofwords1_bagofwords,chattermate_chattermate.chat,cloudflare_agents,cohere-ai_cohere-terrarium,getzep_graphiti,gunthercox_ChatterBot,jackwrichards_FastlyMCP,langchain-ai_helm,londonaicentre_FLIP,openakita_openakita,pab1it0_adx-mcp-server,pipeshub-ai_pipeshub-ai,smn2gnt_MCP-Salesforce,sonirico_mcp-shell --max-workers 6
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

---

## 7. 运行节奏建议

为了更好利用并行能力，建议两人统一按这个节奏推进：

1. 先各自执行 `preflight`
2. 各自执行一次 SDK 冒烟：`--max-workers 2 --max 10`
3. 如果冒烟通过，再进入全量批量：`--max-workers 6`
4. 如遇 SDK backend 不稳定、速率限制或外部错误，先降到 `--max-workers 4`
5. 如仍有问题，再按单项目或单条任务补跑

特别说明：

1. A 组虽然有 `openclaw_openclaw` 971 条的大项目，但仍然建议从一开始就与其它项目一起跑，让 `--max-workers` 同时消费其它项目，减少尾部空转
2. 不建议把 `openclaw_openclaw` 单独拆成另一个人，因为这会违反“按 project 不拆分”的约束，也会打乱统计归属

---

## 8. 合并与最终统计

两个人都完成后，再做统一合并。

建议合并后在总目录执行：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

最终可信结果以这一步为准，不以各自本地中间统计为准。
