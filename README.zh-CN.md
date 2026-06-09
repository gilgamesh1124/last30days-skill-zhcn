# /last30days

<p align="right"><b>中文</b> · <a href="README.md">English</a></p>

**一个由 AI agent 驱动的搜索引擎——按点赞、转发和真金白银排序，而不是按编辑口味。**

> **本仓库是 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) 的 fork**，把引擎扩展到中文平台。**Bilibili（B站）** 已上线，**微博** 和 **知乎** 在路线图上。详见 [中文平台（本 fork）](#中文平台本-fork)。其余部分跟随上游。

> 本文是面向中文读者的适配版，并非英文 README 的逐字翻译——例子换成了中文语境，西方流行文化的演示已省略。完整的功能清单和最新命令以英文 [README](README.md) 和 [skills/last30days/SKILL.md](skills/last30days/SKILL.md) 为准。

---

## 它解决什么问题

每个平台都是一座围墙花园：有自己的 API、自己的 token、自己的登录态。Google 搜不到 Reddit 评论或 X 帖子；ChatGPT 跟 Reddit 有合作但搜不了 X 和 TikTok；Gemini 有 YouTube 没有 Reddit。**中文世界这个问题更严重**——Google、Reddit、X 几乎触及不到微博、知乎、B站、小红书上正在发生的讨论。

`/last30days` 让一个 AI agent **同时**搜索所有这些平台，按真实用户的互动度互相打分，再由一个 AI 评审合成成一份简报。

```
/last30days 长沙麻将
/last30days 英伟达 vs AMD
/last30days OpenClaw --emit=html
```

社交相关性，不是 SEO 相关性。一条 1500 赞的帖子比一篇没人读的博客信号更强。

---

## 数据源，由人民打分

| 数据源 | 它告诉你什么 |
|--------|--------------|
| **Bilibili（B站）** | 中国的视频广场。按 B站用户真正花出去的互动排序——投币（每周有限预算）、收藏、点赞、弹幕。公开 WBI 签名搜索，零配置、免登录。 |
| **小红书（RED）** | 中文生活方式与种草层。笔记按点赞、评论、收藏排序。 |
| **Reddit** | 未经修饰的真实声音。带顶赞数的热评，公开 JSON 免费抓取。 |
| **X / Twitter** | 热评、专家长帖、突发反应。最先知道，最先吵架。 |
| **YouTube** | 45 分钟的深度长视频，整段字幕里搜出最值得引用的 5 句话。 |
| **TikTok / Instagram / Threads** | 创作者视角与口语字幕，文化信号。`SCRAPECREATORS_API_KEY` 设好后自动启用。 |
| **Hacker News** | 开发者共识。技术人真正争论的地方。 |
| **Polymarket** | 不是观点，是赔率，背后是真金白银。 |
| **GitHub** | 对人：PR 速度、按 star 排序的仓库、release notes。对话题：issue 与讨论。 |
| **Perplexity / Web** | 带引用的联网搜索与编辑性报道。众多信号之一，而非唯一。 |

合成结果按真实用户的互动度排序。

---

## 中文平台（本 fork）

围墙花园问题在中文科技圈尤其严重：决定一次产品发布、一场政策反应的对话，就活在微博、知乎、B站、小红书里——藏在 WBI 签名和登录墙背后，对所有西方 AI 隐形。

本 fork 把同一套"并行搜索 + 互动排序"的引擎延伸进了那个世界。

| 平台 | 状态 | 实现方式 |
|------|------|----------|
| **Bilibili（B站）** | ✅ 已上线 | 公开 WBI 签名搜索，自动获取 `buvid3` cookie，零配置。按 投币 > 收藏 > 点赞 > 弹幕 > 播放 排序。 |
| **小红书（RED）** | ✅ 已上线 | 通过 `xpzouying/xiaohongshu-mcp` REST 桥接。 |
| **微博（Weibo）** | 🛠 计划中 | 热搜 + 关键词搜索。路线图上的下一个 adapter。 |
| **知乎（Zhihu）** | 🛠 计划中 | 通过手机版接口抓取深度讨论问题页。 |

每个平台都是一个独立 adapter，仿照上游 `xiaohongshu_api` 模式——一个文件、一个 `search_*` 入口，归一化成 pipeline 已经理解的、带互动评分的 web-item 结构。可用 `EXCLUDE_SOURCES` 按次关闭，或用各平台的开关环境变量全局关闭（例如 `LAST30DAYS_DISABLE_BILIBILI=1`）。

### B站打分逻辑

B站独有的「投币」是社区最强的认可信号——用户每周的硬币有限，掏出一枚意味着真金白银的肯定。打分公式按此加权：

```
weighted = 播放×1 + 点赞×2 + 弹幕×1.5 + 收藏×2.5 + 投币×3
```

经 log 压缩后归一化到 0.05–1.0，让一个中等热度视频落在 0.5 附近，爆款逼近 1.0。

---

## 核心能力（v3）

- **智能搜索**：引擎先搞清楚该去**哪里**搜，再开始搜。输入"OpenClaw"会先解析出创建者的账号、相关 subreddit、对应的 YouTube 频道和话题标签，然后才发第一个请求。
- **Best Takes**：第二个评审给每条结果的幽默度、机智度、传播性打分，每份简报末尾附上最值得分享的金句。
- **跨源聚类合并**：同一个故事在 Reddit、X、B站同时出现时，合并成一个簇而非三条重复项。
- **可分享的 HTML 简报**：`--emit=html` 生成自包含、暗色、可打印的单文件，直接丢进微信/Slack/Notion。
- **一次过对比**："A vs B vs C" 单趟跑完，并行 fanout 多条 pipeline。
- **ELI5 模式**：研究跑完后说一句"eli5 on"，用大白话重写合成结果，数据来源不变。

---

## 安装

| 环境 | 安装命令 | 更新 |
|------|----------|------|
| **Claude Code**（推荐） | `/plugin marketplace add mvanhorn/last30days-skill` | marketplace 自动更新 |
| **Codex / Cursor / Copilot / Gemini CLI 等 50+ [Agent Skills](https://agentskills.io) 宿主** | `npx skills add mvanhorn/last30days-skill -g` | `npx skills update last30days -g` |
| **claude.ai**（网页版） | [下载 `last30days.skill`](https://github.com/mvanhorn/last30days-skill/releases/latest/download/last30days.skill) 后在 设置 > Capabilities > Skills 上传 | 重新下载上传 |

> 以上指向的是上游官方包。要用**本 fork**（含中文平台扩展），把本仓库 clone 下来，或把 `skills/last30days/` 目录复制到你的 skills 安装目录。

### 从本 fork 直接跑

```bash
git clone https://github.com/gilgamesh1124/last30days-skill-zhcn.git
cd last30days-skill-zhcn
# 运行测试确认环境正常
python -m pytest tests/test_bilibili.py tests/test_bilibili_wbi.py -v
```

---

## 配置

零配置即可跑：Reddit、HN、Polymarket、GitHub、**Bilibili** 开箱即用。其余源按需解锁：

| 环境变量 | 作用 |
|----------|------|
| `SCRAPECREATORS_API_KEY` | 解锁 TikTok / Instagram / Threads / Pinterest |
| `OPENROUTER_API_KEY` + `INCLUDE_SOURCES=perplexity` | 解锁 Perplexity 联网搜索 |
| `EXCLUDE_SOURCES=bilibili,tiktok` | 按次排除指定源（逗号分隔） |
| `LAST30DAYS_DISABLE_BILIBILI=1` | 全局关闭 B站源 |

完整配置见 [CONFIGURATION.md](CONFIGURATION.md)。

---

## 与上游的关系

本 fork 只在上游基础上**新增**中文平台 adapter，不改动既有行为。Bilibili adapter 已作为独立 PR 提交给上游（[mvanhorn/last30days-skill#514](https://github.com/mvanhorn/last30days-skill/pull/514)）。其余一切——引擎、打分、合成、安装方式——均跟随上游，定期同步。

致谢原作者 [@mvanhorn](https://github.com/mvanhorn) 及全体上游贡献者。
