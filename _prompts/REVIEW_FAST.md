你是本项目的第二实现 Agent。先完整阅读 `AGENTS.md`、`SPEC.md` 和现有代码。不要重写已通过部分，不要提交、推送或部署。你的任务是基于真实缺口做代码审查、修复和补测试，然后运行所有门禁。

已验证事实：

- `.venv/bin/pytest -q`：10 passed。
- `npm test -- --run`：3 passed。
- `npm run lint`、`npm run build`、`python3 -m ruff check backend` 已通过。
- 本机默认 `python3` 是 3.9，目标与 Docker 运行时是 Python 3.12；README 目前写泛化 `python3`，需改为清晰的 3.12 要求。
- 当前 Vite base、BrowserRouter 与 FastAPI 静态挂载按域名根路径实现，但生产目标是个人网站子路径 `/projects/wordnest/`，API 保持 `/api/wordnest`。
- 前端目前只有 3 个测试，需检查是否覆盖角色选择、录词确认、测试翻面评分、发音无 voice 降级和核心空/错态。

必须完成：

1. 审查所有 API 的 profile 隔离、资源归属校验、事务、重复词幂等、Cookie 安全、图片 5MB/MIME 限制和 AI 无效 JSON 不入库。发现问题直接修并补后端测试。
2. 让生产前端可以稳定部署在 `/projects/wordnest/`：Vite 资源 URL、Router basename、直接刷新嵌套路由、FastAPI 单进程静态 fallback 都要一致；本地开发仍可用。用集中常量或环境变量实现，禁止散落硬编码。
3. 补前端关键行为测试，覆盖至少角色选择、录词确认或保存、测试翻面与评分、发音无 voice 降级中的核心可测路径。不要为了数量写空洞测试。
4. 对照 `SPEC.md` 逐项检查：多词库 CRUD、单词编辑/删除/掌握恢复、OCR 确认、测试抽取与评分、刷新持久化、移动端 safe area 和 48px 触控目标。缺失的必须实现。
5. 审查设计是否真的执行“清晨阅读桌”和音节声轨，移除模板感明显的部分；保持轻松但不幼稚，禁止宋体、Inter、Arial 和紫色渐变。
6. 修 README：明确 Python 3.12、本地入口、生产子路径、测试命令与环境变量。确认 `.env`、数据库、缓存、截图不会被跟踪。
7. 运行 `.venv/bin/pytest -q`、`.venv/bin/ruff check backend`、`npm test -- --run`、`npm run lint`、`npm run build`。最终只报告真实结果和仍需真实浏览器或外部服务验证的事项。

直接修改当前项目代码并完成。
