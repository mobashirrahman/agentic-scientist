"""Use upstream scGPT model and collation in the existing native Torch environment."""
import importlib
import json
import logging
from pathlib import Path
import re
import sys
from types import ModuleType

import numpy as np
import torch


def upstream(source):
    source = Path(source).resolve()
    # Load just the unchanged model and preprocessing sources. The package's
    # training entry point imports torchtext, which is unnecessary for this probe.
    package = ModuleType('scgpt')
    package.__path__ = [str(source / 'scgpt')]
    package.logger = logging.getLogger('scgpt')
    if 'scgpt' in sys.modules:
        raise RuntimeError('Start the frozen probe in a fresh process')
    sys.modules['scgpt'] = package
    model = importlib.import_module('scgpt.model.model').TransformerModel
    collator = importlib.import_module('scgpt.data_collator').DataCollator
    return model, collator


def native_weights(checkpoint):
    pattern = re.compile(r'self_attn\.(?:_impl\.)?Wqkv\.|self_attn\._impl\.out_proj\.')
    return {pattern.sub(lambda m: 'self_attn.in_proj_' if 'Wqkv' in m[0] else 'self_attn.out_proj.', key): value
            for key, value in checkpoint.items()}


def encode_cells(x, model, vocab, gene_ids, collate, conf, device, seed):
    np.random.seed(seed)
    batch_size = 16
    batches = []
    for start in range(0, len(x), batch_size):
        examples = []
        for row in x[start:start + batch_size]:
            keep = np.flatnonzero(row)
            ids = np.r_[vocab['<cls>'], gene_ids[keep]]
            values = np.r_[conf['pad_value'], row[keep]]
            examples.append({'genes': torch.as_tensor(ids, dtype=torch.long),
                             'expressions': torch.as_tensor(values, dtype=torch.float32)})
        batch = collate(examples)
        ids = batch['gene'].to(device)
        with torch.inference_mode():
            state = model._encode(ids, batch['expr'].to(device), ids == vocab[conf['pad_token']])
            batches.append(state[:, 0].cpu().numpy())
    return np.concatenate(batches, axis=0)


def scgpt_embeddings(x, human_genes, model_dir, device, source, seed=42):
    model_type, collator_type = upstream(source)
    vocab = json.loads((model_dir / 'vocab.json').read_text())
    conf = json.loads((model_dir / 'args.json').read_text())
    for token in ('<pad>', '<cls>', '<eoc>'):
        if token not in vocab:
            vocab[token] = len(vocab)
    ids = np.asarray([vocab[gene] for gene in human_genes], dtype=np.int64)
    torch.manual_seed(seed)
    # Disable the nested-tensor fast path in native PyTorch. It diverges from
    # upstream Flash Attention's padding behavior on this inference workload.
    torch.backends.mha.set_fastpath_enabled(False)
    model = model_type(ntoken=len(vocab), d_model=conf['embsize'], nhead=conf['nheads'],
                       d_hid=conf['d_hid'], nlayers=conf['nlayers'], nlayers_cls=conf['n_layers_cls'],
                       n_cls=1, vocab=vocab, dropout=conf['dropout'], pad_token=conf['pad_token'],
                       pad_value=conf['pad_value'], do_mvc=True, use_fast_transformer=False).to(device).eval()
    collate = collator_type(do_padding=True, pad_token_id=vocab[conf['pad_token']], pad_value=conf['pad_value'],
                            do_mlm=False, do_binning=True, max_length=512, sampling=True, keep_first_n_tokens=1)
    random = encode_cells(x, model, vocab, ids, collate, conf, device, seed)
    weights = native_weights(torch.load(model_dir / 'best_model.pt', map_location='cpu', weights_only=True))
    keys = ('encoder.', 'value_encoder.', 'transformer_encoder.')
    required = {name: value.shape for name, value in model.state_dict().items() if name.startswith(keys)}
    missing = sorted(name for name, shape in required.items() if name not in weights or weights[name].shape != shape)
    if missing:
        raise RuntimeError(f'Checkpoint does not cover {len(missing)} encoder parameters: {missing[:8]}')
    model.load_state_dict({name: weights[name] for name in required}, strict=False)
    frozen = encode_cells(x, model, vocab, ids, collate, conf, device, seed)
    return frozen, random, len(required)
