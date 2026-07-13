/**
 * SkyCore - Login Page
 * JWT Authentication
 */

import React, { useState } from 'react';

interface LoginProps {
  onLogin: (username: string, token: string) => void;
}

const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulate authentication
    await new Promise(resolve => setTimeout(resolve, 500));

    const validUsers: Record<string, string> = {
      'admin': 'admin123',
      'operator': 'operator123',
      'viewer': 'viewer123',
      'demo': 'demo'
    };

    if (validUsers[username] && validUsers[username] === password) {
      // Create mock token
      const token = btoa(JSON.stringify({ username, exp: Date.now() + 86400000 }));
      onLogin(username, token);
    } else {
      setError('שם משתמש או סיסמה שגויים');
    }

    setLoading(false);
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>SkyCore</h1>
          <p>Ground Control Station</p>
        </div>
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label>שם משתמש</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="הזן שם משתמש"
              required
            />
          </div>
          
          <div className="form-group">
            <label>סיסמה</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="הזן סיסמה"
              required
            />
          </div>
          
          {error && <div className="error-message">{error}</div>}
          
          <button type="submit" className="login-button" disabled={loading}>
            {loading ? '...טוען' : 'התחבר'}
          </button>
        </form>
        
        <div className="demo-accounts">
          <p>חשבונות לדוגמה:</p>
          <ul>
            <li><strong>admin</strong> / admin123</li>
            <li><strong>operator</strong> / operator123</li>
            <li><strong>demo</strong> / demo</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Login;