"use client";

import React, { useState, useEffect, useRef } from "react";
import { flushSync } from 'react-dom';
import { EditorView, basicSetup } from 'codemirror';
import { unifiedMergeView, updateOriginalDoc } from '@codemirror/merge';
import { Extension } from '@codemirror/state';
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { githubLight } from "@uiw/codemirror-theme-github";
import { Copy, FileText, ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FileChange } from "@/types";

interface DiffViewerProps {
    diff?: string; // Legacy git diff for fallback
    fileChanges?: FileChange[];
    stats?: {
        additions: number;
        deletions: number;
        files: number;
    };
    className?: string;
}

// 根据文件扩展名获取语言标识
const getLanguageExtension = (filename: string): Extension | null => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
        case 'js':
        case 'jsx':
        case 'ts':
        case 'tsx':
            return javascript({ jsx: true });
        case 'py':
            return python();
        default:
            return null;
    }
};

// 单文件的统一合并视图组件
function FileMergeView({ fileChange }: { fileChange: FileChange }) {
    const [isExpanded, setIsExpanded] = useState(true);
    const [mergedContent, setMergedContent] = useState(fileChange.after);
    const containerRef = useRef<HTMLDivElement>(null);
    const viewRef = useRef<EditorView | null>(null);

    const handleCopyFile = () => {
        navigator.clipboard.writeText(mergedContent);
    };

    useEffect(() => {
        if (!containerRef.current || !isExpanded) return;

        // 若存在旧视图则先清理
        if (viewRef.current) {
            viewRef.current.destroy();
            viewRef.current = null;
        }

        // 处理文件新增/删除的情况
        const beforeContent = fileChange.before === 'FILE_NOT_EXISTS' ? '' : fileChange.before;
        const afterContent = fileChange.after === 'FILE_DELETED' ? '' : fileChange.after;

        const languageExtension = getLanguageExtension(fileChange.filename);

        const extensions = [
            basicSetup,
            unifiedMergeView({
                original: beforeContent,
                mergeControls: false, // Show accept/reject buttons
                highlightChanges: false,
                gutter: true
            }),
            githubLight, // Apply GitHub light theme
            EditorView.editable.of(false), // Read-only for viewing
            EditorView.theme({
                '.cm-editor': {
                    fontSize: '13px',
                    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                },
                '.cm-merge-revert': {
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderLeft: '3px solid rgba(239, 68, 68, 0.6)',
                },
                '.cm-merge-accept': {
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    borderLeft: '3px solid rgba(34, 197, 94, 0.6)',
                }
            })
        ];

        // 如可用则添加语言标识
        if (languageExtension) {
            extensions.push(languageExtension);
        }

        // 监听内容变更
        extensions.push(
            EditorView.updateListener.of(update => {
                // 监听文档变更
                if (update.docChanged) {
                    setMergedContent(update.state.doc.toString());
                    return;
                }

                // 监听合并控制操作（接受/撤销）
                for (const tr of update.transactions) {
                    for (const effect of tr.effects) {
                        if (effect.is(updateOriginalDoc)) {
                            flushSync(() => {
                                setMergedContent(effect.value.doc.toString());
                            });
                            return;
                        }
                    }
                }
            })
        );

        viewRef.current = new EditorView({
            parent: containerRef.current,
            doc: afterContent,
            extensions,
        });

        return () => {
            if (viewRef.current) {
                viewRef.current.destroy();
                viewRef.current = null;
            }
        };
    }, [isExpanded, fileChange.filename, fileChange.before, fileChange.after]);

    if (!isExpanded) {
        return (
            <div className="border rounded-lg bg-white shadow-sm">
                <div className="px-6 py-4 pb-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 cursor-pointer" onClick={() => setIsExpanded(true)}>
                            <ChevronRight className="w-4 h-4" />
                            <span className="font-mono text-sm">{fileChange.filename}</span>
                            {fileChange.before === 'FILE_NOT_EXISTS' && (
                                <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">新增</span>
                            )}
                            {fileChange.after === 'FILE_DELETED' && (
                                <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded">删除</span>
                            )}
                        </div>
                        <div className="flex items-center gap-1">
                            <Button variant="ghost" size="sm" onClick={handleCopyFile}>
                                <Copy className="w-3 h-3" />
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="border rounded-lg bg-white shadow-sm">
            <div className="px-6 py-4 pb-1 border-b">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 cursor-pointer" onClick={() => setIsExpanded(false)}>
                        <ChevronDown className="w-4 h-4" />
                        <span className="font-mono text-sm">{fileChange.filename}</span>
                        {fileChange.before === 'FILE_NOT_EXISTS' && (
                            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">新增</span>
                        )}
                        {fileChange.after === 'FILE_DELETED' && (
                            <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded">删除</span>
                        )}
                    </div>
                    <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" onClick={handleCopyFile} title="复制文件内容">
                            <Copy className="w-3 h-3" />
                        </Button>
                    </div>
                </div>
            </div>
            <div className="px-6 pb-6 max-h-[500px] overflow-auto">
                <div className="overflow-hidden">
                    <div 
                        ref={containerRef}
                        className="min-h-[200px]"
                        style={{ width: '100%' }}
                    />
                </div>
            </div>
        </div>
    );
}

// 兼容模式 diff 视图（文件变更数据不可用时）
function LegacyDiffViewer({ diff, stats }: { diff: string; stats?: DiffViewerProps['stats'] }) {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewRef = useRef<EditorView | null>(null);

    const handleCopy = () => {
        navigator.clipboard.writeText(diff);
    };

    useEffect(() => {
        if (!containerRef.current) return;

        // 若存在旧视图则先清理
        if (viewRef.current) {
            viewRef.current.destroy();
            viewRef.current = null;
        }

        const extensions = [
            basicSetup,
            githubLight,
            EditorView.theme({
                '.cm-editor': {
                    fontSize: '13px',
                    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                },
            }),
            EditorView.lineWrapping,
            EditorView.editable.of(false),
        ];

        viewRef.current = new EditorView({
            parent: containerRef.current,
            doc: diff,
            extensions
        });

        return () => {
            if (viewRef.current) {
                viewRef.current.destroy();
                viewRef.current = null;
            }
        };
    }, [diff]);

            return (
            <div className="border rounded-lg overflow-hidden">
                {/* Header */}
                <div className="bg-slate-50 border-b px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <span className="text-slate-700 text-sm font-medium">Git 差异</span>
                        {stats && (
                            <div className="flex items-center gap-4 text-sm">
                                <div className="flex items-center gap-1">
                                    <FileText className="w-3 h-3 text-slate-500" />
                                    <span className="text-slate-600">{stats.files} 个文件</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-green-600 font-mono">+{stats.additions}</span>
                                    <span className="text-red-600 font-mono">-{stats.deletions}</span>
                                </div>
                            </div>
                        )}
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleCopy}
                        className="text-slate-600 hover:text-slate-900 hover:bg-slate-200"
                    >
                        <Copy className="w-3 h-3" />
                    </Button>
                </div>
                
                {/* Diff Content */}
                <div className="max-h-[500px] overflow-auto bg-white">
                    <div 
                        ref={containerRef}
                        style={{ width: '100%', minHeight: '200px' }}
                    />
                </div>
            </div>
        );
}

export function DiffViewer({ diff, fileChanges, stats, className = "" }: DiffViewerProps) {
    const [expandAll, setExpandAll] = useState(false);

    const handleCopyAll = () => {
        if (fileChanges && fileChanges.length > 0) {
            const allChanges = fileChanges.map(fc => 
                `--- ${fc.filename}\n+++ ${fc.filename}\n${fc.before}\n---\n${fc.after}`
            ).join('\n\n');
            navigator.clipboard.writeText(allChanges);
        } else if (diff) {
            navigator.clipboard.writeText(diff);
        }
    };

    const handleExpandAll = () => {
        setExpandAll(!expandAll);
        // 注意：这里需要通过 context 或 props 传递
        // 才能真正控制单个文件的展开/收起状态
    };

    // 若有文件变更数据则使用合并视图，否则回退到旧 diff 视图
    if (fileChanges && fileChanges.length > 0) {
        return (
            <div className={className}>
                {/* Header */}
                <div className="mb-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <h3 className="text-lg font-semibold">文件变更</h3>
                        {stats && (
                            <div className="flex items-center gap-4 text-sm text-slate-600">
                                <div className="flex items-center gap-1">
                                    <FileText className="w-3 h-3" />
                                    <span>{stats.files} 个文件</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-green-600 font-mono">+{stats.additions}</span>
                                    <span className="text-red-600 font-mono">-{stats.deletions}</span>
                                </div>
                            </div>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={handleExpandAll}
                        >
                            {expandAll ? '全部收起' : '全部展开'}
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleCopyAll}>
                            <Copy className="w-3 h-3 mr-1" />
                            复制全部
                        </Button>
                    </div>
                </div>

                {/* File Changes */}
                <div className="space-y-4">
                    {fileChanges.map((fileChange, index) => (
                        <FileMergeView 
                            key={`${fileChange.filename}-${index}`} 
                            fileChange={fileChange}
                        />
                    ))}
                </div>
            </div>
        );
    }

    // 回退到旧 diff 视图
    if (diff) {
        return (
            <div className={className}>
                <LegacyDiffViewer diff={diff} stats={stats} />
            </div>
        );
    }

    // 无可用 diff 数据
    return (
        <div className={`text-center py-8 text-slate-500 ${className}`}>
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>暂无可显示的改动</p>
        </div>
    );
}
