# NTE Board Game

独立的 Flask 版异环网页牌桌项目。

## 主要特性

- 使用数据库保存玩家、密码、token、构筑和对局快照。
- 玩家先向机器人 `Fairy` 发送 `注册账户` 获取密码，再在浏览器中登录。
- 页面拆分为登录页、资料页、主界面、构筑页和对局页。
- 所有规则计算都在后端完成，前端只负责展示和交互。
- 角色、道具、地图都通过目录化文件自动加载。
- 地图使用 PNG 背景，并用图标覆盖展示可互动对象。
- 支持刷新页面后恢复对局。
- 关键流程使用事务包裹，并对规则循环设置安全上限。
- 日志按日期写入 `logs/YYYY-MM-DD.log`。

## 工程规则

- 状态持久化优先：玩家、密码、token、构筑、对局快照全部落数据库。
- 关键流程必须走事务：登录验码、保存构筑、开始对局、行动结算、重置对局都应在事务边界内执行。
- DAO 层保持实用抽象：路由和服务层不直接编写 ORM 细节。
- 前端不参与规则计算：只展示状态、发送指令、渲染地图和提示。
- 用户名统一按最多 8 个汉字处理；机器人注册和网页修改都会自动截断。
- 卡牌实例与卡牌定义分离：定义来自 `app/content/items/`，运行时实例拥有独立 `instance_id`。
- 事件驱动规则优先：角色被动和扩展效果优先通过事件总线组织，而不是在主流程中持续堆叠条件分支。
- 持续性效果使用 `active_effects` 承载，通过 `runtime_effect` 和 `zone_effects` 管理生命周期。
- 伤害统一走伤害包链路，而不是在各处分散扣血。
- 防御性编程：关键状态在读写前后要校验；遇到非法状态要尽快失败并记录日志。
- 循环必须设置上限：抽牌、移动等循环统一走安全上限，避免出现死循环。
- 故障兜底要明确：接口层需要记录异常日志，并返回稳定的错误信息。
- 插件与网站后端只通过共享数据库交互，不能直接互相 import 业务代码。

## 架构概览

- `app/config.py`
  集中管理数据库、日志目录、token 时效、循环安全上限等配置。
- `app/db.py`
  初始化数据库连接，并提供事务上下文。
- `app/models.py`
  定义玩家、密码、token、构筑、对局快照等持久化模型。
- `app/dao.py`
  提供数据库读写入口，屏蔽 ORM 细节。
- `app/auth.py`
  处理密码登录、token 校验和鉴权装饰器。
- `app/templates/index.html`
  登录后的主界面，提供模式选择、退出登录、查看构筑与当前构筑摘要。
- `app/templates/profile.html`
  资料页，提供修改用户名和修改密码功能。
- `app/content/`
  维护角色、道具、地图的定义数据，由加载器统一收集。
- `app/engine/runtime.py`
  构建角色实例与道具实例，确保运行时对象与定义分离。
- `app/engine/event_bus.py`
  负责事件队列、阶段顺序执行、`default handler` / `append` / `replace` 三类 hook 分发与链式触发。
- `app/engine/events.py`
  统一定义回合、移动、地图、伤害包、战斗相关事件常量，以及阶段事件序列。
- `app/engine/damage.py`
  负责伤害包构建与结算，默认链路为 `CREATE_DAMAGE_PACKAGE -> APPLY_DAMAGE_PACKAGE -> DAMAGE_APPLIED`。
- `app/engine/effects.py`
  负责运行时效果实例的注册、聚合、移除和按来源管理。
- `app/engine/game_service.py`
  核心规则层。负责读取快照、按阶段推进事件、执行默认结算并持久化回数据库；不承载具体 item / passive / map object 的业务效果。
- `app/utils/logger.py`
  提供按日期落盘的日志能力。
- `plugins/`
  仓库内提供的机器人桥接参考实现，单独连接共享数据库，不直接引用网站业务代码。

## 运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

打开 `http://127.0.0.1:5001`。

## 部署说明

- 部署网页后端时，只需要部署本项目的网站部分。
- `plugins/` 目录中的机器人桥接代码不应随本项目一起部署到网页服务。
- 正式部署时，应把 `plugins/` 下对应实现放到机器人项目中运行，并由机器人项目直连同一个数据库。
- 本仓库保留 `plugins/`，是为了提供对接参考和本地联调样板，不代表生产环境要把机器人代码和网站代码部署在同一个项目里。

## 日志

- 应用日志会写到 `logs/` 目录。
- 文件名按日期滚动，例如 `logs/2026-05-08.log`。
- 重点记录登录、构筑、开始对局、状态恢复、规则异常和循环上限触发事件。

## Mock 联调

当前环境不运行机器人时，可通过独立 DB 脚本创建一个 mock 账户：

- 玩家号：`10001`
- 密码：`654321`

执行方式：

```bash
python3 scripts/seed_mock_account.py
```

该脚本只通过数据库写入 mock 账户和密码，不会让主链路引用 `plugins/` 目录。

## 机器人交互

机器人命令参考实现位于 `plugins/nte_account.py`，支持 `注册账户` 和 `重置密码`。
你的 QQ 号就是账户，机器人会回传一个验证码作为网页登录密码。
网页端登录后支持修改用户名和密码；用户名最多保留 8 个汉字。
机器人侧通过共享数据库写入网页登录密码，网页端再通过登录接口读取同一份数据完成登录。

## 当前已落地的继承点

- 状态持久化
- 事务包裹关键流程
- DAO 层抽象
- 事件驱动规则系统
- 默认处理器与 `replace/append` 机制
- 伤害包机制
- 运行时效果实例化
- 区域驱动效果注册/注销
- 卡牌实例与卡牌定义分离
- 防御性编程与状态校验
- 循环上限与故障兜底
- 后端统一日志记录与按日期落盘

## 事件引擎

- 新项目参考旧项目的事件管理思想，将回合拆成多个 `GameEvent` 常量。
- 引擎按阶段顺序推进，例如回合开始会固定执行：
  - `turn_begin`
  - `dice_rolled`
  - `action_phase_begin`
- 移动前会先进入 `move_block_check`，让地图物件自行改写阻挡结果；例如门的钥匙消耗逻辑定义在地图物件文件中，而不在引擎里硬编码。
- 战斗和直伤统一通过伤害包推进：
  - `create_damage_package`
  - `apply_damage_package`
  - `damage_applied`
- 角色实例、道具实例后续都可以在自己的内容文件里声明事件 hook。
- hook 收到统一的 `EventContext` 后，可以：
  - 读取当前状态
  - 读取事件入参 payload
  - 修改状态
  - 回写 payload
  - 继续压入新的事件，形成链式触发
- 当效果需要持续多个事件时，内容层应注册 `runtime_effect` 到 `active_effects`。
- 当效果由手牌区等区域决定生效与失效时，内容层应优先使用 `zone_effects`。
- 这样主流程只负责“阶段推进”和“默认规则”，具体内容效果尽量留在 `app/content/` 中维护。

## 当前状态结构

- 当前对局快照的核心字段包括：
  - `character_instance`
  - `player`
  - `map`
  - `hand`
  - `discard_pile`
  - `active_effects`
  - `pending_die`
  - `has_played_item`
  - `route_hint`
  - `log`
- 当前模型已删除 `draw_pile` 和旧兼容层；如果要扩展新规则，应直接基于现模型设计，不再为旧状态做回填。

## 备注

- 详细架构与插件边界说明见 `AGENTS.md`。
- 旧项目 `zzz` 引擎沉淀见 `docs/legacy_zzz_engine.md`。
- 当前规则扩展契约也已并入 `AGENTS.md`。
