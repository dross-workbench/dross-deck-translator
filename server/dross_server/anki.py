import base64
import html
import re
import httpx
from .inference import ServiceError

MODEL = 'Dross Game Immersion'
FIELDS = ['DrossId', 'Word', 'DictionaryForm', 'Reading', 'Meaning', 'Sentence', 'SentenceTranslation', 'Game', 'Screenshot', 'Attribution']


class Anki:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport

    async def invoke(self, action, **params):
        if not self.config.anki_enabled:
            raise ServiceError('anki_disabled', 'Enable AnkiConnect integration on Workbench first.', 409)
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=10, transport=self.transport) as client:
                data = (await client.post('http://127.0.0.1:8765', json={'action': action, 'version': 6, 'params': params})).json()
            if data.get('error'):
                raise ServiceError('anki_error', 'AnkiConnect rejected the operation. Check Anki and its add-on permissions.', 502)
            return data['result']
        except (httpx.HTTPError, ValueError, KeyError):
            raise ServiceError('anki_unavailable', 'Start Anki with AnkiConnect enabled on Workbench localhost.', 503)

    async def sync(self, item, game_subdeck=True):
        deck = 'Japanese::Game Immersion'
        if game_subdeck:
            game = re.sub(r'[^\w .-]', '_', item['game_title'] or item['game_id'])[:80]
            deck += '::' + game
        await self.invoke('createDeck', deck=deck)
        if MODEL not in await self.invoke('modelNames'):
            await self.invoke('createModel', modelName=MODEL, inOrderFields=FIELDS,
                              css='.card { font-family: sans-serif; font-size: 22px; text-align: center; } img { max-width: 100%; }',
                              cardTemplates=[{'Name': 'Japanese to English', 'Front': '{{Word}}<br>{{Sentence}}', 'Back': '{{FrontSide}}<hr id="answer">{{Reading}}<br>{{Meaning}}<br>{{SentenceTranslation}}<br>{{Screenshot}}<br><small>{{Attribution}}</small>'}])
        examples = item['examples']
        escaped = lambda s: html.escape(s).replace('\n', '<br>')
        fields = dict(zip(FIELDS, [item['id'], escaped(item['word']), escaped(item['dictionary_form']), escaped(item['reading']),
                                  escaped(item['meaning']), '<br>'.join(escaped(e['sentence']) for e in examples),
                                  '<br>'.join(escaped(e['translation']) for e in examples), escaped(item['game_title'] or item['game_id']), '',
                                  'JMdict © EDRDG, CC BY-SA 4.0; https://www.edrdg.org/edrdg/licence.html']))
        screenshot = next((e['screenshot'] for e in reversed(examples) if e['screenshot']), None)
        if screenshot:
            path = self.config.data_dir/'screenshots'/screenshot
            filename = 'dross_'+screenshot
            await self.invoke('storeMediaFile', filename=filename, data=base64.b64encode(path.read_bytes()).decode())
            fields['Screenshot'] = f'<img src="{filename}">'
        tag = 'dross_' + item['id']
        notes = await self.invoke('findNotes', query=f'tag:{tag}')
        if notes:
            await self.invoke('updateNoteFields', note={'id': notes[0], 'fields': fields})
            return notes[0]
        return await self.invoke('addNote', note={'deckName': deck, 'modelName': MODEL, 'fields': fields,
                                                'options': {'allowDuplicate': False}, 'tags': ['DrossImmersion', tag]})
