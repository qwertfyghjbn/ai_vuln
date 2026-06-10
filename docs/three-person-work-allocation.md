# AI-VulnAtlas 三人分工单

基于当前仓库实际任务数据生成。

- 统计时间：2026-06-10
- 统计口径：使用 [task_loader.py](../task_loader.py) 从 `vuln-analyzed-0605.xlsx` 实际加载任务
- 总任务数：3365
- 总项目数：185
- 分工目标：按**任务量尽量均衡**切分为 3 组，同时遵守“按 `project` 分工、同一项目不拆给多人”的约束

本次切分结果：

- A 组：1122 条任务，48 个项目
- B 组：1122 条任务，68 个项目
- C 组：1121 条任务，69 个项目

---

## 1. 执行原则

必须遵守：

1. 每个人使用**独立 workspace**
2. 每个人只处理自己负责的 `project`
3. 不允许两个人同时处理同一个 `project`
4. 不允许多人在同一个工作目录同时执行 `python3 main.py run`
5. 每个人本地跑完后先执行：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

6. 最终总统计以合并后的总目录再次执行 `rebuild-summary` 为准

---

## 2. Workspace 约定

建议目录：

- A：`/home/lqs/ai_vuln_worker_a`
- B：`/home/lqs/ai_vuln_worker_b`
- C：`/home/lqs/ai_vuln_worker_c`

每个人执行前，确保自己的目录中已具备：

- 当前代码
- `vuln-analyzed-0605.xlsx`
- `ai-vulns-timeline.zip` 或 `data/ai-vulns-timeline/`
- 正确的 `.env` / API 配置

---

## 3. 统一执行模板

每个人都按同样流程执行，只是 `--project-list` 不同。

### 标准执行

```bash
python3 main.py preflight
python3 main.py run --project-list <PROJECT_LIST> --max-workers 4
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

### 小批量试跑

```bash
python3 main.py run --project-list <PROJECT_LIST> --max-workers 4 --max 10
```

### 强制重跑

```bash
python3 main.py run --project-list <PROJECT_LIST> --max-workers 4 --force
```

---

## 4. A 组分工单

- 负责人：A
- Workspace：`/home/lqs/ai_vuln_worker_a`
- 任务数：1122
- 项目数：48

### A 组项目清单

| Project | Tasks |
|---|---:|
| openclaw_openclaw | 971 |
| Tencent_WeKnora | 11 |
| ray-project_ray | 10 |
| QuantumNous_new-api | 9 |
| PrefectHQ_fastmcp | 8 |
| jupyterhub_jupyterhub | 8 |
| nocobase_nocobase | 7 |
| OpenBMB_XAgent | 6 |
| langfuse_langfuse | 6 |
| sgl-project_sglang | 6 |
| cube-js_cube | 5 |
| mesop-dev_mesop | 5 |
| succinctlabs_sp1 | 5 |
| Flux159_mcp-server-kubernetes | 4 |
| crewAIInc_crewAI | 4 |
| langchain-ai_langsmith-sdk | 4 |
| streamlit_streamlit | 4 |
| Gitlawb_openclaude | 3 |
| NVIDIA-Merlin_Transformers4Rec | 3 |
| bytedance_deer-flow | 3 |
| openai_codex | 3 |
| Comfy-Org_ComfyUI-Manager | 2 |
| ParisNeo_lollms-webui | 2 |
| Upsonic_Upsonic | 2 |
| coze-dev_coze-studio | 2 |
| efforthye_fast-filesystem-mcp | 2 |
| griptape-ai_griptape | 2 |
| marimo-team_marimo | 2 |
| modelcontextprotocol_java-sdk | 2 |
| sooperset_mcp-atlassian | 2 |
| zhongyu09_openchatbi | 2 |
| DeDeveloper23_codebase-mcp | 1 |
| Josh-XT_AGiXT | 1 |
| SylphxAI_filesystem-mcp | 1 |
| Tencent-Hunyuan_HunyuanVideo | 1 |
| Tencent_MedicalNet | 1 |
| VectorSpaceLab_OmniGen2 | 1 |
| agentfront_frontmcp | 1 |
| aws-solutions_qnabot-on-aws | 1 |
| chattermate_chattermate.chat | 1 |
| cocoindex-io_cocoindex | 1 |
| getzep_graphiti | 1 |
| hyperterse_hyperterse | 1 |
| langchain-ai_helm | 1 |
| modelcontextprotocol_ruby-sdk | 1 |
| pab1it0_adx-mcp-server | 1 |
| rowboatlabs_rowboat | 1 |
| sonirico_mcp-shell | 1 |

### A 组 `--project-list`

```text
openclaw_openclaw,Tencent_WeKnora,ray-project_ray,QuantumNous_new-api,PrefectHQ_fastmcp,jupyterhub_jupyterhub,nocobase_nocobase,OpenBMB_XAgent,langfuse_langfuse,sgl-project_sglang,cube-js_cube,mesop-dev_mesop,succinctlabs_sp1,Flux159_mcp-server-kubernetes,crewAIInc_crewAI,langchain-ai_langsmith-sdk,streamlit_streamlit,Gitlawb_openclaude,NVIDIA-Merlin_Transformers4Rec,bytedance_deer-flow,openai_codex,Comfy-Org_ComfyUI-Manager,ParisNeo_lollms-webui,Upsonic_Upsonic,coze-dev_coze-studio,efforthye_fast-filesystem-mcp,griptape-ai_griptape,marimo-team_marimo,modelcontextprotocol_java-sdk,sooperset_mcp-atlassian,zhongyu09_openchatbi,DeDeveloper23_codebase-mcp,Josh-XT_AGiXT,SylphxAI_filesystem-mcp,Tencent-Hunyuan_HunyuanVideo,Tencent_MedicalNet,VectorSpaceLab_OmniGen2,agentfront_frontmcp,aws-solutions_qnabot-on-aws,chattermate_chattermate.chat,cocoindex-io_cocoindex,getzep_graphiti,hyperterse_hyperterse,langchain-ai_helm,modelcontextprotocol_ruby-sdk,pab1it0_adx-mcp-server,rowboatlabs_rowboat,sonirico_mcp-shell
```

### A 组执行命令

```bash
cd /home/lqs/ai_vuln_worker_a
python3 main.py preflight
python3 main.py run --project-list openclaw_openclaw,Tencent_WeKnora,ray-project_ray,QuantumNous_new-api,PrefectHQ_fastmcp,jupyterhub_jupyterhub,nocobase_nocobase,OpenBMB_XAgent,langfuse_langfuse,sgl-project_sglang,cube-js_cube,mesop-dev_mesop,succinctlabs_sp1,Flux159_mcp-server-kubernetes,crewAIInc_crewAI,langchain-ai_langsmith-sdk,streamlit_streamlit,Gitlawb_openclaude,NVIDIA-Merlin_Transformers4Rec,bytedance_deer-flow,openai_codex,Comfy-Org_ComfyUI-Manager,ParisNeo_lollms-webui,Upsonic_Upsonic,coze-dev_coze-studio,efforthye_fast-filesystem-mcp,griptape-ai_griptape,marimo-team_marimo,modelcontextprotocol_java-sdk,sooperset_mcp-atlassian,zhongyu09_openchatbi,DeDeveloper23_codebase-mcp,Josh-XT_AGiXT,SylphxAI_filesystem-mcp,Tencent-Hunyuan_HunyuanVideo,Tencent_MedicalNet,VectorSpaceLab_OmniGen2,agentfront_frontmcp,aws-solutions_qnabot-on-aws,chattermate_chattermate.chat,cocoindex-io_cocoindex,getzep_graphiti,hyperterse_hyperterse,langchain-ai_helm,modelcontextprotocol_ruby-sdk,pab1it0_adx-mcp-server,rowboatlabs_rowboat,sonirico_mcp-shell --max-workers 4
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

---

## 5. B 组分工单

- 负责人：B
- Workspace：`/home/lqs/ai_vuln_worker_b`
- 任务数：1122
- 项目数：68

### B 组项目清单

| Project | Tasks |
|---|---:|
| tensorflow_tensorflow | 431 |
| MervinPraison_PraisonAI | 84 |
| mlflow_mlflow | 59 |
| RocketChat_Rocket.Chat | 54 |
| vllm-project_vllm | 45 |
| langflow-ai_langflow | 37 |
| anthropics_claude-code | 27 |
| Significant-Gravitas_AutoGPT | 26 |
| ollama_ollama | 24 |
| labring_FastGPT | 23 |
| openfga_openfga | 23 |
| argoproj_argo-workflows | 20 |
| huggingface_transformers | 18 |
| TransformerOptimus_SuperAGI | 17 |
| vanna-ai_vanna | 17 |
| bentoml_BentoML | 14 |
| HumanSignal_label-studio | 13 |
| lobehub_lobehub | 13 |
| SillyTavern_SillyTavern | 12 |
| gitroomhq_postiz-app | 12 |
| oobabooga_textgen | 12 |
| dataease_SQLBot | 10 |
| AstrBotDevs_AstrBot | 9 |
| czlonkowski_n8n-mcp | 9 |
| samsung_ONE | 8 |
| pinchtab_pinchtab | 7 |
| eosphoros-ai_DB-GPT | 6 |
| nhost_nhost | 6 |
| windmill-labs_windmill | 6 |
| f_prompts.chat | 5 |
| nanbingxyz_5ire | 5 |
| volcengine_OpenViking | 5 |
| Giskard-AI_giskard-oss | 4 |
| elinsky_execution-system-mcp | 4 |
| letta-ai_letta | 4 |
| zhayujie_CowAgent | 4 |
| HBAI-Ltd_Toonflow-app | 3 |
| agno-agi_agno | 3 |
| langchain-ai_langchainjs | 3 |
| wevm_mppx | 3 |
| FedML-AI_FedML | 2 |
| SepineTam_stata-mcp | 2 |
| Vexa-ai_vexa | 2 |
| docker_model-runner | 2 |
| eigent-ai_eigent | 2 |
| lintsinghua_DeepAudit | 2 |
| microsoft_semantic-kernel | 2 |
| neo4j-contrib_mcp-neo4j | 2 |
| toeverything_AFFiNE | 2 |
| 0xKoda_WireMCP | 1 |
| BigSweetPotatoStudio_HyperChat | 1 |
| Deepractice_PromptX | 1 |
| MontFerret_ferret | 1 |
| Tencent-Hunyuan_Hunyuan3D-1 | 1 |
| TencentCloudBase_CloudBase-MCP | 1 |
| Tencent_MimicMotion | 1 |
| aegra_aegra | 1 |
| agentgateway_agentgateway | 1 |
| bagofwords1_bagofwords | 1 |
| cisco-ai-defense_skill-scanner | 1 |
| cohere-ai_cohere-terrarium | 1 |
| google_sentencepiece | 1 |
| jackwrichards_FastlyMCP | 1 |
| langchain-ai_langgraphjs | 1 |
| openakita_openakita | 1 |
| pgvector_pgvector | 1 |
| smn2gnt_MCP-Salesforce | 1 |
| yangjian102621_geekai | 1 |

### B 组 `--project-list`

```text
tensorflow_tensorflow,MervinPraison_PraisonAI,mlflow_mlflow,RocketChat_Rocket.Chat,vllm-project_vllm,langflow-ai_langflow,anthropics_claude-code,Significant-Gravitas_AutoGPT,ollama_ollama,labring_FastGPT,openfga_openfga,argoproj_argo-workflows,huggingface_transformers,TransformerOptimus_SuperAGI,vanna-ai_vanna,bentoml_BentoML,HumanSignal_label-studio,lobehub_lobehub,SillyTavern_SillyTavern,gitroomhq_postiz-app,oobabooga_textgen,dataease_SQLBot,AstrBotDevs_AstrBot,czlonkowski_n8n-mcp,samsung_ONE,pinchtab_pinchtab,eosphoros-ai_DB-GPT,nhost_nhost,windmill-labs_windmill,f_prompts.chat,nanbingxyz_5ire,volcengine_OpenViking,Giskard-AI_giskard-oss,elinsky_execution-system-mcp,letta-ai_letta,zhayujie_CowAgent,HBAI-Ltd_Toonflow-app,agno-agi_agno,langchain-ai_langchainjs,wevm_mppx,FedML-AI_FedML,SepineTam_stata-mcp,Vexa-ai_vexa,docker_model-runner,eigent-ai_eigent,lintsinghua_DeepAudit,microsoft_semantic-kernel,neo4j-contrib_mcp-neo4j,toeverything_AFFiNE,0xKoda_WireMCP,BigSweetPotatoStudio_HyperChat,Deepractice_PromptX,MontFerret_ferret,Tencent-Hunyuan_Hunyuan3D-1,TencentCloudBase_CloudBase-MCP,Tencent_MimicMotion,aegra_aegra,agentgateway_agentgateway,bagofwords1_bagofwords,cisco-ai-defense_skill-scanner,cohere-ai_cohere-terrarium,google_sentencepiece,jackwrichards_FastlyMCP,langchain-ai_langgraphjs,openakita_openakita,pgvector_pgvector,smn2gnt_MCP-Salesforce,yangjian102621_geekai
```

### B 组执行命令

```bash
cd /home/lqs/ai_vuln_worker_b
python3 main.py preflight
python3 main.py run --project-list tensorflow_tensorflow,MervinPraison_PraisonAI,mlflow_mlflow,RocketChat_Rocket.Chat,vllm-project_vllm,langflow-ai_langflow,anthropics_claude-code,Significant-Gravitas_AutoGPT,ollama_ollama,labring_FastGPT,openfga_openfga,argoproj_argo-workflows,huggingface_transformers,TransformerOptimus_SuperAGI,vanna-ai_vanna,bentoml_BentoML,HumanSignal_label-studio,lobehub_lobehub,SillyTavern_SillyTavern,gitroomhq_postiz-app,oobabooga_textgen,dataease_SQLBot,AstrBotDevs_AstrBot,czlonkowski_n8n-mcp,samsung_ONE,pinchtab_pinchtab,eosphoros-ai_DB-GPT,nhost_nhost,windmill-labs_windmill,f_prompts.chat,nanbingxyz_5ire,volcengine_OpenViking,Giskard-AI_giskard-oss,elinsky_execution-system-mcp,letta-ai_letta,zhayujie_CowAgent,HBAI-Ltd_Toonflow-app,agno-agi_agno,langchain-ai_langchainjs,wevm_mppx,FedML-AI_FedML,SepineTam_stata-mcp,Vexa-ai_vexa,docker_model-runner,eigent-ai_eigent,lintsinghua_DeepAudit,microsoft_semantic-kernel,neo4j-contrib_mcp-neo4j,toeverything_AFFiNE,0xKoda_WireMCP,BigSweetPotatoStudio_HyperChat,Deepractice_PromptX,MontFerret_ferret,Tencent-Hunyuan_Hunyuan3D-1,TencentCloudBase_CloudBase-MCP,Tencent_MimicMotion,aegra_aegra,agentgateway_agentgateway,bagofwords1_bagofwords,cisco-ai-defense_skill-scanner,cohere-ai_cohere-terrarium,google_sentencepiece,jackwrichards_FastlyMCP,langchain-ai_langgraphjs,openakita_openakita,pgvector_pgvector,smn2gnt_MCP-Salesforce,yangjian102621_geekai --max-workers 4
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

---

## 6. C 组分工单

- 负责人：C
- Workspace：`/home/lqs/ai_vuln_worker_c`
- 任务数：1121
- 项目数：69

### C 组项目清单

| Project | Tasks |
|---|---:|
| discourse_discourse | 268 |
| FlowiseAI_Flowise | 92 |
| n8n-io_n8n | 87 |
| open-webui_open-webui | 81 |
| gradio-app_gradio | 57 |
| langchain-ai_langchain | 47 |
| jeecgboot_JeecgBoot | 41 |
| Budibase_budibase | 31 |
| langgenius_dify | 28 |
| Oneflow-Inc_oneflow | 26 |
| outline_outline | 26 |
| Mintplex-Labs_anything-llm | 23 |
| mindsdb_mindsdb | 23 |
| danny-avila_LibreChat | 22 |
| ggml-org_llama.cpp | 19 |
| cvat-ai_cvat | 17 |
| chartbrew_chartbrew | 15 |
| keras-team_keras | 15 |
| Foundationagents_MetaGPT | 13 |
| casdoor_casdoor | 13 |
| nltk_nltk | 13 |
| infiniflow_ragflow | 12 |
| BerriAI_litellm | 11 |
| flipped-aurora_gin-vue-admin | 11 |
| HKUDS_OpenHarness | 9 |
| ChatGPTNextWeb_NextChat | 8 |
| binary-husky_gpt_academic | 8 |
| mlaify_OpenSift | 7 |
| InternLM_lmdeploy | 6 |
| langchain-ai_langgraph | 6 |
| qhkm_zeptoclaw | 6 |
| ParisNeo_lollms | 5 |
| kestra-io_kestra | 5 |
| qdrant_qdrant | 5 |
| Bytedesk_bytedesk | 4 |
| HKUDS_nanobot | 4 |
| huggingface_smolagents | 4 |
| promtengineer_localgpt | 4 |
| Chainlit_chainlit | 3 |
| HKUDS_LightRAG | 3 |
| alexei-led_aws-mcp-server | 3 |
| milvus-io_milvus | 3 |
| CodeWithCJ_SparkyFitness | 2 |
| Mindinventory_MindSQL | 2 |
| Tencent_TFace | 2 |
| aliasrobotics_cai | 2 |
| doobidoo_mcp-memory-service | 2 |
| github_copilot-cli | 2 |
| lm-sys_FastChat | 2 |
| mobile-next_mobile-mcp | 2 |
| run-llama_llama_index | 2 |
| unstructured-IO_unstructured | 2 |
| DayuanJiang_next-ai-draw-io | 1 |
| GLips_Figma-Context-MCP | 1 |
| OpenHands_OpenHands | 1 |
| Tencent-Hunyuan_HunyuanDiT | 1 |
| Tencent_AI-Infra-Guard | 1 |
| Tencent_PatrickStar | 1 |
| agent0ai_agent-zero | 1 |
| apconw_Aix-DB | 1 |
| chatboxai_chatbox | 1 |
| cloudflare_agents | 1 |
| crawlchat_crawlchat | 1 |
| gunthercox_ChatterBot | 1 |
| kubeai-project_kubeai | 1 |
| londonaicentre_FLIP | 1 |
| openlit_openlit | 1 |
| pipeshub-ai_pipeshub-ai | 1 |
| smythOS_sre | 1 |

### C 组 `--project-list`

```text
discourse_discourse,FlowiseAI_Flowise,n8n-io_n8n,open-webui_open-webui,gradio-app_gradio,langchain-ai_langchain,jeecgboot_JeecgBoot,Budibase_budibase,langgenius_dify,Oneflow-Inc_oneflow,outline_outline,Mintplex-Labs_anything-llm,mindsdb_mindsdb,danny-avila_LibreChat,ggml-org_llama.cpp,cvat-ai_cvat,chartbrew_chartbrew,keras-team_keras,Foundationagents_MetaGPT,casdoor_casdoor,nltk_nltk,infiniflow_ragflow,BerriAI_litellm,flipped-aurora_gin-vue-admin,HKUDS_OpenHarness,ChatGPTNextWeb_NextChat,binary-husky_gpt_academic,mlaify_OpenSift,InternLM_lmdeploy,langchain-ai_langgraph,qhkm_zeptoclaw,ParisNeo_lollms,kestra-io_kestra,qdrant_qdrant,Bytedesk_bytedesk,HKUDS_nanobot,huggingface_smolagents,promtengineer_localgpt,Chainlit_chainlit,HKUDS_LightRAG,alexei-led_aws-mcp-server,milvus-io_milvus,CodeWithCJ_SparkyFitness,Mindinventory_MindSQL,Tencent_TFace,aliasrobotics_cai,doobidoo_mcp-memory-service,github_copilot-cli,lm-sys_FastChat,mobile-next_mobile-mcp,run-llama_llama_index,unstructured-IO_unstructured,DayuanJiang_next-ai-draw-io,GLips_Figma-Context-MCP,OpenHands_OpenHands,Tencent-Hunyuan_HunyuanDiT,Tencent_AI-Infra-Guard,Tencent_PatrickStar,agent0ai_agent-zero,apconw_Aix-DB,chatboxai_chatbox,cloudflare_agents,crawlchat_crawlchat,gunthercox_ChatterBot,kubeai-project_kubeai,londonaicentre_FLIP,openlit_openlit,pipeshub-ai_pipeshub-ai,smythOS_sre
```

### C 组执行命令

```bash
cd /home/lqs/ai_vuln_worker_c
python3 main.py preflight
python3 main.py run --project-list discourse_discourse,FlowiseAI_Flowise,n8n-io_n8n,open-webui_open-webui,gradio-app_gradio,langchain-ai_langchain,jeecgboot_JeecgBoot,Budibase_budibase,langgenius_dify,Oneflow-Inc_oneflow,outline_outline,Mintplex-Labs_anything-llm,mindsdb_mindsdb,danny-avila_LibreChat,ggml-org_llama.cpp,cvat-ai_cvat,chartbrew_chartbrew,keras-team_keras,Foundationagents_MetaGPT,casdoor_casdoor,nltk_nltk,infiniflow_ragflow,BerriAI_litellm,flipped-aurora_gin-vue-admin,HKUDS_OpenHarness,ChatGPTNextWeb_NextChat,binary-husky_gpt_academic,mlaify_OpenSift,InternLM_lmdeploy,langchain-ai_langgraph,qhkm_zeptoclaw,ParisNeo_lollms,kestra-io_kestra,qdrant_qdrant,Bytedesk_bytedesk,HKUDS_nanobot,huggingface_smolagents,promtengineer_localgpt,Chainlit_chainlit,HKUDS_LightRAG,alexei-led_aws-mcp-server,milvus-io_milvus,CodeWithCJ_SparkyFitness,Mindinventory_MindSQL,Tencent_TFace,aliasrobotics_cai,doobidoo_mcp-memory-service,github_copilot-cli,lm-sys_FastChat,mobile-next_mobile-mcp,run-llama_llama_index,unstructured-IO_unstructured,DayuanJiang_next-ai-draw-io,GLips_Figma-Context-MCP,OpenHands_OpenHands,Tencent-Hunyuan_HunyuanDiT,Tencent_AI-Infra-Guard,Tencent_PatrickStar,agent0ai_agent-zero,apconw_Aix-DB,chatboxai_chatbox,cloudflare_agents,crawlchat_crawlchat,gunthercox_ChatterBot,kubeai-project_kubeai,londonaicentre_FLIP,openlit_openlit,pipeshub-ai_pipeshub-ai,smythOS_sre --max-workers 4
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

---

## 7. 每人交付模板

每个人完成后提交：

1. `output/{project}/...`
2. `output/summary.csv`
3. `output/batch_report.md`
4. `output/audit_report.md`

同时附带简要说明：

```text
负责人：
Workspace：
负责项目：
运行命令：
成功任务数：
失败任务数：
audit-output 是否通过：
是否有需要人工复核的样本：
```

---

## 8. 总汇总负责人操作

由 1 人统一汇总三份结果。

步骤：

1. 收集 A/B/C 三人的 `output/{project}/...` 目录
2. 合并到同一个总 `output/` 目录
3. 在总目录对应的仓库副本中执行：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

4. 生成最终总表：

- 总 `summary.csv`
- 总 `batch_report.md`
- 总 `audit_report.md`

---

## 9. 注意事项

1. 本次切分是按当前 Excel 实际任务数自动平衡的，不代表项目复杂度完全相同
2. A 组虽然项目数较少，但包含 `openclaw_openclaw` 这一超大项目
3. B、C 组项目更多，但任务量与 A 组已平衡
4. 如果后续 Excel 数据更新，应重新统计后再分组
5. 当前系统只支持：
   - 单个 `run` 进程内部通过 `--max-workers` 并行
   - 不支持多人共享同一个 workspace 并发运行
