import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './App.css';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ResultsPage from './pages/ResultsPage';
import SupplierCRMPage from './pages/SupplierCRMPage';
import UploadPage from './pages/UploadPage';
import { isAuthenticated } from './services/auth';

function App() {
  const authenticated = isAuthenticated();

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={authenticated ? <Navigate to="/upload" replace /> : <LoginPage />}
        />
        <Route
          path="/register"
          element={authenticated ? <Navigate to="/upload" replace /> : <RegisterPage />}
        />

        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/dashboard" element={<ResultsPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/suppliers" element={<SupplierCRMPage />} />
          <Route path="/crm" element={<SupplierCRMPage />} />
        </Route>

        <Route path="*" element={<Navigate to={authenticated ? '/upload' : '/login'} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;