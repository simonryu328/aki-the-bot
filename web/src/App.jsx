import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import WebApp from '@twa-dev/sdk';
import Layout from './components/Layout';
import MemoriesPage from './pages/MemoriesPage';
import CalendarPage from './pages/CalendarPage';

function App() {
    useEffect(() => {
        // Initialize Telegram WebApp
        if (window.Telegram?.WebApp) {
            WebApp.ready();
            WebApp.expand();
            document.documentElement.className = WebApp.colorScheme;
        }
    }, []);

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Layout />}>
                    <Route index element={<MemoriesPage />} />
                    <Route path="calendar" element={<CalendarPage />} />
                </Route>
            </Routes>
        </BrowserRouter>
    );
}

export default App;
