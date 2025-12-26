import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

// 为 git diff 提供基础语法高亮
export function formatDiff(diff: string): string {
    if (!diff) return '';
    
    return diff.split('\n').map(line => {
        if (line.startsWith('+++') || line.startsWith('---')) {
            return line; // 文件头
        } else if (line.startsWith('@@')) {
            return line; // 区块头
        } else if (line.startsWith('+') && !line.startsWith('+++')) {
            return line; // 新增行
        } else if (line.startsWith('-') && !line.startsWith('---')) {
            return line; // 删除行
        }
        return line; // 上下文行
    }).join('\n');
}

// 解析 git diff 并统计变更
export function parseDiffStats(diff: string): { additions: number; deletions: number; files: number } {
    if (!diff) return { additions: 0, deletions: 0, files: 0 };
    
    const lines = diff.split('\n');
    let additions = 0;
    let deletions = 0;
    const files = new Set<string>();
    
    for (const line of lines) {
        if (line.startsWith('+++') || line.startsWith('---')) {
            const filePath = line.substring(4);
            if (filePath !== '/dev/null') {
                // 移除 git diff 中的 a/ 或 b/ 前缀
                const normalizedPath = filePath.replace(/^[ab]\//, '');
                files.add(normalizedPath);
            }
        } else if (line.startsWith('+') && !line.startsWith('+++')) {
            additions++;
        } else if (line.startsWith('-') && !line.startsWith('---')) {
            deletions++;
        }
    }
    
    return { additions, deletions, files: files.size };
}
