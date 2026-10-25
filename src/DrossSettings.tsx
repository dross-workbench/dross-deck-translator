import { useEffect, useState, VFC } from 'react';
import { call } from '@decky/api';
import { PanelSection, PanelSectionRow, TextField, ButtonItem, ToggleField, Dropdown, Field, SliderField } from '@decky/ui';
import { openStudy } from './StudyOverlay';
import { GameTranslatorLogic } from './Translator';

export const DrossSettings: VFC<{ logic: GameTranslatorLogic }> = ({ logic }) => {
    const [settings, setSettings] = useState<Record<string, any>>({});
    const [token, setToken] = useState('');
    const [status, setStatus] = useState('Not tested');
    useEffect(() => { call<[], Record<string, any>>('get_dross_settings').then(setSettings).catch(() => setStatus('Unable to load settings')); }, []);
    const save = async (key: string, value: any) => {
        const ok = await call<[string, any], boolean>('set_setting', key, value);
        if (!ok) throw new Error('Could not save setting');
        setSettings(s => ({ ...s, [key]: value }));
    };
    const connect = async () => {
        setStatus('Connecting…');
        try {
            for (const key of ['dross_server_url', 'dross_certificate_sha256']) await save(key, settings[key] || '');
            if (token) { await save('dross_token', token.trim()); setToken(''); }
            const result = await call<[], any>('test_dross_connection');
            setStatus(result.status === 'ok'
                ? `Connected · Translation: ${result.translation_model} · Analysis: ${result.analysis_model}${result.analysis_available ? '' : ' (not installed)'}${result.context_supported ? '' : ' · This model does not use dialogue history'}`
                : result.message || 'Model is not ready. Check Workbench.');
        } catch { setStatus('Connection failed. Check Workbench settings.'); }
    };
    const toggle = (key: string, label: string, description: string) => <PanelSectionRow><ToggleField label={label} description={description} checked={!!settings[key]} onChange={v => { save(key, v).catch(() => setStatus('Save failed')); }} /></PanelSectionRow>;
    return <>
        <PanelSection title="Dross Local AI">
            <PanelSectionRow><Field label="Mode"><Dropdown selectedOption={settings.dross_mode || 'translate'} rgOptions={[{ label: 'Translate', data: 'translate' }, { label: 'Study', data: 'study' }]} onChange={o => { save('dross_mode', o.data).catch(() => setStatus('Save failed')); }} /></Field></PanelSectionRow>
            <PanelSectionRow><ButtonItem onClick={async () => { if (!await openStudy(logic.dismiss)) setStatus('Translate a screen first, then open Study.'); }}>Study last screen</ButtonItem></PanelSectionRow>
            <PanelSectionRow><TextField label="Workbench gateway" value={settings.dross_server_url || ''} onChange={e => setSettings(s => ({ ...s, dross_server_url: e.target.value }))} /></PanelSectionRow>
            <PanelSectionRow><TextField label="Pairing token" bIsPassword value={token} onChange={e => setToken(e.target.value)} /></PanelSectionRow>
            <PanelSectionRow><TextField label="Certificate SHA-256" value={settings.dross_certificate_sha256 || ''} onChange={e => setSettings(s => ({ ...s, dross_certificate_sha256: e.target.value }))} /></PanelSectionRow>
            <PanelSectionRow><ButtonItem onClick={connect}>Save & Test Connection</ButtonItem></PanelSectionRow>
            <PanelSectionRow><Field label="Connection" description={status} /></PanelSectionRow>
            <PanelSectionRow><Field label="Display"><Dropdown selectedOption={settings.dross_display_mode || 'english'} rgOptions={[{ label: 'English', data: 'english' }, { label: 'Japanese', data: 'japanese' }, { label: 'Bilingual', data: 'bilingual' }]} onChange={o => { save('dross_display_mode', o.data).catch(() => setStatus('Save failed')); }} /></Field></PanelSectionRow>
            <PanelSectionRow><SliderField label="Timeout (seconds)" value={settings.dross_timeout ?? 120} min={10} max={300} step={10} showValue onChange={v => { save('dross_timeout', v).catch(() => setStatus('Save failed')); }} /></PanelSectionRow>
            <PanelSectionRow><SliderField label="Previous dialogue lines" value={settings.dross_context_lines ?? 3} min={0} max={6} step={1} showValue onChange={v => { save('dross_context_lines', v).catch(() => setStatus('Save failed')); }} /></PanelSectionRow>
            {toggle('dross_offline_fallback', 'On-device fallback', 'Use NLLB only if Workbench is unavailable. Download NLLB in Translation first.')}
            {toggle('dross_local_only', 'Local providers only', 'Block cloud OCR and translation. Keep enabled for zero commercial AI usage.')}
            {toggle('dross_save_text', 'Save translation cache', 'Off keeps Dross translations in memory. Turning off deletes the disk cache.')}
            {toggle('dross_allow_screenshots', 'Allow saved screenshots', 'Explicit vocabulary saves only. Normal translation always sends text.')}
            {toggle('dross_allow_http', 'Allow unencrypted LAN HTTP', 'Token and dialogue can be read on this network. HTTPS is preferred.')}
            <PanelSectionRow><ButtonItem onClick={async () => { await call('clear_dross_session'); setStatus('Session context and memory cache cleared'); }}>Clear session context</ButtonItem></PanelSectionRow>
            <PanelSectionRow><ButtonItem onClick={async () => { await call('clear_translation_cache'); await call('clear_dross_session'); setStatus('Translation caches cleared'); }}>Delete translation cache</ButtonItem></PanelSectionRow>
        </PanelSection>
    </>;
};
