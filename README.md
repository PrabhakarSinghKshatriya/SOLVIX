<div align="center">

🚀 SOLVIX

CONNECT. SOLVE. GET IT DONE.

Your Local Needs. The Right Professionals. One Platform.

A smart hyperlocal service marketplace connecting customers with skilled professionals through location-based discovery, intelligent matching, and seamless service management.

<br/>
<br/>
</div>

⸻

🌟 About SOLVIX

SOLVIX is a modern, location-aware service marketplace built to simplify how people discover and connect with local service professionals.

Finding a reliable electrician, plumber, mechanic, carpenter, tutor, photographer, or other skilled professional should not be complicated.

SOLVIX brings customers and professionals together through a unified digital platform where customers can post service requirements and nearby professionals can discover, accept, and complete those requests.

The platform combines location-based matching, professional profiles, request lifecycle management, secure authentication, subscription-based monetization, and administrative verification.

💡 Our Vision

To create a smarter local service ecosystem where every customer can find the right professional and every skilled individual can discover meaningful work opportunities.

⸻

⚡ Why SOLVIX?

Traditional Service Discovery	SOLVIX
Difficult to find nearby professionals	Location-based professional discovery
Limited information about workers	Detailed professional profiles
Unorganized service requests	Structured request management
Difficult to track service progress	Multiple service status updates
Limited professional verification	Aadhaar verification workflow
No centralized management	Dedicated admin dashboard

⸻

✨ Core Features

👥 Customer Experience

* Secure registration and authentication.
* Post service requests with specific requirements.
* Discover nearby professionals.
* Search according to profession and location.
* View worker skills, experience, ratings, and profiles.
* Track request and service progress.
* Access assigned professional contact details.
* Manage service requests.

🧑‍🔧 Professional Dashboard

* Dedicated worker registration and login.
* Professional profile creation and management.
* Add skills, profession, experience, and bio.
* Configure location and availability.
* Receive nearby service requests.
* Accept or reject incoming requests.
* Update service progress.
* Track completed work.
* Manage subscription status.

📍 Smart Location-Based Matching

SOLVIX uses geospatial capabilities to improve local professional discovery.

* Current location detection.
* Manual location selection.
* MongoDB 2dsphere geospatial indexing.
* Configurable search radius.
* Skill-based professional matching.
* Availability-based filtering.
* Rating and experience information.

🛡️ Aadhaar Verification

A dedicated verification workflow helps establish professional accountability.

* Aadhaar document upload.
* Document submission for admin review.
* Admin-controlled verification.
* Verification status management.
* Verified professional identification.
* Service acceptance restrictions until required verification is completed.

💳 Subscription & Payments

A monetization system designed for service professionals.

Subscription	Price
Free Opportunities	5
Monthly Plan	₹150
Yearly Plan	₹1,500

Payment Features:

* Razorpay integration.
* Payment verification.
* Subscription activation.
* Payment status tracking.
* Subscription management.
* Post-payment verification workflow.

🔔 Notifications & Real-Time Updates

* Service request notifications.
* Request acceptance and rejection updates.
* Booking status changes.
* Real-time communication support.
* WebSocket-based functionality.

🛠️ Admin Control Center

A dedicated admin-only dashboard for managing the marketplace.

* Total registered user statistics.
* Customer and worker directories.
* Worker profile inspection.
* Completed work monitoring.
* Aadhaar document verification.
* Worker verification management.
* Subscription and payment monitoring.
* Administrative notifications.
* Platform statistics.

⸻

🔄 How SOLVIX Works

<div align="center">
flowchart TD
    A["👤 Customer"] --> B["📝 Post Service Request"]
    B --> C["📍 Select Location"]
    C --> D["🎯 Skill & Location Matching"]
    D --> E["🧑‍🔧 Find Nearby Professionals"]
    E --> F["📨 Send Service Request"]
    F --> G["✅ Worker Accepts Request"]
    G --> H["📅 Booking Confirmation"]
    H --> I["🚗 Service In Progress"]
    I --> J["🎉 Work Completed"]
    J --> K["⭐ Customer Feedback"]
</div>

⸻

🧰 Technology Stack

<div align="center">

Frontend

Backend

Database & Infrastructure

Integrations & Deployment

</div>

⸻

🏗️ System Architecture

                    SOLVIX PLATFORM
                           |
             +-------------+-------------+
             |             |             |
          CUSTOMER       WORKER         ADMIN
             |             |             |
             +-------------+-------------+
                           |
                    REACT FRONTEND
                           |
                      AXIOS / API
                           |
                    FASTAPI BACKEND
                           |
       +-------------------+-------------------+
       |           |           |               |
      AUTH       WORKERS     REQUESTS       ADMIN
       |           |           |               |
       +-----------+-----------+---------------+
                           |
                     MONGODB DATABASE
                           |
       +-------------------+-------------------+
       |                   |                   |
   GEOLOCATION         PAYMENTS            NOTIFICATIONS
       |                   |                   |
   2dsphere             RAZORPAY            WEBSOCKET

⸻

📂 Project Structure

SOLVIX/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth/
│   │   │   ├── workers/
│   │   │   ├── requests/
│   │   │   ├── subscriptions/
│   │   │   ├── notifications/
│   │   │   ├── admin/
│   │   │   ├── stats/
│   │   │   └── aadhaar/
│   │   │
│   │   ├── core/
│   │   ├── models/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── assets/
│   │   └── App.jsx
│   │
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── docker-compose.yml
└── README.md

Note: This is a representative architecture; actual folders may differ.

⸻

⚙️ Getting Started

Prerequisites

Make sure you have installed:

* Python 3.11+
* Node.js 20+
* npm
* MongoDB
* Git
* Docker (optional)

1. Clone the Repository

git clone https://github.com/PrabhakarSinghKshatriya/SOLVIX.git
cd SOLVIX

2. Backend Installation

cd backend
python -m venv venv

Activate the environment:

macOS / Linux

source venv/bin/activate

Windows

venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Configure the required environment variables for MongoDB, authentication, payment integration, and frontend connectivity.

Run the backend:

uvicorn app.main:app --reload

Backend:

http://localhost:8000

Interactive API Documentation:

http://localhost:8000/docs

3. Frontend Installation

Open another terminal:

cd frontend
npm install

Start development server:

npm run dev

Production build:

npm run build

4. Run with Docker

From the project root:

docker compose up --build

Stop containers:

docker compose down

⸻

☁️ Deployment

SOLVIX is deployed using cloud infrastructure.

Service	Platform
Frontend Hosting	Vercel
Backend Hosting	Render
Database	MongoDB
Version Control	GitHub

<div align="center">

🌐 Explore SOLVIX

</div>

⸻

🔒 Security & Reliability

SOLVIX incorporates several important platform-level safeguards:

* Role-based access control.
* Protected administrative functionality.
* Authentication and authorization.
* Payment verification workflows.
* Worker document verification.
* Database indexing for efficient queries.
* Structured API architecture.
* Backend test coverage.

⸻

🚀 Future Roadmap

SOLVIX is designed with future expansion in mind.

Potential improvements include:

* 🤖 AI-powered professional recommendations.
* 💬 Integrated customer-worker chat.
* 📍 Advanced live service tracking.
* ⭐ Enhanced ratings and review analytics.
* 📊 Advanced business intelligence dashboard.
* 💰 Professional payout management.
* 🌍 Expansion into additional cities.
* 📱 Dedicated Android and iOS applications.

⸻

👨‍💻 About the Developer

<div align="center">

Prabhakar Singh Kshatriya

Full Stack Developer | Python | React | FastAPI | MongoDB

Building practical technology solutions with a focus on real-world problems, scalable architecture, and user experience.

</div>

⸻

<div align="center">

💙 SOLVIX

Connect. Solve. Get It Done.

Empowering Local Professionals. Simplifying Everyday Services.

<br/>

⭐ If you find this project interesting, consider giving the repository a star!

Built with passion by Prabhakar Singh Kshatriya.

</div>
