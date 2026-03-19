📘 Frontend Documentation – AI Document Processing Platform
🧩 1. Overview

This frontend application is part of a document processing platform developed during a hackathon.
It allows users to upload administrative documents, visualize extracted data, and detect inconsistencies across documents.

The application is built using React.js and communicates with a FastAPI backend.

🎯 2. Objectives

The frontend provides:

📤 Multi-document upload interface

📊 Dashboard for processed documents

🔎 Visualization of extracted data (SIREN, SIRET, amounts)

⚠️ Detection and display of inconsistencies

🏢 Supplier CRM interface

🏗️ 3. Project Structure
frontend/
│
├── public/               # Static files
├── src/
│   ├── components/      # Reusable UI components
│   ├── pages/           # Application pages
│   ├── services/        # API calls
│   ├── hooks/           # Custom React hooks
│   ├── utils/           # Utility functions
│   ├── styles/          # Styling (CSS / Tailwind)
│   └── App.js           # Main app & routing
│
├── docs.md              # Documentation
├── Dockerfile           # Container configuration
└── package.json         # Dependencies

🖥️ 4. Features
📤 4.1 Document Upload

Upload multiple files (PDF, images)

Send files to backend API

Display upload status

Handle errors

📊 4.2 Dashboard

Displays key metrics:

Total documents

Validated documents

Inconsistent documents

Total extracted amount

📋 4.3 Documents Table

Each document includes:

| Field  | Description                |
| ------ | -------------------------- |
| Name   | File name                  |
| Type   | Invoice, Certificate, etc. |
| SIREN  | Extracted company ID       |
| SIRET  | Extracted establishment ID |
| Amount | Extracted value            |
| Status | Validated / Inconsistent   |

⚠️ 4.4 Inconsistency Detection

The frontend displays inconsistencies detected by the backend:

SIRET mismatch

Amount mismatch

Missing fields

Visual indicators:

🟢 Validated

🔴 Inconsistent

🔍 4.5 Document Details (if implemented)

Detailed extracted fields

Comparison between documents

Highlighted inconsistencies

🏢 4.6 Supplier CRM

List of suppliers

Linked documents

Compliance status

🔌 5. API Integration
🌐 Base URL

The frontend connects to the backend using:
REACT_APP_API_BASE_URL=http://localhost:8000

📡 Main Endpoints

| Method | Endpoint          | Description          |
| ------ | ----------------- | -------------------- |
| GET    | `/health`         | Check API status     |
| POST   | `/upload`         | Upload documents     |
| GET    | `/documents`      | Retrieve documents   |
| GET    | `/documents/{id}` | Get document details |

⚙️ Example API Call 

const response = await fetch(
  `${process.env.REACT_APP_API_BASE_URL}/documents`
);
const data = await response.json();

🔄 6. Data Flow

User → Frontend → Backend (FastAPI)
       ↓
   Upload file
       ↓
   Backend processing (OCR, validation)
       ↓
   Database (MongoDB / Data Lake)
       ↓
   Response → Frontend UI

   🧠 7. State Management

The application uses:

React hooks (useState, useEffect)

Local component state

API-driven data rendering

🎨 8. UI / UX Design

The UI is designed for:

clarity of data

quick anomaly detection

smooth user experience

Components used:

Cards (statistics)

Tables (documents)

Badges (status)

Alerts (errors / API)

🛠️ 9. Technologies

React.js

JavaScript (ES6+)

CSS / Tailwind (if used)

Fetch API / Axios

🚀 10. Running the Project

▶️ Install dependencies

npm install

▶️ Start the app

npm start

🌐 Access

http://localhost:3000

🔐 11. Environment Variables

Create a .env file in the frontend root:

REACT_APP_API_BASE_URL=http://localhost:8000

⚠️ 12. Error Handling

API connection errors are displayed to the user

Fallback states are handled in UI

Loading states are implemented

📈 13. Future Improvements

Drag & Drop upload

File preview

Advanced filtering

Charts & analytics

Authentication (JWT)

Real-time updates

👨‍💻 14. Role in the Team

Frontend Developer responsibilities:

UI/UX implementation

API integration

Data visualization

Interaction design

🏁 15. Conclusion

The frontend plays a critical role by:

providing user interaction

visualizing processed data

highlighting inconsistencies

It is designed to be scalable, modular, and easily extensible.