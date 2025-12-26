"use client";

import React, { useState, useEffect } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { javascript } from "@codemirror/lang-javascript";
import { githubLight } from "@uiw/codemirror-theme-github";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Save, Key, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { SupabaseService } from "@/lib/supabase-service";
import { isSupabaseConfigured } from "@/lib/supabase";
import { setLocalUserPreferences } from "../lib/local-auth";
import { useUserProfile } from "@/hooks/useUserProfile";

interface CodeAgentConfig {
    claudeCode?: {
        env?: Record<string, string>;
        credentials?: Record<string, any> | null;
    };
    codex?: {
        env?: Record<string, string>;
    };
}

const DEFAULT_CLAUDE_ENV = {
    ANTHROPIC_API_KEY: "",
    // 如需可在此添加其它 Claude 专用环境变量
};

const DEFAULT_CLAUDE_CREDENTIALS = {
    // 示例结构 - 用户可自行扩展
};

const DEFAULT_CODEX_ENV = {
    OPENAI_API_KEY: "",
    DISABLE_SANDBOX: "yes",
    CONTINUE_ON_BROWSER: "no",
    // 如需可在此添加其它 Codex 专用环境变量
};

// 判断凭据是否有效的辅助函数（非空/null/undefined）
const hasMeaningfulCredentials = (creds: any): boolean => {
    if (!creds || creds === null || creds === undefined || creds === '') {
        return false;
    }
    if (typeof creds === 'object' && Object.keys(creds).length === 0) {
        return false;
    }
    return true;
};

export function CodeAgentSettings() {
    const { profile, refreshProfile } = useUserProfile();
    const [claudeEnv, setClaudeEnv] = useState("");
    const [claudeCredentials, setClaudeCredentials] = useState("");
    const [codexEnv, setCodexEnv] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [errors, setErrors] = useState<{ 
        claudeEnv?: string; 
        claudeCredentials?: string; 
        codexEnv?: string; 
    }>({});

    // 初始化时从资料中加载设置
    useEffect(() => {
        if (profile?.preferences) {
            const prefs = profile.preferences as any; // Use any for backward compatibility
            
            // 处理 Claude 配置的向后兼容
            let claudeConfig: any = {};
            if (prefs.claudeCode) {
                // 检查是否为新结构（包含 env/credentials）
                if (prefs.claudeCode.env || prefs.claudeCode.credentials) {
                    claudeConfig = prefs.claudeCode;
                } else {
                    // 旧结构 - 迁移到新格式
                    const { credentials, ...envVars } = prefs.claudeCode;
                    
                    claudeConfig = {
                        env: envVars,
                        credentials: hasMeaningfulCredentials(credentials) ? credentials : null
                    };
                }
            }
            
            // 处理 Codex 配置的向后兼容
            let codexConfig: any = {};
            if (prefs.codex) {
                // 检查是否为新结构
                if (prefs.codex.env) {
                    codexConfig = prefs.codex;
                } else {
                    // Codex 的新结构
                    codexConfig = { env: prefs.codex };
                }
            } else if (prefs.codexCLI) {
                // 旧 codexCLI key - 迁移到新 codex key
                codexConfig = { env: prefs.codexCLI };
            }
            
            setClaudeEnv(JSON.stringify(claudeConfig.env || DEFAULT_CLAUDE_ENV, null, 2));
            setClaudeCredentials(JSON.stringify(claudeConfig.credentials || DEFAULT_CLAUDE_CREDENTIALS, null, 2));
            setCodexEnv(JSON.stringify(codexConfig.env || DEFAULT_CODEX_ENV, null, 2));
        } else {
            setClaudeEnv(JSON.stringify(DEFAULT_CLAUDE_ENV, null, 2));
            setClaudeCredentials(JSON.stringify(DEFAULT_CLAUDE_CREDENTIALS, null, 2));
            setCodexEnv(JSON.stringify(DEFAULT_CODEX_ENV, null, 2));
        }
    }, [profile]);

    const validateJSON = (value: string, key: string) => {
        try {
            JSON.parse(value);
            setErrors(prev => ({ ...prev, [key]: undefined }));
            return true;
        } catch (e) {
            setErrors(prev => ({ ...prev, [key]: "JSON 格式无效" }));
            return false;
        }
    };

    const handleSave = async () => {
        // 校验所有 JSON
        const isClaudeEnvValid = validateJSON(claudeEnv, "claudeEnv");
        const isClaudeCredentialsValid = validateJSON(claudeCredentials, "claudeCredentials");
        const isCodexEnvValid = validateJSON(codexEnv, "codexEnv");

        if (!isClaudeEnvValid || !isClaudeCredentialsValid || !isCodexEnvValid) {
            toast.error("请先修复 JSON 格式错误");
            return;
        }

        setIsLoading(true);
        try {
            const claudeEnvConfig = JSON.parse(claudeEnv);
            const claudeCredentialsConfig = JSON.parse(claudeCredentials);
            const codexEnvConfig = JSON.parse(codexEnv);

            const preferences: CodeAgentConfig = {
                claudeCode: {
                    env: claudeEnvConfig,
                    credentials: hasMeaningfulCredentials(claudeCredentialsConfig) ? claudeCredentialsConfig : null,
                },
                codex: {
                    env: codexEnvConfig,
                },
            };

            // 与现有偏好合并
            const existingPrefs = (profile?.preferences || {}) as Record<string, any>;
            
            // 迁移时清理旧键
            const { codexCLI, ...cleanedPrefs } = existingPrefs;
            
            const mergedPrefs = {
                ...cleanedPrefs,
                ...preferences,
            };

            if (!isSupabaseConfigured()) {
                setLocalUserPreferences(mergedPrefs);
                await refreshProfile();
                toast.success("设置已保存到本地（Supabase 已禁用）。");
                return;
            }

            await SupabaseService.updateUserProfile({ preferences: mergedPrefs });
            await refreshProfile();
            
            // 提示凭据处理情况
            const credentialsMessage = hasMeaningfulCredentials(claudeCredentialsConfig) 
                ? "Claude 凭据将会配置" 
                : "Claude 凭据为空，将被跳过";
            
            toast.success(`代码代理设置保存成功。${credentialsMessage}`);
        } catch (error) {
            console.error("保存设置失败：", error);
            toast.error("保存设置失败");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>代码代理设置</CardTitle>
                    <CardDescription>
                        为各个代码代理配置环境变量与凭据，这些设置会在创建容器时使用。
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                    <Alert>
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            <strong>重要提示：</strong> 环境变量与凭据将分别保存。请将敏感 API Key 存放在环境变量中，认证配置存放在凭据中。
                        </AlertDescription>
                    </Alert>

                    {/* Claude Code Settings */}
                    <div className="space-y-6">
                        <div className="flex items-center gap-2 pb-2 border-b">
                            <Settings2 className="w-5 h-5 text-blue-600" />
                            <h3 className="text-lg font-semibold">Claude Code 配置</h3>
                        </div>
                        
                        {/* Claude Environment Variables */}
                        <div className="space-y-2">
                            <Label htmlFor="claude-env" className="flex items-center gap-2">
                                <Settings2 className="w-4 h-4" />
                                环境变量
                            </Label>
                            <div className="border rounded-lg overflow-hidden">
                                <CodeMirror
                                    id="claude-env"
                                    value={claudeEnv}
                                    height="200px"
                                    extensions={[javascript({ jsx: false })]}
                                    theme={githubLight}
                                    onChange={(value) => {
                                        setClaudeEnv(value);
                                        validateJSON(value, "claudeEnv");
                                    }}
                                    placeholder={JSON.stringify(DEFAULT_CLAUDE_ENV, null, 2)}
                                />
                            </div>
                            {errors.claudeEnv && (
                                <p className="text-sm text-red-500 mt-1">{errors.claudeEnv}</p>
                            )}
                            <p className="text-sm text-muted-foreground">
                                配置 Claude Code CLI（@anthropic-ai/claude-code）的环境变量
                            </p>
                        </div>

                        {/* Claude Credentials */}
                        <div className="space-y-2">
                            <Label htmlFor="claude-credentials" className="flex items-center gap-2">
                                <Key className="w-4 h-4" />
                                凭据（可选）
                            </Label>
                            <div className="border rounded-lg overflow-hidden">
                                <CodeMirror
                                    id="claude-credentials"
                                    value={claudeCredentials}
                                    height="150px"
                                    extensions={[javascript({ jsx: false })]}
                                    theme={githubLight}
                                    onChange={(value) => {
                                        setClaudeCredentials(value);
                                        validateJSON(value, "claudeCredentials");
                                    }}
                                    placeholder={JSON.stringify(DEFAULT_CLAUDE_CREDENTIALS, null, 2)}
                                />
                            </div>
                            {errors.claudeCredentials && (
                                <p className="text-sm text-red-500 mt-1">{errors.claudeCredentials}</p>
                            )}
                            <p className="text-sm text-muted-foreground">
                                配置 Claude Code CLI 的认证凭据（将保存到 ~/.claude/.credentials.json）
                            </p>
                        </div>
                    </div>

                    {/* Codex CLI Settings */}
                    <div className="space-y-6">
                        <div className="flex items-center gap-2 pb-2 border-b">
                            <Settings2 className="w-5 h-5 text-green-600" />
                            <h3 className="text-lg font-semibold">Codex CLI 配置</h3>
                        </div>
                        
                        {/* Codex Environment Variables */}
                        <div className="space-y-2">
                            <Label htmlFor="codex-env" className="flex items-center gap-2">
                                <Settings2 className="w-4 h-4" />
                                环境变量
                            </Label>
                            <div className="border rounded-lg overflow-hidden">
                                <CodeMirror
                                    id="codex-env"
                                    value={codexEnv}
                                    height="200px"
                                    extensions={[javascript({ jsx: false })]}
                                    theme={githubLight}
                                    onChange={(value) => {
                                        setCodexEnv(value);
                                        validateJSON(value, "codexEnv");
                                    }}
                                    placeholder={JSON.stringify(DEFAULT_CODEX_ENV, null, 2)}
                                />
                            </div>
                            {errors.codexEnv && (
                                <p className="text-sm text-red-500 mt-1">{errors.codexEnv}</p>
                            )}
                            <p className="text-sm text-muted-foreground">
                                配置 Codex CLI（@openai/codex）的环境变量
                            </p>
                        </div>
                        
                        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                            <p className="text-sm text-yellow-800">
                                <strong>注意：</strong> Codex CLI 不需要单独的凭据配置，所有设置均通过环境变量完成。
                            </p>
                        </div>
                    </div>

                    <Button
                        onClick={handleSave}
                        disabled={isLoading || !!errors.claudeEnv || !!errors.claudeCredentials || !!errors.codexEnv}
                        className="w-full"
                    >
                        <Save className="w-4 h-4 mr-2" />
                        {isLoading ? "保存中..." : "保存设置"}
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
}
