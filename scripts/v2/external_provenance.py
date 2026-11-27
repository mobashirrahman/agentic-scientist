"""Write docs/external_provenance.json: source -> raw files (URL, sha256, size, mtime) -> build script (+ git blob)
-> processed files (sha256, cells, stages) -> rule filter applied. Re-run after any external-data change.
Run: .venv/bin/python -I scripts/v2/external_provenance.py
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'data/external'
GEO = 'https://ftp.ncbi.nlm.nih.gov/geo'
SOURCES = {
    'qiu2024': dict(
        citation='Qiu et al. 2024, Nature 626:1084, doi 10.1038/s41586-024-07069-w', boards=['temporal'],
        raw=[], raw_note='Fetched cell subsets from CELLxGENE Census 2025-11-08 (server-side stage filter); no raw files kept.',
        scripts=['scripts/v2/fetch_qiu2024.py', 'scripts/v2/fetch_qiu2024_late.py', 'src/v2/anchor.py'],
        processed='qiu2024', manifests=['manifest.json', 'manifest_late.json'],
        rule='Theiler 12-13 and 23-25 only; Theiler 14-22 (covers >E9.5..E13.5) never transferred; asserted per row.'),
    'feulner2024': dict(
        citation='Feulner et al. 2024, bioRxiv 10.1101/2024.03.05.583423; GEO GSE150817', boards=['heart'],
        raw=[('feulner2024_raw/GSE150817_perinatheart.metadata.final_cells.tsv.gz', f'{GEO}/series/GSE150nnn/GSE150817/suppl/GSE150817_perinatheart.metadata.final_cells.tsv.gz'),
             ('feulner2024_raw/GSE150817_perinatheart.raw_umi_counts.final_cells.tsv.gz', f'{GEO}/series/GSE150nnn/GSE150817/suppl/GSE150817_perinatheart.raw_umi_counts.final_cells.tsv.gz')],
        scripts=['scripts/v2/build_heart_anchor_feulner.py'], processed='heart_anchor', manifests=['manifest.json'],
        rule='Age in {E14.5, E16.5, E18.5} kept; P0/P4/P7 dropped. Per-cell stage_days checked by harness.load_anchor.'),
    'gse282547': dict(
        citation='Developing mouse heart spatial atlas (2026 article, CC BY-NC-ND 4.0); GEO GSE282547', boards=['heart'],
        raw=[(f'gse282547_raw/{f}', f'{GEO}/samples/{g[:7]}nnn/{g}/suppl/{f}') for g, f in [
            ('GSM8645806', 'GSM8645806_SlideSeq_e14_1_normalized.rds.gz'), ('GSM8645807', 'GSM8645807_SlideSeq_e14_2_normalized.rds.gz'),
            ('GSM9065771', 'GSM9065771_SlideSeq_e15.5_1_normalized.rds'), ('GSM9065772', 'GSM9065772_SlideSeq_e15.5_2_normalized.rds')]],
        scripts=['scripts/v2/export_slideseq.R', 'scripts/v2/build_heart_spatial.py'], processed='heart_spatial', manifests=['manifest.json'],
        rule='Only pure E14.5/E15.5 Slide-seq pucks. Not downloaded: E10.5-E13.5 pucks, Wt1CreER-DTA mutant, Visium (incl. mixed E17/E11 and P2/E14 sections).'),
    'extended_mouse_atlas': dict(
        citation='Imaz-Rosshandler et al. 2024 (Extended Mouse Atlas), marionilab.github.io/ExtendedMouseAtlas; E-MTAB-13645', boards=['embryo'],
        raw=[('ema_raw/ExtendedMouseAtlas/embryo_complete.h5ad', 'https://bioinformatics.stemcells.cam.ac.uk/rlh60/Supplemental/ExtendedMouseAtlas/ExtendedMouseAtlas.tar.gz (member)'),
             ('ema_raw/ExtendedMouseAtlas/metadata_cells.csv', 'same archive (member)')],
        scripts=['scripts/v2/build_embryo_anchor.py'], processed='embryo_anchor', manifests=['manifest.json'],
        raw_deleted='Deleted after build: contains held-out-window cells (E7.5, E7.75 embryo; E8.5 heart). Re-download and verify by sha256 to rebuild.',
        rule='Stages E6.5-E7.25 and E8.0-E9.5 kept; E7.5, E7.75 and Mixed gastrulation dropped (asserted). Author cell types/clusters/embeddings not kept. log2 values inverted and re-normalised on the panel.'),
    'gene_ontology': dict(
        citation='Gene Ontology Consortium, MOUSE-mod.gaf + go-basic.obo (CC BY 4.0)', boards=['perturbation'],
        raw=[('go_raw/MOUSE-mod.gaf.gz', 'https://current.geneontology.org/annotations/gaf/MOUSE-mod.gaf.gz'),
             ('go_raw/go-basic.obo', 'https://current.geneontology.org/ontology/go-basic.obo')],
        scripts=['scripts/v2/prepare_go_prior.py'], processed='go_prior', manifests=['manifest.json'],
        raw_deleted='Deleted after build: contains mutant/expression-evidence annotations incl. Ctnnb1/Gata4. Re-download and verify by sha256 to rebuild.',
        rule='Evidence IMP/IGI/IEP/HMP/HGI/HEP dropped; annotations citing Ctnnb1/Gata4 (symbol or MGI id) dropped; NOT-qualified dropped.'),
    'expression_prior': dict(
        citation='Derived from the qiu2024 calibration cells (Qiu et al. 2024, Nature 626:1084)', boards=['perturbation'],
        raw=[], raw_note='Built from data/external/qiu2024/calibration_*.h5ad (wild type, Theiler 12-13); no other input.',
        scripts=['scripts/build_expression_prior.py'], processed='expression_prior', manifests=['manifest.json'],
        rule='Per-gene fraction expressing and mean log1p CP10k, overall and per cell type (>=30 cells); Theiler 12-13 only.'),
    'de_soysa2019_hand2': dict(
        citation='de Soysa et al. 2019, Nature 572:120, doi 10.1038/s41586-019-1414-x; GEO GSE126128', boards=['perturbation (validation only)'],
        raw=[(f'ko_validation/raw/hand2/{f}', f'{GEO}/series/GSE126nnn/GSE126128/suppl/{f}')
             for f in ('GSE126128_E775E825_WTKO_10X.csv.gz', 'GSE126128_E925_WTKO_10X.csv.gz')],
        scripts=['scripts/build_ko_validation.py'], processed='ko_validation', manifests=['manifest.json'],
        rule='Dev splits hand2_e825/hand2_e925 only (wild type vs Hand2-null, same experiment; E7.75/E8.25/E9.25, all <= E9.5). '
             'Hand2 is neither a Gata4 allele nor a Wnt/beta-catenin pathway perturbation.'),
}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def git(*a):
    return subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main():
    out = dict(generated=time.strftime('%Y-%m-%d %H:%M:%S'), repo_commit=git('rev-parse', 'HEAD'),
               rules='Rules s10 + organiser Slack answers (docs/SLACK_NOTES.md); disclosure text in docs/EXTERNAL_SOURCES.md',
               harness_checks='shinka_ve/harness.py FORBIDDEN_DAYS + load_anchor (per-cell stage_days, manifest stages, perturbation flag)',
               sources={})
    prev_path = ROOT / 'docs/external_provenance.json'
    prev = {r['path']: r for v in (json.loads(prev_path.read_text())['sources'].values() if prev_path.exists() else [])
            for r in v['raw_files']}
    for k, s in SOURCES.items():
        raw = []
        for rel, url in s['raw']:
            p = E / rel
            if not p.exists() and prev.get(f'data/external/{rel}', {}).get('sha256'):
                r = dict(prev[f'data/external/{rel}'])
                r.update(exists=False, deleted_after_build=True,
                         deleted_reason=s.get('raw_deleted', 'raw file deleted after build'))
                raw.append(r)
                continue
            raw.append(dict(path=f'data/external/{rel}', url=url, exists=p.exists(),
                            sha256=sha(p) if p.exists() else None, bytes=p.stat().st_size if p.exists() else None,
                            downloaded=time.strftime('%Y-%m-%d', time.localtime(p.stat().st_mtime)) if p.exists() else None))
        scripts = [dict(path=x, git_blob=git('rev-parse', f'HEAD:{x}') or None) for x in s['scripts'] if not x.startswith('(')]
        processed = {}
        for m in s['manifests']:
            mp = E / s['processed'] / m
            if mp.exists():
                for name, meta in json.loads(mp.read_text()).get('files', {}).items():
                    f = E / s['processed'] / name
                    processed[name] = dict(manifest_sha256=meta.get('sha256'), disk_sha256=sha(f) if f.exists() else None,
                                           **{x: meta[x] for x in ('cells', 'stages', 'stages_days', 'genes', 'kept', 'dropped', 'release') if x in meta})
                    processed[name]['match'] = processed[name]['manifest_sha256'] == processed[name]['disk_sha256']
        out['sources'][k] = dict(citation=s['citation'], boards=s['boards'], rule_filter=s['rule'], raw_files=raw,
                                 raw_note=s.get('raw_note'), build_scripts=scripts, processed_dir=f"data/external/{s['processed']}",
                                 processed_files=processed)
    p = ROOT / 'docs/external_provenance.json'
    p.write_text(json.dumps(out, indent=1))
    bad = [(k, n) for k, v in out['sources'].items() for n, f in v['processed_files'].items() if not f['match']]
    miss = [r['path'] for v in out['sources'].values() for r in v['raw_files'] if not r['exists'] and not r.get('deleted_after_build')]
    print('sources', len(out['sources']), 'processed', sum(len(v['processed_files']) for v in out['sources'].values()),
          'sha mismatches', bad, 'missing raw', miss)


if __name__ == '__main__':
    main()
