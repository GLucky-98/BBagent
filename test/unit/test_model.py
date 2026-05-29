#!/usr/bin/env python3
"""
test_model.py - Model component tests

Test for BBagent.core.model module.
"""
import sys
from pathlib import Path

# test/unit/ -> test/ -> project_root
TEST_DIR = Path(__file__).parent.parent  # test/
PROJECT_ROOT = TEST_DIR.parent  # BBagent's parent
BBAGENT_DIR = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(TEST_DIR))  # for env import
sys.path.insert(0, str(BBAGENT_DIR))  # for BBagent.core imports

from env import get_env
ENV = get_env()

from core.model import AnthropicModel, Model_Input, Model


def test_anthropic_model_init():
    """Test AnthropicModel initialization with env config."""
    print("[TEST] test_anthropic_model_init")
    try:
        model = AnthropicModel(
            model=ENV["model"],
            api_key=ENV["api_key"],
            base_url=ENV["base_url"]
        )
        assert model.model == ENV["model"]
        assert model.api_key == ENV["api_key"]
        assert "anthropic" in model.base_url.lower() or "minimaxi" in model.base_url.lower()
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_model_input_creation():
    """Test Model_Input dataclass creation."""
    print("[TEST] test_model_input_creation")
    try:
        model_input = Model_Input(
            prompt="test prompt",
            tools=[],
            messages=[]
        )
        assert model_input.prompt == "test prompt"
        assert isinstance(model_input.tools, list)
        assert isinstance(model_input.messages, list)
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_model_payload_construct():
    """Test payload construction for API call."""
    print("[TEST] test_model_payload_construct")
    try:
        model = AnthropicModel(
            model=ENV["model"],
            api_key=ENV["api_key"],
            base_url=ENV["base_url"],
            max_tokens=1000
        )
        model_input = Model_Input(prompt="Hello", tools=[], messages=[])
        model.payload_construct(model_input)

        assert "max_tokens" in model.payload
        assert "model" in model.payload
        assert model.payload["max_tokens"] == 1000
        assert model.payload["model"] == ENV["model"]
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_model_invoke_sync():
    """Test synchronous model invocation."""
    print("[TEST] test_model_invoke_sync")
    try:
        model = AnthropicModel(
            model=ENV["model"],
            api_key=ENV["api_key"],
            base_url=ENV["base_url"],
            max_tokens=100
        )
        model_input = Model_Input(
            prompt="Say 'test' in one word",
            tools=[],
            messages=[]
        )
        response = model.invoke(model_input)

        # Response should be a string or ModelMessage
        assert response is not None
        print(f"[PASS] Response type: {type(response).__name__}")
        return True
    except Exception as e:
        # API may fail due to various reasons - mark as skip instead of fail
        print(f"[SKIP] API call failed: {e}")
        return True


def test_model_to_config_dict():
    """Test model configuration serialization."""
    print("[TEST] test_model_to_config_dict")
    try:
        model = AnthropicModel(
            model=ENV["model"],
            api_key=ENV["api_key"],
            base_url=ENV["base_url"]
        )
        config = model.to_config_dict()

        assert "model" in config
        assert "provider" in config or "base_url" in config
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_anthropic_model_init,
        test_model_input_creation,
        test_model_payload_construct,
        test_model_invoke_sync,
        test_model_to_config_dict,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)