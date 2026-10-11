#!/usr/bin/env python3
"""Static transitive ELF dependency/symbol-name audit; not a linker namespace test."""
import argparse,hashlib,importlib.util,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ['recovery','runtime','dump_erofs','output']:p.add_argument(n,type=Path)
p.add_argument('--stage',type=Path,action='append',required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit-userspace.py'));au=importlib.util.module_from_spec(spec);spec.loader.exec_module(au);_,parts=au.partitions(a.recovery)
providers={};cache={};roots=[]
for image,offset,path in [(a.runtime,0,'/lib64/bionic')]+[(a.recovery,parts[n][0]['offset'],d) for n,d in [('vendor_a','/lib64'),('system_a','/system/lib64'),('system_ext_a','/lib64')]]:
 text=subprocess.check_output([str(a.dump_erofs),'--offset='+str(offset),'--ls','--path='+path,str(image)],text=True)
 for line in text.splitlines():
  m=re.match(r'\s*\d+\s+[137]\s+(\S+\.so)$',line)
  if m:providers.setdefault(m[1],(image,offset,path+'/'+m[1]))
for stage in a.stage:
 for row in json.loads((stage/'manifest.json').read_text())['files']:
  path=stage/'vendor'/row['path']
  if path.read_bytes()[:4]!=b'\x7fELF':continue
  assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'];roots.append(path)
  if 'native_keymint' not in path.parts:providers[path.name]=path
private=next(x for x in roots if 'native_keymint' in x.parts)
def resolve(name,use_private):
 if use_private and name=='libcrypto.so':return private
 value=providers.get(name)
 if value is None:return None
 if isinstance(value,Path):return value
 image,offset,path=value;key=str(image)+':'+str(offset)+':'+path
 if key not in cache:
  target=a.output/(hashlib.sha256(key.encode()).hexdigest()[:16]+'-'+name)
  target.write_bytes(subprocess.check_output([str(a.dump_erofs),'--offset='+str(offset),'--cat','--path='+path,str(image)]));cache[key]=target
 return cache[key]
parsed={}
def parse(path):
 if path in parsed:return parsed[path]
 dynamic=subprocess.check_output(['readelf','-d',str(path)],text=True)
 needed=re.findall(r'\(NEEDED\).*\[(.*?)\]',dynamic)
 text=subprocess.check_output(['readelf','--dyn-syms','--wide',str(path)],text=True)
 exports=set();imports=set()
 for l in text.splitlines():
  m=re.match(r'\s*\d+:\s+[0-9a-fA-F]+\s+\d+\s+.+?\s+(GLOBAL|WEAK|LOCAL)\s+\S+\s+(\S+)\s+(\S+)',l)
  if not m:continue
  binding,index,symbol=m.groups();name=symbol.split('@')[0]
  if index=='UND' and binding!='WEAK':imports.add(name)
  elif index!='UND' and binding in ['GLOBAL','WEAK']:exports.add(name)
 parsed[path]=(needed,exports,imports);return parsed[path]
rows=[]
for root in roots:
 seen=set();missing=set();stack=[root];private_scope=('native_keymint' in root.parts or root.name=='android.hardware.security.keymint-service')
 while stack:
  path=stack.pop()
  if path in seen:continue
  seen.add(path)
  for name in parse(path)[0]:
   dep=resolve(name,private_scope)
   if dep:stack.append(dep)
   else:missing.add(name)
 exports=set().union(*(parse(path)[1] for path in seen))
 unresolved={str(path):sorted(parse(path)[2]-exports) for path in seen if parse(path)[2]-exports}
 rows.append({'root':str(root),'closure_libraries':len(seen),'missing_libraries':sorted(missing),'unresolved_symbol_names':unresolved})
report={'status':'STATIC_SYMBOL_NAMES_ONLY; symbol versions, load ordering and Android namespace access not verified','roots':rows}
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'roots':len(rows),'with_missing_libraries':sum(bool(r['missing_libraries']) for r in rows),'with_unresolved_names':sum(bool(r['unresolved_symbol_names']) for r in rows)}))
