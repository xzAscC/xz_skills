---
name: x-post-writing
description: "Draft English X (Twitter) posts and threads in the user's first-person voice from an article or idea they share, check weighted length with count.py, then archive the posted text in the JD repo. Use when the user wants to 发推, 发 X, write a tweet or thread, or record a post they published on X."
---

# X 发帖写作

写的是用户自己的看法和经历，不替用户编故事、定立场。默认英文，用户另有要求时再换语言。

## 流程

1. **读来源**：读原文，核对标题、作者和发布日期，不要把 URL 里的字样当成标题。查一下作者有没有在 X 上发过原帖：有就建议引用转发，没有就自己发。不确定作者的账号时不要猜 @。
2. **构思**：先给方案，不直接写成稿。列出：单条还是 thread、每条讲一个什么点、开头的钩子，以及需要用户补的经历或立场（用【待补：……】标出）。可以附一两个别的可发角度。等用户确认后再写。
3. **成稿**：按确认的方案写，然后用 en-controlled-writing 的 **light** 档去 AI 味。不要用 strict 或默认档，那两档会把语气磨平。写完用 `count.py` 检查每条的长度。
4. **存档**：用户发完后，按截图或用户给出的**实际发出的文字**逐字存档（见下文“存档”一节）。不要按草稿存。

## 用户的声音

- 简短直接。用户嫌“太复杂”时，删掉解释性的分句，只留一个理由。
- 第一人称，从用户真实的经历切入（例如“今天刚发现 Arc 就换上了”），比单纯复述原文更好。
- 一条只讲一个点。原文的好句子直接引用，加引号。
- 首尾可以呼应，但不要硬凑金句。
- 有争议或可能已经过时的事实要先提醒用户（例如某产品已经停止开发），由用户决定写不写。

## X 的规则

- 加权长度上限 280：中日韩文字和 emoji 每个按 2 算，任何链接固定按 23 算。用户是 Premium，可以发长帖，但超过约 280 的部分会被折叠成 "Show more"，所以默认拆成 thread。
- 链接放在最后一条，正文里的链接会被限流。X 会自动生成预览卡片。
- thread 的第一条结尾加 🧵。
- 发 thread 的方法：每写完一条点输入框旁边的 `+` 加下一条，最后点 Post all。不要把几条贴进同一个框。

检查长度（帖子之间用单独一行的 `1/`、`2/` 分隔；有任何一条超长时退出码为 1）：

```bash
python3 ~/xz_skills/x-post-writing/count.py draft.md
```

## 存档

存到 JD 仓库（`~/JD`）：

1. 文件：`11 Social/11.01 X/<YYYY-MM-DD> <标题>.md`。格式：
   ```markdown
   # <YYYY-MM-DD> <标题>

   - Source: [原文标题](URL) by 作者 (发布日期)
   - Account: [@XudongZhu3944](https://x.com/XudongZhu3944)
   - Format: N-post thread, posted <YYYY-MM-DD>

   ## Thread

   1/

   <逐字>
   ```
   有 HN、Lobsters 等讨论链接时，加一行 `- Discussion:`。
2. 在 `11 Social/11.01 X/README.md` 里加一行：链接 + 一句话说明。
3. 当天日记（`00 Periodic/<YYYY>/<MM>/W*/<YYYY-MM-DD>-<Ddd>.md`）里有对应任务就勾掉，并用 `[[文件名]]` 链到存档。
4. 按 JD 的 `Agents.md` 用 git 提交。
