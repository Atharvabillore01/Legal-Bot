import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useAuthStore from '@/store/authStore';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-blue-600 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/dashboard" className="flex items-center gap-2 text-2xl font-bold">
            <span>⚖️</span>
            <span>LegalBot</span>
          </Link>

          <nav className="hidden md:flex gap-8">
            <Link to="/dashboard" className="hover:text-blue-100 transition-colors">
              Dashboard
            </Link>
            <Link to="/query" className="hover:text-blue-100 transition-colors">
              Query Documents
            </Link>
            <Link to="/audit-log" className="hover:text-blue-100 transition-colors">
              Audit Log
            </Link>
          </nav>

          <div className="flex items-center gap-4">
            <span className="hidden sm:inline text-blue-100">{user?.email}</span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-500 rounded hover:bg-red-600 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 py-8">
          {children}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300 py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p>LegalBot © 2024 - AI-Powered Legal Document Review</p>
          <p className="text-sm text-gray-500 mt-2">
            Always consult with qualified legal counsel for legal advice.
          </p>
        </div>
      </footer>
    </div>
  );
};
