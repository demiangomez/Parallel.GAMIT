# Parallel.GAMIT Login Page

Provide your credentials for login to Parallel.GAMIT

![image](https://github.com/user-attachments/assets/dbdb2bfa-0908-41e8-8605-0dde95324648)

## Parallel.GAMIT Map Interface

The Parallel.GAMIT platform includes an interactive map interface designed for monitoring and managing a network of stations.

### Key Features

- **Search Functionality**  
  At the top of the interface, a search bar labeled **"Search for station code"** allows users to locate specific stations by their unique codes, providing quick access to relevant data points. Filters can be applied to only show specific countries and / or station networks.

- **Map Controls**  
  Users can navigate the map using the **zoom-in** and **zoom-out** buttons located on the left side. These controls enable a detailed view of station locations and regional geography.

- **Station Markers**  
  The map displays multiple station markers:
  - **Green Square Icons**: Represent standard station locations.
  - **Red Triangular Icons**: Likely indicate stations with specific statuses or alerts, distinguishing them from regular stations.
  
  The presence of these icons helps users visually identify different station types or operational statuses across the monitored area.

- **Station List**  
  On the right side of the interface, there is a **"Station lists"** sidebar. This feature provides additional details for managing and viewing individual stations, making it easier for users to analyze data related to specific stations or regions.

- **Map Base**  
  The interface uses **OpenStreetMap** as the geographical base, ensuring accurate and up-to-date cartographic information for the regions displayed. This base map provides the necessary context for station positioning and regional navigation.

![image](https://github.com/user-attachments/assets/36e1166b-5b0f-4a8a-909f-b697cd91ec41)

This map interface is a core component of the Parallel.GAMIT platform, offering an accessible, visual way to monitor and interact with station data across the region.

To access a station's details, click on it's map icon:

![image](https://github.com/user-attachments/assets/75fb4351-35c2-4569-9965-d5b77809ec11)

If the station has a problem that needs to be addressed, the station's errors will be displayed on the pop up:

![image](https://github.com/user-attachments/assets/75346cc6-950e-4441-a3e9-ed59635c61d1)


## Station Detail Interface

The Station Detail interface in the Parallel.GAMIT platform provides in-depth information on individual stations, including location data, error status, visit history, and associated media. This interface is valuable for monitoring station-specific details and ensuring metadata accuracy.

### Key Features

- **Station Information Summary**  
  A summary box providing essential details about the station, including:
  - **Station Code**: four-letter identifier of the station (e.g., "auma").
  - **Network**: Network code (e.g., "sag").
  - **Country**: Country code (e.g., "ARG").
  - **Latitude and Longitude**: Geodetic coordinates.
  - **Height**: Ellipsoidal height.
  
  The summary also displays the **last gaps update** date and time which is the timestamp of the last time the station was checked for RINEX and metadata gaps.

- **Error Status**  
  The **Station errors** section provides a quick overview of any operational issues. In the example below, the status shows **"No errors"**, indicating that the station metadata has no issues.

- **Map Overview**  
  A map section displays the station's geographical location, using **OpenStreetMap** as the base layer. This feature provides context to the station's location within the surrounding area, with zoom-in and zoom-out controls on the left for navigation. This map also offers a an overview of the track that can be used to reach the station (that can be loaded in the Metadata section or individually for site each visit).

- **Photos**  
  A photo section on the right side of the interface displays images related to the station, such as site setup and equipment. Each photo is labeled with its filename and description (e.g., "antenna," "antenna + box"), helping users quickly identify the station's setup and environmental conditions.

### Sidebar Navigation

The left sidebar contains additional navigation options for further station-specific data:
- **Information**: Metadata (station information) for the station.
- **Metadata**: Additional station metadata details.
- **Visits**: Logs and records of site visits.
- **Rinex**: Data files in RINEX format.
- **People**: Information on personnel associated with the station.

![Screenshot from 2024-11-09 12-55-32](https://github.com/user-attachments/assets/e0209616-f70c-4c93-acfc-140bbf0591d0)

This Station Detail interface allows for comprehensive monitoring and management of each station's data, offering visual, geographical, and operational insights at a glance.


## Equipment and Antenna Information Interface

The Equipment and Antenna Information interface in Parallel.GAMIT provides detailed records on equipment configurations, including receiver and antenna models, serial numbers, firmware versions, and operational dates. This information is essential for tracking equipment history and ensuring consistency in data collection. This metadata is stored in the PostgreSQL database ensuring consistency and also allowing automatic checks against RINEX data.

### Key Features

- **Equipment Details Table**  
  The table presents comprehensive data on various equipment used at the station, organized by columns:
  - **RX Code**: Model of the receiver (e.g., "TRIMBLE 4000SSE").
  - **RX Serial**: Serial number of the receiver.
  - **RX FW**: Firmware version installed on the receiver.
  - **ANT Code**: Antenna model code (e.g., "TRM22020.00+GP").
  - **ANT Serial**: Serial number of the antenna.
  - **Height**: Height information, relative to a specific reference point (see column **HC**).
  - **North/East**: Offset in the north and east directions.
  - **HC**: Height Code, detailing specific height settings (e.g., "DHARP").
  - **RAD**: Radome code, indicating if any radome equipment is used (e.g., "NONE").

- **Operational Dates**  
  Each entry in the table has **Date Start** and **Date End** columns, which record the period during which the specific equipment configuration was active. This historical tracking helps maintain a detailed operational timeline for GNSS processing.

- **Comments**  
  A **Comments** column is available for additional notes, allowing users to document specific details or issues related to each equipment configuration.

- **Modify and Add Options**  
  Users can modify existing entries using the **pencil icon** in the "Modify" column, or add new entries via the **Add** button at the top right. These options provide flexibility for updating or expanding equipment records as needed.

- **Navigation**  
  A pagination control at the bottom of the table allows users to navigate through multiple pages of equipment records if necessary, making it easier to manage extensive equipment histories.

### Usage

This interface serves as a crucial component for station management, allowing users to track and update equipment configurations over time, which ensures data consistency and supports troubleshooting and historical analysis.

![image](https://github.com/user-attachments/assets/97645104-db5c-4480-b536-195789c14453)

This Equipment and Antenna Information interface allows for efficient documentation and review of equipment specifics, essential for the ongoing maintenance and reliability of station operations.

## Edit Equipment and Antenna Information Interface

The Edit Equipment and Antenna Information interface in Parallel.GAMIT provides a form for updating or adding information about a station's equipment configuration. This interface allows users to input or modify data related to receiver and antenna specifications.

### Key Features

- **Form Fields**  
  The form includes several fields where users can enter or edit equipment information:
  - **Receiver Code**: Model of the receiver, must exists in the database (e.g., "TRIMBLE 4000SSE").
  - **Receiver Serial**: Serial number of the receiver unit.
  - **Receiver Firmware**: Firmware version running on the receiver.
  - **Antenna Code**: Antenna model code, must exists in the database (e.g., "TRM22020.00+GP").
  - **Antenna Serial**: Serial number of the antenna.
  - **Antenna Height**: Height information, relative to a specific reference point (see column **Height Code**).
  - **Antenna North/East**: Offset in the north and east directions.
  - **Height Code**: Height code setting (e.g., "DHARP").
  - **Radome Code**: Radome equipment code, if applicable (e.g., "NONE").

- **Date Start and Date End**  
  These fields allow users to specify the start and end dates of the equipment configuration. A **DOY** (Day of Year) checkbox is available to switch the date format if needed. When unchecked, a datepicker control appears allowing the user to enter Gregorian dates.

- **Receiver Version**  
  An additional field for the receiver version provides details about the equipment setup.

- **Comments**  
  An optional **Comments** field enables users to document specific notes, issues, or observations regarding the configuration.

- **Submit and Remove Options**  
  - **Submit**: Save the entered or updated information.
  - **Remove**: Delete the equipment configuration record.

![image](https://github.com/user-attachments/assets/5eddbaf3-0145-4976-8150-87897b8ff25c)

## Metadata Interface

The Metadata Interface in provides detailed metadata about a station, including general information, coordinates, last equipment specifications, and attached files. This interface allows users to review key station details and update them as needed.

### Key Features

- **General Information**  
  The General section provides an overview of the station's status and basic details:
  - **Station Type**: Classification of the station (e.g., "Campaign", "Continuous"). These can be added in the database for more flexibility.
  - **Monument**: Name or identifier of the monument and associated picture (e.g., "SAGA monument"). These can be added in the database for more flexibility.
  - **Status**: Current operational status (e.g., "Active Offline", "Active Online", "Destroyed", etc). These can be added in the database for more flexibility.
  - **Battery and Communications**: Indicators showing battery and communication status (e.g., red indicators for not present, green indicated installed).
  - **First/Last RINEX**: Timestamps for the first and most recent RINEX data recorded.
  - **Comments**: Additional notes about the station.
  - **Navigation File**: Link to a kmz file showing the best route to get to the station (e.g., "sag.auma.kmz").

- **Monument Photo**  
  A picture of the station's monument is displayed on the right side, helping users visually confirm the monument setup and condition.

- **Geodetic Coordinates**  
  This section shows the station’s geodetic coordinates:
  - **Latitude** and **Longitude**: Location in degrees, minutes, and seconds.
  - **Height**: Height in meters above the ellipsoid.

- **Cartesian Coordinates**  
  Displays the station's position in the ECEF Cartesian coordinate system with **X**, **Y**, and **Z** values.

- **Equipment**  
  Information about the station's latest equipment setup, including:
  - **Antenna Code** and **Antenna Serial**: Details about the antenna model and serial number.
  - **Receiver Serial** and **Receiver Version**: Receiver identification and firmware version.
  - **Height Code**: The height setting (e.g., "DHARP").
  - **Radome Code**: Code for any radome equipment used (e.g., "NONE").

- **Attached Files**  
  A section for any additional files related to the station. If no files are registered, this area will display a placeholder message ("There is no files registered").

### Edit Option

An **Edit** button is available at the top, allowing users to modify the station metadata. This feature ensures that users can keep the information up-to-date, reflecting any changes in station status or equipment.

![image](https://github.com/user-attachments/assets/5f47cbba-d309-441c-8880-32d91339fe75)

## Visits Interface

The Visits Interface provides a chronological record of field visits to a station. Each visit entry includes photos, dates, and associated campaigns, offering a visual and historical log of the station’s site maintenance and measurement activities.

### Key Features

- **Visit Entries**  
  Each visit is displayed with the following details:
  - **Visit Date**: The date the visit occurred (e.g., "2022-05-17" and "2021-12-08").
  - **Campaign**: The associated campaign or project for that visit (e.g., "La Pampa + Neuquen 2021" or "N/A" if not specified).

- **Photos**  
  Each visit entry contains photos documenting the site conditions, equipment setup, and any maintenance or changes performed during the visit. This visual record provides context to the station's state over time and aids in tracking changes in the environment or equipment.

- **Add and Delete Options**  
  - **Add Visit**: A button at the top-right allows users to add a new visit entry, enabling them to keep the visit log up-to-date with the latest field activities.
  - **Delete Visit**: Each visit entry includes a delete icon, allowing users to remove specific visits if needed.

### Usage

This interface serves as a tool for tracking the maintenance and operational history of the station, helping users document all visits systematically. The photographic evidence and timestamps for each visit help ensure consistency in monitoring and provide a resource for troubleshooting.

![image](https://github.com/user-attachments/assets/98d19c62-760e-47d1-bacc-066e16c9d1ee)

The Visits Interface helps maintain a thorough history of field activities, supporting the management and maintenance of station operations and campaign measurements.

## Add Visit Interface

The Add Visit interface allows users to log a new visit to a station. This form captures the details about the visit, including files, participants, and additional notes, making it easier to maintain a comprehensive record of station activities.

### Key Features

- **Date**  
  A field to enter the **Date** of the visit in `mm/dd/yyyy` format.

- **Log Sheet File**  
  Users can upload a **Log Sheet File** by selecting the file via the **Browse...** button. This file may contain detailed notes or records from the visit. PDF format is recommended.

- **Navigation File**  
  An option to upload a **Navigation File** (kmz or kml) describing how to get to the station. This is useful when one took a different route than the one in the metadata section.

- **Campaign**  
  A dropdown menu for selecting the **Campaign** associated with the visit, which links the visit to a specific project or set of activities (see the **Campaigns** section).

- **People**  
  A field to specify the individuals involved in the visit. This allows for better tracking of personnel assignments and responsibilities (see the **Add People** section).

- **Comments**  
  An **Optional Comments** field where users can enter any additional notes or observations related to the visit, providing further context.

- **Create Button**  
  A **Create** button at the bottom of the interface allows users to submit the form and add the new visit entry to the station's log.

### Usage

The Add Visit interface helps users document each visit systematically, ensuring that all relevant information is captured.

![image](https://github.com/user-attachments/assets/6a49864c-c398-498c-8d6c-b67b1e29409f)

## RINEX Interface

The RINEX Interface provides a detailed view of RINEX data files for a station, along with metadata and status indicators. This interface enables users to identify and manage any inconsistencies or missing information for each RINEX file, ensuring accurate and complete data for processing.

### Key Features

- **Status Icons**  
  - **Yellow Exclamation Mark (!)**: Indicates that the RINEX data contains some inconsistencies relative to the station information. This type of warning does not need to be addressed.
  - **Red Exclamation Mark (!)**: Highlights RINEX files that either lack station information or have incomplete station information coverage. This type of error needs to be addressed before processing.

- **Row Status**  
  - **Gray**: Represent RINEX files with less than 12 hours of data. These files will not be processed in GAMIT.
  - **Green**: Show RINEX files with metadata that is complete and error-free.
  - **Red**: Show RINEX files with metadata problems that need to be addressed before processing.
  - **Light red**: Show RINEX files with metadata problems that have less than 12 hours of observations and will not be processed by GAMIT.

- **Actions**  
  - **V**: Visualize the station information associated with a RINEX file.
  - **E**: Edit the station information for the RINEX file.
  - **+**: Create a new station information file based on an external station file or using RINEX metadata, helpful for resolving data gaps.
  - **↥** or **↧**: Extend the data of the previous or next available station information record to cover this RINEX file.

- **Data Columns**  
  The table provides detailed columns for each RINEX file, including:
  - **Date**: Year, month, day, and day of year (DOY) for the file.
  - **Start and End Times**: Beginning and ending timestamps for each file.
  - **RX Type/Serial/Firmware**: Information on the receiver type, serial number, and firmware.
  - **ANT Type/Serial/Dome**: Antenna type, serial number, and radome information.
  - **File Name**: Name of the RINEX file.
  - **Interval**: Sampling interval of the RINEX file.
  - **Height**: Antenna height.
  - **Completion**: Fraction indicating the file's completion, where 1 equals 24 hours of data. Values greater than 0.5 indicate more than 12 hours of data, making the file eligible for processing in GAMIT.

- **Alerts and Warnings**  
  - Any RINEX files with more than 12 hours of observations (completion > 0.5) and with missing metadata will trigger an **alert status**, displayed as a red exclamation mark on the home page map and on this interface.

### Usage

This interface is crucial for managing the integrity of RINEX data, allowing users to quickly spot issues and take corrective actions. RINEX with problems can be directly viewed by clicking on the check box on the top right.

![image](https://github.com/user-attachments/assets/89f4193b-03dd-4ce8-ab89-109c830bf9a7)

The RINEX Filter Window in the Parallel.GAMIT platform allows users to apply specific filters to refine the list of RINEX files displayed. This feature is useful for isolating files that meet certain criteria, making it easier to locate and review relevant data.

### RINEX Filters

- **Time Filters**  
  - **F Year** and **Year**: Filter files by specific fraction of year or calendar year.
  - **Observation Time**: Allows users to set a date and time range of the observation period for the RINEX files.
  - **DOY**: Filter by Day of Year, useful for quick access to data from a specific day within the year.

- **Equipment Filters**  
  - **Antenna Dome** and **Antenna Offset**: Filter files based on specific antenna dome or offset settings.
  - **Antenna Serial** and **Antenna Type**: Narrow down files by antenna serial number or model.
  - **Receiver FW** and **Receiver Serial**: Filter files according to receiver firmware version and serial number.
  - **Receiver Type**: A dropdown menu to select the receiver type used during data capture.

- **Other Filters**  
  - **Completion**: Filter files based on the completion, allowing users to focus on files with a specific amount of data completeness.
  - **Interval**: Set a sampling interval filter, useful for isolating files with specific data recording intervals.

### Actions

- **Apply Filters**  
  The **Apply Filters** button at the bottom allows users to execute the selected filters, displaying only the files that match the chosen criteria.

- **Clean Filters**  
  The **Clean Filters** button resets all fields, allowing users to start with a fresh set of filter options.


![image](https://github.com/user-attachments/assets/152bd3a2-ddb4-4aab-9ae0-afa235ee1dcc)

