export type Lang = 'pl' | 'en' | 'de'

export const LANGUAGES: { code: Lang; flag: string; label: string }[] = [
  { code: 'pl', flag: '🇵🇱', label: 'Polski' },
  { code: 'en', flag: '🇬🇧', label: 'English' },
  { code: 'de', flag: '🇩🇪', label: 'Deutsch' },
]

export const T = {
  pl: {
    dashboard: 'Dashboard',
    profiles: 'Profile',
    myProfile: 'Mój profil',
    users: 'Użytkownicy',
    conversations: 'Rozmowy',
    logout: 'Wyloguj się',
    loading: 'Ładowanie...',
    // Dashboard page
    dashboardTitle: 'Dashboard',
    chatbotProfiles: 'Profile chatbotów',
    newProfile: '+ Nowy profil',
    noProfiles: 'Brak profili.',
    createFirstProfile: 'Utwórz pierwszy profil.',
    noProfileAssigned: 'Nie masz przypisanego profilu. Skontaktuj się z superadminem.',
    manageUsers: 'Zarządzaj →',
    active: 'Aktywny',
    inactive: 'Nieaktywny',
    edit: 'Edytuj',
    statProfiles: 'Profile',
    statUsers: 'Użytkownicy',
    statActive: 'Aktywne',
    statBlocked: 'Zablokowane',
  },
  en: {
    dashboard: 'Dashboard',
    profiles: 'Profiles',
    myProfile: 'My Profile',
    users: 'Users',
    conversations: 'Conversations',
    logout: 'Log out',
    loading: 'Loading...',
    dashboardTitle: 'Dashboard',
    chatbotProfiles: 'Chatbot Profiles',
    newProfile: '+ New Profile',
    noProfiles: 'No profiles found.',
    createFirstProfile: 'Create your first profile.',
    noProfileAssigned: 'No profile assigned. Contact your superadmin.',
    manageUsers: 'Manage →',
    active: 'Active',
    inactive: 'Inactive',
    edit: 'Edit',
    statProfiles: 'Profiles',
    statUsers: 'Users',
    statActive: 'Active',
    statBlocked: 'Blocked',
  },
  de: {
    dashboard: 'Dashboard',
    profiles: 'Profile',
    myProfile: 'Mein Profil',
    users: 'Benutzer',
    conversations: 'Gespräche',
    logout: 'Abmelden',
    loading: 'Laden...',
    dashboardTitle: 'Dashboard',
    chatbotProfiles: 'Chatbot-Profile',
    newProfile: '+ Neues Profil',
    noProfiles: 'Keine Profile vorhanden.',
    createFirstProfile: 'Erstes Profil erstellen.',
    noProfileAssigned: 'Kein Profil zugewiesen. Superadmin kontaktieren.',
    manageUsers: 'Verwalten →',
    active: 'Aktiv',
    inactive: 'Inaktiv',
    edit: 'Bearbeiten',
    statProfiles: 'Profile',
    statUsers: 'Benutzer',
    statActive: 'Aktiv',
    statBlocked: 'Gesperrt',
  },
} satisfies Record<Lang, Record<string, string>>

export function getLang(): Lang {
  if (typeof window === 'undefined') return 'pl'
  return (localStorage.getItem('mentorix_lang') as Lang) || 'pl'
}

export function setLang(lang: Lang): void {
  localStorage.setItem('mentorix_lang', lang)
}
