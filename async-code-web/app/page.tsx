"use client";

import { useState, useEffect, useRef } from "react";
import { Github, GitBranch, Code2, ExternalLink, CheckCircle, Clock, XCircle, AlertCircle, FileText, Eye, GitCommit, Bell, Settings, LogOut, User, FolderGit2, Plus, Archive, ArchiveRestore } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ProtectedRoute } from "@/components/protected-route";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { PRStatusBadge } from "@/components/pr-status-badge";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { SupabaseService } from "@/lib/supabase-service";
import { isSupabaseConfigured } from "@/lib/supabase";
import { Project, Task } from "@/types";
import { ClaudeIcon } from "@/components/icon/claude";
import { OpenAIIcon } from "@/components/icon/openai";
import { toast } from "sonner";

interface TaskWithProject extends Task {
    project?: Project
}

export default function Home() {
    const { user, signOut } = useAuth();
    const supabaseEnabled = isSupabaseConfigured();
    const [prompt, setPrompt] = useState("");
    const [selectedProject, setSelectedProject] = useState<string>("");
    const [customRepoUrl, setCustomRepoUrl] = useState("");
    const [branch, setBranch] = useState("main");
    const [availableBranches, setAvailableBranches] = useState<string[]>([]);
    const [isLoadingBranches, setIsLoadingBranches] = useState(false);
    const [branchLoadError, setBranchLoadError] = useState<string | null>(null);
    const lastRepoUrlRef = useRef<string>("");
    const [githubToken, setGithubToken] = useState("");
    const [rememberToken, setRememberToken] = useState(false);
    const [model, setModel] = useState("codex");
    const [tasks, setTasks] = useState<TaskWithProject[]>([]);
    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showNotification, setShowNotification] = useState(false);
    const [notificationMessage, setNotificationMessage] = useState("");
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [hasMoreTasks, setHasMoreTasks] = useState(true);
    const [taskPage, setTaskPage] = useState(0);
    const [archivedTaskIds, setArchivedTaskIds] = useState<Set<number>>(new Set());
    const [showArchived, setShowArchived] = useState(false);
    const TASKS_PER_PAGE = 10;

    // 初始化 GitHub 令牌和归档状态
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const sessionToken = sessionStorage.getItem('github-token');
            if (sessionToken) setGithubToken(sessionToken);

            localStorage.removeItem('github-token');
            localStorage.removeItem('github-token-remember');

            // 加载已归档的任务 ID
            const savedArchived = localStorage.getItem('archived-tasks');
            if (savedArchived) {
                try {
                    const parsed = JSON.parse(savedArchived);
                    if (Array.isArray(parsed)) {
                        const ids = parsed.map((id) => Number(id)).filter((id) => Number.isFinite(id));
                        setArchivedTaskIds(new Set(ids));
                    }
                } catch {
                    setArchivedTaskIds(new Set());
                }
            }

            const savedCustomRepoUrl = localStorage.getItem('last-custom-repo-url');
            if (savedCustomRepoUrl) {
                setCustomRepoUrl(savedCustomRepoUrl);
            }
        }
    }, []);

    // 记住最近使用的自定义仓库地址
    useEffect(() => {
        if (typeof window === 'undefined') return;
        if (!customRepoUrl.trim()) {
            localStorage.removeItem('last-custom-repo-url');
            return;
        }
        localStorage.setItem('last-custom-repo-url', customRepoUrl.trim());
    }, [customRepoUrl]);

    // 加载初始数据
    useEffect(() => {
        if (user?.id) {
            loadProjects();
            loadTasks();
        }
    }, [user?.id]);

    // 根据选择的仓库自动拉取分支列表（用于下拉选择）
    useEffect(() => {
        if (!user?.id) return;

        let repoUrl = "";
        if (selectedProject && selectedProject !== 'custom') {
            const project = projects.find((p) => p.id.toString() === selectedProject);
            repoUrl = project?.repo_url || "";
        } else if (selectedProject === 'custom') {
            repoUrl = customRepoUrl.trim();
        }

        const repoChanged = repoUrl !== lastRepoUrlRef.current;
        if (repoChanged) {
            lastRepoUrlRef.current = repoUrl;
            setAvailableBranches([]);
            setBranchLoadError(null);
        }

        if (!repoUrl || !githubToken.trim()) return;

        try {
            ApiService.parseGitHubUrl(repoUrl);
        } catch {
            return;
        }

        let cancelled = false;
        (async () => {
            setIsLoadingBranches(true);
            const result = await ApiService.getRepoBranches(user.id, githubToken, repoUrl);
            if (cancelled) return;

            if (result.status === 'success') {
                const branches = Array.isArray(result.repo?.branches) ? result.repo?.branches : [];
                setAvailableBranches(branches);
                const defaultBranch = result.repo?.default_branch;
                if (repoChanged && defaultBranch) {
                    setBranch(defaultBranch);
                }
            } else {
                setBranchLoadError(result.error || '获取分支失败');
                setAvailableBranches([]);
            }
            setIsLoadingBranches(false);
        })();

        return () => {
            cancelled = true;
        };
    }, [user?.id, selectedProject, customRepoUrl, projects, githubToken]);

    // GitHub 令牌变化时仅写入 sessionStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            if (githubToken.trim()) {
                sessionStorage.setItem('github-token', githubToken);
            } else {
                sessionStorage.removeItem('github-token');
            }
        }
    }, [githubToken]);

    // 轮询运行中任务的状态
    useEffect(() => {
        if (!user?.id) return;

        const runningTasks = tasks.filter(task => task.status === "running" || task.status === "pending");
        if (runningTasks.length === 0) return;

        const interval = setInterval(async () => {
            try {
                const updatedTasks = await Promise.all(
                    runningTasks.map(task => (
                        supabaseEnabled 
                            ? SupabaseService.getTask(task.id) 
                            : ApiService.getTaskStatus(user.id, task.id)
                    ))
                );

                setTasks(prevTasks => 
                    prevTasks.map(task => {
                        const updated = updatedTasks.find(t => t && t.id === task.id);
                        if (updated) {
                            // 检查状态变化并显示通知
                            if (task.status !== updated.status) {
                                if (updated.status === "completed") {
                                    setNotificationMessage(`🎉 任务 #${task.id} 已完成`);
                                    setShowNotification(true);
                                    setTimeout(() => setShowNotification(false), 5000);
                                } else if (updated.status === "failed") {
                                    setNotificationMessage(`❌ 任务 #${task.id} 失败，请查看详情。`);
                                    setShowNotification(true);
                                    setTimeout(() => setShowNotification(false), 5000);
                                }
                            }
                            return { ...task, ...updated };
                        }
                        return task;
                    })
                );
            } catch (error) {
                console.error('轮询任务状态失败：', error);
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [tasks, user?.id, supabaseEnabled]);

    const loadProjects = async () => {
        if (!user?.id) return;

        try {
            const projectData = await ApiService.getProjects(user.id);
            setProjects(projectData);

            // 自动选择最近使用的仓库
            if (projectData.length > 0) {
                const lastUsedProjectId = localStorage.getItem('last-used-project');
                const lastUsedProject = projectData.find(p => p.id.toString() === lastUsedProjectId);
                if (lastUsedProject) {
                    setSelectedProject(lastUsedProject.id.toString());
                    setBranch('main');
                } else {
                    // 没有最近使用的，选择第一个
                    setSelectedProject(projectData[0].id.toString());
                    setBranch('main');
                }
            }
        } catch (error) {
            console.error('加载项目失败：', error);
        }
    };

    const loadTasks = async (reset: boolean = true) => {
        if (!user?.id) return;
        
        try {
            if (!supabaseEnabled) {
                const taskData = await ApiService.getTasks(user.id);
                const enriched = taskData.map(task => ({
                    ...task,
                    project: projects.find(p => p.id === task.project_id)
                }));
                setTasks(enriched as TaskWithProject[]);
                setTaskPage(0);
                setHasMoreTasks(false);
                return;
            }

            const taskData = await SupabaseService.getTasks(undefined, {
                limit: TASKS_PER_PAGE,
                offset: 0
            });

            if (reset) {
                const enriched = taskData.map(task => ({
                    ...task,
                    project: projects.find(p => p.id === task.project_id)
                }));
                setTasks(enriched as TaskWithProject[]);
                setTaskPage(0);
                setHasMoreTasks(taskData.length === TASKS_PER_PAGE);
            }
        } catch (error) {
            console.error('加载任务失败：', error);
        }
    };

    const loadMoreTasks = async () => {
        if (!user?.id || isLoadingMore || !hasMoreTasks) return;
        if (!supabaseEnabled) return;
        
        try {
            setIsLoadingMore(true);
            const nextPage = taskPage + 1;
            const taskData = await SupabaseService.getTasks(undefined, {
                limit: TASKS_PER_PAGE,
                offset: nextPage * TASKS_PER_PAGE
            });
            
            if (taskData.length > 0) {
                const enriched = taskData.map(task => ({
                    ...task,
                    project: projects.find(p => p.id === task.project_id)
                }));
                setTasks(prev => [...prev, ...enriched as TaskWithProject[]]);
                setTaskPage(nextPage);
                setHasMoreTasks(taskData.length === TASKS_PER_PAGE);
            } else {
                setHasMoreTasks(false);
            }
        } catch (error) {
            console.error('加载更多任务失败：', error);
        } finally {
            setIsLoadingMore(false);
        }
    };

    const handleStartTask = async () => {
        if (!prompt.trim() || !githubToken.trim()) {
            toast.error('请填写提示词和 GitHub 令牌');
            return;
        }

        if (!user?.id) {
            toast.error('用户未登录');
            return;
        }

        let repoUrl = "";
        let projectId = undefined;

        if (selectedProject && selectedProject !== "custom") {
            const project = projects.find(p => p.id.toString() === selectedProject);
            if (project) {
                repoUrl = project.repo_url;
                projectId = project.id;
            }
        } else if (selectedProject === "custom") {
            const url = customRepoUrl.trim();
            if (!url) {
                toast.error('请填写自定义仓库地址');
                return;
            }
            try {
                ApiService.parseGitHubUrl(url);
            } catch (e) {
                toast.error(`仓库地址无效：${String(e)}`);
                return;
            }
            repoUrl = url;
            projectId = undefined;
        } else {
            toast.error('请选择一个项目或填写自定义仓库地址');
            return;
        }

        setIsLoading(true);
        try {
            const response = await ApiService.startTask(user.id, {
                prompt: prompt.trim(),
                repo_url: repoUrl,
                branch: branch,
                github_token: githubToken,
                model: model,
                project_id: projectId
            });

            // 先构造任务对象以便即时展示
            const newTask = {
                id: response.task_id,
                status: "pending",
                repo_url: repoUrl,
                target_branch: branch,
                agent: model,
                chat_messages: [{
                    role: 'user',
                    content: prompt.trim(),
                    timestamp: new Date().toISOString()
                }],
                created_at: new Date().toISOString(),
                user_id: user.id,
                project_id: projectId || null,
                project: projects.find(p => p.id === projectId)
            } as unknown as TaskWithProject;

            setTasks(prev => [newTask, ...prev]);
            setPrompt("");

            // 保存最近使用的项目
            if (projectId) {
                localStorage.setItem('last-used-project', String(projectId));
            }

            // 显示成功通知
            setNotificationMessage(`🚀 任务 #${response.task_id} 已启动`);
            setShowNotification(true);
            setTimeout(() => setShowNotification(false), 5000);
        } catch (error) {
            toast.error(`启动任务失败：${error}`);
        } finally {
            setIsLoading(false);
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
            case "pending": return <Clock className="w-3 h-3" />;
            case "running": return <AlertCircle className="w-3 h-3" />;
            case "completed": return <CheckCircle className="w-3 h-3" />;
            case "failed": return <XCircle className="w-3 h-3" />;
            default: return null;
        }
    };

    // 归档任务
    const archiveTask = (taskId: number) => {
        const newArchived = new Set(archivedTaskIds);
        newArchived.add(taskId);
        setArchivedTaskIds(newArchived);
        localStorage.setItem('archived-tasks', JSON.stringify([...newArchived]));
        toast.success('任务已归档');
    };

    // 取消归档
    const unarchiveTask = (taskId: number) => {
        const newArchived = new Set(archivedTaskIds);
        newArchived.delete(taskId);
        setArchivedTaskIds(newArchived);
        localStorage.setItem('archived-tasks', JSON.stringify([...newArchived]));
        toast.success('任务已取消归档');
    };

    const getAgentIcon = (agent: string) => {
        switch (agent) {
            case "claude": return <ClaudeIcon className="w-3 h-3" />;
            case "codex": return <OpenAIIcon className="w-3 h-3" />;
            default: return null;
        }
    };

    return (
        <ProtectedRoute>
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
            {/* Notification Banner */}
            {showNotification && (
                <div className="bg-green-600 text-white px-6 py-3 text-center relative">
                    <div className="flex items-center justify-center gap-2">
                        <Bell className="w-4 h-4" />
                        <span>{notificationMessage}</span>
                    </div>
                    <button
                        onClick={() => setShowNotification(false)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-white hover:text-gray-200"
                    >
                        <XCircle className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Header */}
            <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-black rounded-lg flex items-center justify-center">
                                <Code2 className="w-4 h-4 text-white" />
                            </div>
                            <div>
                                <h1 className="text-xl font-semibold text-slate-900">Async Code</h1>
                                <p className="text-sm text-slate-500">管理并行 AI 代码代理（Codex & Claude）</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            <Link href="/projects">
                                <Button variant="outline" className="gap-2">
                                    <FolderGit2 className="w-4 h-4" />
                                    项目
                                </Button>
                            </Link>
                            
                            <Link href="/settings">
                                <Button variant="outline" className="gap-2">
                                    <Settings className="w-4 h-4" />
                                    设置
                                </Button>
                            </Link>
                            
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Avatar className="cursor-pointer">
                                        <AvatarFallback>
                                            {user?.email ? 
                                                user.email.split('@')[0].slice(0, 2).toUpperCase() : 
                                                'U'
                                            }
                                        </AvatarFallback>
                                    </Avatar>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-56">
                                    <div className="p-2">
                                        <p className="text-sm font-medium">{user?.email}</p>
                                        <p className="text-xs text-slate-500">已登录</p>
                                    </div>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={signOut} className="gap-2 text-red-600">
                                        <LogOut className="w-4 h-4" />
                                        退出登录
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="container mx-auto px-6 py-8 max-w-6xl">
                <div className="space-y-8">
                    {/* Task Creation Section */}
                    <div className="space-y-6">
                        {/* Main Input Card */}
                        <Card>
                            <CardHeader>
                                <CardTitle>代码生成提示</CardTitle>
                                <CardDescription>
                                    描述你希望 AI 实现的功能、修复或改进
                                </CardDescription>
                                {!githubToken.trim() && (
                                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                                        <div className="flex items-start gap-2 text-amber-800">
                                            <Github className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                            <div className="text-sm">
                                                <strong>需要 GitHub 令牌：</strong> 请在{" "}
                                                <Link href="/settings" className="underline hover:text-amber-900">
                                                    设置
                                                </Link>{" "}
                                                中配置 GitHub 令牌以启用代码生成。
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-2">
                                    <Label htmlFor="prompt">提示词</Label>
                                    <Textarea
                                        id="prompt"
                                        value={prompt}
                                        onChange={(e) => setPrompt(e.target.value)}
                                        placeholder="例如：为导航栏添加深色模式开关，并持久化用户偏好..."
                                        className="min-h-[120px] resize-none"
                                    />
                                </div>

                                <Separator />

                                {/* Repository Configuration */}
                                <div className="space-y-4">
                                    <h3 className="font-medium text-slate-900 flex items-center gap-2">
                                        <Github className="w-4 h-4" />
                                        仓库设置
                                    </h3>
                                    
                                    {/* Project Selection - Full Width */}
                                    <div className="space-y-2">
                                        <Label htmlFor="project" className="flex items-center gap-2">
                                            <FolderGit2 className="w-3 h-3" />
                                            项目
                                        </Label>
                                        <Select value={selectedProject} onValueChange={setSelectedProject}>
                                            <SelectTrigger id="project" className="w-full">
                                                <SelectValue placeholder="选择项目" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {projects.map((project) => (
                                                    <SelectItem key={project.id} value={project.id.toString()}>
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <Github className="w-3 h-3 flex-shrink-0" />
                                                            <span className="truncate">{project.name}</span>
                                                            <span className="text-slate-500 text-xs flex-shrink-0">
                                                                ({project.repo_owner}/{project.repo_name})
                                                            </span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                                <SelectItem value="custom">自定义仓库地址</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        {projects.length === 0 && (
                                            <p className="text-sm text-slate-500">
                                                未找到项目。{" "}
                                                <Link href="/projects" className="text-blue-600 hover:underline">
                                                    先创建一个项目
                                                </Link>
                                            </p>
                                        )}
                                    </div>

                                    {selectedProject === 'custom' && (
                                        <div className="space-y-2">
                                            <Label htmlFor="custom-repo">自定义仓库地址</Label>
                                            <Input
                                                id="custom-repo"
                                                value={customRepoUrl}
                                                onChange={(e) => setCustomRepoUrl(e.target.value)}
                                                placeholder="https://github.com/owner/repo 或 git@github.com:owner/repo.git"
                                            />
                                            <p className="text-sm text-slate-500">目前仅支持 GitHub 仓库地址（HTTPS / SSH）。</p>
                                        </div>
                                    )}

                                    {/* Branch and Model in a responsive grid */}
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="branch" className="flex items-center gap-2">
                                                <GitBranch className="w-3 h-3" />
                                                分支
                                            </Label>
                                            {availableBranches.length > 0 ? (
                                                <Select value={branch} onValueChange={setBranch}>
                                                    <SelectTrigger id="branch" className="w-full">
                                                        <SelectValue placeholder="选择分支" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {availableBranches.map((b) => (
                                                            <SelectItem key={b} value={b}>{b}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            ) : (
                                                <Input
                                                    id="branch"
                                                    value={branch}
                                                    onChange={(e) => setBranch(e.target.value)}
                                                    placeholder="main"
                                                    className="w-full"
                                                />
                                            )}
                                            {isLoadingBranches && (
                                                <p className="text-sm text-slate-500">正在获取分支列表...</p>
                                            )}
                                            {!isLoadingBranches && branchLoadError && (
                                                <p className="text-sm text-amber-700">{branchLoadError}</p>
                                            )}
                                        </div>
                                        
                                        <div className="space-y-2">
                                            <Label htmlFor="model" className="flex items-center gap-2">
                                                <Code2 className="w-3 h-3" />
                                                代码代理
                                            </Label>
                                            <Select value={model} onValueChange={setModel}>
                                                <SelectTrigger id="model" className="w-full">
                                                    <SelectValue placeholder="选择 AI 模型" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="claude">
                                                        <div className="flex items-center gap-3">
                                                            <ClaudeIcon className="w-4 h-4 flex-shrink-0" />
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-medium">Claude Code</span>
                                                                <span className="text-xs text-slate-500">• Anthropic 的自主编码工具</span>
                                                            </div>
                                                        </div>
                                                    </SelectItem>
                                                    <SelectItem value="codex">
                                                        <div className="flex items-center gap-3">
                                                            <OpenAIIcon className="w-4 h-4 flex-shrink-0" />
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-medium">Codex</span>
                                                                <span className="text-xs text-slate-500">• OpenAI 的轻量级编码代理</span>
                                                            </div>
                                                        </div>
                                                    </SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex justify-start pt-2">
                                    <Button
                                        onClick={handleStartTask}
                                        disabled={isLoading || !selectedProject || !prompt.trim() || !githubToken.trim()}
                                        className="gap-2 rounded-full min-w-[100px]"
                                    >
                                        <Code2 className="w-4 h-4" />
                                        {isLoading ? '生成中...' : '开始生成'}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        {/* 运行中任务概览 */}
                        {tasks.filter(task => task.status === "running" || task.status === "pending").length > 0 && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <AlertCircle className="w-5 h-5 text-blue-600" />
                                        进行中的任务
                                    </CardTitle>
                                    <CardDescription>
                                        当前有 {tasks.filter(task => task.status === "running" || task.status === "pending").length} 个任务在运行
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="animate-spin">
                                                <AlertCircle className="w-5 h-5 text-blue-600" />
                                            </div>
                                            <div>
                                                <div className="font-medium text-blue-900">AI 代理正在处理你的代码...</div>
                                                <div className="text-sm text-blue-700 mt-1">
                                                    你可以启动更多任务，或在任务列表中查看进度。
                                                </div>
                                            </div>
                                        </div>
                                        <div className="mt-3 bg-blue-100 rounded-full h-2">
                                            <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{width: '60%'}}></div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    {/* Task List Section */}
                    <div className="space-y-6">
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-lg">全部任务</CardTitle>
                                    <div className="flex items-center gap-3">
                                        <Button
                                            variant={showArchived ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setShowArchived(!showArchived)}
                                            className="gap-1"
                                        >
                                            <Archive className="w-3 h-3" />
                                            {showArchived ? '隐藏已归档' : `已归档 (${archivedTaskIds.size})`}
                                        </Button>
                                        <div className="text-sm text-slate-500">
                                            已加载 {tasks.length} 个任务
                                        </div>
                                    </div>
                                </div>
                                <CardDescription>
                                    跟踪所有自动化任务
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {tasks.length === 0 ? (
                                    <div className="text-center py-8 text-slate-500">
                                        <Code2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                        <p className="text-sm">暂无任务</p>
                                        <p className="text-xs">在上方开始你的第一个自动化任务</p>
                                    </div>
                                ) : (
                                    <>
                                        <div className="space-y-3 max-h-[500px] overflow-y-auto">
                                            {tasks
                                                .filter(task => showArchived ? archivedTaskIds.has(task.id) : !archivedTaskIds.has(task.id))
                                                .map((task) => (
                                                <div key={task.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <TaskStatusBadge status={task.status || ''} />
                                                            {task.pr_url && task.pr_number && (
                                                                <PRStatusBadge 
                                                                    prUrl={task.pr_url}
                                                                    prNumber={task.pr_number}
                                                                    prBranch={task.pr_branch}
                                                                    variant="badge"
                                                                    size="sm"
                                                                />
                                                            )}
                                                            <span className="text-xs text-slate-500 flex items-center gap-1">
                                                                #{task.id} • {getAgentIcon(task.agent || '')} {task.agent?.toUpperCase()}
                                                            </span>
                                                        </div>
                                                        <p className="text-sm font-medium text-slate-900 truncate">
                                                            {(task.chat_messages as any[])?.[0]?.content?.substring(0, 50) || ''}...
                                                        </p>
                                                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                                                            {task.project ? (
                                                                <>
                                                                    <FolderGit2 className="w-3 h-3" />
                                                                    {task.project.repo_name}
                                                                </>
                                                            ) : (
                                                                <>
                                                                    <Github className="w-3 h-3" />
                                                                    自定义
                                                                </>
                                                            )}
                                                            <span>•</span>
                                                            <span>{new Date(task.created_at || '').toLocaleDateString()}</span>
                                                        </div>
                                                        {(task.status === 'running' || task.status === 'pending') && (
                                                            <div className="text-xs text-slate-600 mt-1">
                                                                阶段：{((task as any).stage || (task as any).execution_metadata?.stage || '—')}
                                                            </div>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {task.status === "completed" && (
                                                            <CheckCircle className="w-4 h-4 text-green-600" />
                                                        )}
                                                        {task.status === "running" && (
                                                            <div className="animate-spin">
                                                                <AlertCircle className="w-4 h-4 text-blue-600" />
                                                            </div>
                                                        )}
                                                        {/* 归档按钮 - 仅对已完成或失败的任务显示 */}
                                                        {(task.status === "completed" || task.status === "failed") && (
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                onClick={() => archivedTaskIds.has(task.id) ? unarchiveTask(task.id) : archiveTask(task.id)}
                                                                title={archivedTaskIds.has(task.id) ? '取消归档' : '归档'}
                                                            >
                                                                {archivedTaskIds.has(task.id) ? (
                                                                    <ArchiveRestore className="w-3 h-3" />
                                                                ) : (
                                                                    <Archive className="w-3 h-3" />
                                                                )}
                                                            </Button>
                                                        )}
                                                        <Link href={`/tasks/${task.id}`}>
                                                            <Button variant="ghost" size="sm">
                                                                <Eye className="w-3 h-3" />
                                                            </Button>
                                                        </Link>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        
                                        {/* Load More Button */}
                                        {hasMoreTasks && (
                                            <div className="flex justify-center pt-4">
                                                <Button 
                                                    onClick={loadMoreTasks}
                                                    disabled={isLoadingMore}
                                                    variant="outline"
                                                    className="gap-2"
                                                >
                                                    {isLoadingMore ? (
                                                        <>
                                                            <div className="animate-spin">
                                                                <AlertCircle className="w-4 h-4" />
                                                            </div>
                                                            加载中...
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Plus className="w-4 h-4" />
                                                            加载更多
                                                        </>
                                                    )}
                                                </Button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </main>
        </div>
        </ProtectedRoute>
    );
}
