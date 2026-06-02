# Web UI 使用指南 - 终端不会被阻塞

## 🎯 问题解答

**问：启动 Web UI 后，CLI 终端会不会被阻塞？**

**答：不会！** 我们已经优化了 Web UI 的启动方式，支持**后台运行模式**。

---

## 🚀 启动方式

### 方式一：使用 Web UI 管理器（推荐）

```bash
# 交互模式
python tools/webui_manager.py

# 命令行模式
python tools/webui_manager.py start    # 后台启动
python tools/webui_manager.py status   # 查看状态
python tools/webui_manager.py stop     # 停止服务器
```

**优势**：
- ✅ 终端不被阻塞
- ✅ 可以继续使用终端
- ✅ 方便管理服务器

### 方式二：主程序启动

```bash
python main.py
# 选择 [4] Web UI
# 选择启动模式：
#   1. 前台运行（占用终端）
#   2. 后台运行（推荐）
```

**推荐选择模式 2**，这样终端可以继续使用。

### 方式三：直接启动（会阻塞）

```bash
python web/server.py
# ⚠️ 这种方式会占用终端
# 按 Ctrl+C 停止
```

---

## 💡 使用场景

### 场景 1：同时使用 CLI 和 Web

```bash
# 终端 1：启动 Web UI（后台）
python tools/webui_manager.py start

# 终端 2：运行 CLI 分析
python main.py
# 选择 [2] 分析已有数据
# 进行数据分析...
```

**效果**：
- Web UI 在后台运行
- CLI 可以正常操作
- 两个界面同时可用

### 场景 2：长时间运行

```bash
# 启动 Web 服务器
python tools/webui_manager.py start

# 终端可以做其他事情
# 比如：查看日志、运行其他脚本...

# 随时访问 Web UI
# http://localhost:9527

# 需要时停止服务器
python tools/webui_manager.py stop
```

### 场景 3：多用户协作

```bash
# 用户 A：启动 Web UI
python tools/webui_manager.py start --port 9527

# 用户 B：启动另一个实例
python tools/webui_manager.py start --port 9528

# 两个用户可以同时使用不同端口
```

---

## 🔧 技术实现

### 后台运行原理

```python
import threading

def start_server_background():
    # 创建守护线程
    server_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=9527),
        daemon=True,  # 守护线程，主程序退出时自动停止
        name="web-server"
    )
    server_thread.start()
    return server_thread
```

**关键点**：
- 使用 `threading.Thread` 创建后台线程
- 设置 `daemon=True`，主程序退出时自动停止
- 终端不会被阻塞

### 前台 vs 后台对比

| 特性 | 前台运行 | 后台运行 |
|------|----------|----------|
| 终端占用 | ✅ 占用 | ❌ 不占用 |
| 可继续操作 | ❌ 不可以 | ✅ 可以 |
| 日志输出 | ✅ 直接显示 | ⚠️ 需要查看文件 |
| 停止方式 | Ctrl+C | 调用 stop 命令 |
| 适用场景 | 调试 | 生产 |

---

## 📊 状态查看

### 查看服务器状态

```bash
python tools/webui_manager.py status
```

**输出示例**：
```
╭──────────────┬──────────────╮
│ 项目         │ 状态         │
├──────────────┼──────────────┤
│ 服务器状态   │ 🟢 运行中    │
│ 访问地址     │ http://localhost:9527 │
│ 线程         │ <Thread(web-server, started)> │
╰──────────────┴──────────────╯
```

### 查看日志

```bash
# 查看实时日志
tail -f output/app.log

# 查看错误日志
grep "ERROR" output/app.log
```

---

## 🎨 使用示例

### 示例 1：快速启动

```bash
# 一键启动
python tools/webui_manager.py start

# 浏览器自动打开
# 终端显示：
# ✅ Web 服务器已启动
# 访问地址: http://localhost:9527
# 终端可继续使用
```

### 示例 2：CLI + Web 协作

```bash
# 终端 1
python tools/webui_manager.py start

# 终端 2
python main.py
# 选择 [2] 分析已有数据
# 选择文件...
# 进行分析...
# 生成报告...

# 浏览器访问 Web UI
# 查看相同的功能
```

### 示例 3：自动化脚本

```bash
#!/bin/bash
# start_services.sh

# 启动 Web UI
python tools/webui_manager.py start

# 等待服务器启动
sleep 2

# 运行分析脚本
python analyze_data.py

# 生成报告
python generate_report.py

# 停止服务器
python tools/webui_manager.py stop
```

---

## ⚠️ 注意事项

### 1. 端口冲突

```bash
# 如果端口被占用
OSError: [Errno 48] Address already in use

# 解决方案
lsof -i :9527  # 查看占用进程
kill -9 <PID>  # 停止进程

# 或使用其他端口
python tools/webui_manager.py start --port 8080
```

### 2. 服务器停止

```bash
# 后台服务器会在主程序退出时自动停止
# 如果需要手动停止
python tools/webui_manager.py stop
```

### 3. 日志查看

```bash
# 后台运行时，日志输出到文件
tail -f output/app.log

# 或查看特定日志
grep "web.server" output/app.log
```

---

## 🔮 高级用法

### 1. 自定义端口

```bash
python tools/webui_manager.py start --port 8080
```

### 2. 绑定所有接口

```bash
# 修改 web/server.py
app.run(host='0.0.0.0', port=9527)
# 允许外部访问
```

### 3. 生产环境部署

```bash
# 使用 Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:9527 web.server:app

# 或使用 Docker
docker-compose up -d
```

---

## 📚 相关文档

- [README.md](../README.md) - 项目概述
- [CLI_GUIDE.md](CLI_GUIDE.md) - CLI 使用指南
- [ANALYSIS_TOOLS_GUIDE.md](ANALYSIS_TOOLS_GUIDE.md) - 分析工具指南

---

## 💬 常见问题

### Q1: 后台服务器会影响性能吗？

**A**: 影响很小。后台线程占用资源很少，不会影响 CLI 操作。

### Q2: 可以同时运行多个实例吗？

**A**: 可以，但需要使用不同端口：
```bash
python tools/webui_manager.py start --port 9527
python tools/webui_manager.py start --port 9528
```

### Q3: 如何查看服务器是否在运行？

**A**:
```bash
python tools/webui_manager.py status
```

### Q4: 服务器崩溃了怎么办？

**A**:
```bash
# 查看错误日志
tail -f output/app.log

# 重启服务器
python tools/webui_manager.py stop
python tools/webui_manager.py start
```

---

## 🎉 总结

**Web UI 支持后台运行，终端不会被阻塞！**

✅ **推荐使用**：
```bash
python tools/webui_manager.py start
```

✅ **终端可继续操作**

✅ **Web UI 在后台运行**

✅ **随时访问 http://localhost:9527**

---

**文档版本**: v1.0  
**最后更新**: 2024-01-27
# Scrapling 通用网页采集

项目已接入 Scrapling 作为可选增强，用于采集任意网页的标题、段落和链接。

使用方式：

1. 打开 Web UI 的“数据采集”页面。
2. 选择“通用网页 / Scrapling 通用网页采集”。
3. 填入网页 URL。
4. 点击“开始采集”。

注意：

- Scrapling 当前需要 Python 3.10+。
- 本项目仍兼容 Python 3.9；在 Python 3.9 环境中，Scrapling 会被跳过，其他爬虫和分析功能不受影响。
- 如果需要启用 Scrapling，请使用 Python 3.10+ 后运行 `pip install scrapling` 或重新安装 `requirements.txt`。
