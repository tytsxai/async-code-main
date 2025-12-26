# Supabase 数据库设计

本文档描述 async-code 项目基于 Supabase 的数据库结构。

## 概览

数据库包含三张核心表：
- **`users`**：用户资料，自动与 Supabase Auth 同步（UUID 主键，便于 RLS）
- **`projects`**：用户管理的 GitHub 仓库（BIGSERIAL 主键，性能更好）
- **`tasks`**：AI 自动化任务与执行历史（BIGSERIAL 主键，性能更好）

### 主键策略

- **Users 表**：使用 `UUID`，与 Supabase Auth 一致，简化 RLS（`auth.uid() = user_id`）
- **Projects & Tasks 表**：使用 `BIGSERIAL`，便于高频操作与索引优化

## 表结构

### 1. Users 表（`public.users`）

通过数据库触发器与 `auth.users` 自动同步。

```sql
CREATE TABLE public.users (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  email TEXT,
  full_name TEXT,
  avatar_url TEXT,
  github_username TEXT,
  github_token TEXT, -- 加密的 GitHub token
  preferences JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**特性：**
- ✅ 与 Supabase Auth 自动同步
- ✅ 启用行级安全（RLS）
- ✅ 用户仅能访问自己的数据
- ✅ 安全存储 GitHub Token
- ✅ JSONB 可扩展偏好设置

### 2. Projects 表（`public.projects`）

代表用户管理的 GitHub 仓库。

```sql
CREATE TABLE public.projects (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  
  -- GitHub repository information
  repo_url TEXT NOT NULL,
  repo_name TEXT NOT NULL,
  repo_owner TEXT NOT NULL,
  
  -- Project settings
  name TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT true,
  
  -- Custom settings (extensible)
  settings JSONB DEFAULT '{}',
  
  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Constraints
  UNIQUE(user_id, repo_url)
);
```

**特性：**
- ✅ 每个用户对同一仓库只允许创建一个项目
- ✅ 分支选择是任务级别的（非项目级）
- ✅ JSONB 可扩展配置
- ✅ 完整 RLS 保护
- ✅ 自动更新时间戳

### 3. Tasks 表（`public.tasks`）

保存 AI 自动化任务及完整执行历史。

```sql
CREATE TABLE public.tasks (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  project_id BIGINT REFERENCES public.projects(id) ON DELETE CASCADE,
  
  -- Task information
  status task_status DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
  agent TEXT DEFAULT 'claude', -- AI agent name (flexible string)
  
  -- GitHub/Repository information
  repo_url TEXT,
  target_branch TEXT DEFAULT 'main', -- The branch we're targeting (e.g., 'main')
  pr_branch TEXT, -- The branch we created for the PR (e.g., 'feature/optimize-readme')
  
  -- Container and execution details
  container_id TEXT,
  
  -- Git workflow tracking
  commit_hash TEXT, -- Final commit hash
  pr_number INTEGER, -- Pull request number
  pr_url TEXT, -- Full PR URL
  
  -- Results and patches
  git_diff TEXT,
  git_patch TEXT,
  changed_files JSONB DEFAULT '[]',
  
  -- Error handling
  error TEXT,
  
  -- AI Chat Messages (stored as JSONB array)
  chat_messages JSONB DEFAULT '[]', -- Array of {role, content, timestamp} objects
  
  -- Execution metadata
  execution_metadata JSONB DEFAULT '{}', -- Store execution logs, timing, etc.
  
  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE
);
```

**特性：**
- ✅ 任务执行全链路追踪
- ✅ AI 对话消息存储（无需单独 prompt 字段）
- ✅ Git 工作流追踪（目标分支、PR 分支、PR 号/URL）
- ✅ 补丁与 diff 存储
- ✅ 灵活的元数据存储
- ✅ 完整的状态管理
- ✅ 支持任意 AI 代理名称（TEXT）
- ✅ GitHub Token 位于 users 表（非 task 级）

## 数据库设计原则

保持简洁、聚焦核心功能：
- **必要索引** 提升性能
- **agent 字段为 TEXT**，便于扩展
- **GitHub Token 存储在 user 级别**
- **直接使用 Supabase SDK**，避免自定义函数

## 安全性（RLS）

所有表均启用行级安全策略，确保用户只能访问自己的数据：

- **Users**：可查看和更新自己的资料
- **Projects**：仅能对自己的项目进行 CRUD
- **Tasks**：仅能对自己的任务进行 CRUD

## 索引

仅保留关键索引以优化性能：

```sql
-- Essential indexes only
CREATE INDEX idx_projects_user_id ON public.projects(user_id);
CREATE INDEX idx_tasks_user_id ON public.tasks(user_id);
CREATE INDEX idx_tasks_project_id ON public.tasks(project_id);
CREATE INDEX idx_tasks_status ON public.tasks(status);
```

## 初始化步骤

### 1. 初始化数据库

在 Supabase 控制台的 SQL Editor 执行以下脚本：

```bash
# In Supabase SQL Editor, execute:
psql -f db/init_supabase.sql
```

### 2. 启用认证

确保 Supabase 项目已启用认证：

```javascript
// In your app
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'your-project-url',
  'your-anon-key'
)
```

### 3. 环境变量

设置以下环境变量：

```bash
SUPABASE_URL=your-project-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

## 数据迁移

无需复杂的迁移脚本，业务代码使用 Supabase SDK 进行正常读写即可。

## 示例

### 创建项目

```javascript
const { data, error } = await supabase
  .from('projects')
  .insert({
    repo_url: 'https://github.com/user/repo',
    repo_name: 'repo',
    repo_owner: 'user',
    name: 'My Project',
    description: 'Project description'
  });
```

### 创建任务

```javascript
// Create a task with initial chat message
const { data, error } = await supabase
  .from('tasks')
  .insert({
    project_id: projectId,
    repo_url: 'https://github.com/user/repo',
    target_branch: 'main',
    agent: 'claude',
    chat_messages: [
      {
        role: 'user',
        content: 'Optimize the README file',
        timestamp: Date.now() / 1000
      }
    ]
  });
```

### 查询任务

```javascript
// Get user tasks with filtering
const { data, error } = await supabase
  .from('tasks')
  .select(`
    *,
    projects (
      name,
      repo_name
    )
  `)
  .eq('status', 'completed')
  .order('created_at', { ascending: false })
  .limit(50);

// Get tasks by PR status
const { data: tasksWithPRs } = await supabase
  .from('tasks')
  .select('id, target_branch, pr_branch, pr_number, pr_url, status')
  .not('pr_number', 'is', null)
  .order('pr_number', { ascending: false });
```

### 更新对话消息

```javascript
// Update chat messages array directly
const { data, error } = await supabase
  .from('tasks')
  .update({
    chat_messages: [
      ...existingMessages,
      {
        role: 'assistant',
        content: 'I have optimized your README file with better structure.',
        timestamp: Date.now() / 1000
      }
    ]
  })
  .eq('id', taskId);
```

## 最佳实践

1. **使用 Supabase SDK** 进行所有数据库操作
2. **充分利用 JSONB 字段**（chat_messages、settings）
3. **遵守 RLS**，自动获得安全隔离
4. **GitHub Token 放在 users 表**（不要放在 tasks 表）
5. **保持结构简洁**，必要时再扩展

## 监控指标

建议关注：

- 不同模型的任务完成率
- 任务平均执行时长
- 错误率及常见失败原因
- 用户活跃度与留存
- 数据库性能与查询时间
