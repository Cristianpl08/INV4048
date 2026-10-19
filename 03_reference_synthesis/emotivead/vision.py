"""Local Ollama vision inference. No paid service or API key."""
import base64
import json
import os
import urllib.request
import urllib.error
from emotivead.contracts import EMOTIONS, emotion
from emotivead.media import frames

SCHEMA = {'type': 'object', 'properties': {
    'text': {'type': 'string'}, 'emotion': {'type':'string','enum': EMOTIONS},
    'rationale': {'type':'string'}, 'intensity': {'type':'string','enum':['baja','media','alta']},
    'tone': {'type':'string'}, 'rhythm': {'type':'string'}},
    'required': ['text','emotion','rationale','intensity','tone','rhythm'], 'additionalProperties': False}


def describe(video, start, end, output, provider='ollama'):
    images = frames(video, start, end, output)
    model = os.environ.get('EMOTIVE_VISION_MODEL', 'qwen2.5vl:7b') if provider == 'ollama' else os.environ.get('OPENAI_MODEL', 'gpt-4o-2024-08-06')
    prompt = (
        'Eres un redactor de audiodescripción en español. Los fotogramas están en orden temporal. '
        'Describe únicamente acciones y objetos visibles; no inventes diálogos, identidades ni intenciones. '
        f'Escribe UNA narración breve que pueda leerse en {end-start:.2f} segundos, '
        f'idealmente no más de {max(2,int((end-start)*2))} palabras. '
        'No digas "la imagen muestra" ni agregues etiquetas o instrucciones al texto. '
        'Propón una emoción para la FORMA de narrar, sin atribuir emociones no observables a personas. '
        'rationale explica tu propuesta para revisión humana. Devuelve solo JSON con este esquema: '
        + json.dumps(SCHEMA, ensure_ascii=False))
    payload = {'model': model, 'stream': False, 'format': SCHEMA, 'keep_alive': 0,
               'options': {'temperature': 0, 'seed': 42, 'num_predict': 500},
               'messages': [{'role':'user','content':prompt,
                             'images':[base64.b64encode(p.read_bytes()).decode() for p in images]}]}
    base = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434').rstrip('/')
    headers = {'Content-Type':'application/json'}
    url = base+'/api/chat'
    if provider == 'openai':
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError('Define OPENAI_API_KEY mediante un secreto de Colab o una variable de entorno.')
        content = [{'type':'text','text':prompt}] + [
            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+image}}
            for image in payload['messages'][0]['images']]
        payload = {'model':model,'temperature':0,'max_tokens':800,
                   'messages':[{'role':'user','content':content}],
                   'response_format':{'type':'json_schema','json_schema':{
                       'name':'audiodescription','strict':True,'schema':SCHEMA}}}
        url = 'https://api.openai.com/v1/chat/completions'
        headers['Authorization'] = 'Bearer '+api_key
    elif provider != 'ollama':
        raise ValueError('Proveedor visual no admitido.')
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'El proveedor visual devolvió HTTP {exc.code}. Revisa el servicio, modelo y credenciales; no se usó una descripción ficticia.') from None
    if provider == 'openai':
        choice = result['choices'][0]
        if choice['message'].get('refusal') or choice.get('finish_reason') != 'stop':
            raise ValueError('La respuesta fue rechazada o quedó incompleta; revisa el segmento.')
        content = choice['message']['content']
    else:
        content = result['message']['content']
    proposed = json.loads(content)
    if not isinstance(proposed, dict) or any(k not in proposed for k in SCHEMA['required']):
        raise ValueError('El modelo no devolvió el JSON requerido. Puedes editar manualmente o reintentar.')
    if not isinstance(proposed['text'], str) or not 1 <= len(proposed['text'].strip()) <= 2000:
        raise ValueError('La descripción del modelo está vacía o excede el límite.')
    if proposed['intensity'] not in ['baja','media','alta']:
        raise ValueError('Intensidad inválida en la respuesta del modelo.')
    proposed['emotion'] = emotion(proposed['emotion'])
    proposed['model'] = model
    proposed['provider'] = provider
    proposed['review_status'] = 'draft'
    return proposed
