from pathlib import Path
import streamlit as st

from dashboard_common import APP_DIR, OUTPUT_DIR, footer, inject_css, load_data

st.set_page_config(page_title="Reports and Downloads", page_icon="📥", layout="wide")
inject_css()
master, _, _ = load_data(show_uploader=True)

st.markdown(
    '<div class="hero"><h1>Reports and Downloads</h1>'
    '<p>Download the master workbook, statistical results, report, presentation, and filtered data.</p></div>',
    unsafe_allow_html=True,
)

files = [
    ("Master Excel workbook", OUTPUT_DIR / "Hospital_Quality_Master.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("Master CSV", OUTPUT_DIR / "Hospital_Quality_Master.csv", "text/csv"),
    ("Statistical results", OUTPUT_DIR / "Statistical_Results.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("Word report", OUTPUT_DIR / "Hospital_Quality_Report.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("PowerPoint presentation", OUTPUT_DIR / "Hospital_Quality_Presentation.pptx",
     "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("Manual review workbook", OUTPUT_DIR / "Manual_Review.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
]

for label, path, mime in files:
    left, right = st.columns([4, 1])
    left.write(f"**{label}**")
    if path.exists():
        right.download_button(
            "Download", data=path.read_bytes(), file_name=path.name, mime=mime,
            key=f"download_{path.name}",
        )
    else:
        right.caption("Run main.py")

st.markdown("### Current master data")
st.download_button(
    "Download dashboard-ready CSV",
    master.to_csv(index=False).encode("utf-8"),
    file_name="dashboard_master_data.csv",
    mime="text/csv",
)

footer()
