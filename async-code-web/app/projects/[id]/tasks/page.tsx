"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Clock, CheckCircle, XCircle, AlertCircle, Eye, Plus, Github, FolderGit2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/protected-route";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { Task, Project } from "@/types";

interface TaskWithProject extends Task {
    project?: Project
}

export default function ProjectTasksPage() {
    const { user } = useAuth();
    const params = useParams();
    const projectId = parseInt(params.id as string);
    
    const [project, setProject] = useState<Project | null>(null);
    const [tasks, setTasks] = useState<TaskWithProject[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (user?.id && projectId) {
            loadProject();
            loadTasks();
        }
    }, [user?.id, projectId]);

    const loadProject = async () => {
        if (!user?.id) return;
        
        try {
            const projectData = await ApiService.getProject(user.id, projectId);
            setProject(projectData);
        } catch (error) {
            console.error('加载项目失败：', error);
        }
    };

    const loadTasks = async () => {
        if (!user?.id) return;
        
        try {
            setLoading(true);
            const taskData = await ApiService.getTasks(user.id, projectId);
            setTasks(taskData);
        } catch (error) {
            console.error('加载任务失败：', error);
        } finally {
            setLoading(false);
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

    if (!project) {
        return (
            <ProtectedRoute>
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                    <div className="text-center">
                        <XCircle className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                        <h3 className="text-xl font-semibold text-slate-900 mb-2">未找到项目</h3>
                        <p className="text-slate-600 mb-6">该项目不存在或你没有访问权限。</p>
                        <Link href="/projects">
                            <Button>返回项目列表</Button>
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
                                <Link href="/projects" className="text-slate-600 hover:text-slate-900 flex items-center gap-2">
                                    <ArrowLeft className="w-4 h-4" />
                                    返回项目列表
                                </Link>
                                <div>
                                    <h1 className="text-xl font-semibold text-slate-900 flex items-center gap-2">
                                        <FolderGit2 className="w-5 h-5" />
                                        {project.name} 任务
                                    </h1>
                                    <p className="text-sm text-slate-500 flex items-center gap-1">
                                        <Github className="w-3 h-3" />
                                        {project.repo_owner}/{project.repo_name}
                                    </p>
                                </div>
                            </div>
                            <Link href={`/?project=${projectId}`}>
                                <Button className="gap-2">
                                    <Plus className="w-4 h-4" />
                                    新建任务
                                </Button>
                            </Link>
                        </div>
                    </div>
                </header>

                {/* Main Content */}
                <main className="container mx-auto px-6 py-8 max-w-4xl">
                    {/* Project Info */}
                    <Card className="mb-6">
                        <CardContent className="pt-6">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="text-center p-4 bg-slate-50 rounded-lg">
                                    <div className="text-2xl font-bold text-slate-900">{tasks.length}</div>
                                    <div className="text-sm text-slate-500">任务总数</div>
                                </div>
                                <div className="text-center p-4 bg-green-50 rounded-lg">
                                    <div className="text-2xl font-bold text-green-700">
                                        {tasks.filter(t => t.status === 'completed').length}
                                    </div>
                                    <div className="text-sm text-green-600">已完成</div>
                                </div>
                                <div className="text-center p-4 bg-blue-50 rounded-lg">
                                    <div className="text-2xl font-bold text-blue-700">
                                        {tasks.filter(t => t.status === 'running' || t.status === 'pending').length}
                                    </div>
                                    <div className="text-sm text-blue-600">进行中</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Tasks List */}
                    <Card>
                        <CardHeader>
                            <CardTitle>全部任务</CardTitle>
                            <CardDescription>
                                本项目的自动化任务
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {tasks.length === 0 ? (
                                <div className="text-center py-12">
                                    <AlertCircle className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                                    <h3 className="text-xl font-semibold text-slate-900 mb-2">暂无任务</h3>
                                    <p className="text-slate-600 mb-6">为该项目开始第一个自动化任务</p>
                                    <Link href={`/?project=${projectId}`}>
                                        <Button size="lg" className="gap-2">
                                            <Plus className="w-4 h-4" />
                                            创建首个任务
                                        </Button>
                                    </Link>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {tasks.map((task) => (
                                        <div key={task.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-slate-50">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-3 mb-2">
                                                    <Badge variant={getStatusVariant(task.status || '')} className="gap-1">
                                                        {getStatusIcon(task.status || '')}
                                                        {getStatusLabel(task.status || '')}
                                                    </Badge>
                                                    <span className="text-sm text-slate-500">
                                                        任务 #{task.id}
                                                    </span>
                                                    <span className="text-sm text-slate-500">
                                                        {task.agent?.toUpperCase()}
                                                    </span>
                                                </div>
                                                <p className="text-sm font-medium text-slate-900 truncate mb-1">
                                                    {(task.chat_messages as any[])?.[0]?.content || '暂无提示词'}
                                                </p>
                                                <div className="flex items-center gap-4 text-xs text-slate-500">
                                                    <span>创建时间：{new Date(task.created_at || '').toLocaleString()}</span>
                                                    {task.completed_at && (
                                                        <span>完成时间：{new Date(task.completed_at).toLocaleString()}</span>
                                                    )}
                                                    {task.commit_hash && (
                                                        <span>提交：{task.commit_hash.substring(0, 8)}</span>
                                                    )}
                                                    {task.pr_number && (
                                                        <span>PR：#{task.pr_number}</span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {task.pr_url && (
                                                    <Button variant="outline" size="sm" asChild>
                                                        <a href={task.pr_url} target="_blank" rel="noopener noreferrer">
                                                            <Github className="w-3 h-3" />
                                                        </a>
                                                    </Button>
                                                )}
                                                <Link href={`/tasks/${task.id}`}>
                                                    <Button variant="outline" size="sm">
                                                        <Eye className="w-4 h-4" />
                                                    </Button>
                                                </Link>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </main>
            </div>
        </ProtectedRoute>
    );
}
