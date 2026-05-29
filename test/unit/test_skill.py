#!/usr/bin/env python3
"""
test_skill.py - Skill component tests

Test for BBagent.core.skill module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "BBagent"))

from core.skill import Skill


def test_skill_creation():
    """Test Skill creation."""
    print("[TEST] test_skill_creation")
    try:
        skill = Skill(
            name="test_skill",
            description="A test skill",
            body="# Test Skill\n\nThis is a test skill."
        )
        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_skill_to_config_dict():
    """Test Skill configuration serialization."""
    print("[TEST] test_skill_to_config_dict")
    try:
        skill = Skill(
            name="test_skill",
            description="A test skill",
            body="# Test Skill"
        )
        config = skill.to_config_dict()
        assert "name" in config
        assert "description" in config
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_scan_skills():
    """Test scan_skills with a real skills directory."""
    print("[TEST] test_scan_skills")
    try:
        skills_dir = Path(__file__).parent.parent.parent / "skills"
        if not skills_dir.exists():
            print("[SKIP] skills directory not found")
            return True
        from core.skill import scan_skills
        skills = scan_skills(skills_dir)
        assert len(skills) > 0
        print(f"  Found {len(skills)} skills: {list(skills.keys())}")
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_skill_creation,
        test_skill_to_config_dict,
        test_scan_skills,
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