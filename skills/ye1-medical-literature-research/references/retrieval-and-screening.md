# PubMed 检索与筛选辅助

脚本使用 Python 3 标准库和 PubMed E-utilities；不依赖其他 Skill。按实际问题建立查询 JSON，保存在专题目录，例如：

```json
{"topic":"成人问题的具体范围","page_size":100,"queries":[{"name":"main","term":"实际 PubMed 检索式"},{"name":"safety","term":"实际安全性检索式"}]}
```

执行 `python3 <skill>/scripts/pubmed_search.py --queries <查询.json> --out <新输出目录>`。完整返回时退出码为 0；`receipt.json` 记载查询、来源、翻译、数量、分页、分段、时间和错误；`candidates.csv` 保存题录与可得摘要及待筛状态，`raw/` 保存各批原始 XML。输出目录已有回执时拒绝覆盖。NCBI 按其限制请求，支持从环境变量读取 `NCBI_EMAIL`、`NCBI_API_KEY`；不要在报告、命令输出或交付物中写入密钥。

PubMed ESearch 单查询超过 10,000 条时，脚本按 PMID 数值范围递归切分并核对父子计数；计数不一致或页面短缺时标记失败。默认单查询上限 20,000，超出则明确失败，缩小问题或在有实际必要时调整 `--max-per-query`，不可把上限截断伪装成完整。分段机制有本地合成测试，超过 10,000 条的真实临床查询仍需单独验证。数据库更新可能导致分段计数变化，需要重跑或改用 NCBI EDirect，不应自行修补数字。

`candidates.csv` 初始均为待筛选。依据实际读到的材料形成 JSON 数组，每条含 `pmid`、`status`（纳入重点／背景参考／排除／待复核）、`scope`（题名／摘要／全文部分／全文）和具体 `reason`，可加 `study_family` 和 `review_priority`（优先／常规）。优先级只是后续阅读顺序，不是纳入结论。执行 `python3 <skill>/scripts/screen_queue.py --candidates <candidates.csv> --decisions <决策.json> --out <新筛选表.csv>`。它验证 PMID、状态、理由与可得摘要并生成新文件；不自动做筛选。可将已有筛选表作为下一轮输入，保留未判断项，不能将关键词命中或论文被取回视作人工阅读。

在报告中分别计数匹配／取回／去重、实际题名判断／摘要复核／全文阅读和待筛数量。详细说明每组检索条件、数据库、筛选尺度和限制。PubMed 元数据可能附更正／撤稿关联线索，但缺少标记不证明无撤稿；重要结论需进一步核实。
