# A：官方基线与协议差异

日期：2026-09-15。用户已批准实施。状态：A1 done，A2—A4进行中；前端未修改。

## 已确认事实

- GraphHarbor独立仓库测试环境Python3.11.9；langgraph1.2.11、langgraph-api0.13.0、langgraph-sdk0.4.3、langgraph-cli0.4.31。工作树版本为post28，editable安装metadata仍显示post27；对照报告不能将metadata误当源码版本。
- 官方`langgraph dev`绑定127.0.0.1:31398。启动必须在fixture目录解析相对graph路径，首次从仓库根启动因路径错误失败，已纠正；不是协议缺陷。
- 实测`POST /threads/{id}/runs/stream`传version=v2或v3均200，v3仍返回`event: values`及旧形状data，没有typed envelope。官方源码`langgraph_api/models/run.py`说明typed lifecycle走线程Protocol，不由legacy Run SSE提供。因此不能把当前GraphHarbor的Run SSE v3扩展宣称为此官方版本的等价实现。
- 官方`event_streaming/session.py:_handle_lifecycle_event`会将更深的data.namespace提升到外层，根生命周期由session拥有；`start()`发running及graph_name，非started。这与当前GraphHarbor `protocol_event`的根started映射不同，需真实线程样本确认后修复。

## 新增参考图与采集器（GraphHarbor仓库）

| 文件／函数 | 需求与实现 |
|---|---|
| `tests/acceptance_app/v3_graphs.py` | 纯确定性命名根／子图、edge、Send同名并发、ToolNode工具分派、异常与interrupt；无Dear业务或真实模型调用 |
| `tests/acceptance_app/v3.langgraph.json` | 独立注册3个验证图，不改原验收图配置 |
| `tests/acceptance_app/run_v3_probe.py:capture`、`probe` | 通过真实线程commands/events采集生命周期，并独立记录Run SSE version=v3返回内容；单场景30秒上限，原始证据保留 |

启动命令（GraphHarbor的tests/acceptance_app目录）：

```bash
../../.venv/bin/langgraph dev --config v3.langgraph.json --port 31398 --no-browser --no-reload
```

采集命令（GraphHarbor根目录）：

```bash
.venv/bin/python tests/acceptance_app/run_v3_probe.py --url http://127.0.0.1:31398 --output artifacts/v3-official-baseline.json
```

后续将在本记录追加实际结果；未采集完不得勾选A2/A3，未与GraphHarbor对照不得勾选A4或Server兼容。
