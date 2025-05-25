# 🌍 WanderVerse – Your AI-Powered Travel Companion

**WanderVerse** is an intelligent travel itinerary generator that transforms the way you plan your trips. With just a few clicks, users can select their destination, travel dates, and preferences—and our platform takes care of the rest. Powered by AI and a rich stack of APIs, WanderVerse creates fully personalized day-by-day itineraries including places to visit, local experiences, transportation suggestions, and more.

The platform is built using **Django** for the backend, **Firebase** for user authentication and cloud data storage, and integrates with powerful tools like **Gemini API**, **Amadeus**, **GeoDB**, and **Geoapify** to deliver comprehensive travel planning assistance.

Whether you're a backpacker on a budget, a family looking for comfort, or an explorer seeking hidden gems—WanderVerse 2.0 adapts to your style and helps you plan with ease. You can create, view, and modify your trips anytime with a beautifully designed and responsive interface.

---

### 🔑 Key Features
- User-friendly trip creation with custom dates and cities  
- AI-generated itineraries tailored to preferences (budget, travel style, interests)  
- Daily plans mapped to real calendar dates  
- Firebase-authenticated login and secure itinerary storage  
- Real-time itinerary viewing and trip management  

---

### 🔧 Tech Stack
- **Backend**: Django (Python)  
- **Frontend**: HTML, CSS (Tailwind/Bootstrap), JavaScript  
- **Authentication & DB**: Firebase Authentication & Firestore  
- **APIs**: Gemini, GeoDB, Geoapify, Amadeus  

---

### 🚀 Setup Instructions

To run WanderVerse locally, follow these steps:

#### 1. Install Docker & Docker Compose
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop) (includes Docker Compose).
- Verify installation with:
  ```bash
  docker --version
  docker compose version
  ```
#### 2. Clone the Repository
  ```bash
  git clone https://github.com/CodePokeX/WanderVerse.git
  cd WanderVerse/
  ```
#### 3. Configure Environment Variables
- Copy the example environment file:
  ```bash
  cp .env.example .env
  ```
- Open .env and fill in all necessary environment variables, including:
  - Firebase credentials
  - API keys (Gemini, Amadeus, GeoDB, Geoapify)
  - Django secret key and any other config variables
#### 4. Run the App with Docker
  ```bash
  docker compose up --build
  ```
#### 5. Access the App
    Once the containers are up and running, open your browser and go to: http://localhost:8000





