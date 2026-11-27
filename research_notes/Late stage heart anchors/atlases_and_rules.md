# Late-stage heart anchors: whole-embryo atlases and the external-data rules

Research date: 2026-11-17. Scope: mouse only. No large files were downloaded.

Evidence labels:
- **Verified**: read from the page in this session. Challenge pages were checked against raw HTML saved at `/scratch/user/tmp/claude-7059086/-scratch-user-virtual-embryo/276ca0d4-5ce5-45dc-b11c-442640774cbc/scratchpad/ve_pages/` (rules.html, faq.html, tasks_temporal.html, tasks_spatial.html, tasks_perturbation.html, data.html, plus stripped .txt copies). WebFetch summaries were not used as quotes.
- **Snippet**: seen only in a search-result summary, not opened.
- **Unverified**: not checked in this session. Listed from memory or as a gap.

---

## Key Question 1: The external-data rules, quoted

### Takeaway
External public data may be used for every task and is "expressly encouraged" for Task 1. Four fixed limits apply: (1) no measured data from held-out stages or genotypes by any route; (2) an explicit window that excludes everything after E9.5 up to and including E13.5; (3) strict bracketing for interpolation targets; (4) every external source disclosed with the submission and described in the method summary. The 26 August 2026 restatement applies to all submissions made from that date, so it governs any submission made now (today is 17 November 2026).

### Cited Findings
All rule quotes are from the raw page. Section numbers are from the page's headings.

- Licence (section 10): "Competition data is released under the Terms of Use, clause 14, and is provided for research and educational purposes." [Rules](https://virtualembryo.ai/challenge/rules)
- Permission (section 10): "External public data, pre-trained models and published code may be used, provided their licences permit it and their use is described in the method summary. For Task 1 this is expressly encouraged." [Rules](https://virtualembryo.ai/challenge/rules)
- Disclosure (section 10): "Every external source must be disclosed with the submission. An undisclosed source is a rules violation whether or not it changed the result, because the disclosure is what makes the previous condition checkable." [Rules](https://virtualembryo.ai/challenge/rules)
- Held-out list (section 10): "The held-out stages and genotypes are: E10.5 and E12.5 for Task 1; E7.5 and E7.75 in the embryo setting and E8.5, E10.5 and E12.5 in the heart setting for Task 2; and the Gata4 and β-catenin knockouts at E8.75 for Task 3. Everything else is fair game, and for Task 1 external data is expressly encouraged." [Rules](https://virtualembryo.ai/challenge/rules)
- No-route clause: "What you may not use is measured data from a held-out stage or genotype, by any route: not directly, not through a model pre-trained on it, and not through a public dataset that contains it." [FAQ](https://virtualembryo.ai/challenge/faq)
- Midpoint rule (the brief's paraphrase is not the wording): "Nearness counts, and the stage label is not the test. External data is treated as a held-out stage when it sits closer to that stage than to the nearest stage we released for the same task: the midpoint between them is the boundary." It continues: "Holding out E9.5 and training on an external E9.45 embryo is using the answer under a different name; so is a dataset labelled with a somite count or a Theiler stage that lands in the same window. Where a held-out stage lies beyond the last released one, as the extrapolation targets do, everything from the midpoint onwards is treated as held out." [Rules](https://virtualembryo.ai/challenge/rules)
- Window: "For the extrapolation targets the window is stated outright rather than derived, and it relaxes the midpoint rule above rather than following it: without it, everything from E10.0 onwards would be held out and no later development could be used at all. External data is excluded from after E9.5 up to and including E13.5. External data at E10.5 and E12.5 remains prohibited. [...] Anything after E13.5 may be used, provided the source and its stages are stated explicitly with the submission." [Rules](https://virtualembryo.ai/challenge/rules)
- Endpoints: "External data measured at exactly E9.5 is permitted: E9.5 is a released training stage [...]. External data measured at exactly E13.5 is not permitted: E13.5 is the far edge of the protected window rather than the first point outside it, and it sits one day from the test target." [Rules](https://virtualembryo.ai/challenge/rules)
- Interpolation bracketing: "For interpolation targets, external data too close to a held-out stage is also treated as held out. The boundary is the released stage on either side of it: external data may not be used if it stages strictly between the two released stages that bracket a held-out one. In Task 2 that means heart data strictly between E8.25 and E8.75, and embryo data strictly between E7.25 and E8.0. The bracketing stages themselves are permitted [...]. Fractional stagings do arise in external data, from somite counts and Theiler stages, and they are placed on this scale and judged by the same boundary; the boundary itself stays on the stages we published." [Rules](https://virtualembryo.ai/challenge/rules)
- Genotype and perturbation: "The same applies to genotype. Data from the held-out knockouts, from another allele of the same gene at a comparable stage, or from a perturbation that phenocopies them, is treated as the held-out condition." [Rules](https://virtualembryo.ai/challenge/rules)
- Spanning resources: "A general-purpose resource that happens to span a held-out stage is not banned outright: the cells inside the window must be removed before training, and the removal described in the method summary. Using the resource with them left in is using the held-out data." [Rules](https://virtualembryo.ai/challenge/rules)
- Uncertain sources: "If a source sits near the boundary and you are unsure, ask before submitting. The Organisers will answer, and an answer given in advance is not a finding of misconduct afterwards." [Rules](https://virtualembryo.ai/challenge/rules)
- Restatement (section 10): "This restatement corrects the previous wording rather than tightening it, and it applies to submissions made from 26 August 2026. The embryo interval is wider than the text it replaces. Nothing already submitted is reopened." [Rules](https://virtualembryo.ai/challenge/rules). The FAQ does not contain a restatement. Its only later date is the 2 December 2026 final deadline.
- P2 validation exception (section 10): "[...] solely for preparing P3 predictions after access is granted. This exception does not permit hidden test data, additional external data from protected stages or genotypes, or redistribution outside the applicable data terms." [Rules](https://virtualembryo.ai/challenge/rules)
- Disqualification (section 16) includes "use of held-out data, or any attempt to recover it;" [Rules](https://virtualembryo.ai/challenge/rules)
- Temporal task page: "Participants may additionally train on external public single-cell data; only the evaluation stages are fixed, and any external source must be disclosed with the submission." [Temporal](https://virtualembryo.ai/challenge/tasks/temporal)
- Spatial and perturbation task pages (raw HTML checked): no external-data rule text.
- **Conflict**: the data page says, in the Task 1 description: "Task 1 is the only task where training on external public single-cell data is allowed, provided the source is disclosed with the submission." [Data](https://virtualembryo.ai/challenge/data). This conflicts with rules section 10 ("External public data [...] may be used") and with the temporal page.
- Virtual Embryo atlas (challenge's own browsable atlas) is also an external source: "no measured data from a held-out stage or condition may be used, not for training, not for fine-tuning, not transferred in under another name." [Data](https://virtualembryo.ai/challenge/data)
- FAQ on overlap: "Hidden splits are defined by developmental stage, perturbation condition, or combinations thereof. Distinct from public splits. Models must learn generalisable developmental dynamics, not memorise." [FAQ](https://virtualembryo.ai/challenge/faq)

### Inferences
- Window reading: E9.5 exactly is permitted. Anything in (E9.5, E13.5] is excluded. Anything after E13.5 is permitted with disclosure. The window starts at E9.5, earlier than the E10.0 midpoint that the midpoint rule would give, so it is stricter over E9.5–E10.0 and more permissive after E13.5.
- The window is written "for the extrapolation targets". Those are E10.5 and E12.5 for Task 1 and for the heart setting of Task 2. The embryo setting has no extrapolation target, so the rules do not say whether the window applies to embryo-setting data at E9.6–E13.5. The conservative reading applies it.
- Held-out lists for Task 2 are split by setting ("in the embryo setting", "in the heart setting"). The rules do not say whether a stage held out in one setting (for example E8.5 for heart) blocks external data for the other. The conservative reading treats it as blocked.
- The operative midpoint wording is "closer to that stage than to the nearest stage we released for the same task", not "closer to a held-out stage than to the nearest released stage" as in the brief.
- For Tasks 2 and 3, the rules permit external data generally, but the data page limits external single-cell training to Task 1. Until this is resolved, external training data for Tasks 2 and 3 should be treated as not cleared.
- Rules may be amended. "Material changes are announced on this page and carry a new version," and each acceptance is "recorded against the version in force" (rules sections 1 and 2). The team should record the version it accepted. [Rules](https://virtualembryo.ai/challenge/rules)

### Gaps
- The wording of the pre-26 August 2026 embryo interval is not on any page checked. The restatement says it was narrower.
- No forum or discussion pages were searched or read. The FAQ has no entry on P0, adult, or heart-atlas use.
- The data-page "only Task 1" sentence versus the rules is unresolved (see Key Question 2 questions for the organisers).

---

## Key Question 2: Which external stages are allowed per task

### Takeaway
- Task 1 (temporal): any stage up to and including E9.5, and any stage after E13.5 with disclosure. E10.5–E13.5 are excluded.
- Task 2 heart: up to E8.25, E8.75, E9.0–E9.5, and after E13.5 with disclosure. E8.5 and the open interval (E8.25, E8.75) are excluded. E10.0–E13.5 is excluded by the window.
- Task 2 embryo: up to E7.25 (including E6.5, E6.75, E7.0), E8.0 exactly, and E8.25 by the letter of the rules. E7.5, E7.75 and the open interval (E7.25, E8.0) are excluded.
- Task 3 (genotype): no stage is held out by the stage rules, because the held-out items are the Gata4 and β-catenin knockouts at E8.75. External Gata4 and β-catenin data is excluded for any allele at a comparable stage and for phenocopying perturbations. Everything else is not restricted by the letter, but the data-page conflict makes external training unresolved.
- E14.5, E14.0, and later stages are allowed for all tasks with disclosure. E13.5 is excluded. TS22 is ambiguous.

### Cited Findings
Task definitions and released/held-out stages are from the task pages and the rules page.

- Temporal (Task 1): train E8.5 and E9.5; validation E10.5; test E12.5. The page says "There is no E9.25 in this release." [Temporal](https://virtualembryo.ai/challenge/tasks/temporal)
- Heart (Task 2): train E8.25, E8.75, E9.5; validation E8.5 (interpolation) and E10.5 (extrapolation); test E12.5 (extrapolation). The page says "The heart setting follows heart-tube formation and looping." [Spatial](https://virtualembryo.ai/challenge/tasks/spatial)
- Embryo (Task 2): train E6.75, E7.25, E8.0; validation E7.5; test E7.75 (not released). "Sits between E7.25 and E8.0, so the embryo setting is interpolation throughout." [Spatial](https://virtualembryo.ai/challenge/tasks/spatial)
- Perturbation (Task 3): Mab21l2 KO at E9.5 (train); Gata4 KO at E8.75 (validation); β-catenin KO at E8.75 (test). "Broadly expressed, so its effect is diffuse: the hardest of the three." [Perturbation](https://virtualembryo.ai/challenge/tasks/perturbation). The data page lists matched WT at E8.75 and E9.5 as references. [Data](https://virtualembryo.ai/challenge/data)
- The rules' bracket rule gives the same embryo and heart intervals as stated in the brief. [Rules](https://virtualembryo.ai/challenge/rules)

Allowed-stage table (my reading of the rules, per task):

| Task | Allowed external stages | Excluded | Unresolved |
|---|---|---|---|
| Task 1 (temporal) | Any t ≤ E9.5, including E9.5 exactly (E8.5 is a released stage). Any t > E13.5 with disclosure: E14.0, E14.5, E15.5, E16.5, E17+, P0. | E9.5 < t ≤ E13.5: E10.5, E11.5, E12.5, E13.5 | TS22 (see below) |
| Task 2 heart | t ≤ E8.25 (E8.25 is a bracket stage). E8.75 exactly. E9.0 to E9.5 including E9.5. Any t > E13.5 with disclosure. | E8.5 (held out). Open interval (E8.25, E8.75). E9.5 < t ≤ E13.5 (window; E10.5 and E12.5 held out). | Embryo-setting held-out stages (E7.5, E7.75) and embryo-setting E8.5, if held-out status is task-wide |
| Task 2 embryo | t ≤ E7.25 (E6.5, E6.75, E7.0, E7.25). E8.0 exactly. E8.25 and later by the letter (not held out; closer to E8.0 than to E7.75). Any t > E13.5 with disclosure. | E7.5 and E7.75 (held out). Open interval (E7.25, E8.0). | Whether the window applies to E9.6–E13.5 in this setting; whether heart-held-out E8.5 blocks this setting |
| Task 3 (genotype) | No stage held out by the stage rules. Non-Gata4, non-β-catenin external data at any stage is not restricted by the letter. | Any Gata4 or β-catenin knockout data (other alleles at comparable stage, phenocopying perturbations) | Whether external WT E8.75 is blocked (E8.75 is a KO held-out stage but a WT reference); "comparable stage" and "phenocopies" undefined; data-page conflict |

Direct answers:
- **Is E14.5 allowed?** Yes, for all tasks, with the source and its stages stated explicitly in the submission. The window ends at E13.5.
- **Is E13.5 excluded?** Yes. The rules say "External data measured at exactly E13.5 is not permitted."
- **Are E14.0 and later allowed?** Yes, with disclosure, because "Anything after E13.5 may be used."
- **TS22 and TS23**: Sources put TS22 at about E13.5 (UNSW) or 13.5–15 dpc (EMAP). Under the rules, a TS22 dataset is placed on the E-scale and judged by the same boundary. A TS22 dataset at or before E13.5 is excluded. A TS22 dataset with documented embryo age above E13.5 is permitted with disclosure. TS23 (about E14.5 per UNSW) is permitted with disclosure. See Key Question 9.
- **P0 heart and adult heart**: after E13.5, so permitted by the letter with disclosure. The FAQ does not address them.

### Inferences
- A general-purpose atlas that spans held-out stages (Qiu 2024, MOCA, MOSTA, and others) can be used only after the window cells are removed before training, and the removal must be described in the method summary.
- The team's late-stage anchor value is confined to stages after E13.5 (Task 1 and heart) and E9.5 exactly for MOCA-type data. Stages E10–E13.5 are the protected window.

### Gaps: questions to put to the organisers before submitting
1. The data page says Task 1 is the only task allowing external single-cell training. The rules and temporal page say otherwise. Which governs Tasks 2 and 3?
2. Are held-out stage lists per task or per setting? In particular, is embryo-setting data at E8.5 blocked by the heart held-out E8.5?
3. Does the window (after E9.5 to E13.5) apply to the embryo setting of Task 2?
4. How are TS22 embryos placed? Is a dpc range (13.5–15) accepted, or must it be documented per embryo?
5. For Task 3: is WT E8.75 external data blocked? What counts as a "comparable stage" and a "phenocopying perturbation"?
6. What was the pre-26 August 2026 embryo interval? Is any earlier submission affected? (The restatement says nothing already submitted is reopened.)
7. Is a heart-setting P0 or adult atlas permitted without further clearance? The rules' letter says yes with disclosure.

---

## Key Question 3: Disclosure, FAQ, and atlas-anchor guidance

### Takeaway
Disclosure is required per submission. Every external source must be disclosed with the submission and described in the method summary, and window cells must be removed with the removal described. The FAQ does not discuss P0, adult or heart atlases. No forum was checked.

### Cited Findings
- Disclosure, method summary, window-cell removal, and "ask before submitting" are quoted in Key Question 1. [Rules](https://virtualembryo.ai/challenge/rules)
- FAQ entry "May I train on external public data?" restates the held-out list, the midpoint, the embryo and heart brackets, the perturbation exclusion, and the window. It says "You may train on external data, public or your own, and for Task 1 this is expressly encouraged." [FAQ](https://virtualembryo.ai/challenge/faq). It also says "Every external source must be disclosed with the submission; an undisclosed one is a violation whether or not" it changed the result (truncated in the raw text).
- FAQ entry "Will the test data overlap with public atlases?" answer quoted in Key Question 1. [FAQ](https://virtualembryo.ai/challenge/faq)
- Data page on the Virtual Embryo atlas: "using it there is using the answer, however it is routed." [Data](https://virtualembryo.ai/challenge/data)
- Rules section 16 lists "use of held-out data, or any attempt to recover it;" as grounds for disqualification. [Rules](https://virtualembryo.ai/challenge/rules)

### Inferences
- Disclosure must be attached to each submission that uses an external source, and must name the source and its stages. Because the rules tie disclosure to "the submission", a source used in an earlier submission and not disclosed there is a violation risk.
- P0 and adult heart data are far from the window boundary, so the rules do not require asking in advance. Asking is still low cost.

### Gaps
- No forum or Discord pages were searched or read.
- The FAQ entry "Does my coordinate frame have to match the atlas?" was not read.

---

## Key Question 4: Qiu et al. 2024 (sci-RNA-seq3, E8 to P0)

### Takeaway
Qiu 2024 is the only atlas here covering E8 to P0. Under the rules it is usable only at or before E9.5 (somite-staged embryos, with the edge near 24–26 somites) and at E14.0 and later (6-hour bins, disclosed). E10–E13.5 must be removed. Cardiomyocyte labels are present in Supplementary Table 5 (see addendum). The format is H5AD, the accession is GEO GSE186069 and GSE228590 per the CELLxGENE collection, and the four embryos labelled TS23 in the coordinator's request are E15.0–E15.75 in the paper's Supplementary Table 1 (see addendum). The PMC full text was not reached (reCAPTCHA page).

### Cited Findings
- Citation: Nature 626, 1084–1093 (2024), DOI 10.1038/s41586-024-07069-w, online 14 February 2024 [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/) (verified). The Shendure-lab PDF is also listed: [PDF](https://shendure-web.gs.washington.edu/documents/qiu_nature_february2024.pdf) (snippet).
- Scale (verified, conflict within the paper): the abstract gives 12.4 million nuclei from 83 embryos; the Results give 11,441,407 nuclei from 74 embryos. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)
- Staging (verified): somite counts to about E10 (2-hour bins for 0–34 somites; counts 1, 13 and 19 missing); limb-bud geometry for E10–E15; gestational age for E17.0–E18.75. Six-hour bins from E8 to P0 (45 bins). [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)
- Somite-to-age (verified): Extended Data Fig. 8a maps "24 to 26 somites to about E9.5". [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)
- Named timepoints in the visible text (verified): E9.5 (via somite mapping), E10.5, E11, E11.75, E13.5, E14.0–E14.75, E17.0–E17.75, E18.75, P0. E12.5, E14.5, E15.5 and E16.5 are not named. Their ages fall in six-hour bins that the fetch summary describes as spanning, for example, E12.0–E14.25 and E15.0–E16.75. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)
- Cell types (verified): 26 major clusters and 190 labelled cell types (Supplementary Table 5), described as preliminary. Visible cardiac terms: "cardiac (proepicardium)" among lateral-plate and intermediate-mesoderm subtypes, and a proepicardium/mesothelium marker set. The PMC text read did not show a cardiomyocyte label, but Supplementary Table 5 does (see addendum). [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)
- Embryos per stage: Supplementary Table 1, not accessible. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)
- Sequencing and licence (snippet): 15 sci-RNA-seq3 experiments, 21 NovaSeq runs; article under CC BY 4.0. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/) (snippet from search).
- Challenge organisers: "The Challenge is organised by the Qiu Lab at Stanford University". [Rules](https://virtualembryo.ai/challenge/rules). Whether this lab produced the dataset is not verified.

### Inferences
- Usable for Task 1 and heart under the rules:
  - E8.0 to E9.5 embryos, identified by somite count, if the mapped age is at or before E9.5. Embryos at about 24–26 somites map to E9.5, so anything at or above that range is at the window edge. Exclude or confirm with the organisers.
  - Bins from E14.0 onward, including the E14.0–E14.75 bin that contains E14.5, with disclosure.
  - Remove E10–E13.5 bins. Any bin that straddles E13.5 (for example the E12.0–E14.25 bin described in the fetch summary) must be split by per-embryo age or dropped.
- Whether a heart or cardiomyocyte subset exists must be checked in Supplementary Table 5 or the data object. It cannot be claimed from the text read.

### Gaps
- **Partly verified since the first pass** (see addendum): accession (GEO GSE186069 and GSE228590, per the CELLxGENE collection links), format (H5AD), size (whole raw-count H5AD 46.3 GB), and heart labels (Supplementary Table 5 "22) Cardiomyocytes"). **Still not verified**: GSE228590 series matrix, dataset-level licence (the CC BY 4.0 statement is for the article), per-cell embryo-to-stage mapping in the CELLxGENE data.
- The JAX affiliation in the brief was not verified. The one search hit was a JAX meeting abstract (https://mouseion.jax.org/stfb2024/42), which was not opened.
- The PMC article page returns a reCAPTCHA challenge to scripted requests, so the data availability section was not read. The Springer supplementary files were reachable (see addendum).

### Addendum (coordinator compliance check, 2026-11-17): embryo_57 to embryo_60 labelled "Theiler stage 23"

**Result: none of the four embryos is at or below E13.5. Their ages in the paper are E15.0, E15.25, E15.5 and E15.75.** The window clause says "Anything after E13.5 may be used, provided the source and its stages are stated explicitly with the submission." So these four can be used if the source and stages are disclosed. The result holds whatever Theiler-stage label is attached, because it rests on the paper's own day labels.

Evidence:
- Qiu et al. 2024 Supplementary Table 1 (sheet "Table.1", "Summary of individual embryos"), read from https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-07069-w/MediaObjects/41586_2024_7069_MOESM4_ESM.xlsx (1.9 MB, read locally):
  - embryo_57: RT group E15.0_L2-01; Bin E15.0; somite count "Not counted"; time window E15.0 - E15.75; 215,781 cells; reference "This study".
  - embryo_58: E15.25_L1-01; Bin E15.25; "Not counted"; E15.0 - E15.75; 156,648 cells.
  - embryo_59: E15.5_L2-01; Bin E15.5; "Not counted"; E15.0 - E15.75; 215,284 cells.
  - embryo_60: E15.75_L1-01; Bin E15.75; "Not counted"; E15.0 - E15.75; 239,821 cells.
- The CELLxGENE collection "A single-cell transcriptional timelapse of mouse embryonic development, from gastrula to pup" (https://api.cellxgene.cziscience.com/curation/v1/collections/45d5d2c3-bc28-4814-aed6-0bb6f0e11c82, DOI 10.1038/s41586-024-07069-w) lists donor IDs embryo_1 to embryo_74 (74 distinct) across its datasets. embryo_57 to embryo_60 are therefore in that donor set.

Not verified: the cell-level link from embryo_57 to embryo_60 to the label "Theiler stage 23". The dataset-level labels include TS23, but the donor-to-stage mapping sits in the cell metadata of the H5AD files (or the Census obs). I did not download those, and the Census Python client is not installed. The coordinator's label assignment is taken as given and not checked.

Theiler stages 22 and 23 in this dataset:
- Ontology IDs used in the collection: TS22 = MmusDv:0000029; TS23 = MmusDv:0000032. IDs 0000030 and 0000031 do not appear in these labels; their meaning was not checked.
- Age range for TS22 and TS23 in this dataset: not determinable from accessible sources. Table 1 gives day labels only, with no Theiler column. Not verified.
- External reference points (not this dataset): UNSW Embryology gives E13.5 = TS22 and E14.5 = TS23 ([UNSW](https://embryology.med.unsw.edu.au/embryology/index.php/Mouse_Timeline_Detailed), snippet). EMAP gives TS22 as 14 dpc, range 13.5–15 ([EMAP TS22](https://clynelish.hgu.mrc.ac.uk/emap/ema/theiler_stages/StageDefinition/ts22definition.html), snippet).
- Inconsistency to flag: the four embryos labelled TS23 are E15.0–E15.75 in Table 1. That is later than the UNSW TS23 reference of E14.5. Either this dataset's TS23 label does not follow the UNSW mapping, or labels were assigned differently. The organisers should confirm the Theiler-to-day mapping for this dataset. The compliance result for these four embryos is unchanged, since all their paper ages are after E13.5.
- Practical rule: a cell labelled TS22 in this dataset could come from an embryo at or before E13.5 (UNSW places TS22 at E13.5, and EMAP's range starts at 13.5). Check TS22-labelled cells against the per-embryo day labels, and remove any at or before E13.5.

Other counts (not reconciled): Table 1 lists 99 distinct embryo IDs. The CELLxGENE collection has 74 donor IDs (embryo_1 to embryo_74), the Results give 74 embryos, and the abstract gives 83.

Heart labels: Supplementary Table 5 (sheet "Table.5", 190 cell types) lists "22) Cardiomyocytes" with subtypes: First heart field (Tbx5, Hcn4, Gata4), Second heart field (Isl1, Tbx1), Ventricular cardiomyocytes (Myh7, Myl2, Fhl2), Atrial cardiomyocytes (Nppa, Myl4, Myl7, Tnnt2). It also lists "Endocardial cells" (Tbx20, Cdh11, Npr3, Hand2). Supplementary file MOESM5 (panel_b) tracks a "Cardiomyocytes" trajectory with day labels from E8.5 to P0. Source: the Springer supplementary files above.

Accession, format and size (updated): the CELLxGENE collection links GEO GSE186069 and GSE228590. GSE186069's series matrix (https://ftp.ncbi.nlm.nih.gov/geo/series/GSE186nnn/GSE186069/matrix/GSE186069_series_matrix.txt.gz) is the 2022 E8.5 "bridge" series (sub-series of GSE186070), not the atlas's embryo table. GSE228590's series matrix was not retrieved (403 on that path). CELLxGENE holds the atlas as H5AD: the whole raw-count dataset (dcfd4feb-18a3-4b30-81d7-1b0c544a8ab3) has 11,441,407 cells and is 46.3 GB, the normalized subsets are about 2.86 M cells and about 34 GB, and the cell-cluster subsets range from about 0.2 to 4 GB. None of these were downloaded for this check.

---

## Key Question 5: Cao et al. 2019 MOCA (E9.5–E13.5)

### Takeaway
MOCA is a Nature paper, not Science. Its stages are E9.5 to E13.5. Under the rules only E9.5 exactly is usable. E10.5 and E12.5 are held out, and E11.5 and E13.5 are in the window. MOCA therefore cannot supply late-heart anchors.

### Cited Findings
- Citation: Cao J et al., "The single-cell transcriptional landscape of mammalian organogenesis", Nature 566, 496–502 (2019), published 20 February 2019. [Trapnell lab page](https://cole-trapnell-lab.github.io/papers/cao-spielmann-mouse-embryo) (snippet). Journal confirmed as Nature in search results.
- Accession (snippet): GEO GSE119945; ENA PRJNA490754. [OmicsDI](https://omicsdi.org/dataset/biostudies-literature/S-EPMC6434952) (snippet; GEO page not opened).
- Scale (snippet): about 2 million cells from 61 embryos staged 9.5–13.5 dpc. The data were made available through the MOCA website. [Brotman Baty MOCA news](https://brotmanbaty.org/news/mouse-organogenesis-cell-atlas-moca) (snippet).

### Inferences
- E9.5 exactly: permitted. E10.5 and E12.5: held out for Task 1 and the heart setting. E11.5 and E13.5: in the window.
- Heart annotation, format, size and licence: not verified.

### Gaps
- Heart or cardiomyocyte annotation, file formats and sizes, and the MOCA website were not opened.

---

## Key Question 6: Chen et al. 2022 MOSTA (Stereo-seq)

### Takeaway
MOSTA is a Stereo-seq atlas of sagittal 2D sections. Under the rules, E9.5 exactly, E14.5, E15.5 and E16.5 (with disclosure) are usable. E10.5–E13.5 are excluded. The STOmicsDB page shows no heart label, and format and licence were not captured.

### Cited Findings
- Citation: Chen A et al., Cell 185(10):1777–1792.e21 (2022), DOI 10.1016/j.cell.2022.04.003, PMID 35512705. [STOmicsDB](https://db.cngb.org/stomics/datasets/STDS0000058/) (verified).
- Accession: STOmicsDB STDS0000058; CNGB project CNP0001543. Portal: [MOSTA](https://db.cngb.org/stomics/mosta/) (snippet).
- Platform and content (verified): DNBSEQ-T1; Mus musculus mm10; tissue "Embryo"; 16 samples, 6 sections, 351,014 spots, 28,879 genes; submitted 2021-10-22. No cell count and no stage list on the page. [STOmicsDB](https://db.cngb.org/stomics/datasets/STDS0000058/)
- Stages (snippet, conflicting with the brief): search summary describes sections for E9.5 to E15.5, with four to six sections per stage (E14.5 about 64.1 mm2, E15.5 about 70.8 mm2). No E16.5 was found in my sources, though the brief says E9.5–E16.5. [STOmicsDB](https://db.cngb.org/stomics/datasets/STDS0000058/) and search results.
- Annotation (verified): no cell-type or organ annotation described; only "Embryo". No heart or cardiac label shown. [STOmicsDB](https://db.cngb.org/stomics/datasets/STDS0000058/)
- Terms (verified): "Terms and Conditions," "Data Sharing Policy," and "User notice" are linked, but their text was not captured. No download file list was captured.
- Database citation: Xu Z et al., Nucleic Acids Research 52(D1):1053–1061 (2024), DOI 10.1093/nar/gkad933. [STOmicsDB](https://db.cngb.org/stomics/datasets/STDS0000058/)
- Preprint (snippet): bioRxiv 10.1101/2021.01.17.427004. [bioRxiv](https://www.biorxiv.org/content/10.1101/2021.01.17.427004.full.pdf)

### Inferences
- Allowed under the rules: E9.5 exactly; E14.5, E15.5, E16.5 with disclosure. Excluded: E10.5–E13.5.
- The Task 1 data page says "No spatial coordinates anywhere in Task 1." [Data](https://virtualembryo.ai/challenge/data). MOSTA would need to be aggregated or cell-binned before any Task 1 use.
- Heart cells would have to be identified by region or markers (my inference). No heart label exists in the source.

### Gaps
- Format (h5ad, GEF or other), file sizes, licence text, E16.5 presence, and heart annotation were not verified.

---

## Key Question 7: Early calibration atlases (E6.5–E8.5)

### Takeaway
Early datasets are useful for the early stages but collide with per-task holdouts. E8.5 is blocked for Task 2 heart. E7.5 and E7.75 are blocked for Task 2 embryo. E7.25, E8.0 and E8.75 are bracket stages and are permitted. Pijuan-Sala and Lohoff were not verified in this session. The brief's Imaz-Rosshandler 2024 spatial description does not match what the search found.

### Cited Findings
- **Pijuan-Sala et al., 2019 (E6.5–E8.5)**: UNVERIFIED. Not searched in this session. From memory: Nature 566:490–495 (2019). Stages not checked.
- **Imaz-Rosshandler (brief: "2024, E8–E8.5")**: the search found a 2023 bioRxiv preprint (identifier read from a file name: 10.1101/2023.03.17.532833). It sampled single-cell transcriptomes at 6-hour intervals from E8.5 to E9.5 and combined them with an earlier E6.5–E8.5 atlas to more than 400,000 cells. [Search result](https://storage.prod.researchhub.com/uploads/papers/2025/11/21/2023_E0DAiKm.03.17.532833v2.full.pdf) (snippet). No 2024 Imaz-Rosshandler spatial paper was found.
- **Harland et al. (bioRxiv 2024.12.12.628063)**: "A Spatiotemporal Atlas of Mouse Gastrulation and Early Organogenesis to Explore Axial Patterning and Project In Vitro Models onto In Vivo Space". Preprint: E6.5 and E7.5 embryos, previously published E8.5 spatial data, and an E6.5–E9.5 scRNA-seq atlas, with 88 annotations. Cell Reports (2025) version: E7.25 and E7.5 embryos, 82 annotations. Sources: [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.12.12.628063.full.pdf) (snippet). The brief's "2024" spatial paper is probably this one.
- **Lohoff et al. (seqFISH, E8.5/E8.75, Nature Biotechnology 2022)**: UNVERIFIED. Not searched.

### Inferences (per task, under the rules)
- Pijuan-Sala (from memory; not verified): Task 1 can use every stage up to E8.5. Task 2 heart can use E6.5 to E8.25 and must exclude E8.5. Task 2 embryo can use E6.5, E6.75, E7.0, E7.25 and E8.0, must exclude E7.5 and E7.75, and may use E8.25 by the letter. E8.5 is unresolved for the embryo setting.
- Imaz-Rosshandler (if the preprint's stage list is right): Task 1 can use all of E8.5–E9.5. Task 2 heart can use E8.75–E9.5 and must exclude E8.5. Task 2 embryo: E8.5 unresolved; E8.75–E9.5 allowed by the letter.
- Harland: for the embryo setting, E7.25 is permitted and E7.5 is excluded. For the heart setting, E8.5 spatial data is excluded. For Task 1, all stages up to E9.5 are permitted. Spatial use for Tasks 2 and 3 depends on the data-page question.
- Lohoff (unverified): E8.5 excluded for heart; E8.75 exactly permitted as a bracket stage.

### Gaps
- Pijuan-Sala and Lohoff: stages, accessions, and formats were not verified.
- The 2024 Imaz-Rosshandler spatial paper was not found. The brief may have conflated Imaz-Rosshandler with Harland.
- Accessions and formats for all early datasets were not checked.

---

## Key Question 8: Other whole-embryo, 3D and spatial atlases

### Takeaway
No mouse 3D whole-embryo atlas covering E14.5 or E15.5 was found for 2023–2026. Candidates: MOSTA3D (E9.5 and E11.5, so E9.5 is usable); a June 2025 Cell 3D digital embryo (E7.5–E8.0); the STOmics cardiac Stereo-seq project STT0000062 (stages not seen); and a 2023 Slide-seq whole-embryo paper (stages not seen). Human MERFISH+ is out of scope. Visium and Open-ST were not searched.

### Cited Findings
- MOSTA3D (snippet): bioRxiv 10.1101/2024.08.17.608366, "Three-dimension transcriptomics maps of whole mouse embryo during organogenesis". 3D Stereo-seq at E9.5 and E11.5 only, with an open-access database. [bioRxiv](https://www.biorxiv.org/content/10.1101/2024.08.17.608366.full.pdf)
- Cell, 18 June 2025 (snippet, no URL retrieved): six intact embryos at E7.5, E7.75 and E8.0, sectioned and sequenced to build a single-cell 3D digital embryo.
- STOmics cardiac project STT0000062, "Exploring the Cellular and Molecular Basis of Murine Cardiac Development through Spatiotemporal Transcriptome Sequencing" (snippet; stages not in snippet). [STOmics](https://db.cngb.org/stomics/project/STT0000062)
- Nature Genetics 2023 (s41588-023-01435-6), Slide-seq maps of whole embryos during early organogenesis (snippet; authors and stages not confirmed). [Nature Genetics](https://www.nature.com/articles/s41588-023-01435-6.pdf)
- MERFISH+ (bioRxiv 10.1101/2025.11.02.686137) is a human 12-post-conceptual-week heart atlas. [bioRxiv](https://www.biorxiv.org/content/10.1101/2025.11.02.686137.full.pdf). Out of scope (not mouse).
- The challenge's own Virtual Embryo atlas (virtualembryo.ai) spans the same window as the benchmark and is browsable. Held-out rules apply to it. [Data](https://virtualembryo.ai/challenge/data)

### Inferences
- MOSTA3D: E9.5 usable; E11.5 excluded.
- June 2025 Cell 3D embryo: E7.5 and E7.75 excluded for the embryo setting; E8.0 usable.
- STT0000062: usable only if its stages are at or before E9.5, or after E13.5. Stages in E10–E13.5 are excluded.

### Gaps
- No mouse MERFISH whole-embryo 3D atlas at E14.5, E15.5 or E18.5 was found.
- Visium whole-embryo and Open-ST were not searched.
- Stages, formats, and accessions for STT0000062 and the Slide-seq paper were not verified.

---

## Key Question 9: Theiler stage and somite-count mapping

### Takeaway
TS22 straddles the window edge: about E13.5 (UNSW) or 13.5–15 dpc (EMAP). TS23 is about E14.5. Somite counts near 24–26 sit at the E9.5 edge. The rules place such fractional stages on the E-scale and judge them by the same boundary. Ambiguous labels should be excluded or cleared with the organisers.

### Cited Findings
- EMAP TS22 (snippet): "14 dpc (range 13.5-15) 56-~60 somite pairs". EMAP also says somite number is "a loose guide after TS12". [EMAP TS22](https://clynelish.hgu.mrc.ac.uk/emap/ema/theiler_stages/StageDefinition/ts22definition.html)
- UNSW Embryology wiki (snippet): E13.5 is TS22; E14.5 is TS23. [UNSW](https://embryology.med.unsw.edu.au/embryology/index.php/Mouse_Timeline_Detailed)
- Qiu 2024 (verified): 24–26 somites to about E9.5. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10901739/)

### Inferences
- A TS22 dataset is excluded if its embryos are at or before E13.5. It is usable with disclosure only if documented embryo age is above E13.5.
- TS23 (about E14.5) is usable with disclosure.
- Somite-staged embryos at the edge of E9.5 should be excluded or cleared with the organisers.

### Gaps
- The organisers' placement of TS22 is not stated. The EMAP range makes the mapping approximate.

---

## Key Question 10: Catalogue summary

| Dataset | Citation | Accession | Stages | Assay, cells | Heart labels | Format, size, licence | Verification | Allowed under the rules |
|---|---|---|---|---|---|---|---|---|
| Qiu et al. 2024 | Nature 626:1084–1093 | Not found (GEO/ENA unverified) | E8 to P0; 6-h bins; somite-staged to about E10 | sci-RNA-seq3; 11.4–12.4 M nuclei; 74–83 embryos (paper conflict) | "cardiac (proepicardium)" seen; cardiomyocyte not confirmed | Not verified | PMC (partial) | Task 1 and heart: at or before E9.5 (somite edge about 24–26); after E13.5 with disclosure; remove E10–E13.5 |
| Cao et al. 2019 (MOCA) | Nature 566:496–502 | GEO GSE119945; ENA PRJNA490754 (snippet) | E9.5–E13.5 | scRNA-seq; about 2 M cells, 61 embryos (snippet) | Not verified | Not verified | Snippet | E9.5 exactly only |
| Chen et al. 2022 (MOSTA) | Cell 185:1777–1792 | STOmicsDB STDS0000058; CNGB CNP0001543 | E9.5–E16.5 per brief (snippet: E9.5–E15.5) | Stereo-seq; 16 samples, 6 sections, 351,014 spots | None seen (tissue "Embryo") | Not captured; terms not read | STOmicsDB (partial) | E9.5; E14.5, E15.5, E16.5 with disclosure; not E10.5–E13.5 |
| MOSTA3D (bioRxiv 2024.08.17.608366) | Preprint | Open database (ID not seen) | E9.5, E11.5 | 3D Stereo-seq | Not verified | Not verified | Snippet | E9.5 only |
| Harland et al. (bioRxiv 2024.12.12.628063; Cell Rep 2025) | Preprint and Cell Reports | Not verified | E6.5, E7.25, E7.5 embryos; E8.5 spatial; E6.5–E9.5 scRNA | Spatial and scRNA-seq; 82–88 annotations | Not verified | Not verified | Snippet | Embryo: E6.5, E7.25 allowed, E7.5 excluded. Heart: E8.5 excluded. Task 1: up to E9.5 |
| Imaz-Rosshandler (bioRxiv 10.1101/2023.03.17.532833) | Preprint (2023) | Not verified | E8.5–E9.5 at 6-h intervals; combined with E6.5–E8.5 atlas | scRNA-seq; more than 400,000 cells combined | Not verified | Not verified | Snippet | Task 1: all. Heart: E8.5 excluded |
| Pijuan-Sala et al. 2019 | Nature 566:490–495 (memory) | Not verified | E6.5–E8.5 (memory) | scRNA-seq | Not verified | Not verified | Unverified | See Key Question 7 |
| Lohoff et al. 2022 (seqFISH) | Nat Biotechnol (memory) | Not verified | E8.5, E8.75 (brief) | seqFISH spatial | Not verified | Not verified | Unverified | Heart: E8.5 excluded; E8.75 bracket stage |
| Cell 2025, 3D digital embryo | Cell, June 2025 | Not found | E7.5, E7.75, E8.0 | Sectioned and sequenced, six embryos | Not verified | Not verified | Snippet, no URL | Embryo: E7.5 and E7.75 excluded; E8.0 allowed |
| STOmics cardiac Stereo-seq (STT0000062) | STOmics project | STT0000062 | Not seen | Stereo-seq | Cardiac focus | Not verified | Snippet | Unknown; check stages |
| Slide-seq whole embryo (Nat Genet 2023, s41588-023-01435-6) | Nature Genetics 2023 | Not found | Not seen | Slide-seq, 10 µm | Not verified | Not verified | Snippet | Unknown; check stages |
| MERFISH+ human heart (bioRxiv 2025.11.02.686137) | bioRxiv 2025 | — | Human 12 PCW | — | — | — | Snippet | Out of scope (human) |

---

## Next steps
1. Read the Qiu data-availability section (PMC, offset 100000) to get accession, format, size and any cardiomyocyte label.
2. Check MOSTA's data tab and terms, and confirm E16.5 presence and any heart annotation.
3. Ask the organisers the seven questions in Key Question 2, Gaps, before using any Tasks 2 or 3 external data or any Task 1 data within the window.
4. Verify Pijuan-Sala, Lohoff, STT0000062 and the Slide-seq paper if they are to be used.
