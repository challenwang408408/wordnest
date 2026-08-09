# 词芽 WordNest

给家长在手机上快速记录孩子阅读中不认识的英语单词。哥哥和妹妹各自独立词库、学习进度和测试记录，数据保存在服务端 SQLite。

生产部署目标：个人网站子路径 `/projects/wordnest/`，API 固定为 `/api/wordnest`。

## 迭代计划

### 1.1 已有功能（本次迭代之前）

| 模块 | 能力 |
|---|---|
| 家庭登录 | 单一家庭访问码 + HttpOnly 会话Cookie，未登录一律401 |
| 孩子档案 | 哥哥、妹妹两个档案，所有查询与写入在后端按 `profile_id` 隔离 |
| 词库管理 | 每个孩子可建多个词库，展示词数与待复习数，单词可多库归属 |
| 手动加词 | 输入单词后 AI 自动补全中文意思、词性、音标、音节（1.3 起支持一次多词） |
| 拍照加词 | 上传书页照片做 OCR 抽词，逐条确认后入库；照片只在内存识别，不落盘不入库 |
| 词库维护 | 搜索、按词库/状态筛选、编辑释义与音标音节、标记已掌握、删除 |
| 认读测试 | 按`next_review_at` 与熟悉度出题，三档评分驱动 familiarity 与下次复习时间 |
| 发音与音节 | Web Speech API 朗读，音节声轨逐块高亮；无可用语音时给出可见提示 |
| 首页看板 | 总词数、待复习数、已掌握数，一键进入测试 |

### 1.2 测试四选一与例句

聚焦一个问题：**孩子打开不熟悉的词库做测试时，不知道该做什么。** 旧流程只给一个英文单词和"看答案"，然后让孩子自己评"不认识 / 有点熟 / 会了"，等于让二年级的孩子既当考生又当考官。

| 改动 | 说明 |
|---|---|
| 测试改为四选一 | 每题给 4 个中文选项，点选即判对错，孩子不用自己想"我算不算会了" |
| 干扰项来自孩子自己的词| 从该孩子已有释义里取干扰项；新词库词太少时用小学常见义兜底，保证永远是四选一 |
| 明确的"下一个"按钮 | 作答后出现全宽"下一个"（最后一题为"看看结果"），进度靠明确点击推进，不会误触跳题 |
| 评分从答题结果推导 | 答对记`known`、答错记 `unknown`；答对但是猜的，可点"刚才是猜的，还不太熟"降为 `familiar` |
| 即时反馈与进度 | 正确项绿框、错选项红框、其余淡出；标题显示"第 N / M 题 · 已答对 X"，结束页给本轮成绩 |
| 词条增加例句 | 词卡展示英文例句 + 中文翻译两行；测试中作答后才显示，避免提前泄题 |
| 老词补例句入口 | 词库页编辑面板新增英文/中文例句输入，以及"用 AI 补例句"按钮，回填迭代前保存的词 |

数据层无需迁移：`words.example_en` / `words.example_zh` 在建表时已存在，本次只是把它们接到 API 与界面上。

### 1.3 批量录词与拍照验证（历史版本）

聚焦家长录入效率：**一次录多个词，再统一补全**；并对拍照识别做真实可用性验证。

| 改动 | 说明 |
|---|---|
| 批量手输 | 录词页改为多行输入（换行 / 逗号 / 空格分隔），一次最多 20 词，去重后点「统一补全」 |
| 一次 AI 补全 | 新增 `POST .../words/enrich-batch`，单次 `grok-4.5` 返回多词结果，比逐词串行快 |
| 列表确认入库 | 补全后按列表勾选、展开改字段，共用词库选择，一键保存勾选词 |
| 拍照可用性 | 真实 AI smoke（`kimi-k2.5`）已通过；保留拍照找词入口，不做二次 OCR 方案 |

### 2.0 蛛网英雄城市与家庭学习闭环

这一版把产品名统一为「词芽」，采用原创的深夜城市、英雄红、电光蓝和发光嫩芽视觉语言，不使用受保护的角色、服装或标志。

| 模块 | 当前能力 |
|---|---|
| 孩子首页 | 单一「今日挑战」主任务，题数与服务端真实可出题集合一致 |
| 专注测试 | 四选一、连续答对、即时反馈、结果复盘、中途退出保护、只练需要再看的词 |
| 家长看板 | 家庭本地时区下近 7 个自然日答题量、正确率、活跃天数、待复习建议和薄弱词直练 |
| 家长录词 | 手输与拍照均为候选确认流程；统一批量补全，最终以单次原子请求保存 |
| 词库管理 | 搜索与双筛选、紧凑列表、按需展开编辑、明确危险操作和失败恢复 |
| 安全 | 访问码 constant-time compare、安全 Cookie、失败限流；只信任私网/回环代理提供的真实 IP |
| 安装体验 | PWA manifest、原创 192/512 图标、Apple touch icon 和应用壳缓存；API 与儿童数据不进入离线缓存 |

固定视觉回归视口为 390×844 和 1280×900，并额外以 195×422 模拟 200% 缩放检查横向溢出。

### 2.1 浅色专业视觉系统

当前版本采用 `blue-professional` 浅色设计方向：浅灰页面、白色内容表面、钴蓝主行动和克制阴影。Spire 城市英雄主视觉只保留在登录品牌区，词库、测试与家长看板统一使用明亮的操作界面。

词库筛选区使用“范围 / 进度”作为可见分组名，同时保留“按词库筛选 / 按学习状态筛选”的无障碍名称。拍照入口使用统一的 Lucide 图标与上传卡片，不改变文件选择、OCR 和候选确认流程。

## 环境要求

- **Python 3.12**（与 Docker 镜像一致；本机请用 3.12 创建虚拟环境，不要依赖系统默认的 `python3`，它可能是 3.9）
- Node.js 20+（前端构建）
- 环境变量见 `.env.example`

## 本地开发

```bash
cp .env.example .env
# 编辑 .env：FAMILY_ACCESS_CODE、SESSION_SECRET、AI_BUILDER_TOKEN

# 必须用 Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 终端 1：API（默认不托管前端，或挂已有 dist）
PYTHONPATH=. .venv/bin/uvicorn backend.app.main:app --reload --port 8000

# 终端 2：前端（开发用根路径 /，Vite 代理 /api → 8000）
cd frontend && npm install && npm run dev
```

浏览器打开 Vite 地址（默认 `http://127.0.0.1:5173`）。

### 本地模拟生产子路径

```bash
cd frontend && npm run build
# 产物 base 为 /projects/wordnest/
PYTHONPATH=. .venv/bin/uvicorn backend.app.main:app --port 8000
```

然后访问 `http://127.0.0.1:8000/projects/wordnest/`。根路径会 307 跳转到该子路径。可用环境变量覆盖：

| 变量 | 作用 |
|---|---|
| `FRONTEND_BASE_PATH` | FastAPI 静态挂载前缀，默认 `/projects/wordnest` |
| `VITE_BASE_PATH` | 前端构建 base（需带尾部 `/`），默认生产 `/projects/wordnest/` |

本地 `npm run dev` 仍使用 `/`，不读生产子路径。

## 测试与检查

在项目根目录执行：

```bash
.venv/bin/pytest -q
.venv/bin/ruff check backend

cd frontend
npm test -- --run
npm run lint
npm run build
```

真实 AI 调用（会消耗额度，默认跳过）：

```bash
RUN_AI_SMOKE=1 AI_BUILDER_TOKEN=... PYTHONPATH=. .venv/bin/python scripts/ai_smoke.py
```

“家长工具 > 批量录词”支持浏览器话筒录入。录音停止后会等浏览器交付最终音频，把录音物化为原始字节并在内存中转发到 AI Builders，只回填最多 20 个逗号分隔的英文单词，不会直接写入词库。生产环境需通过 HTTPS 访问，浏览器才会开放话筒权限；原始字节上传用于兼容 iPhone Safari 和第三方 WKWebView。

## 环境变量

见 `.env.example`。生产必须：

- 更换示例 `FAMILY_ACCESS_CODE` 与足够长的 `SESSION_SECRET`
- 设置 `APP_ENV=production`（启用 Secure Cookie）
- 设置 `FAMILY_TIMEZONE`（默认 `Asia/Shanghai`），保证家长看板按家庭自然日统计
- 通过 `DATABASE_URL` 或 `DATA_DIR` 把数据库放到代码目录外
- 配置 `AI_BUILDER_TOKEN`

`.env`、数据库、`data/`、`screenshots/*.png`、缓存目录已在 `.gitignore` 中排除，勿提交。

## Docker

```bash
docker build -t wordnest .
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e FAMILY_ACCESS_CODE=... \
  -e SESSION_SECRET=... \
  -e AI_BUILDER_TOKEN=... \
  -e APP_ENV=production \
  -e DATA_DIR=/data \
  -v wordnest-data:/data \
  wordnest
```

容器内入口：`http://localhost:8000/projects/wordnest/`，API：`http://localhost:8000/api/wordnest/healthz`。

## 产品约束摘要

- 服务端数据库是事实源，不用浏览器存储冒充后端。
- 孩子数据按 `profile_id` 隔离。
- 拍照仅内存识别，不落盘、不入库、不写日志。
- 密钥只来自环境变量。
