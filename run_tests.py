#!/usr/bin/env python3
"""
Test runner script for the comprehensive test suite.

Provides:
- Easy test execution with different configurations
- Test categorization and filtering
- Performance monitoring
- Test result reporting
- CI/CD integration support

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit              # Run unit tests only
    python run_tests.py --integration       # Run integration tests only
    python run_tests.py --api               # Run API tests only
    python run_tests.py --edge              # Run edge case tests
    python run_tests.py --performance       # Run performance tests
    python run_tests.py --coverage         # Run with coverage
    python run_tests.py --parallel         # Run in parallel
"""

import sys
import os
import subprocess
import argparse
import time
from pathlib import Path


def run_command(cmd_parts, description):
    """Run a command and handle the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd_parts)}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd_parts, check=True, capture_output=False)
        end_time = time.time()
        
        print(f"\n✅ {description} completed successfully!")
        print(f"⏱️  Time taken: {end_time - start_time:.2f} seconds")
        return True
        
    except subprocess.CalledProcessError as e:
        end_time = time.time()
        print(f"\n❌ {description} failed!")
        print(f"⏱️  Time taken: {end_time - start_time:.2f} seconds")
        print(f"Exit code: {e.returncode}")
        return False


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner")
    
    # Test category options
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--api', action='store_true', help='Run API tests only')
    parser.add_argument('--ai', action='store_true', help='Run AI service tests only')
    parser.add_argument('--mock', action='store_true', help='Run mocked tests only')
    parser.add_argument('--edge', action='store_true', help='Run edge case tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    
    # Test execution options
    parser.add_argument('--coverage', action='store_true', help='Run with coverage reporting')
    parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--fast', action='store_true', help='Run only fast tests (skip slow)')
    
    # Test filtering options
    parser.add_argument('--file', type=str, help='Run specific test file')
    parser.add_argument('--function', type=str, help='Run specific test function')
    parser.add_argument('--class', type=str, dest='test_class', help='Run specific test class')
    
    args = parser.parse_args()
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Build pytest command
    cmd_parts = [sys.executable, "-m", "pytest"]
    
    # Add test file/function/class filters
    if args.file:
        cmd_parts.append(args.file)
    elif args.function:
        cmd_parts.extend(["-k", args.function])
    elif args.test_class:
        cmd_parts.extend(["-k", args.test_class])
    
    # Add category markers
    markers = []
    if args.unit:
        markers.append("unit")
    if args.integration:
        markers.append("integration")
    if args.api:
        markers.append("api")
    if args.ai:
        markers.append("ai")
    if args.mock:
        markers.append("mock")
    if args.edge:
        markers.append("edge")
    if args.performance:
        markers.append("performance")
    
    if markers:
        marker_expr = " or ".join(markers)
        cmd_parts.extend(["-m", marker_expr])
    
    # Add execution options
    if args.coverage:
        cmd_parts.extend(["--cov=app", "--cov-report=html", "--cov-report=term-missing"])
    
    if args.parallel:
        cmd_parts.extend(["-n", "auto"])
    
    if args.verbose:
        cmd_parts.append("-vv")
    else:
        cmd_parts.append("-v")
    
    if args.fast:
        cmd_parts.extend(["-m", "not slow"])
    
    # Default to all tests if no specific category selected
    if not any([args.unit, args.integration, args.api, args.ai, args.mock, args.edge, args.performance, args.file, args.function, args.test_class]):
        print("🚀 Running all tests...")
    
    # Run the tests
    success = run_command(cmd_parts, "Test Suite")
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
