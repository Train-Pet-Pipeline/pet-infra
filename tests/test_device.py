"""Tests for pet_infra.device module."""

import os
from unittest.mock import MagicMock, patch

from pet_infra.device import detect_device


class TestDetectDevice:
    def test_env_override_api(self):
        with patch.dict(os.environ, {"INFERENCE_BACKEND": "api"}):
            assert detect_device() == "api"

    def test_env_override_cpu(self):
        with patch.dict(os.environ, {"INFERENCE_BACKEND": "cpu"}):
            assert detect_device() == "cpu"

    def test_cuda_detected(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = True
            with patch.dict(
                "sys.modules",
                {
                    "torch": mock_torch,
                    "torch.cuda": mock_torch.cuda,
                    "torch.backends": mock_torch.backends,
                    "torch.backends.mps": mock_torch.backends.mps,
                },
            ):
                assert detect_device() == "cuda"

    def test_mps_detected(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = False
            mock_torch.backends.mps.is_available.return_value = True
            with patch.dict(
                "sys.modules",
                {
                    "torch": mock_torch,
                    "torch.cuda": mock_torch.cuda,
                    "torch.backends": mock_torch.backends,
                    "torch.backends.mps": mock_torch.backends.mps,
                },
            ):
                assert detect_device() == "mps"

    def test_cpu_fallback_no_torch(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict("sys.modules", {"torch": None}):
                assert detect_device() == "cpu"

    def test_rknn_detected(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_rknn = MagicMock()
            with patch.dict("sys.modules", {"torch": None, "rknn_toolkit2": mock_rknn}):
                assert detect_device() == "rknn"
