"""
Module: granger_daily_verify.py
Description: Implementation of granger daily verify functionality

External Dependencies:
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Module: granger_daily_verify.py
Description: Daily verification script for Marker's integration with the Granger ecosystem

External Dependencies:
- typer: https://typer.tiangolo.com/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # Run verification for marker project
>>> python granger_daily_verify.py --project marker

Expected Output:
>>> 🔍 Granger Daily Verification for: marker
>>> ✅ Slash command integration: PASS (8 commands registered)
>>> ✅ MCP integration: PASS (server configured)
>>> ✅ Module communication: PASS (messages directory found)
>>> ⚠️  Configuration issues: 1 warning found

Example Usage:
>>> from granger_daily_verify import verify_project_integration
>>> results = verify_project_integration("marker")
>>> print(results['overall_status'])
'PASS_WITH_WARNINGS'
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import importlib.util
from datetime import datetime
import typer
from loguru import logger

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

app = typer.Typer()


class GrangerVerifier:
    """Verifies Granger ecosystem integration for a project."""
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.project_root = Path(__file__).parent.parent
        self.src_root = self.project_root / "src" / project_name.replace("-", "_")
        self.results = {
            "project": project_name,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "warnings": [],
            "errors": [],
            "overall_status": "UNKNOWN"
        }
    
    def verify_all(self) -> Dict:
        """Run all verification checks."""
        logger.info(f"🔍 Starting Granger verification for: {self.project_name}")
        
        # Run checks
        self._check_slash_commands()
        self._check_mcp_integration()
        self._check_module_communication()
        self._check_configuration()
        self._check_dependencies()
        
        # Determine overall status
        self._determine_overall_status()
        
        return self.results
    
    def _check_slash_commands(self):
        """Check slash command integration."""
        check_name = "slash_commands"
        logger.info("Checking slash command integration...")
        
        try:
            # Check if slash commands directory exists
            slash_cmd_dir = self.src_root / "cli" / "slash_commands"
            if not slash_cmd_dir.exists():
                self.results["checks"][check_name] = {
                    "status": "FAIL",
                    "message": "Slash commands directory not found",
                    "details": f"Expected: {slash_cmd_dir}"
                }
                return
            
            # Check for command files
            command_files = list(slash_cmd_dir.glob("*.py"))
            command_files = [f for f in command_files if f.name != "__init__.py"]
            
            # Check if commands are registered
            try:
                from marker.cli.slash_commands import registry
                registered_commands = registry.list_commands()
                
                self.results["checks"][check_name] = {
                    "status": "PASS",
                    "message": f"Found {len(registered_commands)} registered commands",
                    "details": {
                        "command_files": len(command_files),
                        "registered_commands": len(registered_commands),
                        "commands": sorted(registered_commands)
                    }
                }
                
                # Check for granger-specific commands
                granger_commands = [cmd for cmd in registered_commands if "granger" in cmd]
                if not granger_commands:
                    self.results["warnings"].append({
                        "type": "missing_granger_commands",
                        "message": "No Granger-specific slash commands found",
                        "suggestion": "Consider adding /granger-daily-verify command"
                    })
                    
            except ImportError as e:
                self.results["checks"][check_name] = {
                    "status": "FAIL",
                    "message": f"Failed to import slash command registry: {e}",
                    "details": str(e)
                }
                
        except Exception as e:
            self.results["checks"][check_name] = {
                "status": "ERROR",
                "message": f"Error checking slash commands: {e}",
                "details": str(e)
            }
            self.results["errors"].append(str(e))
    
    def _check_mcp_integration(self):
        """Check MCP (Model Context Protocol) integration."""
        check_name = "mcp_integration"
        logger.info("Checking MCP integration...")
        
        try:
            # Check for MCP directory
            mcp_dir = self.src_root / "mcp"
            if not mcp_dir.exists():
                self.results["checks"][check_name] = {
                    "status": "FAIL",
                    "message": "MCP directory not found",
                    "details": f"Expected: {mcp_dir}"
                }
                return
            
            # Check for server.py
            server_file = mcp_dir / "server.py"
            if not server_file.exists():
                self.results["checks"][check_name] = {
                    "status": "FAIL",
                    "message": "MCP server.py not found",
                    "details": f"Expected: {server_file}"
                }
                return
            
            # Check for mcp.json configuration
            mcp_configs = list(self.project_root.glob("mcp*.json"))
            
            # Check if granger mixin is used
            cli_main = self.src_root / "cli" / "main.py"
            uses_granger_mixin = False
            if cli_main.exists():
                content = cli_main.read_text()
                if "granger_slash_mcp_mixin" in content:
                    uses_granger_mixin = True
            
            self.results["checks"][check_name] = {
                "status": "PASS",
                "message": "MCP integration configured",
                "details": {
                    "mcp_server_exists": server_file.exists(),
                    "mcp_configs_found": len(mcp_configs),
                    "uses_granger_mixin": uses_granger_mixin,
                    "config_files": [str(f.name) for f in mcp_configs]
                }
            }
            
            # Check for FastMCP usage
            if server_file.exists():
                server_content = server_file.read_text()
                if "fastmcp" not in server_content.lower():
                    self.results["warnings"].append({
                        "type": "mcp_standard",
                        "message": "Not using FastMCP standard",
                        "suggestion": "Consider migrating to FastMCP for Granger compliance"
                    })
                    
        except Exception as e:
            self.results["checks"][check_name] = {
                "status": "ERROR",
                "message": f"Error checking MCP integration: {e}",
                "details": str(e)
            }
            self.results["errors"].append(str(e))
    
    def _check_module_communication(self):
        """Check module communication system."""
        check_name = "module_communication"
        logger.info("Checking module communication system...")
        
        try:
            # Check for messages directory
            messages_dirs = []
            
            # Check in src
            src_messages = self.src_root.parent / "messages"
            if src_messages.exists():
                messages_dirs.append(src_messages)
            
            # Check in project root
            root_messages = self.project_root / "messages"
            if root_messages.exists():
                messages_dirs.append(root_messages)
            
            if not messages_dirs:
                self.results["checks"][check_name] = {
                    "status": "FAIL",
                    "message": "No messages directory found",
                    "details": "Module communication system not configured"
                }
                return
            
            # Check for standard message directories
            expected_dirs = ["from_arangodb", "to_arangodb", "from_marker", "to_marker"]
            found_dirs = {}
            
            for msg_dir in messages_dirs:
                for expected in expected_dirs:
                    if (msg_dir / expected).exists():
                        found_dirs[expected] = True
            
            # Check for marker_module.py
            integrations_dir = self.src_root / "integrations"
            marker_module_exists = False
            if integrations_dir.exists():
                marker_module = integrations_dir / "marker_module.py"
                marker_module_exists = marker_module.exists()
            
            self.results["checks"][check_name] = {
                "status": "PASS" if found_dirs else "PARTIAL",
                "message": f"Module communication system {'configured' if found_dirs else 'partially configured'}",
                "details": {
                    "messages_directories": [str(d) for d in messages_dirs],
                    "standard_dirs_found": list(found_dirs.keys()),
                    "marker_module_exists": marker_module_exists
                }
            }
            
            if not marker_module_exists:
                self.results["warnings"].append({
                    "type": "missing_marker_module",
                    "message": "marker_module.py not found in integrations",
                    "suggestion": "Create marker_module.py for inter-module communication"
                })
                
        except Exception as e:
            self.results["checks"][check_name] = {
                "status": "ERROR",
                "message": f"Error checking module communication: {e}",
                "details": str(e)
            }
            self.results["errors"].append(str(e))
    
    def _check_configuration(self):
        """Check configuration and environment setup."""
        check_name = "configuration"
        logger.info("Checking configuration...")
        
        try:
            issues = []
            
            # Check .env.example
            env_example = self.project_root / ".env.example"
            if not env_example.exists():
                issues.append("Missing .env.example file")
            else:
                content = env_example.read_text()
                if not content.startswith("PYTHONPATH=./src"):
                    issues.append(".env.example must start with PYTHONPATH=./src")
            
            # Check pyproject.toml
            pyproject = self.project_root / "pyproject.toml"
            if not pyproject.exists():
                issues.append("Missing pyproject.toml")
            else:
                content = pyproject.read_text()
                if "uv" not in content and "[tool.uv]" not in content:
                    self.results["warnings"].append({
                        "type": "package_manager",
                        "message": "Not configured for uv package manager",
                        "suggestion": "Add uv configuration to pyproject.toml"
                    })
            
            # Check CLAUDE.md
            claude_md = self.project_root / "CLAUDE.md"
            if not claude_md.exists():
                issues.append("Missing CLAUDE.md project instructions")
            
            self.results["checks"][check_name] = {
                "status": "PASS" if not issues else "FAIL",
                "message": f"Configuration {'complete' if not issues else 'has issues'}",
                "details": {
                    "issues": issues,
                    "env_example_exists": env_example.exists(),
                    "pyproject_exists": pyproject.exists(),
                    "claude_md_exists": claude_md.exists()
                }
            }
            
        except Exception as e:
            self.results["checks"][check_name] = {
                "status": "ERROR",
                "message": f"Error checking configuration: {e}",
                "details": str(e)
            }
            self.results["errors"].append(str(e))
    
    def _check_dependencies(self):
        """Check Granger ecosystem dependencies."""
        check_name = "dependencies"
        logger.info("Checking dependencies...")
        
        try:
            required_deps = {
                "typer": "CLI framework",
                "loguru": "Logging",
                "fastmcp": "MCP server (optional but recommended)"
            }
            
            missing_deps = []
            found_deps = {}
            
            # Check in pyproject.toml
            pyproject = self.project_root / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text()
                for dep, desc in required_deps.items():
                    if dep in content:
                        found_deps[dep] = desc
                    elif dep != "fastmcp":  # fastmcp is optional
                        missing_deps.append(f"{dep} ({desc})")
            
            self.results["checks"][check_name] = {
                "status": "PASS" if not missing_deps else "FAIL",
                "message": f"Dependencies {'satisfied' if not missing_deps else 'missing'}",
                "details": {
                    "found": list(found_deps.keys()),
                    "missing": missing_deps
                }
            }
            
        except Exception as e:
            self.results["checks"][check_name] = {
                "status": "ERROR",
                "message": f"Error checking dependencies: {e}",
                "details": str(e)
            }
            self.results["errors"].append(str(e))
    
    def _determine_overall_status(self):
        """Determine overall verification status."""
        statuses = [check["status"] for check in self.results["checks"].values()]
        
        if "ERROR" in statuses:
            self.results["overall_status"] = "ERROR"
        elif "FAIL" in statuses:
            self.results["overall_status"] = "FAIL"
        elif self.results["warnings"]:
            self.results["overall_status"] = "PASS_WITH_WARNINGS"
        elif "PARTIAL" in statuses:
            self.results["overall_status"] = "PARTIAL"
        else:
            self.results["overall_status"] = "PASS"


def verify_project_integration(project_name: str, verbose: bool = False) -> Dict:
    """Verify a project's integration with Granger ecosystem."""
    verifier = GrangerVerifier(project_name)
    results = verifier.verify_all()
    
    # Display results
    print(f"\n🔍 Granger Daily Verification for: {project_name}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    # Show check results
    for check_name, check_result in results["checks"].items():
        status = check_result["status"]
        message = check_result["message"]
        
        icon = {
            "PASS": "✅",
            "FAIL": "❌",
            "PARTIAL": "⚠️ ",
            "ERROR": "💥"
        }.get(status, "❓")
        
        print(f"{icon} {check_name.replace('_', ' ').title()}: {status}")
        print(f"   {message}")
        
        if verbose and "details" in check_result:
            details = check_result["details"]
            if isinstance(details, dict):
                for key, value in details.items():
                    print(f"   - {key}: {value}")
            else:
                print(f"   Details: {details}")
    
    # Show warnings
    if results["warnings"]:
        print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            print(f"   - {warning['message']}")
            if "suggestion" in warning:
                print(f"     💡 {warning['suggestion']}")
    
    # Show errors
    if results["errors"]:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"   - {error}")
    
    # Overall status
    print("\n" + "=" * 60)
    status_icon = {
        "PASS": "✅",
        "PASS_WITH_WARNINGS": "⚠️ ",
        "PARTIAL": "⚠️ ",
        "FAIL": "❌",
        "ERROR": "💥"
    }.get(results["overall_status"], "❓")
    
    print(f"{status_icon} Overall Status: {results['overall_status']}")
    
    # Recommendations
    if results["overall_status"] != "PASS":
        print("\n📋 Recommendations:")
        if "slash_commands" in results["checks"] and results["checks"]["slash_commands"]["status"] != "PASS":
            print("   1. Implement slash command system in src/marker/cli/slash_commands/")
        if "mcp_integration" in results["checks"] and results["checks"]["mcp_integration"]["status"] != "PASS":
            print("   2. Configure MCP server in src/marker/mcp/server.py")
        if results["warnings"]:
            print("   3. Address warnings to achieve full Granger compliance")
    
    return results


@app.command()
def main(
    project: str = typer.Argument("marker", help="Project name to verify"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save results to JSON file")
):
    """Run Granger daily verification for a project."""
    try:
        results = verify_project_integration(project, verbose)
        
        # Save to file if requested
        if output:
            output.write_text(json.dumps(results, indent=2))
            print(f"\n📄 Results saved to: {output}")
        
        # Exit with appropriate code
        exit_code = {
            "PASS": 0,
            "PASS_WITH_WARNINGS": 0,
            "PARTIAL": 1,
            "FAIL": 1,
            "ERROR": 2
        }.get(results["overall_status"], 2)
        
        raise typer.Exit(exit_code)
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        print(f"\n💥 Fatal error: {e}")
        raise typer.Exit(2)


if __name__ == "__main__":
    # Validation when run directly
    results = verify_project_integration("marker", verbose=True)
    
    # Show summary
    total_checks = len(results["checks"])
    passed = sum(1 for c in results["checks"].values() if c["status"] == "PASS")
    
    print(f"\n📊 Summary: {passed}/{total_checks} checks passed")
    print(f"⚠️  Warnings: {len(results['warnings'])}")
    print(f"❌ Errors: {len(results['errors'])}")
    
    if results["overall_status"] == "PASS":
        print("\n✅ Granger daily verification passed!")
    else:
        print(f"\n⚠️  Verification completed with status: {results['overall_status']}")