# Frontend Architecture - Radar Telemetry Analyzer

## Overview
The frontend of the Radar Telemetry Analyzer is a lightweight, responsive, and interactive single-page application (SPA) designed to upload, analyze, and visualize radar log data. It relies on vanilla web technologies (HTML5, CSS3, JavaScript) and communicates with a Python Flask backend via RESTful APIs.

## Technology Stack
- **HTML5**: Defines the semantic structure of the application.
- **CSS3 (Vanilla)**: Provides styling, layout, and a premium modern design.
- **JavaScript (Vanilla)**: Handles user interactions, asynchronous file uploading, and API communication.
- **Marked.js**: A third-party CDN library used for parsing Markdown responses from the backend into rich HTML.

## Directory Structure
```text
LogDataSummarizer/
├── app.py                  # Flask Backend serving frontend assets and APIs
├── templates/
│   └── index.html          # Main HTML structure
└── static/
    ├── style.css           # Styling rules and design system
    ├── script.js           # Client-side logic and API integrations
    ├── drdo_logo.png       # Logo asset
    ├── plane_bg.png        # Background image asset
    └── aircraft_bg.png     # Alternative background asset
```

## Component Details

### 1. Structure (`templates/index.html`)
The user interface is divided into semantic HTML5 components:
- **`<header>`**: Displays the application title and branding.
- **Upload Bar (`.upload-bar`)**: A dedicated section for uploading log files (`.txt` or `.json`). It contains a hidden file input styled with custom buttons and an upload status indicator.
- **`<main>` Content Area**:
  - **Action Buttons (`.button-grid`)**: Provides quick actions to run different analyses (Brief Summary, Interactive Summary, Deep Analysis, Graphical Summary).
  - **Interactive Container (`.interactive-container`)**: A search bar for submitting natural language queries, toggled by the "Interactive Summary" button.
  - **Results Section (`.result-section`)**: Displays the parsed output from the backend. It dynamically updates based on the action executed and handles both text (markdown) responses and image rendering.

### 2. Styling (`static/style.css`)
The application employs a custom design system focusing on a premium aesthetic:
- **Design Tokens**: Uses CSS variables (e.g., `--primary-blue`, `--bg-overlay`) for consistent color theming and maintainability.
- **Backgrounds & Overlays**: Utilizes a dynamic background image (`plane_bg.png`) combined with semi-transparent overlays (`rgba`) to ensure text readability while maintaining an immersive visual appeal.
- **Typography**: Uses the 'Noto Sans' Google Font for a clean, modern, and readable look.
- **Layouts**: Extensively uses Flexbox and CSS Grid to manage component positioning, alignment, and responsiveness.
- **Micro-interactions**: Incorporates hover effects, transitions, and subtle scaling (e.g., `.btn-action:hover { transform: scale(1.05); }`) for better user engagement.

### 3. Logic & API Integration (`static/script.js`)
The client-side logic manages asynchronous communication with the backend without reloading the page:
- **File Uploading (`uploadFile`)**: Reads the selected file using `FormData` and sends a POST request to `/api/upload`. It provides real-time UI feedback (Processing, Success, Error).
- **Action Execution (`runAction`, `doAction`)**: Sends POST requests to `/api/action` with specific action commands. 
- **Interactive Queries (`runInteractive`)**: Handles custom user inputs and routes them to the interactive summary API.
- **Dynamic Content Rendering**: 
  - Handles JSON responses from the backend.
  - Renders image tags if the response type is `image`.
  - Uses `marked.parse()` to render Markdown responses into structured HTML elements when the response type is `text`.
  - Automatically scrolls the view to the results section for better UX.

## Data Flow
1. **User Interaction**: The user selects a file or clicks an action button on the interface.
2. **Client-Side Request**: `script.js` captures the event, prepares the JSON payload or FormData, and sends an asynchronous `fetch` POST request to the Flask server (`/api/upload` or `/api/action`).
3. **Backend Processing**: `app.py` routes the request, interacts with the RAG engine or logs processing modules, and returns a structured JSON response.
4. **Client-Side Update**: `script.js` processes the JSON response, dynamically updates the DOM elements (status messages, results area), and applies Marked.js for formatting if the content contains markdown.
