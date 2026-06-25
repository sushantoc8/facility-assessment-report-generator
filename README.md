### Facility Assessment Report Generator ###

Live App: https://facility-assessment-report-generator-kfy5.onrender.com/
GitHub Repository: https://github.com/sushantoc8/facility-assessment-report-generator


## Overview ##
This project was built for the Medelite Technical Case Study. It is a lightweight web application that allows a user to enter 
a facility’s CMS Certification Number (CCN), pull public facility data, add Medelite-specific operational inputs, and generate 
a polished Facility Assessment Snapshot as a PDF.

The main goal of this project was to make the facility review process faster and easier. Instead of manually searching through 
public healthcare databases and separate notes, the app brings the most important facility information into one simple report generator.


## How the Application Works ##
A user enters a CCN into the app, and the application fetches the matching nursing facility data from the CMS public data source. The app
then displays the facility information and lets the user add internal details such as EMR, current census, patient type, previous Medelite
coverage, previous provider performance, and medical coverage.

For the facility name, I added conditional override logic. The official CMS facility name is used by default, but if the user enters a 
custom facility name, the custom name replaces the CMS name in the final report. This keeps the report accurate to the public data while
still supporting Medelite’s internal naming workflow.

The generated PDF includes the required “INFINITE – Managed by MEDELITE” branding, the Facility Assessment Snapshot header, facility 
information, star ratings, manual operational inputs, and a clickable Medicare Care Compare link built dynamically from the entered CCN.


## Tech Stack ##
This project was built using Python, HTML, CSS, JavaScript, ReportLab for PDF generation, the CMS Provider Data Catalog API for public 
facility data, GitHub for version control, and Render for live deployment.


## Data Validation ##
To make sure the data was accurate, I tested the application using the provided sample CCN 686123 for Kendall Lakes Healthcare and Rehab 
Center. I verified the facility data by comparing the app’s output with the official Medicare Care Compare website and the case study 
reference materials. This helped confirm that the CMS fields were being mapped correctly into the cleaner report labels used in the final
PDF.


## Biggest Challenge ##
The biggest challenge was getting the CMS data to fetch and map correctly. The raw government data was not already organized
in the same clean format as the report, so I had to inspect the API response, identify the correct fields, and build the 
logic that translated that raw data into the final report layout. At first, the data was not being fetched and displayed properly
, but I debugged the issue by testing with the sample CCN, checking the returned API fields, and comparing the results against 
Medicare Care Compare until the mappings were correct.

What made the project possible was breaking the problem into smaller parts: first confirming that the CCN lookup worked, 
then mapping the CMS data, then adding the manual inputs, and finally generating the PDF. 
This helped me turn a broad real-world workflow into a working hosted application.


## Running Locally ##
To run the project locally, clone the repository, install the required dependencies, and start the application with Python.

git clone https://github.com/sushantoc8/facility-assessment-report-generator.git
cd facility-assessment-report-generator
pip install -r requirements.txt
python app.py

Then open the local URL shown in the terminal.


## Test Case ##
A good test case is CCN 686123, which should load the facility data for Kendall Lakes Healthcare and Rehab Center. After the data 
loads, the user can fill in the manual fields and download the final PDF report.


## Future Improvements ##
With more time, I would add more advanced hospitalization and emergency department metrics, improve the frontend loading states, 
and add more automated tests around the CMS field mapping. I would also continue refining the PDF styling so the report feels even
closer to a production-ready internal business document and tackle the extra bonus features mentioned.

