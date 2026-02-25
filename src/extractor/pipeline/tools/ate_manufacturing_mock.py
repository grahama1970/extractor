"""
Mock data generator for avionics manufacturing Automated Test Equipment (ATE) results.

Generates realistic test results from ATE stations testing F-35 Line Replaceable
Units (LRUs). Output format is IEEE 1671 ATML-inspired, simplified to JSON/CSV.

Usage:
    python -m extractor.pipeline.tools.ate_manufacturing_mock --lru MISSION_COMPUTER --count 10
    python -m extractor.pipeline.tools.ate_manufacturing_mock --lru POWER_SUPPLY --count 30 --format csv --output shift.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LRUType(str, Enum):
    MISSION_COMPUTER = "MISSION_COMPUTER"
    RADAR_PROCESSOR = "RADAR_PROCESSOR"
    EW_SUITE = "EW_SUITE"
    DISPLAY_PROCESSOR = "DISPLAY_PROCESSOR"
    CNI_MODULE = "CNI_MODULE"
    POWER_SUPPLY = "POWER_SUPPLY"
    SENSOR_FUSION = "SENSOR_FUSION"
    STORES_MANAGEMENT = "STORES_MANAGEMENT"


class OverallResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ABORT = "ABORT"
    RETEST = "RETEST"


class StepResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MARGINAL = "MARGINAL"


class MeasurementType(str, Enum):
    VOLTAGE = "VOLTAGE"
    CURRENT = "CURRENT"
    RESISTANCE = "RESISTANCE"
    FREQUENCY = "FREQUENCY"
    TIMING = "TIMING"
    BIT_ERROR_RATE = "BIT_ERROR_RATE"
    SIGNAL_LEVEL = "SIGNAL_LEVEL"
    TEMPERATURE = "TEMPERATURE"
    LOGIC_STATE = "LOGIC_STATE"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class UUTInfo:
    part_number: str
    serial_number: str
    nomenclature: str
    lru_type: str


@dataclass
class Environment:
    temperature_c: float
    humidity_pct: float
    altitude_ft: float


@dataclass
class TestStep:
    step_id: int
    step_name: str
    measurement_type: str
    measured_value: float
    unit: str
    lower_limit: float
    upper_limit: float
    result: str
    test_time_ms: int


@dataclass
class TestResult:
    session_id: str
    timestamp: str
    station_id: str
    operator_id: str
    uut_info: UUTInfo
    test_program: str
    overall_result: str
    test_steps: List[TestStep]
    environment: Environment
    duration_seconds: int


# ---------------------------------------------------------------------------
# Test step templates per LRU type
# ---------------------------------------------------------------------------

# Each entry: (step_name, measurement_type, unit, nominal, lower, upper, time_ms_range)
# nominal is the centre value; generator adds noise around it.

_MISSION_COMPUTER_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    # --- Power ---
    ("Power Supply Input Voltage 28VDC", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current Standby", "CURRENT", "A", 2.1, 0.5, 4.0, (300, 600)),
    ("Input Current Full Load", "CURRENT", "A", 12.5, 2.0, 15.0, (400, 800)),
    ("28VDC Ripple Peak-to-Peak", "VOLTAGE", "mV", 22.0, 0.0, 50.0, (500, 1000)),
    ("Power Supply Transient Response", "TIMING", "ms", 1.2, 0.0, 5.0, (600, 1200)),
    ("3.3V Rail Voltage", "VOLTAGE", "V", 3.30, 3.23, 3.37, (150, 300)),
    ("5V Rail Voltage", "VOLTAGE", "V", 5.00, 4.90, 5.10, (150, 300)),
    ("12V Rail Voltage", "VOLTAGE", "V", 12.00, 11.76, 12.24, (150, 300)),
    ("Power Sequencing Delay", "TIMING", "ms", 45.0, 10.0, 100.0, (300, 600)),
    ("Inrush Current Peak", "CURRENT", "A", 35.0, 0.0, 50.0, (200, 500)),
    # --- Processor ---
    ("CPU Clock Frequency", "FREQUENCY", "GHz", 1.500, 1.4985, 1.5015, (1000, 2000)),
    ("Memory BIT Pass/Fail", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 12000)),
    ("Boot Time to OS Ready", "TIMING", "s", 5.5, 0.0, 8.0, (8000, 15000)),
    ("L2 Cache Latency", "TIMING", "ns", 4.2, 0.0, 8.0, (800, 1500)),
    ("Floating Point MFLOPS", "FREQUENCY", "MHz", 4500.0, 4000.0, 6000.0, (2000, 4000)),
    ("Watchdog Timer Period", "TIMING", "ms", 500.0, 490.0, 510.0, (300, 600)),
    ("NVRAM Retention Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("RTC Drift 24h Equivalent", "TIMING", "ms", 12.0, 0.0, 50.0, (1000, 2000)),
    # --- I/O ---
    ("1553B Bus A Timing", "TIMING", "ns", 0.0, -500.0, 500.0, (600, 1200)),
    ("1553B Bus B Timing", "TIMING", "ns", 5.0, -500.0, 500.0, (600, 1200)),
    ("1553B Bus A Amplitude", "VOLTAGE", "V", 9.0, 6.0, 14.0, (300, 600)),
    ("1553B Bus B Amplitude", "VOLTAGE", "V", 9.1, 6.0, 14.0, (300, 600)),
    ("1553B Remote Terminal Response", "TIMING", "us", 5.5, 0.0, 12.0, (500, 1000)),
    ("Ethernet 1 Throughput", "FREQUENCY", "Mbps", 945.0, 900.0, 1000.0, (3000, 6000)),
    ("Ethernet 2 Throughput", "FREQUENCY", "Mbps", 942.0, 900.0, 1000.0, (3000, 6000)),
    ("Fibre Channel Link Rate", "FREQUENCY", "Gbps", 8.49, 8.0, 8.6, (2000, 4000)),
    ("Fibre Channel BER", "BIT_ERROR_RATE", "ratio", 1e-13, 0.0, 1e-10, (5000, 10000)),
    ("ARINC 429 TX Rate High", "FREQUENCY", "kHz", 100.0, 99.0, 101.0, (400, 800)),
    ("ARINC 429 TX Rate Low", "FREQUENCY", "kHz", 12.5, 12.0, 13.0, (400, 800)),
    ("Discrete Input Threshold High", "VOLTAGE", "V", 18.0, 15.0, 32.0, (200, 400)),
    ("Discrete Input Threshold Low", "VOLTAGE", "V", 3.0, 0.0, 6.0, (200, 400)),
    ("Discrete Output Drive High", "VOLTAGE", "V", 27.5, 22.0, 32.0, (200, 400)),
    ("Discrete Output Drive Low", "VOLTAGE", "V", 0.3, 0.0, 2.0, (200, 400)),
    ("RS-422 Channel 1 Data Rate", "FREQUENCY", "kbps", 460.0, 450.0, 470.0, (500, 1000)),
    ("RS-422 Channel 2 Data Rate", "FREQUENCY", "kbps", 461.0, 450.0, 470.0, (500, 1000)),
    ("USB 2.0 Enumeration", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (1000, 2000)),
    ("Video Output HDMI Sync", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (800, 1500)),
    # --- Environmental ---
    ("Cold Soak -40C Power-On", "TEMPERATURE", "\u00b0C", -39.5, -42.0, -38.0, (30000, 60000)),
    ("Hot Soak +71C Operation", "TEMPERATURE", "\u00b0C", 70.8, 69.0, 73.0, (30000, 60000)),
    ("Case Temperature Rise", "TEMPERATURE", "\u00b0C", 18.5, 0.0, 25.0, (10000, 20000)),
    ("Vibration Spectrum Check", "SIGNAL_LEVEL", "grms", 4.8, 0.0, 7.0, (15000, 30000)),
    # --- Functional ---
    ("OFP Load and Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 10000)),
    ("Crypto Module Init", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (2000, 4000)),
    ("BIT Self-Test Complete", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (8000, 15000)),
    ("Mission Data Load Time", "TIMING", "s", 12.0, 0.0, 20.0, (12000, 20000)),
    ("Inter-Processor Bus Latency", "TIMING", "us", 2.3, 0.0, 5.0, (500, 1000)),
    ("DMA Transfer Rate", "FREQUENCY", "MBps", 3200.0, 2800.0, 4000.0, (1000, 2000)),
    ("Interrupt Latency", "TIMING", "us", 0.8, 0.0, 2.0, (300, 600)),
    ("GPIO Port A Loopback", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (500, 1000)),
    ("GPIO Port B Loopback", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (500, 1000)),
    ("Thermal Shutdown Threshold", "TEMPERATURE", "\u00b0C", 95.0, 90.0, 100.0, (5000, 10000)),
    ("Power Consumption Idle", "CURRENT", "W", 45.0, 10.0, 60.0, (500, 1000)),
    ("Power Consumption Full Load", "CURRENT", "W", 180.0, 50.0, 220.0, (500, 1000)),
    ("EMI Conducted Emissions", "SIGNAL_LEVEL", "dBuV", 52.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.02, 0.0, 0.1, (300, 600)),
]

_RADAR_PROCESSOR_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    # --- Power ---
    ("Power Supply 28VDC Input", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current Quiescent", "CURRENT", "A", 3.5, 0.5, 6.0, (300, 600)),
    ("Input Current Full RF", "CURRENT", "A", 28.0, 5.0, 35.0, (400, 800)),
    ("28VDC Ripple", "VOLTAGE", "mV", 18.0, 0.0, 50.0, (400, 800)),
    ("3.3V Rail", "VOLTAGE", "V", 3.30, 3.23, 3.37, (150, 300)),
    ("5V Rail", "VOLTAGE", "V", 5.00, 4.90, 5.10, (150, 300)),
    ("Power Sequencing", "TIMING", "ms", 55.0, 10.0, 120.0, (300, 600)),
    # --- RF Transmit ---
    ("TX Power X-Band Peak", "SIGNAL_LEVEL", "dBm", 43.0, 42.5, 43.5, (2000, 4000)),
    ("TX Power X-Band Average", "SIGNAL_LEVEL", "dBm", 33.0, 32.0, 34.0, (2000, 4000)),
    ("TX Frequency Accuracy 9.0GHz", "FREQUENCY", "MHz", 9000.0, 8999.0, 9001.0, (1000, 2000)),
    ("TX Frequency Accuracy 10.0GHz", "FREQUENCY", "MHz", 10000.0, 9999.0, 10001.0, (1000, 2000)),
    ("TX Phase Noise -80dBc/Hz", "SIGNAL_LEVEL", "dBc/Hz", -82.0, -120.0, -80.0, (3000, 6000)),
    ("TX Pulse Width 1us", "TIMING", "ns", 1000.0, 990.0, 1010.0, (800, 1500)),
    ("TX Pulse Width 10us", "TIMING", "ns", 10000.0, 9950.0, 10050.0, (800, 1500)),
    ("TX Rise Time", "TIMING", "ns", 12.0, 0.0, 20.0, (600, 1200)),
    ("TX Fall Time", "TIMING", "ns", 14.0, 0.0, 20.0, (600, 1200)),
    ("TX Duty Cycle Max", "FREQUENCY", "%", 25.0, 0.0, 30.0, (500, 1000)),
    ("TX Spurious Emissions", "SIGNAL_LEVEL", "dBc", -58.0, -80.0, -50.0, (3000, 6000)),
    ("TX Harmonic 2nd", "SIGNAL_LEVEL", "dBc", -42.0, -80.0, -35.0, (2000, 4000)),
    ("TX Harmonic 3rd", "SIGNAL_LEVEL", "dBc", -48.0, -80.0, -40.0, (2000, 4000)),
    # --- RF Receive ---
    ("RX Noise Figure", "SIGNAL_LEVEL", "dB", 3.2, 0.0, 4.5, (2000, 4000)),
    ("RX Sensitivity MDS", "SIGNAL_LEVEL", "dBm", -108.0, -120.0, -105.0, (3000, 6000)),
    ("RX Dynamic Range", "SIGNAL_LEVEL", "dB", 85.0, 80.0, 100.0, (2000, 4000)),
    ("RX Image Rejection", "SIGNAL_LEVEL", "dB", 55.0, 50.0, 80.0, (2000, 4000)),
    ("RX Frequency Response Flatness", "SIGNAL_LEVEL", "dB", 1.2, 0.0, 2.0, (3000, 6000)),
    ("RX Gain 9.0GHz", "SIGNAL_LEVEL", "dB", 32.0, 30.0, 35.0, (1500, 3000)),
    ("RX Gain 10.0GHz", "SIGNAL_LEVEL", "dB", 31.5, 30.0, 35.0, (1500, 3000)),
    # --- Signal Processing ---
    ("FFT 1024-Point Accuracy", "SIGNAL_LEVEL", "dB", 0.05, 0.0, 0.5, (2000, 4000)),
    ("FFT 4096-Point Accuracy", "SIGNAL_LEVEL", "dB", 0.08, 0.0, 0.5, (3000, 6000)),
    ("Clutter Rejection Ratio", "SIGNAL_LEVEL", "dB", 48.0, 40.0, 60.0, (5000, 10000)),
    ("MTI Improvement Factor", "SIGNAL_LEVEL", "dB", 42.0, 35.0, 55.0, (4000, 8000)),
    ("Doppler Processing Accuracy", "FREQUENCY", "Hz", 5.0, 0.0, 20.0, (3000, 6000)),
    ("Range Resolution", "TIMING", "m", 0.45, 0.0, 1.0, (2000, 4000)),
    ("Angle Accuracy Azimuth", "SIGNAL_LEVEL", "mrad", 1.2, 0.0, 2.0, (3000, 6000)),
    ("Angle Accuracy Elevation", "SIGNAL_LEVEL", "mrad", 1.5, 0.0, 2.5, (3000, 6000)),
    ("Track Initiation Time", "TIMING", "ms", 120.0, 0.0, 250.0, (5000, 10000)),
    ("Simultaneous Tracks Max", "LOGIC_STATE", "count", 24.0, 20.0, 32.0, (4000, 8000)),
    ("ECCM Mode Switch Time", "TIMING", "ms", 8.0, 0.0, 15.0, (2000, 4000)),
    # --- Cooling ---
    ("Liquid Coolant Flow Rate", "FREQUENCY", "L/min", 4.8, 3.5, 6.0, (2000, 4000)),
    ("Coolant Inlet Temperature", "TEMPERATURE", "\u00b0C", 22.0, 15.0, 35.0, (500, 1000)),
    ("Coolant Outlet Temperature", "TEMPERATURE", "\u00b0C", 38.0, 15.0, 50.0, (500, 1000)),
    ("Thermal Resistance Junction", "TEMPERATURE", "\u00b0C/W", 0.35, 0.0, 0.5, (3000, 6000)),
    ("Hot Spot Temperature", "TEMPERATURE", "\u00b0C", 62.0, 0.0, 85.0, (5000, 10000)),
    # --- Digital ---
    ("DSP Clock Frequency", "FREQUENCY", "GHz", 2.000, 1.998, 2.002, (800, 1500)),
    ("Memory BIT", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 12000)),
    ("Boot Time", "TIMING", "s", 8.0, 0.0, 12.0, (8000, 15000)),
    ("1553B Bus Timing", "TIMING", "ns", 2.0, -500.0, 500.0, (600, 1200)),
    ("Fibre Channel Rate", "FREQUENCY", "Gbps", 8.48, 8.0, 8.6, (2000, 4000)),
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (8000, 15000)),
    ("OFP Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("Waveguide VSWR", "SIGNAL_LEVEL", "ratio", 1.15, 1.0, 1.5, (2000, 4000)),
    ("Antenna Port Isolation", "SIGNAL_LEVEL", "dB", 62.0, 55.0, 80.0, (2000, 4000)),
    ("EMI Conducted", "SIGNAL_LEVEL", "dBuV", 48.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.015, 0.0, 0.1, (300, 600)),
    ("Environmental Cold -40C", "TEMPERATURE", "\u00b0C", -39.8, -42.0, -38.0, (30000, 60000)),
    ("Environmental Hot +71C", "TEMPERATURE", "\u00b0C", 70.5, 69.0, 73.0, (30000, 60000)),
]

_EW_SUITE_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    # --- Power ---
    ("28VDC Input", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current", "CURRENT", "A", 18.0, 2.0, 25.0, (300, 600)),
    ("Ripple", "VOLTAGE", "mV", 20.0, 0.0, 50.0, (400, 800)),
    # --- Receiver ---
    ("RWR Sensitivity 2-6GHz", "SIGNAL_LEVEL", "dBm", -65.0, -80.0, -55.0, (3000, 6000)),
    ("RWR Sensitivity 6-18GHz", "SIGNAL_LEVEL", "dBm", -60.0, -80.0, -50.0, (3000, 6000)),
    ("RWR Frequency Coverage Low", "FREQUENCY", "GHz", 2.0, 1.8, 2.2, (1000, 2000)),
    ("RWR Frequency Coverage High", "FREQUENCY", "GHz", 18.0, 17.5, 18.5, (1000, 2000)),
    ("Direction Finding Accuracy Az", "SIGNAL_LEVEL", "deg", 2.5, 0.0, 5.0, (4000, 8000)),
    ("Direction Finding Accuracy El", "SIGNAL_LEVEL", "deg", 4.0, 0.0, 8.0, (4000, 8000)),
    ("Instantaneous Bandwidth", "FREQUENCY", "MHz", 500.0, 400.0, 600.0, (2000, 4000)),
    ("POI 2-18GHz", "SIGNAL_LEVEL", "%", 98.0, 95.0, 100.0, (5000, 10000)),
    ("Amplitude Accuracy", "SIGNAL_LEVEL", "dB", 1.5, 0.0, 3.0, (2000, 4000)),
    # --- Jammer ---
    ("Jammer Output Power Low Band", "SIGNAL_LEVEL", "dBm", 38.0, 35.0, 42.0, (3000, 6000)),
    ("Jammer Output Power High Band", "SIGNAL_LEVEL", "dBm", 35.0, 32.0, 40.0, (3000, 6000)),
    ("Jammer Response Time", "TIMING", "us", 80.0, 0.0, 150.0, (2000, 4000)),
    ("Noise Jamming Flatness", "SIGNAL_LEVEL", "dB", 2.0, 0.0, 4.0, (3000, 6000)),
    ("DRFM Loop Delay", "TIMING", "ns", 45.0, 0.0, 100.0, (2000, 4000)),
    ("DRFM Spurious Free Range", "SIGNAL_LEVEL", "dBc", -52.0, -80.0, -45.0, (3000, 6000)),
    ("Modulation Accuracy AM", "SIGNAL_LEVEL", "%", 1.5, 0.0, 3.0, (2000, 4000)),
    ("Modulation Accuracy FM", "FREQUENCY", "kHz", 2.0, 0.0, 5.0, (2000, 4000)),
    ("Technique Switch Time", "TIMING", "us", 5.0, 0.0, 10.0, (1500, 3000)),
    # --- ELINT ---
    ("Pulse Width Accuracy", "TIMING", "ns", 8.0, 0.0, 25.0, (2000, 4000)),
    ("PRI Accuracy", "TIMING", "ns", 15.0, 0.0, 50.0, (2000, 4000)),
    ("Frequency Measurement Accuracy", "FREQUENCY", "MHz", 0.8, 0.0, 2.0, (2000, 4000)),
    ("Emitter Classification Rate", "SIGNAL_LEVEL", "%", 96.0, 90.0, 100.0, (5000, 10000)),
    ("Threat Library Load Time", "TIMING", "s", 3.5, 0.0, 8.0, (3000, 6000)),
    ("Simultaneous Emitter Tracking", "LOGIC_STATE", "count", 120.0, 80.0, 200.0, (4000, 8000)),
    # --- Digital / Integration ---
    ("1553B Bus Timing", "TIMING", "ns", 3.0, -500.0, 500.0, (600, 1200)),
    ("Fibre Channel Rate", "FREQUENCY", "Gbps", 8.50, 8.0, 8.6, (2000, 4000)),
    ("Boot Time", "TIMING", "s", 6.0, 0.0, 10.0, (6000, 12000)),
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (8000, 15000)),
    ("OFP Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("Crypto Module Init", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (2000, 4000)),
    ("Cooling Flow Rate", "FREQUENCY", "L/min", 5.2, 4.0, 7.0, (1000, 2000)),
    ("Case Temperature", "TEMPERATURE", "\u00b0C", 48.0, 0.0, 65.0, (3000, 6000)),
    ("EMI Conducted", "SIGNAL_LEVEL", "dBuV", 50.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.018, 0.0, 0.1, (300, 600)),
    ("Environmental Cold -40C", "TEMPERATURE", "\u00b0C", -39.6, -42.0, -38.0, (30000, 60000)),
    ("Environmental Hot +71C", "TEMPERATURE", "\u00b0C", 70.7, 69.0, 73.0, (30000, 60000)),
]

_POWER_SUPPLY_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    # --- Input ---
    ("Input Voltage 28VDC Nominal", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Voltage Low Line", "VOLTAGE", "V", 22.0, 20.0, 24.0, (200, 500)),
    ("Input Voltage High Line", "VOLTAGE", "V", 32.0, 30.0, 34.0, (200, 500)),
    ("Inrush Current", "CURRENT", "A", 42.0, 0.0, 60.0, (300, 600)),
    ("No-Load Input Current", "CURRENT", "A", 0.15, 0.0, 0.5, (200, 400)),
    # --- Output Voltages ---
    ("3.3V Output Voltage", "VOLTAGE", "V", 3.30, 3.234, 3.366, (200, 400)),
    ("3.3V Load Regulation", "VOLTAGE", "%", 0.5, 0.0, 2.0, (500, 1000)),
    ("3.3V Ripple", "VOLTAGE", "mV", 12.0, 0.0, 33.0, (400, 800)),
    ("3.3V Max Current", "CURRENT", "A", 9.8, 0.0, 10.0, (500, 1000)),
    ("5V Output Voltage", "VOLTAGE", "V", 5.00, 4.90, 5.10, (200, 400)),
    ("5V Load Regulation", "VOLTAGE", "%", 0.4, 0.0, 2.0, (500, 1000)),
    ("5V Ripple", "VOLTAGE", "mV", 15.0, 0.0, 50.0, (400, 800)),
    ("5V Max Current", "CURRENT", "A", 14.5, 0.0, 15.0, (500, 1000)),
    ("12V Output Voltage", "VOLTAGE", "V", 12.00, 11.76, 12.24, (200, 400)),
    ("12V Load Regulation", "VOLTAGE", "%", 0.6, 0.0, 2.0, (500, 1000)),
    ("12V Ripple", "VOLTAGE", "mV", 25.0, 0.0, 120.0, (400, 800)),
    ("12V Max Current", "CURRENT", "A", 4.8, 0.0, 5.0, (500, 1000)),
    ("28V Output Voltage", "VOLTAGE", "V", 28.0, 27.44, 28.56, (200, 400)),
    ("28V Load Regulation", "VOLTAGE", "%", 0.3, 0.0, 2.0, (500, 1000)),
    ("28V Ripple", "VOLTAGE", "mV", 30.0, 0.0, 140.0, (400, 800)),
    ("28V Max Current", "CURRENT", "A", 7.8, 0.0, 8.0, (500, 1000)),
    # --- Efficiency / Power ---
    ("Efficiency Full Load", "SIGNAL_LEVEL", "%", 88.0, 85.0, 98.0, (2000, 4000)),
    ("Efficiency Half Load", "SIGNAL_LEVEL", "%", 91.0, 85.0, 98.0, (2000, 4000)),
    ("Power Factor", "SIGNAL_LEVEL", "ratio", 0.97, 0.90, 1.0, (1000, 2000)),
    ("Total Output Power", "CURRENT", "W", 280.0, 0.0, 350.0, (1000, 2000)),
    # --- Protection ---
    ("Overcurrent Trip 3.3V", "CURRENT", "A", 12.0, 10.5, 15.0, (1000, 2000)),
    ("Overcurrent Trip 5V", "CURRENT", "A", 18.0, 16.0, 22.0, (1000, 2000)),
    ("Overcurrent Trip 12V", "CURRENT", "A", 6.5, 5.5, 8.0, (1000, 2000)),
    ("Overvoltage Trip 3.3V", "VOLTAGE", "V", 3.7, 3.5, 4.0, (800, 1500)),
    ("Overvoltage Trip 5V", "VOLTAGE", "V", 5.6, 5.3, 6.0, (800, 1500)),
    ("Overvoltage Trip 12V", "VOLTAGE", "V", 13.5, 13.0, 14.5, (800, 1500)),
    ("Thermal Shutdown Temperature", "TEMPERATURE", "\u00b0C", 105.0, 100.0, 115.0, (5000, 10000)),
    ("Short Circuit Recovery", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (2000, 4000)),
    # --- EMI ---
    ("Conducted Emissions CE102", "SIGNAL_LEVEL", "dBuV", 52.0, 0.0, 60.0, (5000, 10000)),
    ("Radiated Emissions RE102", "SIGNAL_LEVEL", "dBuV/m", 30.0, 0.0, 40.0, (5000, 10000)),
    # --- Environmental ---
    ("Cold Start -40C", "TEMPERATURE", "\u00b0C", -39.7, -42.0, -38.0, (30000, 60000)),
    ("Hot Operation +85C", "TEMPERATURE", "\u00b0C", 84.5, 83.0, 87.0, (30000, 60000)),
    ("Altitude Operation 50kft", "SIGNAL_LEVEL", "kft", 50.0, 48.0, 52.0, (10000, 20000)),
    # --- Miscellaneous ---
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("Power Sequencing", "TIMING", "ms", 35.0, 10.0, 80.0, (300, 600)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.01, 0.0, 0.1, (300, 600)),
]

_CNI_MODULE_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    # --- Power ---
    ("28VDC Input", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current", "CURRENT", "A", 8.5, 1.0, 12.0, (300, 600)),
    ("Ripple", "VOLTAGE", "mV", 18.0, 0.0, 50.0, (400, 800)),
    # --- Radio TX ---
    ("UHF TX Power High", "SIGNAL_LEVEL", "dBm", 37.0, 35.0, 40.0, (2000, 4000)),
    ("UHF TX Power Low", "SIGNAL_LEVEL", "dBm", 20.0, 18.0, 23.0, (2000, 4000)),
    ("VHF TX Power", "SIGNAL_LEVEL", "dBm", 36.0, 34.0, 39.0, (2000, 4000)),
    ("TX Frequency Accuracy UHF", "FREQUENCY", "Hz", 5.0, 0.0, 25.0, (1000, 2000)),
    ("TX Frequency Accuracy VHF", "FREQUENCY", "Hz", 3.0, 0.0, 25.0, (1000, 2000)),
    ("TX Spurious Emissions", "SIGNAL_LEVEL", "dBc", -55.0, -80.0, -50.0, (3000, 6000)),
    ("TX Modulation Deviation FM", "FREQUENCY", "kHz", 5.0, 4.5, 5.5, (1500, 3000)),
    ("TX Rise Time", "TIMING", "us", 2.0, 0.0, 5.0, (800, 1500)),
    ("HAVE QUICK Hop Rate", "FREQUENCY", "hops/s", 340.0, 300.0, 400.0, (2000, 4000)),
    # --- Radio RX ---
    ("UHF RX Sensitivity", "SIGNAL_LEVEL", "dBm", -110.0, -120.0, -107.0, (3000, 6000)),
    ("VHF RX Sensitivity", "SIGNAL_LEVEL", "dBm", -112.0, -120.0, -107.0, (3000, 6000)),
    ("RX Selectivity Adjacent", "SIGNAL_LEVEL", "dB", 65.0, 60.0, 80.0, (2000, 4000)),
    ("RX Intermod Rejection", "SIGNAL_LEVEL", "dB", 70.0, 65.0, 90.0, (2000, 4000)),
    ("Audio Output Level", "SIGNAL_LEVEL", "dBm", 0.0, -3.0, 3.0, (500, 1000)),
    ("Squelch Threshold", "SIGNAL_LEVEL", "dBm", -105.0, -115.0, -100.0, (1000, 2000)),
    # --- GPS ---
    ("GPS Cold Acquisition Time", "TIMING", "s", 35.0, 0.0, 60.0, (60000, 120000)),
    ("GPS Warm Acquisition Time", "TIMING", "s", 5.0, 0.0, 12.0, (12000, 25000)),
    ("GPS Position Accuracy CEP", "SIGNAL_LEVEL", "m", 2.5, 0.0, 5.0, (10000, 20000)),
    ("GPS Velocity Accuracy", "SIGNAL_LEVEL", "m/s", 0.05, 0.0, 0.1, (5000, 10000)),
    ("GPS Anti-Jam Margin", "SIGNAL_LEVEL", "dB", 45.0, 40.0, 65.0, (5000, 10000)),
    ("GPS P(Y) Code Tracking", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 10000)),
    ("GPS M-Code Acquisition", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 10000)),
    ("GPS 1PPS Accuracy", "TIMING", "ns", 15.0, 0.0, 50.0, (2000, 4000)),
    # --- IFF ---
    ("IFF Mode 5 Crypto Init", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("IFF Interrogator TX Power", "SIGNAL_LEVEL", "dBm", 33.0, 30.0, 36.0, (2000, 4000)),
    ("IFF Transponder TX Power", "SIGNAL_LEVEL", "dBm", 27.0, 24.0, 30.0, (2000, 4000)),
    ("IFF Interrogator Timing", "TIMING", "us", 3.5, 2.0, 5.0, (1500, 3000)),
    ("IFF Transponder Reply Delay", "TIMING", "us", 3.0, 2.0, 4.0, (1500, 3000)),
    ("IFF Mode S Address", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (1000, 2000)),
    ("IFF Side Lobe Suppression", "SIGNAL_LEVEL", "dB", 25.0, 20.0, 35.0, (2000, 4000)),
    # --- Digital / Integration ---
    ("1553B Bus Timing", "TIMING", "ns", 1.0, -500.0, 500.0, (600, 1200)),
    ("Ethernet Throughput", "FREQUENCY", "Mbps", 940.0, 900.0, 1000.0, (3000, 6000)),
    ("Boot Time", "TIMING", "s", 7.0, 0.0, 12.0, (7000, 14000)),
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (8000, 15000)),
    ("OFP Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("COMSEC Key Load", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (2000, 4000)),
    ("Antenna Port VSWR", "SIGNAL_LEVEL", "ratio", 1.3, 1.0, 2.0, (1500, 3000)),
    ("EMI Conducted", "SIGNAL_LEVEL", "dBuV", 50.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.02, 0.0, 0.1, (300, 600)),
    ("Environmental Cold -40C", "TEMPERATURE", "\u00b0C", -39.4, -42.0, -38.0, (30000, 60000)),
    ("Environmental Hot +71C", "TEMPERATURE", "\u00b0C", 70.9, 69.0, 73.0, (30000, 60000)),
]

_DISPLAY_PROCESSOR_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    ("28VDC Input", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current", "CURRENT", "A", 6.0, 1.0, 9.0, (300, 600)),
    ("3.3V Rail", "VOLTAGE", "V", 3.30, 3.23, 3.37, (150, 300)),
    ("5V Rail", "VOLTAGE", "V", 5.00, 4.90, 5.10, (150, 300)),
    ("GPU Clock Frequency", "FREQUENCY", "GHz", 1.200, 1.194, 1.206, (800, 1500)),
    ("GPU Memory Bandwidth", "FREQUENCY", "GBps", 128.0, 110.0, 150.0, (2000, 4000)),
    ("Video Output 1 Sync", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (500, 1000)),
    ("Video Output 2 Sync", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (500, 1000)),
    ("Video Output Resolution", "FREQUENCY", "pixels", 2048.0, 2048.0, 2048.0, (300, 600)),
    ("Frame Rate", "FREQUENCY", "Hz", 60.0, 58.0, 62.0, (500, 1000)),
    ("Symbol Generation Rate", "FREQUENCY", "sym/s", 5000.0, 4500.0, 6000.0, (2000, 4000)),
    ("Luminance Range", "SIGNAL_LEVEL", "cd/m2", 350.0, 300.0, 500.0, (1000, 2000)),
    ("Contrast Ratio", "SIGNAL_LEVEL", "ratio", 800.0, 500.0, 1200.0, (1000, 2000)),
    ("Color Accuracy Delta-E", "SIGNAL_LEVEL", "dE", 1.8, 0.0, 3.0, (2000, 4000)),
    ("Touch Input Accuracy", "SIGNAL_LEVEL", "mm", 1.2, 0.0, 3.0, (1500, 3000)),
    ("Touch Response Time", "TIMING", "ms", 12.0, 0.0, 25.0, (800, 1500)),
    ("NVIS Compatibility", "SIGNAL_LEVEL", "NR", 0.15, 0.0, 0.3, (2000, 4000)),
    ("Map Rendering Latency", "TIMING", "ms", 35.0, 0.0, 60.0, (3000, 6000)),
    ("3D Terrain Update Rate", "FREQUENCY", "Hz", 30.0, 25.0, 60.0, (2000, 4000)),
    ("1553B Bus Timing", "TIMING", "ns", 2.0, -500.0, 500.0, (600, 1200)),
    ("Ethernet Throughput", "FREQUENCY", "Mbps", 938.0, 900.0, 1000.0, (3000, 6000)),
    ("Fibre Channel Rate", "FREQUENCY", "Gbps", 8.48, 8.0, 8.6, (2000, 4000)),
    ("Memory BIT", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 12000)),
    ("Boot Time", "TIMING", "s", 6.5, 0.0, 10.0, (6000, 12000)),
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (8000, 15000)),
    ("OFP Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("Backlight Uniformity", "SIGNAL_LEVEL", "%", 88.0, 80.0, 100.0, (2000, 4000)),
    ("Sunlight Readability", "SIGNAL_LEVEL", "cd/m2", 1000.0, 800.0, 1500.0, (2000, 4000)),
    ("Power Consumption", "CURRENT", "W", 85.0, 20.0, 120.0, (500, 1000)),
    ("Case Temperature", "TEMPERATURE", "\u00b0C", 42.0, 0.0, 55.0, (3000, 6000)),
    ("EMI Conducted", "SIGNAL_LEVEL", "dBuV", 48.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.02, 0.0, 0.1, (300, 600)),
    ("Environmental Cold -40C", "TEMPERATURE", "\u00b0C", -39.3, -42.0, -38.0, (30000, 60000)),
    ("Environmental Hot +71C", "TEMPERATURE", "\u00b0C", 70.6, 69.0, 73.0, (30000, 60000)),
]

_SENSOR_FUSION_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    ("28VDC Input", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current", "CURRENT", "A", 10.0, 2.0, 14.0, (300, 600)),
    ("3.3V Rail", "VOLTAGE", "V", 3.30, 3.23, 3.37, (150, 300)),
    ("CPU Clock Frequency", "FREQUENCY", "GHz", 1.800, 1.797, 1.803, (800, 1500)),
    ("Memory BIT", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 12000)),
    ("Boot Time", "TIMING", "s", 7.0, 0.0, 10.0, (7000, 14000)),
    ("Sensor Input Channels Active", "LOGIC_STATE", "count", 16.0, 16.0, 16.0, (2000, 4000)),
    ("Data Fusion Latency", "TIMING", "ms", 8.0, 0.0, 15.0, (3000, 6000)),
    ("Track Correlation Accuracy", "SIGNAL_LEVEL", "%", 96.0, 90.0, 100.0, (5000, 10000)),
    ("Track Update Rate", "FREQUENCY", "Hz", 20.0, 15.0, 30.0, (2000, 4000)),
    ("Multi-Sensor Track Capacity", "LOGIC_STATE", "count", 200.0, 150.0, 300.0, (3000, 6000)),
    ("Kinematic Filter Accuracy", "SIGNAL_LEVEL", "m", 5.0, 0.0, 10.0, (4000, 8000)),
    ("Classification Confidence", "SIGNAL_LEVEL", "%", 92.0, 85.0, 100.0, (5000, 10000)),
    ("Threat Prioritization Latency", "TIMING", "ms", 15.0, 0.0, 30.0, (3000, 6000)),
    ("Radar Data Input Rate", "FREQUENCY", "Mbps", 450.0, 400.0, 500.0, (2000, 4000)),
    ("EW Data Input Rate", "FREQUENCY", "Mbps", 200.0, 150.0, 250.0, (2000, 4000)),
    ("Datalink Input Rate", "FREQUENCY", "Mbps", 100.0, 80.0, 120.0, (2000, 4000)),
    ("1553B Bus Timing", "TIMING", "ns", 3.0, -500.0, 500.0, (600, 1200)),
    ("Fibre Channel Rate", "FREQUENCY", "Gbps", 8.49, 8.0, 8.6, (2000, 4000)),
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (8000, 15000)),
    ("OFP Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("Crypto Module Init", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (2000, 4000)),
    ("Power Consumption", "CURRENT", "W", 120.0, 30.0, 160.0, (500, 1000)),
    ("Case Temperature", "TEMPERATURE", "\u00b0C", 52.0, 0.0, 65.0, (3000, 6000)),
    ("Cooling Flow Rate", "FREQUENCY", "L/min", 3.5, 2.5, 5.0, (1000, 2000)),
    ("EMI Conducted", "SIGNAL_LEVEL", "dBuV", 50.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.02, 0.0, 0.1, (300, 600)),
    ("Environmental Cold -40C", "TEMPERATURE", "\u00b0C", -39.5, -42.0, -38.0, (30000, 60000)),
    ("Environmental Hot +71C", "TEMPERATURE", "\u00b0C", 70.8, 69.0, 73.0, (30000, 60000)),
]

_STORES_MANAGEMENT_STEPS: List[Tuple[str, str, str, float, float, float, Tuple[int, int]]] = [
    ("28VDC Input", "VOLTAGE", "V", 28.0, 22.0, 32.0, (200, 500)),
    ("Input Current", "CURRENT", "A", 5.0, 1.0, 8.0, (300, 600)),
    ("3.3V Rail", "VOLTAGE", "V", 3.30, 3.23, 3.37, (150, 300)),
    ("5V Rail", "VOLTAGE", "V", 5.00, 4.90, 5.10, (150, 300)),
    ("CPU Clock", "FREQUENCY", "GHz", 1.200, 1.198, 1.202, (800, 1500)),
    ("Memory BIT", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 12000)),
    ("Boot Time", "TIMING", "s", 4.5, 0.0, 8.0, (4000, 8000)),
    ("Station Count Active", "LOGIC_STATE", "count", 11.0, 11.0, 11.0, (1000, 2000)),
    ("Release Pulse Timing", "TIMING", "ms", 15.0, 10.0, 20.0, (2000, 4000)),
    ("Release Pulse Voltage", "VOLTAGE", "V", 28.0, 26.0, 30.0, (500, 1000)),
    ("Jettison Command Verify", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (1500, 3000)),
    ("Safety Interlock Chain", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (1000, 2000)),
    ("Arming Discrete Timing", "TIMING", "ms", 5.0, 2.0, 10.0, (1000, 2000)),
    ("Fuze Setting Accuracy", "TIMING", "us", 2.0, 0.0, 5.0, (2000, 4000)),
    ("Inventory Polling Time", "TIMING", "ms", 50.0, 0.0, 100.0, (2000, 4000)),
    ("1553B Bus Timing", "TIMING", "ns", 2.0, -500.0, 500.0, (600, 1200)),
    ("1760 MILSTD Interface", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (2000, 4000)),
    ("Weapon Data Rate", "FREQUENCY", "Mbps", 10.0, 8.0, 12.0, (1500, 3000)),
    ("Carriage Power Monitor", "CURRENT", "W", 35.0, 10.0, 50.0, (500, 1000)),
    ("Emergency Jettison Latency", "TIMING", "ms", 8.0, 0.0, 15.0, (1500, 3000)),
    ("BIT Self-Test", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (5000, 10000)),
    ("OFP Checksum", "LOGIC_STATE", "bool", 1.0, 1.0, 1.0, (3000, 6000)),
    ("Power Consumption", "CURRENT", "W", 55.0, 10.0, 80.0, (500, 1000)),
    ("EMI Conducted", "SIGNAL_LEVEL", "dBuV", 48.0, 0.0, 70.0, (5000, 10000)),
    ("Grounding Continuity", "RESISTANCE", "ohm", 0.02, 0.0, 0.1, (300, 600)),
    ("Environmental Cold -40C", "TEMPERATURE", "\u00b0C", -39.6, -42.0, -38.0, (30000, 60000)),
    ("Environmental Hot +71C", "TEMPERATURE", "\u00b0C", 70.4, 69.0, 73.0, (30000, 60000)),
]

# Registry mapping LRU type to (steps_template, step_count_range, nomenclature, part_prefix, duration_range_min)
_LRU_PROFILES: Dict[str, Dict[str, Any]] = {
    "MISSION_COMPUTER": {
        "steps": _MISSION_COMPUTER_STEPS,
        "step_range": (50, 80),
        "nomenclature": "Mission Computer MC-1",
        "part_prefix": "1F-400",
        "duration_min": (35, 55),
        "tps": "TPS-MC1-4A7B",
    },
    "RADAR_PROCESSOR": {
        "steps": _RADAR_PROCESSOR_STEPS,
        "step_range": (60, 100),
        "nomenclature": "Radar Processor RP-1",
        "part_prefix": "1F-410",
        "duration_min": (50, 75),
        "tps": "TPS-RP1-9C2D",
    },
    "EW_SUITE": {
        "steps": _EW_SUITE_STEPS,
        "step_range": (40, 70),
        "nomenclature": "EW Suite AN/ASQ-239",
        "part_prefix": "1F-420",
        "duration_min": (30, 55),
        "tps": "TPS-EW239-6E3F",
    },
    "DISPLAY_PROCESSOR": {
        "steps": _DISPLAY_PROCESSOR_STEPS,
        "step_range": (35, 55),
        "nomenclature": "Display Processor DP-1",
        "part_prefix": "1F-430",
        "duration_min": (25, 40),
        "tps": "TPS-DP1-2A8C",
    },
    "CNI_MODULE": {
        "steps": _CNI_MODULE_STEPS,
        "step_range": (40, 60),
        "nomenclature": "CNI Module AN/ASQ-242",
        "part_prefix": "1F-440",
        "duration_min": (30, 50),
        "tps": "TPS-CNI242-7B1D",
    },
    "POWER_SUPPLY": {
        "steps": _POWER_SUPPLY_STEPS,
        "step_range": (30, 50),
        "nomenclature": "Power Supply PS-1",
        "part_prefix": "1F-450",
        "duration_min": (12, 20),
        "tps": "TPS-PS1-3F5A",
    },
    "SENSOR_FUSION": {
        "steps": _SENSOR_FUSION_STEPS,
        "step_range": (35, 55),
        "nomenclature": "Sensor Fusion Processor SF-1",
        "part_prefix": "1F-460",
        "duration_min": (30, 50),
        "tps": "TPS-SF1-8D4E",
    },
    "STORES_MANAGEMENT": {
        "steps": _STORES_MANAGEMENT_STEPS,
        "step_range": (30, 45),
        "nomenclature": "Stores Management Processor SM-1",
        "part_prefix": "1F-470",
        "duration_min": (20, 35),
        "tps": "TPS-SM1-5C9B",
    },
}

# Operator badge pool
_OPERATOR_BADGES = [
    "OP-3341", "OP-3342", "OP-3355", "OP-3367", "OP-3371",
    "OP-3380", "OP-3392", "OP-3401", "OP-3415", "OP-3428",
    "OP-3433", "OP-3447", "OP-3459", "OP-3462", "OP-3478",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, value))


def _normal(mean: float, sigma: float, rng: random.Random) -> float:
    """Generate a normally distributed value using Box-Muller (no numpy)."""
    return rng.gauss(mean, sigma)


def _skew_normal(mean: float, sigma: float, skew: float, rng: random.Random) -> float:
    """Approximate skew-normal: shift distribution slightly."""
    val = _normal(mean, sigma, rng)
    # Apply mild skew by biasing toward one tail
    if skew != 0.0:
        u = rng.random()
        if u < abs(skew):
            direction = 1.0 if skew > 0.0 else -1.0
            val += direction * abs(_normal(0, sigma * 0.3, rng))
    return val


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclass/enum instances to plain dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class ATEManufacturingGenerator:
    """Generates realistic mock ATE manufacturing test data for avionics LRUs."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._serial_counter = 0
        # Per-station calibration biases (percentage of nominal)
        self._station_biases: Dict[str, float] = {}
        # Lot-level failure correlation: maps lot_id to set of step names that tend to fail
        self._lot_failure_affinity: Dict[str, List[str]] = {}

    def _get_station_bias(self, station_id: str) -> float:
        """Each station has a small systematic calibration offset."""
        if station_id not in self._station_biases:
            # Bias range: -0.3% to +0.3% of nominal
            self._station_biases[station_id] = self._rng.gauss(0.0, 0.001)
        return self._station_biases[station_id]

    def _get_lot_id(self, serial_number: str) -> str:
        """Derive manufacturing lot from serial number (last 3 digits grouped)."""
        digits = "".join(c for c in serial_number if c.isdigit())
        if len(digits) >= 3:
            return f"LOT-{digits[-5:-2]}" if len(digits) >= 5 else f"LOT-{digits[-3:]}"
        return "LOT-000"

    def _get_lot_failure_steps(self, lot_id: str, step_names: List[str]) -> List[str]:
        """Lots from the same manufacturing run share correlated failure modes."""
        if lot_id not in self._lot_failure_affinity:
            # Pick 1-4 steps that this lot is predisposed to fail on
            count = self._rng.randint(1, 4)
            self._lot_failure_affinity[lot_id] = self._rng.sample(
                step_names, min(count, len(step_names))
            )
        return self._lot_failure_affinity[lot_id]

    def _next_serial(self) -> str:
        self._serial_counter += 1
        return f"SN-2026-{self._serial_counter:05d}"

    def _generate_measurement(
        self,
        nominal: float,
        lower: float,
        upper: float,
        station_bias: float,
        temp_offset: float,
        is_logic: bool,
        force_fail: bool,
        force_marginal: bool,
    ) -> Tuple[float, str]:
        """Generate a single measurement value and its pass/fail result.

        Returns (measured_value, result_string).
        """
        if is_logic:
            # Logic state tests: pass=1.0, fail=0.0
            if force_fail:
                return (0.0, StepResult.FAIL.value)
            return (1.0, StepResult.PASS.value)

        span = upper - lower
        if span <= 0:
            # Zero tolerance: treat like an exact-value check
            if force_fail:
                offset = abs(nominal) * 0.01 if nominal != 0 else 1.0
                return (round(nominal + offset, 6), StepResult.FAIL.value)
            return (round(nominal, 6), StepResult.PASS.value)

        if force_fail:
            # Push measurement out of spec
            if self._rng.random() < 0.5:
                overshoot = span * self._rng.uniform(0.02, 0.15)
                value = upper + overshoot
            else:
                undershoot = span * self._rng.uniform(0.02, 0.15)
                value = lower - undershoot
            return (round(value, 6), StepResult.FAIL.value)

        if force_marginal:
            # Within 5% of a limit
            margin = span * 0.05
            if self._rng.random() < 0.5:
                value = upper - self._rng.uniform(0, margin)
            else:
                value = lower + self._rng.uniform(0, margin)
            return (round(value, 6), StepResult.MARGINAL.value)

        # Normal pass measurement: cluster around nominal with realistic
        # spread. Use the distance from nominal to the nearest limit as
        # the basis, with sigma = 15% of that distance (so ~3-sigma stays
        # well within spec). Clamp to within limits to prevent natural
        # process variation from generating unintended failures.
        margin_low = abs(nominal - lower)
        margin_high = abs(upper - nominal)
        nearest_margin = min(margin_low, margin_high)
        if nearest_margin <= 0:
            nearest_margin = span * 0.5
        sigma = nearest_margin * 0.15
        biased_nominal = nominal * (1.0 + station_bias) + temp_offset * nominal * 0.0005
        value = _skew_normal(biased_nominal, sigma, 0.05, self._rng)
        # Keep within spec for non-failing measurements; real ATE processes
        # have Cpk > 1.33 so out-of-spec on a passing unit is extremely rare
        inner_low = lower + span * 0.005
        inner_high = upper - span * 0.005
        value = _clamp(value, inner_low, inner_high)
        value = round(value, 6)

        if value < lower or value > upper:
            # Rare natural out-of-spec (genuine process variation)
            return (value, StepResult.FAIL.value)
        # Check marginal (within 5% of limit)
        margin = span * 0.05
        if value >= (upper - margin) or value <= (lower + margin):
            return (value, StepResult.MARGINAL.value)
        return (value, StepResult.PASS.value)

    def generate_single_test(
        self,
        lru_type: str = "MISSION_COMPUTER",
        serial_number: Optional[str] = None,
        station_id: str = "ATE-BLDG4-STN03",
        timestamp: Optional[str] = None,
        pass_rate: float = 0.92,
        abort_rate: float = 0.02,
    ) -> TestResult:
        """Generate a single complete UUT test session.

        Args:
            lru_type: One of the LRUType enum values.
            serial_number: Serial number for the UUT. Auto-generated if None.
            station_id: ATE station identifier.
            timestamp: ISO 8601 timestamp. Current time if None.
            pass_rate: Probability of overall PASS (0.0 to 1.0).
            abort_rate: Probability of test ABORT (0.0 to 1.0).

        Returns:
            A TestResult dataclass.
        """
        profile = _LRU_PROFILES[lru_type]
        step_templates = profile["steps"]

        if serial_number is None:
            serial_number = self._next_serial()
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        # Determine step count: use template steps, padding with repeated
        # variants if needed to reach the target range
        step_min, step_max = profile["step_range"]
        available = len(step_templates)
        lo = min(step_min, available)
        hi = min(step_max, available)
        if lo > hi:
            lo = hi
        target_steps = self._rng.randint(lo, hi) if lo < hi else lo
        # Use up to target_steps from the template
        selected_templates = step_templates[:target_steps]

        # Decide overall outcome
        roll = self._rng.random()
        if roll < abort_rate:
            desired_outcome = OverallResult.ABORT
        elif roll < abort_rate + (1.0 - pass_rate - abort_rate) * 0.3:
            desired_outcome = OverallResult.RETEST
        elif roll < abort_rate + (1.0 - pass_rate):
            desired_outcome = OverallResult.FAIL
        else:
            desired_outcome = OverallResult.PASS

        # Station bias
        station_bias = self._get_station_bias(station_id)

        # Environmental conditions
        env_temp = _normal(23.0, 2.0, self._rng)
        env_humidity = _clamp(_normal(45.0, 8.0, self._rng), 15.0, 80.0)
        env_altitude = _clamp(_normal(500.0, 200.0, self._rng), 0.0, 2000.0)
        temp_offset = env_temp - 23.0  # deviation from nominal

        # Lot-correlated failures
        lot_id = self._get_lot_id(serial_number)
        step_names = [t[0] for t in selected_templates]
        lot_weak_steps = self._get_lot_failure_steps(lot_id, step_names)

        # Decide which steps fail/marginal
        fail_step_indices: set = set()
        marginal_step_indices: set = set()

        if desired_outcome in (OverallResult.FAIL, OverallResult.RETEST):
            # Pick 1-3 steps to fail
            num_failures = self._rng.randint(1, 3)
            # Prefer lot-correlated steps
            candidate_indices = []
            for i, tmpl in enumerate(selected_templates):
                if tmpl[0] in lot_weak_steps:
                    candidate_indices.append(i)
            # Fill with random if not enough
            all_indices = list(range(len(selected_templates)))
            self._rng.shuffle(all_indices)
            for idx in all_indices:
                if idx not in candidate_indices:
                    candidate_indices.append(idx)
            fail_step_indices = set(candidate_indices[:num_failures])
            # Also add 1-2 marginal steps
            remaining = [i for i in all_indices if i not in fail_step_indices]
            if remaining:
                num_marginal = self._rng.randint(0, min(2, len(remaining)))
                marginal_step_indices = set(remaining[:num_marginal])

        if desired_outcome == OverallResult.ABORT:
            # Abort partway through — only generate partial steps
            abort_at = self._rng.randint(
                max(3, len(selected_templates) // 4),
                len(selected_templates) * 3 // 4,
            )
            selected_templates = selected_templates[:abort_at]
            # May or may not have failures before abort
            if self._rng.random() < 0.3:
                fail_idx = self._rng.randint(0, len(selected_templates) - 1)
                fail_step_indices = {fail_idx}

        # Generate test steps
        steps: List[TestStep] = []
        total_time_ms = 0
        any_fail = False

        for i, tmpl in enumerate(selected_templates):
            name, mtype, unit, nominal, lower, upper, time_range = tmpl

            is_logic = (mtype == "LOGIC_STATE")
            force_fail = (i in fail_step_indices)
            force_marginal = (i in marginal_step_indices)

            measured, result = self._generate_measurement(
                nominal, lower, upper, station_bias, temp_offset,
                is_logic, force_fail, force_marginal,
            )

            step_time = self._rng.randint(time_range[0], time_range[1])
            total_time_ms += step_time

            if result == StepResult.FAIL.value:
                any_fail = True

            steps.append(TestStep(
                step_id=i + 1,
                step_name=name,
                measurement_type=mtype,
                measured_value=measured,
                unit=unit,
                lower_limit=lower,
                upper_limit=upper,
                result=result,
                test_time_ms=step_time,
            ))

        # Reconcile overall result with actual step outcomes
        if desired_outcome == OverallResult.ABORT:
            overall = OverallResult.ABORT.value
        elif any_fail:
            if desired_outcome == OverallResult.RETEST:
                overall = OverallResult.RETEST.value
            else:
                overall = OverallResult.FAIL.value
        else:
            overall = OverallResult.PASS.value

        # Duration: sum of step times plus overhead (setup, teardown)
        dur_min, dur_max = profile["duration_min"]
        # Target duration in seconds, but respect step time sum as minimum
        target_duration = self._rng.randint(dur_min * 60, dur_max * 60)
        actual_duration = max(target_duration, total_time_ms // 1000 + 30)

        part_suffix = self._rng.randint(1000, 9999)
        operator = self._rng.choice(_OPERATOR_BADGES)

        return TestResult(
            session_id=str(uuid.UUID(int=self._rng.getrandbits(128), version=4)),
            timestamp=timestamp,
            station_id=station_id,
            operator_id=operator,
            uut_info=UUTInfo(
                part_number=f"{profile['part_prefix']}-{part_suffix}",
                serial_number=serial_number,
                nomenclature=profile["nomenclature"],
                lru_type=lru_type,
            ),
            test_program=profile["tps"],
            overall_result=overall,
            test_steps=steps,
            environment=Environment(
                temperature_c=round(env_temp, 1),
                humidity_pct=round(env_humidity, 1),
                altitude_ft=round(env_altitude, 0),
            ),
            duration_seconds=actual_duration,
        )

    def generate_batch(
        self,
        lru_type: str = "MISSION_COMPUTER",
        count: int = 10,
        station_id: str = "ATE-BLDG4-STN03",
        start_time: Optional[str] = None,
        pass_rate: float = 0.92,
        abort_rate: float = 0.02,
    ) -> List[TestResult]:
        """Generate a batch of test results.

        Args:
            lru_type: LRU type to test.
            count: Number of UUTs.
            station_id: ATE station.
            start_time: ISO 8601 start. Defaults to now.
            pass_rate: Target pass rate.
            abort_rate: Target abort rate.

        Returns:
            List of TestResult objects.
        """
        if start_time is None:
            ts = datetime.now(timezone.utc)
        else:
            ts = datetime.fromisoformat(start_time)

        results = []
        profile = _LRU_PROFILES[lru_type]
        dur_min, dur_max = profile["duration_min"]

        for _ in range(count):
            result = self.generate_single_test(
                lru_type=lru_type,
                station_id=station_id,
                timestamp=ts.isoformat(),
                pass_rate=pass_rate,
                abort_rate=abort_rate,
            )
            results.append(result)
            # Advance timestamp by test duration plus changeover (5-15 min)
            changeover = self._rng.randint(5 * 60, 15 * 60)
            ts += timedelta(seconds=result.duration_seconds + changeover)

        return results

    def generate_shift(
        self,
        station_id: str = "ATE-BLDG4-STN03",
        lru_type: str = "MISSION_COMPUTER",
        shift_start: str = "2026-02-17T06:00:00",
        shift_hours: int = 8,
        pass_rate: float = 0.92,
    ) -> List[TestResult]:
        """Generate a full shift of testing.

        Produces as many UUT tests as fit in the shift duration.

        Args:
            station_id: ATE station identifier.
            lru_type: LRU type.
            shift_start: ISO 8601 shift start time.
            shift_hours: Duration of shift in hours.
            pass_rate: Target pass rate.

        Returns:
            List of TestResult objects fitting within the shift window.
        """
        ts = datetime.fromisoformat(shift_start)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        shift_end = ts + timedelta(hours=shift_hours)

        results: List[TestResult] = []
        while ts < shift_end:
            result = self.generate_single_test(
                lru_type=lru_type,
                station_id=station_id,
                timestamp=ts.isoformat(),
                pass_rate=pass_rate,
            )
            results.append(result)
            changeover = self._rng.randint(5 * 60, 15 * 60)
            ts += timedelta(seconds=result.duration_seconds + changeover)

        return results

    def stream_shift(
        self,
        lru_type: str = "POWER_SUPPLY",
        station_id: str = "ATE-BLDG4-STN03",
        interval_seconds: float = 0.5,
        pass_rate: float = 0.92,
        max_results: int = 100,
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream test results with real-time delays.

        Yields one JSON-serializable dict per UUT test, sleeping between yields.

        Args:
            lru_type: LRU type.
            station_id: ATE station.
            interval_seconds: Sleep between results.
            pass_rate: Target pass rate.
            max_results: Maximum results to stream (safety limit).

        Yields:
            Dict representation of each TestResult.
        """
        ts = datetime.now(timezone.utc)
        count = 0
        while count < max_results:
            result = self.generate_single_test(
                lru_type=lru_type,
                station_id=station_id,
                timestamp=ts.isoformat(),
                pass_rate=pass_rate,
            )
            yield _to_dict(result)
            count += 1
            changeover = self._rng.randint(5 * 60, 15 * 60)
            ts += timedelta(seconds=result.duration_seconds + changeover)
            time.sleep(interval_seconds)

    # -------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------

    @staticmethod
    def export_json(
        results: List[TestResult],
        output_path: str,
        indent: int = 2,
    ) -> None:
        """Export results as nested JSON (one object per session).

        Args:
            results: List of TestResult objects.
            output_path: File path. Use "-" for stdout.
            indent: JSON indentation.
        """
        data = [_to_dict(r) for r in results]
        payload = json.dumps(data, indent=indent, ensure_ascii=False)
        if output_path == "-":
            sys.stdout.write(payload + "\n")
        else:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(payload + "\n")

    @staticmethod
    def export_csv(
        results: List[TestResult],
        output_path: str,
    ) -> None:
        """Export results as flat CSV (one row per measurement step).

        Session-level fields are repeated on every row for that session.

        Args:
            results: List of TestResult objects.
            output_path: File path. Use "-" for stdout.
        """
        fieldnames = [
            "session_id", "timestamp", "station_id", "operator_id",
            "part_number", "serial_number", "nomenclature", "lru_type",
            "test_program", "overall_result",
            "env_temperature_c", "env_humidity_pct", "env_altitude_ft",
            "duration_seconds",
            "step_id", "step_name", "measurement_type",
            "measured_value", "unit", "lower_limit", "upper_limit",
            "result", "test_time_ms",
        ]

        if output_path == "-":
            fh = sys.stdout
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            _write_csv_rows(writer, results)
        else:
            with open(output_path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                _write_csv_rows(writer, results)


def _write_csv_rows(writer: csv.DictWriter, results: List[TestResult]) -> None:
    """Write CSV rows from test results."""
    for r in results:
        session_fields = {
            "session_id": r.session_id,
            "timestamp": r.timestamp,
            "station_id": r.station_id,
            "operator_id": r.operator_id,
            "part_number": r.uut_info.part_number,
            "serial_number": r.uut_info.serial_number,
            "nomenclature": r.uut_info.nomenclature,
            "lru_type": r.uut_info.lru_type,
            "test_program": r.test_program,
            "overall_result": r.overall_result,
            "env_temperature_c": r.environment.temperature_c,
            "env_humidity_pct": r.environment.humidity_pct,
            "env_altitude_ft": r.environment.altitude_ft,
            "duration_seconds": r.duration_seconds,
        }
        for step in r.test_steps:
            row = dict(session_fields)
            row.update({
                "step_id": step.step_id,
                "step_name": step.step_name,
                "measurement_type": step.measurement_type,
                "measured_value": step.measured_value,
                "unit": step.unit,
                "lower_limit": step.lower_limit,
                "upper_limit": step.upper_limit,
                "result": step.result,
                "test_time_ms": step.test_time_ms,
            })
            writer.writerow(row)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    lru_choices = [e.value for e in LRUType]

    parser = argparse.ArgumentParser(
        description="Generate mock ATE manufacturing test data for avionics LRUs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --lru MISSION_COMPUTER --count 10
  %(prog)s --lru POWER_SUPPLY --count 30 --format csv --output shift.csv
  %(prog)s --lru RADAR_PROCESSOR --count 5 --pass-rate 0.80 --seed 42
  %(prog)s --mode shift --lru CNI_MODULE --shift-hours 8 --station ATE-BLDG7-STN01
""",
    )
    parser.add_argument(
        "--lru", default="MISSION_COMPUTER", choices=lru_choices,
        help="LRU type to test (default: MISSION_COMPUTER)",
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Number of UUTs to test (batch mode, default: 10)",
    )
    parser.add_argument(
        "--pass-rate", type=float, default=0.92,
        help="Target pass rate 0.0-1.0 (default: 0.92)",
    )
    parser.add_argument(
        "--format", choices=["json", "csv"], default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--output", default="-",
        help="Output file path, or - for stdout (default: -)",
    )
    parser.add_argument(
        "--station", default="ATE-BLDG4-STN03",
        help="ATE station identifier (default: ATE-BLDG4-STN03)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--mode", choices=["batch", "shift"], default="batch",
        help="Generation mode: batch (fixed count) or shift (fill time window)",
    )
    parser.add_argument(
        "--shift-start", default="2026-02-17T06:00:00",
        help="Shift start time ISO 8601 (shift mode, default: 2026-02-17T06:00:00)",
    )
    parser.add_argument(
        "--shift-hours", type=int, default=8,
        help="Shift duration in hours (shift mode, default: 8)",
    )

    args = parser.parse_args()

    gen = ATEManufacturingGenerator(seed=args.seed)

    if args.mode == "shift":
        results = gen.generate_shift(
            station_id=args.station,
            lru_type=args.lru,
            shift_start=args.shift_start,
            shift_hours=args.shift_hours,
            pass_rate=args.pass_rate,
        )
    else:
        results = gen.generate_batch(
            lru_type=args.lru,
            count=args.count,
            station_id=args.station,
            pass_rate=args.pass_rate,
        )

    if args.format == "csv":
        gen.export_csv(results, args.output)
    else:
        gen.export_json(results, args.output)

    if args.output != "-":
        # Summary to stderr so it doesn't pollute piped output
        pass_count = sum(1 for r in results if r.overall_result == "PASS")
        fail_count = sum(1 for r in results if r.overall_result == "FAIL")
        abort_count = sum(1 for r in results if r.overall_result == "ABORT")
        retest_count = sum(1 for r in results if r.overall_result == "RETEST")
        print(
            f"Generated {len(results)} test sessions for {args.lru} "
            f"on {args.station}",
            file=sys.stderr,
        )
        print(
            f"  PASS={pass_count}  FAIL={fail_count}  "
            f"ABORT={abort_count}  RETEST={retest_count}  "
            f"yield={pass_count / len(results) * 100:.1f}%",
            file=sys.stderr,
        )
        print(f"  Written to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
