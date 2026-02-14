import React, { useState, useEffect } from 'react';
import { Page, Block, Preloader } from 'konsta/react';
import axios from 'axios';
import WebApp from '@twa-dev/sdk';
import DiaryLog from '../components/DiaryLog';

export default function MemoriesPage() {
    const [memories, setMemories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchMemories = async () => {
            try {
                const urlParams = new URLSearchParams(window.location.search);
                const userId = urlParams.get('user_id') || WebApp.initDataUnsafe?.user?.id;

                if (!userId) {
                    throw new Error("User ID not found. Please open from Telegram.");
                }

                const response = await axios.get(`/api/memories/${userId}`);
                setMemories(response.data);
            } catch (err) {
                console.error(err);
                if (err.response) {
                    setError(`Error ${err.response.status}: ${JSON.stringify(err.response.data)}`);
                } else if (err.request) {
                    setError("No response received from server.");
                } else {
                    setError(err.message);
                }
            } finally {
                setLoading(false);
            }
        };

        fetchMemories();
    }, []);

    return (
        <div className="space-y-4 pb-24">
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
    );
}
