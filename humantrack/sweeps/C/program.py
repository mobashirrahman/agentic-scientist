"""Human-track T1 workspace: only the temporal board is implemented."""
import temporal


def predict(board, inputs, times, target_time, context):
    assert board == 'temporal', board
    return temporal.predict_temporal(inputs, times, target_time, context)
