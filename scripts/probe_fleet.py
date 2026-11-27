"""Read-only SSH inventory of Bio01–Bio24; saves resource and reachability evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REMOTE='''import json,os,subprocess,socket
mem={}
for line in open('/proc/meminfo'):
 k,v=line.split(':',1)
 if k in ('MemTotal','MemAvailable'):mem[k]=int(v.split()[0])
p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader'],capture_output=True,text=True)
print(json.dumps(dict(host=socket.getfqdn(),cpus=os.cpu_count(),memory_kib=mem,gpu=p.stdout.strip(),project_exists=os.path.isdir('/scratch/user/virtual-embryo'))))
'''

def probe(i):
 host=f'bio{i:02}.cluster.example'
 try:
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=6',host,'python3 -c '+shlex.quote(REMOTE)],capture_output=True,text=True,timeout=15)
  if p.returncode:return host,{'reachable':False,'error':p.stderr.strip()[-300:]}
  return host,dict(reachable=True,**json.loads(p.stdout))
 except Exception as e:return host,{'reachable':False,'error':str(e)}

if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=6) as pool:
  result=dict(pool.map(probe,range(1,25)))
 (ROOT/'docs/compute_inventory.json').write_text(json.dumps(result,indent=2)+'\n')
 for host,item in result.items():print(host,item,flush=True)
