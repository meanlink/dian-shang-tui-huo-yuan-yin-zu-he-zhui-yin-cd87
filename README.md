# 电商退货原因组合追因

青屿自营家居的 12 人售后与品控团队用它把退货表象、到货批号和仓库验货结论串起来。品控从高提升度组合回查票据，确认后将改进工单发给对应供应商，并跟进验证结案。

## 业务场景

售后过去在订单后台记工单，再用表格汇总客诉原因。仓库通过验货登记簿维护批号和验货结论，采购再手动把结论转给供应商。常见问题有三个：相同 SKU 的不同到货批次被合并，互斥标签进入统计，供应商提交的整改证据难以回查原始验货单。

上游输入是订单号、SKU、到货批号、售后标签和仓库验货编号。下游由本批次供应商接收整改要求，品控验证返工或归档。售后单、批次台账、组合追因和改进工单分别提供可操作的页面。在办工单可进一步登记批次实物库存隔离并安排整改复验抽检。

| 账号 | 角色 | 主要权限 |
| --- | --- | --- |
| `lin` | 售后客服 `service` | 登记、补正退货来源，查看批次、追因结果及整改进度 |
| `zhou` | 品控主管 `quality` | 登记到货、签录质检、运行追因、确认或驳回候选根因、验证整改 |
| `haixi` | 海汐杯业 `supplier` | 查看自家批次、封存与复验进度，接单并提交整改说明与凭证编号 |
| `xinmao` | 新茂金工 `supplier` | 查看自家批次、整改工单与封存和复验进度 |

演示账号的密码都是 `returns2026`。

### 一天的工作剧本

以下为模拟剧本，可按当前日期重放。seed 中的退货窗口固定使用 2026-11-07 至 2026-11-21。

1. **09:00** 林夏在售后清单核对 `RT-261125`，该单属于 `MUG-480`，尚未查到批号。
2. **09:15** 周岁查看 `RT-261126`，发现同一互斥组同时选了「沿杯口漏水」和「开合卡滞」，清单标为隔离待补。
3. **09:40** 周岁打开海汐杯业 `HX-261107-A` 批次。台账显示青屿翻盖杯 480 mL 到货 4,800 件。
4. **10:00** 在批次页发起上述窗口的追因。worker 完成后显示 27 张票据，24 张符合纳入条件，3 张排除。
5. **10:10** 选择「沿杯口漏水＋手感松动 → 密封圈压装偏位」，回查 `RT-261101` 至 `RT-261108` 的质检结论。8 张组合票据全部验出该结论，同现率 33.3%，提升度 3.00。
6. **10:30** 周岁记录复核依据、整改要求及期限，系统生成批次对应的改进工单。
7. **14:00** 海汐杯业接单，校正压装夹具，并提交凭证 `CAPA-HX-CAL-021` 请求验证。
8. **16:20** 周岁核对夹具记录和 12 件复测结果，签录验证结论并归档。

### 批次库存隔离与整改复验抽检

- **批次库存隔离**。品控从已确认根因且未结案的工单登记仓库封存凭证和盘点件数。一批一单，封存量不得超过到货数量。品控逐笔登记放行、报废或退供，处置不得超过剩余库存，隔离数量清零后才可结案。供应商仅能查看自家批次的库存隔离及复验详情。
- **整改复验抽检**。品控依据供应商最近一次提交的整改凭证抽检。抽样至少 12 件，余量不足 12 件时全部检验。零不合格才通过。同一整改版本只可签录一轮，复工重提后新旧凭证和抽检分别保留。每笔放行引用通过的抽检轮次。未抽检、抽检失败或旧版本通过均无法放行。
- `backend/migrations/002_stock_holds.sql` 在启动时增量建表。`backend/src/schemas.py` 的 `HoldStatus`、`DispositionKind`、`ReinspectionOutcome` 由 `frontend/src/pages/stock.js` 对应显示。后端事务和权限分别在 `backend/src/stock.py`、`backend/src/stock_routes.py`。

### 计算与复核口径

- 仅对指定批次、日期窗口内已签录验货且客诉标签无冲突的退货计算。缺批号的同 SKU 票据出现在排除清单，已绑定同 SKU 其他批次的票据归入各自批次。
- Python worker 用 FP-tree 及按计数加权的条件前缀路径挖掘频繁项集。解释方向为 1–2 个客诉标签指向 1 个质检结论，至少 8 张有效单，每个规则至少 3 张同现票据。
- 对 𝐴→𝐵，同现率为同现单数 ÷ 有效验货单数，置信度为同现单数 ÷ 含 𝐴 的单数，提升度为置信度 ÷ 𝐵 在当批窗口的基线率。按提升度、同现数、标签代码依次排序。
- 提升度大于 1 的组合可进入人工根因确认。品控需提交验货依据与整改要求。更新批号、客诉标签或质检会改变证据版本，待确认的旧结果须重新计算。同一批次及质检结论只生成一张整改工单。

## 快速启动

```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

| 用途 | 地址 |
| --- | --- |
| 前端 | `http://127.0.0.1:18252` |
| API 文档 | `http://127.0.0.1:19252/docs` |
| PostgreSQL | `127.0.0.1:17752`，库名和用户名均为 `returns` |

`SEED_DEMO=true` 时后端启动前自动生成演示数据。手动命令可重复执行，按自然键保留已补正或新增的业务数据。`docker compose down -v --remove-orphans` 会清除本栈的容器、网络与数据库卷。

| 服务 | 技术及职责 |
| --- | --- |
| `frontend` | Nginx 和原生 HTML/CSS/JavaScript ES modules，反向代理 `/api/` |
| `backend` | Python 3.12、FastAPI、JWT、psycopg，维护退货、质检与整改流程 |
| `worker` | PostgreSQL 持久化任务队列，执行 FP-Growth，刷新共享卷健康心跳 |
| `db` | PostgreSQL 16，持久化业务记录和审计事件 |
| `redis` | Redis 7，支持 API 请求配额 |

`.env.example` 包含 Compose 项目名、三个宿主端口、`POSTGRES_PASSWORD`、`JWT_SECRET` 和 `SEED_DEMO`。容器的 `DATABASE_URL`、`REDIS_URL` 和 `HEARTBEAT_PATH` 在 Compose 中设置。宿主端口只绑定本机。

### 本地开发

前端通过 Nginx 访问 API，无需 Node 构建。修改静态文件后执行 `docker compose up -d --build frontend`。后端与 worker 可用 `docker compose up -d --build backend worker` 启动。

如果已有本机 Redis，可用 `docker compose up -d db` 启动 PostgreSQL，再在 `backend/` 中安装和运行 Python 服务。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://returns:returns-local-db@127.0.0.1:17752/returns
export REDIS_URL=redis://127.0.0.1:6379/0
SEED_DEMO=true python -m src.db
uvicorn src.app:app --reload
```

在另一个终端以相同环境启动 `python -m src.worker`。此方式可直接访问 `http://127.0.0.1:8000/docs`。

### 目录与共享枚举

- `backend/migrations/001_returns.sql` 定义表与约束。`backend/src/{cases,trace,work}.py` 承载领域服务，`backend/src/app.py` 提供接口与中间件，`backend/src/fpgrowth.py` 为算法实现。
- `frontend/src/pages/` 对应四个业务页面。`frontend/src/api.js` 集中处理会话、引用数据和 API 请求，`frontend/src/ui.js` 提供标签、表单、状态提示及页面标题等共享组件。
- 身份 `Role` 出现在 `backend/src/auth.py`、`backend/src/app.py`、`backend/src/work.py`、SQL 的 `staff` 约束以及前端 `ui.js`、`main.js` 和各角色页面。
- 工单 `WorkStatus` 出现在 `backend/src/schemas.py`、`backend/src/work.py`、SQL 的 `improvement` 约束和前端 `ui.js`、`pages/work.js`。
- 运行状态在 SQL `trace_run` 和后端 `trace.py`、`worker.py` 定义，在前端 `RUN` 与 `pages/trace.js` 显示。复核结果在 SQL `trace_rule`、后端 `schemas.py`、`trace.py` 与前端 `DECISION`、`pages/trace.js` 使用。隔离标记由 `cases.py` 生成，由 `trace.py` 汇总，在前端 `FLAGS`、`pages/returns.js` 和 `pages/trace.js` 显示。
- 验收脚本、业务追踪表和截图见 [test-artifacts/gb-1053](../../test-artifacts/gb-1053/TESTING.md)。

## 许可

本项目供工作区内部演示使用。

### 退供运单与货款冲抵

品控用仓库 `vendor_return` 处置流水登记唯一退供运单，发出数量沿用已封存的出库量。供方提交签收件数和凭证，短件停在待裁定状态。品控补录承运差异依据后确认货款可结算件数。货款冲抵为结算件数乘单价减约定扣减运费，供应商能确认或退回自家账单。重议使用新编号并保留已退回版本。
