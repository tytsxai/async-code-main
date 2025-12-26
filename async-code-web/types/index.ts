import { Tables } from './supabase'

// Supabase 类型
export type Project = Tables<'projects'>
export type Task = Tables<'tasks'>
export type User = Tables<'users'>

// 任务聊天消息类型
export interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
    timestamp: string
}

// 合并视图的文件变更类型
export interface FileChange {
    filename: string
    before: string
    after: string
}

// 前端专用类型
export interface TaskWithProject extends Task {
    project?: Project
    file_changes?: FileChange[]
}

export interface ProjectWithStats extends Project {
    task_count?: number
    completed_tasks?: number
    active_tasks?: number
}

// 旧任务类型（兼容历史数据）
export interface LegacyTask {
    id: string;
    status: string;
    prompt: string;
    repo_url: string;
    branch: string;
    model?: string;
    commit_hash?: string;
    error?: string;
    created_at: number;
}

// API 响应类型
export interface ApiResponse<T = any> {
    status: 'success' | 'error'
    data?: T
    error?: string
    message?: string
}

export interface TaskListResponse {
    status: 'success'
    tasks: Record<string, {
        id: number
        status: string
        created_at: string
        prompt: string
        has_patch: boolean
        project_id?: number
        repo_url: string
        agent: string
    }>
    total_tasks: number
}

export interface ProjectListResponse {
    status: 'success'
    projects: Project[]
}
