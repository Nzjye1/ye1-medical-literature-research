# Zotero 和 PubMed 追踪

## Zotero

仅当 Zotero 正在本机运行且已启用本地 API 时，`python3 <skill>/scripts/zotero_preview.py --candidates <候选表.csv> --pmids <逗号分隔PMID>` 可只读比较个人文库；可加 `--collection <分类key>` 限定分类。它按 DOI 和可识别的 PMID、URL、Extra 比较；DOI 相同但 PMID 不同、仅 DOI 相同或相同 PMID 的 DOI 冲突均提示人工核对，而非自动判重。它不检查子笔记或外部文库；未匹配仍需确认。遇到 403、应用未运行或接口不可用应如实说明，不擅自修改用户配置。

`python3 <skill>/scripts/export_ris.py --candidates <候选表.csv> --pmids <逗号分隔PMID> --out <新文件.ris>` 生成选定文献 RIS，包含可得题名、作者、年份、期刊、DOI、PubMed 链接和 PMID，不包含 PDF。M2 字段由本次 Zotero 9.0.6 测试映射至 PMID；其他版本或导入器可能不同。提供给用户导入，或在用户要求保存且目标与权限明确时选择可用导入方式，先查重、确认实际文库／分类并在导入后回读；禁止对结果未知的写入盲目重试。

隔离测试中，Zotero 9.0.6 本地 API 可读；其 Connector 的 RIS 导入写到 Zotero 当前选中位置。连接器导入不是 Zotero 10+ 的本地 API 写入功能，也不能据此声称已自动选择或控制任意分类。当前脚本不执行导入，不接收或保存账号密钥。真实用户库、远程同步、其他 Zotero 版本及 PDF 导入需各自验证。[Zotero Local API](https://www.zotero.org/support/dev/web_api/v3/local_api)

## 可重复的手动或定时追踪

先用上面的检索脚本建立完整基线。配置中的每组主题查询必须与基线中完整执行过的查询一致：

```
python3 <skill>/scripts/track_pubmed.py init --queries <追踪查询.json> --baseline <完整检索目录> --state <专题状态.json>
python3 <skill>/scripts/track_pubmed.py run --state <专题状态.json> --runs-dir <专题运行目录>
```

如果该方向已建立[本地文献库](local-library.md)，运行时加 `--library-topic <主题目录>` 可在游标推进前合并本轮题录；再加 `--save-fulltext` 可为本轮返回且尚未保存全文的未排除题录尝试保存 PMC 数据集中的全文。文献库整体更新失败时游标不推进；单篇全文未找到或下载失败则保留记录和状态，不能声称全文均已获取。追踪脚本不会自行创建定时任务。

每轮按上次成功开始时间回退 3 天，以 PubMed `[crdt]` 和 `[lr]` 查询当前范围；按 PMID 去重并比较若干书目字段。`delta.json` 分开记录本轮新发现、已知题录变化及无变化；新发现不等于新发表，书目变化也不自动等于更正／撤稿。每次检索只有完整、数量一致时才推进状态；失败留下日志，不推进。状态文件有互斥锁；中途异常终止遗留锁时先确认无运行进程，再处理锁文件。

3 天重叠不能保证捕获所有延迟索引、匹配条件变化、已删除或不再匹配的题录；定期重新跑全量检索并核对重要论文状态。此原型尚未验证跨机器迁移、网络断线后宿主重试、强制终止后的通知恢复或长期运行；需要人工复核新文献。

用户明确要求定时执行时，使用当前宿主的官方调度入口，将上面的 `run` 及状态目录写入任务，限定职责、时区、频率、可访问的本地路径和需要报告的变化。不要让未指定的测试任务持续运行。宿主调度器的实际触发、断电恢复、权限和通知另需实测；直接手动运行或创建暂停任务都不证明自动触发成功。没有可用宿主时保留手动更新方案。
