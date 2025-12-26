"use client";

import { useState, useEffect } from "react";
import { Plus, Settings, Trash2, Activity, ExternalLink, Github } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ProtectedRoute } from "@/components/protected-route";
import { useAuth } from "@/contexts/auth-context";
import { ApiService } from "@/lib/api-service";
import { Project } from "@/types";
import { toast } from "sonner";

interface ProjectWithStats extends Project {
    task_count?: number
    completed_tasks?: number
    active_tasks?: number
}

export default function ProjectsPage() {
    const { user } = useAuth();
    const [projects, setProjects] = useState<ProjectWithStats[]>([]);
    const [loading, setLoading] = useState(true);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        repo_url: ''
    });

    useEffect(() => {
        if (user?.id) {
            loadProjects();
        }
    }, [user?.id]);

    const loadProjects = async () => {
        if (!user?.id) return;
        
        try {
            setLoading(true);
            const data = await ApiService.getProjects(user.id);
            setProjects(data);
        } catch (error) {
            console.error('加载项目失败：', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateProject = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!user?.id) return;
        
        try {
            await ApiService.createProject(user.id, {
                name: formData.name,
                description: formData.description,
                repo_url: formData.repo_url
            });

            setFormData({ name: '', description: '', repo_url: '' });
            setCreateDialogOpen(false);
            loadProjects();
        } catch (error) {
            console.error('创建项目失败：', error);
            toast.error('创建项目失败，请检查 GitHub 地址格式。');
        }
    };

    const handleDeleteProject = async (id: number) => {
        if (!user?.id) return;
        
        if (!confirm('确定删除此项目吗？同时会删除所有相关任务。')) {
            return;
        }

        try {
            await ApiService.deleteProject(user.id, id);
            loadProjects();
        } catch (error) {
            console.error('删除项目失败：', error);
            toast.error('删除项目失败');
        }
    };

    if (loading) {
        return (
            <ProtectedRoute>
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
                        <p className="text-slate-600 mt-2">正在加载项目...</p>
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
                                <Link href="/" className="text-slate-600 hover:text-slate-900">
                                    ← 返回仪表盘
                                </Link>
                                <div>
                                    <h1 className="text-2xl font-semibold text-slate-900">项目</h1>
                                    <p className="text-sm text-slate-500">管理你的 GitHub 仓库与自动化任务</p>
                                </div>
                            </div>
                            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button className="gap-2">
                                        <Plus className="w-4 h-4" />
                                        新建项目
                                    </Button>
                                </DialogTrigger>
                                <DialogContent>
                                    <DialogHeader>
                                        <DialogTitle>创建新项目</DialogTitle>
                                        <DialogDescription>
                                            添加 GitHub 仓库以开始 AI 自动化
                                        </DialogDescription>
                                    </DialogHeader>
                                    <form onSubmit={handleCreateProject} className="space-y-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="name">项目名称</Label>
                                            <Input
                                                id="name"
                                                value={formData.name}
                                                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                                                placeholder="我的项目"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="repo_url">GitHub 仓库地址</Label>
                                            <Input
                                                id="repo_url"
                                                type="url"
                                                value={formData.repo_url}
                                                onChange={(e) => setFormData(prev => ({ ...prev, repo_url: e.target.value }))}
                                                placeholder="https://github.com/owner/repo"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="description">描述（可选）</Label>
                                            <Textarea
                                                id="description"
                                                value={formData.description}
                                                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                                                placeholder="简要说明你的项目..."
                                                rows={3}
                                            />
                                        </div>
                                        <div className="flex justify-end gap-2">
                                            <Button type="button" variant="outline" onClick={() => setCreateDialogOpen(false)}>
                                                取消
                                            </Button>
                                            <Button type="submit">创建项目</Button>
                                        </div>
                                    </form>
                                </DialogContent>
                            </Dialog>
                        </div>
                    </div>
                </header>

                {/* Main Content */}
                <main className="container mx-auto px-6 py-8">
                    {projects.length === 0 ? (
                        <div className="text-center py-12">
                            <Github className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                            <h3 className="text-xl font-semibold text-slate-900 mb-2">暂无项目</h3>
                            <p className="text-slate-600 mb-6">创建第一个项目以开始 AI 自动化</p>
                            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button size="lg" className="gap-2">
                                        <Plus className="w-4 h-4" />
                                        创建第一个项目
                                    </Button>
                                </DialogTrigger>
                            </Dialog>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {projects.map((project) => (
                                <Card key={project.id} className="hover:shadow-lg transition-shadow">
                                    <CardHeader>
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <CardTitle className="text-lg">{project.name}</CardTitle>
                                                <CardDescription className="flex items-center gap-1 mt-1">
                                                    <Github className="w-3 h-3" />
                                                    {project.repo_owner}/{project.repo_name}
                                                </CardDescription>
                                            </div>
                                            <div className="flex gap-1">
                                                <Button variant="ghost" size="sm" asChild>
                                                    <Link href={`/projects/${project.id}`}>
                                                        <Settings className="w-4 h-4" />
                                                    </Link>
                                                </Button>
                                                <Button 
                                                    variant="ghost" 
                                                    size="sm"
                                                    onClick={() => handleDeleteProject(project.id)}
                                                    className="text-red-600 hover:text-red-700"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                        {project.description && (
                                            <p className="text-sm text-slate-600 mt-2">{project.description}</p>
                                        )}
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-4">
                                            {/* Project Stats */}
                                            <div className="grid grid-cols-3 gap-2 text-center">
                                                <div className="p-2 bg-slate-50 rounded-lg">
                                                    <div className="text-lg font-semibold text-slate-900">{project.task_count || 0}</div>
                                                    <div className="text-xs text-slate-500">任务总数</div>
                                                </div>
                                                <div className="p-2 bg-green-50 rounded-lg">
                                                    <div className="text-lg font-semibold text-green-700">{project.completed_tasks || 0}</div>
                                                    <div className="text-xs text-green-600">已完成</div>
                                                </div>
                                                <div className="p-2 bg-blue-50 rounded-lg">
                                                    <div className="text-lg font-semibold text-blue-700">{project.active_tasks || 0}</div>
                                                    <div className="text-xs text-blue-600">进行中</div>
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="flex gap-2">
                                                <Button variant="outline" size="sm" className="flex-1" asChild>
                                                    <Link href={`/projects/${project.id}/tasks`}>
                                                        <Activity className="w-4 h-4 mr-1" />
                                                        查看任务
                                                    </Link>
                                                </Button>
                                                <Button variant="outline" size="sm" asChild>
                                                    <a href={project.repo_url} target="_blank" rel="noopener noreferrer">
                                                        <ExternalLink className="w-4 h-4" />
                                                    </a>
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </main>
            </div>
        </ProtectedRoute>
    );
}
