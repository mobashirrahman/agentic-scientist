"""Stream a 10x matrix.mtx.gz from stdin, keeping only rows (features) listed in a keep-file. Writes a small mtx-like TSV."""
import sys
keep = set(int(x) for x in open(sys.argv[1]))
out = open(sys.argv[2], 'w')
header = True
for line in sys.stdin:
    if line.startswith('%'):
        continue
    if header:
        out.write('#' + line); header = False; continue
    r, rest = line.split(' ', 1)
    if int(r) in keep:
        out.write(line)
out.close()
