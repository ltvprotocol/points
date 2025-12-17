#!/usr/bin/env python3
"""
Main test runner for all tests in the test directory.
Run this file to execute all tests using pytest.
"""
import sys
import os

try:
    import pytest
except ImportError:
    print("Error: pytest is not installed. Please install it with: pip install pytest")
    sys.exit(1)


def run_all_tests():
    """Run all tests using pytest"""
    print("=" * 60)
    print("Running All Tests")
    print("=" * 60)
    
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get project root directory
    project_root = os.path.dirname(test_dir)
    
    # Add project root to sys.path so imports work from any directory
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Change to the project root directory
    os.chdir(project_root)
    
    # Run pytest on the test directory
    exit_code = pytest.main([
        "./",
        "-v",
        "--tb=short",
        "-s"  # Show print statements
    ])
    
    sys.exit(exit_code)


if __name__ == "__main__":
    run_all_tests()

