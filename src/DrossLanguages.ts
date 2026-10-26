export const DROSS_LANGUAGE_CODES = ['en', 'ja', 'ko', 'zh-CN', 'zh-TW', 'es', 'fr', 'de', 'pt', 'id'];
const names: Record<string, string> = { en: 'English', ja: 'Japanese', ko: 'Korean', zh: 'Chinese', 'zh-CN': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Traditional)', es: 'Spanish', fr: 'French', de: 'German', pt: 'Portuguese', id: 'Indonesian', und: 'Uncertain' };
export const languageName = (code: string): string => names[code] || code;

export interface DrossCapabilities {
    source_languages?: string[];
    target_languages?: string[];
    translation_model?: string;
    automatic_detection?: boolean;
    status?: string;
}

export function drossLanguageChoices(capabilities?: DrossCapabilities | null) {
    // A connected pre-0.2 gateway only accepts Japanese -> English.
    if (capabilities?.status === 'ok') return {
        source: capabilities.source_languages || ['ja'],
        target: capabilities.target_languages || ['en'],
    };
    return { source: ['auto', ...DROSS_LANGUAGE_CODES], target: DROSS_LANGUAGE_CODES };
}
