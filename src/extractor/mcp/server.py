"""
MCP Server for Marker with Claude Code Integration
Module: server.py

Provides tools for agents to intelligently use Marker with system-aware Claude configuration.
Agents can check system resources and get recommendations for optimal Claude settings.
"""

import json
import os
import psutil
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import asyncio
from dataclasses import asdict

from extractor.core.config.claude_config import (
    MarkerClaudeSettings,
    get_recommended_config_for_use_case,
    validate_claude_config,
    CLAUDE_DISABLED,
    CLAUDE_MINIMAL,
    CLAUDE_TABLE_ANALYSIS_ONLY,
    CLAUDE_ACCURACY_FOCUSED,
    CLAUDE_RESEARCH_QUALITY
)

class SystemResourceAnalyzer:
    """Analyzes system resources to recommend optimal Claude configuration."""
    
    @staticmethod
    def get_system_resources() -> Dict[str, Any]:
        """Get comprehensive system resource information."""
        
        # CPU information
        cpu_info = {
            "count": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "current_usage": psutil.cpu_percent(interval=1),
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_percent": memory.percent,
            "free_gb": round(memory.free / (1024**3), 2)
        }
        
        # Disk information for Claude workspace
        disk = psutil.disk_usage('/')
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "used_percent": round((disk.used / disk.total) * 100, 1)
        }
        
        # Check for Claude Code CLI
        claude_available = shutil.which('claude') is not None
        claude_info = {
            "cli_available": claude_available,
            "cli_path": shutil.which('claude') if claude_available else None
        }
        
        if claude_available:
            try:
                # Test Claude CLI responsiveness
                result = subprocess.run(
                    ['claude', '--version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                claude_info["version"] = result.stdout.strip() if result.returncode == 0 else "unknown"
                claude_info["responsive"] = result.returncode == 0
            except (subprocess.TimeoutExpired, Exception) as e:
                claude_info["version"] = "unknown"
                claude_info["responsive"] = False
                claude_info["error"] = str(e)
        
        # Process information
        processes = len(psutil.pids())
        high_cpu_processes = len([p for p in psutil.process_iter(['cpu_percent']) 
                                 if p.info['cpu_percent'] and p.info['cpu_percent'] > 50])
        
        process_info = {
            "total_processes": processes,
            "high_cpu_processes": high_cpu_processes,
            "system_load": "high" if high_cpu_processes > 2 else "normal"
        }
        
        return {
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "claude": claude_info,
            "processes": process_info,
            "timestamp": time.time()
        }
    
    @staticmethod
    def recommend_claude_config(system_resources: Dict[str, Any] = None) -> Tuple[str, MarkerClaudeSettings, List[str]]:
        """
        Recommend optimal Claude configuration based on system resources.
        
        Returns:
            Tuple of (config_name, config_object, reasoning)
        """
        
        if system_resources is None:
            system_resources = SystemResourceAnalyzer.get_system_resources()
        
        reasoning = []
        
        # Check Claude availability
        if not system_resources["claude"]["cli_available"]:
            reasoning.append("Claude CLI not available - disabling all Claude features")
            return "disabled", CLAUDE_DISABLED, reasoning
        
        if not system_resources["claude"]["responsive"]:
            reasoning.append("Claude CLI not responsive - disabling Claude features for reliability")
            return "disabled", CLAUDE_DISABLED, reasoning
        
        # Memory-based recommendations
        memory_gb = system_resources["memory"]["available_gb"]
        memory_usage = system_resources["memory"]["used_percent"]
        
        if memory_gb < 4:
            reasoning.append(f"Low available memory ({memory_gb:.1f}GB) - disabling Claude features")
            return "disabled", CLAUDE_DISABLED, reasoning
        elif memory_gb < 8:
            reasoning.append(f"Limited memory ({memory_gb:.1f}GB) - using minimal Claude features")
            return "minimal", CLAUDE_MINIMAL, reasoning
        
        # CPU-based recommendations
        cpu_cores = system_resources["cpu"]["count"]
        cpu_usage = system_resources["cpu"]["current_usage"]
        system_load = system_resources["processes"]["system_load"]
        
        if cpu_cores < 4:
            reasoning.append(f"Limited CPU cores ({cpu_cores}) - using minimal configuration")
            return "minimal", CLAUDE_MINIMAL, reasoning
        
        if cpu_usage > 80 or system_load == "high":
            reasoning.append(f"High system load (CPU: {cpu_usage}%) - reducing Claude features")
            return "tables_only", CLAUDE_TABLE_ANALYSIS_ONLY, reasoning
        
        # Disk space check
        disk_free_gb = system_resources["disk"]["free_gb"]
        if disk_free_gb < 2:
            reasoning.append(f"Low disk space ({disk_free_gb:.1f}GB) - using minimal configuration")
            return "minimal", CLAUDE_MINIMAL, reasoning
        
        # Optimal recommendations based on available resources
        if memory_gb >= 16 and cpu_cores >= 8 and cpu_usage < 50:
            reasoning.append(f"Excellent resources (RAM: {memory_gb:.1f}GB, CPU: {cpu_cores} cores) - enabling accuracy-focused configuration")
            return "accuracy", CLAUDE_ACCURACY_FOCUSED, reasoning
        elif memory_gb >= 12 and cpu_cores >= 6:
            reasoning.append(f"Good resources (RAM: {memory_gb:.1f}GB, CPU: {cpu_cores} cores) - enabling table analysis")
            return "tables_only", CLAUDE_TABLE_ANALYSIS_ONLY, reasoning
        else:
            reasoning.append(f"Moderate resources (RAM: {memory_gb:.1f}GB, CPU: {cpu_cores} cores) - using minimal configuration")
            return "minimal", CLAUDE_MINIMAL, reasoning

class MarkerMCPServer:
    """MCP Server for Marker with intelligent Claude configuration."""
    
    def __init__(self):
        self.resource_analyzer = SystemResourceAnalyzer()
        self.last_resource_check = None
        self.cached_resources = None
        self.cache_duration = 30  # seconds
    
    def get_fresh_system_resources(self) -> Dict[str, Any]:
        """Get system resources with caching to avoid excessive system calls."""
        
        current_time = time.time()
        
        if (self.last_resource_check is None or 
            current_time - self.last_resource_check > self.cache_duration or
            self.cached_resources is None):
            
            self.cached_resources = self.resource_analyzer.get_system_resources()
            self.last_resource_check = current_time
        
        return self.cached_resources
    
    async def convert_pdf_with_claude_intelligence(self, 
                                                  file_path: str,
                                                  claude_config: Optional[str] = None,
                                                  check_system_resources: bool = True,
                                                  force_config: bool = False,
                                                  extraction_method: str = "marker") -> Dict[str, Any]:
        """
        Convert PDF with intelligent Claude configuration selection.
        
        Args:
            file_path: Path to PDF file
            claude_config: Requested config name or None for auto-selection
            check_system_resources: Whether to check system resources first
            force_config: Use requested config even if system resources suggest otherwise
            extraction_method: "marker" (full processing) or "pymupdf4llm" (fast text extraction)
            
        Returns:
            Conversion result with metadata about decisions made
        """
        
        result = {
            "file_path": file_path,
            "extraction_method": extraction_method,
            "claude_config_used": None,
            "claude_config_requested": claude_config,
            "system_resources_checked": check_system_resources,
            "recommendations": [],
            "warnings": [],
            "performance_estimate": {},
            "conversion_result": None
        }
        
        # Check if file exists
        if not os.path.exists(file_path):
            result["error"] = f"File not found: {file_path}"
            return result
        
        # Handle PyMuPDF4LLM fast extraction (bypasses Claude entirely)
        if extraction_method == "pymupdf4llm":
            result["claude_config_used"] = "disabled"
            result["recommendations"].append("Using PyMuPDF4LLM for fastest possible text extraction")
            result["performance_estimate"] = {
                "base_processing_time": 2.0,
                "claude_overhead": 0.0,
                "estimated_time": 2.0,
                "slowdown_factor": 1.0,
                "features_contributing": [],
                "extraction_method": "pymupdf4llm_fast"
            }
            result["conversion_result"] = {
                "status": "would_convert_fast",
                "estimated_time": 2.0,
                "method": "pymupdf4llm",
                "note": "Fast text-only extraction - no table/image processing or Claude features"
            }
            return result
        
        # Get system resources if requested
        if check_system_resources:
            system_resources = self.get_fresh_system_resources()
            result["system_resources"] = system_resources
            
            # Get system-based recommendation
            recommended_config, recommended_settings, reasoning = self.resource_analyzer.recommend_claude_config(system_resources)
            result["system_recommendation"] = {
                "config_name": recommended_config,
                "reasoning": reasoning
            }
            
            # Decide which config to use
            if claude_config is None:
                # Use system recommendation
                final_config_name = recommended_config
                final_config = recommended_settings
                result["recommendations"].append("Using system-recommended configuration")
            elif force_config:
                # Use requested config regardless of system resources
                final_config_name = claude_config
                final_config = get_recommended_config_for_use_case(claude_config)
                result["warnings"].append("Forcing requested configuration despite system recommendations")
            else:
                # Compare requested vs recommended
                requested_config = get_recommended_config_for_use_case(claude_config)
                
                if claude_config == recommended_config:
                    final_config_name = claude_config
                    final_config = requested_config
                    result["recommendations"].append("Requested configuration matches system recommendation")
                else:
                    # Warn about potential issues but use requested config
                    final_config_name = claude_config
                    final_config = requested_config
                    result["warnings"].append(f"Requested '{claude_config}' config may not be optimal for current system resources")
                    result["warnings"].extend(reasoning)
        else:
            # Use requested config or default without resource checking
            final_config_name = claude_config or "disabled"
            final_config = get_recommended_config_for_use_case(final_config_name)
        
        result["claude_config_used"] = final_config_name
        
        # Validate final configuration
        validation = validate_claude_config(final_config)
        result["config_validation"] = validation
        
        if not validation["valid"]:
            result["warnings"].extend(validation["warnings"])
        
        # Estimate performance impact
        result["performance_estimate"] = self._estimate_performance_impact(final_config, file_path)
        
        # Perform the actual conversion
        try:
            from extractor.core.converters.pdf import PdfConverter
            from extractor.core.processors.claude_post_processor import ClaudePostProcessor
            from extractor.core.renderers.markdown import MarkdownRenderer
            from extractor.core.renderers.json import JSONRenderer
            from extractor.core.models import create_model_dict
            
            start_time = time.time()
            
            # Create model dict if not provided
            model_dict = create_model_dict()
            
            # Determine extraction method
            if extraction_method == "pymupdf4llm":
                # Fast text-only extraction
                try:
                    import pymupdf4llm
                    markdown_text = pymupdf4llm.to_markdown(file_path)
                    result["conversion_result"] = {
                        "status": "success",
                        "markdown": markdown_text,
                        "processing_time": time.time() - start_time,
                        "method": "pymupdf4llm",
                        "claude_enhanced": False
                    }
                    return result
                except ImportError:
                    result["warnings"].append("pymupdf4llm not available, falling back to marker")
                    extraction_method = "marker"
            
            # Full Marker extraction
            config = {"claude": final_config} if final_config.enable_claude_features else {}
            
            # Get processor list - include Claude post-processor if enabled
            processor_list = None  # Use defaults
            if final_config.enable_claude_features:
                from extractor.core.util import strings_to_classes
                # Add Claude post-processor to the end
                processor_list = "default+marker.processors.claude_post_processor.ClaudePostProcessor"
            
            # Create converter
            converter = PdfConverter(
                config=config,
                artifact_dict=model_dict,
                processor_list=processor_list,
                renderer=MarkdownRenderer
            )
            
            # Convert the document
            rendered = converter(file_path)
            
            # Collect metadata
            metadata = {
                "processing_time": time.time() - start_time,
                "method": "marker",
                "claude_enhanced": final_config.enable_claude_features,
                "pages": len(converter.document.pages) if hasattr(converter, 'document') else 0
            }
            
            # Add Claude-specific metadata if enabled
            if final_config.enable_claude_features:
                # Count tables and merged tables
                table_count = 0
                merged_count = 0
                for page in converter.document.pages:
                    for table in page.contained_blocks(converter.document, ["Table"]):
                        table_count += 1
                        if hasattr(table, 'merge_info') and table.merge_info:
                            merged_count += len(table.merge_info)
                
                metadata["claude_analysis"] = {
                    "features_used": [f for f in ["section_verification", "table_merge_analysis", 
                                                 "content_validation", "structure_analysis"]
                                    if getattr(final_config, f"enable_{f}", False)],
                    "tables_analyzed": table_count,
                    "tables_merged": merged_count
                }
            
            result["conversion_result"] = {
                "status": "success",
                "markdown": rendered.markdown,
                "metadata": metadata,
                "processing_time": metadata["processing_time"]
            }
            
            # Clean up
            del model_dict
            
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            result["conversion_result"] = {
                "status": "error",
                "error": str(e),
                "processing_time": time.time() - start_time
            }
        
        return result
    
    def _estimate_performance_impact(self, config: MarkerClaudeSettings, file_path: str) -> Dict[str, Any]:
        """Estimate performance impact of Claude configuration."""
        
        # Get file size for estimation
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        except:
            file_size_mb = 10  # Default estimate
        
        # Base processing time estimate (heuristic)
        base_time = max(file_size_mb * 2, 10)  # ~2 seconds per MB, minimum 10s
        
        # Claude feature overhead estimates
        claude_overhead = 0
        features_used = []
        
        if config.enable_claude_features:
            if config.enable_section_verification:
                claude_overhead += 45  # 30-60s average
                features_used.append("section_verification")
            
            if config.enable_table_merge_analysis:
                # Estimate based on likely table count
                estimated_tables = max(int(file_size_mb / 2), 1)
                claude_overhead += estimated_tables * 20  # 15-30s per table pair
                features_used.append("table_merge_analysis")
            
            if config.enable_content_validation:
                claude_overhead += 30  # 20-40s average
                features_used.append("content_validation")
            
            if config.enable_structure_analysis:
                claude_overhead += 20  # 10-30s average
                features_used.append("structure_analysis")
        
        total_estimated_time = base_time + claude_overhead
        slowdown_factor = total_estimated_time / base_time if base_time > 0 else 1
        
        return {
            "base_processing_time": round(base_time, 1),
            "claude_overhead": round(claude_overhead, 1),
            "estimated_time": round(total_estimated_time, 1),
            "slowdown_factor": round(slowdown_factor, 2),
            "features_contributing": features_used,
            "file_size_mb": round(file_size_mb, 2)
        }
    
    async def get_system_resources_for_agent(self) -> Dict[str, Any]:
        """Get system resources formatted for agent decision-making."""
        
        resources = self.get_fresh_system_resources()
        
        # Add interpretation for agent
        interpretation = {
            "claude_feasible": resources["claude"]["cli_available"] and resources["claude"]["responsive"],
            "resource_level": "unknown",
            "recommended_config": "disabled",
            "limitations": [],
            "advantages": []
        }
        
        # Determine resource level
        memory_gb = resources["memory"]["available_gb"]
        cpu_cores = resources["cpu"]["count"]
        
        if memory_gb >= 16 and cpu_cores >= 8:
            interpretation["resource_level"] = "excellent"
            interpretation["advantages"].append("High memory and CPU cores available")
        elif memory_gb >= 8 and cpu_cores >= 4:
            interpretation["resource_level"] = "good"
            interpretation["advantages"].append("Adequate resources for Claude features")
        elif memory_gb >= 4 and cpu_cores >= 2:
            interpretation["resource_level"] = "limited"
            interpretation["limitations"].append("Limited resources - minimal Claude features recommended")
        else:
            interpretation["resource_level"] = "insufficient"
            interpretation["limitations"].append("Insufficient resources for Claude features")
        
        # Get recommendation
        recommended_config, _, reasoning = self.resource_analyzer.recommend_claude_config(resources)
        interpretation["recommended_config"] = recommended_config
        interpretation["reasoning"] = reasoning
        
        # Add specific limitations
        if resources["memory"]["used_percent"] > 80:
            interpretation["limitations"].append("High memory usage detected")
        
        if resources["cpu"]["current_usage"] > 70:
            interpretation["limitations"].append("High CPU usage detected")
        
        if not resources["claude"]["cli_available"]:
            interpretation["limitations"].append("Claude CLI not installed")
        
        return {
            "resources": resources,
            "interpretation": interpretation,
            "timestamp": resources["timestamp"]
        }
    
    async def recommend_extraction_strategy(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend extraction strategy based on user requirements.
        
        Args:
            requirements: Dict with keys like 'speed_priority', 'accuracy_priority', 'content_types', etc.
            
        Returns:
            Recommendation with extraction method and Claude config
        """
        
        # Default recommendation
        recommendation = {
            "extraction_method": "marker",
            "claude_config": "disabled",
            "reasoning": [],
            "trade_offs": []
        }
        
        speed_priority = requirements.get('speed_priority', 'normal')  # 'fastest', 'fast', 'normal', 'slow'
        accuracy_priority = requirements.get('accuracy_priority', 'normal')  # 'basic', 'normal', 'high', 'research'
        content_types = requirements.get('content_types', ['text'])  # ['text', 'tables', 'images', 'equations']
        
        # Speed-first recommendations
        if speed_priority == 'fastest':
            recommendation["extraction_method"] = "pymupdf4llm"
            recommendation["claude_config"] = "disabled"
            recommendation["reasoning"].append("Fastest text extraction using PyMuPDF4LLM")
            recommendation["trade_offs"].append("No table/image extraction, no Claude enhancements")
            
        elif speed_priority == 'fast':
            recommendation["extraction_method"] = "marker"
            recommendation["claude_config"] = "disabled"
            recommendation["reasoning"].append("Fast Marker processing without Claude features")
            recommendation["trade_offs"].append("Basic table/image extraction, no AI enhancements")
            
        else:
            # Normal or slow speed - consider accuracy and content types
            recommendation["extraction_method"] = "marker"
            
            # Need tables or images? Must use Marker
            if any(content in content_types for content in ['tables', 'images', 'equations']):
                recommendation["reasoning"].append("Complex content types require full Marker processing")
                
                # Accuracy-based Claude config
                if accuracy_priority == 'research':
                    recommendation["claude_config"] = "research"
                    recommendation["reasoning"].append("Research-quality accuracy requested")
                elif accuracy_priority == 'high':
                    recommendation["claude_config"] = "accuracy"
                    recommendation["reasoning"].append("High accuracy with table analysis")
                elif 'tables' in content_types:
                    recommendation["claude_config"] = "tables_only"
                    recommendation["reasoning"].append("Table content detected - enabling table analysis")
                else:
                    recommendation["claude_config"] = "minimal"
                    recommendation["reasoning"].append("Basic Claude enhancements for accuracy")
            else:
                # Text-only content
                if accuracy_priority in ['basic']:
                    recommendation["claude_config"] = "disabled"
                    recommendation["reasoning"].append("Basic accuracy sufficient for text-only content")
                else:
                    recommendation["claude_config"] = "minimal"
                    recommendation["reasoning"].append("Minimal Claude features for text accuracy")
        
        # Check if recommendation is feasible with current system
        system_resources = self.get_fresh_system_resources()
        system_recommendation, _, system_reasoning = self.resource_analyzer.recommend_claude_config(system_resources)
        
        # Adjust if system can't handle requested config
        if (recommendation["claude_config"] != "disabled" and 
            system_recommendation == "disabled"):
            recommendation["claude_config"] = "disabled"
            recommendation["reasoning"].append("System resources insufficient for Claude features")
            recommendation["trade_offs"].append("Claude features disabled due to system limitations")
        
        # Add system context
        recommendation["system_context"] = {
            "system_recommendation": system_recommendation,
            "system_reasoning": system_reasoning,
            "adjusted_for_system": recommendation["claude_config"] != "disabled" and system_recommendation == "disabled"
        }
        
        return recommendation
    
    async def validate_claude_config_for_agent(self, config_name: str) -> Dict[str, Any]:
        """Validate a Claude configuration and provide agent-friendly feedback."""
        
        try:
            config = get_recommended_config_for_use_case(config_name)
        except:
            return {
                "valid": False,
                "error": f"Unknown configuration: {config_name}",
                "available_configs": ["disabled", "minimal", "tables_only", "accuracy", "research"]
            }
        
        validation = validate_claude_config(config)
        system_resources = self.get_fresh_system_resources()
        
        # Check if config is appropriate for current system
        recommended_config, _, reasoning = self.resource_analyzer.recommend_claude_config(system_resources)
        
        system_appropriate = config_name == recommended_config
        
        # Add agent-specific guidance
        agent_guidance = {
            "config_name": config_name,
            "system_appropriate": system_appropriate,
            "performance_impact": validation["estimated_slowdown"],
            "features_enabled": [],
            "resource_requirements": {},
            "alternatives": []
        }
        
        # List enabled features
        if config.enable_claude_features:
            if config.enable_section_verification:
                agent_guidance["features_enabled"].append("section_verification")
            if config.enable_table_merge_analysis:
                agent_guidance["features_enabled"].append("table_merge_analysis")
            if config.enable_content_validation:
                agent_guidance["features_enabled"].append("content_validation")
            if config.enable_structure_analysis:
                agent_guidance["features_enabled"].append("structure_analysis")
        
        # Resource requirements
        if validation["estimated_slowdown"] == "high":
            agent_guidance["resource_requirements"] = {
                "memory_gb": "16+",
                "cpu_cores": "8+",
                "processing_time_multiplier": "3-5x"
            }
        elif validation["estimated_slowdown"] == "medium":
            agent_guidance["resource_requirements"] = {
                "memory_gb": "8+", 
                "cpu_cores": "4+",
                "processing_time_multiplier": "2-3x"
            }
        else:
            agent_guidance["resource_requirements"] = {
                "memory_gb": "4+",
                "cpu_cores": "2+", 
                "processing_time_multiplier": "1.2-2x"
            }
        
        # Suggest alternatives if not appropriate
        if not system_appropriate:
            agent_guidance["alternatives"] = [recommended_config]
            if recommended_config != "disabled":
                agent_guidance["alternatives"].append("disabled")
        
        return {
            "validation": validation,
            "agent_guidance": agent_guidance,
            "system_recommendation": recommended_config,
            "system_reasoning": reasoning
        }

# MCP Tool Definitions for Agents
MCP_TOOLS = {
    "convert_pdf": {
        "description": "Convert PDF to Markdown with optional Claude enhancements. Automatically selects optimal Claude configuration based on system resources unless specified.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the PDF file to convert"
                },
                "claude_config": {
                    "type": "string", 
                    "enum": ["disabled", "minimal", "tables_only", "accuracy", "research"],
                    "description": "Claude configuration preset. If not specified, automatically selected based on system resources."
                },
                "check_system_resources": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to check system resources before processing. Recommended for optimal performance."
                },
                "force_config": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use specified claude_config even if system resources suggest otherwise."
                },
                "extraction_method": {
                    "type": "string",
                    "enum": ["marker", "pymupdf4llm"],
                    "default": "marker",
                    "description": "Extraction method: 'marker' for full processing with tables/images/Claude features, 'pymupdf4llm' for fastest text-only extraction."
                }
            },
            "required": ["file_path"]
        }
    },
    "get_system_resources": {
        "description": "Check current system resources (CPU, memory, disk, Claude CLI availability) to determine optimal Claude configuration.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "validate_claude_config": {
        "description": "Validate a Claude configuration against current system resources and get performance estimates.",
        "parameters": {
            "type": "object",
            "properties": {
                "config_name": {
                    "type": "string",
                    "enum": ["disabled", "minimal", "tables_only", "accuracy", "research"],
                    "description": "Claude configuration to validate"
                }
            },
            "required": ["config_name"]
        }
    },
    "recommend_extraction_strategy": {
        "description": "Get intelligent recommendations for extraction method and Claude config based on user requirements (speed, accuracy, content types).",
        "parameters": {
            "type": "object",
            "properties": {
                "speed_priority": {
                    "type": "string",
                    "enum": ["fastest", "fast", "normal", "slow"],
                    "default": "normal",
                    "description": "Speed requirement: 'fastest' uses PyMuPDF4LLM, 'fast' uses Marker without Claude, 'normal'/'slow' enable Claude features"
                },
                "accuracy_priority": {
                    "type": "string", 
                    "enum": ["basic", "normal", "high", "research"],
                    "default": "normal",
                    "description": "Accuracy requirement: affects Claude configuration selection"
                },
                "content_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["text", "tables", "images", "equations"]
                    },
                    "default": ["text"],
                    "description": "Expected content types in the PDF - affects extraction method selection"
                }
            },
            "required": []
        }
    }
}

# Example MCP Server Usage
async def demo_mcp_server():
    """Demonstrate MCP server functionality for agents."""
    
    server = MarkerMCPServer()
    
    print("=== MCP Server Demo for Agents ===\n")
    
    # 1. Check system resources
    print("1. Checking system resources...")
    resources = await server.get_system_resources_for_agent()
    print(f"Resource level: {resources['interpretation']['resource_level']}")
    print(f"Recommended config: {resources['interpretation']['recommended_config']}")
    print(f"Claude feasible: {resources['interpretation']['claude_feasible']}")
    
    if resources['interpretation']['limitations']:
        print(f"Limitations: {', '.join(resources['interpretation']['limitations'])}")
    
    print()
    
    # 2. Validate different configs
    configs_to_test = ["minimal", "accuracy", "research"]
    
    for config in configs_to_test:
        print(f"2. Validating '{config}' configuration...")
        validation = await server.validate_claude_config_for_agent(config)
        
        guidance = validation['agent_guidance']
        print(f"   System appropriate: {guidance['system_appropriate']}")
        print(f"   Performance impact: {guidance['performance_impact']}")
        print(f"   Features: {', '.join(guidance['features_enabled']) if guidance['features_enabled'] else 'none'}")
        
        if not guidance['system_appropriate']:
            print(f"   Recommended instead: {validation['system_recommendation']}")
        print()
    
    # 3. User requirement example: "I only need to download the pdf quickly"
    print("3. Example: User wants fastest PDF download...")
    strategy = await server.recommend_extraction_strategy({
        "speed_priority": "fastest",
        "accuracy_priority": "basic",
        "content_types": ["text"]
    })
    
    print(f"   Recommended method: {strategy['extraction_method']}")
    print(f"   Recommended config: {strategy['claude_config']}")
    print(f"   Reasoning: {'; '.join(strategy['reasoning'])}")
    print(f"   Trade-offs: {'; '.join(strategy['trade_offs'])}")
    print()
    
    # 4. Mock PDF conversion with recommended strategy
    print("4. Mock PDF conversion using recommended strategy...")
    conversion = await server.convert_pdf_with_claude_intelligence(
        "sample.pdf",  # Mock file
        claude_config=strategy['claude_config'],
        extraction_method=strategy['extraction_method'],
        check_system_resources=True
    )
    
    print(f"   Method used: {conversion['extraction_method']}")
    print(f"   Config used: {conversion['claude_config_used']}")
    print(f"   Estimated time: {conversion['performance_estimate']['estimated_time']}s")
    print(f"   Status: {conversion['conversion_result']['status']}")
    print(f"   Note: {conversion['conversion_result']['note']}")


async def validate():
    """Validate server configuration"""
    result = await capabilities()
    assert "marker" in result.lower()
    print(" Server validation passed")


if __name__ == "__main__":
    asyncio.run(demo_mcp_server())