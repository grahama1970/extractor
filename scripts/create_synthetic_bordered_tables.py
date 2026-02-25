#!/usr/bin/env python3
"""Create synthetic PDFs with bordered tables for training data balance.

Generates PDFs with various bordered table styles to produce lattice_*
strategy outcomes, balancing the stream_default-dominated training set.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "pdfs"


def _styles():
    return getSampleStyleSheet()


def create_defense_requirements_pdf(path: Path):
    """MIL-STD style requirements table with thick borders."""
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = _styles()
    story = []

    story.append(Paragraph("MIL-STD-SYNTH-001 — System Requirements", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Table 1. Performance Requirements", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data = [
        ["Req ID", "Requirement", "Threshold", "Objective", "Verification"],
        ["SRD-001", "Operating Temperature", "-40°C to +71°C", "-54°C to +85°C", "Test"],
        ["SRD-002", "Shock Resistance", "40g, 11ms", "75g, 6ms", "Test"],
        ["SRD-003", "Vibration (Random)", "7.7 grms", "10.0 grms", "Test"],
        ["SRD-004", "EMI Susceptibility", "MIL-STD-461G CS101", "MIL-STD-461G CS101/CS114", "Test"],
        ["SRD-005", "MTBF", ">2000 hrs", ">5000 hrs", "Analysis"],
        ["SRD-006", "Weight", "<15 kg", "<12 kg", "Inspection"],
        ["SRD-007", "Power Consumption", "<150W steady", "<120W steady", "Test"],
        ["SRD-008", "Data Rate", "≥100 Mbps", "≥1 Gbps", "Test"],
    ]

    t = Table(data, colWidths=[0.8 * inch, 1.8 * inch, 1.3 * inch, 1.5 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1.5, colors.black),
        ("BOX", (0, 0), (-1, -1), 2.5, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * inch))

    # Second table — interface requirements
    story.append(Paragraph("Table 2. Interface Requirements", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data2 = [
        ["Interface", "Protocol", "Connector", "Data Rate", "Notes"],
        ["Primary Data", "Ethernet 1000BASE-T", "MIL-DTL-38999", "1 Gbps", "Redundant pair"],
        ["Control Bus", "MIL-STD-1553B", "MIL-DTL-38999", "1 Mbps", "Dual redundant"],
        ["Power Input", "28V DC ±4V", "MIL-DTL-26482", "N/A", "MIL-STD-704F"],
        ["Debug Port", "RS-422", "Micro-D", "115.2 kbps", "Maintenance only"],
        ["RF Output", "L-Band", "SMA", "N/A", "50Ω impedance"],
        ["GPS Antenna", "L1/L2", "TNC", "N/A", "Active antenna"],
    ]

    t2 = Table(data2, colWidths=[1.0 * inch, 1.5 * inch, 1.2 * inch, 0.9 * inch, 1.3 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1.5, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)

    doc.build(story)


def create_engineering_specs_pdf(path: Path):
    """Engineering specification tables with full grid borders."""
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = _styles()
    story = []

    story.append(Paragraph("Component Specification — Power Supply Unit", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    # Electrical characteristics
    story.append(Paragraph("Table 1. Electrical Characteristics", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data = [
        ["Parameter", "Min", "Typ", "Max", "Unit", "Condition"],
        ["Input Voltage", "18", "28", "36", "V DC", "Continuous"],
        ["Input Current", "—", "5.4", "8.5", "A", "Full load"],
        ["Output Voltage (3.3V)", "3.234", "3.300", "3.366", "V", "0-100% load"],
        ["Output Voltage (5V)", "4.900", "5.000", "5.100", "V", "0-100% load"],
        ["Output Voltage (12V)", "11.76", "12.00", "12.24", "V", "0-100% load"],
        ["Ripple (3.3V)", "—", "15", "33", "mV p-p", "20MHz BW"],
        ["Ripple (5V)", "—", "20", "50", "mV p-p", "20MHz BW"],
        ["Ripple (12V)", "—", "40", "120", "mV p-p", "20MHz BW"],
        ["Efficiency", "87", "92", "—", "%", "Full load, 28V"],
        ["Operating Temp", "-55", "—", "+125", "°C", "Derated above 85°C"],
    ]

    t = Table(data, colWidths=[1.4 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 1.3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#154360")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#555555")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eaf2f8")]),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * inch))

    # Mechanical specs
    story.append(Paragraph("Table 2. Mechanical Specifications", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data2 = [
        ["Parameter", "Value", "Tolerance", "Unit"],
        ["Length", "152.4", "±0.25", "mm"],
        ["Width", "101.6", "±0.25", "mm"],
        ["Height", "38.1", "±0.50", "mm"],
        ["Weight", "680", "±20", "g"],
        ["Mounting Holes", "4x M4", "—", "—"],
        ["Baseplate Material", "6061-T6 Al", "—", "—"],
        ["Surface Finish", "Chem film per MIL-DTL-5541", "—", "—"],
        ["Conformal Coating", "Per MIL-I-46058C, Type UR", "—", "—"],
    ]

    t2 = Table(data2, colWidths=[2.0 * inch, 1.8 * inch, 1.0 * inch, 0.8 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0e6655")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.4 * inch))

    # Test matrix
    story.append(Paragraph("Table 3. Qualification Test Matrix", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data3 = [
        ["Test", "Standard", "Level", "Duration", "Pass/Fail Criteria"],
        ["High Temp Op", "MIL-STD-810H 501.7", "+71°C", "72 hrs", "All params within spec"],
        ["Low Temp Op", "MIL-STD-810H 502.7", "-40°C", "72 hrs", "All params within spec"],
        ["Thermal Shock", "MIL-STD-810H 503.7", "-40/+71°C", "100 cycles", "No degradation"],
        ["Vibration", "MIL-STD-810H 514.8", "Cat 24", "3 axes", "No resonance shift >5%"],
        ["Shock", "MIL-STD-810H 516.8", "40g 11ms", "3 axes ×2", "Functional after"],
        ["Humidity", "MIL-STD-810H 507.6", "95% RH", "240 hrs", "No corrosion"],
        ["Altitude", "MIL-STD-810H 500.6", "70,000 ft", "4 hrs", "No arcing"],
        ["Salt Fog", "MIL-STD-810H 509.7", "5% NaCl", "48 hrs", "No corrosion"],
        ["EMI/EMC", "MIL-STD-461G", "All applicable", "Per std", "Per limits"],
    ]

    t3 = Table(data3, colWidths=[0.9 * inch, 1.4 * inch, 0.9 * inch, 0.8 * inch, 1.5 * inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a235a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 1.5, colors.black),
        ("BOX", (0, 0), (-1, -1), 2.5, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4ecf7")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t3)

    doc.build(story)


def create_financial_bordered_pdf(path: Path):
    """Financial/audit-style tables with heavy borders and merged cells."""
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = _styles()
    story = []

    story.append(Paragraph("Quarterly Financial Summary — Q4 FY2025", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    # Income statement
    story.append(Paragraph("Table 1. Consolidated Income Statement", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data = [
        ["", "Q4 FY2025", "Q3 FY2025", "Q4 FY2024", "YoY Change"],
        ["Revenue", "$142.3M", "$138.7M", "$121.5M", "+17.1%"],
        ["  Product Revenue", "$98.6M", "$95.2M", "$84.3M", "+17.0%"],
        ["  Service Revenue", "$43.7M", "$43.5M", "$37.2M", "+17.5%"],
        ["Cost of Revenue", "$71.2M", "$69.8M", "$63.4M", "+12.3%"],
        ["Gross Profit", "$71.1M", "$68.9M", "$58.1M", "+22.4%"],
        ["Gross Margin", "50.0%", "49.7%", "47.8%", "+2.2pp"],
        ["Operating Expenses", "$52.3M", "$50.1M", "$45.6M", "+14.7%"],
        ["  R&D", "$28.4M", "$27.2M", "$24.1M", "+17.8%"],
        ["  Sales & Marketing", "$15.7M", "$14.9M", "$13.8M", "+13.8%"],
        ["  G&A", "$8.2M", "$8.0M", "$7.7M", "+6.5%"],
        ["Operating Income", "$18.8M", "$18.8M", "$12.5M", "+50.4%"],
        ["Net Income", "$14.2M", "$14.0M", "$9.3M", "+52.7%"],
        ["EPS (Diluted)", "$1.42", "$1.40", "$0.93", "+52.7%"],
    ]

    t = Table(data, colWidths=[1.6 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2631")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        # Bold total rows
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
        ("FONTNAME", (0, 11), (-1, 11), "Helvetica-Bold"),
        ("FONTNAME", (0, 12), (-1, 12), "Helvetica-Bold"),
        ("FONTNAME", (0, 13), (-1, 13), "Helvetica-Bold"),
        ("LINEABOVE", (0, 5), (-1, 5), 1.5, colors.black),
        ("LINEABOVE", (0, 11), (-1, 11), 1.5, colors.black),
        ("LINEABOVE", (0, 12), (-1, 12), 1.5, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * inch))

    # Balance sheet
    story.append(Paragraph("Table 2. Balance Sheet Summary", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data2 = [
        ["Assets", "FY2025", "FY2024"],
        ["Cash & Equivalents", "$245.3M", "$198.7M"],
        ["Accounts Receivable", "$67.8M", "$58.2M"],
        ["Inventory", "$42.1M", "$38.9M"],
        ["Total Current Assets", "$372.4M", "$310.5M"],
        ["PP&E (net)", "$89.6M", "$82.3M"],
        ["Goodwill & Intangibles", "$156.2M", "$156.2M"],
        ["Total Assets", "$643.8M", "$572.1M"],
        ["", "", ""],
        ["Liabilities & Equity", "FY2025", "FY2024"],
        ["Accounts Payable", "$34.5M", "$31.2M"],
        ["Current Debt", "$25.0M", "$25.0M"],
        ["Total Current Liabilities", "$78.2M", "$73.4M"],
        ["Long-term Debt", "$100.0M", "$125.0M"],
        ["Total Liabilities", "$198.7M", "$218.9M"],
        ["Total Equity", "$445.1M", "$353.2M"],
        ["Total L&E", "$643.8M", "$572.1M"],
    ]

    t2 = Table(data2, colWidths=[2.2 * inch, 1.5 * inch, 1.5 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2631")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 9), (-1, 9), colors.HexColor("#1b2631")),
        ("TEXTCOLOR", (0, 9), (-1, 9), colors.white),
        ("FONTNAME", (0, 9), (-1, 9), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("FONTNAME", (0, 7), (-1, 7), "Helvetica-Bold"),
        ("FONTNAME", (0, 12), (-1, 12), "Helvetica-Bold"),
        ("FONTNAME", (0, 14), (-1, 14), "Helvetica-Bold"),
        ("FONTNAME", (0, 15), (-1, 15), "Helvetica-Bold"),
        ("FONTNAME", (0, 16), (-1, 16), "Helvetica-Bold"),
        ("LINEABOVE", (0, 4), (-1, 4), 1.5, colors.black),
        ("LINEABOVE", (0, 7), (-1, 7), 1.5, colors.black),
        ("LINEABOVE", (0, 16), (-1, 16), 1.5, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t2)

    doc.build(story)


def create_multipage_bordered_pdf(path: Path):
    """Multi-page PDF with bordered tables on every page — max lattice outcomes."""
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = _styles()
    story = []

    story.append(Paragraph("Technical Data Package — Subsystem Allocations", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))

    # Generate several tables across multiple pages
    subsystems = [
        ("Avionics", [
            ["Parameter", "Requirement", "Allocation", "Margin", "Status"],
            ["Processing", "1000 MIPS", "850 MIPS", "15%", "Green"],
            ["Memory", "4 GB", "3.2 GB", "20%", "Green"],
            ["Bus Bandwidth", "1 Gbps", "780 Mbps", "22%", "Green"],
            ["Latency", "<10 ms", "7.2 ms", "28%", "Green"],
            ["Power", "45W", "41W", "9%", "Yellow"],
            ["Weight", "2.5 kg", "2.3 kg", "8%", "Yellow"],
            ["MTBF", "10,000 hr", "12,500 hr", "25%", "Green"],
            ["BIT Coverage", ">95%", "97.2%", "2.2pp", "Green"],
        ]),
        ("Communications", [
            ["Parameter", "Requirement", "Allocation", "Margin", "Status"],
            ["Tx Power", "20 dBm", "18 dBm", "2 dB", "Yellow"],
            ["Rx Sensitivity", "-95 dBm", "-98 dBm", "3 dB", "Green"],
            ["Frequency Range", "225-400 MHz", "225-400 MHz", "N/A", "Green"],
            ["Channel Spacing", "25 kHz", "25 kHz", "N/A", "Green"],
            ["Data Rate", "16 kbps", "19.2 kbps", "20%", "Green"],
            ["ECCM Modes", "≥3", "4", "33%", "Green"],
            ["Crypto", "Type 1", "Type 1", "N/A", "Green"],
            ["Antenna Gain", "0 dBi", "2.1 dBi", "2.1 dB", "Green"],
        ]),
        ("Navigation", [
            ["Parameter", "Requirement", "Allocation", "Margin", "Status"],
            ["Position Accuracy", "10 m CEP", "7.5 m CEP", "25%", "Green"],
            ["Velocity Accuracy", "0.1 m/s", "0.08 m/s", "20%", "Green"],
            ["Time to First Fix", "<60 s", "45 s", "25%", "Green"],
            ["Update Rate", "10 Hz", "20 Hz", "100%", "Green"],
            ["Anti-Jam", "40 dB", "35 dB", "-5 dB", "Red"],
            ["INS Drift", "1 nmi/hr", "0.8 nmi/hr", "20%", "Green"],
            ["SAASM", "Required", "Implemented", "N/A", "Green"],
        ]),
        ("Power Distribution", [
            ["Parameter", "Requirement", "Allocation", "Margin", "Status"],
            ["Total Power Budget", "5 kW", "4.2 kW", "16%", "Green"],
            ["Emergency Power", "500W / 30min", "500W / 45min", "50%", "Green"],
            ["Voltage Regulation", "±2%", "±1.5%", "25%", "Green"],
            ["Transient Recovery", "<100 µs", "75 µs", "25%", "Green"],
            ["Fault Isolation", "<50 ms", "35 ms", "30%", "Green"],
            ["Bus Voltage", "270V DC", "270V DC", "N/A", "Green"],
            ["Ground Fault", "<1 mA", "0.3 mA", "70%", "Green"],
            ["Arc Fault Detect", "Required", "Implemented", "N/A", "Green"],
        ]),
        ("Thermal Management", [
            ["Parameter", "Requirement", "Allocation", "Margin", "Status"],
            ["Max Junction Temp", "125°C", "115°C", "10°C", "Green"],
            ["Cooling Capacity", "3 kW", "3.5 kW", "17%", "Green"],
            ["Coolant Flow Rate", "5 L/min", "6 L/min", "20%", "Green"],
            ["Inlet Temp", "<40°C", "35°C", "5°C", "Green"],
            ["Pressure Drop", "<50 kPa", "42 kPa", "16%", "Green"],
            ["Cold Plate θ", "<0.5°C/W", "0.35°C/W", "30%", "Green"],
            ["Fan Reliability", "50,000 hr", "65,000 hr", "30%", "Green"],
        ]),
        ("Structures", [
            ["Parameter", "Requirement", "Allocation", "Margin", "Status"],
            ["Ultimate Load Factor", "9.0g", "9.0g", "1.5 FS", "Green"],
            ["Fatigue Life", "6000 hrs", "8000 hrs", "33%", "Green"],
            ["Stiffness (1st mode)", ">25 Hz", "32 Hz", "28%", "Green"],
            ["Weight", "450 kg", "438 kg", "2.7%", "Yellow"],
            ["CG Location", "Sta 245±5", "Sta 243.8", "0.5%", "Green"],
            ["Moment of Inertia Ixx", "120 kg·m²", "118 kg·m²", "1.7%", "Green"],
            ["Corrosion Protection", "MIL-PRF-23377", "Applied", "N/A", "Green"],
        ]),
    ]

    status_colors = {
        "Green": colors.HexColor("#27ae60"),
        "Yellow": colors.HexColor("#f39c12"),
        "Red": colors.HexColor("#e74c3c"),
    }

    for subsystem_name, table_data in subsystems:
        story.append(Paragraph(f"Table: {subsystem_name} Subsystem Allocations", styles["Heading2"]))
        story.append(Spacer(1, 0.1 * inch))

        t = Table(table_data, colWidths=[1.2 * inch, 1.2 * inch, 1.1 * inch, 0.8 * inch, 0.7 * inch])

        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 1.5, colors.black),
            ("BOX", (0, 0), (-1, -1), 2, colors.black),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

        # Color-code status column
        for row_idx in range(1, len(table_data)):
            status = table_data[row_idx][-1]
            if status in status_colors:
                style_cmds.append(("TEXTCOLOR", (4, row_idx), (4, row_idx), status_colors[status]))
                style_cmds.append(("FONTNAME", (4, row_idx), (4, row_idx), "Helvetica-Bold"))

        t.setStyle(TableStyle(style_cmds))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)


def create_dense_grid_pdf(path: Path):
    """Dense grid tables — lookup tables, truth tables, register maps."""
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = _styles()
    story = []

    story.append(Paragraph("Hardware Register Map — Controller FPGA", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    # Register map
    story.append(Paragraph("Table 1. Register Address Map", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data = [
        ["Offset", "Name", "Width", "Access", "Reset", "Description"],
        ["0x0000", "CTRL", "32", "RW", "0x00000001", "Main control register"],
        ["0x0004", "STATUS", "32", "RO", "0x00000000", "Status register"],
        ["0x0008", "INT_EN", "32", "RW", "0x00000000", "Interrupt enable"],
        ["0x000C", "INT_STAT", "32", "RW1C", "0x00000000", "Interrupt status"],
        ["0x0010", "DATA_IN", "32", "WO", "—", "Input data FIFO"],
        ["0x0014", "DATA_OUT", "32", "RO", "—", "Output data FIFO"],
        ["0x0018", "FIFO_STAT", "32", "RO", "0x00000100", "FIFO status"],
        ["0x001C", "DMA_ADDR", "32", "RW", "0x00000000", "DMA base address"],
        ["0x0020", "DMA_LEN", "16", "RW", "0x0000", "DMA transfer length"],
        ["0x0024", "DMA_CTRL", "8", "RW", "0x00", "DMA control"],
        ["0x0028", "CLK_DIV", "16", "RW", "0x0004", "Clock divider"],
        ["0x002C", "VERSION", "32", "RO", "0x01020003", "IP version (1.2.3)"],
        ["0x0030", "SCRATCH", "32", "RW", "0x00000000", "Scratch register"],
        ["0x0034", "DEBUG", "32", "RO", "—", "Debug status"],
    ]

    t = Table(data, colWidths=[0.7 * inch, 0.8 * inch, 0.5 * inch, 0.6 * inch, 1.0 * inch, 1.8 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Courier"),
        ("FONTNAME", (4, 1), (4, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
        ("ALIGN", (0, 0), (4, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * inch))

    # Bit field detail
    story.append(Paragraph("Table 2. CTRL Register Bit Fields", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data2 = [
        ["Bits", "Field", "Access", "Reset", "Description"],
        ["31:16", "RESERVED", "RO", "0x0000", "Reserved — reads as zero"],
        ["15:12", "MODE", "RW", "0x0", "Operating mode select"],
        ["11", "DMA_EN", "RW", "0", "DMA enable"],
        ["10", "INT_EN", "RW", "0", "Global interrupt enable"],
        ["9:8", "FIFO_THR", "RW", "0x0", "FIFO threshold select"],
        ["7:4", "PRESCALE", "RW", "0x0", "Clock prescaler"],
        ["3", "LOOPBACK", "RW", "0", "Loopback test mode"],
        ["2", "FLUSH", "RW", "0", "FIFO flush (auto-clear)"],
        ["1", "RESET", "RW", "0", "Soft reset (auto-clear)"],
        ["0", "ENABLE", "RW", "1", "Module enable"],
    ]

    t2 = Table(data2, colWidths=[0.7 * inch, 1.0 * inch, 0.6 * inch, 0.7 * inch, 2.5 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTNAME", (0, 1), (1, -1), "Courier"),
        ("FONTNAME", (3, 1), (3, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f7")]),
        ("ALIGN", (0, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.4 * inch))

    # Truth table / state machine
    story.append(Paragraph("Table 3. Mode Select Truth Table", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data3 = [
        ["MODE[3:0]", "Operating Mode", "Clock", "Data Width", "Duplex"],
        ["0x0", "Idle", "—", "—", "—"],
        ["0x1", "SPI Master", "SCLK out", "8-bit", "Full"],
        ["0x2", "SPI Slave", "SCLK in", "8-bit", "Full"],
        ["0x3", "I2C Master", "SCL out", "8-bit", "Half"],
        ["0x4", "I2C Slave", "SCL in", "8-bit", "Half"],
        ["0x5", "UART", "Baud gen", "8-bit", "Full"],
        ["0x6", "Parallel 8", "PCLK", "8-bit", "Half"],
        ["0x7", "Parallel 16", "PCLK", "16-bit", "Half"],
        ["0x8", "DMA Streaming", "System", "32-bit", "Half"],
        ["0x9-0xE", "Reserved", "—", "—", "—"],
        ["0xF", "Test Mode", "Internal", "32-bit", "Loopback"],
    ]

    t3 = Table(data3, colWidths=[0.9 * inch, 1.2 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1117")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#58a6ff")),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#333333")),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fafafa"), colors.HexColor("#f0f0f0")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t3)

    doc.build(story)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = [
        ("synth_defense_requirements.pdf", create_defense_requirements_pdf),
        ("synth_engineering_specs.pdf", create_engineering_specs_pdf),
        ("synth_financial_bordered.pdf", create_financial_bordered_pdf),
        ("synth_multipage_allocations.pdf", create_multipage_bordered_pdf),
        ("synth_dense_grid_registers.pdf", create_dense_grid_pdf),
    ]

    for filename, creator in pdfs:
        path = OUTPUT_DIR / filename
        creator(path)
        size_kb = path.stat().st_size / 1024
        print(f"Created {path.name} ({size_kb:.1f} KB)")

    print(f"\n{len(pdfs)} synthetic PDFs created in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
