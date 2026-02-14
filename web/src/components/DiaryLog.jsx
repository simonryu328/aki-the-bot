import React from 'react';
import { Card } from 'konsta/react';

const DiaryLog = ({ memory }) => {
    const date = new Date(memory.timestamp).toLocaleDateString(undefined, {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    return (
        <div className="px-4 py-2">
            <div className="relative bg-space-dark border border-gray-800 rounded-xl p-4 shadow-lg overflow-hidden">
                {/* Sci-fi decorative elements */}
                <div className="absolute top-0 right-0 w-16 h-16 bg-blue-500/10 rounded-bl-full -mr-4 -mt-4"></div>

                {/* Header */}
                <div className="flex justify-between items-start mb-3">
                    <div className="flex flex-col">
                        <span className="text-xs font-mono text-blue-400 uppercase tracking-widest">
                            LOG #{memory.id.toString().padStart(4, '0')}
                        </span>
                        <h3 className="text-lg font-bold text-white mt-1">
                            {memory.title}
                        </h3>
                    </div>
                    {memory.importance >= 8 && (
                        <span className="bg-yellow-500/20 text-yellow-300 text-[10px] font-bold px-2 py-1 rounded uppercase border border-yellow-500/30">
                            Critical
                        </span>
                    )}
                </div>

                {/* Content */}
                <div className="text-gray-300 text-sm leading-relaxed font-sans whitespace-pre-wrap">
                    {memory.content}
                </div>

                {/* Footer */}
                <div className="mt-4 pt-3 border-t border-gray-800 flex justify-between items-center">
                    <span className="text-xs text-gray-500 font-mono">
                        {date}
                    </span>
                    <span className="text-xs text-gray-600 font-mono">
                        TYPE: {memory.entry_type?.toUpperCase() || 'UNKNOWN'}
                    </span>
                </div>

                {/* Image if available */}
                {memory.image_url && (
                    <div className="mt-4 rounded-lg overflow-hidden border border-gray-700">
                        <img src={memory.image_url} alt="Memory Visual" className="w-full h-auto object-cover max-h-60" />
                    </div>
                )}
            </div>
        </div>
    );
};

export default DiaryLog;
