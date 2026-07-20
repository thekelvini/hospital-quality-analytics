# Hospital Quality Project Version 6

Version 6 is a complete replacement for Version 5.

It retains the full Version 4 and Version 5 analysis pipeline. It adds a professional multipage Streamlit application.

## Included analysis pipeline

- Downloads the complete CMS Hospital General Information dataset.
- Reads the hospital base-rate dataset.
- Parses the local BCBS Blue Distinction Spine Surgery PDF.
- Matches CMS hospitals by CCN and hospital name.
- Matches BCBS hospitals by state and hospital name.
- Runs statistical analyses.
- Creates Excel, Word, and PowerPoint outputs.
- Creates publication-ready figures.

## Dashboard pages

- Executive Dashboard
- Hospital Explorer
- Hospital Profiles
- Compare Hospitals
- Analytics Lab
- Data Quality
- Reports and Downloads

## Setup

Copy the official BCBS PDF into the data folder:

`data/Blue_Distinction_Spine_Surgery.pdf`

Then open the project in VS Code.

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
python -m streamlit run app.py
```

You can also double-click:

- `run_project.bat` to rebuild the data outputs.
- `run_dashboard.bat` to launch the dashboard.
- `run_all.bat` to run the analysis and then launch the dashboard.

## Important

Close Excel, Word, and PowerPoint output files before rerunning `main.py`. Windows prevents Python from overwriting files that are open.


## Version 6.1
Restores the Version 5 upload control, CMS star slider, dashboard tabs, working Fast Access links, statistical view, and filtered export while retaining all Version 6 pages.


## Version 6.2 navigation fix

Version 6.2 replaces `st.page_link()` with button-based `st.switch_page()` navigation.
This avoids the Streamlit `KeyError: url_pathname` error.
