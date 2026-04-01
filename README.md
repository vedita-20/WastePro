# ♻️ WastePro: Smart Urban Waste Management System
WastePro is a **Full-Stack Web Application** designed to modernize city-wide waste collection, fleet logistics, and citizen engagement. Built with a high-performance Python/Flask backend and an interactive data-driven frontend, it provides specialized interfaces for both City Administrators (**Eco-Architects**) and Citizens (**Elite Recyclers**).
## 🚀 Key Features
### 🏛️ For Administrators (Eco-Architects)
* **Operational Analytics:** Real-time visualization of weekly waste trends and system efficiency using **Chart.js**.
* **Fleet Management:** Comprehensive CRUD (Create, Read, Update, Delete) system for tracking vehicle capacity, driver assignments, and maintenance status.
* **Filtered KPIs:** Dynamic dashboard that intelligently counts only "Active" vehicles, excluding those in maintenance or retired.
* **Secure Authorization:** Protected Admin signup requiring a unique system-level Authorization Key.
### 👤 For Citizens (Elite Recyclers)
* **Incident Reporting:** Streamlined form for reporting waste overflow or missed pickups.
* **Interactive Dashboard:** Personal impact tracking and real-time status updates on submitted complaints.
* **Security First:** Integrated account recovery using encrypted 4-digit PINs and session-based authentication.
## 🛠️ Technical Stack
* **Backend:** Python 3.x, Flask (Server-side logic, Session handling, RESTful routing)
* **Frontend:** HTML5, CSS3 (Advanced Flexbox/Grid), JavaScript (ES6+), Jinja2 Templating
* **Database:** MySQL / MariaDB (Relational schema, Data aggregation, Complex Joins)
* **Visualization:** Chart.js (Line & Doughnut implementations)
* **Design:** Modern Dark-Mode UI with Split-Screen Authentication layouts
## 📂 Database Architecture
The system utilizes a relational model to ensure data integrity and real-time synchronization:
* `Users`: Manages role-based access control (RBAC) for Admins and Citizens.
* `Collection_Vehicle`: Tracks fleet logistics, including unique plate IDs and operational health.
* `Collection_Record`: Logs daily weight data used for trend forecasting.
* `Complaint`: Facilitates the lifecycle of citizen feedback from 'Pending' to 'Resolved'.
## ⚙️ Installation & Local Setup
1. **Clone the repository** ```bash
   git clone [https://github.com/](https://github.com/)[vedita-20]/WastePro.git
   cd WastePro
   ```bash
   git clone [https://github.com/](https://github.com/)[YOUR_GITHUB_USERNAME]/WastePro.git
   cd WastePro
