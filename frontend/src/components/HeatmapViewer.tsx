import { useMemo } from 'react';

interface HeatmapProps {
    title: string;
    data: number[][];
    xAxis: number[];
    yAxis: number[];
    unit: string;
    colorMap?: 'heat' | 'cool' | 'ignition';
    recommendations?: { rpm_index: number, map_index: number, delta: number }[];
}

export function HeatmapViewer({ title, data, xAxis, yAxis, unit, colorMap = 'heat', recommendations = [] }: HeatmapProps) {

    // Find min/max for color scaling
    const { min, max } = useMemo(() => {
        let min = Infinity;
        let max = -Infinity;
        data.forEach(row => {
            row.forEach(val => {
                if (val < min) min = val;
                if (val > max) max = val;
            });
        });
        return { min, max };
    }, [data]);

    const getColor = (value: number) => {
        const ratio = (value - min) / (max - min || 1);

        // Simple color maps
        if (colorMap === 'heat') {
            // Blue -> Red
            const h = (1.0 - ratio) * 240;
            return `hsl(${h}, 80%, 40%)`;
        } else if (colorMap === 'ignition') {
            // Greenish -> Yellowish
            const h = 120 - (ratio * 60);
            return `hsl(${h}, 70%, 40%)`;
        }

        return `hsl(0, 0%, ${ratio * 100}%)`;
    };

    const hasRec = (rIdx: number, cIdx: number) => {
        return recommendations.find(r => r.rpm_index === cIdx && r.map_index === rIdx);
    };

    if (!data || data.length === 0) return null;

    return (
        <div className="bg-black/40 rounded-xl border border-white/10 p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
                <span className="text-xs text-gray-500">[{min.toFixed(1)} - {max.toFixed(1)} {unit}]</span>
            </div>

            <div className="overflow-x-auto pb-2">
                <table className="border-collapse text-[10px] text-center w-full">
                    <thead>
                        <tr>
                            <th className="w-10 h-6 text-gray-500 border border-white/5 bg-white/5 font-medium">MAP \ RPM</th>
                            {xAxis.map((rpm, i) => (
                                <th key={i} className="w-10 h-6 text-gray-400 border border-white/5 bg-white/5 font-medium">{rpm}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.map((row, rIdx) => (
                            <tr key={rIdx}>
                                <th className="w-10 h-6 text-gray-400 border border-white/5 bg-white/5 font-medium">{yAxis[rIdx]}</th>
                                {row.map((val, cIdx) => {
                                    const rec = hasRec(rIdx, cIdx);

                                    return (
                                        <td
                                            key={cIdx}
                                            className={`w-10 h-6 border ${rec ? 'border-yellow-500/50 relative z-10' : 'border-black/50'} text-xs font-mono text-white/90 relative group transition-colors`}
                                            style={{ backgroundColor: getColor(val) }}
                                        >
                                            {val.toFixed(1)}

                                            {/* Tooltip for recommendations */}
                                            {rec && (
                                                <div className="absolute hidden group-hover:block bottom-full left-1/2 -translate-x-1/2 mb-1 p-2 rounded bg-gray-900 border border-yellow-500/50 text-white text-xs w-32 shadow-xl z-50">
                                                    <div className="font-semibold text-yellow-400 mb-1">Proposed Change</div>
                                                    <div className="flex justify-between">
                                                        <span>Delta:</span>
                                                        <span className={rec.delta > 0 ? 'text-green-400' : 'text-red-400'}>
                                                            {rec.delta > 0 ? '+' : ''}{rec.delta.toFixed(1)}
                                                        </span>
                                                    </div>
                                                </div>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
