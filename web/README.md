# Insight Agent Web UI

## 🌐 Web 界面使用指南

### 启动方式

#### 方式一：独立管理器（推荐）
```bash
# 交互模式
python webui/webui_manager.py

# 命令行模式
python webui/webui_manager.py start    # 启动服务器
python webui/webui_manager.py stop     # 停止服务器
python webui/webui_manager.py status   # 查看状态
python webui/webui_manager.py open     # 在浏览器打开
```

#### 方式二：主程序启动
```bash
python main.py
# 选择 [4] Web UI
# 选择启动模式：
#   1. 前台运行（占用终端）
#   2. 后台运行（推荐，终端可继续使用）
```

#### 方式三：直接启动
```bash
python web/server.py
# 默认前台运行，按 Ctrl+C 停止
```

### 访问地址

启动后访问：**http://localhost:9527**

---

## 🎯 功能说明

### 1. 数据采集
- **自然语言描述**：用日常语言描述想采集什么
- **手动选择平台**：8 大平台爬虫
- **文件上传**：支持 CSV、Excel、JSON

### 2. 数据分析
- **选择数据文件**：从已上传的文件中选择
- **分析模板**：预设的分析流程
- **自定义分析**：AI 驱动的动态分析

### 3. AI 对话
- **创建会话**：开始新的分析对话
- **持续对话**：多轮追问和深度挖掘
- **会话管理**：查看和恢复历史会话

### 4. 报告生成
- **HTML 报告**：可视化图表
- **PDF 导出**：一键生成 PDF
- **数据分析**：详细的数据统计

---

## 💡 使用技巧

### 后台运行模式
```bash
# 启动后台服务器
python webui/webui_manager.py start

# 终端可继续使用
# 做其他操作...

# 查看服务器状态
python webui/webui_manager.py status

# 停止服务器
python webui/webui_manager.py stop
```

### 多终端协作
```bash
# 终端 1：启动 Web UI
python webui/webui_manager.py start

# 终端 2：运行 CLI
python main.py

# 两个界面可以同时使用
```

### 自定义端口
```bash
# 修改 web/server.py 中的端口
python webui/webui_manager.py start --port 8080
```

---

## 🔧 故障排除

### 问题 1：端口被占用
```
OSError: [Errno 48] Address already in use
```

**解决方案**：
```bash
# 查看端口占用
lsof -i :9527

# 停止占用进程
kill -9 <PID>

# 或使用其他端口
python webui/webui_manager.py start --port 8080
```

### 问题 2：浏览器未自动打开
**解决方案**：
```bash
# 手动打开浏览器
python webui/webui_manager.py open

# 或直接访问 http://localhost:9527
```

### 问题 3：页面无法访问
**解决方案**：
```bash
# 检查服务器状态
python webui/webui_manager.py status

# 查看日志
tail -f output/app.log

# 重启服务器
python webui/webui_manager.py stop
python webui/webui_manager.py start
```

---

## 🎨 界面预览

### 首页
- 功能入口卡片
- 最近会话列表
- 快速开始按钮

### 爬虫页面
- 自然语言输入框
- 平台选择网格
- 参数配置表单

### 分析页面
- 文件选择器
- 分析模板列表
- 结果展示区域

### 对话页面
- 会话列表
- 聊天界面
- 消息历史

---

## 📊 技术架构

### 前端技术
- **HTML5** + **CSS3**
- **Tailwind CSS**：样式框架
- **Alpine.js**：轻量级交互
- **Chart.js**：图表库

### 后端技术
- **Flask**：Web 框架
- **RESTful API**：接口设计
- **WebSocket**：实时通信（计划中）

### 数据流
```
用户操作 → API 请求 → 后端处理 → 返回数据 → 前端渲染
```

---

## 🚀 高级功能

### 1. 文件拖拽上传
- 支持拖拽文件到上传区域
- 自动识别文件格式
- 实时上传进度

### 2. 实时数据预览
- 上传后立即预览
- 显示数据统计
- 字段类型检测

### 3. 交互式图表
- 点击查看详情
- 缩放和平移
- 数据导出

### 4. 多标签页分析
- 同时打开多个分析
- 标签页切换
- 独立会话管理

---

## 📝 API 文档

### 爬虫相关
- `GET /api/crawlers` - 获取爬虫列表
- `POST /api/crawl` - 启动爬虫
- `POST /api/nl-crawl` - 自然语言爬虫

### 分析相关
- `GET /api/templates` - 获取分析模板
- `POST /api/templates/run` - 运行分析模板

### 会话相关
- `GET /api/sessions` - 获取会话列表
- `POST /api/sessions` - 创建会话
- `POST /api/chat` - 发送消息

### 文件相关
- `GET /api/files` - 获取文件列表
- `POST /api/upload` - 上传文件

---

## 🔮 未来计划

### 短期 (1个月)
- [ ] WebSocket 实时通信
- [ ] 更多图表类型
- [ ] 移动端适配

### 中期 (3个月)
- [ ] 多用户支持
- [ ] 权限管理
- [ ] 数据共享

### 长期 (6个月)
- [ ] 移动 APP
- [ ] 离线模式
- [ ] 插件系统

---

## 💬 反馈与建议

如有问题或建议，请：
1. 查看本文档
2. 检查日志文件
3. 提交 GitHub Issue

---

**Web UI 版本**: v1.0  
**最后更新**: 2024-01-27
