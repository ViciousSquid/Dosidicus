"""
Optional NPU / AI Accelerator support via ONNX Runtime
===========================================================================

A thin abstraction over the core matrix operations used by the
brain engine (forward pass MatMul, Hebbian outer-product update, zeros
initialisation) so that an ONNX Runtime execution provider can be dropped
in without touching the rest of the codebase.

Backend selection
-----------------
Set  [Compute] backend = onnx  in config.ini to enable ONNX.
Leave as  backend = numpy  (or omit the section entirely) for the default
NumPy path.  ONNX silently falls back to NumPy if onnxruntime is not
installed.

Public API
----------
    get_backend(backend_name=None)  →  ComputeBackend instance (singleton)

ComputeBackend methods used by brain_widget / brain_worker:
    .zeros(shape)                              → ndarray-compatible 2-D matrix
    .forward(weights_matrix, inputs)           → 1-D result of weights @ inputs
    .hebbian(associations, sample, lr)         → updated associations matrix
    .get_value(matrix, i, j)                   → float scalar

Author note: dynamic neurogenesis is supported because the ONNX MatMul
graph is rebuilt whenever the network shape changes.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class ComputeBackend:
    """Abstract base class for compute backends."""

    def zeros(self, shape: tuple):
        """Return a zero-filled matrix of *shape* compatible with this backend."""
        raise NotImplementedError

    def forward(self, weights_matrix, inputs):
        """Dense matrix-vector product:  result = weights_matrix @ inputs."""
        raise NotImplementedError

    def hebbian(self, associations, sample: list, learning_rate: float):
        """
        Hebbian outer-product update applied to *associations* in place.

        For each pair (i, j) where i < j:
            associations[i][j] += learning_rate * sample[i] * sample[j]
            associations[j][i]  = associations[i][j]   (keep symmetric)

        Returns the updated associations matrix.
        """
        raise NotImplementedError

    def get_value(self, matrix, i: int, j: int) -> float:
        """Return matrix[i][j] as a plain Python float."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# NumPy backend  (default, always available)
# ---------------------------------------------------------------------------

class NumpyBackend(ComputeBackend):
    """
    Default compute backend.  Uses NumPy for all operations – identical
    behaviour to the pre-integration codebase.
    """

    def __init__(self):
        import numpy as _np  # already a project dependency
        self._np = _np
        print("🧠 Compute backend: NumPy")

    # --- ComputeBackend interface -------------------------------------------

    def zeros(self, shape: tuple):
        return self._np.zeros(shape)

    def forward(self, weights_matrix, inputs):
        return weights_matrix @ inputs

    def hebbian(self, associations, sample: list, learning_rate: float):
        np = self._np
        arr = np.array(sample, dtype=np.float64)
        delta = np.outer(arr, arr) * learning_rate
        n = len(sample)
        if hasattr(associations, 'shape'):
            # Vectorised upper-triangle update (associations is a NumPy array).
            # Increment the strict upper triangle, then mirror it to the lower
            # triangle. The diagonal is left untouched, exactly as the explicit
            # double loop did.
            rows, cols = np.triu_indices(n, k=1)
            associations[rows, cols] += delta[rows, cols]
            associations[cols, rows] = associations[rows, cols]
        else:
            # Fallback for plain list-of-lists matrices.
            for i in range(n):
                for j in range(i + 1, n):
                    associations[i][j] += delta[i][j]
                    associations[j][i]  = associations[i][j]
        return associations

    def get_value(self, matrix, i: int, j: int) -> float:
        return float(matrix[i][j])

    @property
    def name(self) -> str:
        return "numpy"


# ---------------------------------------------------------------------------
# ONNX Runtime backend  (optional)
# ---------------------------------------------------------------------------

class ONNXBackend(ComputeBackend):
    """
    Optional ONNX Runtime backend.

    * Lazy-imports  onnx  and  onnxruntime  so Dosidicus starts fine even
      when neither package is installed.
    * Automatically selects the best available execution provider:
        DirectML   → AMD / Intel / NVIDIA via Windows ML (NPU-capable)
        OpenVINO   → Intel NPU
        QNN        → Qualcomm Snapdragon X
        CPU        → universal fallback
    * Rebuilds the ONNX MatMul graph whenever the network shape changes,
      which means dynamic neurogenesis is fully supported.
    * Falls back to NumPy arithmetic internally for the Hebbian update
      (the association matrix is small; ONNX overhead would dominate).
    """

    # Execution-provider preference order
    _PROVIDER_PRIORITY = [
        'QNNExecutionProvider',          # Qualcomm Snapdragon X Elite NPU
        'DmlExecutionProvider',          # DirectML  (AMD XDNA, Intel Arc, NVIDIA)
        'OpenVINOExecutionProvider',     # Intel NPU / iGPU
        'CPUExecutionProvider',          # Always available
    ]

    def __init__(self):
        self._available   = False
        self._session     = None
        self._last_shape  = None
        self._provider    = 'CPUExecutionProvider'
        self._np          = None

        try:
            import numpy as np
            import onnx           # noqa: F401  (confirms package present)
            import onnxruntime as ort

            self._np  = np
            self._ort = ort

            available_providers = ort.get_available_providers()
            for pref in self._PROVIDER_PRIORITY:
                if pref in available_providers:
                    self._provider = pref
                    break

            self._available = True
            print(f"🧠 Compute backend: ONNX Runtime  [{self._provider}]")
            print(f"   Available providers: {available_providers}")

        except ImportError as exc:
            print(f"⚠️  ONNX Runtime not available ({exc}).")
            print("   Falling back to NumPy backend.  "
                  "Install 'onnxruntime' (or 'onnxruntime-directml') to enable NPU support.")

    # --- Internal helpers ---------------------------------------------------

    def _build_session(self, rows: int, cols: int):
        """
        Build (or rebuild) an ONNX MatMul session for a (rows, cols) weight
        matrix applied to a cols-element input vector → rows-element output.

        Called automatically from forward() when the shape changes.
        """
        from onnx import helper, TensorProto

        W = helper.make_tensor_value_info('weights', TensorProto.FLOAT, [rows, cols])
        V = helper.make_tensor_value_info('inputs',  TensorProto.FLOAT, [cols])
        Y = helper.make_tensor_value_info('output',  TensorProto.FLOAT, [rows])

        node  = helper.make_node('MatMul', inputs=['weights', 'inputs'], outputs=['output'])
        graph = helper.make_graph([node], 'dosidicus_forward', [W, V], [Y])
        model = helper.make_model(
            graph,
            opset_imports=[helper.make_opsetid('', 17)]
        )

        model_bytes = model.SerializeToString()

        sess_opts = self._ort.SessionOptions()
        sess_opts.log_severity_level = 3  # suppress verbose ONNX logs

        self._session    = self._ort.InferenceSession(
            model_bytes,
            sess_options=sess_opts,
            providers=[self._provider, 'CPUExecutionProvider']
        )
        self._last_shape = (rows, cols)

    # --- ComputeBackend interface -------------------------------------------

    def zeros(self, shape: tuple):
        return self._np.zeros(shape)

    def forward(self, weights_matrix, inputs):
        if not self._available:
            # Transparent NumPy fallback
            return weights_matrix @ inputs

        np = self._np
        w  = np.array(weights_matrix, dtype=np.float32)
        v  = np.array(inputs,         dtype=np.float32)

        rows, cols = w.shape
        if (rows, cols) != self._last_shape:
            # Network topology changed (neurogenesis) → rebuild graph
            self._build_session(rows, cols)

        result = self._session.run(['output'], {'weights': w, 'inputs': v})
        return result[0]

    def hebbian(self, associations, sample: list, learning_rate: float):
        """
        For the Hebbian update we stay in NumPy.
        The association matrix is small (N × N where N ≈ 10–100 neurons);
        the ONNX round-trip cost far exceeds the compute benefit at this size.
        """
        np  = self._np
        arr = np.array(sample, dtype=np.float64)
        delta = np.outer(arr, arr) * learning_rate
        n = len(sample)
        if hasattr(associations, 'shape'):
            # Vectorised upper-triangle update (associations is a NumPy array).
            # Increment the strict upper triangle, then mirror it to the lower
            # triangle. The diagonal is left untouched, exactly as the explicit
            # double loop did.
            rows, cols = np.triu_indices(n, k=1)
            associations[rows, cols] += delta[rows, cols]
            associations[cols, rows] = associations[rows, cols]
        else:
            # Fallback for plain list-of-lists matrices.
            for i in range(n):
                for j in range(i + 1, n):
                    associations[i][j] += delta[i][j]
                    associations[j][i]  = associations[i][j]
        return associations

    def get_value(self, matrix, i: int, j: int) -> float:
        return float(matrix[i][j])

    @property
    def name(self) -> str:
        if self._available:
            return f"onnx [{self._provider}]"
        return "numpy (onnx unavailable)"


# ---------------------------------------------------------------------------
# Factory / singleton
# ---------------------------------------------------------------------------

_backend_instance: ComputeBackend | None = None


def get_backend(backend_name: str | None = None) -> ComputeBackend:
    """
    Return the (singleton) compute backend.

    backend_name : 'numpy' | 'onnx'
        If None, reads [Compute] backend from config.ini.
        Defaults to 'numpy' if the section / key is absent.

    The ONNX backend silently falls back to NumPy if onnxruntime is not
    installed, so callers never need to guard against ImportError.
    """
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    if backend_name is None:
        backend_name = _read_backend_from_config()

    backend_name = backend_name.strip().lower()

    if backend_name == 'onnx':
        candidate = ONNXBackend()
        # If ONNX packages are missing, silently use NumPy
        _backend_instance = candidate if candidate._available else NumpyBackend()
    else:
        _backend_instance = NumpyBackend()

    return _backend_instance


def reset_backend():
    """Force re-initialisation on next get_backend() call (useful for tests)."""
    global _backend_instance
    _backend_instance = None


# ---------------------------------------------------------------------------
# Config reader (standalone – avoids circular import with config_manager)
# ---------------------------------------------------------------------------

def _read_backend_from_config() -> str:
    """Read [Compute] backend from config.ini, returns 'numpy' on any error."""
    try:
        import configparser
        import os
        import sys

        config = configparser.ConfigParser()

        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            # __file__ is  src/compute_backend.py  → go up one level
            src_dir   = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.dirname(src_dir)

        config_path = os.path.join(base_path, 'config.ini')
        config.read(config_path)
        return config.get('Compute', 'backend', fallback='numpy')

    except Exception:
        return 'numpy'
