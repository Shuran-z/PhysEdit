import sqlite3,json,collections
from pathlib import Path
root=Path('/srv/phylabel/current');conn=sqlite3.connect('file:/srv/phylabel/data/annotations.sqlite3?mode=ro',uri=True);print('tables',[x[0] for x in conn.execute("select name from sqlite_master where type='table'")]);print('task_columns',[x[1] for x in conn.execute('pragma table_info(tasks)')]);rows=conn.execute('select * from tasks limit 1');r=rows.fetchone();names=[x[0] for x in rows.description];p=json.loads(r[names.index('payload')]);print('payload_keys',list(p));print('source_keys',list(p.get('source',{})));print('generation_metadata_keys',list(p.get('source',{}).get('generation_metadata',{})))
def walk(x,path=''):
 if isinstance(x,dict):
  for k,v in x.items():
   if k in ['selected_parameter_keys','omitted_parameter_keys']:yield path+'/'+k,v
   yield from walk(v,path+'/'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from walk(v,path+'/'+str(i))
found=[];t04=[]
for row in conn.execute('select id,payload from tasks'):
 p=json.loads(row[1]);matches=list(walk(p))
 if matches:found.append({'id':row[0],'clip_id':p.get('clip_id'),'matches':matches})
 if p.get('clip_id','').startswith('T04_C'):t04.append({'id':row[0],'clip_id':p['clip_id'],'source_keys':list(p.get('source',{})),'source_video_id':p.get('source',{}).get('source_video_id'),'source_video_sha256':p.get('source',{}).get('source_video_sha256'),'matches':matches})
print('tasks_with_selection_keys',len(found));print('examples',json.dumps(found[:2])[:4000]);print('t04_tasks',len(t04),'example',json.dumps(t04[:2])[:2000])
files=[]
for p in (root/'resources').glob('*.json'):
 if 'selected_parameter_keys' in p.read_text(errors='replace'):files.append(p.name)
print('resources_with_selected_keys',files);print('reference_pointer',(root/'resources/active_reference_release.json').read_text()[:1600])
