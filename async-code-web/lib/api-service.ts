import { Project, Task, ProjectWithStats, ChatMessage } from '@/types'
import { getSupabase, isSupabaseConfigured } from '@/lib/supabase'

const API_BASE = typeof window !== 'undefined' && window.location.hostname === 'localhost' 
    ? 'http://localhost:5000' 
    : '/api';

async function getAuthHeader(userId?: string): Promise<HeadersInit> {
    if (!isSupabaseConfigured()) {
        return userId ? { 'X-User-ID': userId } : {}
    }

    const supabase = getSupabase()
    if (!supabase) {
        return {}
    }

    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    return token ? { Authorization: `Bearer ${token}` } : {}
}

export class ApiService {
    // 项目相关操作
    static async getProjects(userId: string): Promise<Project[]> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/projects`, {
            headers: authHeader
        })
        
        if (!response.ok) {
            throw new Error('获取项目失败')
        }
        
        const data = await response.json()
        return data.projects || []
    }

    static async createProject(userId: string, projectData: {
        name: string
        description?: string
        repo_url: string
    }): Promise<Project> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/projects`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeader
            },
            body: JSON.stringify(projectData)
        })
        
        if (!response.ok) {
            throw new Error('创建项目失败')
        }
        
        const data = await response.json()
        return data.project
    }

    static async updateProject(userId: string, id: number, updates: Partial<Project>): Promise<Project> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/projects/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...authHeader
            },
            body: JSON.stringify(updates)
        })
        
        if (!response.ok) {
            throw new Error('更新项目失败')
        }
        
        const data = await response.json()
        return data.project
    }

    static async deleteProject(userId: string, id: number): Promise<void> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/projects/${id}`, {
            method: 'DELETE',
            headers: authHeader
        })
        
        if (!response.ok) {
            throw new Error('删除项目失败')
        }
    }

    static async getProject(userId: string, id: number): Promise<Project | null> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/projects/${id}`, {
            headers: authHeader
        })
        
        if (response.status === 404) {
            return null
        }
        
        if (!response.ok) {
            throw new Error('获取项目失败')
        }
        
        const data = await response.json()
        return data.project
    }

    // 任务相关操作
    static async getTasks(userId: string, projectId?: number): Promise<any[]> {
        const url = projectId 
            ? `${API_BASE}/projects/${projectId}/tasks`
            : `${API_BASE}/tasks`

        const authHeader = await getAuthHeader(userId)
        const response = await fetch(url, {
            headers: authHeader
        })
        
        if (!response.ok) {
            throw new Error('获取任务失败')
        }
        
        const data = await response.json()
        return Object.values(data.tasks || {})
    }

    static async getTask(userId: string, id: number): Promise<Task | null> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/tasks/${id}`, {
            headers: authHeader
        })
        
        if (response.status === 404) {
            return null
        }
        
        if (!response.ok) {
            throw new Error('获取任务失败')
        }
        
        const data = await response.json()
        return data.task
    }

    static async startTask(userId: string, taskData: {
        prompt: string
        repo_url: string
        branch?: string
        github_token: string
        model?: string
        project_id?: number
    }): Promise<{ task_id: number }> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/start-task`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeader
            },
            body: JSON.stringify(taskData)
        })
        
        if (!response.ok) {
            throw new Error('启动任务失败')
        }
        
        const data = await response.json()
        return data
    }

    static async getTaskStatus(userId: string, taskId: number): Promise<any> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/task-status/${taskId}`, {
            headers: authHeader
        })
        
        if (!response.ok) {
            throw new Error('获取任务状态失败')
        }
        
        const data = await response.json()
        return data.task
    }

    static async addChatMessage(userId: string, taskId: number, message: {
        role: string
        content: string
    }): Promise<Task> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/tasks/${taskId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeader
            },
            body: JSON.stringify(message)
        })
        
        if (!response.ok) {
            throw new Error('添加消息失败')
        }
        
        const data = await response.json()
        return data.task
    }

    static async createPullRequest(userId: string, taskId: number, prData: {
        title?: string
        body?: string
        github_token: string
    }): Promise<{ pr_url: string; pr_number: number }> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/create-pr/${taskId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeader
            },
            body: JSON.stringify(prData)
        })
        
        if (!response.ok) {
            throw new Error('创建 PR 失败')
        }
        
        const data = await response.json()
        return data
    }

    static async validateGitHubToken(
        userId: string,
        token: string,
        repoUrl?: string
    ): Promise<{
        status: 'success' | 'error'
        user?: string
        repo?: {
            name?: string
            private?: boolean
            permissions?: {
                read?: boolean
                write?: boolean
                create_branches?: boolean
                read_branches?: boolean
                admin?: boolean
            }
            default_branch?: string
        }
        error?: string
        message?: string
    }> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/validate-token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeader,
            },
            body: JSON.stringify({
                github_token: token,
                repo_url: repoUrl
            })
        })

        let data: any = null
        try {
            data = await response.json()
        } catch {
            data = null
        }

        if (response.ok) {
            return data
        }

        return {
            status: 'error',
            user: data?.user,
            repo: data?.repo,
            error: data?.error || 'GitHub 令牌验证失败'
        }
    }

    static async getGitDiff(userId: string, taskId: number): Promise<string> {
        const authHeader = await getAuthHeader(userId)
        const response = await fetch(`${API_BASE}/git-diff/${taskId}`, {
            headers: authHeader
        })
        
        if (!response.ok) {
            throw new Error('获取 git diff 失败')
        }
        
        const data = await response.json()
        return data.git_diff || ''
    }

    // 工具函数
    static parseGitHubUrl(url: string): { owner: string, repo: string } {
        const match = url.match(/github\.com\/([^\/]+)\/([^\/]+?)(?:\.git)?(?:\/|$)/)
        if (!match) throw new Error('GitHub 地址无效')
        return { owner: match[1], repo: match[2] }
    }
}
