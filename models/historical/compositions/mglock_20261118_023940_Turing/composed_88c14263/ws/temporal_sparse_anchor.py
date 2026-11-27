"""Sparse realisation of the weak expression created by the external-anchor drift.

Rationale
---------
AnchorFlow adds a per-gene, per-lineage drift to the sampled donor profiles in
log space.  Where the donor cell had no molecule for a gene, the drift turns the
zero into a small positive value (approximately 0.98 of these additions are
below 0.1 log units, and together they carry only 0.4% of the linear
expression mass, yet they account for ~48% of all nonzeros).  A real
single-nucleus profile is a sparse stochastic observation of a biological
state: a lineage mean of e.g. 0.05 log units is realised as molecule counts in
a *subset* of nuclei, not as an identical fractional measurement in every
nucleus.  Spreading the mean over all cells therefore inflates the number of
detected genes per cell (Endocardium: 4,141 donor vs 12,842 output detected
genes) and flattens the gene-gene covariation that the variogram scores.

This module only re-realises that artificially created weak component:

For each output lineage and gene, take the entries E where the *donor* cell had
zero, the parent output is positive but below
    q = min(0.5, median over sampled donor rows of the smallest positive
            log expression in that row)
(0.5 is the existing anchor bound; the row minimum is an input-derived
"one-observed-molecule" log level).  Let S = sum(E) and
k = min(|E|, ceil(S/q)).  Zero E, and place S/k on k chosen positions without
replacement.  The per-lineage/gene log-expression budget is therefore conserved
exactly (before library renormalisation), allocated values never exceed q, and
donor-positive entries plus created entries at or above q are untouched.
Row-wise CP10k ``normalize_log`` on the changed rows then restores library size,
which makes the pseudobulk conservation approximate only.

Recipient law (state-conditioned realisation)
---------------------------------------------
Which nuclei carry the realised weak signal is itself observable information.
The detection pattern of a gene is autocorrelated in the *input* latent state
space: nuclei whose latent neighbours detect a gene are more likely to detect
it themselves (Poisson / dropout sampling of a shared state).  Uniform
recipients ignore that, so the realised nonzeros are spread over nuclei that
are less state-compatible than a real observation would be, which leaves the
gene-pair co-detection structure (and hence the variogram) slightly too flat.

For each lineage block with enough latest-stage cells, we therefore place the
weak entries preferentially in nuclei whose latest-stage latent neighbours
(``embedding``) detect the gene.  Per gene g in the block:

    pi_g      = detection frequency of g over the lineage's latest cells
    r_ig      = fraction of donor i's 30 nearest other lineage cells detecting g
    w_ig      = clip( (0.5*pi_g + 0.5*r_ig) / pi_g , 0.5, 2 )   on the eligible rows
    chosen    ~ categorical(w / sum(w)),  k rows without replacement

The 0.5 shrink toward ``pi_g`` and the [0.5, 2] bounds keep the placement a
bounded, half-shrunk reweighting of the existing uniform law: no expression mass
is created, S and k are unchanged, and the uniform draw is still made on the
parent stream first (so the parent stays bit-identical whenever the embedding is
absent, and unchanged genes fall back exactly).  The program passes the flow's
own latest-input latent coordinates (``flow.zb``) as ``embedding``; it is an
input-derived observation model, recomputed from whatever latest WT stage is
given, with no time or split branching and no added extrapolation.

Empirical hurdle amplitude (detection / positive-amplitude factorisation)
-------------------------------------------------------------------------
The operator above replaces millions of tiny artificial positives with sparse
entries, but draws their magnitude from a single lineage quantum q <= 0.5.
That conflates two separately observable properties of an expressed gene: the
*detection probability* and the *conditional positive amplitude*.  A two-part
(hurdle) observation law keeps them apart (Finak et al., Genome Biol 2015;
Sun et al., Genome Biol 2021 treat means, zero proportions and correlations as
distinct properties).

For every lineage we therefore learn, from the latest supplied stage's own
cells of that lineage, the empirical positive amplitude

    u[c,g] = mean(log1p(CP10k) | expression > 0, lineage = c)

requiring at least MIN_POSITIVE_CELLS positive observations.  Supported genes
take a[c,g] = max(q, min(u[c,g], AMP_CEILING)); unsupported genes keep the
exact parent amplitude q.  The eligible weak component of a supported gene with
budget S is then emitted in k1 = min(k0, max(1, ceil(S/a))) cells at S/k1
instead of k0 cells at S/k0.  The per-lineage/gene log budget S is unchanged;
only the number of carriers shrinks, so the marginal law moves toward fewer
detections at empirical positive amplitudes (the biological premise: zeros are
often finite-molecule sampling, not absence of the program).

Recipient ordering stays the parent's state-conditioned weighted draw: the k0
draws (both RNG streams) are made exactly as before, in the original gene
order, and the first k1 entries of that list are used.  No new RNG call, no
re-shuffle, so an unsupported gene is bit-identical to the parent.

This is an empirical observation model, not a transcriptional-burst model or an
exact count likelihood.  No tunable strength: q, k, the neighbour count, the
shrinkage, the bounds, MIN_POSITIVE_CELLS and AMP_CEILING are fixed a priori
(the pre-registered values), and all statistics are derived from the passed
inputs.
"""
import numpy as np
from scipy import sparse
from sklearn.neighbors import NearestNeighbors

from temporal_transport import lineages, normalize_log

ANCHOR_BOUND = 0.5      # existing clip bound used by AnchorFlow
MIN_LINEAGE_CELLS = 50  # kNN support guard: pre-registered, not tuned
N_NEIGHBOURS = 31       # query cell + 30 other cells, pre-registered
WEIGHT_SHRINK = 0.5     # half-shrinkage of r_ig toward pi_g, pre-registered
WEIGHT_LO, WEIGHT_HI = 0.5, 2.0  # pre-registered bound on the weight
MIN_POSITIVE_CELLS = 10         # support rule for the empirical amplitude, pre-registered
AMPLITUDE_CEILING = 2.0         # a priori cap in log1p(CP10k) units, pre-registered


def _donor_one_molecule(donor_block):
    """Smallest positive log expression per donor row (NaN for empty rows)."""
    out = np.full(donor_block.shape[0], np.nan, dtype=np.float64)
    d = sparse.csr_matrix(donor_block)
    for i in range(d.shape[0]):
        seg = d.data[d.indptr[i]:d.indptr[i + 1]]
        if seg.size:
            out[i] = float(seg.min())
    return out


def _valid_embedding(embedding, latest):
    """Return a finite (latest.n_obs x d) float array, or None (uniform fallback)."""
    if embedding is None:
        return None
    emb = np.asarray(embedding, dtype=np.float64)
    if emb.ndim != 2 or emb.shape[0] != latest.n_obs or emb.shape[1] < 2:
        return None
    if not np.all(np.isfinite(emb)):
        return None
    return emb


def _recipient_model(emb, latest_labels, detect, label, block_donors, genes):
    """Neighbour/state statistics for one operator lineage block.

    Returns ``(inv, R, pi)`` where ``inv`` maps each output row of the block to a
    row of ``R`` (one row per distinct donor), ``R[i, a]`` is the neighbour
    detection rate of ``genes[a]`` for donor ``i`` and ``pi[a]`` the lineage-wide
    detection frequency, or ``None`` when the lineage is not supported.
    """
    lin = np.flatnonzero(latest_labels == label)          # latest cells of this lineage
    if lin.size < MIN_LINEAGE_CELLS:
        return None
    k_nb = min(N_NEIGHBOURS, lin.size)
    index = NearestNeighbors(n_neighbors=k_nb).fit(emb[lin])
    donors, inv = np.unique(block_donors, return_inverse=True)
    _, nbr_local = index.kneighbors(emb[donors], n_neighbors=k_nb)
    # Average detection over each donor's neighbours, self excluded.  A sparse
    # (donors x lineage-cells) indicator matrix does the averaging for all genes
    # at once.
    agg = sparse.lil_matrix((donors.size, lin.size), dtype=np.float64)
    for a in range(donors.size):
        nb = nbr_local[a]
        nb = nb[lin[nb] != donors[a]]
        if nb.size:
            agg[a, nb] = 1.0 / nb.size
    agg = agg.tocsr()
    det_lin = detect[lin][:, genes].astype(np.float32)
    pi = np.asarray(det_lin.mean(0), dtype=np.float64).ravel()
    R = np.empty((donors.size, genes.size), dtype=np.float32)
    step = 2048
    for s in range(0, genes.size, step):
        dense = det_lin[:, s:s + step].toarray().astype(np.float32)
        R[:, s:s + step] = agg @ dense
    return inv, R, pi


def _positive_amplitude(donor_lin, det_lin, donor_cols):
    """Empirical conditional-positive amplitude per gene for one lineage.

    ``u[c, g] = mean(log1p(CP10k) | expression > 0)`` over ALL latest-stage
    cells of lineage ``c``, obtained from two sparse moments (one pass over the
    lineage's cells).  Returns ``(counts, means)`` aligned with
    ``donor_cols``; ``means`` is NaN where the support rule fails, which makes
    those genes keep the parent amplitude exactly.
    """
    counts = np.asarray(det_lin[:, donor_cols].sum(0),
                        dtype=np.float64).ravel()
    sums = np.asarray(donor_lin[:, donor_cols].sum(0),
                      dtype=np.float64).ravel()
    means = np.full(counts.shape, np.nan, dtype=np.float64)
    ok = counts >= MIN_POSITIVE_CELLS
    means[ok] = sums[ok] / counts[ok]
    return counts, means


def realise_sparse_anchor(out, latest, seed, embedding=None):
    """Re-realise the weak created entries of ``out`` (an AnchorFlow prediction).

    ``out`` is modified in place (``out.X`` replaced by a CSR matrix) and
    returned.  ``latest`` is the newest input stage, whose empirical profiles
    are the donors of ``out`` (``out.obs['source_row']``).  Only lineage blocks
    are materialised densely, never the whole 3000 x ~32k matrix twice.

    ``embedding`` (optional ``latest.n_obs x d`` latent coordinates of the
    latest input, i.e. ``flow.zb``) conditions the recipient law described in
    the module docstring.  ``None``, a mis-shaped or a non-finite embedding
    reproduces the parent uniform law bit-for-bit.
    """
    if not sparse.issparse(out.X):
        out.X = sparse.csr_matrix(out.X)
    # Align the donor matrix to the output gene order (normally identical).
    pos = {g: i for i, g in enumerate(latest.var_names)}
    gene_cols = np.array([pos[g] for g in out.var_names if g in pos], dtype=int)
    out_cols = np.array([i for i, g in enumerate(out.var_names) if g in pos], dtype=int)
    donor_all = sparse.csr_matrix(latest.X)[:, gene_cols]
    detect = (donor_all > 0).tocsr()  # binary detection, aligned to out columns
    # Map an output gene column to its column in the aligned donor matrix.
    col_of_out = np.full(out.n_vars, -1, dtype=int)
    col_of_out[out_cols] = np.arange(out_cols.size)

    source_row = np.asarray(out.obs['source_row'].to_numpy())
    latest_labels = lineages(latest)
    labels = latest_labels[source_row]

    emb = _valid_embedding(embedding, latest)

    # Separate deterministic stream; independent of the flow's sampling RNG.
    # The parent's uniform draw is always taken on this stream first, in the
    # original gene order, so an abstention is bit-identical and later genes
    # keep the parent's draws.
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 12345]))
    rng_w = np.random.default_rng(np.random.SeedSequence([int(seed), 23456]))
    x = sparse.csr_matrix(out.X, dtype=np.float32)

    n_weighted = 0
    n_fallback = 0
    n_supported = 0
    enrich_sum = 0.0   # mean over weighted genes of mean_{chosen} r/pi
    base_sum = 0.0     # same weighted genes, mean_{eligible} r/pi (uniform baseline)
    n_enrich = 0
    max_budget_error = 0.0
    # Empirical-hurdle diagnostics (flat, data-derived; no control flow).
    n_amp_supported = 0    # genes that used a learned positive amplitude
    n_amp_unsupported = 0  # genes that kept the parent quantum q
    n_amp_reduced = 0      # supported genes whose carrier count actually shrank
    k0_total = 0
    k1_total = 0
    elig_total = 0
    emit_before_total = 0
    emit_after_total = 0
    amps = []              # a[q,c,g] actually used (supported genes)
    created_sum = 0.0      # sum of the realised per-entry amplitude S/k1
    per_lineage = {}       # sanitized lineage -> emitted/eligible carrier ratio

    for label in np.unique(labels):
        rows = np.flatnonzero(labels == label)
        if rows.size == 0:
            continue
        lin_snapshot = emit_before_total
        donor = donor_all[source_row[rows]]
        one = _donor_one_molecule(donor)
        one = one[np.isfinite(one)]
        if one.size == 0:
            continue
        q = float(min(ANCHOR_BOUND, np.median(one)))
        if not np.isfinite(q) or q <= 0:
            continue

        dens = x[rows].toarray()
        dens_donor = donor.toarray()
        eligible_mask = (dens_donor == 0) & (dens > 0) & (dens < q)
        genes = np.flatnonzero(eligible_mask.any(0))
        if genes.size == 0:
            continue

        # Empirical hurdle amplitude for this lineage, learned from ALL latest
        # cells of the lineage (not only the sampled donors): a gene's positive
        # amplitude is an observation-law property of the lineage, so every
        # available nucleus informs it.  Unsupported genes get NaN -> parent q.
        lin_rows = np.flatnonzero(latest_labels == label)
        amp = np.full(genes.size, np.nan, dtype=np.float64)
        if lin_rows.size:
            dcols = col_of_out[genes]
            keep = dcols >= 0
            if keep.any():
                _, means = _positive_amplitude(donor_all[lin_rows],
                                               detect[lin_rows], dcols[keep])
                amp[keep] = means

        # State-conditioned recipient statistics for this operator lineage block
        # (grouped exactly like the sparse realisation: lineages(latest)[source_row]).
        model = (_recipient_model(emb, latest_labels, detect, label,
                                  source_row[rows], genes)
                 if emb is not None else None)
        if model is not None:
            inv, R, pi = model
            n_supported += 1

        for a, j in enumerate(genes):
            elig = np.flatnonzero(eligible_mask[:, j])
            total = float(dens[elig, j].sum(dtype=np.float64))
            if total <= 0:
                continue
            k0 = min(elig.size, max(1, int(np.ceil(total / q))))
            # Parent uniform draw: always made, on the parent stream, in the
            # parent's gene order.  Used as the result for fallback genes.
            chosen_u = rng.choice(elig, k0, replace=False)
            chosen = chosen_u
            if model is not None and pi[a] > 0:
                r = np.asarray(R[inv[elig], a], dtype=np.float64)
                w = (WEIGHT_SHRINK * pi[a] + (1.0 - WEIGHT_SHRINK) * r) / pi[a]
                w = np.clip(w, WEIGHT_LO, WEIGHT_HI)
                if np.ptp(w) > 1e-12:
                    chosen = rng_w.choice(elig, k0, replace=False, p=w / w.sum())
                    n_weighted += 1
                    at = np.searchsorted(elig, chosen)
                    enrich_sum += float(np.mean(r[at] / pi[a]))
                    base_sum += float(np.mean(r / pi[a]))
                    n_enrich += 1
                else:
                    n_fallback += 1
            else:
                n_fallback += 1
            # Empirical hurdle amplitude: supported genes emit the same log
            # budget S over fewer carriers at an empirical positive amplitude,
            # keeping the first k1 entries of the already drawn recipient list
            # (both RNG streams above are untouched, so unsupported genes and
            # all later genes keep the parent's draws).
            k = k0
            u = amp[a]
            if np.isfinite(u) and u > 0:
                a_amp = max(q, min(float(u), AMPLITUDE_CEILING))
                k1 = min(k0, max(1, int(np.ceil(total / a_amp))))
                k = k1
                n_amp_supported += 1
                amps.append(a_amp)
                created_sum += float(total / k1)
                if k1 < k0:
                    chosen = chosen[:k1]
                    n_amp_reduced += 1
            else:
                n_amp_unsupported += 1
            dens[elig, j] = 0.0
            dens[chosen, j] = total / k
            k0_total += k0
            k1_total += k
            elig_total += elig.size
            emit_before_total += k0
            emit_after_total += k
            # Budget is conserved before library renormalisation by construction;
            # report the worst floating-point deviation as a guard.
            err = abs(float(dens[elig, j].sum(dtype=np.float64)) - total)
            if err > max_budget_error:
                max_budget_error = err

        # CP10k restoration is row-wise, so doing it per lineage block is
        # identical to doing it once on the full matrix.  Only rows whose
        # nonzeros actually changed are renormalised, leaving all other rows
        # bit-identical to the parent prediction.
        changed = np.flatnonzero(eligible_mask.any(1))
        if changed.size:
            dens[changed] = normalize_log(dens[changed]).toarray()
        x[rows] = sparse.csr_matrix(dens)
        # Per-lineage carrier reduction (diagnostic only, data-derived key).
        lin_before = emit_before_total - lin_snapshot
        lin_after = emit_after_total - lin_snapshot
        if lin_before > 0:
            safe = ''.join(ch if ch.isalnum() else '_' for ch in str(label))
            per_lineage[safe] = float(lin_after / lin_before)

    out.X = x.tocsr()
    # Flat scalar diagnostics only (h5ad uns cannot store nested structures).
    out.uns['sparse_anchor'] = dict(
        embedding_used=float(emb is not None),
        n_latent_dims=float(emb.shape[1] if emb is not None else 0),
        n_supported_lineages=int(n_supported),
        n_weighted_genes=int(n_weighted),
        n_fallback_genes=int(n_fallback),
        mean_recipient_r_over_pi=float(enrich_sum / n_enrich) if n_enrich else 0.0,
        mean_uniform_r_over_pi=float(base_sum / n_enrich) if n_enrich else 0.0,
        recipient_enrichment_ratio=(float(enrich_sum / base_sum) if base_sum > 0 else 0.0),
        max_budget_error=float(max_budget_error),
        # Empirical-hurdle audit (pre-normalisation log budget is conserved by
        # construction; CP10k restoration makes it approximate afterwards).
        n_hurdle_genes=int(n_amp_supported),
        n_quantum_genes=int(n_amp_unsupported),
        n_reduced_genes=int(n_amp_reduced),
        k0_total=int(k0_total),
        k1_total=int(k1_total),
        eligible_entries_total=int(elig_total),
        emitted_entries_total=int(emit_after_total),
        carrier_reduction=float(1.0 - emit_after_total / emit_before_total)
        if emit_before_total > 0 else 0.0,
        amplitude_q10=float(np.quantile(amps, 0.10)) if amps else 0.0,
        amplitude_q50=float(np.quantile(amps, 0.50)) if amps else 0.0,
        amplitude_q90=float(np.quantile(amps, 0.90)) if amps else 0.0,
        created_amplitude_mean=(created_sum / n_amp_supported) if n_amp_supported else 0.0,
    )
    # Per-lineage emitted/eligible carrier ratios, flat scalar keys.
    out.uns['sparse_anchor_hurdle_lineage'] = per_lineage
    return out
