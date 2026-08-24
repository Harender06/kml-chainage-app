import xml.etree.ElementTree as ET
from geopy.distance import geodesic
import simplekml
import streamlit as st

st.set_page_config(page_title="KML Chainage Generator", layout="centered")

st.title("🛣️ Road KML Chainage Generator")
st.write(
    "अपनी Alignment KML फ़ाइल अपलोड करें और Major/Minor चेनज तुरंत जनरेट करें।"
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


def generate_chainage_kml(coords, major_int, minor_int):
    kml = simplekml.Kml()
    next_target = 0.0
    accumulated_dist = 0.0

    # Start Point 0+000
    pnt = kml.newpoint(name="0+000", coords=[(coords[0][1], coords[0][0])])
    pnt.style.iconstyle.scale = 1.0

    next_target += minor_int

    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i + 1]
        segment_dist = geodesic(p1, p2).meters

        while accumulated_dist + segment_dist >= next_target:
            overshoot = next_target - accumulated_dist
            fraction = overshoot / segment_dist if segment_dist > 0 else 0

            target_lat = p1[0] + fraction * (p2[0] - p1[0])
            target_lon = p1[1] + fraction * (p2[1] - p1[1])

            km = int(next_target // 1000)
            m = int(next_target % 1000)
            ch_text = f"{km}+{m:03d}"

            # Major vs Minor Styling
            pnt = kml.newpoint(name=ch_text, coords=[(target_lon, target_lat)])
            if int(next_target) % major_int == 0:
                pnt.style.iconstyle.scale = 1.0  # Major (100m) bada dikhega
                pnt.style.iconstyle.color = simplekml.Color.red
            else:
                pnt.style.iconstyle.scale = 0.6  # Minor (20m) chhota dikhega
                pnt.style.iconstyle.color = simplekml.Color.yellow

            next_target += minor_int

        accumulated_dist += segment_dist

    return kml.kml(), accumulated_dist


# UI Controls
uploaded_file = st.file_uploader("KML File Upload Karein", type=["kml"])

col1, col2 = st.columns(2)
with col1:
    major_interval = st.number_input(
        "Major Chainage (Meters)", value=100, step=10
    )
with col2:
    minor_interval = st.number_input(
        "Minor Chainage (Meters)", value=20, step=5
    )

if uploaded_file is not None:
    if st.button("Generate Chainages"):
        kml_bytes = uploaded_file.read()
        coords = extract_coords(kml_bytes)

        if not coords:
            st.error("KML file me koi line data nahi mila!")
        else:
            kml_data, total_len = generate_chainage_kml(
                coords, major_interval, minor_interval
            )
            st.success(f"Done! Total Length: {total_len/1000:.3f} km")

            st.download_button(
                label="📥 Download Chainage KML",
                data=kml_data,
                file_name="Chainage_Output.kml",
                mime="application/vnd.google-earth.kml+xml",
            )