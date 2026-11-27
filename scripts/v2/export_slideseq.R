# Export raw counts, bead metadata and 2D coordinates from a GSE282547 Slide-seq Seurat object, without Seurat.
# Usage: R_LIBS_USER=/scratch/user/Rlib Rscript export_slideseq.R in.rds out_prefix
suppressMessages({library(SeuratObject); library(Matrix)})
a <- commandArgs(TRUE); x <- readRDS(a[1]); o <- a[2]
an <- names(x@assays); cat("assays:", an, "\n")
s <- x@assays[[intersect(c("Spatial", "RNA", "originalexp", an[an != "SCT"]), an)[1]]]
m <- if (inherits(s, "Assay5")) LayerData(s, layer = "counts") else s@counts
writeMM(m, paste0(o, "_counts.mtx")); writeLines(rownames(m), paste0(o, "_genes.txt")); writeLines(colnames(m), paste0(o, "_beads.txt"))
meta <- x@meta.data; write.csv(meta, paste0(o, "_meta.csv"))
im <- x@images
for (n in names(im)) {
  co <- attr(im[[n]], "coordinates")
  if (is.null(co)) { b <- attr(im[[n]], "boundaries"); co <- attr(b[[1]], "coords"); rownames(co) <- attr(b[[1]], "cells") }
  write.csv(as.data.frame(co), paste0(o, "_coords_", n, ".csv"))
}
cat("exported", dim(m), "images:", names(im), "meta cols:", colnames(meta), "\n")
