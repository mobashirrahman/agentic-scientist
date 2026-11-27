"""Empirical heart anchor from the first historical-entry submission."""
from src.models import TemporalTransport


def predict_heart(inputs, times, target_time, context):
    anchor = TemporalTransport(*inputs[-2:], interval=times[-1] - times[-2])
    return anchor.predict(target_time - times[-1], n=context['n'], seed=context['seed'],
                          state=0, composition=0, geometry=0)
