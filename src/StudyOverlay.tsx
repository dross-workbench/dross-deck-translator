import { useEffect, useRef, useState, VFC } from 'react';
import { call } from '@decky/api';
import { ModalRoot, DialogButton, Dropdown, Focusable, showModal, ToggleField } from '@decky/ui';
import { TranslatedRegion } from './TextTranslator';

interface Token {
    id: number; surface: string; dictionary_form: string; reading: string;
    part_of_speech: string[]; particle_note?: string;
    dictionary_entries: { reading: string; senses: { definitions: string[]; part_of_speech: string[] }[] }[];
}
interface Analysis {
    tokens: Token[]; dictionary_available: boolean; grammar?: { explanation: string; source: string };
    error?: boolean; message?: string;
}
interface Snapshot { regions: TranslatedRegion[]; context: string[]; game_id: string; image?: string; }

const StudyOverlay: VFC<{ snapshot: Snapshot; closeModal?: () => void }> = ({ snapshot, closeModal }) => {
    const [sentence, setSentence] = useState(0);
    const [word, setWord] = useState(0);
    const [analysis, setAnalysis] = useState<Analysis | null>(null);
    const [message, setMessage] = useState('');
    const [busy, setBusy] = useState(false);
    const [showGrammar, setShowGrammar] = useState(false);
    const [includeImage, setIncludeImage] = useState(false);
    const saveEvents = useRef(new Map<string, string>());
    const requestId = useRef(0);
    const region = snapshot.regions[sentence];
    const analyze = async (explain: boolean) => {
        const id = ++requestId.current;
        setBusy(true); setMessage(explain ? 'Preparing local grammar explanation…' : 'Looking up local dictionary…');
        try {
            const result = await call<[any], Analysis>('analyze_dross_sentence', { text: region.text, translation: region.englishTranslation || region.translatedText, context: snapshot.context, explain });
            if (id !== requestId.current) return;
            if (result.error) { setMessage(result.message || 'Study request failed'); return; }
            setAnalysis(result); setMessage(result.dictionary_available ? '' : 'JMdict is not installed. Run Install-Study.ps1 on Workbench.');
            if (explain) setShowGrammar(true);
        } catch { if (id === requestId.current) setMessage('Workbench study service is unavailable'); }
        finally { if (id === requestId.current) setBusy(false); }
    };
    useEffect(() => { setWord(0); setAnalysis(null); setShowGrammar(false); analyze(false); return () => { requestId.current++; }; }, [sentence]);
    const token = analysis?.tokens[word];
    const entries = token?.dictionary_entries || [];
    const meaning = entries[0]?.senses.slice(0, 3).map(s => s.definitions.join('; ')).join(' / ') || 'No local dictionary definition found';
    const save = async (syncAnki = false) => {
        if (!token) return;
        setBusy(true);
        try {
            const selection = `${sentence}:${word}`;
            if (!saveEvents.current.has(selection)) saveEvents.current.set(selection, crypto.randomUUID());
            const result = await call<[any], any>('save_dross_word', {
                event_id: saveEvents.current.get(selection), word: token.surface, dictionary_form: token.dictionary_form,
                reading: entries[0]?.reading || token.reading, meaning,
                sentence: region.text, sentence_translation: region.englishTranslation || region.translatedText,
                game_id: snapshot.game_id,
                sync_anki: syncAnki,
                ...(includeImage && snapshot.image ? { screenshot_base64: snapshot.image.replace(/^data:image\/\w+;base64,/, '') } : {}),
            });
            setMessage(result.error ? result.message : `Saved · ${result.encounters} encounter(s)${result.anki_error ? ' · '+result.anki_error : result.anki_id ? ' · Synced to Anki' : ''}`);
        } catch { setMessage('Save failed. Check Workbench.'); }
        finally { setBusy(false); }
    };
    return <ModalRoot onCancel={closeModal} onEscKeypress={closeModal}>
        <div style={{ padding: 20, width: 680, maxHeight: '78vh', overflowY: 'auto' }}>
            <h2>Japanese Study</h2>
            <div style={{ fontSize: 13, opacity: 0.7 }}>Game: {snapshot.game_id} · D-pad selects · A activates · B returns</div>
            <Dropdown selectedOption={sentence} rgOptions={snapshot.regions.map((r, i) => ({ label: r.text, data: i }))} onChange={o => setSentence(o.data)} />
            <p style={{ fontSize: 23, lineHeight: 2.2 }}>{analysis?.tokens.map(t => <ruby key={t.id} style={{ marginRight: 3 }}>{t.surface}<rt style={{ fontSize: 12 }}>{t.reading !== t.surface ? t.reading : ''}</rt></ruby>) || region.text}</p>
            <p>{region.englishTranslation || region.translatedText}</p>
            {analysis && <Dropdown selectedOption={word} rgOptions={analysis.tokens.map((t, i) => ({ label: `${t.surface} · ${t.reading}`, data: i }))} onChange={o => setWord(o.data)} />}
            {token && <div style={{ margin: '12px 0', lineHeight: 1.5 }}>
                <strong>{token.dictionary_form}</strong> · {entries[0]?.reading || token.reading} · {token.part_of_speech.join(' / ')}
                <p>{meaning}</p>
                {token.particle_note && <p>{token.particle_note}</p>}
                <small>JMdict definitions are possible senses, not a guaranteed match for this context.</small>
            </div>}
            {snapshot.image && <ToggleField label="Include screenshot in this save" checked={includeImage} onChange={setIncludeImage} />}
            <Focusable style={{ display: 'flex', gap: 8 }}>
                <DialogButton disabled={busy || !token} onClick={() => save()}>Save vocabulary</DialogButton>
                <DialogButton disabled={busy || !token} onClick={() => save(true)}>Save + Anki</DialogButton>
                <DialogButton disabled={busy} onClick={() => analysis?.grammar ? setShowGrammar(!showGrammar) : analyze(true)}>{showGrammar ? 'Hide grammar' : 'Explain grammar'}</DialogButton>
                <DialogButton onClick={closeModal}>Resume game</DialogButton>
            </Focusable>
            {message && <p role="status">{message}</p>}
            {showGrammar && <div><p>{analysis?.grammar?.explanation}</p><small>{analysis?.grammar?.source}</small></div>}
            <p style={{ fontSize: 11, opacity: 0.6 }}>Readings: Sudachi. Definitions: JMdict © EDRDG, CC BY-SA 4.0. edrdg.org/edrdg/licence.html</p>
        </div>
    </ModalRoot>;
};

export async function openStudy(onDismissOverlay: () => void, image?: string) {
    const snapshot = await call<[], Snapshot>('get_dross_study_snapshot');
    if (!snapshot.regions.length) return false;
    snapshot.image = image;
    onDismissOverlay();
    showModal(<StudyOverlay snapshot={snapshot} />);
    return true;
}
