---
name: showcase-notes
description: Analyze, repair and verify the bundled Python CSV sales-report project.
---

# 销售报表工程任务

## 工作区与资源

- /workspace/sales.csv：实际销售数据，quantity 是数量，unit_price 是单价。
- /workspace/report.py：可运行脚本，初始版本有一个明确的教学缺陷。
- /workspace/README.md：任务和正确结果说明。
- /skills/ 为只读技能资源；它不是宿主机路径，也不需要部署者填写开发机目录。

文件工具使用 /workspace/report.py；execute 的工作目录是 /workspace，
因此运行 python report.py 即可。程序、CSV 和生成的产物都在同一个线程工作区。

## 根据目标开展工作

只要求分析：使用 read_file、grep、glob 或 research，解释原因，不修改、不执行。

要求修复：
1. 读取实际代码和数据；任务复杂时用 write_todos 维护状态。
2. 给出最小修改，可委派 general-purpose 实现助手。
3. 文件修改和 execute 通过官方 HITL 审批后执行。
4. 用 Decimal 计算金额，乘以数量；原始样例正确总金额为 43.50。
5. 留下一个可以运行的检查，再执行检查；如实报告退出码与结果。

查询 Python 标准库使用方式时，可调用 fetch_documentation 获取
https://docs.python.org/3/library/csv.html 或
https://docs.python.org/3/library/decimal.html 。

拒绝审批后停止该操作。不要换用 execute 绕过被拒绝的文件修改。
不得把工具调用记录、计划更新或“done”文本当成测试已经通过。
