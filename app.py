import xml.etree.ElementTree as ET
from geopy.distance import geodesic
import simplekml
import streamlit as st

st.set_page_config(page_title="KML Chainage Generator", layout="centered")

st.title("🛣️ Road KML Chainage Generator")
st.write(
    "Upload your Alignment KML file, configure interval settings, and download line with chainages."
)


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


def generate_chainage_kml(coords, start_ch, major_int, minor_int, reverse_dir):
    if reverse_dir:
        coords = coords[::-1]

    kml = simplekml.Kml()

    # 1. Road Alignment Line (Red Line)
    linestring_coords = [(c[1], c[0]) for c in coords]
    line = kml.newlinestring(name="Road Alignment", coords=linestring_coords)
    line.style.linestyle.width = 4
    line.style.linestyle.color = simplekml.Color.red

    accumulated_dist = 0.0
    current_chainage = float(start_ch)

    # Start Point
    km = int(current_chainage // 1000)
    m = int(current_chainage % 1000)
    pnt = kml.newpoint(
        name=f"{km}+{m:03d}", coords=[(coords[0][1], coords[0][0])]
    )
    pnt.style.iconstyle.scale = 1.0
    pnt.style.iconstyle.color = simplekml.Color.red

    next_target = current_chainage + minor_int

    # 2. Chainage Points Generation
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i + 1]
        segment_dist = geodesic(p1, p2).meters

        while (current_chainage + accumulated_dist + segment_dist) >= next_target:
            overshoot = next_target - (current_chainage + accumulated_dist)
            fraction = overshoot / segment_dist if segment_dist > 0 else 0

            target_lat = p1[0] + fraction * (p2[0] - p1[0])
            target_lon = p1[1] + fraction * (p2[1] - p1[1])

            km = int(next_target // 1000)
            m = int(next_target % 1000)
            ch_text = f"{km}+{m:03d}"

            pnt = kml.newpoint(name=ch_text, coords=[(target_lon, target_lat)])

            # Major vs Minor Styling
            if int(next_target) % major_int == 0:
                pnt.style.iconstyle.scale = 1.0  # Major (100m) - Red Pin
                pnt.style.iconstyle.color = simplekml.Color.red
            else:
                pnt.style.iconstyle.scale = 0.6  # Minor (20m) - Yellow Pin
                pnt.style.iconstyle.color = simplekml.Color.yellow

            next_target += minor_int

        accumulated_dist += segment_dist

    return kml.kml(), accumulated_dist


# UI Layout
uploaded_file = st.file_uploader("Upload KML File", type=["kml"])

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
    minor_interval = st.number_input("Minor Interval (m)", value=20, step=5)

# Output File Name Input
output_name = st.text_input(
    "Output File Name (Optional)",
    value="Chainage_Output",
    help="Enter file name without extension",
)

reverse_direction = st.checkbox(
    "🔄 Reverse Road Direction (Start chainage from opposite end)"
)

if uploaded_file is not None:
    if st.button("Generate Chainages"):
        kml_bytes = uploaded_file.read()
        coords = extract_coords(kml_bytes)

        if not coords:
            st.error("No valid line string data found in the KML file!")
        else:
            kml_data, total_len = generate_chainage_kml(
                coords,
                start_chainage,
                major_interval,
                minor_interval,
                reverse_direction,
            )
            st.success(f"Success! Total Road Length: {total_len/1000:.3f} km")

            # File name formatting
            clean_filename = (
                output_name.strip() if output_name.strip() else "Chainage_Output"
            )
            if not clean_filename.endswith(".kml"):
                final_filename = f"{clean_filename}.kml"
            else:
                final_filename = clean_filename

            st.download_button(
                label=f"📥 Download {final_filename}",
                data=kml_data,
                file_name=final_filename,
                mime="application/vnd.google-earth.kml+xml",
            )
