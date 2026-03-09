import React, { useCallback, useState } from 'react';
import { UploadCloud, CheckCircle, AlertCircle } from 'lucide-react';

export function DatalogUploader({ onUploadComplete }: { onUploadComplete: (data: any) => void }) {
    const [isDragging, setIsDragging] = useState(false);
    const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');

    const onDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const onDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleFile = async (file: File) => {
        if (!file.name.endsWith('.csv') && !file.name.endsWith('.msl')) {
            setStatus('error');
            return;
        }

        setStatus('uploading');

        // Simulate API call to POST /upload_datalog
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('http://localhost:8000/api/v1/upload_datalog', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Upload failed');

            const data = await response.json();
            setStatus('success');
            onUploadComplete(data);
        } catch (e) {
            setStatus('error');
        }
    };

    const onDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    }, []);

    return (
        <div
            className={`relative flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-xl transition-all duration-200 ${isDragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
                }`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
        >
            {status === 'idle' && (
                <>
                    <div className="w-12 h-12 rounded-full bg-indigo-500/20 flex items-center justify-center mb-4 text-indigo-400">
                        <UploadCloud className="w-6 h-6" />
                    </div>
                    <h3 className="text-lg font-medium text-gray-200 mb-2">Upload Datalog</h3>
                    <p className="text-sm text-gray-400 text-center max-w-sm">
                        Drag and drop your TunerStudio .msl or .csv file here to analyze and generate corrections.
                    </p>
                </>
            )}

            {status === 'uploading' && (
                <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin mb-4" />
                    <h3 className="text-lg font-medium text-gray-200">Processing Datalog...</h3>
                </div>
            )}

            {status === 'success' && (
                <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mb-4 text-green-400">
                        <CheckCircle className="w-6 h-6" />
                    </div>
                    <h3 className="text-lg font-medium text-green-400">Analysis Complete</h3>
                </div>
            )}

            {status === 'error' && (
                <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center mb-4 text-red-400">
                        <AlertCircle className="w-6 h-6" />
                    </div>
                    <h3 className="text-lg font-medium text-red-400 mb-2">Upload Failed</h3>
                    <button
                        onClick={() => setStatus('idle')}
                        className="px-4 py-1.5 rounded bg-red-500/20 text-red-300 text-sm font-medium hover:bg-red-500/30"
                    >
                        Try Again
                    </button>
                </div>
            )}
        </div>
    );
}
