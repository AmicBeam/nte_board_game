# NTE Board Game Architecture

## 目标

本项目是一个独立的 Flask 网站，提供异环主题的网页牌桌，并通过数据库保存玩家、登录态、构筑和对局状态。
与机器人交互的代码位于 `plugins/` 目录；网页端只负责展示状态和发送用户操作，所有规则计算都在后端完成。

## 设计宗旨与更新方向

游戏应同时满足轻度游玩、逻辑挑战、随机刺激和强成就反馈。每次更新都应优先降低玩家的记忆负担和操作负担，让玩家能快速理解当前局势、做出选择并看到结果；同时通过清晰的规则关系、可预判的风险收益和逐步抬升的难度，保留足够的推理空间与挑战感。随机性应服务于刺激感，而不是制造无力感：随机事件、掉落、敌人和地图变化都要给玩家留下应对窗口、补救手段或高风险高回报的决策点。胜利应来自“看懂规则、抓住机会、承担风险并成功翻盘”的过程，让玩家在轻量流程里持续感到紧张、惊喜和掌控感。

后续更新优先围绕“局内刺激循环”展开：增加可读的风险提示、即时收益反馈、随机奖励分支、短链路目标和可逆转局势的爆点；避免纯惩罚、长时间空转、信息隐藏过重或只能被动承受的失败。任何新增角色、道具、地图物件和敌人机制，都应让玩家至少多一个有意义的选择，而不是只增加额外计算。

## 分层

- `app/config.py`
  统一管理配置、数据库路径、token 过期时间、密码策略等。
- `app/db.py`
  初始化 `peewee` 数据库连接与建表流程。
- `app/models.py`
  定义玩家、密码、token、构筑、对局快照等模型。
- `app/dao.py`
  提供数据库读写方法，避免路由和服务层直接操作模型细节。
- `app/auth.py`
  负责 token 创建、校验，以及 Flask 路由鉴权装饰器。
- `app/content/`
  通过目录化 Python 文件维护角色、道具和地图内容，由 `loader.py` 自动收集。
- `app/engine/events.py`
  定义回合阶段、移动阻挡、地图交互、伤害包、战斗流程等事件常量，并维护阶段事件序列。
- `app/engine/event_bus.py`
  统一执行事件队列；支持 `default handler`、`append`、`replace` 三类语义。实例 hook 可读取 payload、修改状态，并继续压入新的事件。
- `app/engine/damage.py`
  统一构造和结算伤害包；默认链路为 `CREATE_DAMAGE_PACKAGE -> APPLY_DAMAGE_PACKAGE -> DAMAGE_APPLIED`。
- `app/engine/effects.py`
  管理运行时效果实例；支持按来源注册、查找、移除，以及聚合运行时数值。
- `app/engine/game_service.py`
  核心规则层。负责从数据库加载对局快照，按阶段顺序派发事件，再把结算后的快照写回数据库；主链路只保留通用默认行为，不写具体 item / passive / map object 效果。
- `app/routes.py`
  提供 HTML 页面和 JSON API。只做参数校验、鉴权和调用服务。
- `app/templates/` + `app/static/`
  前端页面。前端不做规则计算，只根据后端状态渲染页面和发送操作；页面拆分为登录页、资料页、主界面、构筑页和对局页。
- `plugins/nte_account_db.py`
  插件侧独立数据库桥接层。直接连接同一个数据库文件，并使用相同表名进行数据交互，不引用 `app/` 下的业务代码。
- `plugins/nte_account.py`
  机器人桥接层，提供“注册账号”“重置密码”命令；只通过 `plugins/nte_account_db.py` 访问数据库。QQ 号作为账号，附带用户名时按最多 8 个汉字截断保存。
- `scripts/seed_mock_account.py`
  当前环境不运行机器人时，用于预置 mock 账号和密码，便于联调；该脚本直接写共享数据库，不参与网站主链路启动。

## 数据流

1. 玩家向机器人发送注册指令。
2. 玩家先向机器人 `Fairy` 发送 `注册账号` 或 `重置密码` 指令；QQ 号就是账号。
3. `plugins/nte_account.py` 通过 `plugins/nte_account_db.py` 直连共享数据库，创建或查找玩家并生成登录密码。
4. 玩家在浏览器登录页输入玩家号和密码。
5. 后端校验密码后签发 token，浏览器将 token 存储在本地。
6. 登录后玩家可在网页修改用户名和密码；用户名最多保留 8 个汉字。
7. 浏览器后续请求在 `Authorization: Bearer <token>` 中携带 token。
8. 路由层通过 `app/auth.py` 获取当前玩家，再调用 `game_service.py` 执行逻辑。
9. 游戏状态以 JSON 快照方式保存到数据库，页面刷新后可重新读取并恢复。

## 插件边界

- `plugins/` 目录下的代码不能直接引用 `app/` 下的 Python 模块。
- 插件与网站后端之间只通过共享数据库表进行交互。
- 因此插件侧会维护一份最小化的数据库连接和表映射，只覆盖注册密码所需字段。

## 持久化策略

- 玩家信息、构筑、密码、token、对局快照全部进入数据库。
- 对局状态不保存在 Flask 进程内存中。
- 每次用户操作都会：读取快照 -> 计算 -> 写回快照。
- 因此前端刷新、服务重启后仍可恢复最后一次落库的状态。
- 当前对局状态不再保留兼容层，也不再维护 `draw_pile`。

## 当前状态模型

- 所有道具在开局时一次性置入 `hand`，当前规则没有抽牌、洗牌和牌库机制。
- 运行时状态最少包含：
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
- `active_effects` 用于承载“会持续存在并响应事件”的效果实例，不要再把这类能力写回临时状态桶。

## 内容扩展规范

- 新角色：在 `app/content/characters/` 下新增一个 Python 文件，导出 `CHARACTER`。
- 新道具：在 `app/content/items/` 下新增一个 Python 文件，导出 `ITEM`。
- 新地图：在 `app/content/maps/` 下新增一个 `.json` 文件，并在 `app/static/images/maps/` 下放置对应 PNG 背景。
- 地图 JSON 的 `tiles` 使用按层字符串矩阵，配合 `legend` 解释字符含义；加载器会按每层数组推导尺寸并展开为运行时格子列表。
- 地图起始点使用 `legend` 中 `type=entry` 的符号表达，不在顶层额外配置 `start`；不同层可以拥有不同宽高。
- 每一层 `tiles` 都应裁掉外围全空白行列，避免前端按无效空白区域计算显示比例。
- 地图 JSON 默认只写 `type` 和必要参数；只有当 `type` 与实际地图物件处理模块不一致时才写 `object_id`。不要内嵌道具名称、图标、价值等产物数据，这些信息由道具和地图物件定义注册。
- 敌人和地图格子的掉落都通过地图级 `loot_tables` 配置，并在对应格子或敌人上引用战利品表 ID。
- 随机地图产物使用 `type=random` 格子，初始化时按 `loot_table_id` 变身为具体道具或地图物件；不要再用独立坐标列表叠加随机掉落。
- 怪物位置由地图矩阵中的 `type=monster` 符号决定，怪物配置只写属性与掉落表，不重复写坐标。
- 加载器会自动扫描并注册上述内容，主链路不应硬编码完整目录内容。
- 地图物件定义位于 `app/content/map_objects/`；tooltip、阻挡类型和交互规则都应定义在各自文件内，不写回地图布局文件。

## 事件规则约束

- 事件常量统一定义在 `app/engine/events.py`，不要在主链路里直接拼裸字符串。
- `game_service.py` 负责阶段推进和默认规则，不负责保存角色/道具/地图物件的具体效果细节。
- 角色与道具的被动效果应尽量写在各自内容文件里，由内容层导出 hook。
- hook 应通过事件 payload 获取入参，并允许继续压入新事件，避免回到主流程里追加条件分支。
- 当某条规则需要“改写默认主链路”时，优先使用事件总线的 `replace` 语义，而不是在 `game_service.py` 增加 if/else 分支。
- 当某条规则需要跨多个事件保留状态时，优先注册 `runtime_effect`，而不是新增临时状态字段。
- 当某条规则由区域进入/离开决定生效时，优先使用 `zone_effects`。
- 地图阻挡判断也应走通用事件位，例如 `MOVE_BLOCK_CHECK`，不要把“钥匙消耗”“开门”之类规则写死在引擎里。

## 规则契约

### 什么时候加 `GameEvent`

- 当某段规则需要被多个内容定义共享监听时，加新的 `GameEvent`。
- 当主流程里的一个时机已经稳定存在，但内容层拿不到它时，加新的 `GameEvent`。
- 如果只是单个内容私有的小逻辑，不要为它单独加事件，优先挂在已有事件上。

### 什么时候用 `runtime_effect`

- 需要跨多个事件保存运行时状态时，用 `runtime_effect`。
- 需要“本回合生效”“下回合消费”“受击后衰减”这类状态时，用 `runtime_effect`。
- 新设计不要再引入 `temp` 一类临时状态桶；关键效果应显式进入 `runtime_effect` 或事件 payload。

### 什么时候用 `zone_effects`

- 当效果的生命周期由区域决定时，用 `zone_effects`。
- 进入某个区就注册，离开某个区就移除，这类都属于 `zone_effects`。
- 当前约定：
  - `hand`：允许常驻姿态、光环、提示类效果。

### 什么时候允许 `replace`

- 只有带明确默认处理器的主链路事件允许 `replace`。
- 当前允许 `replace` 的事件：
  - `turn_begin`
  - `dice_rolled`
  - `action_phase_begin`
  - `move_phase_begin`
  - `direct_attack`
  - `ranged_attack`
  - `apply_damage_package`
- 其他事件即使声明 `mode: replace`，事件总线也会退回成 `append`。

### Damage Package 字段

- 基础字段：
  - `source_type`
  - `source_name`
  - `source_id`
  - `target_type`
  - `target_id`
  - `target_name`
  - `attack_kind`
  - `allow_block`
- 结算字段：
  - `base_amount`
  - `amount`
  - `bonus_damage`
  - `reduced_damage`
  - `blocked_damage`
  - `reflected_damage`
  - `final_damage`
  - `target_hp`
  - `target_defeated`
- 扩展字段：
  - `tags`
  - `meta`

### 伤害包修改约定

- `CREATE_DAMAGE_PACKAGE`：用来改写伤害值、加伤、减伤、标记反伤。
- `APPLY_DAMAGE_PACKAGE`：用来替换默认扣血逻辑，只有非常特殊的结算才应使用 `replace`。
- `DAMAGE_APPLIED`：用来做战后反应，例如反震、吸血、击杀后效果。

### 最小 Item 模板

```python
from typing import TYPE_CHECKING

from app.engine.effects import build_runtime_effect, register_runtime_effect, remove_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def item_played(context: 'EventContext') -> None:
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='sample_item',
        effect_id='sample_item_turn_buff',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'attack_bonus': 2},
    ))
    context.payload['resolved'] = True


def item_turn_end(context: 'EventContext') -> None:
    remove_runtime_effect(context.state, str(context.instance_id))


ITEM = {
    'id': 'sample_item',
    'name': 'Sample Item',
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: item_played,
    },
    'zone_effects': {
        'hand': ['sample_item_hand_aura'],
    },
    'runtime_effects': {
        'sample_item_hand_aura': {
            'initial_data': {
                'block_bonus': 1,
            },
            'event_hooks': {},
        },
        'sample_item_turn_buff': {
            'event_hooks': {
                GameEvent.TURN_END.value: item_turn_end,
            },
        },
    },
}
```

### 最小 Passive 模板

```python
from typing import TYPE_CHECKING

from app.engine.damage import apply_damage_bonus
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def passive_on_create_damage_package(context: 'EventContext') -> None:
    if context.payload.get('source_type') != 'player':
        return
    apply_damage_bonus(context.payload, 1)


CHARACTER = {
    'id': 'sample_character',
    'name': 'Sample Character',
    'passive': '直接攻击伤害 +1。',
    'passive_events': {
        GameEvent.CREATE_DAMAGE_PACKAGE.value: passive_on_create_damage_package,
    },
}
```

## 类型标注约束

- 函数签名应尽可能显式写明参数类型与返回类型，优先覆盖事件系统、规则层、DAO 层和工具层等会被项目内其他模块直接调用的函数。
- 为避免循环引用，可参考旧项目使用 `TYPE_CHECKING` 加字符串类型注解的方式，不要因为担心循环引用而完全省略类型。
- `EventContext`、快照字典、hook callable 等公共类型应尽量集中在引擎类型模块中复用，避免在各文件重复发散定义。
- `routes.py` 这类主要由 Flask 框架回调的入口函数，不强制补返回值类型；优先保证项目内显式调用链上的函数签名清晰。

## 前端约束

- 前端不计算骰子、移动、战斗、奖励和掉落结果。
- 前端只做渲染、提示、按钮禁用控制和 token 携带。
- 地图以 PNG 为背景，交互点通过图标叠加展示；悬停提示由后端返回的说明文案驱动。
