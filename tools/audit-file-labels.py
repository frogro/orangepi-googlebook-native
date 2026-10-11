#!/usr/bin/env python3
"""Resolve staged paths using libselinux against the original vendor file contexts."""
import argparse,ctypes,json,stat
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('contexts',type=Path);p.add_argument('output',type=Path);p.add_argument('manifests',type=Path,nargs='+');a=p.parse_args()
class Opt(ctypes.Structure):_fields_=[('type',ctypes.c_int),('value',ctypes.c_char_p)]
lib=ctypes.CDLL('libselinux.so.1',use_errno=True)
lib.selabel_open.argtypes=[ctypes.c_uint,ctypes.POINTER(Opt),ctypes.c_uint];lib.selabel_open.restype=ctypes.c_void_p
lib.selabel_lookup_raw.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),ctypes.c_char_p,ctypes.c_int];lib.selabel_lookup_raw.restype=ctypes.c_int
lib.freecon.argtypes=[ctypes.c_void_p];lib.selabel_close.argtypes=[ctypes.c_void_p]
opt=Opt(3,str(a.contexts.resolve()).encode());handle=lib.selabel_open(0,ctypes.byref(opt),1)
if not handle:raise OSError(ctypes.get_errno(),'Cannot load file contexts')
rows=[]
try:
 for m in a.manifests:
  for f in json.loads(m.read_text())['files']:
   path='/vendor/'+f['path'];ctx=ctypes.c_void_p()
   ret=lib.selabel_lookup_raw(handle,ctypes.byref(ctx),path.encode(),stat.S_IFREG|int(f['mode'],8))
   actual=ctypes.string_at(ctx).decode() if ret==0 else None
   if ctx.value:lib.freecon(ctx)
   expected='u:object_r:'+f['selinux_type_required']+':s0'
   rows.append({'path':path,'expected':expected,'resolved':actual,'matches':actual==expected})
finally:lib.selabel_close(handle)
report={'status':'PATH_LABEL_AUDIT_ONLY; does not verify domain permissions or transitions','files':rows,'mismatches':sum(not r['matches'] for r in rows)}
with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(str(report['mismatches'])+' mismatches in '+str(len(rows))+' files')
for r in rows:
 if not r['matches']:print(r['path'],r['resolved'],'expected',r['expected'])
