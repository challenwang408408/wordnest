# 词芽 WordNest：产品与技术规格

## 1. 产品目标

给家长在手机上快速记录孩子阅读中不认识的英语单词。系统自动补全中文意思、IPA 音标、自然拼读音节分隔，并提供标准美式发音。哥哥和妹妹拥有完全独立的词库、子词库、学习进度和测试记录，数据刷新或换设备后仍保留。

产品服务两类人：家长负责录入、管理和判断学习节奏，孩子负责认读、听音与测试。高频路径必须短：登录一次后，选择孩子即可看到唯一的「今日挑战」；录词和拍照明确归入家长工具。

## 2. 必须交付的用户能力

### 2.1 登录与角色

- 首次访问输入家庭访问码；验证成功后写入安全的 HttpOnly 会话 Cookie。
- 登录后显示哥哥、妹妹两张角色卡，进入后可随时切换。
- 角色不是前端标签。后端每个孩子相关的查询和写入都按 `profile_id` 隔离。
- 首次鉴权和任一受保护请求中途返回 401 时，清理当前孩子与前端私有缓存，回到访问码页面并给出明确提示；登录请求本身失败时留在当前表单。

### 2.2 多子词库

- 每个孩子默认拥有“日常阅读”词库。
- 支持新建、重命名、删除空词库；非空词库删除前必须先确认，删除关联但不误删其他词库仍在使用的单词。
- 支持查看词库单词数、待复习数，并选择一个或多个词库开始测试。
- 0 词词库在首页挑战范围中保留可见但禁止勾选，不进入默认出题参数。

### 2.3 单词录入

- 手工录入：支持一次输入多个英语单词或词组（换行 / 逗号分隔，兼容分号和制表符，最多 20 项，自动去重）。词组内部空格保留，连续空白归一为空格；例如 `take off` 始终作为一个条目补全与保存。调用 AI Builders `grok-4.5` 批量返回规范 JSON 数组，每项含标准拼写、一个核心中文释义、词性、IPA、美式音节分隔和简短例句。单词输入仍可用。
- 语音录入：批量录词输入框提供话筒按钮，支持最多 60 秒短录音。停止后等待最终 `dataavailable` 再释放话筒轨道，录音物化为原始字节后只在内存中转发给 AI Builders，不落盘；识别固定提示为英文单词听写，后端再做英文字符过滤、小写化、去重与最多 20 个限制，按逗号分隔回填现有输入框。
- 批量补全后进入确认列表：用户可勾选、展开改字段、选择目标词库，再统一保存；AI 漏掉的词以可编辑空草稿保留，不静默丢弃。
- 拍照录入：手机相机或相册上传图片，后端仅在内存中处理，调用 AI Builders `kimi-k2.5` vision 提取适合小学生学习的英语候选词。
- OCR 结果必须进入确认页。用户可勾选、改拼写、补中文提示、选择目标词库，再通过单次批量 AI 请求补全，并用一个后端事务统一保存；识别结果不得未经确认直接入库。
- 对同一孩子的同一规范拼写去重。重复录入时只追加词库关联，不重置学习进度。
- 失败时允许手工补充或重试，并展示可行动的错误原因。

### 2.4 发音与自然拼读

- 词卡展示拼写、IPA 和带分隔符的音节，例如 `beau·ti·ful`。
- 使用浏览器 Web Speech API 优先选择 `en-US` voice 播放标准发音；无可用 voice 时给出可见提示，不静默失败。
- 紧凑词库行直接提供发音按钮；详情卡的音节声轨本身也是发音热区。点击后音节轨道有一次克制的逐段亮起动效；尊重 `prefers-reduced-motion`。

### 2.5 测试与记忆

- 从当前孩子选中的词库生成认读测试，默认 10 题，不足则全部使用；首页预览与真正出题共用「按孩子隔离、未掌握、词库去重」口径。
- 题型以“看到英文，知道中文并会读”为中心：先显示英文、音标和发音按钮，再从四个中文选项中选择，作答后才展示释义和例句。
- 答对自动记为 `known`，答错记为 `unknown`；答对但属于猜中时，孩子可用“其实是蒙的”降级为 `familiar`。答对后仍明确点“下一个”，不自动跳题，保留纠偏时间。后端记录每次结果，更新熟悉度、连续答对、总测试次数、最近测试时间和下次复习时间。
- 随机算法优先抽取到期、低熟悉度和较久未测的词，仍保留少量随机性；同一轮不重复。
- 答题过程进入专注模式，中途退出准确说明已提交和未提交数据；结果页列出需要再看的词，并可只针对这些 `word_id` 开始下一轮。
- “已掌握”词默认不进入测试，但可在管理页重新启用或删除。

### 2.6 词库管理

- 按关键词、子词库、学习状态筛选；请求失败与真正空词库、筛选无结果使用不同状态。
- 页头直接提供“录新词”入口。紧凑行的主体区域整块可展开，并保留独立发音按钮；支持编辑释义、音标、音节、例句和词库归属，支持标记已掌握、恢复测试、删除。
- 删除单词和子词库使用产品内确认弹层，默认焦点在取消动作；所有状态变化刷新后保持。

## 3. 数据模型

使用 SQLAlchemy 2.x 与 SQLite，启用 foreign keys 和 WAL。生产数据库路径由 `DATABASE_URL` 或 `DATA_DIR` 环境变量决定，不放在代码目录或静态目录。

- `profiles`: `id`, `slug` (`brother`/`sister`, unique), `display_name`, timestamps。
- `libraries`: `id`, `profile_id`, `name`, `is_default`, timestamps；同一孩子下名称唯一。
- `words`: `id`, `profile_id`, `normalized_spelling`, `spelling`, `meaning_zh`, `part_of_speech`, `ipa`, `syllables`, `example_en`, `example_zh`, `is_mastered`, timestamps；`profile_id + normalized_spelling` 唯一。
- `library_words`: `library_id + word_id` 复合主键，外键级联。
- `word_progress`: `profile_id + word_id` 唯一，含 `familiarity`, `correct_streak`, `review_count`, `last_rating`, `last_reviewed_at`, `next_review_at`。
- `review_events`: `id`, `profile_id`, `word_id`, `rating`, `reviewed_at`，用于长期记录。

所有跨表写入使用事务。种子逻辑幂等创建哥哥、妹妹和各自默认词库。

## 4. API 契约

统一前缀 `/api/wordnest`。

- `POST /auth/login`, `POST /auth/logout`, `GET /auth/session`
- `GET /profiles`
- `GET|POST /profiles/{profile_id}/libraries`
- `PATCH|DELETE /profiles/{profile_id}/libraries/{library_id}`
- `GET|POST /profiles/{profile_id}/words`
- `PATCH|DELETE /profiles/{profile_id}/words/{word_id}`
- `POST /profiles/{profile_id}/words/enrich`
- `POST /profiles/{profile_id}/words/enrich-batch`
- `POST /profiles/{profile_id}/words/batch`
- `POST /profiles/{profile_id}/words/scan`
- `POST /profiles/{profile_id}/words/transcribe-voice`
- `POST /profiles/{profile_id}/quiz/preview`
- `POST /profiles/{profile_id}/quiz/start`
- `POST /profiles/{profile_id}/quiz/{word_id}/rate`
- `GET /profiles/{profile_id}/dashboard`
- `GET /healthz`

会话中允许访问两个固定家庭角色，但所有资源必须验证 URL 中 profile 与资源真实归属一致。不得通过猜测 ID 跨角色读取或修改。

## 5. AI Builders 集成

API base：`https://space.ai-builders.com/backend/v1`，Token 仅从 `AI_BUILDER_TOKEN` 读取。

- 手输 enrichment 模型：`grok-4.5`（单词与批量共用）。
- 图片识别模型：`kimi-k2.5`，请求温度固定 `1.0`，图片以经过尺寸和大小限制的 data URL 发送。
- 服务端设置超时、最大 5MB 图片、MIME 白名单和结构化响应校验。
- 短语音使用 `/v1/audio/transcriptions`，固定 `language=en` 与英文词表听写 prompt；前端以带音频 MIME 的原始字节请求规避 iOS WKWebView 的空 multipart 文件兼容问题，后端暂时兼容旧版 multipart 客户端。最大 8MB，使用音频 MIME 白名单，响应只暴露规范单词、逗号分隔文本和 `request_id`。
- AI 响应先去 Markdown fence，再 JSON parse，再用 Pydantic 校验。无效响应返回可识别的 502 错误，不保存半成品。
- 测试中 mock AI 客户端；另提供一个显式 opt-in 的真实 smoke 脚本，不在普通测试中消耗额度。

## 6. 技术结构

单仓应用，FastAPI 单进程可同时服务 API 与前端生产构建。

```text
backend/
  app/{main,config,database,models,schemas,auth}.py
  app/api/*.py
  app/services/{ai_builder,quiz}.py
  tests/
frontend/
  src/{api,components,features,hooks,styles,types}/
scripts/
Dockerfile
requirements.txt
.env.example
```

前端使用 React、TypeScript、Vite、React Router、TanStack Query。避免引入大而无用的 UI 套件。移动端视口与 iPhone safe area 必须处理。

## 7. 视觉与交互方向

方向名：蓝调轻盈。采用 `blue-professional` 的浅色专业基底，并吸收 Apple 教育页面的大留白、清晰层级和克制表面设计。孩子喜欢的城市英雄氛围只保留在 Spire 登录主视觉、少量红蓝细节和任务文案中，不复刻角色、服装、面罩、蜘蛛标志或任何受保护宣传素材。

### Token

- `page #F5F7FB`：全站浅灰页面底色。
- `paper #FFFFFF`：内容卡片与操作表面。
- `ink #1D2433`：主文字。
- `hero-blue #0A66D8`：主行动、焦点与学习进度。
- `hero-blue-soft #EAF3FF`：选中态、图标容器与次级反馈。
- `hero-red #D9495B`：危险操作与少量英雄主题强调，不作为大面积背景。
- `line #DFE5EE`：输入框、分隔线和轻边框。

中文正文与界面标题优先使用 `SF Pro` / `PingFang SC` 系统栈，英文大词使用 `Bricolage Grotesque`，数据与音标使用 `IBM Plex Mono`。不使用紫色渐变、深浅混搭或过度装饰的模板式界面。

### 布局

- 手机首页顶部是当前孩子和切换入口，中部只有「今日挑战」主任务，录词与拍照位于家长工具区域。
- 词库页和家长看板都提供录词入口，家长发现漏词时不必先回首页。
- 底部三项导航：首页、词库、家长；固定栏处理 safe area。
- 个人网站返回栏只在登录页显示；进入词芽后优先保留手机首屏空间和 PWA 沉浸感。
- 操作页统一使用浅色背景和白色表面；深色 Spire 图片仅出现在登录品牌区，不进入词库、测试和家长管理页面。
- 所有主触控目标至少 48px，常用动作一只手可达。
- 桌面端限制内容宽度，保留工具感，不简单把手机 UI 拉满。
- 195×422 用于模拟 390×844 下的 200% 缩放，任何核心路径不得产生横向溢出。

### 标志性元素

每张单词卡都有“音节声轨”：音节被分成连续的圆角片段，点击发音后从左到右短暂亮起。这个元素同时服务自然拼读、发音反馈和品牌识别，其余装饰保持克制。

## 8. 安全与隐私

- 家庭访问码使用 constant-time compare；生产不得使用示例默认值。
- 同一客户端 60 秒内连续 5 次失败后短时限流；只有回环或私网代理来源的 `X-Real-IP` 才被信任。当前进程内限流依赖单进程部署，多 worker 时必须切换共享存储。
- Cookie 设置 HttpOnly、SameSite=Lax，生产环境 Secure；会话签名密钥来自环境变量。
- CORS 默认不开放；同源部署。
- 图片和录音不落盘、不记录 base64 或转写正文；日志不记录访问码、Token、Cookie 或儿童数据正文。
- 所有环境文件、数据库、上传和测试产物写入 `.gitignore`。

## 9. 验收标准

### 自动化

- 后端：登录、角色资源隔离、词库 CRUD、重复词幂等、AI 无效 JSON 不入库、测试抽取与评分持久化。
- 前端：关键组件与角色切换、批量录词、拍照批量补全、紧凑词库、四选一评分和薄弱词直练。
- 语音录词：覆盖开始、异步最终音频到达后再停轨、原始字节上传、旧 multipart 兼容、识别回填、权限失败和不支持录音时的降级提示。
- `pytest`, `npm test`, `npm run lint`, `npm run build` 全通过。

### 本地端到端

- 390x844 视口：登录、选哥哥、新建词库、手输录词、刷新仍存在、开始测试、评分、管理删除。
- 切到妹妹后看不到哥哥刚创建的词库和单词。
- 用一张测试图片走 OCR 确认流程，候选词不会直接入库。
- 发音按钮可调用可用的 en-US voice；无 voice 的测试环境验证降级提示。
- 控制台无 error，页面无横向溢出，关键截图保存到项目 `screenshots/`。
- PWA manifest、service worker、192/512 图标和 Apple touch icon 均可从生产子路径返回；不得缓存 `/api/`。

### 线上

- 应用入口、独有正文与静态资源均非 fallback，返回正确内容。
- 线上执行一次真实手输 enrichment 和一次真实 OCR。
- 新增单词后刷新与重新登录仍存在；服务器进程重启后数据仍存在。
- 首页项目档案包含“词芽 WordNest”卡片和正确链接。

## 10. 发布边界

开发 Agent 只完成可部署产物，不提交、推送或改远端。主线 Agent 负责锁定拓扑、凭据与远端配置范围后再执行发布和线上验收。
