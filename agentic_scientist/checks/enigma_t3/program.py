from perturbation import predict_perturbation


def predict(board, inputs, times, target_time, context):
    if board != "perturbation":
        raise ValueError(board)
    return predict_perturbation(inputs, times, target_time, context)
