import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Undo2, Redo2, Save, ChevronUp, ChevronDown } from 'lucide-react';

interface TableEditorProps {
    tableName: string;
    data: number[][];
    xAxis: number[];
    yAxis: number[];
    onSave: (newData: number[][]) => void;
    connected: boolean;
    limits?: { min: number, max: number };
    risk?: { low: number, high: number };
}

export function TableEditor({
    tableName,
    data: initialData,
    xAxis,
    yAxis,
    onSave,
    connected,
    limits = { min: 0, max: 255 },
    risk = { low: 210, high: 235 }
}: TableEditorProps) {
    const [matrix, setMatrix] = useState<number[][]>(initialData);
    const [selection, setSelection] = useState<[number, number][]>([]);
    const [isSelecting, setIsSelecting] = useState(false);
    const [anchor, setAnchor] = useState<[number, number] | null>(null);
    const [undoStack, setUndoStack] = useState<string[]>([]);
    const [redoStack, setRedoStack] = useState<string[]>([]);
    const [message, setMessage] = useState("");

    const gridRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setMatrix(initialData);
        setSelection([]);
        setUndoStack([]);
        setRedoStack([]);
    }, [initialData, tableName]);

    const pushUndo = useCallback(() => {
        setUndoStack(prev => [...prev.slice(-49), JSON.stringify(matrix)]);
        setRedoStack([]);
    }, [matrix]);

    const handleUndo = () => {
        if (undoStack.length === 0) return;
        const last = undoStack[undoStack.length - 1];
        setRedoStack(prev => [...prev, JSON.stringify(matrix)]);
        setMatrix(JSON.parse(last));
        setUndoStack(prev => prev.slice(0, -1));
        showMessage("Undo applied");
    };

    const handleRedo = () => {
        if (redoStack.length === 0) return;
        const last = redoStack[redoStack.length - 1];
        setUndoStack(prev => [...prev, JSON.stringify(matrix)]);
        setMatrix(JSON.parse(last));
        setRedoStack(prev => prev.slice(0, -1));
        showMessage("Redo applied");
    };

    const showMessage = (msg: string) => {
        setMessage(msg);
        setTimeout(() => setMessage(v => v === msg ? "" : v), 3000);
    };

    const getCellClass = (val: number) => {
        if (val < limits.min || val > limits.max) return "bg-red-900/40 text-red-400 font-bold border-red-500/50";
        if (val >= risk.low && val <= risk.high) return "bg-amber-900/30 text-amber-400 border-amber-500/30";
        return "bg-emerald-900/10 text-emerald-400 border-emerald-500/20";
    };

    const isSelected = (r: number, c: number) => {
        return selection.some(([sr, sc]) => sr === r && sc === c);
    };

    const handleMouseDown = (r: number, c: number, e: React.MouseEvent) => {
        if (e.button !== 0) return;
        setIsSelecting(true);
        setAnchor([r, c]);
        if (!e.shiftKey) {
            setSelection([[r, c]]);
        } else if (anchor) {
            updateSelection(anchor, [r, c]);
        }
    };

    const handleMouseOver = (r: number, c: number) => {
        if (!isSelecting || !anchor) return;
        updateSelection(anchor, [r, c]);
    };

    const updateSelection = (start: [number, number], end: [number, number]) => {
        const minR = Math.min(start[0], end[0]), maxR = Math.max(start[0], end[0]);
        const minC = Math.min(start[1], end[1]), maxC = Math.max(start[1], end[1]);
        const newSel: [number, number][] = [];
        for (let r = minR; r <= maxR; r++) {
            for (let c = minC; c <= maxC; c++) newSel.push([r, c]);
        }
        setSelection(newSel);
    };

    const handleCellChange = (r: number, c: number, val: string) => {
        const v = parseFloat(val);
        if (isNaN(v)) return;
        pushUndo();
        const newMatrix = [...matrix];
        newMatrix[r] = [...newMatrix[r]];
        newMatrix[r][c] = v;
        setMatrix(newMatrix);
    };

    // Math Tools
    const applyMath = (type: 'average' | 'interp_h' | 'interp_v' | 'interp_2d' | 'incr' | 'decr' | 'set') => {
        if (selection.length === 0) return;
        pushUndo();
        const newMatrix = JSON.parse(JSON.stringify(matrix));
        const rows = selection.map(s => s[0]), cols = selection.map(s => s[1]);
        const minR = Math.min(...rows), maxR = Math.max(...rows);
        const minC = Math.min(...cols), maxC = Math.max(...cols);

        if (type === 'average') {
            let sum = 0;
            selection.forEach(([r, c]) => sum += matrix[r][c]);
            const avg = parseFloat((sum / selection.length).toFixed(2));
            selection.forEach(([r, c]) => newMatrix[r][c] = avg);
        } else if (type === 'interp_h') {
            for (let r = minR; r <= maxR; r++) {
                const vS = matrix[r][minC], vE = matrix[r][maxC], count = maxC - minC;
                if (count > 0) for (let c = minC; c <= maxC; c++)
                    newMatrix[r][c] = parseFloat((vS + (vE - vS) * (c - minC) / count).toFixed(2));
            }
        } else if (type === 'interp_v') {
            for (let c = minC; c <= maxC; c++) {
                const vS = matrix[minR][c], vE = matrix[maxR][c], count = maxR - minR;
                if (count > 0) for (let r = minR; r <= maxR; r++)
                    newMatrix[r][c] = parseFloat((vS + (vE - vS) * (r - minR) / count).toFixed(2));
            }
        } else if (type === 'interp_2d') {
            const v00 = matrix[minR][minC], v01 = matrix[minR][maxC], v10 = matrix[maxR][minC], v11 = matrix[maxR][maxC];
            const rC = maxR - minR, cC = maxC - minC;
            if (rC > 0 && cC > 0) {
                for (let r = minR; r <= maxR; r++) for (let c = minC; c <= maxC; c++) {
                    const tr = (r - minR) / rC, tc = (c - minC) / cC;
                    newMatrix[r][c] = parseFloat(((1 - tr) * (1 - tc) * v00 + (1 - tr) * tc * v01 + tr * (1 - tc) * v10 + tr * tc * v11).toFixed(2));
                }
            }
        } else if (type === 'incr') {
            selection.forEach(([r, c]) => newMatrix[r][c] = parseFloat((matrix[r][c] * 1.05).toFixed(2)));
        } else if (type === 'decr') {
            selection.forEach(([r, c]) => newMatrix[r][c] = parseFloat((matrix[r][c] * 0.95).toFixed(2)));
        }

        setMatrix(newMatrix);
        showMessage(`Applied ${type}`);
    };

    useEffect(() => {
        const handleGlobalMouseUp = () => setIsSelecting(false);
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.ctrlKey && e.key === 'z') { e.preventDefault(); handleUndo(); }
            if (e.ctrlKey && e.key === 'y') { e.preventDefault(); handleRedo(); }
            if (e.ctrlKey && e.key === 's') { e.preventDefault(); onSave(matrix); }
        };
        window.addEventListener('mouseup', handleGlobalMouseUp);
        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('mouseup', handleGlobalMouseUp);
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [matrix, undoStack, redoStack, onSave]);

    return (
        <div className="flex flex-col h-full bg-[#1e293b] rounded-xl border border-white/10 overflow-hidden shadow-2xl">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-3 bg-black/40 border-b border-white/5">
                <div className="flex items-center gap-4">
                    <h3 className="text-sm font-bold text-indigo-400 uppercase tracking-wider">{tableName}</h3>
                    <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
                        <button onClick={handleUndo} disabled={undoStack.length === 0} className="p-1.5 hover:bg-white/10 disabled:opacity-30 rounded transition-colors text-gray-300" title="Undo (Ctrl+Z)"><Undo2 size={16} /></button>
                        <button onClick={handleRedo} disabled={redoStack.length === 0} className="p-1.5 hover:bg-white/10 disabled:opacity-30 rounded transition-colors text-gray-300" title="Redo (Ctrl+Y)"><Redo2 size={16} /></button>
                    </div>
                    <div className="h-6 w-px bg-white/10 mx-1" />
                    <div className="flex items-center gap-1">
                        <button onClick={() => applyMath('average')} className="px-2 py-1 text-xs font-medium hover:bg-indigo-500/20 text-indigo-300 rounded border border-indigo-500/30 transition-all">AVERAGE</button>
                        <button onClick={() => applyMath('interp_2d')} className="px-2 py-1 text-xs font-medium hover:bg-indigo-500/20 text-indigo-300 rounded border border-indigo-500/30 transition-all">INTERP 2D</button>
                        <button onClick={() => applyMath('incr')} className="p-1.5 hover:bg-white/10 text-gray-300 rounded transition-colors" title="+5%"><ChevronUp size={16} /></button>
                        <button onClick={() => applyMath('decr')} className="p-1.5 hover:bg-white/10 text-gray-300 rounded transition-colors" title="-5%"><ChevronDown size={16} /></button>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-amber-500 font-bold">{message}</span>
                    <button
                        onClick={() => onSave(matrix)}
                        className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-indigo-900/40 transition-all"
                    >
                        <Save size={14} />
                        WRITE TO ECU
                    </button>
                </div>
            </div>

            {/* Grid Container */}
            <div className="flex-1 overflow-auto p-4 custom-scrollbar bg-[#0f172a]" ref={gridRef}>
                <table className="border-collapse w-full select-none cursor-cell">
                    <thead>
                        <tr>
                            <th className="sticky left-0 top-0 z-20 bg-[#1e293b] border border-white/10 px-3 py-2 text-[10px] font-bold text-gray-500 uppercase">MAP \ RPM</th>
                            {xAxis.map((val, i) => (
                                <th key={i} className="sticky top-0 z-10 bg-[#1e293b] border border-white/10 px-2 py-1.5 text-[10px] font-mono text-gray-400 min-w-[50px]">
                                    {val}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {matrix.map((row, r) => (
                            <tr key={r}>
                                <th className="sticky left-0 z-10 bg-[#1e293b] border border-white/10 px-3 py-1.5 text-[10px] font-mono text-gray-400 text-right min-w-[60px]">
                                    {yAxis[r]}
                                </th>
                                {row.map((val, c) => (
                                    <td
                                        key={c}
                                        onMouseDown={(e) => handleMouseDown(r, c, e)}
                                        onMouseOver={() => handleMouseOver(r, c)}
                                        className={`border px-2 py-1.5 text-xs font-mono text-center transition-all duration-75 relative
                                            ${getCellClass(val)}
                                            ${isSelected(r, c) ? 'ring-2 ring-white ring-inset z-10 brightness-110 shadow-lg' : 'border-white/5'}
                                        `}
                                    >
                                        <input
                                            type="text"
                                            value={val}
                                            onChange={(e) => handleCellChange(r, c, e.target.value)}
                                            className="w-full bg-transparent text-center border-none outline-none focus:ring-0 cursor-cell"
                                            readOnly={!connected}
                                        />
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Footer / Info */}
            <div className="px-4 py-2 bg-black/60 border-t border-white/5 flex justify-between items-center text-[10px] font-medium text-gray-500 uppercase tracking-widest">
                <div className="flex gap-4">
                    <span>Range: {limits.min} - {limits.max}</span>
                    <span className={connected ? 'text-emerald-500' : 'text-red-500'}>{connected ? '● LIVE' : '○ OFFLINE'}</span>
                </div>
                <div>{selection.length} Cells Selected</div>
            </div>
        </div>
    );
}
