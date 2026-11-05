# 本地医学文献库

不依赖 Zotero。优先使用用户已有或指定的库；否则放在用户文档目录的“医学文献库”，无法使用时选择持久工作区并报告路径。每个主题单独建目录：文献清单 CSV、可点击的文献索引、全文文件夹、个人笔记以及检索与追踪资料。父目录的“研究方向索引”由脚本更新。索引是自动生成文件；不在里面保存个人笔记。

## 建立与继续主题

```text
python3 <skill>/scripts/local_library.py init --topic <库/主题目录> --name <主题名称>
python3 <skill>/scripts/local_library.py import --topic <库/主题目录> --candidates <候选或筛选表.csv>
python3 <skill>/scripts/local_library.py fetch --topic <库/主题目录> --relevant
```

导入表使用 `pmid`、`doi` 或 `local_id` 作为稳定标识。没有 PMID 和 DOI 的其他来源，可为单篇分配稳定的字母数字 `local_id` 并保存来源链接；不要仅凭相同题名自动合并。相同 PMID 按一条更新；不同 PMID 即使 DOI 相同也保留；仅有 DOI 的记录和后来取得 PMID 的记录不会自动合并，须人工确认。同 PMID DOI 不一致时保留原值并标记冲突。默认重新导入不会覆盖已作筛选判断或已保存全文；确有新判断时可显式使用 `--update-screening`。

`--relevant` 覆盖重点、背景、待复核、待筛选等未排除条目，不仅是重点文献；用户需要包括排除项时用 `--all`。大量文献可用 `--limit 25` 分批，普通续跑会跳过已尝试条目；确需重查未保存条目时用 `--retry`。也可用 `--pmids 123,456` 或 `--ids PMID:123,DOI:10.1234/example` 定向处理。保存状态、来源、版本和检查时间逐条写入文献清单；进程退出后仍可续跑。保存全文与已阅读是两件事。

自动下载仅使用 [PMC 官方开放数据集](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)和其公开元数据，不批量抓取 PMC 网页。优先 PDF，再尝试公开全文文本或 XML；核验文件格式、标识及可用时的校验值，不覆盖不同的已有文件。数据集各篇许可可能不同，库用于用户本地研究，不把论文全文打入 Skill 安装包。缺少 PMCID、PMC 数据集没有文件、网络错误或文件超过大小上限，分别记录并保留题录；这些状态不意味着其他渠道没有全文。

可按需另查合法开放来源或用户机构已有权限；如果用户提供 PDF、TXT 或正文 XML，可以复制进库（不移动原文件），例如：

```text
python3 <skill>/scripts/local_library.py attach --topic <库/主题目录> --pmid 123 --file <用户提供的全文.pdf>
```

没有 PMID 可使用 `--doi` 或 `--local-id`。脚本不获取或保存账号密钥，也不绕过付费墙。多个不同版本或补充材料须另行核对；自动下载只保存主文，不声称已取得补充材料。

除 PMC 数据集外，Agent 可把公开 PMID／DOI 写入任务目录中的 JSON `{"items":[{"pmid":"真实PMID"},{"doi":"真实DOI"}]}`，运行 `python3 <skill>/scripts/find_fulltext_links.py --input ids.json --out links.json` 查询 Europe PMC 的全文链接与可用状态。一次最多 50 项；返回的候选有来源、标识、论文类型及链接，`links_only_not_fetched` 明确表示**尚未下载或阅读**，不得据此称取得全文。查询失败记录错误并可按需重试；记录可能是预印本或作者稿，应核对版本与同一研究身份。用宿主实际可用工具打开／取得合法可用的资料，或用 `attach` 导入用户有权提供的全文；未发现链接不代表其他渠道没有全文。

主题报告用不覆盖旧报告的文件名保存在主题目录，报告引用的本地文件保留可访问路径。通过主题索引打开，或按题名、作者、年份、PMID、DOI 搜索：

```text
python3 <skill>/scripts/local_library.py search --root <医学文献库> --term <关键词>
python3 <skill>/scripts/local_library.py reindex --topic <库/主题目录>
```

如进程异常中断留下 `.文献库.lock`，先确认对应主题没有运行中的库更新，再处理锁文件。文件保存在本地；换设备需自行复制或使用用户选定的同步方式。

## 持续追踪

在主题的“检索与追踪”目录保留检索配置、完整基线和状态。沿用 [PubMed 追踪说明](zotero-and-tracking.md)初始化状态；运行时给出主题目录：

```text
python3 <skill>/scripts/track_pubmed.py run --state <主题状态.json> --runs-dir <运行目录> --library-topic <库/主题目录> --save-fulltext
```

检索结果完整时合并题录，为本轮返回且尚无本地全文的未排除文献尝试保存 PMC 可用全文；取得全文失败不会伪装为成功，记录在文献清单中。历史条目若未在本轮返回，可按需用 `fetch --relevant --retry` 再检查。若文献库更新整体失败，追踪游标不推进，可修复后重试。设置定时任务仍需可用宿主及用户要求；没有调度时可手动运行。
