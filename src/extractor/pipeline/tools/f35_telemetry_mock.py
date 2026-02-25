"""
Mock data generator for F-35 Lightning II flight test instrumentation (FTI)
telemetry and avionics bus data.

Generates realistic time-series CSV data representing decommutated FTI
output from flight test instrumentation systems, including:
- Flight dynamics parameters (50 Hz)
- F135 engine parameters (20 Hz)
- MIL-STD-1553B bus health (100 Hz)
- EW/Sensor suite status (10 Hz)
- Structural loads (200 Hz)
- Environmental control system (1 Hz)

Also provides raw bus capture generators:
- MIL-STD-1553B message-level data
- ARINC 429 word-level data

All output is CSV-based, the standard interchange format for FTI data
after decommutation. No external dependencies beyond Python stdlib.
"""

from __future__ import annotations

import csv
import io
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Generator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Parameter definitions
# ---------------------------------------------------------------------------

@dataclass
class Parameter:
    """Single telemetry parameter definition."""
    param_id: str
    name: str
    unit: str
    subsystem: str
    min_val: float
    max_val: float
    sample_rate_hz: float
    noise_amplitude: float = 0.0
    decimal_places: int = 2


# Flight dynamics — 50 Hz
FLIGHT_DYNAMICS: List[Parameter] = [
    Parameter("FD-ALT-BARO", "Barometric Altitude", "ft", "flight_dynamics",
              0, 60000, 50, 2.0, 1),
    Parameter("FD-ALT-RADAR", "Radar Altitude", "ft", "flight_dynamics",
              0, 5000, 50, 0.5, 1),
    Parameter("FD-IAS", "Indicated Airspeed", "kts", "flight_dynamics",
              0, 800, 50, 0.3, 1),
    Parameter("FD-TAS", "True Airspeed", "kts", "flight_dynamics",
              0, 1200, 50, 0.3, 1),
    Parameter("FD-MACH", "Mach Number", "", "flight_dynamics",
              0, 1.8, 50, 0.001, 3),
    Parameter("FD-AOA", "Angle of Attack", "deg", "flight_dynamics",
              -10, 30, 50, 0.05, 2),
    Parameter("FD-AOS", "Angle of Sideslip", "deg", "flight_dynamics",
              -15, 15, 50, 0.03, 2),
    Parameter("FD-NZ", "Normal Acceleration", "g", "flight_dynamics",
              -3, 9, 50, 0.01, 3),
    Parameter("FD-NY", "Lateral Acceleration", "g", "flight_dynamics",
              -2, 2, 50, 0.005, 3),
    Parameter("FD-NX", "Longitudinal Acceleration", "g", "flight_dynamics",
              -1, 3, 50, 0.005, 3),
    Parameter("FD-ROLL-RATE", "Roll Rate", "deg/s", "flight_dynamics",
              -200, 200, 50, 0.1, 2),
    Parameter("FD-PITCH-RATE", "Pitch Rate", "deg/s", "flight_dynamics",
              -40, 40, 50, 0.05, 2),
    Parameter("FD-YAW-RATE", "Yaw Rate", "deg/s", "flight_dynamics",
              -30, 30, 50, 0.03, 2),
    Parameter("FD-ROLL-ATT", "Roll Attitude", "deg", "flight_dynamics",
              -180, 180, 50, 0.02, 2),
    Parameter("FD-PITCH-ATT", "Pitch Attitude", "deg", "flight_dynamics",
              -90, 90, 50, 0.02, 2),
    Parameter("FD-HDG-MAG", "Magnetic Heading", "deg", "flight_dynamics",
              0, 360, 50, 0.05, 2),
    Parameter("FD-VERT-SPEED", "Vertical Speed", "ft/min", "flight_dynamics",
              -10000, 10000, 50, 5.0, 0),
]

# Engine (F135-PW-100) — 20 Hz
ENGINE_PARAMS: List[Parameter] = [
    Parameter("ENG-N1", "Fan Speed (N1)", "%RPM", "engine",
              0, 100, 20, 0.05, 2),
    Parameter("ENG-N2", "Core Speed (N2)", "%RPM", "engine",
              0, 100, 20, 0.03, 2),
    Parameter("ENG-EGT", "Exhaust Gas Temperature", "degC", "engine",
              200, 1000, 20, 1.0, 1),
    Parameter("ENG-FF", "Fuel Flow", "pph", "engine",
              0, 25000, 20, 10, 0),
    Parameter("ENG-OIL-P", "Oil Pressure", "psi", "engine",
              0, 100, 20, 0.2, 1),
    Parameter("ENG-OIL-T", "Oil Temperature", "degC", "engine",
              -40, 180, 20, 0.3, 1),
    Parameter("ENG-VIB-N1", "N1 Vibration", "mils", "engine",
              0, 5.0, 20, 0.02, 3),
    Parameter("ENG-VIB-N2", "N2 Vibration", "mils", "engine",
              0, 5.0, 20, 0.02, 3),
    Parameter("ENG-NOZZLE", "Nozzle Position", "%", "engine",
              0, 100, 20, 0.1, 1),
    Parameter("ENG-EPR", "Engine Pressure Ratio", "", "engine",
              1.0, 4.5, 20, 0.005, 3),
    Parameter("ENG-ITT", "Interstage Turbine Temp", "degC", "engine",
              100, 900, 20, 0.8, 1),
]

# MIL-STD-1553B bus health — 100 Hz
BUS_PARAMS: List[Parameter] = [
    Parameter("BUS-1553-UTIL-A", "1553 Bus A Utilization", "%", "avionics_bus",
              0, 100, 100, 0.5, 1),
    Parameter("BUS-1553-UTIL-B", "1553 Bus B Utilization", "%", "avionics_bus",
              0, 100, 100, 0.5, 1),
    Parameter("BUS-1553-MSG-CNT", "1553 Message Count", "msg/s", "avionics_bus",
              0, 4000, 100, 5, 0),
    Parameter("BUS-1553-ERR-RATE", "1553 Error Rate", "err/s", "avionics_bus",
              0, 50, 100, 0.1, 2),
    Parameter("BUS-1553-RT-RESP", "RT Response Time", "us", "avionics_bus",
              2.0, 14.0, 100, 0.1, 2),
    Parameter("BUS-ARINC-UTIL", "ARINC 429 Bus Utilization", "%", "avionics_bus",
              0, 100, 100, 0.3, 1),
]

# EW / Sensor — 10 Hz
EW_SENSOR_PARAMS: List[Parameter] = [
    Parameter("EW-RWR-CONTACTS", "RWR Contact Count", "", "ew_sensor",
              0, 20, 10, 0, 0),
    Parameter("EW-RADAR-MODE", "Radar Mode Code", "", "ew_sensor",
              0, 7, 10, 0, 0),  # 0=off,1=stby,2=search,3=TWS,4=STT,5=SAR,6=GMTI,7=test
    Parameter("EW-CM-REMAINING", "Countermeasure Remaining", "", "ew_sensor",
              0, 120, 10, 0, 0),
    Parameter("EW-TGTD-RANGE", "Tracked Target Range", "nm", "ew_sensor",
              0, 200, 10, 0.1, 1),
    Parameter("EW-DAS-STATUS", "DAS System Status", "", "ew_sensor",
              0, 3, 10, 0, 0),  # 0=off,1=init,2=oper,3=degrade
    Parameter("EW-EOTS-ELEV", "EOTS Elevation", "deg", "ew_sensor",
              -150, 30, 10, 0.02, 2),
    Parameter("EW-EOTS-AZIM", "EOTS Azimuth", "deg", "ew_sensor",
              -90, 90, 10, 0.02, 2),
]

# Structural loads — 200 Hz
STRUCTURAL_PARAMS: List[Parameter] = [
    Parameter("STR-WING-ROOT-L", "Left Wing Root Strain", "ustrain", "structural",
              -2000, 5000, 200, 3.0, 0),
    Parameter("STR-WING-ROOT-R", "Right Wing Root Strain", "ustrain", "structural",
              -2000, 5000, 200, 3.0, 0),
    Parameter("STR-VTAIL-L", "Left Vertical Tail Load", "lbf", "structural",
              -5000, 15000, 200, 10, 0),
    Parameter("STR-VTAIL-R", "Right Vertical Tail Load", "lbf", "structural",
              -5000, 15000, 200, 10, 0),
    Parameter("STR-HTAIL-L", "Left Horizontal Tail Load", "lbf", "structural",
              -8000, 20000, 200, 15, 0),
    Parameter("STR-HTAIL-R", "Right Horizontal Tail Load", "lbf", "structural",
              -8000, 20000, 200, 15, 0),
    Parameter("STR-GEAR-NOSE", "Nose Gear Load", "lbf", "structural",
              0, 30000, 200, 5, 0),
    Parameter("STR-GEAR-LEFT", "Left Main Gear Load", "lbf", "structural",
              0, 60000, 200, 8, 0),
    Parameter("STR-GEAR-RIGHT", "Right Main Gear Load", "lbf", "structural",
              0, 60000, 200, 8, 0),
    Parameter("STR-FUSELAGE-BM", "Fuselage Bending Moment", "in-lbf", "structural",
              -500000, 1500000, 200, 50, 0),
]

# Environmental — 1 Hz
ENVIRONMENTAL_PARAMS: List[Parameter] = [
    Parameter("ENV-COCKPIT-T", "Cockpit Temperature", "degC", "environmental",
              15, 35, 1, 0.1, 1),
    Parameter("ENV-COCKPIT-P", "Cockpit Pressure", "psi", "environmental",
              5.0, 14.7, 1, 0.02, 2),
    Parameter("ENV-ECS-FLOW", "ECS Mass Flow Rate", "lb/min", "environmental",
              0, 50, 1, 0.05, 2),
    Parameter("ENV-CANOPY-SEAL", "Canopy Seal Pressure", "psi", "environmental",
              0, 25, 1, 0.01, 2),
    Parameter("ENV-OAT", "Outside Air Temperature", "degC", "environmental",
              -60, 50, 1, 0.05, 1),
    Parameter("ENV-BLEED-AIR-T", "Bleed Air Temperature", "degC", "environmental",
              100, 450, 1, 0.5, 1),
    Parameter("ENV-BLEED-AIR-P", "Bleed Air Pressure", "psi", "environmental",
              20, 80, 1, 0.1, 1),
]

ALL_PARAMS: List[Parameter] = (
    FLIGHT_DYNAMICS + ENGINE_PARAMS + BUS_PARAMS +
    EW_SENSOR_PARAMS + STRUCTURAL_PARAMS + ENVIRONMENTAL_PARAMS
)

PARAM_LOOKUP: Dict[str, Parameter] = {p.param_id: p for p in ALL_PARAMS}


# ---------------------------------------------------------------------------
# Smooth interpolation helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    """Hermite smoothstep for smooth transitions."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _smootherstep(t: float) -> float:
    """Ken Perlin's improved smoothstep for very smooth transitions."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _oat_from_altitude(alt_ft: float) -> float:
    """ISA outside air temperature from altitude (ft)."""
    if alt_ft <= 36089:
        return 15.0 - 0.001981 * alt_ft
    return -56.5  # tropopause


def _mach_from_tas_alt(tas_kts: float, alt_ft: float) -> float:
    """Approximate Mach number from TAS and altitude."""
    oat_c = _oat_from_altitude(alt_ft)
    oat_k = oat_c + 273.15
    speed_of_sound_kts = 661.47 * math.sqrt(oat_k / 288.15)
    if speed_of_sound_kts < 1:
        return 0.0
    return tas_kts / speed_of_sound_kts


def _ias_from_tas_alt(tas_kts: float, alt_ft: float) -> float:
    """Rough IAS from TAS and altitude (simplified compressibility)."""
    if alt_ft <= 0:
        return tas_kts
    # Simplified density ratio
    rho_ratio = math.exp(-alt_ft / 28000.0)
    return tas_kts * math.sqrt(rho_ratio)


def _egt_from_power(n2_pct: float) -> float:
    """Approximate EGT from N2 percent."""
    if n2_pct < 20:
        return 200.0 + n2_pct * 5.0
    return 300.0 + (n2_pct - 20.0) * 8.75  # tops out ~1000 at N2=100


def _fuel_flow_from_power(n2_pct: float, alt_ft: float, mach: float) -> float:
    """Approximate fuel flow (pph) from power setting, altitude, Mach."""
    base = n2_pct * 200.0  # ~20000 at full power
    # Higher altitude reduces fuel flow
    alt_factor = math.exp(-alt_ft / 50000.0)
    # Afterburner region above 95%
    ab_factor = 1.0
    if n2_pct > 95:
        ab_factor = 1.0 + (n2_pct - 95.0) * 0.5
    return base * alt_factor * ab_factor


def _wing_strain_from_g(nz: float, base_strain: float = 800.0) -> float:
    """Wing root strain roughly proportional to G load."""
    return base_strain * nz


# ---------------------------------------------------------------------------
# Flight state — drives all parameters from physics
# ---------------------------------------------------------------------------

@dataclass
class FlightState:
    """Instantaneous aircraft state from which all parameters derive."""
    time_s: float = 0.0
    altitude_ft: float = 0.0
    tas_kts: float = 0.0
    aoa_deg: float = 2.0
    aos_deg: float = 0.0
    nz_g: float = 1.0
    ny_g: float = 0.0
    nx_g: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 3.0
    heading_deg: float = 270.0
    roll_rate: float = 0.0
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0
    vert_speed_fpm: float = 0.0
    n1_pct: float = 0.0
    n2_pct: float = 0.0
    nozzle_pct: float = 50.0
    gear_down: bool = True
    flaps_deg: float = 0.0
    radar_mode: int = 1  # standby
    rwr_contacts: int = 0
    cm_remaining: int = 120
    das_status: int = 2  # operational
    cockpit_temp_c: float = 22.0
    cockpit_pres_psi: float = 14.7
    ecs_flow: float = 25.0

    def get_mach(self) -> float:
        return _mach_from_tas_alt(self.tas_kts, self.altitude_ft)

    def get_ias(self) -> float:
        return _ias_from_tas_alt(self.tas_kts, self.altitude_ft)

    def get_egt(self) -> float:
        return _egt_from_power(self.n2_pct)

    def get_fuel_flow(self) -> float:
        return _fuel_flow_from_power(self.n2_pct, self.altitude_ft, self.get_mach())

    def get_oat(self) -> float:
        return _oat_from_altitude(self.altitude_ft)

    def get_cockpit_pressure(self) -> float:
        """Cockpit pressurized to ~8000ft cabin altitude above 8000ft."""
        if self.altitude_ft < 8000:
            return 14.7 - self.altitude_ft * 0.000495
        # Cabin altitude held at ~8000ft equivalent
        return 14.7 - 8000 * 0.000495  # ~10.74 psi

    def get_radar_alt(self) -> float:
        """Radar altimeter, valid below ~5000 ft AGL."""
        if self.altitude_ft > 5000:
            return 0.0  # invalid / flagged
        return max(0.0, self.altitude_ft)

    def derive_param(self, param_id: str) -> float:
        """Derive a parameter value from the current flight state."""
        m = self.get_mach()
        ias = self.get_ias()
        oat = self.get_oat()

        mapping = {
            "FD-ALT-BARO": self.altitude_ft,
            "FD-ALT-RADAR": self.get_radar_alt(),
            "FD-IAS": ias,
            "FD-TAS": self.tas_kts,
            "FD-MACH": m,
            "FD-AOA": self.aoa_deg,
            "FD-AOS": self.aos_deg,
            "FD-NZ": self.nz_g,
            "FD-NY": self.ny_g,
            "FD-NX": self.nx_g,
            "FD-ROLL-RATE": self.roll_rate,
            "FD-PITCH-RATE": self.pitch_rate,
            "FD-YAW-RATE": self.yaw_rate,
            "FD-ROLL-ATT": self.roll_deg,
            "FD-PITCH-ATT": self.pitch_deg,
            "FD-HDG-MAG": self.heading_deg % 360.0,
            "FD-VERT-SPEED": self.vert_speed_fpm,
            # Engine
            "ENG-N1": self.n1_pct,
            "ENG-N2": self.n2_pct,
            "ENG-EGT": self.get_egt(),
            "ENG-FF": self.get_fuel_flow(),
            "ENG-OIL-P": _lerp(25, 65, self.n2_pct / 100.0),
            "ENG-OIL-T": _lerp(40, 150, self.n2_pct / 100.0),
            "ENG-VIB-N1": 0.3 + 0.01 * self.n1_pct + abs(self.nz_g - 1) * 0.05,
            "ENG-VIB-N2": 0.2 + 0.008 * self.n2_pct + abs(self.nz_g - 1) * 0.04,
            "ENG-NOZZLE": self.nozzle_pct,
            "ENG-EPR": 1.0 + self.n2_pct * 0.035,
            "ENG-ITT": _lerp(120, 850, self.n2_pct / 100.0),
            # 1553 bus
            "BUS-1553-UTIL-A": _lerp(30, 75, self.n2_pct / 100.0) + (5 if self.radar_mode >= 3 else 0),
            "BUS-1553-UTIL-B": _lerp(25, 60, self.n2_pct / 100.0),
            "BUS-1553-MSG-CNT": int(_lerp(800, 3200, self.n2_pct / 100.0)),
            "BUS-1553-ERR-RATE": 0.1 + random.random() * 0.3,
            "BUS-1553-RT-RESP": _lerp(4.0, 8.0, self.n2_pct / 100.0),
            "BUS-ARINC-UTIL": _lerp(15, 45, self.n2_pct / 100.0),
            # EW / Sensor
            "EW-RWR-CONTACTS": self.rwr_contacts,
            "EW-RADAR-MODE": self.radar_mode,
            "EW-CM-REMAINING": self.cm_remaining,
            "EW-TGTD-RANGE": max(0, 80 + random.gauss(0, 5)) if self.radar_mode >= 3 else 0,
            "EW-DAS-STATUS": self.das_status,
            "EW-EOTS-ELEV": _lerp(-30, 10, 0.5 + 0.3 * math.sin(self.time_s * 0.1)),
            "EW-EOTS-AZIM": _lerp(-20, 20, 0.5 + 0.3 * math.cos(self.time_s * 0.07)),
            # Structural
            "STR-WING-ROOT-L": _wing_strain_from_g(self.nz_g, 810),
            "STR-WING-ROOT-R": _wing_strain_from_g(self.nz_g, 790),
            "STR-VTAIL-L": _lerp(500, 3000, abs(self.yaw_rate) / 30.0) * self.nz_g,
            "STR-VTAIL-R": _lerp(500, 3000, abs(self.yaw_rate) / 30.0) * self.nz_g,
            "STR-HTAIL-L": _lerp(1000, 12000, abs(self.pitch_rate) / 40.0) * self.nz_g,
            "STR-HTAIL-R": _lerp(1000, 12000, abs(self.pitch_rate) / 40.0) * self.nz_g,
            "STR-GEAR-NOSE": 8000 if self.gear_down and self.altitude_ft < 5 else 0,
            "STR-GEAR-LEFT": 22000 if self.gear_down and self.altitude_ft < 5 else 0,
            "STR-GEAR-RIGHT": 22000 if self.gear_down and self.altitude_ft < 5 else 0,
            "STR-FUSELAGE-BM": int(200000 * self.nz_g + 50000 * math.sin(self.time_s * 0.5)),
            # Environmental
            "ENV-COCKPIT-T": self.cockpit_temp_c,
            "ENV-COCKPIT-P": self.get_cockpit_pressure(),
            "ENV-ECS-FLOW": self.ecs_flow,
            "ENV-CANOPY-SEAL": _lerp(18, 22, 0.5 + 0.1 * math.sin(self.time_s * 0.02)),
            "ENV-OAT": oat,
            "ENV-BLEED-AIR-T": _lerp(150, 400, self.n2_pct / 100.0),
            "ENV-BLEED-AIR-P": _lerp(25, 70, self.n2_pct / 100.0),
        }
        return mapping.get(param_id, 0.0)


# ---------------------------------------------------------------------------
# Keyframe-based flight profile definitions
# ---------------------------------------------------------------------------

@dataclass
class Keyframe:
    """A point in time with target flight state values."""
    time_s: float
    altitude_ft: float = 0.0
    tas_kts: float = 0.0
    aoa_deg: float = 2.0
    nz_g: float = 1.0
    roll_deg: float = 0.0
    pitch_deg: float = 3.0
    heading_deg: float = 270.0
    n2_pct: float = 50.0
    nozzle_pct: float = 50.0
    gear_down: bool = True
    radar_mode: int = 1
    rwr_contacts: int = 0


def _interpolate_keyframes(kfs: List[Keyframe], t: float) -> FlightState:
    """Interpolate between keyframes to produce a smooth flight state."""
    if t <= kfs[0].time_s:
        kf = kfs[0]
        return _keyframe_to_state(kf, t)
    if t >= kfs[-1].time_s:
        kf = kfs[-1]
        return _keyframe_to_state(kf, t)

    # Find surrounding keyframes
    for i in range(len(kfs) - 1):
        if kfs[i].time_s <= t <= kfs[i + 1].time_s:
            k0, k1 = kfs[i], kfs[i + 1]
            dt = k1.time_s - k0.time_s
            frac = (t - k0.time_s) / dt if dt > 0 else 0.0
            s = _smootherstep(frac)

            fs = FlightState(time_s=t)
            fs.altitude_ft = _lerp(k0.altitude_ft, k1.altitude_ft, s)
            fs.tas_kts = _lerp(k0.tas_kts, k1.tas_kts, s)
            fs.aoa_deg = _lerp(k0.aoa_deg, k1.aoa_deg, s)
            fs.nz_g = _lerp(k0.nz_g, k1.nz_g, s)
            fs.roll_deg = _lerp(k0.roll_deg, k1.roll_deg, s)
            fs.pitch_deg = _lerp(k0.pitch_deg, k1.pitch_deg, s)
            fs.heading_deg = _interp_heading(k0.heading_deg, k1.heading_deg, s)
            fs.n2_pct = _lerp(k0.n2_pct, k1.n2_pct, s)
            fs.n1_pct = fs.n2_pct * 0.95  # N1 tracks N2
            fs.nozzle_pct = _lerp(k0.nozzle_pct, k1.nozzle_pct, s)
            fs.gear_down = k0.gear_down if frac < 0.5 else k1.gear_down
            fs.radar_mode = k0.radar_mode if frac < 0.5 else k1.radar_mode
            fs.rwr_contacts = int(_lerp(k0.rwr_contacts, k1.rwr_contacts, s))

            # Derived rates from state changes
            eps = 0.02
            if frac > eps and frac < 1.0 - eps:
                prev_alt = _lerp(k0.altitude_ft, k1.altitude_ft, _smootherstep(frac - eps))
                fs.vert_speed_fpm = (fs.altitude_ft - prev_alt) / (dt * eps) * 60.0
                prev_pitch = _lerp(k0.pitch_deg, k1.pitch_deg, _smootherstep(frac - eps))
                fs.pitch_rate = (fs.pitch_deg - prev_pitch) / (dt * eps)
                prev_roll = _lerp(k0.roll_deg, k1.roll_deg, _smootherstep(frac - eps))
                fs.roll_rate = (fs.roll_deg - prev_roll) / (dt * eps)
                prev_hdg = _interp_heading(k0.heading_deg, k1.heading_deg, _smootherstep(frac - eps))
                fs.yaw_rate = _heading_diff(fs.heading_deg, prev_hdg) / (dt * eps)

            # Cockpit environment
            fs.cockpit_pres_psi = fs.get_cockpit_pressure()
            fs.cockpit_temp_c = _lerp(22, 24, fs.n2_pct / 100.0)
            fs.ecs_flow = _lerp(20, 40, fs.n2_pct / 100.0)

            return fs

    return _keyframe_to_state(kfs[-1], t)


def _keyframe_to_state(kf: Keyframe, t: float) -> FlightState:
    fs = FlightState(time_s=t)
    fs.altitude_ft = kf.altitude_ft
    fs.tas_kts = kf.tas_kts
    fs.aoa_deg = kf.aoa_deg
    fs.nz_g = kf.nz_g
    fs.roll_deg = kf.roll_deg
    fs.pitch_deg = kf.pitch_deg
    fs.heading_deg = kf.heading_deg
    fs.n2_pct = kf.n2_pct
    fs.n1_pct = kf.n2_pct * 0.95
    fs.nozzle_pct = kf.nozzle_pct
    fs.gear_down = kf.gear_down
    fs.radar_mode = kf.radar_mode
    fs.rwr_contacts = kf.rwr_contacts
    fs.cockpit_pres_psi = fs.get_cockpit_pressure()
    fs.cockpit_temp_c = _lerp(22, 24, fs.n2_pct / 100.0)
    fs.ecs_flow = _lerp(20, 40, fs.n2_pct / 100.0)
    return fs


def _interp_heading(h0: float, h1: float, t: float) -> float:
    """Interpolate heading angles accounting for 360 wraparound."""
    diff = ((h1 - h0) + 180) % 360 - 180
    return (h0 + diff * t) % 360


def _heading_diff(h1: float, h0: float) -> float:
    """Signed heading difference."""
    d = ((h1 - h0) + 180) % 360 - 180
    return d


# ---------------------------------------------------------------------------
# Pre-built flight profiles
# ---------------------------------------------------------------------------

def _profile_takeoff_and_climb() -> List[Keyframe]:
    """0 to 350 kts, 0 to 25000 ft over 5 minutes."""
    return [
        Keyframe(0, altitude_ft=0, tas_kts=0, aoa_deg=0, nz_g=1.0,
                 pitch_deg=0, n2_pct=30, nozzle_pct=20, gear_down=True, radar_mode=1),
        Keyframe(15, altitude_ft=0, tas_kts=80, aoa_deg=0, nz_g=1.0,
                 pitch_deg=0, n2_pct=92, nozzle_pct=85, gear_down=True, radar_mode=1),
        Keyframe(30, altitude_ft=0, tas_kts=150, aoa_deg=2, nz_g=1.0,
                 pitch_deg=0, n2_pct=95, nozzle_pct=90, gear_down=True, radar_mode=1),
        # Rotation
        Keyframe(35, altitude_ft=20, tas_kts=165, aoa_deg=8, nz_g=1.3,
                 pitch_deg=10, n2_pct=95, nozzle_pct=90, gear_down=True, radar_mode=1),
        # Gear up
        Keyframe(45, altitude_ft=500, tas_kts=200, aoa_deg=6, nz_g=1.1,
                 pitch_deg=12, n2_pct=92, nozzle_pct=80, gear_down=False, radar_mode=2),
        # Climbing
        Keyframe(90, altitude_ft=5000, tas_kts=300, aoa_deg=4, nz_g=1.0,
                 pitch_deg=8, n2_pct=88, nozzle_pct=70, gear_down=False, radar_mode=2),
        Keyframe(180, altitude_ft=15000, tas_kts=350, aoa_deg=3, nz_g=1.0,
                 pitch_deg=5, n2_pct=85, nozzle_pct=60, gear_down=False, radar_mode=2),
        Keyframe(300, altitude_ft=25000, tas_kts=400, aoa_deg=2, nz_g=1.0,
                 pitch_deg=3, n2_pct=80, nozzle_pct=50, gear_down=False, radar_mode=2),
    ]


def _profile_high_g_maneuver() -> List[Keyframe]:
    """Level flight then 6G pull, 3 minutes total."""
    return [
        Keyframe(0, altitude_ft=20000, tas_kts=450, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, n2_pct=82, nozzle_pct=50, gear_down=False, radar_mode=3),
        # Set up
        Keyframe(30, altitude_ft=20000, tas_kts=500, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, n2_pct=90, nozzle_pct=65, gear_down=False, radar_mode=4),
        # Entry: roll and pull
        Keyframe(40, altitude_ft=20000, tas_kts=500, aoa_deg=4, nz_g=1.5,
                 roll_deg=60, pitch_deg=5, n2_pct=95, nozzle_pct=80, gear_down=False, radar_mode=4),
        # Peak G
        Keyframe(48, altitude_ft=19000, tas_kts=480, aoa_deg=12, nz_g=6.0,
                 roll_deg=70, pitch_deg=15, n2_pct=97, nozzle_pct=90, gear_down=False, radar_mode=4),
        # Sustain
        Keyframe(55, altitude_ft=18000, tas_kts=440, aoa_deg=14, nz_g=5.5,
                 roll_deg=65, pitch_deg=12, heading_deg=330, n2_pct=97, nozzle_pct=90,
                 gear_down=False, radar_mode=4),
        # Unload
        Keyframe(65, altitude_ft=17500, tas_kts=420, aoa_deg=6, nz_g=2.0,
                 roll_deg=30, pitch_deg=5, heading_deg=350, n2_pct=90, nozzle_pct=70,
                 gear_down=False, radar_mode=3),
        # Recovery
        Keyframe(90, altitude_ft=18000, tas_kts=400, aoa_deg=3, nz_g=1.0,
                 roll_deg=0, pitch_deg=3, heading_deg=10, n2_pct=85, nozzle_pct=55,
                 gear_down=False, radar_mode=3),
        Keyframe(180, altitude_ft=20000, tas_kts=420, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, heading_deg=30, n2_pct=82, nozzle_pct=50,
                 gear_down=False, radar_mode=2),
    ]


def _profile_supersonic_dash() -> List[Keyframe]:
    """Mach 0.9 to 1.6 and back, 10 minutes at FL350+."""
    return [
        Keyframe(0, altitude_ft=35000, tas_kts=520, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, n2_pct=82, nozzle_pct=45, gear_down=False, radar_mode=2),
        # Accelerate — military power
        Keyframe(60, altitude_ft=36000, tas_kts=600, aoa_deg=1.5, nz_g=1.0,
                 pitch_deg=2, n2_pct=95, nozzle_pct=80, gear_down=False, radar_mode=2),
        # Afterburner — push through Mach 1
        Keyframe(120, altitude_ft=38000, tas_kts=750, aoa_deg=1, nz_g=1.0,
                 pitch_deg=1, n2_pct=100, nozzle_pct=100, gear_down=False, radar_mode=3),
        # Mach 1.6 cruise
        Keyframe(240, altitude_ft=42000, tas_kts=920, aoa_deg=1, nz_g=1.0,
                 pitch_deg=1, n2_pct=100, nozzle_pct=100, gear_down=False, radar_mode=3),
        # Sustain supercruise
        Keyframe(360, altitude_ft=43000, tas_kts=920, aoa_deg=1, nz_g=1.0,
                 pitch_deg=1, heading_deg=280, n2_pct=100, nozzle_pct=95,
                 gear_down=False, radar_mode=3),
        # Decelerate
        Keyframe(450, altitude_ft=40000, tas_kts=700, aoa_deg=2, nz_g=1.0,
                 pitch_deg=0, heading_deg=285, n2_pct=85, nozzle_pct=50,
                 gear_down=False, radar_mode=2),
        Keyframe(540, altitude_ft=37000, tas_kts=530, aoa_deg=2, nz_g=1.0,
                 pitch_deg=1, heading_deg=290, n2_pct=80, nozzle_pct=45,
                 gear_down=False, radar_mode=2),
        Keyframe(600, altitude_ft=35000, tas_kts=500, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, heading_deg=290, n2_pct=78, nozzle_pct=42,
                 gear_down=False, radar_mode=2),
    ]


def _profile_weapons_delivery() -> List[Keyframe]:
    """Approach, weapons release, egress — 5 minutes."""
    return [
        # Ingress
        Keyframe(0, altitude_ft=15000, tas_kts=420, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, n2_pct=82, nozzle_pct=50, gear_down=False,
                 radar_mode=5, rwr_contacts=3),
        Keyframe(60, altitude_ft=12000, tas_kts=440, aoa_deg=2, nz_g=1.0,
                 pitch_deg=-2, heading_deg=275, n2_pct=85, nozzle_pct=55,
                 gear_down=False, radar_mode=4, rwr_contacts=5),
        # Weapons release — pop up
        Keyframe(90, altitude_ft=10000, tas_kts=460, aoa_deg=4, nz_g=2.0,
                 pitch_deg=8, heading_deg=278, n2_pct=90, nozzle_pct=70,
                 gear_down=False, radar_mode=4, rwr_contacts=6),
        # Pickle
        Keyframe(100, altitude_ft=11000, tas_kts=450, aoa_deg=3, nz_g=1.0,
                 pitch_deg=5, heading_deg=280, n2_pct=88, nozzle_pct=65,
                 gear_down=False, radar_mode=4, rwr_contacts=6),
        # Egress — hard turn
        Keyframe(110, altitude_ft=10500, tas_kts=470, aoa_deg=6, nz_g=4.0,
                 roll_deg=-60, pitch_deg=3, heading_deg=310, n2_pct=95, nozzle_pct=85,
                 gear_down=False, radar_mode=3, rwr_contacts=4),
        # Egress climb
        Keyframe(140, altitude_ft=15000, tas_kts=500, aoa_deg=3, nz_g=1.5,
                 roll_deg=0, pitch_deg=10, heading_deg=90, n2_pct=95, nozzle_pct=80,
                 gear_down=False, radar_mode=2, rwr_contacts=2),
        Keyframe(200, altitude_ft=22000, tas_kts=480, aoa_deg=2, nz_g=1.0,
                 pitch_deg=5, heading_deg=90, n2_pct=88, nozzle_pct=60,
                 gear_down=False, radar_mode=2, rwr_contacts=0),
        Keyframe(300, altitude_ft=25000, tas_kts=450, aoa_deg=2, nz_g=1.0,
                 pitch_deg=2, heading_deg=90, n2_pct=82, nozzle_pct=50,
                 gear_down=False, radar_mode=2, rwr_contacts=0),
    ]


def _profile_landing() -> List[Keyframe]:
    """250 kts to stop, 10000 ft to touchdown, gear/flap transitions."""
    return [
        # Pattern entry
        Keyframe(0, altitude_ft=10000, tas_kts=300, aoa_deg=3, nz_g=1.0,
                 pitch_deg=0, n2_pct=72, nozzle_pct=35, gear_down=False, radar_mode=1),
        # Initial approach
        Keyframe(60, altitude_ft=5000, tas_kts=250, aoa_deg=4, nz_g=1.0,
                 pitch_deg=-3, heading_deg=260, n2_pct=65, nozzle_pct=30,
                 gear_down=False, radar_mode=1),
        # Gear down
        Keyframe(120, altitude_ft=3000, tas_kts=220, aoa_deg=5, nz_g=1.0,
                 pitch_deg=-3, heading_deg=265, n2_pct=60, nozzle_pct=28,
                 gear_down=True, radar_mode=1),
        # On glideslope
        Keyframe(200, altitude_ft=1500, tas_kts=180, aoa_deg=7, nz_g=1.0,
                 pitch_deg=-3, heading_deg=270, n2_pct=55, nozzle_pct=25,
                 gear_down=True, radar_mode=0),
        # Short final
        Keyframe(280, altitude_ft=500, tas_kts=160, aoa_deg=8, nz_g=1.0,
                 pitch_deg=-2.5, heading_deg=270, n2_pct=50, nozzle_pct=22,
                 gear_down=True, radar_mode=0),
        # Flare
        Keyframe(320, altitude_ft=30, tas_kts=145, aoa_deg=11, nz_g=1.0,
                 pitch_deg=3, heading_deg=270, n2_pct=40, nozzle_pct=20,
                 gear_down=True, radar_mode=0),
        # Touchdown
        Keyframe(325, altitude_ft=0, tas_kts=140, aoa_deg=10, nz_g=1.5,
                 pitch_deg=5, heading_deg=270, n2_pct=30, nozzle_pct=15,
                 gear_down=True, radar_mode=0),
        # Rollout
        Keyframe(350, altitude_ft=0, tas_kts=80, aoa_deg=2, nz_g=1.0,
                 pitch_deg=0, heading_deg=270, n2_pct=30, nozzle_pct=15,
                 gear_down=True, radar_mode=0),
        # Stop
        Keyframe(380, altitude_ft=0, tas_kts=0, aoa_deg=0, nz_g=1.0,
                 pitch_deg=0, heading_deg=270, n2_pct=25, nozzle_pct=10,
                 gear_down=True, radar_mode=0),
    ]


def _profile_random_flight(duration_s: float = 1800) -> List[Keyframe]:
    """30 minutes of varied flight with realistic transitions."""
    rng = random.Random(42)
    kfs: List[Keyframe] = []

    # Start airborne
    alt = 20000.0
    tas = 400.0
    hdg = rng.uniform(0, 360)
    n2 = 80.0
    t = 0.0

    kfs.append(Keyframe(0, altitude_ft=alt, tas_kts=tas, aoa_deg=2, nz_g=1.0,
                        heading_deg=hdg, n2_pct=n2, nozzle_pct=50,
                        gear_down=False, radar_mode=2))

    while t < duration_s:
        seg_time = rng.uniform(30, 120)
        t += seg_time
        if t > duration_s:
            t = duration_s

        # Random maneuver selection
        maneuver = rng.choice(["cruise", "climb", "descend", "turn", "accel", "decel"])

        if maneuver == "cruise":
            pass
        elif maneuver == "climb":
            alt = min(50000, alt + rng.uniform(1000, 8000))
            n2 = min(98, n2 + rng.uniform(2, 10))
        elif maneuver == "descend":
            alt = max(5000, alt - rng.uniform(1000, 8000))
            n2 = max(55, n2 - rng.uniform(2, 10))
        elif maneuver == "turn":
            hdg = (hdg + rng.uniform(-90, 90)) % 360
        elif maneuver == "accel":
            tas = min(900, tas + rng.uniform(20, 100))
            n2 = min(100, n2 + rng.uniform(2, 8))
        elif maneuver == "decel":
            tas = max(200, tas - rng.uniform(20, 100))
            n2 = max(55, n2 - rng.uniform(2, 8))

        nz = 1.0
        aoa = 2.0
        roll = 0.0
        if maneuver == "turn":
            nz = rng.uniform(1.5, 3.5)
            aoa = rng.uniform(4, 10)
            roll = rng.choice([-1, 1]) * rng.uniform(30, 60)

        nozzle = _lerp(30, 100, n2 / 100.0)
        rdr = rng.choice([2, 2, 2, 3, 3, 4])
        rwr = rng.randint(0, 4)

        kfs.append(Keyframe(t, altitude_ft=alt, tas_kts=tas, aoa_deg=aoa,
                            nz_g=nz, roll_deg=roll, heading_deg=hdg,
                            n2_pct=n2, nozzle_pct=nozzle,
                            gear_down=False, radar_mode=rdr, rwr_contacts=rwr))

    return kfs


PROFILES = {
    "takeoff_and_climb": _profile_takeoff_and_climb,
    "high_g_maneuver": _profile_high_g_maneuver,
    "supersonic_dash": _profile_supersonic_dash,
    "weapons_delivery": _profile_weapons_delivery,
    "landing": _profile_landing,
    "random_flight": _profile_random_flight,
}


# ---------------------------------------------------------------------------
# Quality flag generation
# ---------------------------------------------------------------------------

def _quality_flag(rng: random.Random) -> str:
    """99% GOOD, 0.8% SUSPECT, 0.2% BAD."""
    r = rng.random()
    if r < 0.002:
        return "BAD"
    if r < 0.01:
        return "SUSPECT"
    return "GOOD"


# ---------------------------------------------------------------------------
# CSV row formatting
# ---------------------------------------------------------------------------

CSV_HEADER = "timestamp,parameter_id,value,unit,subsystem,quality_flag"


def _format_value(val: float, param: Parameter) -> str:
    """Format a value with appropriate decimal places."""
    if param.decimal_places == 0:
        return str(int(round(val)))
    return f"{val:.{param.decimal_places}f}"


def _make_row(ts: datetime, param: Parameter, value: float,
              quality: str) -> str:
    """Build a single CSV row."""
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"
    clamped = _clamp(value, param.min_val, param.max_val)
    return f"{ts_str},{param.param_id},{_format_value(clamped, param)},{param.unit},{param.subsystem},{quality}"


# ---------------------------------------------------------------------------
# MIL-STD-1553B bus capture generator
# ---------------------------------------------------------------------------

# Realistic RT address assignments for F-35
RT_ADDRESSES = {
    1: "INS",           # Inertial Navigation System
    2: "ADC",           # Air Data Computer
    3: "FCC",           # Flight Control Computer
    5: "RADAR",         # AN/APG-81 AESA Radar
    6: "CNI",           # Communications, Navigation, Identification
    7: "DAS",           # Distributed Aperture System
    8: "SMS",           # Stores Management System
    10: "HMDS",         # Helmet Mounted Display System
    12: "EW",           # AN/ASQ-239 EW Suite
    14: "EOTS",         # Electro-Optical Targeting System
    15: "HUD",          # HUD / PCD (Panoramic Cockpit Display)
    17: "FLCS",         # Flight Control System
    20: "JTIDS",        # Link 16 / MADL
    22: "IFF",          # IFF Transponder
    25: "RECORDER",     # Flight Test Instrumentation Recorder
}

_1553_HEADER = "timestamp,bus,rt_address,subaddress,word_count,tr_bit,data_words_hex,status_word_hex"


def generate_1553b_bus_capture(
    duration_seconds: float = 1.0,
    start_time: Optional[datetime] = None,
    messages_per_second: int = 3000,
    seed: int = 12345,
) -> Generator[str, None, None]:
    """
    Generate MIL-STD-1553B message-level bus capture data.

    Yields CSV rows (without header) representing individual 1553 bus
    command/response transactions. Realistic RT addresses are used
    corresponding to F-35 subsystems.

    Fields:
        timestamp       - ISO 8601 with millisecond precision
        bus             - A or B (dual-redundant bus)
        rt_address      - Remote Terminal address (0-31)
        subaddress      - Subaddress (0-31)
        word_count      - Number of data words (1-32)
        tr_bit          - Transmit/Receive (0=receive from BC, 1=transmit to BC)
        data_words_hex  - Space-separated 16-bit hex words
        status_word_hex - RT status word (16-bit hex)
    """
    rng = random.Random(seed)
    if start_time is None:
        start_time = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)

    rt_addrs = list(RT_ADDRESSES.keys())
    msg_interval_us = 1_000_000.0 / messages_per_second
    total_messages = int(duration_seconds * messages_per_second)

    for i in range(total_messages):
        t_us = i * msg_interval_us + rng.gauss(0, msg_interval_us * 0.05)
        t_us = max(0, t_us)
        ts = start_time + timedelta(microseconds=t_us)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"

        bus = rng.choice(["A", "B"])
        rt = rng.choice(rt_addrs)
        sa = rng.randint(1, 30)
        wc = rng.randint(1, 32)
        tr = rng.randint(0, 1)

        # Generate data words
        data_words = [f"{rng.randint(0, 0xFFFF):04X}" for _ in range(wc)]
        data_hex = " ".join(data_words)

        # Status word: bits 15-11=RT addr, bit 8=busy, bit 0-2=various flags
        status_busy = 0x0100 if rng.random() < 0.005 else 0
        status_svc_req = 0x0400 if rng.random() < 0.02 else 0
        status_word = (rt << 11) | status_busy | status_svc_req
        # Message error bit (rare)
        if rng.random() < 0.001:
            status_word |= 0x0200

        yield f"{ts_str},{bus},{rt},{sa},{wc},{tr},{data_hex},{status_word:04X}"


# ---------------------------------------------------------------------------
# ARINC 429 word generator
# ---------------------------------------------------------------------------

# Standard ARINC 429 labels for air data (octal notation)
ARINC_LABELS = {
    0o310: ("Airspeed", "kts", 0, 800),
    0o312: ("Altitude", "ft", -1000, 60000),
    0o314: ("Heading", "deg", 0, 360),
    0o361: ("Latitude", "deg", -90, 90),
    0o362: ("Longitude", "deg", -180, 180),
    0o324: ("Vertical Speed", "ft/min", -10000, 10000),
    0o325: ("Total Air Temp", "degC", -80, 80),
    0o320: ("Mach Number", "", 0, 2.0),
    0o326: ("Static Air Temp", "degC", -80, 50),
    0o313: ("Baro Correction", "mb", 900, 1100),
    0o270: ("Discrete Word 1", "", 0, 0xFFFF),
    0o271: ("Discrete Word 2", "", 0, 0xFFFF),
}

_ARINC_HEADER = "timestamp,channel,label_octal,sdi,data,ssm,parity"


def generate_arinc429_words(
    duration_seconds: float = 1.0,
    start_time: Optional[datetime] = None,
    words_per_second: int = 1200,
    seed: int = 54321,
    flight_state: Optional[FlightState] = None,
) -> Generator[str, None, None]:
    """
    Generate ARINC 429 word-level data.

    Yields CSV rows representing individual ARINC 429 32-bit words
    on a high-speed (100 kHz) channel. Labels correspond to standard
    air data parameters.

    Fields:
        timestamp    - ISO 8601 with millisecond precision
        channel      - Channel number (1-4)
        label_octal  - 8-bit label in octal (standard ARINC 429 notation)
        sdi          - Source/Destination Identifier (0-3)
        data         - 19-bit data field (decimal value)
        ssm          - Sign/Status Matrix (0=failure, 1=no_data, 2=test, 3=normal)
        parity       - Odd parity bit (0 or 1)
    """
    rng = random.Random(seed)
    if start_time is None:
        start_time = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)

    labels = list(ARINC_LABELS.keys())
    word_interval_us = 1_000_000.0 / words_per_second
    total_words = int(duration_seconds * words_per_second)

    for i in range(total_words):
        t_us = i * word_interval_us
        ts = start_time + timedelta(microseconds=t_us)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"

        label = rng.choice(labels)
        label_name, unit, lo, hi = ARINC_LABELS[label]
        channel = rng.randint(1, 4)
        sdi = rng.randint(0, 3)

        # Generate plausible data value
        if flight_state is not None and label == 0o310:
            raw = flight_state.get_ias()
        elif flight_state is not None and label == 0o312:
            raw = flight_state.altitude_ft
        elif flight_state is not None and label == 0o314:
            raw = flight_state.heading_deg
        elif flight_state is not None and label == 0o320:
            raw = flight_state.get_mach()
        else:
            raw = rng.uniform(lo, hi)

        # Quantize to 19-bit BNR (binary representation)
        data_range = hi - lo if hi != lo else 1
        normalized = (raw - lo) / data_range
        data_val = int(_clamp(normalized, 0, 1) * 524287)  # 2^19 - 1

        # SSM: mostly normal operation
        ssm_roll = rng.random()
        if ssm_roll < 0.002:
            ssm = 0  # failure warning
        elif ssm_roll < 0.005:
            ssm = 1  # no computed data
        elif ssm_roll < 0.008:
            ssm = 2  # functional test
        else:
            ssm = 3  # normal operation

        # Compute odd parity over the 32-bit word
        word32 = (label & 0xFF) | (sdi << 8) | (data_val << 10) | (ssm << 29)
        parity = 1 if bin(word32).count("1") % 2 == 0 else 0

        yield f"{ts_str},{channel},{label:03o},{sdi},{data_val},{ssm},{parity}"


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------

class F35TelemetryGenerator:
    """
    Generates realistic F-35 FTI telemetry CSV data.

    Supports pre-built flight profiles and streaming output.
    All data derives from a physics-based flight state model
    with smooth keyframe interpolation.
    """

    def __init__(self, seed: int = 99999):
        self.seed = seed
        self.rng = random.Random(seed)

    def _get_keyframes(self, profile: str, duration_seconds: Optional[float]) -> Tuple[List[Keyframe], float]:
        """Get keyframes and effective duration for a profile."""
        if profile not in PROFILES:
            raise ValueError(
                f"Unknown profile {profile!r}. "
                f"Available: {', '.join(sorted(PROFILES))}"
            )

        if profile == "random_flight" and duration_seconds is not None:
            kfs = _profile_random_flight(duration_seconds)
        else:
            kfs = PROFILES[profile]()

        profile_duration = kfs[-1].time_s
        if duration_seconds is not None:
            effective = min(duration_seconds, profile_duration)
        else:
            effective = profile_duration

        return kfs, effective

    def stream(
        self,
        profile: str = "random_flight",
        duration_seconds: Optional[float] = None,
        start_time: Optional[datetime] = None,
        include_header: bool = False,
        subsystems: Optional[List[str]] = None,
    ) -> Generator[str, None, None]:
        """
        Stream telemetry rows one at a time.

        Args:
            profile: Flight profile name.
            duration_seconds: Clip duration (None = full profile).
            start_time: Base timestamp (default: 2026-03-15T14:30:00Z).
            include_header: Yield the CSV header as first row.
            subsystems: Filter to specific subsystems (None = all).

        Yields:
            CSV-formatted row strings.
        """
        if start_time is None:
            start_time = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)

        kfs, effective = self._get_keyframes(profile, duration_seconds)

        # Build parameter list filtered by subsystem
        params = ALL_PARAMS
        if subsystems:
            sub_set = set(subsystems)
            params = [p for p in ALL_PARAMS if p.subsystem in sub_set]
        if not params:
            return

        if include_header:
            yield CSV_HEADER

        # Determine the master sample rate (LCM-based would be ideal,
        # but for practical generation we use the highest rate and
        # sub-sample each parameter)
        max_rate = max(p.sample_rate_hz for p in params)
        dt = 1.0 / max_rate
        n_samples = int(effective * max_rate)
        rng = random.Random(self.seed)

        for i in range(n_samples):
            t = i * dt
            state = _interpolate_keyframes(kfs, t)
            ts = start_time + timedelta(seconds=t)

            for p in params:
                # Only emit if this sample aligns with the parameter's rate
                samples_per_master = max_rate / p.sample_rate_hz
                if i % int(samples_per_master) != 0:
                    continue

                raw = state.derive_param(p.param_id)
                # Add sensor noise
                if p.noise_amplitude > 0:
                    raw += rng.gauss(0, p.noise_amplitude)

                quality = _quality_flag(rng)
                # BAD quality: inject a spike or NaN-like value
                if quality == "BAD":
                    raw += rng.choice([-1, 1]) * (p.max_val - p.min_val) * 0.1

                yield _make_row(ts, p, raw, quality)

    def generate(
        self,
        profile: str = "random_flight",
        duration_seconds: Optional[float] = None,
        output: Optional[str] = None,
        start_time: Optional[datetime] = None,
        subsystems: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Generate telemetry data and write to file or return as string.

        Args:
            profile: Flight profile name.
            duration_seconds: Clip duration (None = full profile).
            output: File path to write CSV. None returns string.
            start_time: Base timestamp.
            subsystems: Filter to specific subsystems.

        Returns:
            CSV string if output is None, else None (writes to file).
        """
        rows = list(self.stream(
            profile, duration_seconds, start_time,
            include_header=True, subsystems=subsystems,
        ))

        text = "\n".join(rows) + "\n"

        if output is None:
            return text

        with open(output, "w", newline="") as f:
            f.write(text)
        return None

    def generate_bus_capture(
        self,
        output: Optional[str] = None,
        duration_seconds: float = 1.0,
        bus_type: str = "1553",
        start_time: Optional[datetime] = None,
        seed: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generate MIL-STD-1553B or ARINC 429 bus capture data.

        Args:
            output: File path for CSV. None returns string.
            duration_seconds: Capture duration.
            bus_type: "1553" or "arinc429".
            start_time: Base timestamp.
            seed: RNG seed.

        Returns:
            CSV string if output is None, else None.
        """
        s = seed if seed is not None else self.seed

        if bus_type == "1553":
            header = _1553_HEADER
            gen = generate_1553b_bus_capture(
                duration_seconds=duration_seconds,
                start_time=start_time,
                seed=s,
            )
        elif bus_type == "arinc429":
            header = _ARINC_HEADER
            gen = generate_arinc429_words(
                duration_seconds=duration_seconds,
                start_time=start_time,
                seed=s,
            )
        else:
            raise ValueError(f"Unknown bus_type {bus_type!r}. Use '1553' or 'arinc429'.")

        buf = io.StringIO()
        buf.write(header + "\n")
        for row in gen:
            buf.write(row + "\n")

        text = buf.getvalue()
        if output is None:
            return text

        with open(output, "w", newline="") as f:
            f.write(text)
        return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Command-line interface for F-35 telemetry generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="F-35 FTI Telemetry Mock Data Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available profiles:
  takeoff_and_climb   0->350kts, 0->25000ft (5 min)
  high_g_maneuver     Level flight then 6G pull (3 min)
  supersonic_dash     Mach 0.9->1.6->0.9 (10 min)
  weapons_delivery    Approach, release, egress (5 min)
  landing             250kts->0, 10000ft->0 (6.3 min)
  random_flight       Varied flight (30 min default)

Examples:
  %(prog)s --profile takeoff_and_climb --duration 30 -o takeoff.csv
  %(prog)s --profile high_g_maneuver --duration 10 --subsystem flight_dynamics
  %(prog)s --bus 1553 --bus-duration 0.1 -o bus_capture.csv
  %(prog)s --bus arinc429 --bus-duration 0.5 -o arinc.csv
        """,
    )
    parser.add_argument("--profile", "-p", default="random_flight",
                        choices=sorted(PROFILES.keys()),
                        help="Flight profile (default: random_flight)")
    parser.add_argument("--duration", "-d", type=float, default=None,
                        help="Duration in seconds (default: full profile)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output CSV file (default: stdout)")
    parser.add_argument("--seed", type=int, default=99999,
                        help="Random seed (default: 99999)")
    parser.add_argument("--subsystem", "-s", action="append", default=None,
                        help="Filter to subsystem(s); repeatable. "
                             "Options: flight_dynamics, engine, avionics_bus, "
                             "ew_sensor, structural, environmental")
    parser.add_argument("--bus", choices=["1553", "arinc429"], default=None,
                        help="Generate bus capture instead of telemetry")
    parser.add_argument("--bus-duration", type=float, default=1.0,
                        help="Bus capture duration in seconds (default: 1.0)")

    args = parser.parse_args()

    gen = F35TelemetryGenerator(seed=args.seed)

    if args.bus:
        result = gen.generate_bus_capture(
            output=args.output,
            duration_seconds=args.bus_duration,
            bus_type=args.bus,
        )
        if result is not None:
            sys.stdout.write(result)
    else:
        if args.output:
            gen.generate(
                profile=args.profile,
                duration_seconds=args.duration,
                output=args.output,
                subsystems=args.subsystem,
            )
        else:
            for row in gen.stream(
                profile=args.profile,
                duration_seconds=args.duration,
                include_header=True,
                subsystems=args.subsystem,
            ):
                print(row)


if __name__ == "__main__":
    main()
