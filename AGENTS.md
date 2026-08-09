# 家庭英语单词库开发约束

先读根目录 `SPEC.md`，它是本项目唯一产品与技术规格。实现时必须遵守 workspace 根目录的 `AGENTS.md`。

## 硬约束

- 服务端数据库是业务事实源，禁止用 localStorage 或 IndexedDB 冒充持久化后端。
- 所有孩子相关查询与写入都必须在后端按 `profile_id` 隔离，并通过授权会话访问。
- 照片只用于本次识别，不落数据库、不写日志、不提交。
- `AI_BUILDER_TOKEN`、`FAMILY_ACCESS_CODE`、`SESSION_SECRET` 只能来自环境变量。
- 禁止在代码、配置和文档中硬编码 `/Users/<用户名>/` 路径。
- 不提交、不推送、不部署，除非主线 Agent 另行执行。
- 改动后运行规格要求的测试、类型检查、构建和静态检查。

## 代码风格

- React + TypeScript + Vite 前端，FastAPI + SQLAlchemy + SQLite 后端。
- 前端 API 类型集中管理，后端请求与响应使用 Pydantic 模型。
- 稳定业务逻辑和数据隔离必须有测试；禁止 `any`、静默吞错和假实现。
- 页面文案面向家长与孩子，用中文直白描述操作，不暴露实现术语。
