#!/bin/bash
# Fetch GSE280543 snRNA (Mef2c) E8.5/E9 samples, keeping panel-gene rows only (streamed; full matrices never stored).
set -euo pipefail
PY=/scratch/user/virtual-embryo/.venv/bin/python
D=/scratch/user/virtual-embryo/data/external/ko_validation/raw/mef2c
S=$(dirname "$0")
cd "$D"
$PY -I -c "import anndata as ad;print('\n'.join(ad.read_h5ad('/scratch/user/virtual-embryo/data/raw/T2/E8.75.h5ad',backed='r').var_names))" > panel.txt
one() {
  g=$1; n=$2; base=https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM8600nnn/$g/suppl/${g}_$n
  curl -sf -o ${g}_barcodes.tsv.gz ${base}_barcodes.tsv.gz
  curl -sf -o ${g}_features.tsv.gz ${base}_features.tsv.gz
  zcat ${g}_features.tsv.gz | awk -F'\t' 'NR==FNR{p[$1];next} ($2 in p)&&($3=="Gene Expression"){print FNR}' panel.txt - > ${g}_keep.txt
  curl -sf ${base}_matrix.mtx.gz | zcat | $PY -I $S/stream_mtx.py ${g}_keep.txt ${g}_panel.mtx
  echo "$g done $(wc -l < ${g}_keep.txt) genes $(wc -l < ${g}_panel.mtx) entries"
}
one GSM8600343 s10 & one GSM8600344 s11 & one GSM8600342 s9 & one GSM8600345 s12 & wait
one GSM8600338 s5 & one GSM8600341 s8 & one GSM8600339 s6 & one GSM8600340 s7 & wait
