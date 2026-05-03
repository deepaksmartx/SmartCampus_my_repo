# SmartCampus Frontend

A React-based frontend for the SmartCampus IoT Management System.

## Project Structure

```
frontend/
├── src/
│   ├── pages/           # Page components (Registration, Login, Home, etc.)
│   ├── styles/          # CSS files for pages
│   ├── App.js           # Main app component with routing
│   ├── App.css          # Global styles
│   └── index.js         # Entry point
├── public/
│   ├── index.html       # Main HTML file
│   ├── favicon.ico      # App icon
│   └── manifest.json    # PWA manifest
├── package.json         # Dependencies and scripts
└── README.md            # This file
```

## Getting Started

### Prerequisites
- Node.js (v14 or higher)
- npm (v6 or higher)

### Installation

1. Install dependencies:
```bash
npm install
```

## Available Scripts

### `npm start`
Runs the app in development mode at [http://localhost:3000](http://localhost:3000)

### `npm run build`
Builds the app for production to the `build/` folder

### `npm test`
Runs tests in interactive watch mode

## Current Features

- **Registration Page**: User sign-up with form validation
- **Login Page**: User authentication
- **Home Page**: Landing page with navigation

## Environment Variables

Create a `.env` file in the root directory:
```
REACT_APP_API_URL=http://localhost:8000
# Production (e.g. Render static site): set to your API origin, no trailing slash
# REACT_APP_API_URL=https://your-api.onrender.com
```

## Dependencies

- React 18
- React Router DOM - For navigation between pages
- React Scripts - Build and test utilities

## Notes for Teammates

- All page components are in the `src/pages/` folder
- Styling is separated in the `src/styles/` folder
- The backend API is running on `http://localhost:8000`
- The app uses JWT tokens stored in localStorage for authentication

## Backend API

The frontend connects to the SmartCampus backend API. Make sure the backend is running on `http://localhost:8000` before starting the frontend.

- **Registration**: `POST /users/register`
- **Login**: `POST /login`
- **User Profile**: `GET /users/profile` (requires token)


### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
