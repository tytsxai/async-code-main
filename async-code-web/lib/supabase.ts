import { createClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'

type SupabaseClient = ReturnType<typeof createClient<Database>>

let supabaseInstance: SupabaseClient | null = null

const PLACEHOLDER_URLS = new Set(['your_supabase_url_here'])
const PLACEHOLDER_KEYS = new Set(['your_supabase_anon_key_here'])

export const isSupabaseConfigured = () => {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
    const disabled = (process.env.NEXT_PUBLIC_SUPABASE_DISABLED || '').toLowerCase()
    if (disabled === 'true' || disabled === '1' || disabled === 'yes') return false
    if (!supabaseUrl || !supabaseAnonKey) return false
    if (PLACEHOLDER_URLS.has(supabaseUrl) || PLACEHOLDER_KEYS.has(supabaseAnonKey)) return false
    return true
}

export const getSupabase = (): SupabaseClient | null => {
    if (!isSupabaseConfigured()) {
        return null
    }
    if (!supabaseInstance) {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
        const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
        
        supabaseInstance = createClient<Database>(supabaseUrl, supabaseAnonKey, {
            auth: {
                autoRefreshToken: true,
                persistSession: true,
                detectSessionInUrl: true
            }
        })
    }
    
    return supabaseInstance
}
