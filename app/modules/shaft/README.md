# 排轴计算模块

排轴计算是独立的配装与伤害模拟工具，页面入口为 `/shaft`。它提供队伍配装、0.1 秒动作轴、伤害结果和方案广场。

## 模块范围

- `/shaft/build`：角色、弧盘、弧盘精炼、卡带、觉醒、副词条与敌人配置。
- `/shaft/rotation`：动作轴编辑、前后台状态与伤害明细。
- `/shaft/plaza`：公开方案浏览、筛选、点赞和收藏。
- 登录用户可以保存、更新和删除自己的方案。

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

弧盘精炼的 1–5 档数据来自 Nanoka 1.2，生成文件为
`static/data/arc_refinements.json`。每张弧盘按原有录入数值映射默认
精炼等级，玩家只能在精炼 1–5 中选择；旧配装没有精炼字段时自动
补为该弧盘的默认等级。面板与已实现的弧盘 buff 使用对应 Nanoka 档位。

## 验证

```bash
python3 -m unittest discover -s tests -p 'test_shaft_*.py'
```

涉及页面交互时，还需检查 `/shaft/build`、`/shaft/rotation` 和 `/shaft/plaza` 的导航、编辑、计算与方案操作。
