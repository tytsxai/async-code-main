"use client";

import { useState, useEffect } from "react";
import { Github, CheckCircle, ArrowLeft, Settings, Key, Shield, Info, Code } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { CodeAgentSettings } from "@/components/code-agent-settings";
import { ApiService } from "@/lib/api-service";
import { useAuth } from "@/contexts/auth-context";
import { ProtectedRoute } from "@/components/protected-route";
import { isSupabaseConfigured } from "@/lib/supabase";

import Link from "next/link";

export default function SettingsPage() {
    const { user } = useAuth();
    const supabaseEnabled = isSupabaseConfigured();
    const [githubToken, setGithubToken] = useState("");
    const [rememberToken, setRememberToken] = useState(false);
    const [tokenValidation, setTokenValidation] = useState<{status: string; user?: string; repo?: {name?: string; permissions?: {read?: boolean; write?: boolean; create_branches?: boolean; admin?: boolean}}; error?: string} | null>(null);
    const [isValidatingToken, setIsValidatingToken] = useState(false);
    const [repoUrl, setRepoUrl] = useState("https://github.com/ObservedObserver/streamlit-react");

    // 初始化 GitHub Token（默认仅 sessionStorage；可选持久化到 localStorage）
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const savedRemember = localStorage.getItem('github-token-remember');
            const remember = savedRemember === 'true';
            setRememberToken(remember);

            const sessionToken = sessionStorage.getItem('github-token');
            const localToken = remember ? localStorage.getItem('github-token') : null;
            const token = sessionToken || localToken;
            if (token) setGithubToken(token);
        }
    }, []);

    // GitHub 令牌变化时写入 sessionStorage；如选择“记住”则同步写入 localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            if (githubToken.trim()) {
                sessionStorage.setItem('github-token', githubToken);
                if (rememberToken) {
                    localStorage.setItem('github-token', githubToken);
                } else {
                    localStorage.removeItem('github-token');
                }
            } else {
                sessionStorage.removeItem('github-token');
                localStorage.removeItem('github-token');
            }
        }
    }, [githubToken, rememberToken]);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        localStorage.setItem('github-token-remember', rememberToken ? 'true' : 'false');
        if (!rememberToken) {
            localStorage.removeItem('github-token');
        } else if (githubToken.trim()) {
            localStorage.setItem('github-token', githubToken);
        }
    }, [rememberToken, githubToken]);

    const handleValidateToken = async () => {
        if (!githubToken.trim() || !repoUrl.trim()) {
            toast.error('请填写 GitHub 令牌和仓库地址');
            return;
        }

        setIsValidatingToken(true);
        try {
            if (!user?.id) {
                toast.error('用户未登录');
                return;
            }

            const data = await ApiService.validateGitHubToken(user.id, githubToken, repoUrl);
            setTokenValidation(data);
            
            if (data.status === 'success') {
                const permissions = data.repo?.permissions || {};
                const permissionSummary = [
                    `用户：${data.user}`,
                    `仓库：${data.repo?.name || 'N/A'}`,
                    `读取：${permissions.read ? '是' : '否'}`,
                    `写入：${permissions.write ? '是' : '否'}`,
                    `创建分支：${permissions.create_branches ? '是' : '否'}`,
                    `管理员：${permissions.admin ? '是' : '否'}`
                ].join('\n');
                
                if (permissions.create_branches) {
                    toast.success(`✅ 令牌验证通过，可创建 PR！\n\n${permissionSummary}`);
                } else {
                    toast.warning(`⚠️ 令牌验证部分通过！\n\n${permissionSummary}\n\n❌ 无法创建分支，因而不能创建 PR。\n请确保令牌包含 'repo' 权限（而非仅 'public_repo'）。`);
                }
            } else {
                toast.error(`❌ 令牌验证失败：${data.error}`);
            }
        } catch (error) {
            toast.error(`验证令牌失败：${error}`);
            setTokenValidation({ status: 'error', error: String(error) });
        } finally {
            setIsValidatingToken(false);
        }
    };

    const handleExportLocalDb = async () => {
        if (!user?.id) {
            toast.error('用户未登录');
            return;
        }
        const result = await ApiService.exportLocalDb(user.id);
        if (result.status !== 'success') {
            toast.error(result.error || '导出失败');
            return;
        }

        const payload = JSON.stringify(result.data, null, 2);
        const blob = new Blob([payload], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `async-code-local-db-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        toast.success('已导出本地数据');
    };

    const handleResetLocalDb = async () => {
        if (!user?.id) {
            toast.error('用户未登录');
            return;
        }
        if (!confirm('确认清空本地模式下的项目与任务数据？此操作不可恢复。')) return;
        const result = await ApiService.resetLocalDb(user.id);
        if (result.status !== 'success') {
            toast.error(result.error || '清空失败');
            return;
        }
        toast.success('已清空本地数据');
    };

    return (
        <ProtectedRoute>
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
            {/* Header */}
            <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <Link href="/" className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors">
                                <ArrowLeft className="w-4 h-4" />
                                返回
                            </Link>
                            <div className="w-8 h-8 bg-slate-700 rounded-lg flex items-center justify-center">
                                <Settings className="w-4 h-4 text-white" />
                            </div>
                            <div>
                                <h1 className="text-xl font-semibold text-slate-900">设置</h1>
                                <p className="text-sm text-slate-500">配置 GitHub 认证与代码代理环境</p>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="container mx-auto px-6 py-8 max-w-3xl">
                <div className="space-y-6">
                    {/* GitHub Authentication Section */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Github className="w-5 h-5" />
                                GitHub 认证
                            </CardTitle>
                            <CardDescription>
                                配置 GitHub 个人访问令牌以访问仓库并创建 PR
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-2">
                                <Label htmlFor="github-token" className="flex items-center gap-2">
                                    <Key className="w-4 h-4" />
                                    个人访问令牌
                                </Label>
                                <Input
                                    id="github-token"
                                    type="password"
                                    value={githubToken}
                                    onChange={(e) => setGithubToken(e.target.value)}
                                    placeholder="ghp_..."
                                    className="font-mono"
                                />
                                <label className="flex items-center gap-2 text-sm text-slate-700">
                                    <input
                                        type="checkbox"
                                        checked={rememberToken}
                                        onChange={(e) => setRememberToken(e.target.checked)}
                                    />
                                    记住令牌（仅此设备）
                                </label>
                                <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                                    <div className="flex items-start gap-2 text-blue-800">
                                        <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                        <div className="text-sm">
                                        默认仅在当前会话中保存；启用“记住”会写入浏览器本地存储，用于访问仓库和创建 PR。
                                        请确保令牌包含 <strong>repo</strong> 权限以获得完整功能。
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Test Repository URL */}
                            <div className="space-y-2">
                                <Label htmlFor="test-repo">测试仓库地址（用于验证）</Label>
                                <Input
                                    id="test-repo"
                                    type="url"
                                    value={repoUrl}
                                    onChange={(e) => setRepoUrl(e.target.value)}
                                    placeholder="https://github.com/owner/repo"
                                />
                                <p className="text-sm text-slate-600">
                                    使用任意可访问仓库来测试令牌权限
                                </p>
                            </div>

                            {/* Validation Section */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <Button
                                        onClick={handleValidateToken}
                                        disabled={isValidatingToken || !githubToken.trim() || !repoUrl.trim()}
                                        variant="outline"
                                        className="gap-2"
                                    >
                                        <CheckCircle className="w-4 h-4" />
                                        {isValidatingToken ? '验证中...' : '验证令牌'}
                                    </Button>
                                    {tokenValidation && (
                                        <div className="flex items-center gap-2">
                                            {tokenValidation.status === 'success' ? (
                                                <div className="flex items-center gap-1 text-sm text-green-600">
                                                    <CheckCircle className="w-4 h-4" />
                                                    令牌有效
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-1 text-sm text-red-600">
                                                    <Shield className="w-4 h-4" />
                                                    令牌无效
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {tokenValidation && tokenValidation.status === 'success' && (
                                    <Card className="bg-green-50 border-green-200">
                                        <CardContent className="pt-6">
                                            <div className="space-y-2">
                                                <div className="flex items-center gap-2 text-green-800">
                                                    <CheckCircle className="w-4 h-4" />
                                                    <span className="font-medium">令牌验证成功</span>
                                                </div>
                                                <div className="text-sm text-green-700">
                                                    <div>用户：<strong>{tokenValidation.user}</strong></div>
                                                    <div>仓库：<strong>{tokenValidation.repo?.name || 'N/A'}</strong></div>
                                                    <div className="mt-2">
                                                        <strong>权限：</strong>
                                                        <ul className="ml-4 mt-1 space-y-1">
                                                            <li>读取：{tokenValidation.repo?.permissions?.read ? '✅' : '❌'}</li>
                                                            <li>写入：{tokenValidation.repo?.permissions?.write ? '✅' : '❌'}</li>
                                                            <li>创建分支：{tokenValidation.repo?.permissions?.create_branches ? '✅' : '❌'}</li>
                                                            <li>管理员：{tokenValidation.repo?.permissions?.admin ? '✅' : '❌'}</li>
                                                        </ul>
                                                    </div>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}

                                {tokenValidation && tokenValidation.status === 'error' && (
                                    <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                                        <div className="flex items-start gap-2 text-red-800">
                                            <Shield className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                            <div className="text-sm">
                                                <strong>验证错误：</strong> {tokenValidation.error}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Code Agent Settings */}
                    <CodeAgentSettings />

                    {!supabaseEnabled && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Code className="w-5 h-5" />
                                    本地数据管理
                                </CardTitle>
                                <CardDescription>
                                    仅在本地模式下可用：导出/清空当前用户的项目与任务数据
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="flex gap-3">
                                <Button variant="outline" onClick={handleExportLocalDb}>导出本地数据</Button>
                                <Button variant="destructive" onClick={handleResetLocalDb}>清空本地数据</Button>
                            </CardContent>
                        </Card>
                    )}

                    {/* Token Creation Instructions */}
                    <Card className="bg-blue-50 border-blue-200">
                        <CardHeader>
                        <CardTitle className="text-lg">创建 GitHub 个人访问令牌</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3 text-sm">
                                <div>
                                    <strong>1. 前往 GitHub 设置</strong>
                                    <p className="text-blue-700 ml-4">依次进入 Settings → Developer settings → Personal access tokens → Tokens (classic)</p>
                                </div>
                                <div>
                                    <strong>2. 生成新令牌</strong>
                                    <p className="text-blue-700 ml-4">点击 “Generate new token (classic)” 并填写描述性名称</p>
                                </div>
                                <div>
                                    <strong>3. 必需权限</strong>
                                    <p className="text-blue-700 ml-4">勾选 <strong>repo</strong> 权限以获得完整仓库访问（包括私有仓库）</p>
                                </div>
                                <div>
                                    <strong>4. 复制并保存</strong>
                                    <p className="text-blue-700 ml-4">立即复制生成的令牌并粘贴到上方（之后无法再次查看）</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </main>
        </div>
        </ProtectedRoute>
    );
} 
