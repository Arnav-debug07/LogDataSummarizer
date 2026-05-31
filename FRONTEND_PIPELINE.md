# Frontend Interaction Pipeline

This document describes the interaction pipeline and data flow of the Radar Telemetry Analyzer's frontend. The flowchart below maps out how user actions trigger client-side scripts, communicate with the Flask backend, and update the User Interface dynamically.

## User Interaction Flowchart

```text
        ┌─────────────────────────────────────────────────────────┐
        │                     USER ACCESSES UI                    │
        │                                                         │
        │         File Upload          Action Selection           │
        └────────────────────┬────────────────────┬───────────────┘
                             │                    │
                             ▼                    ▼
        ┌────────────────────────┐┌───────────────────────────────┐
        │     DATA INGESTION     ││       ACTION SELECTION        │
        │                        ││                               │
        │ 1. Select .txt/.json   ││ 1. Click Pre-defined Action   │
        │ 2. Click Upload        ││ 2. Click Interactive Summary  │
        │ 3. call uploadFile()   ││ 3. Enter Query (Interactive)  │
        └────────────┬───────────┘└────────────┬──────────────────┘
                     │                         │
                     │                         ▼
                     │            ┌───────────────────────────────┐
                     │            │       CORE EXECUTION          │
                     │            │                               │
                     │            │ 1. call doAction()            │
                     │            │ 2. Show 'Processing...' UI    │
                     │            └────────────┬──────────────────┘
                     ▼                         ▼
        ┌─────────────────────────────────────────────────────────┐
        │                      API REQUEST                        │
        │                                                         │
        │           POST /api/upload OR POST /api/action          │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │                  BACKEND PROCESSING                     │
        │               (Flask Server & RAG Engine)               │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │                  RESPONSE HANDLING                      │
        │                (Inspect JSON data.type)                 │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                       ┌────────────┴────────────┐
                       │                         │
                       ▼                         ▼
            ┌────────────────────┐    ┌────────────────────┐
            │   data.type: image │    │   data.type: text  │
            │                    │    │                    │
            │ Render <img> tag   │    │ Parse Markdown via │
            │ with URL           │    │ marked.js library  │
            └──────────┬─────────┘    └──────────┬─────────┘
                       │                         │
                       └────────────┬────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │                      UI UPDATE                          │
        │                                                         │
        │  1. Inject styled HTML into DOM (#result-content)       │
        │  2. Execute smooth scroll to results view               │
        └─────────────────────────────────────────────────────────┘
```

## Flow Description

1. **Initialization:** The user accesses the application and is presented with a file upload bar and action buttons.
2. **Data Ingestion:** 
   - The user selects a file and uploads it. 
   - The `uploadFile()` function in `script.js` handles reading the file using `FormData` and sends it to the `/api/upload` endpoint.
   - The frontend updates the status message based on whether the ingestion was successful or failed.
3. **Execution Requests:** 
   - Users can either click a direct action (Brief Summary, Deep Analysis, Graphical Summary, Error Codes) or open the Interactive Summary input.
   - For Interactive requests, `runInteractive()` gathers the text input and passes it along.
   - All actions are ultimately routed to `doAction(action, query)`.
4. **Processing State:** 
   - `doAction()` reveals the hidden results section and injects a "Processing..." message while scrolling the user down.
   - A POST request containing the `action` and `query` parameters is dispatched to `/api/action`.
5. **Rendering Results:** 
   - When the backend responds, the frontend inspects `data.type`. 
   - If it's an **image** (e.g., from Graphical Summary), it dynamically constructs an image tag. 
   - If it's **text**, it leverages the `marked.js` library to parse Markdown content into styled HTML components.
   - The UI is then smoothly scrolled to ensure the newly injected content is perfectly framed within the viewport.
