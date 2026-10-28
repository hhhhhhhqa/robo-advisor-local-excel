# 本地 Excel 投资组合工具

每个人下载一份，Setup 一次，在自己的桌面 Excel 中记录交易。交易改变后自动使用本地缓存计算持仓、现金、净值、收益和回撤，并生成资产走势图。**只有用户自己点击 Update（或主动运行外部 2_Update）时，才请求资产价格和汇率。** 打开 Excel、编辑交易和自动计算都不会请求行情 API。

当前为 **1.1 测试版**。缓存计算、手动下载分离、独立数据、宏源码一致性和失败保护有自动测试；新宏已在 Mac 原生 Excel 中运行并创建按钮。Excel 内完整刷新、事件触发和结果导回的组合流程尚未完成原生实测，Windows 原生 Excel 的界面行为也未实测。外部更新入口保留作为备用。

## 首次使用

下载 [1.1 测试包](https://github.com/hhhhhhhqa/robo-advisor-local-excel/releases/tag/v1.1.0-beta.1)，把 ZIP **完整解压**到自己的本地文件夹。Windows 双击 `1_Setup.cmd`；Mac 双击 `1_Setup.command`。Setup 会在项目文件夹下载 Python 和依赖，并生成 `Portfolio.xlsm`；Mac 还会安装 Excel 调用本地程序所需的桥接文件。无需自行安装 Python。**Setup 不下载行情。**

打开 `Portfolio.xlsm`，允许这个文件运行宏。首次使用由用户手动点击表内 **Update**，获取初始行情和汇率。首次下载历史数据可能需要几分钟。以后是否、何时获取新行情，都由用户自己点击 Update 决定。

支持 Windows 和 Mac 桌面 Microsoft Excel。需要保留整个工具文件夹；仅发送 Excel 文件不足以运行 Python 功能。发给别人时请发原始 ZIP，让对方自行 Setup，不要发送包含自己交易、缓存和运行环境的工作文件夹。

## 日常使用

在交易输入区填写或修改记录。停止编辑约两秒后，程序自动读取本地缓存重新计算，生成成交记录、逐日净值、持仓和现金余额，并更新图表。一次填写尚未完成时，状态区可能提示补全输入；继续完成填写后会再次计算。自动计算会使用未保存的输入副本，完成后仍按通常习惯保存 Excel。

想获取新行情时，**自己点击 Update**。按钮会刷新资产价格和四组汇率，将历史数据按日期去重合并到本地缓存，然后重新计算并保存工作簿。没有定时下载，没有打开文件时的自动下载；旧版 E5/E6 的 Yes/No 开关不再控制行情请求。新界面在这两格说明“Manual Update”和“Automatic (local)”。

交易需要用户输入，资产走势图由交易记录及已缓存的历史价格、汇率计算生成。修改旧交易会重新计算受影响的历史走势。数据只覆盖已下载的交易日；缺少价格、汇率或输入无效时，H6 状态区会显示 **RESULTS NOT CURRENT** 和原因，原有结果保留但不能当作本次输入的有效结果。用户可按提示修正输入，或自行决定点击 Update 补充数据。

## 如何填写 Dashboard

| 位置 | 内容 | 填写方式 |
| --- | --- | --- |
| B4:B8 | USD、JPY、EUR、AUD、CNY 初始现金 | 非负；日元整数，其余币种最多两位小数；至少一项大于零 |
| E3 | 估值日期 | 留空为缓存中最新 ETF 交易日；指定日期必须有美国市场收盘价 |
| E4 | 年化无风险利率 | 如 `0.04` 或 `4%` |
| A27:F226 | 用户的交易记录 | 按日期升序填写；同日按行顺序执行；最多 200 笔 |
| E17 / E18 | 本地行情和汇率覆盖日期 | 用于判断数据新旧；点击 Update 后不一定存在今天的收盘价 |
| H6:M7 | 当前计算状态 | 缺数据、输入问题和更新结果显示在这里 |

输入表六列分别是日期、操作、ETF、股数或金额、支付币种、换入币种。支持 19 只美国上市 ETF，名单在 `config/assets.json`。

| Date | Action | ETF | Shares / amount | Cash currency | To currency |
| --- | --- | --- | ---: | --- | --- |
| 2026-08-27 | Buy | SPY | 2 | USD | 留空 |
| 2026-08-28 | Sell | SPY | 1 | USD | 留空 |
| 2026-08-28 | Exchange | 留空 | 500 | USD | JPY |

Buy/Sell 使用正整数股数，换入币种留空；Exchange 使用换出币种金额，ETF 留空，换入币种必须不同。不能产生负现金或超额卖出。交易日期必须是 Excel 日期和存在行情的美国交易日。

## 结果和计算口径

同一张 Dashboard 显示持仓、各币种现金、模拟成交记录、逐日 USD 组合价值，以及收益率、Sharpe、最大和当前回撤。日期滑块改变历史指标及图中标记；持仓和余额表显示估值日结果。

沿用上游的日收盘价模拟，未接券商，不会实际下单。ETF 使用 USD 收盘价，非美元现金使用当日或之前最近一期汇率，最多滞后五个自然日，不使用未来汇率。Sharpe 按 252 个交易日年化及 E4 利率计算；样本不足或波动为零时显示 n.a.。不含分红、手续费和买卖价差。资产历史价格不会凭空补齐，ETF 上市前也没有其收盘价。

行情来自 Yahoo Finance。一次 Update 会涉及多个资产和汇率请求；API 调用额度、网络与服务可用性仍由数据提供方决定。ETF 不纳入当前尚未完成的纽约交易日，汇率不纳入当前 UTC 日。

## 备用入口与失败恢复

表内宏无法使用时，保存并关闭 `Portfolio.xlsm`，主动双击 `2_Update` 获取最新行情并计算。若只想按已有数据重算、不请求 API，可双击 `3_Recalculate`。外部程序要求关闭工作簿，以免覆盖正在编辑的内容。

Python 先在临时文件计算，成功后才交给 Excel 接收结果。行情两部分全部下载成功后才更新本地缓存；API 下载中途失败会保留旧缓存。每次成功计算的输入副本保存在 `local_data/backups`，保留最近五份。计算失败不覆盖原交易文件；详情在 `local_data/last_update.log`。恢复时先关闭工作簿，再把选定的备份复制到根目录并命名为 `Portfolio.xlsm`，保留原文件作为另一个备份。

初始数据缺失时请自行点击 Update。`insufficient cash/shares` 表示余额或持仓不足；`no ETF close` 需要检查日期及行情范围；`FX rate is stale` 需要检查汇率覆盖。若未运行 Setup 或本地环境丢失，程序会提示运行 Setup，自动计算不会借机联网安装依赖。

Mac 若提示启动文件没有执行权限，可在终端输入 `chmod +x `（末尾有空格），把三个 `.command` 文件拖入后按回车。如系统限制打开，请按系统提示允许可信下载来源。只对这个工作簿启用宏，不需要调低 Excel 全局安全设置。受管理的公司电脑可能需要管理员允许本地程序。

## 文件、升级和开发

`Portfolio.xlsm` 是个人工作文件，`local_data/market` 是独立行情缓存，`local_data/backups` 是输入备份。`.tools`、`.runtime`、`.venv` 为本地环境，均与个人数据一起排除在 Git 之外。工具没有上传交易的功能。

从 1.0 升级：解压到新文件夹，将旧的 `Portfolio.xlsx` 及需要沿用的 `local_data/market` 复制过来，再运行新包的 Setup。程序把旧文件的内容迁移到 `Portfolio.xlsm`，并保留旧文件。已经存在的 `Portfolio.xlsm` 不会被 Setup 重置；因此不要拿旧测试版 xlsm 直接替代新模板，否则其中的宏也会保持旧版。移动整个工具文件夹后需重新 Setup 修复运行环境路径。

本项目基于 [winstonFang05/cuhk-cdas-robo-advisor](https://github.com/winstonFang05/cuhk-cdas-robo-advisor)，上游提交 `53743116b40cc2638620acded8f4d44cfc725405`，说明保存在 `UPSTREAM.md`；上游未另外声明开源许可证。1.1 增加 Excel 按钮、工作簿事件、本地缓存计算和手动行情请求的分离。

开发测试可运行 `uv sync --extra test` 与 `uv run pytest -q`。宏源码保存在 `excel_button`，模板中的源码由测试独立提取核对。修改源码后运行 `python scripts/build_workbook.py`，它使用固定版本的 [ovba-writer](https://github.com/kay-ws/ovba-writer) 按 MS-OVBA 重建源码项目，由收件人的 Excel 编译；此步骤需要 Go，仅开发者需要。macOS/Windows CI 检查初始化和 Python 工作流，不代表两个系统的原生 Excel 界面都已验证。
