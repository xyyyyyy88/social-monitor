# 部署说明

目标：每小时自动跑一次 `src/monitor.py`，结果推钉钉。本机不参与运行。

## 方案 A：轻量应用服务器（最省心，推荐）
1. 买一台轻量服务器（2 核 2G 起，系统选 Ubuntu/Debian）。
2. 上传代码：`git clone` 你的私有仓库，或 `scp -r` 整个 `social-monitor/`。
3. 安装运行环境：
   ```bash
   cd social-monitor
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```
4. 写入凭证（用云厂商「密钥管理」或直接在 `~/.bashrc` 里 `export`，**别提交进仓库**）：
   ```bash
   export DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=xxx"
   export DINGTALK_SECRET="你的secret"
   export DTC_COOKIES='[{"name":"sessionid","value":"...","domain":".douyin.com","path":"/"}]'
   ```
5. 设每小时定时（`crontab -e`）：
   ```cron
   0 * * * *  cd /root/social-monitor && source .venv/bin/activate && python src/monitor.py >> run.log 2>&1
   ```
6. 完成。服务器 7x24 运行，与你电脑格式化无关。

## 方案 B：容器镜像函数（无长期服务器，按量计费）
Playwright 需要把 Chromium 打进镜像，普通「函数」运行时装不下，请用**容器镜像**方式：
- 腾讯云 SCF：函数类型选「容器镜像」，Dockerfile 基于 `python:3.11-slim`，
  安装 `playwright` + `playwright install chromium`，入口 `python src/monitor.py`。
  配置「定时触发器」cron `0 * * * *`。
- 阿里云 FC：使用「Custom Container」+ 定时触发器（EventBridge 计时）。
- 快照存储把 `config.json` 的 `store.type` 改为 `cos`，避免冷启动后快照丢失（见 store.py）。

## 方案 C：GitHub Actions（零服务器，适合低频）
- 在仓库 `Settings → Secrets` 配置 `DINGTALK_WEBHOOK`/`DINGTALK_SECRET`/`DTC_COOKIES`。
- 加一个 workflow：`on.schedule.cron "0 * * * *"`，steps 里 `pip install -r requirements.txt`、
  `playwright install chromium`、`python src/monitor.py`。
- 注意：Actions 免费额度有运行时限制，且每小时任务可能被排队；生产建议方案 A/B。

## 通用提醒
- 首次部署后，观察钉钉是否收到「存活播报」，确认链路通。
- cookie 过期时任务会推异常，重新登录并更新 `DTC_COOKIES` 即可，无需重装。
- 抖音/小红书若提取不到内容，多半是选择器变了：登录后在浏览器 DevTools 里确认最新选择器，
  改 `config.json` 的 `selectors` 后重新部署。
