const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function loadModule(path, requireFn) {
    const context = {exports: {}, require: requireFn};
    vm.runInNewContext(ts.transpileModule(fs.readFileSync(path, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText, context);
    return context.exports;
}

test('Dross language controls advertise Portuguese and Indonesian and respect legacy gateways', () => {
    const {drossLanguageChoices, languageName} = loadModule('src/DrossLanguages.ts');
    const offline = drossLanguageChoices();
    assert(offline.source.includes('auto') && offline.source.includes('id') && offline.target.includes('pt'));
    assert.equal(languageName('id'), 'Indonesian'); assert.equal(languageName('pt'), 'Portuguese');
    const legacy = drossLanguageChoices({status: 'ok'});
    assert.deepEqual(Array.from(legacy.source), ['ja']); assert.deepEqual(Array.from(legacy.target), ['en']);
    const advertised = drossLanguageChoices({status: 'ok', source_languages: ['auto', 'id'], target_languages: ['pt']});
    assert.deepEqual(Array.from(advertised.source), ['auto', 'id']);
    assert.deepEqual(Array.from(advertised.target), ['pt']);
});

test('changing language stops immersion before an unchanged frame can reuse an old translation', () => {
    // Arrow methods are initialized by the constructor; use lightweight collaborators.
    const calls = [];
    class Input { onShortcutPressed() {} onProgress() {} setEnabled() {} }
    class TextTranslator {
        constructor() { this.source = 'ja'; this.target = 'en'; }
        getInputLanguage() { return this.source; } getTargetLanguage() { return this.target; }
        setInputLanguage(v) { calls.push(['source', v]); this.source = v; }
        setTargetLanguage(v) { calls.push(['target', v]); this.target = v; }
    }
    const mod = loadModule('src/Translator.tsx', name => {
        if (name === '@decky/api') return {call: async () => true};
        if (name === './Input') return {Input};
        if (name === './TextTranslator') return {TextTranslator};
        if (name === './TextRecognizer') return {TextRecognizer: class {}};
        if (name === './ImmersionLoop') return {ImmersionLoop: class { active = true; }};
        if (name === './Logger') return {logger: new Proxy({}, {get: () => () => {}})};
        return {};
    });
    const instance = new mod.GameTranslatorLogic({onStateChanged() {}});
    instance.stopImmersion = () => calls.push(['stop']);
    instance.setTargetLanguage('pt'); instance.setInputLanguage('id'); instance.setInputLanguage('id');
    assert.deepEqual(calls, [['stop'], ['target', 'pt'], ['stop'], ['source', 'id'], ['source', 'id']]);
});

function scheduler() {
    const tasks = new Map(); let next = 0;
    const context = { exports: {}, setTimeout: (fn, ms) => { const id = ++next; tasks.set(id, {fn, ms}); return id; }, clearTimeout: id => tasks.delete(id) };
    const output = ts.transpileModule(fs.readFileSync('src/ImmersionLoop.ts', 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText;
    vm.runInNewContext(output, context);
    return { loop: new context.exports.ImmersionLoop(), tasks, async tick() {
        const [id, task] = tasks.entries().next().value; tasks.delete(id); task.fn();
        await Promise.resolve(); await Promise.resolve();
    }};
}

test('immersion never overlaps work and stop cancels pending work', async () => {
    const s = scheduler(); let calls = 0, finish;
    s.loop.start(15000, () => { calls++; return new Promise(resolve => finish = resolve); });
    assert.equal(s.tasks.size, 1);
    await s.tick();
    assert.equal(calls, 1); assert.equal(s.tasks.size, 0);
    s.loop.stop(); finish(); await Promise.resolve(); await Promise.resolve();
    assert.equal(s.tasks.size, 0); assert.equal(s.loop.active, false);
});

test('immersion applies battery-conscious floor and stops on error', async () => {
    const s = scheduler();
    s.loop.start(1, async () => {}); await s.tick();
    assert.equal([...s.tasks.values()][0].ms, 5000);
    s.loop.stop(); assert.equal(s.tasks.size, 0);
    s.loop.start(15000, async () => { throw Error('offline'); }); await s.tick();
    assert.equal(s.loop.active, false); assert.equal(s.tasks.size, 0);
});

test('restart ignores the completion of an earlier capture', async () => {
    const s = scheduler(); let finish;
    s.loop.start(5000, () => new Promise(resolve => finish = resolve)); await s.tick();
    s.loop.start(20000, async () => {});
    finish(); await Promise.resolve(); await Promise.resolve();
    assert.equal(s.tasks.size, 1);
    await s.tick(); assert.equal([...s.tasks.values()][0].ms, 20000);
});

test('existing OCR fixture pipeline preserves Japanese dialogue and rectangles', async () => {
    const samples = JSON.parse(fs.readFileSync('tests/fixtures/dialogue.json', 'utf8'));
    let fixture;
    const logger = new Proxy({}, { get: () => () => {} });
    const context = { exports: {}, require: name => name === '@decky/api' ? {call: async () => fixture} : {logger} };
    const output = ts.transpileModule(fs.readFileSync('src/TextRecognizer.tsx', 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText;
    vm.runInNewContext(output, context);
    const recognizer = new context.exports.TextRecognizer();
    for (const sample of samples) {
        fixture = [{text: sample.text, rect: sample.rect, confidence: 0.95, isDialog: true}];
        const result = await recognizer.recognizeTextFile('synthetic-fixture.png');
        assert.equal(result[0].text, sample.text);
        assert.deepEqual(result[0].rect, sample.rect);
    }
    fixture = [{text: 'bad OCR', rect: samples[0].rect, confidence: 0.1, isDialog: true}];
    assert.equal((await recognizer.recognizeTextFile('synthetic-low-confidence.png')).length, 0);
});
