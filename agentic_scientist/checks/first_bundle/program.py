"""Replay the methods recorded in the first submission manifest."""
from src.models import TemporalTransport, interpolate, lineage_perturbation


def predict(board, inputs, times, target_time, context):
    seed, n = context['seed'], context['n']
    if board == 'temporal':
        return TemporalTransport(*inputs[-2:], interval=times[-1] - times[-2]).predict(
            target_time - times[-1], seed=seed, n=n, state=0, composition=0.5)
    if board == 'embryo':
        fraction = (target_time - times[0]) / (times[-1] - times[0])
        return interpolate(*inputs, fraction, seed=seed, n=n)
    if board == 'perturbation':
        return lineage_perturbation(inputs[-1], target='bcatenin', seed=seed, n=n,
                                    strength=0, depletion=0)
    return TemporalTransport(*inputs[-2:], interval=times[-1] - times[-2]).predict(
        target_time - times[-1], seed=seed, n=n, state=0, composition=0)
