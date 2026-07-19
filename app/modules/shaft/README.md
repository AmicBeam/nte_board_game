# 排轴计算模块

排轴计算是独立的配装与伤害模拟工具，页面入口为 `/shaft`。它提供队伍配装、0.1 秒动作轴、伤害结果和方案广场。

## 模块范围

- `/shaft/build`：角色、弧盘、弧盘精炼、卡带、觉醒、副词条与敌人配置。
- 配装页角色自身伤害占比不包含环合与倾陷伤害；环合、倾陷与角色共用贡献占比列表的行式布局和“分析详情”入口，两类伤害分别打开独立弹窗；环合弹窗可继续拆分到创生、浊燃、黯星等来源，创生复制体的伤害在占比展示中并入创生。
- `/shaft/rotation`：动作轴编辑、前后台状态与伤害明细。
- `/shaft/plaza`：公开方案浏览、筛选、点赞和收藏。
- 登录用户可以保存、更新、备份和删除自己的方案；同名保存时可改名、覆盖或取消。
- 上传从“我的排轴”卡片发起，并创建独立公开快照；之后继续保存本地排轴不会修改或移除已上传快照。
- “我的排轴”与收藏列表均支持按角色筛选，并可按最新、DPS、点赞或收藏排序。
- 伊洛伊仅对 `Player.shaft_test_whitelisted` 标记为真的账号开放。使用
  `python3 scripts/manage_shaft_test_whitelist.py add <玩家账号>` 加入白名单，
  `remove` 移出，`status` 查询单个账号，`list` 查看全部白名单账号。

详细公式、数据模型和交互设计见 [排轴模块设计](../../../docs/shaft-module-design.md)。角色动作资料见 [角色动作说明](../../../docs/shaft-character-actions.md)。

## 代码边界

- `app/modules/shaft/domain/`：数据加载、buff 注册和领域计算支持。
- `app/modules/shaft/service.py`：页面 API 的应用服务与持久化协调。
- `app/modules/shaft/templates/shaft/index.html`：页面模板。
- `app/modules/shaft/static/`：前端、计算引擎与静态数据。
- `scripts/shaft_compute.js`：后端复用前端计算引擎的 Node 包装。
- `scripts/import_shaft_xlsx.py`：离线数据导入。
- `tests/test_shaft_*.py`：公式、数据、布局和自检测试。

排轴是独立工具，不进入异象对决规则层。运行时只读取仓库内维护的数据，不依赖用户本地 xlsx。

## 永久 Buff 约定

- 需要画在角色时间轴上的永久状态统一配置为 `duration.type = time`、`ticks = 9990`、`loop_carry = true`，即以 999 秒 Buff 线表达“本轴内永久持续”；时间轴只绘制当前可视范围内的线段，不改变其实际 999 秒持续时间。
- 仅提供常驻数值、无需画 Buff 线的被动使用 `trigger.event = passive` 与 `duration.type = permanent`，默认进入动作详情的生效增益但不绘制时间轴 Buff 线。
- 不为单个角色另设永久状态或超长时长展示逻辑。伊洛伊长e的“退行（3名队友）”、白藏言灵等可见永久状态复用同一套 999 秒 Buff 线机制。

弧盘精炼的 1–5 档数据来自 Nanoka 1.2，生成文件为
`static/data/arc_refinements.json`。每张弧盘按原有录入数值映射默认
精炼等级，玩家只能在精炼 1–5 中选择；旧配装没有精炼字段时自动
补为该弧盘的默认等级。面板与已实现的弧盘 buff 使用对应 Nanoka 档位。

## 在线角色数据源

角色技能倍率、命中段数、基础回能、环合值和倾陷值以腾讯文档
[角色技能数值](https://docs.qq.com/sheet/DUEVxck1xTFpoZ0ZU?tab=000003)
的 `000003` 子表为校对来源。仓库运行时不联网读取该表；数据确认后再写入
`static/data/actions.json`、`static/data/buffs.json` 或对应说明文档。

录入与校对遵循以下口径：

- 动作与持续伤害的基础倍率取 `1级倍率`；多段动作按 `倍率呈现方式` 聚合，并据此填写 `source_formula` 和 `hit_count`。
- `固定暴击率`、`基础终结能量累积`、`基础环合值累积`、`基础倾陷值削减` 分别映射到模拟器对应字段，不用相邻等级倍率代替。
- `actions.json` 和 Buff 周期伤害保存1级基础倍率；模拟器根据角色配置的技能等级统一应用等级倍率。被动伤害只有明确不受技能等级影响时才跳过等级换算。
- 同名技能存在多个形态时，必须按 `GEName` 和描述区分。例如安魂曲Q使用“汽车”五段公式 `{0}%*4+{1}%`，不能误用其他形态或其他动作的段数。

只读核对时，先解析工作表信息，再按区域读取，避免通用全文接口在长表格中截断：

```bash
mcporter call "tencent-docs" "sheet.get_sheet_info" \
  --args '{"file_id":"PEqrMqLZhgFT"}'

mcporter call "tencent-docs" "sheet.get_cell_data" \
  --args '{"file_id":"PEqrMqLZhgFT","sheet_id":"000003","start_row":300,"end_row":399,"start_col":0,"end_col":27,"return_csv":true}'
```

## 验证

```bash
python3 -m unittest discover -s tests -p 'test_shaft_*.py'
```

涉及页面交互时，还需检查 `/shaft/build`、`/shaft/rotation` 和 `/shaft/plaza` 的导航、编辑、计算与方案操作。
