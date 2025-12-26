const LOCAL_USER_ID_KEY = 'local-user-id'
const LOCAL_USER_EMAIL_KEY = 'local-user-email'
const LOCAL_USER_PREFERENCES_KEY = 'local-user-preferences'

const isBrowser = typeof window !== 'undefined'

const generateId = () => {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
        return crypto.randomUUID()
    }
    return `local-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export const ensureLocalUser = () => {
    if (!isBrowser) {
        return { id: 'local-user', email: 'local@localhost' }
    }
    let id = localStorage.getItem(LOCAL_USER_ID_KEY)
    if (!id) {
        id = generateId()
        localStorage.setItem(LOCAL_USER_ID_KEY, id)
    }
    let email = localStorage.getItem(LOCAL_USER_EMAIL_KEY)
    if (!email) {
        email = 'local@localhost'
        localStorage.setItem(LOCAL_USER_EMAIL_KEY, email)
    }
    return { id, email }
}

export const clearLocalUser = () => {
    if (!isBrowser) return
    localStorage.removeItem(LOCAL_USER_ID_KEY)
    localStorage.removeItem(LOCAL_USER_EMAIL_KEY)
}

export const getLocalUserProfile = () => {
    if (!isBrowser) return null
    const id = localStorage.getItem(LOCAL_USER_ID_KEY)
    if (!id) return null
    const email = localStorage.getItem(LOCAL_USER_EMAIL_KEY) || 'local@localhost'
    let preferences: any = {}
    const rawPrefs = localStorage.getItem(LOCAL_USER_PREFERENCES_KEY)
    if (rawPrefs) {
        try {
            preferences = JSON.parse(rawPrefs)
        } catch {
            preferences = {}
        }
    }
    return { id, email, preferences }
}

export const setLocalUserPreferences = (preferences: any) => {
    if (!isBrowser) return
    const payload = preferences ?? {}
    localStorage.setItem(LOCAL_USER_PREFERENCES_KEY, JSON.stringify(payload))
}
