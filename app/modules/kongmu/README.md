# 空幕计算模块

空幕计算是独立网页工具，页面入口为 `/kongmu`，用于选择角色与卡带并生成可用的空幕搭配方案。

## 模块范围

- 页面展示角色、卡带和计算结果。
- 浏览器只提交选择并渲染结果，方案计算由后端应用服务完成。
- 该模块不依赖异象对决的房间、对局快照或规则结算。

## 代码边界

- `app/modules/kongmu/service.py`：catalog 与布局方案计算。
- `app/modules/kongmu/templates/kongmu/index.html`：页面模板。
- `app/modules/kongmu/static/`：页面脚本、样式与模块静态数据。
- `app/routes.py` 中 `/kongmu`、`/api/kongmu/catalog` 和 `/api/kongmu/plan`：页面与 API 入口。

新增算法应留在模块服务中，路由只做输入解析、并发保护和错误转换。

## 验证

```bash
python3 -m unittest tests.test_module_routes.ModuleRoutesTest.test_kongmu_module_page_catalog_and_asset
```

涉及交互调整时，还需通过 `/kongmu` 检查角色选择、卡带选择、方案生成和返回工具主页。
