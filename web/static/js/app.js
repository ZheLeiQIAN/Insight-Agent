// Insight Agent Web UI - Alpine.js 应用

function app() {
    return {
        // 状态
        currentView: 'home',
        loading: false,
        systemStatus: null,
        
        // 爬虫相关
        crawlers: [],
        selectedCrawler: null,
        nlQuery: '',
        crawlParams: { url: '', max: 100 },
        crawlJob: null,
        crawlStatus: null,
        crawlLogs: [],
        crawlPolling: null,
        
        // 分析相关
        files: [],
        selectedFile: null,
        templates: [],
        analysisResult: null,
        
        // 会话相关
        sessions: [],
        currentSession: null,
        chatMessages: [],
        chatInput: '',
        chatLoading: false,
        
        // 初始化
        async init() {
            await this.loadSystemStatus();
            await this.loadCrawlers();
            await this.loadFiles();
            await this.loadTemplates();
            await this.loadSessions();
        },

        async refreshAll() {
            await this.loadSystemStatus();
            await this.loadFiles();
            await this.loadSessions();
        },

        async loadSystemStatus() {
            try {
                const resp = await fetch('/api/system/status');
                this.systemStatus = await resp.json();
            } catch (e) {
                console.error('加载系统状态失败:', e);
            }
        },
        
        // ======== 爬虫 ========
        async loadCrawlers() {
            try {
                const resp = await fetch('/api/crawlers');
                this.crawlers = await resp.json();
            } catch (e) {
                console.error('加载爬虫失败:', e);
            }
        },
        
        selectCrawler(c) {
            this.selectedCrawler = c;
            this.crawlParams = { url: '', max: 100 };
        },
        
        async nlCrawl() {
            if (!this.nlQuery.trim()) return;
            
            this.loading = true;
            try {
                const resp = await fetch('/api/nl-crawl', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ description: this.nlQuery })
                });
                const data = await resp.json();
                
                if (data.error) {
                    alert('❌ ' + data.error);
                } else {
                    this.crawlJob = data.job_id;
                    this.crawlStatus = { status: 'started', platform: data.platform, reason: data.reason };
                    this.crawlLogs = [`AI 已选择平台：${data.platform}`, data.reason ? `原因：${data.reason}` : ''];
                    this.pollCrawlJob(data.job_id);
                }
            } catch (e) {
                alert('❌ 请求失败: ' + e.message);
                this.loading = false;
            } finally {
            }
        },
        
        async startCrawl() {
            if (!this.selectedCrawler) return;
            
            this.loading = true;
            this.crawlJob = null;
            this.crawlStatus = null;
            this.crawlLogs = [];
            try {
                const resp = await fetch('/api/crawl', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        crawler: this.selectedCrawler.key,
                        params: this.crawlParams
                    })
                });
                const data = await resp.json();
                
                if (data.error) {
                    alert('❌ ' + data.error);
                } else {
                    this.crawlJob = data.job_id;
                    this.crawlStatus = { status: 'started' };
                    this.pollCrawlJob(data.job_id);
                }
            } catch (e) {
                alert('❌ 请求失败: ' + e.message);
                this.loading = false;
            }
        },

        async pollCrawlJob(jobId) {
            if (this.crawlPolling) {
                clearInterval(this.crawlPolling);
            }

            const poll = async () => {
                try {
                    const resp = await fetch(`/api/crawl/status/${jobId}`);
                    const data = await resp.json();
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    this.crawlStatus = data;
                    this.crawlLogs = data.logs || [];

                    if (['done', 'failed', 'cancelled'].includes(data.status)) {
                        clearInterval(this.crawlPolling);
                        this.crawlPolling = null;
                        this.loading = false;
                        await this.loadFiles();
                        await this.loadSystemStatus();

                        if (data.status === 'done' && data.file) {
                            alert(`✅ 采集完成！\n文件: ${data.name}\n记录: ${data.rows}条`);
                            this.currentView = 'analysis';
                        } else if (data.status === 'cancelled') {
                            alert('已中止采集任务');
                        } else if (data.status === 'failed') {
                            alert('❌ 采集失败: ' + (data.error || '未知错误'));
                        }
                    }
                } catch (e) {
                    clearInterval(this.crawlPolling);
                    this.crawlPolling = null;
                    this.loading = false;
                    alert('❌ 获取采集状态失败: ' + e.message);
                }
            };

            await poll();
            this.crawlPolling = setInterval(poll, 1500);
        },

        async cancelCrawl() {
            if (!this.crawlJob) return;
            try {
                await fetch(`/api/crawl/cancel/${this.crawlJob}`, { method: 'POST' });
                this.crawlStatus = { ...(this.crawlStatus || {}), status: 'cancelling' };
                this.crawlLogs = [...this.crawlLogs, '正在中止任务...'];
            } catch (e) {
                alert('❌ 中止失败: ' + e.message);
            } finally {
            }
        },
        
        async uploadFile(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const resp = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await resp.json();
                
                if (data.error) {
                    alert('❌ ' + data.error);
                } else {
                    alert(`✅ 上传成功！\n文件: ${data.name}\n大小: ${(data.size / 1024).toFixed(1)}KB`);
                    await this.loadFiles();
                    await this.loadSystemStatus();
                    this.currentView = 'analysis';
                }
            } catch (e) {
                alert('❌ 上传失败: ' + e.message);
            }
            
            event.target.value = '';
        },
        
        // ======== 分析 ========
        async loadFiles() {
            try {
                const resp = await fetch('/api/files');
                this.files = await resp.json();
            } catch (e) {
                console.error('加载文件失败:', e);
            }
        },
        
        async loadTemplates() {
            try {
                const resp = await fetch('/api/templates');
                this.templates = await resp.json();
            } catch (e) {
                console.error('加载模板失败:', e);
            }
        },
        
        async runTemplate(template) {
            if (!this.selectedFile) {
                alert('请先选择数据文件');
                return;
            }
            
            this.loading = true;
            this.analysisResult = null;
            
            try {
                const resp = await fetch('/api/templates/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        template_id: template.id,
                        file: this.selectedFile.path
                    })
                });
                const data = await resp.json();
                
                if (data.error) {
                    alert('❌ ' + data.error);
                } else {
                    this.analysisResult = `✅ 分析完成！\n\n模板: ${template.name}\n报告: ${data.report}\n执行模型: ${data.models_ran}个`;
                    alert(this.analysisResult);
                    await this.loadSystemStatus();
                }
            } catch (e) {
                alert('❌ 分析失败: ' + e.message);
            } finally {
                this.loading = false;
            }
        },
        
        showReport() {
            alert('请先完成数据采集或分析，然后查看 output/reports/ 目录');
        },
        
        // ======== 会话 ========
        async loadSessions() {
            try {
                const resp = await fetch('/api/sessions');
                this.sessions = await resp.json();
            } catch (e) {
                console.error('加载会话失败:', e);
            }
        },
        
        async createSession() {
            try {
                const resp = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                const data = await resp.json();
                
                if (data.error) {
                    alert('❌ ' + data.error);
                    return;
                }
                
                this.currentSession = data.session_id;
                this.chatMessages = [
                    { role: 'assistant', content: data.greeting }
                ];
                await this.loadSessions();
            } catch (e) {
                alert('❌ 创建会话失败: ' + e.message);
            }
        },
        
        async resumeSession(sid) {
            this.currentSession = sid;
            this.chatMessages = [];
            
            try {
                const resp = await fetch('/api/sessions');
                const sessions = await resp.json();
                const session = sessions.find(s => s.id === sid);
                
                if (session) {
                    // 加载历史消息
                    this.chatMessages = Array.isArray(session.messages) ? session.messages : [];
                }
            } catch (e) {
                console.error('恢复会话失败:', e);
            }
        },
        
        async sendMessage() {
            if (!this.chatInput.trim() || !this.currentSession) return;
            
            const message = this.chatInput.trim();
            this.chatInput = '';
            this.chatMessages.push({ role: 'user', content: message });
            this.chatLoading = true;
            
            try {
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: this.currentSession,
                        message: message
                    })
                });
                const data = await resp.json();
                
                if (data.error) {
                    this.chatMessages.push({ role: 'assistant', content: '❌ 错误: ' + data.error });
                } else if (data.closed) {
                    this.chatMessages.push({ role: 'assistant', content: data.response });
                    setTimeout(() => {
                        this.currentSession = null;
                        this.loadSessions();
                    }, 2000);
                } else {
                    this.chatMessages.push({ role: 'assistant', content: data.response });
                }
                
                this.$nextTick(() => {
                    const container = document.getElementById('chatContainer');
                    if (container) {
                        container.scrollTop = container.scrollHeight;
                    }
                });
            } catch (e) {
                this.chatMessages.push({ role: 'assistant', content: '❌ 请求失败: ' + e.message });
            } finally {
                this.chatLoading = false;
            }
        },
        
        renderMarkdown(text) {
            // 简单的 Markdown 渲染
            if (!text) return '';
            
            let html = text
                // 代码块
                .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
                // 行内代码
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                // 加粗
                .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                // 斜体
                .replace(/\*([^*]+)\*/g, '<em>$1</em>')
                // 标题
                .replace(/^### (.+)$/gm, '<h3>$1</h3>')
                .replace(/^## (.+)$/gm, '<h2>$1</h2>')
                .replace(/^# (.+)$/gm, '<h1>$1</h1>')
                // 链接
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-cyan-600 hover:underline">$1</a>')
                // 无序列表
                .replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>')
                // 有序列表
                .replace(/^\s*\d+\.\s+(.+)$/gm, '<li>$1</li>')
                // 引用
                .replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>')
                // 表格行
                .replace(/^\|(.+)\|$/gm, function(match, p1) {
                    const cells = p1.split('|').map(c => c.trim());
                    if (cells.every(c => /^[-:]+$/.test(c))) {
                        return ''; // 分隔行，跳过
                    }
                    const tag = match.startsWith('|---') ? 'th' : 'td';
                    return '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
                })
                // 换行
                .replace(/\n/g, '<br>');
            
            // 包裹表格
            html = html.replace(/(<tr>.*<\/tr>)+/g, '<table class="markdown-body">$&</table>');
            
            // 包裹列表
            html = html.replace(/(<li>.*<\/li>)+/g, '<ul class="markdown-body list-disc pl-5">$&</ul>');
            
            return html;
        }
    };
}
