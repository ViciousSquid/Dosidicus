#### New in v2.6.1.2 (experimental)

[compute_backend.py](https://github.com/ViciousSquid/Dosidicus/blob/2.6.1.2_onnx/src/compute_backend.py) facilitates hardware acceleration for neural calculations by changing one line:

in `config.ini`:

```
[Compute]

backend = numpy
```

 Options:
-    `numpy`  - default, no extra dependencies
-    `onnx`   - enables hardware AI accelerator support via ONNX Runtime

auto-selects `DirectML`, `OpenVINO`, `QNN`, or falls back to `numpy` if no runtime is present.

---------------------------------

requires package to be installed (refer to the following list:)

#### Recommended packages by platform:

- **Windows** | _NVIDIA + AMD + Intel GPU + NPU (DirectML)_ | `pip install onnxruntime-directml`

- **Windows** | _NVIDIA only (maximum CUDA performance)_ | `pip install onnxruntime-gpu`

- **Windows** | _Qualcomm 8CX / SQX / Snapdragon (NPU)_ | `pip install onnxruntime-qnn`

- **macOS** | _Apple Silicon and Intel Macs_ | `pip install onnxruntime`

- **Linux** | _NVIDIA GPUs_ | `pip install onnxruntime-gpu`

- **Linux** | _AMD GPUs_ | Use the ROCm/MIGraphX build (see [ONNX Runtime docs](https://onnxruntime.ai/docs/execution-providers/MIGraphX-ExecutionProvider.html))

```

If no package is installed, the default `numpy` will be used (neural calculations performed on CPU)
Any failure conditions will print to the console and we fall back to default `numpy`
Detection should happen automatically.       ONNX SUPPORT IS NEW AND EXPERIMENTAL
```

-------------------------------

The Brain Tool Network Tab displays which backend is being used in (top right)