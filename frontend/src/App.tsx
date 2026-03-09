import { Activity, Car, Settings2, FileBarChart, Gauge, Zap, Database, RefreshCw } from 'lucide-react'
import { DatalogUploader } from './components/DatalogUploader'
import { TableEditor } from './components/TableEditor'
import { useState, useEffect } from 'react'

function App() {
    const [activeTab, setActiveTab] = useState('profile')
    const [baseTune, setBaseTune] = useState<any>(null)
    const [datalogData, setDatalogData] = useState<any>(null)
    const [analysisResult, setAnalysisResult] = useState<any>(null)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [selectedTable, setSelectedTable] = useState('veTable')
    const [tableData, setTableData] = useState<any>(null)
    const [isLoadingTable, setIsLoadingTable] = useState(false)
    const [ecuConnected, setEcuConnected] = useState(false)

    const loadTableFromEcu = async (tableName: string) => {
        setIsLoadingTable(true);
        try {
            const res = await fetch('http://localhost:8001/api/v1/tables/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ table_name: tableName })
            });
            const data = await res.json();
            setTableData(data);
            setEcuConnected(true);
        } catch (err) {
            console.error(err);
            setEcuConnected(false);
        } finally {
            setIsLoadingTable(false);
        }
    }

    const saveTableToEcu = async (newData: number[][]) => {
        try {
            await fetch('http://localhost:8001/api/v1/tables/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    table_name: selectedTable,
                    data: newData
                })
            });
            alert("Table saved to ECU successfully!");
        } catch (err) {
            console.error(err);
            alert("Failed to save table to ECU.");
        }
    }

    useEffect(() => {
        if (activeTab === 'tune') {
            loadTableFromEcu(selectedTable);
        }
    }, [activeTab, selectedTable]);

    // Form states
    const [profile, setProfile] = useState({
        vehicle_id: 'test-car',
        make: 'Honda',
        model: 'Civic',
        displacement_l: 1.8,
        cylinders: 4,
        engine_family: 'B18C',
        injector_cc_min: 440,
        fuel_type: 'gas93',
        aspiration: 'na',
        target_hp: 200,
        compression_ratio: 10.6,
        fuel_pressure_psi: 43.5,
        max_safe_rpm: 8400,
        usage: 'street'
    })

    const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setProfile(p => ({
            ...p,
            [name]: e.target.type === 'number' ? parseFloat(value) : value
        }));
    }

    const generateBaseTune = async () => {
        try {
            const res = await fetch('http://localhost:8001/api/v1/generate_base_tune', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(profile)
            });
            const data = await res.json();
            setBaseTune(data);
            setActiveTab('tune');
        } catch (err) {
            console.error(err);
        }
    }

    const analyzeDatalog = async () => {
        if (!baseTune || !datalogData) return;
        setIsAnalyzing(true);
        try {
            const res = await fetch('http://localhost:8001/api/v1/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vehicle_profile: profile,
                    calibration: baseTune,
                    datalog_summary: datalogData,
                    options: { aggressiveness: 0.5, optimize_for: "power" }
                })
            });
            const data = await res.json();
            setAnalysisResult(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsAnalyzing(false);
        }
    }

    return (
        <div className="min-h-screen bg-[#0f1115] text-white flex flex-col font-sans selection:bg-indigo-500/30">
            <header className="border-b border-indigo-500/10 bg-black/40 backdrop-blur-md sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center h-16">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                                <Gauge className="w-5 h-5 text-white" />
                            </div>
                            <h1 className="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-gray-100 to-gray-400">
                                BaseTune Architect
                            </h1>
                            <span className="ml-2 px-2 py-0.5 rounded text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                rusEFI
                            </span>
                        </div>

                        <nav className="flex space-x-1">
                            {[
                                { id: 'profile', label: 'Vehicle Profile', icon: Car },
                                { id: 'tune', label: 'Base Tune', icon: Settings2 },
                                { id: 'analyze', label: 'Analyze Datalog', icon: FileBarChart },
                                { id: 'live', label: 'Live Monitoring', icon: Activity }
                            ].map((tab) => {
                                const Icon = tab.icon;
                                const isActive = activeTab === tab.id;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${isActive
                                            ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                                            : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                                            }`}
                                    >
                                        <Icon className="w-4 h-4" />
                                        {tab.label}
                                    </button>
                                )
                            })}
                        </nav>

                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
                                <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                                Companion DB
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">

                {activeTab === 'profile' && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <div className="mb-8">
                            <h2 className="text-2xl font-semibold text-gray-100 mb-2">Build Profile Wizard</h2>
                            <p className="text-gray-400">Configure your engine fundamentals to generate an accurate base calibration.</p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="p-6 rounded-xl bg-white/[0.02] border border-white/5 backdrop-blur-sm">
                                <h3 className="text-lg font-medium text-gray-200 mb-4 flex items-center gap-2">
                                    <Settings2 className="w-5 h-5 text-indigo-400" />
                                    Engine Core
                                </h3>
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-xs font-medium text-gray-400 mb-1.5">Make</label>
                                            <input name="make" value={profile.make} onChange={handleProfileChange} type="text" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50" />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-400 mb-1.5">Model</label>
                                            <input name="model" value={profile.model} onChange={handleProfileChange} type="text" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50" />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-xs font-medium text-gray-400 mb-1.5">Displacement (L)</label>
                                            <input name="displacement_l" value={profile.displacement_l} onChange={handleProfileChange} type="number" step="0.1" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50" />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-400 mb-1.5">Cylinders</label>
                                            <input name="cylinders" value={profile.cylinders} onChange={handleProfileChange} type="number" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50" />
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1.5">Engine Family</label>
                                        <input name="engine_family" value={profile.engine_family} onChange={handleProfileChange} type="text" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50" />
                                    </div>
                                </div>
                            </div>

                            <div className="p-6 rounded-xl bg-white/[0.02] border border-white/5 backdrop-blur-sm">
                                <h3 className="text-lg font-medium text-gray-200 mb-4 flex items-center gap-2">
                                    <Zap className="w-5 h-5 text-indigo-400" />
                                    Fuel & Air
                                </h3>
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-xs font-medium text-gray-400 mb-1.5">Injector Size (cc/min)</label>
                                            <input name="injector_cc_min" value={profile.injector_cc_min} onChange={handleProfileChange} type="number" step="10" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50" />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-400 mb-1.5">Fuel Type</label>
                                            <select name="fuel_type" value={profile.fuel_type} onChange={handleProfileChange} className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50 appearance-none">
                                                <option value="gas93">Gasoline (93 Oct)</option>
                                                <option value="e85">E85</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1.5">Aspiration</label>
                                        <select name="aspiration" value={profile.aspiration} onChange={handleProfileChange} className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50 appearance-none">
                                            <option value="na">Naturally Aspirated</option>
                                            <option value="turbo">Turbocharged</option>
                                            <option value="supercharged">Supercharged</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1.5">Target HP</label>
                                        <input name="target_hp" value={profile.target_hp} onChange={handleProfileChange} type="number" step="10" className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50" />
                                    </div>
                                </div>

                                <div className="mt-8 flex justify-end">
                                    <button onClick={generateBaseTune} className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white text-sm font-medium shadow-lg shadow-indigo-500/25 transition-all w-full flex items-center justify-center gap-2">
                                        <Settings2 className="w-4 h-4" />
                                        Generate Base Tune
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'tune' && (
                    <div className="h-[calc(100vh-12rem)] flex gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        {/* Table Sidebar */}
                        <div className="w-64 space-y-4">
                            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Available Tables</h3>
                                <div className="space-y-1">
                                    {[
                                        { id: 'veTable', label: 'Fuel VE' },
                                        { id: 'ignitionTable', label: 'Ignition' },
                                        { id: 'boostTableOpenLoop', label: 'Boost Open Loop' },
                                        { id: 'boostTableClosedLoop', label: 'Boost Closed Loop' },
                                        { id: 'lambdaTable', label: 'Target Lambda' }
                                    ].map(t => (
                                        <button
                                            key={t.id}
                                            onClick={() => setSelectedTable(t.id)}
                                            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${selectedTable === t.id
                                                ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-lg shadow-indigo-500/5'
                                                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                                                }`}
                                        >
                                            {t.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <button
                                onClick={() => loadTableFromEcu(selectedTable)}
                                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/[0.02] border border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/10 transition-all text-sm font-medium"
                            >
                                <RefreshCw className={`w-4 h-4 ${isLoadingTable ? 'animate-spin' : ''}`} />
                                Reload from ECU
                            </button>
                        </div>

                        {/* Editor Main Area */}
                        <div className="flex-1 flex flex-col gap-6">
                            {tableData ? (
                                <TableEditor
                                    tableName={tableData.table_name || selectedTable}
                                    data={tableData.data}
                                    xAxis={tableData.rpm_axis}
                                    yAxis={tableData.map_axis}
                                    onSave={saveTableToEcu}
                                    connected={ecuConnected}
                                />
                            ) : (
                                <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-white/10 rounded-xl bg-white/[0.01]">
                                    {isLoadingTable ? (
                                        <RefreshCw className="w-12 h-12 text-indigo-500 animate-spin mb-4" />
                                    ) : (
                                        <Database className="w-12 h-12 text-gray-600 mb-4" />
                                    )}
                                    <h3 className="text-lg font-medium text-gray-400">
                                        {isLoadingTable ? 'Fetching Table Data...' : 'Connection Required'}
                                    </h3>
                                    <p className="text-sm text-gray-600 mt-2 text-center max-w-xs">
                                        {isLoadingTable
                                            ? 'Reading binary data from rusEFI over serial protocol.'
                                            : 'Please ensure your ECU is connected via binary protocol.'}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'analyze' && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <div className="mb-6">
                            <h2 className="text-2xl font-semibold text-gray-100 mb-2">Datalog Analyzer</h2>
                            <p className="text-gray-400">Upload a datalog to let the Guardian system analyze and propose safe corrections.</p>
                        </div>

                        {!datalogData ? (
                            <DatalogUploader onUploadComplete={setDatalogData} />
                        ) : (
                            <div className="p-6 rounded-xl bg-white/[0.02] border border-white/5 space-y-4">
                                <h3 className="text-lg font-medium text-green-400">Datalog Uploaded Successfully</h3>
                                <p className="text-sm text-gray-400">
                                    The datalog has been parsed into {datalogData.cells?.length || 0} distinct load/rpm cells.
                                    We can now run this against your `{profile.engine_family}` profile and the Knowledge Base constraints.
                                </p>

                                {!analysisResult ? (
                                    <div className="flex gap-4 pt-4">
                                        <button
                                            onClick={analyzeDatalog}
                                            disabled={isAnalyzing}
                                            className="px-6 py-2 rounded bg-indigo-500 hover:bg-indigo-400 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 disabled:opacity-50 flex items-center gap-2 transition-colors">
                                            {isAnalyzing ? <span className="animate-spin w-4 h-4 border-2 border-white/20 border-t-white rounded-full"></span> : <Zap className="w-4 h-4" />}
                                            {isAnalyzing ? "Analyzing via LLM..." : "Analyze with Guardian LLM"}
                                        </button>
                                        <button onClick={() => setDatalogData(null)} className="px-4 py-2 rounded border border-white/10 hover:bg-white/5 text-sm font-medium text-gray-200 transition-colors">Cancel</button>
                                    </div>
                                ) : (
                                    <div className="mt-4 p-4 border border-indigo-500/20 bg-indigo-500/5 rounded-lg">
                                        <h4 className="text-indigo-400 font-medium mb-2">Analysis Complete!</h4>
                                        <p className="text-sm text-gray-300 mb-4">{analysisResult.summary_text}</p>
                                        {analysisResult.warnings?.length > 0 && (
                                            <div className="mb-4">
                                                <p className="text-xs font-semibold text-yellow-500 mb-1">Guardrail Warnings:</p>
                                                <ul className="list-disc list-inside text-xs text-yellow-400/80">
                                                    {analysisResult.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
                                                </ul>
                                            </div>
                                        )}
                                        <div className="flex gap-3">
                                            <button onClick={() => setActiveTab('tune')} className="px-4 py-2 rounded bg-indigo-500 hover:bg-indigo-400 text-sm font-medium text-white transition-colors">Review Heatmap Setup</button>
                                            <button onClick={() => { setDatalogData(null); setAnalysisResult(null); }} className="px-4 py-2 rounded border border-white/10 hover:bg-white/5 text-sm font-medium text-gray-200 transition-colors">Start Over</button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'live' && (
                    <div className="flex flex-col items-center justify-center h-64 border border-dashed border-white/10 rounded-xl bg-white/[0.01]">
                        <Activity className="w-12 h-12 text-gray-600 mb-4 animate-pulse" />
                        <h3 className="text-lg font-medium text-gray-400">Live Monitor Preview</h3>
                        <p className="text-sm text-gray-600 mt-2">Coming in Milestone 5.</p>
                    </div>
                )}
            </main>
        </div>
    )
}

export default App
