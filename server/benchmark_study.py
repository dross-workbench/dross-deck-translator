import asyncio
import json
import time
from pathlib import Path
from dross_server.config import Config
from dross_server.inference import Ollama, ServiceError
from dross_server.study import JapaneseStudy
from dross_server.schemas import AnalysisRequest


async def main():
    results = []
    for model in ('qwen3:1.7b', 'qwen3:4b'):
        client = Ollama(Config(token='synthetic-benchmark-not-a-secret', analysis_model=model))
        study = JapaneseStudy(Path(__file__).parent/'.local/data')
        start = time.perf_counter()
        try:
            result = await study.explain(AnalysisRequest(text='約束を忘れないで。', translation="Don't forget your promise."), client)
        except ServiceError as e:
            result = {'error': e.code}
        record = {'model': model, 'wall_ms': round((time.perf_counter()-start)*1000), 'result': result}
        results.append(record)
        print(json.dumps(record, ensure_ascii=True), flush=True)
        await client.request('POST', '/api/generate', json={'model': model, 'keep_alive': 0})
        await client.client.aclose()
    (Path(__file__).parents[1]/'.local/benchmark-study.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

asyncio.run(main())
