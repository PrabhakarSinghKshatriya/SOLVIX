🚀 SOLVIX – Hyperlocal Service Marketplace

Connect. Solve. Get It Done.

SOLVIX is a hyperlocal service marketplace designed to connect customers with skilled professionals in their nearby locations. Whether someone needs a plumber, electrician, mechanic, carpenter, tutor, photographer, or any other professional, SOLVIX makes finding and connecting with the right person simple and convenient.

SOLVIX bridges the gap between people who need services and professionals who provide them through location-based matching, real-time request management, verified worker profiles, and a subscription-based business model.

🌐 Live Website: https://solvix-rho.vercel.app/

⚙️ Backend API: https://solvix-api-9p2r.onrender.com/

📂 GitHub Repository: https://github.com/PrabhakarSinghKshatriya/SOLVIX

⸻

✨ Key Features

👤 1. Customer Features

* User registration and secure login.
* Find nearby service professionals.
* Post service requests based on specific requirements.
* Location-based professional matching.
* View worker profiles, skills, experience, and ratings.
* Track service request status.
* Access assigned worker contact details.
* View service progress.
* Cancel requests when applicable.

🛠️ 2. Professional / Worker Features

* Worker registration and profile management.
* Add profession, skills, experience, and bio.
* Set service location and availability.
* Receive nearby customer service requests.
* Accept or reject service requests.
* Update job status throughout the service process.
* View completed work and profile information.
* Subscription-based access to service opportunities.

📍 3. Location-Based Matching

SOLVIX uses location-based matching to connect customers with relevant professionals.

* Detect current location.
* Manual location support.
* Geospatial worker search using MongoDB 2dsphere indexes.
* Adjustable search radius.
* Match professionals according to skills and availability.
* Consider worker ratings and experience.

🔐 4. Aadhaar Verification System

To improve platform trust and professional accountability:

* Workers can upload Aadhaar documents.
* Support for document uploads.
* Admin reviews submitted documents.
* Admin can approve worker verification.
* Verified professionals receive a verification status.
* Service acceptance is restricted until required verification is completed after subscription payment.

💳 5. Subscription & Payment System

SOLVIX follows a subscription-based monetization model for professionals.

* Five free service opportunities for eligible workers.
* Monthly subscription: ₹150.
* Yearly subscription: ₹1,500.
* Razorpay payment integration.
* Payment verification and subscription management.
* Subscription status tracking.
* Aadhaar verification requirement after successful subscription payment.

🛡️ 6. Admin Dashboard

A dedicated administrative dashboard provides platform management capabilities.

* Admin-only dashboard access.
* View total registered users.
* Manage customer and worker information.
* View worker profiles and professional details.
* Monitor completed jobs.
* Review Aadhaar verification requests.
* Manage worker verification status.
* Monitor subscriptions and payments.
* View platform statistics.
* Manage platform notifications.

🔔 7. Notifications & Request Management

* Service request notifications.
* Request acceptance and rejection.
* Booking status updates.
* Request lifecycle management.
* Real-time communication support through WebSockets.

⭐ 8. Worker Reputation

Worker profiles support professional credibility through ratings, experience, and completed-work information.

⸻

🔄 How SOLVIX Works

       CUSTOMER NEED
             |
             ▼
       POST A REQUEST
             |
             ▼
       SELECT LOCATION
             |
             ▼
       SKILL-BASED MATCHING
             |
             ▼
       FIND NEARBY WORKERS
             |
             ▼
       CONNECT WITH WORKER
             |
             ▼
       REQUEST ACCEPTANCE
             |
             ▼
       BOOKING CONFIRMATION
             |
             ▼
       SERVICE IN PROGRESS
             |
             ▼
       SERVICE COMPLETED
             |
             ▼
       REVIEW & RATING

⸻

🧰 Technology Stack

Frontend

* React.js
* Vite
* JavaScript
* HTML5
* CSS3
* Axios
* React Router
* Google OAuth

Backend

* Python 3.11
* FastAPI
* REST APIs
* WebSockets
* Pydantic

Database

* MongoDB
* MongoDB Geospatial Indexing (2dsphere)

Authentication & Security

* JWT-based authentication
* OTP-based authentication
* Google OAuth
* Role-based access control
* Admin authorization
* Aadhaar document verification

Payment Integration

* Razorpay

Deployment & Development

* Git & GitHub
* Docker
* Docker Compose
* Vercel (Frontend)
* Render (Backend)

⸻

🏗️ Project Architecture

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

Note: Directory structure is representative of the project’s architecture.

⸻

⚙️ Installation & Setup

Prerequisites

Make sure you have installed:

* Python 3.11+
* Node.js 20+
* npm
* MongoDB
* Git
* Docker (optional)

1. Clone Repository

git clone https://github.com/PrabhakarSinghKshatriya/SOLVIX.git
cd SOLVIX

2. Backend Setup

cd backend
python -m venv venv

Activate virtual environment:

macOS / Linux

source venv/bin/activate

Windows

venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Configure the required backend environment variables using your deployment configuration.

Start backend:

uvicorn app.main:app --reload

Backend runs at:

http://localhost:8000

API Documentation:

http://localhost:8000/docs

3. Frontend Setup

Open another terminal:

cd SOLVIX/frontend

Install dependencies:

npm install

Start development server:

npm run dev

Build production version:

npm run build

4. Docker Setup

From the project root:

docker compose up --build

To stop containers:

docker compose down

⸻

🌍 Deployment

SOLVIX uses cloud-based deployment:

Component	Platform
Frontend	Vercel
Backend	Render
Database	MongoDB
Source Code	GitHub

Live Application:

https://solvix-rho.vercel.app/

Backend API:

https://solvix-api-9p2r.onrender.com/

⸻

🎯 Project Objectives

SOLVIX aims to:

* Make local services easily accessible.
* Help skilled professionals discover work opportunities.
* Reduce the time required to find reliable service providers.
* Promote digital opportunities for local workers.
* Build a location-aware service ecosystem.
* Establish a scalable marketplace connecting customers and professionals.

⸻

🚀 Future Scope

Potential future enhancements include:

* Advanced AI-based professional recommendations.
* Enhanced real-time tracking.
* Integrated in-app chat.
* Advanced analytics and business intelligence.
* Automated worker performance insights.
* Expanded payment and payout capabilities.
* Improved customer feedback and reputation management.
* Expansion into multiple cities and regions.

⸻

👨‍💻 Developer

Prabhakar Singh Kshatriya

Full Stack Developer | Python | React.js | FastAPI | MongoDB

GitHub: https://github.com/PrabhakarSinghKshatriya

⸻

📜 License

This project is currently maintained as an independent development project.

For permissions regarding reuse, modification, or commercial distribution, please contact the developer.

⸻

<p align="center">
  <b>SOLVIX – Connect. Solve. Get It Done.</b>
  <br/>
  Making local services smarter, faster, and more accessible.
</p>
