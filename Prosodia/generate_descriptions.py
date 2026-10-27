"""Optional new video -> reviewed-project draft. Existing data is never overwritten."""
import argparse
from pathlib import Path
from emotivead.contracts import read_json, validate_segments, write_json
from emotivead.media import probe
from emotivead.vision import describe


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--provider', choices=['openai','ollama'], default='openai')
    p.add_argument('--intervals', type=Path, help='Lista JSON de {start,end}; sin ella se describe el clip completo')
    a=p.parse_args()
    info=probe(a.video)
    intervals=read_json(a.intervals) if a.intervals else [{'start':0,'end':info['duration']}]
    selections=validate_segments([{**s,'id':f's{i+1:03d}','text':'validación','emotion':'Serenidad'}
                                  for i,s in enumerate(intervals)],info['duration'])
    if (a.output/'projects.json').exists():
        raise SystemExit('Ya existe projects.json: usa una carpeta nueva para conservar la versión revisada.')
    segments=[]
    for s in selections:
        result=describe(a.video,s['start'],s['end'],a.output/'frames'/s['id'],a.provider)
        segments.append({**s,'text':result['text'],'emotion':result['emotion'],'analysis':result})
    project={'schema_version':1,'video_id':a.video.stem,'video':str(a.video.resolve()),
             'duration':info['duration'],'source':a.provider,'review_status':'draft','segments':segments}
    write_json(a.output/'projects.json',[project])
    write_json(a.output/'audiodescriptions.json',segments)
    write_json(a.output/'video_summary.json',{'main_summary':' '.join(s['text'] for s in segments)})
    write_json(a.output/'prosody_analysis.json',{'schema_version':1,'segments':[
        {'id':s['id'],'complementary_emotion':s['emotion'],**s['analysis']} for s in segments]})
    print('JSON guardados. Revisa texto, emoción y tiempos antes de sintetizar con --projects.')
