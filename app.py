import io
import math
import xml.etree.ElementTree as ET
from geopy.distance import geodesic
import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import simplekml
import streamlit as st

st.set_page_config(
    page_title="Highway Alignment & Chainage Tool", layout="wide"
)

st.title("🛣️ Highway Alignment & Chainage Engineering Tool")

tab1, tab2 = st.tabs(
    ["📍 Chainage Generator", "📐 Horizontal Alignment & Best Fit Curves"]
)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------


def extract_coords(kml_bytes):
    root = ET.fromstring(kml_bytes)
    coords = []
    for elem in root.iter():
        if elem.tag.endswith("coordinates"):
            raw_text = elem.text.strip()
            points = raw_text.split()
            for p in points:
                parts = p.split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    coords.append((lat, lon))
            if coords:
                break
    return coords


def rdp_simplify(pts, epsilon):
    """Ramer-Douglas-Peucker algorithm to filter Polyline into PIs"""
    if len(pts) < 3:
        return pts
    dmax = 0.0
    index = 0
    end = len(pts) - 1

    p1 = np.array(pts[0])
    p2 = np.array(pts[end])

    for i in range(1, end):
        p3 = np.array(pts[i])
        if np.all(p1 == p2):
            d = np.linalg.norm(p3 - p1)
        else:
            d = np.linalg.norm(np.cross(p2 - p1, p1 - p3)) / np.linalg.norm(
                p2 - p1
            )
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        rec_res1 = rdp_simplify(pts[: index + 1], epsilon)
        rec_res2 = rdp_simplify(pts[index:], epsilon)
        return rec_res1[:-1] + rec_res2
    else:
        return [pts[0], pts[end]]


def calculate_bearing(p1, p2):
    """Calculates bearing between two (lat, lon) coordinates in degrees"""
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(
        lat2
    ) * math.cos(dlon)
    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360


def generate_excel_alignment_report(
    curve_data, total_len, design_speed, terrain_type
):
    """Generates a professional Excel Engineering Report for Horizontal Alignment"""
    wb = openpyxl.Workbook()

    # Sheet 1: Executive Summary
    ws_sum = wb.active
    ws_sum.title = "Executive Summary"
    ws_sum.views.sheetView[0].showGridLines = True

    # Header styling
    header_fill = PatternFill(
        start_color="1F4E78", end_color="1F4E78", fill_type="solid"
    )
    section_fill = PatternFill(
        start_color="D9E1F2", end_color="D9E1F2", fill_type="solid"
    )
    white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=16, bold=True, color="1F4E78")
    bold_font = Font(name="Calibri", size=11, bold=True)
    normal_font = Font(name="Calibri", size=11)

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    ws_sum["A1"] = "HIGHWAY HORIZONTAL ALIGNMENT DESIGN REPORT"
    ws_sum["A1"].font = title_font

    ws_sum["A3"] = "1. Project & Design Criteria Summary"
    ws_sum.merge_cells("A3:D3")
    ws_sum["A3"].font = bold_font
    ws_sum["A3"].fill = section_fill

    summary_rows = [
        ("Design Speed", f"{design_speed} km/h"),
        ("Terrain Classification", terrain_type),
        ("Total Road Alignment Length", f"{total_len/1000:.3f} km"),
        ("Total Intersection Points (PIs)", len(curve_data)),
        ("Standard Guidelines", "IRC:73 / IRC:SP:48 / MORTH"),
    ]

    for r_idx, (k, v) in enumerate(summary_rows, start=4):
        ws_sum.cell(row=r_idx, column=1, value=k).font = bold_font
        ws_sum.cell(row=r_idx, column=2, value=v).font = normal_font

    # Sheet 2: Curve Data Schedule
    ws_curves = wb.create_sheet(title="Horizontal Curve Schedule")
    ws_curves.views.sheetView[0].showGridLines = True

    headers = [
        "PI No.",
        "Latitude (°)",
        "Longitude (°)",
        "Deflection Angle Δ (°)",
        "Direction",
        "Design Radius R (m)",
        "Tangent Length T (m)",
        "Curve Length L (m)",
        "PC Chainage (m)",
        "PI Chainage (m)",
        "PT Chainage (m)",
    ]

    ws_curves.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws_curves.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = white_bold
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, cd in enumerate(curve_data, start=2):
        direction = "Right" if cd["Deflection Angle (deg)"] > 0 else "Left"
        row_vals = [
            cd["PI Index"],
            cd["Latitude"],
            cd["Longitude"],
            abs(cd["Deflection Angle (deg)"]),
            direction,
            cd["Design Radius (m)"],
            cd["Tangent Length T (m)"],
            cd["Curve Length L (m)"],
            cd["PC Chainage (m)"],
            cd["PI Chainage (m)"],
            cd["PT Chainage (m)"],
        ]
        ws_curves.append(row_vals)

        for c_idx in range(1, len(row_vals) + 1):
            cell = ws_curves.cell(row=row_idx, column=c_idx)
            cell.font = normal_font
            cell.border = thin_border
            if c_idx in [2, 3, 4, 6, 7, 8, 9, 10, 11]:
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="center")

    # Adjust Column Widths
    for ws in [ws_sum, ws_curves]:
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ---------------------------------------------------------
# TAB 1: CHAINAGE GENERATOR
# ---------------------------------------------------------
with tab1:
    st.subheader("Generate Major & Minor Chainages")
    uploaded_file1 = st.file_uploader(
        "Upload Alignment KML File", type=["kml"], key="kml_tab1"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        start_chainage = st.number_input(
            "Start Chainage (m)", value=0, step=100, help="E.g., 0 for 0+000"
        )
    with col2:
        major_interval = st.number_input(
            "Major Interval (m)", value=100, step=10
        )
    with col3:
        minor_interval = st.number_input(
            "Minor Interval (m)", value=20, step=5
        )

    output_name1 = st.text_input(
        "Output File Name (Optional)",
        value="Chainage_Output",
        key="name_tab1",
    )
    reverse_direction1 = st.checkbox(
        "🔄 Reverse Road Direction (Start chainage from opposite end)",
        key="rev_tab1",
    )

    if uploaded_file1 is not None:
        if st.button("Generate Chainages"):
            coords = extract_coords(uploaded_file1.read())
            if not coords:
                st.error("No valid line string data found in KML!")
            else:
                if reverse_direction1:
                    coords = coords[::-1]

                kml = simplekml.Kml()
                linestring_coords = [(c[1], c[0]) for c in coords]
                line = kml.newlinestring(
                    name="Road Alignment", coords=linestring_coords
                )
                line.style.linestyle.width = 4
                line.style.linestyle.color = simplekml.Color.red

                accumulated_dist = 0.0
                current_chainage = float(start_chainage)

                km = int(current_chainage // 1000)
                m = int(current_chainage % 1000)
                pnt = kml.newpoint(
                    name=f"{km}+{m:03d}", coords=[(coords[0][1], coords[0][0])]
                )
                pnt.style.iconstyle.scale = 1.0
                pnt.style.iconstyle.color = simplekml.Color.red

                next_target = current_chainage + minor_interval

                for i in range(len(coords) - 1):
                    p1, p2 = coords[i], coords[i + 1]
                    segment_dist = geodesic(p1, p2).meters

                    while (
                        current_chainage + accumulated_dist + segment_dist
                    ) >= next_target:
                        overshoot = next_target - (
                            current_chainage + accumulated_dist
                        )
                        fraction = (
                            overshoot / segment_dist if segment_dist > 0 else 0
                        )

                        target_lat = p1[0] + fraction * (p2[0] - p1[0])
                        target_lon = p1[1] + fraction * (p2[1] - p1[1])

                        km = int(next_target // 1000)
                        m = int(next_target % 1000)
                        ch_text = f"{km}+{m:03d}"

                        pnt = kml.newpoint(
                            name=ch_text, coords=[(target_lon, target_lat)]
                        )
                        if int(next_target) % major_interval == 0:
                            pnt.style.iconstyle.scale = 1.0
                            pnt.style.iconstyle.color = simplekml.Color.red
                        else:
                            pnt.style.iconstyle.scale = 0.6
                            pnt.style.iconstyle.color = simplekml.Color.yellow

                        next_target += minor_interval

                    accumulated_dist += segment_dist

                st.success(
                    f"Success! Total Road Length: {accumulated_dist/1000:.3f} km"
                )

                fname = (
                    output_name1.strip()
                    if output_name1.strip()
                    else "Chainage_Output"
                )
                fname = fname if fname.endswith(".kml") else f"{fname}.kml"

                st.download_button(
                    label=f"📥 Download {fname}",
                    data=kml.kml(),
                    file_name=fname,
                    mime="application/vnd.google-earth.kml+xml",
                )


# ---------------------------------------------------------
# TAB 2: BEST FIT HORIZONTAL ALIGNMENT & REPORTING
# ---------------------------------------------------------
with tab2:
    st.subheader(
        "Generate Best Fit Curves & Detailed Horizontal Alignment Report"
    )
    uploaded_file2 = st.file_uploader(
        "Upload Raw KML Alignment", type=["kml"], key="kml_tab2"
    )

    st.markdown("#### ⚙️ Design & Analysis Parameters")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        design_radius = st.number_input(
            "Design Curve Radius R (meters)",
            value=150.0,
            step=10.0,
            help="Design radius for circular curves at IPs",
        )
    with col_b:
        design_speed = st.number_input(
            "Design Speed (km/h)",
            value=60,
            step=10,
            help="Project design speed for report compliance check",
        )
    with col_c:
        terrain_type = st.selectbox(
            "Terrain Classification",
            ["Plain", "Rolling", "Mountainous / Steep"],
        )

    filter_sensitivity = st.slider(
        "IP Filtering Sensitivity (Epsilon)",
        min_value=0.00005,
        max_value=0.00100,
        value=0.00020,
        step=0.00005,
        format="%.5f",
        help="Higher values reduce minor vertices and isolate main Intersection Points (PIs)",
    )

    output_name2 = st.text_input(
        "Output KML Name (Optional)",
        value="Smooth_Alignment_Fit",
        key="name_tab2",
    )

    if uploaded_file2 is not None:
        if st.button("Generate Alignment & Engineering Report"):
            raw_coords = extract_coords(uploaded_file2.read())

            if not raw_coords or len(raw_coords) < 3:
                st.error("Insufficient points in KML to construct alignment curves!")
            else:
                pi_coords = rdp_simplify(raw_coords, filter_sensitivity)

                curve_data = []
                smoothed_coords = []
                smoothed_coords.append((pi_coords[0][1], pi_coords[0][0]))

                kml_fit = simplekml.Kml()
                running_chainage = 0.0

                for i in range(1, len(pi_coords) - 1):
                    p_prev = pi_coords[i - 1]
                    p_curr = pi_coords[i]
                    p_next = pi_coords[i + 1]

                    b1 = calculate_bearing(p_prev, p_curr)
                    b2 = calculate_bearing(p_curr, p_next)

                    deflection = b2 - b1
                    if deflection > 180:
                        deflection -= 360
                    elif deflection < -180:
                        deflection += 360

                    abs_def = abs(deflection)
                    delta_rad = math.radians(abs_def)

                    tangent_dist = design_radius * math.tan(delta_rad / 2)
                    arc_length = design_radius * delta_rad

                    dist_prev = geodesic(p_prev, p_curr).meters
                    dist_next = geodesic(p_curr, p_next).meters

                    max_allowable_t = min(dist_prev / 2, dist_next / 2)
                    actual_t = min(tangent_dist, max_allowable_t)

                    frac_pc = 1.0 - (actual_t / dist_prev if dist_prev > 0 else 0)
                    pc_lat = p_prev[0] + frac_pc * (p_curr[0] - p_prev[0])
                    pc_lon = p_prev[1] + frac_pc * (p_curr[1] - p_prev[1])

                    frac_pt = actual_t / dist_next if dist_next > 0 else 0
                    pt_lat = p_curr[0] + frac_pt * (p_next[0] - p_curr[0])
                    pt_lon = p_curr[1] + frac_pt * (p_next[1] - p_curr[1])

                    dist_to_pi = geodesic(p_prev, p_curr).meters
                    pi_chainage = running_chainage + dist_to_pi
                    pc_chainage = pi_chainage - actual_t
                    pt_chainage = pc_chainage + arc_length

                    curve_data.append(
                        {
                            "PI Index": f"PI-{i}",
                            "Latitude": round(p_curr[0], 6),
                            "Longitude": round(p_curr[1], 6),
                            "Deflection Angle (deg)": round(deflection, 2),
                            "Design Radius (m)": design_radius,
                            "Tangent Length T (m)": round(actual_t, 2),
                            "Curve Length L (m)": round(arc_length, 2),
                            "PC Chainage (m)": round(pc_chainage, 2),
                            "PI Chainage (m)": round(pi_chainage, 2),
                            "PT Chainage (m)": round(pt_chainage, 2),
                        }
                    )

                    arc_points = 10
                    for step in range(arc_points + 1):
                        f = step / arc_points
                        lat_interp = (1 - f) ** 2 * pc_lat + 2 * (
                            1 - f
                        ) * f * p_curr[0] + f**2 * pt_lat
                        lon_interp = (1 - f) ** 2 * pc_lon + 2 * (
                            1 - f
                        ) * f * p_curr[1] + f**2 * pt_lon
                        smoothed_coords.append((lon_interp, lat_interp))

                    pnt = kml_fit.newpoint(
                        name=f"PI-{i} (Δ={deflection:.1f}°)",
                        coords=[(p_curr[1], p_curr[0])],
                    )
                    pnt.style.iconstyle.scale = 0.8
                    pnt.style.iconstyle.color = simplekml.Color.blue

                    running_chainage = pt_chainage

                smoothed_coords.append((pi_coords[-1][1], pi_coords[-1][0]))

                total_road_length = running_chainage + geodesic(
                    pi_coords[-2], pi_coords[-1]
                ).meters

                fit_line = kml_fit.newlinestring(
                    name="Best Fit Horizontal Alignment",
                    coords=smoothed_coords,
                )
                fit_line.style.linestyle.width = 4
                fit_line.style.linestyle.color = simplekml.Color.cyan

                st.success(
                    f"Alignment & Report generated successfully! Total Length: {total_road_length/1000:.3f} km"
                )

                df_curves = pd.DataFrame(curve_data)
                st.write("### 📋 Horizontal Curve Schedule & Geometry")
                st.dataframe(df_curves, use_container_width=True)

                col_dl1, col_dl2, col_dl3 = st.columns(3)

                fname2 = (
                    output_name2.strip()
                    if output_name2.strip()
                    else "Smooth_Alignment_Fit"
                )
                fname2 = fname2 if fname2.endswith(".kml") else f"{fname2}.kml"

                with col_dl1:
                    st.download_button(
                        label=f"📥 Download Alignment KML",
                        data=kml_fit.kml(),
                        file_name=fname2,
                        mime="application/vnd.google-earth.kml+xml",
                    )
                with col_dl2:
                    csv_data = df_curves.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📊 Download Curve Data (CSV)",
                        data=csv_data,
                        file_name="Horizontal_Curve_Schedule.csv",
                        mime="text/csv",
                    )
                with col_dl3:
                    excel_report = generate_excel_alignment_report(
                        curve_data,
                        total_road_length,
                        design_speed,
                        terrain_type,
                    )
                    st.download_button(
                        label="📄 Download Detailed Engineering Report (Excel)",
                        data=excel_report,
                        file_name="Horizontal_Alignment_Engineering_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
