"""Frozen dispatcher (do not edit). Each board's code lives in <board>.py and its private <board>_*.py helpers."""
import temporal
import heart
import embryo
import perturbation

_FN = {'temporal': temporal.predict_temporal, 'heart': heart.predict_heart,
       'embryo': embryo.predict_embryo, 'perturbation': perturbation.predict_perturbation}


def predict(board, inputs, times, target_time, context):
    return _FN[board](inputs, times, target_time, context)
