"use client";

import { useState, useEffect, useCallback } from "react";
import { SupabaseService } from "@/lib/supabase-service";
import { isSupabaseConfigured } from "@/lib/supabase";
import { getLocalUserProfile } from "../lib/local-auth";
import { User } from "@/types";

export function useUserProfile() {
    const [profile, setProfile] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    const fetchProfile = useCallback(async () => {
        try {
            setIsLoading(true);
            if (!isSupabaseConfigured()) {
                const localProfile = getLocalUserProfile();
                setProfile(
                    localProfile
                        ? {
                              id: localProfile.id,
                              email: localProfile.email ?? null,
                              preferences: localProfile.preferences ?? null,
                              avatar_url: null,
                              created_at: null,
                              full_name: null,
                              github_token: null,
                              github_username: null,
                              updated_at: null,
                          }
                        : null
                );
                setError(null);
                return;
            }
            const data = await SupabaseService.getUserProfile();
            setProfile(data);
            setError(null);
        } catch (err) {
            setError(err as Error);
            console.error("获取用户资料失败：", err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    const refreshProfile = useCallback(async () => {
        await fetchProfile();
    }, [fetchProfile]);

    return {
        profile,
        isLoading,
        error,
        refreshProfile,
    };
}
