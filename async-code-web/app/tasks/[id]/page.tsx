"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Github, Clock, CheckCircle, XCircle, AlertCircle, GitCommit, FileText, ExternalLink, MessageSquare, Plus, Copy, Loader2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { ProtectedRoute } from "@/components/protected-route";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { Task, Project, ChatMessage } from "@/types";
import { formatDiff, parseDiffStats } from "@/lib/utils";
import { DiffViewer } from "@/components/diff-viewer";
import { toast } from "sonner";

interface TaskWithProject extends Task {
    project?: Project
}

const formatMessageTimestamp = (value: unknown) => {
    if (value === null || value === undefined || value === "") return "未知时间";
    let date: Date;
    if (typeof value === "number") {
        const ms = value < 1e12 ? value * 1000 : value;
        date = new Date(ms);
    } else if (typeof value === "string" && /^\d+(\.\d+)?$/.test(value.trim())) {
        const numeric = Number(value);
        const ms = numeric < 1e12 ? numeric * 1000 : numeric;
        date = new Date(ms);
    } else {
        date = new Date(value as string);
    }
    if (Number.isNaN(date.getTime())) return "未知时间";
    return date.toLocaleString();
};

export default function TaskDetailPage() {
    const { user } = useAuth();
    const params = useParams();
    const taskId = parseInt(params.id as string);
    
    const [task, setTask] = useState<TaskWithProject | null>(null);
    const [loading, setLoading] = useState(true);
    const [gitDiff, setGitDiff] = useState("");
    const [diffStats, setDiffStats] = useState({ additions: 0, deletions: 0, files: 0 });
    const [newMessage, setNewMessage] = useState("");
    const [githubToken, setGithubToken] = useState("");
    const [creatingPR, setCreatingPR] = useState(false);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const sessionToken = sessionStorage.getItem('github-token');
            if (sessionToken) setGithubToken(sessionToken);

            localStorage.removeItem('github-token');
            localStorage.removeItem('github-token-remember');
        }
    }, []);

    useEffect(() => {
        if (user?.id && taskId) {
            loadTask();
        }
    }, [user?.id, taskId]);

    // 若任务运行中则轮询状态更新
    useEffect(() => {
        if (!user?.id || !task || (task.status !== "running" && task.status !== "pending")) return;

        const interval = setInterval(async () => {
            try {
                const updatedTask = await ApiService.getTaskStatus(user.id, taskId);
                setTask(prev => ({ ...prev, ...updatedTask }));

                // 任务完成后获取 git diff
                if (updatedTask.status === "completed" && !gitDiff) {
                    try {
                        const diff = await ApiService.getGitDiff(user.id, taskId);
                        setGitDiff(diff);
                        const stats = parseDiffStats(diff);
                        setDiffStats(stats);
                    } catch (error) {
                        console.error('获取 git diff 失败：', error);
                    }
                }
            } catch (error) {
                console.error('轮询任务状态失败：', error);
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [task, user?.id, taskId, gitDiff]);

    const loadTask = async () => {
        if (!user?.id) return;
        
        try {
            setLoading(true);
            const taskData = await ApiService.getTask(user.id, taskId);
            setTask(taskData);

            // 任务完成时加载 git diff
            if (taskData?.status === "completed") {
                try {
                    const diff = await ApiService.getGitDiff(user.id, taskId);
                    setGitDiff(diff);
                    const stats = parseDiffStats(diff);
                    setDiffStats(stats);
                } catch (error) {
                    console.error('获取 git diff 失败：', error);
                }
            }
        } catch (error) {
            console.error('加载任务失败：', error);
        } finally {
            setLoading(false);
        }
    };

    const handleAddMessage = async () => {
        if (!newMessage.trim() || !user?.id) return;

        try {
            await ApiService.addChatMessage(user.id, taskId, {
                role: 'user',
                content: newMessage.trim()
            });
            setNewMessage("");
            toast.success("消息已添加");
            loadTask(); // Reload to get updated messages
        } catch (error) {
            console.error('添加消息失败：', error);
            toast.error('添加消息失败');
        }
    };

    const handleCreatePR = async () => {
        if (!task || task.status !== "completed" || !user?.id) return;

        setCreatingPR(true);
        
        try {
            const prompt = (task.chat_messages as unknown as ChatMessage[])?.[0]?.content || '';
            const modelName = task.agent === 'codex' ? 'Codex' : 'Claude Code';
            
            toast.loading("正在创建 PR...");
            
            const response = await ApiService.createPullRequest(user.id, task.id, {
                title: `${modelName}: ${prompt.substring(0, 50)}...`,
                body: `由 ${modelName} 生成的自动化改动。\n\n提示词：${prompt}`,
                github_token: githubToken
            });

            toast.dismiss();
            toast.success(`PR #${response.pr_number} 创建成功！`);
            
            // 刷新任务数据以显示新的 PR 信息
            await loadTask();
            
            // 在新标签页打开 PR
            window.open(response.pr_url, '_blank');
        } catch (error) {
            toast.dismiss();
            toast.error(`创建 PR 失败：${error}`);
        } finally {
            setCreatingPR(false);
        }
    };

    const getStatusVariant = (status: string) => {
        switch (status) {
            case "pending": return "secondary";
            case "running": return "default";
            case "completed": return "default";
            case "failed": return "destructive";
            default: return "outline";
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "pending": return <Clock className="w-4 h-4" />;
            case "running": return <AlertCircle className="w-4 h-4" />;
            case "completed": return <CheckCircle className="w-4 h-4" />;
            case "failed": return <XCircle className="w-4 h-4" />;
            default: return null;
        }
    };

    const getStatusLabel = (status: string) => {
        switch (status) {
            case "pending": return "待处理";
            case "running": return "进行中";
            case "completed": return "已完成";
            case "failed": return "失败";
            default: return status || "未知";
        }
    };

    if (loading) {
        return (
            <ProtectedRoute>
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
                        <p className="text-slate-600 mt-2">正在加载任务...</p>
                    </div>
                </div>
            </ProtectedRoute>
        );
    }

    if (!task) {
        return (
            <ProtectedRoute>
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                    <div className="text-center">
                        <XCircle className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                        <h3 className="text-xl font-semibold text-slate-900 mb-2">未找到任务</h3>
                        <p className="text-slate-600 mb-6">该任务不存在或你没有访问权限。</p>
                        <Link href="/">
                            <Button>返回仪表盘</Button>
                        </Link>
                    </div>
                </div>
            </ProtectedRoute>
        );
    }

    return (
        <ProtectedRoute>
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
                {/* Header */}
                <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                    <div className="container mx-auto px-6 py-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <Link href="/" className="text-slate-600 hover:text-slate-900 flex items-center gap-2">
                                    <ArrowLeft className="w-4 h-4" />
                                    返回仪表盘
                                </Link>
                                <div>
                                    <h1 className="text-xl font-semibold text-slate-900 flex items-center gap-2">
                                        任务 #{task.id}
                                        <Badge variant={getStatusVariant(task.status || '')} className="gap-1">
                                            {getStatusIcon(task.status || '')}
                                            {getStatusLabel(task.status || '')}
                                        </Badge>
                                    </h1>
                                    <p className="text-sm text-slate-500">
                                        {task.project ? `${task.project.name} • ` : ''}
                                        {task.agent?.toUpperCase()} • 
                                        {new Date(task.created_at || '').toLocaleString()}
                                    </p>
                                </div>
                            </div>
                            {task.status === "completed" && (
                                task.pr_url ? (
                                    <Button asChild variant="outline" className="gap-2">
                                        <a href={task.pr_url} target="_blank" rel="noopener noreferrer">
                                            <ExternalLink className="w-4 h-4" />
                                            查看 PR #{task.pr_number}
                                        </a>
                                    </Button>
                                ) : (
                                    <Button onClick={handleCreatePR} disabled={creatingPR} className="gap-2">
                                        {creatingPR ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <ExternalLink className="w-4 h-4" />
                                        )}
                                        {creatingPR ? "正在创建 PR..." : "创建 PR"}
                                    </Button>
                                )
                            )}
                        </div>
                    </div>
                </header>

                {/* Main Content */}
                <main className="container mx-auto px-6 py-8 max-w-8xl">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Left Column - Task Details */}
                        <div className="lg:col-span-2 space-y-6">
                            {/* Task Info */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>任务信息</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <Label className="text-sm font-medium text-slate-500">仓库</Label>
                                            <p className="text-sm">{task.repo_url}</p>
                                        </div>
                                        <div>
                                            <Label className="text-sm font-medium text-slate-500">分支</Label>
                                            <p className="text-sm">{task.target_branch}</p>
                                        </div>
                                        <div>
                                            <Label className="text-sm font-medium text-slate-500">AI 模型</Label>
                                            <p className="text-sm">{task.agent?.toUpperCase()}</p>
                                        </div>
                                        <div>
                                            <Label className="text-sm font-medium text-slate-500">创建时间</Label>
                                            <p className="text-sm">{new Date(task.created_at || '').toLocaleString()}</p>
                                        </div>
                                    </div>

                                    {task.commit_hash && (
                                        <div>
                                            <Label className="text-sm font-medium text-slate-500">提交哈希</Label>
                                            <div className="flex items-center gap-2 mt-1">
                                                <code className="bg-slate-100 px-2 py-1 rounded text-sm">
                                                    {task.commit_hash.substring(0, 12)}
                                                </code>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => navigator.clipboard.writeText(task.commit_hash || '')}
                                                >
                                                    <Copy className="w-3 h-3" />
                                                </Button>
                                            </div>
                                        </div>
                                    )}

                                    {task.pr_url && (
                                        <div>
                                            <Label className="text-sm font-medium text-slate-500">拉取请求（PR）</Label>
                                            <div className="flex items-center gap-2 mt-1">
                                                <a 
                                                    href={task.pr_url} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className="text-blue-600 hover:underline text-sm"
                                                >
                                                    #{task.pr_number} - 在 GitHub 查看
                                                </a>
                                                <ExternalLink className="w-3 h-3 text-slate-400" />
                                            </div>
                                        </div>
                                    )}

                                    {task.error && (
                                        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                                            <div className="flex items-center gap-2 text-red-800 mb-2">
                                                <XCircle className="w-4 h-4" />
                                                <span className="font-medium">错误</span>
                                            </div>
                                            <p className="text-sm text-red-700">{task.error}</p>
                                        </div>
                                    )}

                                    {task.status === "running" && (
                                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                            <div className="flex items-center gap-3">
                                                <div className="animate-spin">
                                                    <AlertCircle className="w-5 h-5 text-blue-600" />
                                                </div>
                                                <div>
                                                    <div className="font-medium text-blue-900">AI 正在处理你的代码...</div>
                                                    <div className="text-sm text-blue-700 mt-1">
                                                        这可能需要几分钟。你可以放心关闭此页面。
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="mt-3 bg-blue-100 rounded-full h-2">
                                                <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{width: '60%'}}></div>
                                            </div>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Git Diff */}
                            {gitDiff && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center gap-2">
                                            <CheckCircle className="w-5 h-5 text-green-600" />
                                            代码变更
                                        </CardTitle>
                                        <CardDescription>
                                            查看 AI 生成的改动
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <DiffViewer 
                                            diff={gitDiff} 
                                            fileChanges={(task.execution_metadata as any)?.file_changes}
                                            stats={diffStats}
                                        />
                                    </CardContent>
                                </Card>
                            )}
                        </div>

                        {/* Right Column - Chat Messages */}
                        <div>
                            <Card className="h-fit">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <MessageSquare className="w-5 h-5" />
                                        任务消息
                                    </CardTitle>
                                    <CardDescription>
                                        此任务的对话记录
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {/* Chat Messages */}
                                    <div className="space-y-3 max-h-96 overflow-y-auto">
                                        {(task.chat_messages as unknown as ChatMessage[])?.map((message, index) => (
                                            <div 
                                                key={index}
                                                className={`p-3 rounded-lg ${
                                                    message.role === 'user' 
                                                        ? 'bg-blue-50 border border-blue-200' 
                                                        : 'bg-slate-50 border border-slate-200'
                                                }`}
                                            >
                                                <div className="flex items-center gap-2 mb-2">
                                                    <Badge variant={message.role === 'user' ? 'default' : 'secondary'}>
                                                        {message.role === 'user' ? '你' : '助手'}
                                                    </Badge>
                                                    <span className="text-xs text-slate-500">
                                                        {formatMessageTimestamp(message.timestamp)}
                                                    </span>
                                                </div>
                                                <p className="text-sm text-slate-700 whitespace-pre-wrap">
                                                    {message.content}
                                                </p>
                                            </div>
                                        )) || (
                                            <div className="text-center py-4 text-slate-500">
                                                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                                <p className="text-sm">暂无消息</p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Add Message Input */}
                                    <Separator />
                                    <div className="space-y-3">
                                        <Label className="text-sm font-medium">添加备注或后续指令</Label>
                                        <div className="flex gap-2">
                                            <Input
                                                value={newMessage}
                                                onChange={(e) => setNewMessage(e.target.value)}
                                                placeholder="输入你的消息..."
                                                onKeyPress={(e) => e.key === 'Enter' && handleAddMessage()}
                                            />
                                            <Button onClick={handleAddMessage} disabled={!newMessage.trim()}>
                                                <Plus className="w-4 h-4" />
                                            </Button>
                                        </div>
                                        <p className="text-xs text-slate-500">
                                            注意：此处仅用于记录，不会触发新的 AI 处理。
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </main>
            </div>
        </ProtectedRoute>
    );
}
