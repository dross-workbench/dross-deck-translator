const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

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
