# 社媒主页更新监测（微博/抖音/快手/小红书 → 钉钉）

每小时检查 5 个指定主页有无新视频/文字，发现更新即通过**钉钉机器人**推送。
代码跑在云端（无头浏览器），本机只需在部署时参与，日常运行不依赖你的电脑。

## 目录结构
```
social-monitor/
├── config.json          # 监控目标 + 钉钉(占位符) + 选择器
├── .env.example         # 凭证模板（钉钉 webhook/secret、cookie）
├── requirements.txt
├── src/
│   ├── monitor.py       # 主程序：一轮检查 + 推送 + 每日存活播报
│   ├── extractors.py    # 四平台提取（微博走API，其余走 Playwright）
│   ├── dingtalk.py      # 钉钉加签推送（仅标准库）
│   ├── diff.py          # 快照差集
│   └── store.py         # 快照存储（本地文件 / 腾讯云 COS）
└── deploy/DEPLOY.md     # 轻量服务器 / 容器函数部署
```

## 快速开始（本地试跑）
```bash
cd social-monitor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # 仅首次需要
cp .env.example .env                # 填入 DINGTALK_WEBHOOK/SECRET、DTC_COOKIES
set -a; source .env; set +a         # 载入环境变量（Windows 用：set 变量=值）
python src/monitor.py               # 跑一轮，看钉钉是否收到消息
```
> Windows PowerShell 设置变量： `$env:DINGTALK_WEBHOOK="..."` 等，再 `python src/monitor.py`。

## 各平台须知
- **微博**：用 `m.weibo.cn` 公开接口，最稳。公开微博可不填 cookie；私有/受限需登录 cookie。
- **抖音 / 小红书 / 快手**：必须**登录态 cookie** 才能看到完整内容；且这三家反爬/前端常变，
  提取选择器在 `config.json` 的 `selectors` 里，登录后按实际页面用 DevTools 调。
  - 抖音正文列表：`li[data-e2e="user-post-item"]`
  - 小红书笔记：`section.note-item`
  - 快手：`div[data-e2e="feed-item"]` / `div.video-card`
- **快手分享链接**是 `chenzhongtech.com/fw/user/...` 形式，代码会让浏览器自动跳转到
  `kuaishou.com/profile/...`，无需手动转换。

## 安全
- 钉钉 webhook/secret、登录 cookie **只放环境变量/密钥管理，绝不写进代码或提交仓库**。
- `data/snapshots.json` 只存内容 ID，不含任何凭证，会随仓库提交（用于跨运行持久化快照）。

## 部署（GitHub Actions，零服务器，推荐）
GitHub Actions **公开仓库免费额度无限、可真正每小时运行**，是本任务首选。代码跑在 GitHub 临时机器上，
本机只参与「推一次仓库」；日常运行不依赖你的电脑，电脑格式化也不影响。

1. 在 github.com 新建**公开**仓库（公开库 Actions 免费无限；私有库每月仅 2000 分钟，每小时跑不够用）。
   > 注意主页 URL 本就不是秘密，公开库安全；真正敏感的是 Secrets，不会进代码。
2. 仓库 `Settings → Secrets and variables → Actions → New repository secret`，依次加：
   - `DINGTALK_WEBHOOK`：钉钉机器人 Webhook 地址
   - `DINGTALK_SECRET`：钉钉机器人加签 secret（没开加签就填空字符串）
   - `DTC_COOKIES`：登录态 cookie（JSON 数组，见下「Secrets 取值格式详解」）
3. 本地把代码推到 GitHub（你本地分支是 `master`）：
   ```bash
   cd social-monitor
   git remote add origin https://github.com/你的用户名/social-monitor.git
   git push -u origin master
   ```
   > 若之前已把代码推到 gitcode/gitee，不影响；这里再加一个 GitHub 远程即可（或用 `git remote set-url origin ...` 覆盖）。
4. 工作流 `.github/workflows/monitor.yml` 已配好每小时整点附近运行 + 快照提交回仓库。
   推上去后在仓库 `Actions` 页点一次 `Run workflow` 手动验证，之后自动每小时跑。
5. 完成。GitHub 每小时拉起临时机器跑 `monitor.py`，推钉钉，并把 `data/snapshots.json` 提交回仓库——
   **不占用任何常驻服务器，电脑格式化也不影响运行**。

> 快照持久化：每次运行后工作流自动 `git commit` 最新 `data/snapshots.json`，下轮 checkout 即带最新状态，
> 差集比对在临时机器上也能连续，无需额外买 COS。

### 注意事项
- GitHub 定时任务**不保证准点**，可能晚几分钟（仍每小时一次）。
- 仓库超过 60 天无活动，GitHub 会自动停用定时工作流；重新进 Actions 页点一下启用即可。
- 抖音/小红书/快手提取选择器可能需按实际页面微调（见上「各平台须知」）。

### 本机零依赖
- 代码/凭证（在 GitHub Secrets）都在云端，你电脑只参与「推一次仓库」。
- 电脑格式化后：从 github.com 重新 clone 即可重部署；cookie 过期时在 GitHub Secrets 更新 `DTC_COOKIES`。

## 备选平台（仅当 GitHub 再次打不开时参考）
- **Gitee Go**：配置见 `.gitee/workflows/monitor.yml`；注意免费额度仅 1000 核分/月，真·每小时约第 5–6 天跑光，需买加时包或降频到每 4–6 小时。
- **GitCode**：配置见 `.gitlab-ci.yml`；试用时未找到稳定可用的 CI 入口，仅供参考。

## Secrets 取值格式详解（GitHub → Settings → Secrets → Actions）

三个密钥都是**纯文本值**，不要加引号、不要换行。复制到 Secret 的 Value 框即可。

### 1. `DINGTALK_WEBHOOK`
钉钉群里 `智能群助手 → 添加机器人 → 自定义（Webhook）`，创建后得到整串 URL：
```
https://oapi.dingtalk.com/robot/send?access_token=7a8b9c...
```
**直接整串粘贴**。

### 2. `DINGTALK_SECRET`
创建机器人时若勾选了「加签」，页面会显示一段 secret（形如 `SEC7a8b9c...`）。
**整串粘贴**。
> 没开加签：这个 Secret 也要建（代码读得到才会跳过签名），值填一个空字符串即可。

### 3. `DTC_COOKIES`（最关键）
值是一个 **JSON 数组**，每个元素是 `{name, value, domain}` 对象：
```json
[{"name":"sessionid","value":"abc123","domain":".douyin.com"},
 {"name":"sid_tt","value":"xyz","domain":".douyin.com"},
 {"name":"web_session","value":"uuu","domain":".xiaohongshu.com"}]
```
代码会自动给缺 `domain` 的 cookie 补上目标域名，所以**手动导出的 `{name,value}` 也能用**，但带 `domain` 最稳。

#### 怎么从浏览器导出（推荐：插件法，最省事也最全）
1. 给浏览器装插件 **Cookie-Editor**（Chrome / Edge / Firefox 扩展商店都有）。
2. 在**已登录**状态下打开对应平台网页（douyin.com / kuaishou.com / xiaohongshu.com）。
3. 点开 Cookie-Editor 插件 → 右下角 `Export` → 格式选 **JSON** → 复制出来的就是合规数组。
4. 三个平台**分别导出**，把三段数组**合并**成一个大数组填进同一个 Secret：
   - 例：抖音导出的 `[{...}]` + 小红书导出的 `[{...}]` + 快手导出的 `[{...}]`
   - 合并 = `[]` 包住所有对象，用逗号分隔：
     ```json
     [ {"name":"a","value":"1","domain":".douyin.com"}, {"name":"b","value":"2","domain":".xiaohongshu.com"} ]
     ```

#### 备选：无插件（Network 法，也能拿到 HttpOnly）
1. 登录后按 `F12` → `Network` → 刷新页面 → 点列表里任意一条到该域的请求。
2. 在 `Request Headers` 里找到 `Cookie:` 那一行，复制整段值（形如 `name1=val1; name2=val2; ...`）。
3. 在浏览器控制台粘贴下面这段，自动转成 JSON 数组并复制到剪贴板：
   ```js
   copy(JSON.stringify(document.cookie.split('; ').map(c=>{const i=c.indexOf('=');return {name:c.slice(0,i),value:c.slice(i+1),domain:location.hostname};})))
   ```
   ⚠️ `document.cookie` **读不到 HttpOnly 的登录态 cookie**，可能不完整；插件法最稳。
> Network 法更完整：直接复制请求头里那串 `name=val; name=val`，交给代码前无需转换——
> 但当前代码吃的是 JSON 数组，所以用上面的控制台脚本转一下即可。

#### 注意
- 必须是**已登录会话**导出的 cookie；未登录抓不到完整内容。
- cookie 会过期（抖音/小红书最快，几天到几周），失效时钉钉会收到「抓取失败」，重新导出更新即可。
- 微博可不填 cookie 先试公开接口；只有抖音/快手/小红书需要。

## 维护点
- cookie 会过期（抖音/小红书较快）。失效时本轮会推「抓取失败」或登录页，需重新登录并更新 `DTC_COOKIES`。
- 建议开启钉钉「加签」，secret 与 webhook 一起注入环境变量。
