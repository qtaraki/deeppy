import numpy as np
import cudarray as ca
from ..base import ParamMixin


def approx_fprime(xk, f, epsilon, *args):
    # Slightly modified version of scipy.optimize.approx_fprime()
    f0 = f(*((xk,) + args))
    grad = np.zeros((len(xk),), ca.float_)
    ei = np.zeros((len(xk),), ca.float_)
    for k in range(len(xk)):
        ei[k] = 1.0
        d = epsilon * ei
        grad[k] = (f(*((xk + d,) + args)) - f0) / d[k]
        ei[k] = 0.0
    return grad


def check_grad(func, grad, x0, eps, *args):
    # Slightly modified version of scipy.optimize.check_grad()
    return np.sqrt(np.mean((grad(x0, *args) -
                            approx_fprime(x0, func, eps, *args))**2))


def check_bprop(layer, x0, eps=None, random_seed=123456):
    # The code below is a bit nasty - we need to handle float32 and float64
    # depending on the cudarray back-end.
    if eps is None:
        eps = np.sqrt(np.finfo(ca.float_).eps)
    x_shape = x0.shape
    layer._setup(x_shape)

    # Check bprop to input
    def func(x):
        ca.random.seed(random_seed)
        x = ca.array(np.reshape(x, x_shape))
        out = layer.fprop(ca.array(x), 'train')
        y = ca.sum(out)
        return np.array(y)

    def grad(x):
        ca.random.seed(random_seed)
        x = ca.array(np.reshape(x, x_shape))
        out = layer.fprop(ca.array(x), 'train')
        y_grad = ca.ones_like(out, dtype=np.float32)
        x_grad = layer.bprop(y_grad)
        return np.ravel(np.array(x_grad))

    err = check_grad(func, grad, np.ravel(x0), eps)
    print('%s_input: %.2e' % (layer.name, err))

    # Check bprop to parameters
    if isinstance(layer, ParamMixin):
        def func(x, *args):
            ca.random.seed(random_seed)
            p_idx = args[0]
            param_vals = layer._params[p_idx].array
            param_vals *= 0
            param_vals += ca.array(np.reshape(x, param_vals.shape))
            out = layer.fprop(ca.array(x0), 'train')
            y = ca.sum(out)
            return np.array(y)

        def grad(x, *args):
            ca.random.seed(random_seed)
            p_idx = args[0]
            param_vals = layer._params[p_idx].array
            param_vals *= 0
            param_vals += ca.array(np.reshape(x, param_vals.shape))
            out = layer.fprop(ca.array(x0), 'train')
            y_grad = ca.ones_like(out, dtype=np.float32)
            layer.bprop(y_grad)
            param_grad = layer._params[p_idx].grad()
            return np.ravel(np.array(param_grad))

        for p_idx, p in enumerate(layer._params):
            args = p_idx
            x = np.array(layer._params[p_idx].array)
            err = check_grad(func, grad, np.ravel(x), eps, args)
            print('%s: %.2e' % (p.name, err))
