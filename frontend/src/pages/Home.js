import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../styles/Home.css';

const Home = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate]);

  return (
    <div className="home-container">
      <div className="home-bg-decoration">
        {/* Building Silhouette - Blue */}
        <svg className="building-silhouette" viewBox="0 0 400 300" preserveAspectRatio="xMidYMax meet">
          <path d="M50,300 L50,150 L100,150 L100,100 L150,100 L150,50 L250,50 L250,100 L300,100 L300,150 L350,150 L350,300 Z" />
          <rect x="170" y="70" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="210" y="70" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="120" y="120" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="170" y="120" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="210" y="120" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="260" y="120" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="70" y="170" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="120" y="170" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="170" y="170" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="210" y="170" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="260" y="170" width="20" height="20" fill="white" opacity="0.4" />
          <rect x="310" y="170" width="20" height="20" fill="white" opacity="0.4" />
        </svg>

        {/* Campus Foliage - Green */}
        <svg className="campus-foliage" viewBox="0 0 600 200" preserveAspectRatio="xMinYMax meet">
          <path d="M0,200 C150,150 250,180 400,120 C500,80 550,120 600,200 Z" />
          <circle cx="100" cy="160" r="40" />
          <circle cx="160" cy="140" r="50" />
          <circle cx="240" cy="155" r="45" />
          <circle cx="340" cy="130" r="60" />
          <circle cx="450" cy="150" r="50" />
        </svg>
      </div>

      <div className="home-content">
        <h1>Welcome to <span style={{color: 'var(--primary)'}}>SmartCampus</span></h1>
        <p>Your Intelligent Hub for Campus Life & Automation</p>

        <div className="button-group">
          <Link to="/login" className="btn btn-primary">
            Login
          </Link>
          <Link to="/register" className="btn btn-secondary">
            Get Started
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Home;
