import React, { useState, useEffect } from 'react';
import { App as KonstaApp, Page, Navbar, Block, BlockTitle, List, Card, Preloader, Link } from 'konsta/react';
import axios from 'axios';
import DiaryLog from './components/DiaryLog';

// WebApp SDK
import WebApp from '@twa-dev/sdk';

function App() {
    const [memories, setMemories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        // Initialize Telegram WebApp
        if (window.Telegram?.WebApp) {
            WebApp.ready();
            WebApp.expand();
            // Set theme params if needed
            document.documentElement.className = WebApp.colorScheme;
        }
    }, []);

    useEffect(() => {
        const fetchMemories = async () => {
            try {
                // In real app, get user_id from WebApp.initDataUnsafe.user.id
                // For dev/personal bot, we might hardcode or pass via URL query param
                // For now, let's fetch for a default user or from query param
                const urlParams = new URLSearchParams(window.location.search);
                const userId = urlParams.get('user_id') || WebApp.initDataUnsafe?.user?.id;

                if (!userId) {
                    throw new Error("User ID not found. Please open from Telegram.");
                }

                const response = await axios.get(`/api/memories/${userId}`);
                setMemories(response.data);
            } catch (err) {
                console.error(err);
                setError("Failed to load memories from space.");
            } finally {
                setLoading(false);
            }
        };

        fetchMemories();
    }, []);

    return (
        <KonstaApp theme="ios" dark={true}>
            <Page>
                <Navbar
                    title="Log Entries"
                    subtitle="Mission Log"
                    className="top-0 sticky"
                    bgClassName="bg-space-dark/80 backdrop-blur-md"
                />

                <div className="space-y-4 pb-10">
                    {loading && (
                        <Block className="text-center mt-10">
                            <Preloader size="w-8 h-8" />
                            <div className="mt-2 text-gray-400">Receiving transmission...</div>
                        </Block>
                    )}

                    {error && (
                        <Block className="text-center mt-10 text-red-400">
                            <p>{error}</p>
                            <p className="text-sm mt-2 text-gray-500">Signal lost.</p>
                        </Block>
                    )}

                    {!loading && !error && memories.length === 0 && (
                        <Block className="text-center mt-10 text-gray-400">
                            <p>No log entries found.</p>
                            <p className="text-sm">The void is silent.</p>
                        </Block>
                    )}

                    {!loading && memories.map((memory) => (
                        <DiaryLog key={memory.id} memory={memory} />
                    ))}
                </div>
            </Page>
        </KonstaApp>
    );
}

export default App;
