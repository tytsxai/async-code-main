'use client'

import { Auth } from '@supabase/auth-ui-react'
import { ThemeSupa } from '@supabase/auth-ui-shared'
import { getSupabase, isSupabaseConfigured } from '@/lib/supabase'
import { ensureLocalUser } from '../../lib/local-auth'
import { useAuth } from '@/contexts/auth-context'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Code2 } from 'lucide-react'

export default function SignIn() {
    const { user, loading } = useAuth()
    const router = useRouter()
    const supabaseEnabled = isSupabaseConfigured()

    useEffect(() => {
        if (user && !loading) {
            router.push('/')
        }
    }, [user, loading, router])

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900"></div>
            </div>
        )
    }

    if (user) {
        return null // Will redirect
    }

    if (!supabaseEnabled) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
                <div className="w-full max-w-md">
                    <div className="text-center mb-8">
                        <div className="w-12 h-12 bg-black rounded-lg flex items-center justify-center mx-auto mb-4">
                            <Code2 className="w-6 h-6 text-white" />
                        </div>
                        <h1 className="text-2xl font-bold text-slate-900 mb-2">
                            已启用本地模式
                        </h1>
                        <p className="text-slate-600">
                            未配置 Supabase，可在本地模式下无需登录继续使用。
                        </p>
                    </div>

                    <Card>
                        <CardHeader>
                            <CardTitle>本地继续</CardTitle>
                            <CardDescription>
                                创建本地会话，无需 Supabase 即可使用应用。
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <button
                                onClick={() => {
                                    ensureLocalUser()
                                    router.push('/')
                                }}
                                className="w-full px-4 py-2 rounded-md font-medium bg-slate-900 text-white hover:bg-slate-800"
                            >
                                继续使用
                            </button>
                        </CardContent>
                    </Card>
                </div>
            </div>
        )
    }

    const supabase = getSupabase()
    if (!supabase) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
                <div className="w-full max-w-md">
                    <Card>
                        <CardHeader>
                            <CardTitle>Supabase 配置异常</CardTitle>
                            <CardDescription>
                                已检测到 Supabase 环境变量，但客户端初始化失败。
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <button
                                onClick={() => {
                                    ensureLocalUser()
                                    router.push('/')
                                }}
                                className="w-full px-4 py-2 rounded-md font-medium bg-slate-900 text-white hover:bg-slate-800"
                            >
                                切换到本地模式继续
                            </button>
                        </CardContent>
                    </Card>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
            <div className="w-full max-w-md">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="w-12 h-12 bg-black rounded-lg flex items-center justify-center mx-auto mb-4">
                        <Code2 className="w-6 h-6 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 mb-2">
                        欢迎使用 AI 代码自动化
                    </h1>
                    <p className="text-slate-600">
                        登录后即可使用 Claude Code 与 Codex CLI 自动化你的代码
                    </p>
                </div>

                {/* Auth Card */}
                <Card>
                    <CardHeader>
                        <CardTitle>登录</CardTitle>
                        <CardDescription>
                            登录账号以继续
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Auth
                            supabaseClient={supabase}
                            appearance={{
                                theme: ThemeSupa,
                                variables: {
                                    default: {
                                        colors: {
                                            brand: '#0f172a',
                                            brandAccent: '#1e293b',
                                        },
                                    },
                                },
                                className: {
                                    button: 'w-full px-4 py-2 rounded-md font-medium',
                                    input: 'w-full px-3 py-2 border border-slate-300 rounded-md',
                                }
                            }}
                            providers={['github']}
                            redirectTo={typeof window !== 'undefined' ? `${window.location.origin}/` : '/'}
                            onlyThirdPartyProviders={false}
                        />
                    </CardContent>
                </Card>

                {/* Footer */}
                <div className="text-center mt-6 text-sm text-slate-600">
                    <p>
                        登录即表示你同意我们的服务条款与隐私政策。
                    </p>
                </div>
            </div>
        </div>
    )
} 
