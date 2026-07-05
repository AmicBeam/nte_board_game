# NTE Board Game

异环主题网页卡牌牌桌，采用 Flask 实现。项目通过数据库保存玩家、登录态、构筑、房间和对局快照，并提供可在浏览器中游玩的“异象对决”模式。

当前主游戏模式是 **异象对决**：玩家使用异象道具组成主牌组，围绕启动、调度、回收、小干扰、素材消耗和异能者共鸣争夺场面。历史探索玩法已从当前代码与资源中移除，不保留兼容入口。

## 当前模式：异象对决

异象对决是一套 6 回合的单战场卡牌对决：

- 玩家使用 10 到 20 张异象道具组成主牌组，同名道具最多 3 张。
- 异能者放在异能者编队中，满足素材条件后登场或再次共鸣。
- 每回合双方共享部署阶段，先支付费用并部署道具，双方结束部署后再统一进入素材消耗与揭示结算。
- 结算先手在回合开始时由当前总战力决定，锁定后不会被本回合后续操作改变。
- 异象道具统一以“揭示”结算效果，需要检视牌库、选择目标或二选一的道具必须在部署前完成宣言。
- 只有进入本回合前已经稳定在场的异象道具可以作为异能者素材。
- 异能者登场或再共鸣会消耗素材，并带来环合、铺场、清场、返场、资源中转或终端爆发。
- 基础环合为创生、延滞、浊燃、黯星；盈蓄与失谐是融合结果，不作为普通道具体系存在。

现行规则、术语、卡牌设计和异能者职责以 `docs/everness-item-chain-card-design.md` 为唯一设计真源。平衡迭代流程、三角看板验收标准和报告索引记录在 `docs/duel-balance-iteration.md`。

## 主要特性

- 账号、密码、token、构筑、房间和对局快照全部持久化到数据库。
- 对局内快照使用“进程内最新态缓存 + 异步入库队列”，保证操作反馈尽快返回，并避免异步入库窗口读到旧状态。
- 玩家先通过机器人 `Fairy` 注册账号或重置密码，再在浏览器登录。
- 页面包含登录页、资料页、主界面、构筑页和对局页。
- 构筑页支持异象道具主牌组与异能者编队配置。
- 战斗页展示双方牌库、手牌、墓地、战场、结算先手、能量、日志和动画反馈。
- 所有费用、抽牌、调度、素材消耗、异能者条件、战力变化、环合持续、胜负和 AI 决策都在后端结算。
- 前端只负责状态渲染、宣言选择、按钮禁用、动画衔接和 token 携带。
- 刷新页面后可恢复最新对局状态。
- 关键资料写入使用同步数据库事务，对局快照写入使用异步持久化队列。
- 日志按日期写入 `logs/YYYY-MM-DD.log`。

## 工程边界

- `app/` 是网站后端和前端主链路。
- `plugins/` 是机器人桥接参考实现，不能直接 import `app/` 下业务代码。
- 机器人与网站只通过共享数据库表交互。
- 前端不做规则计算；新增规则应进入后端规则层、内容定义或事件系统。
- 异象对决内容按卡牌类型维护在 `app/content/items/`、`app/content/characters/`、`app/content/common/`、`app/content/effects/` 和 `app/content/duel_decks.py`；`app/content/duel_common.py` 仅作为薄聚合入口。
- 跨内容共享的时机优先通过 `app/engine/events.py` 和 `app/engine/event_bus.py` 暴露。
- 持续到未来回合或未来时机的效果应进入显式运行时状态或对局快照字段，不写不透明临时桶。

## 架构概览

- `app/config.py`
  统一管理配置、数据库路径、token 过期时间、密码策略等。
- `app/db.py`
  初始化数据库连接与建表流程，并提供事务上下文。
- `app/models.py`
  定义玩家、密码、token、构筑、房间和对局快照等模型。
- `app/dao.py`
  提供数据库读写方法，避免路由和服务层直接操作 ORM 细节。
- `app/async_persistence.py`
  管理对局快照的进程内最新态缓存与异步入库队列。
- `app/auth.py`
  负责登录、token 创建、token 校验和 Flask 路由鉴权装饰器。
- `app/content/common/` 与 `app/content/effects/`
  维护异象对决的共享常量、卡牌工厂、区域操作、衍生牌和共用效果工具。
- `app/content/duel_common.py`
  内容层薄聚合入口，汇总 common/effects 的公开符号。
- `app/content/duel_decks.py`
  维护异象对决的流派构筑。
- `app/content/items/`
  维护异象对决的异象道具卡牌定义；卡面优先使用 `app/static/images/item/` 中已有资源。
- `app/content/characters/`
  维护异象对决的异能者卡牌定义。异能者应使用真实角色名、有效属性和有效立绘路径。
- `app/engine/events.py`
  定义事件常量。
- `app/engine/event_bus.py`
  统一执行事件队列，支持 `default handler`、`append`、`replace` 三类语义。
- `app/engine/state/`
  维护对局快照、卡牌、地点、选择等 JSON 状态类型契约。
- `app/engine/application/run_state.py`
  维护对局快照加载、公开状态投影适配和持久化排队。
- `app/engine/flow/`
  维护回合推进、揭示流程和胜负/撤退/undo 等流程编排。
- `app/engine/game_service.py`
  对局 API 编排入口。保留路由直接调用的对局操作，协调应用适配、流程、规则、AI 和事件模块。
- `app/routes.py`
  提供 HTML 页面和 JSON API，只做参数校验、鉴权和调用服务层。
- `app/templates/` 与 `app/static/`
  前端页面、脚本、样式和图片资源。
- `plugins/nte_account_db.py`
  插件侧独立数据库桥接层，直连同一个数据库文件并使用相同表名。
- `plugins/nte_account.py`
  机器人桥接层，提供“注册账号”和“重置密码”命令。
- `scripts/seed_mock_account.py`
  本地无机器人时预置 mock 账号和密码。

## 数据流

1. 玩家向机器人 `Fairy` 发送 `注册账号` 或 `重置密码` 指令；QQ 号就是账号。
2. `plugins/nte_account.py` 通过 `plugins/nte_account_db.py` 直连共享数据库，创建或查找玩家并生成登录密码。
3. 玩家在浏览器登录页输入玩家号和密码。
4. 后端校验密码后签发 token，浏览器将 token 存储在本地。
5. 登录后玩家可在网页修改用户名和密码；用户名最多保留 8 个汉字。
6. 浏览器后续请求在 `Authorization: Bearer <token>` 中携带 token。
7. 路由层通过 `app/auth.py` 获取当前玩家，再调用服务层执行构筑、房间或对局逻辑。
8. 对局操作先更新进程内最新态并返回，再异步入库；后续读取优先使用进程内最新态，回退到数据库快照。

## 运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

打开 `http://127.0.0.1:5001`。

## Mock 联调

当前环境不运行机器人时，可通过独立 DB 脚本创建一个 mock 账号：

- 玩家号：`10001`
- 密码：`654321`

执行方式：

```bash
python3 scripts/seed_mock_account.py
```

该脚本只通过数据库写入 mock 账号和密码，不会让主链路引用 `plugins/` 目录。

## 机器人交互

机器人命令参考实现位于 `plugins/nte_account.py`，支持 `注册账号` 和 `重置密码`。
QQ 号就是账号，机器人会回传一个网页登录密码。
网页端登录后支持修改用户名和密码；用户名最多保留 8 个汉字。

## 验证与迭代

- 平衡验收以三角数据看板为准。
- 浏览器验收用于确认真实页面体验，需从牌桌 UI 完成出牌、宣言、选择素材、唤醒异能者、选择目标、结束回合和查看日志。
- 平衡迭代至少保留三角看板数据、验收状态、关键问题归因、改动清单和下一轮验证重点。
- 规则和卡牌内容优先对齐 `docs/everness-item-chain-card-design.md`。

常用本地检查：

```bash
python3 -m unittest tests.test_solo_room_flow
node --check app/static/card_game/js/table.js
node --check app/static/card_game/js/build.js
```

## 部署说明

- 部署网页后端时，只需要部署本项目的网站部分。
- `plugins/` 目录中的机器人桥接代码不应随网站主服务一起部署。
- 正式部署时，应把 `plugins/` 下对应实现放到机器人项目中运行，并由机器人项目直连同一个数据库。
- 本仓库保留 `plugins/`，是为了提供对接参考和本地联调样板，不代表生产环境要把机器人代码和网站代码部署在同一个项目里。

## 备注

- 详细架构、设计宗旨、插件边界和前端约束见 `AGENTS.md`。
- 当前规则设计见 `docs/everness-item-chain-card-design.md`。
- 平衡迭代流程见 `docs/duel-balance-iteration.md`。
