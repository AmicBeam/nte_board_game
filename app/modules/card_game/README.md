# 异象对决模块

异象对决是仓库内的网页卡牌桌游模块，页面入口为 `/card-game`。它提供账号登录后的构筑、图鉴、对局数据和单战场牌桌体验。

## 模块范围

- 使用异象道具组成主牌组，使用异能者组成异能者编队。
- 后端负责费用、抽牌、宣言、素材、揭示、环合、胜负和 AI 决策。
- 前端只负责本地部署草稿、状态展示、选择提示和结算动画。
- 玩家、登录态、构筑、房间和对局快照写入共享数据库。

现行规则、术语、卡牌设计和异能者职责以 [异象道具链卡牌设计](../../../docs/everness-item-chain-card-design.md) 为唯一设计真源。平衡流程与报告索引见 [异象对决平衡迭代](../../../docs/duel-balance-iteration.md)。

## 页面入口

- `/card-game`：模块主页。
- `/login`：登录页。
- `/profile`：账号设置。
- `/build`：构筑页。
- `/codex`：空间档案。
- `/analytics`：对局数据。
- `/table`：牌桌。

模块不再提供 `/home` 入口。

## 代码边界

- `app/modules/card_game/content/`：卡牌、异能者、构筑和通用效果定义。
- `app/modules/card_game/engine/`：对局应用服务、流程、规则、AI、投影与状态契约。
- `app/room_service.py`：房间与开局协作。
- `app/modules/card_game/templates/card_game/`：页面模板。
- `app/modules/card_game/static/`：前端脚本和样式。
- `tests/test_solo_room_flow.py`：主要接口与对局流程测试。

分层与依赖方向必须遵循仓库根目录 [AGENTS.md](../../../AGENTS.md)。卡牌私有逻辑优先留在内容定义中，不在路由或主流程增加长期硬编码分支。

## 验证

```bash
python3 -m unittest tests.test_module_routes.ModuleRoutesTest.test_card_game_module_page_and_asset
python3 -m unittest tests.test_solo_room_flow
node --check app/modules/card_game/static/js/home.js
node --check app/modules/card_game/static/js/build.js
node --check app/modules/card_game/static/js/table.js
```

涉及真实交互或动画时，还需从 `/card-game` 通过页面进入牌桌完成浏览器验收。
