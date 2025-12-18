import { useState, useEffect } from 'react';

const scenarios = {
  none: { name: '⚙️ Custom', desc: 'Use manual settings without predefined events', ticks: null },
  balanced: { name: '⚖️ Balanced', desc: 'Standard training with normal event rates', ticks: 10000 },
  stress_test: { name: '😰 Stress Test', desc: 'High anxiety to develop resilience neurons', ticks: 5000 },
  reward_rich: { name: '🎁 Reward Rich', desc: 'Frequent positive outcomes for reward pathways', ticks: 8000 },
  novelty_exploration: { name: '🔍 Novelty', desc: 'High curiosity with new object encounters', ticks: 6000 },
  endurance: { name: '🏃 Endurance', desc: 'Long-duration training session', ticks: 50000 },
};

export default function HeadlessLauncher() {
  const [brainFile, setBrainFile] = useState('');
  const [outputFile, setOutputFile] = useState('');
  const [ticks, setTicks] = useState(10000);
  const [progress, setProgress] = useState(500);
  const [learningRate, setLearningRate] = useState('');
  const [maxNeurons, setMaxNeurons] = useState('');
  const [neurogenesis, setNeurogenesis] = useState(true);
  const [quietMode, setQuietMode] = useState(false);
  const [scenario, setScenario] = useState('none');
  const [copied, setCopied] = useState('');

  const selectScenario = (key) => {
    setScenario(key);
    if (scenarios[key].ticks) {
      setTicks(scenarios[key].ticks);
    }
  };

  const getCommand = () => {
    let cmd = 'python headless_trainer.py';
    if (brainFile) cmd += ` --brain "${brainFile}"`;
    if (scenario !== 'none') cmd += ` --scenario ${scenario}`;
    cmd += ` --ticks ${ticks}`;
    if (outputFile) cmd += ` --output "${outputFile}"`;
    if (progress !== 500) cmd += ` --progress ${progress}`;
    if (learningRate) cmd += ` --learning-rate ${learningRate}`;
    if (maxNeurons) cmd += ` --max-neurons ${maxNeurons}`;
    if (!neurogenesis) cmd += ` --neurogenesis False`;
    if (quietMode) cmd += ` --quiet`;
    return cmd;
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(''), 2000);
  };

  const estTime = (ticks / 30000).toFixed(1);
  const estNeuronsMin = Math.floor(ticks / 2000);
  const estNeuronsMax = Math.min(Math.floor(ticks / 500), 100);
  const estHebbian = Math.floor(ticks / 30);

  return (
    <div className="min-h-screen bg-slate-900 text-gray-100 p-4">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6 p-4 bg-slate-800 rounded-xl border border-slate-700">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-rose-400 to-pink-300 bg-clip-text text-transparent">
            🦑 Dosidicus-2 Headless Trainer
          </h1>
          <p className="text-gray-400 text-sm mt-1">Configure and launch accelerated brain training</p>
        </div>

        {/* Brain Config */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4 border border-slate-700">
          <h2 className="text-rose-400 font-semibold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 bg-rose-400 rounded" />
            Brain Configuration
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400">Brain File (JSON)</label>
              <input
                type="text"
                value={brainFile}
                onChange={(e) => setBrainFile(e.target.value)}
                placeholder="path/to/brain.json"
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm focus:border-rose-400 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400">Output File</label>
              <input
                type="text"
                value={outputFile}
                onChange={(e) => setOutputFile(e.target.value)}
                placeholder="trained_brain.json"
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm focus:border-rose-400 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Training Params */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4 border border-slate-700">
          <h2 className="text-rose-400 font-semibold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 bg-rose-400 rounded" />
            Training Parameters
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="text-xs text-gray-400">Training Ticks</label>
              <input
                type="number"
                value={ticks}
                onChange={(e) => setTicks(parseInt(e.target.value) || 1000)}
                min={100}
                step={1000}
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm focus:border-rose-400 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400">Progress Interval</label>
              <input
                type="number"
                value={progress}
                onChange={(e) => setProgress(parseInt(e.target.value) || 0)}
                min={0}
                step={100}
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm focus:border-rose-400 focus:outline-none"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-slate-900 rounded p-3 text-center">
              <div className="text-xl font-bold text-rose-400">{estTime}s</div>
              <div className="text-xs text-gray-500">Est. Time</div>
            </div>
            <div className="bg-slate-900 rounded p-3 text-center">
              <div className="text-xl font-bold text-rose-400">~{estNeuronsMin}-{estNeuronsMax}</div>
              <div className="text-xs text-gray-500">New Neurons</div>
            </div>
            <div className="bg-slate-900 rounded p-3 text-center">
              <div className="text-xl font-bold text-rose-400">~{estHebbian}</div>
              <div className="text-xs text-gray-500">Hebbian Updates</div>
            </div>
          </div>
        </div>

        {/* Scenarios */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4 border border-slate-700">
          <h2 className="text-rose-400 font-semibold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 bg-rose-400 rounded" />
            Training Scenario
          </h2>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(scenarios).map(([key, info]) => (
              <button
                key={key}
                onClick={() => selectScenario(key)}
                className={`p-2 rounded border text-left transition-all text-sm ${
                  scenario === key
                    ? 'border-emerald-400 bg-emerald-400/10'
                    : 'border-slate-600 bg-slate-900 hover:border-rose-400'
                }`}
              >
                <div className="font-medium">{info.name}</div>
                <div className="text-xs text-gray-500 mt-1">{info.desc}</div>
                {info.ticks && (
                  <div className="text-xs text-amber-400 mt-1">{info.ticks.toLocaleString()} ticks</div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Advanced */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4 border border-slate-700">
          <h2 className="text-rose-400 font-semibold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 bg-rose-400 rounded" />
            Advanced Options
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-400">Learning Rate</label>
              <input
                type="number"
                value={learningRate}
                onChange={(e) => setLearningRate(e.target.value)}
                placeholder="0.1"
                step={0.01}
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm focus:border-rose-400 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400">Max Neurons</label>
              <input
                type="number"
                value={maxNeurons}
                onChange={(e) => setMaxNeurons(e.target.value)}
                placeholder="100"
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm focus:border-rose-400 focus:outline-none"
              />
            </div>
          </div>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={neurogenesis}
                onChange={(e) => setNeurogenesis(e.target.checked)}
                className="w-4 h-4 accent-rose-400"
              />
              <span className="text-sm">Enable Neurogenesis</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={quietMode}
                onChange={(e) => setQuietMode(e.target.checked)}
                className="w-4 h-4 accent-rose-400"
              />
              <span className="text-sm">Quiet Mode</span>
            </label>
          </div>
        </div>

        {/* Command Output */}
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <h2 className="text-rose-400 font-semibold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 bg-rose-400 rounded" />
            Generated Command
          </h2>
          <div className="bg-slate-900 rounded p-3 font-mono text-sm break-all border border-slate-700">
            <span className="text-emerald-400">python</span>{' '}
            <span className="text-gray-300">headless_trainer.py</span>
            {brainFile && (
              <> <span className="text-amber-400">--brain</span> <span className="text-sky-300">"{brainFile}"</span></>
            )}
            {scenario !== 'none' && (
              <> <span className="text-amber-400">--scenario</span> <span className="text-sky-300">{scenario}</span></>
            )}
            <> <span className="text-amber-400">--ticks</span> <span className="text-sky-300">{ticks}</span></>
            {outputFile && (
              <> <span className="text-amber-400">--output</span> <span className="text-sky-300">"{outputFile}"</span></>
            )}
            {progress !== 500 && (
              <> <span className="text-amber-400">--progress</span> <span className="text-sky-300">{progress}</span></>
            )}
            {learningRate && (
              <> <span className="text-amber-400">--learning-rate</span> <span className="text-sky-300">{learningRate}</span></>
            )}
            {maxNeurons && (
              <> <span className="text-amber-400">--max-neurons</span> <span className="text-sky-300">{maxNeurons}</span></>
            )}
            {!neurogenesis && (
              <> <span className="text-amber-400">--neurogenesis</span> <span className="text-sky-300">False</span></>
            )}
            {quietMode && (
              <> <span className="text-amber-400">--quiet</span></>
            )}
          </div>
          
          <div className="flex gap-2 mt-3 flex-wrap">
            <button
              onClick={() => copyToClipboard(getCommand(), 'cmd')}
              className="px-4 py-2 bg-rose-500 hover:bg-rose-400 rounded font-medium text-sm transition-colors"
            >
              {copied === 'cmd' ? '✓ Copied!' : '📋 Copy Command'}
            </button>
            <button
              onClick={() => copyToClipboard(
                `@echo off\necho Dosidicus-2 Headless Trainer\necho.\n${getCommand()}\npause`,
                'bat'
              )}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded font-medium text-sm transition-colors border border-slate-600"
            >
              {copied === 'bat' ? '✓ Copied!' : '📄 Copy .bat'}
            </button>
            <button
              onClick={() => copyToClipboard(
                `#!/bin/bash\necho "Dosidicus-2 Headless Trainer"\n${getCommand()}`,
                'sh'
              )}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded font-medium text-sm transition-colors border border-slate-600"
            >
              {copied === 'sh' ? '✓ Copied!' : '📄 Copy .sh'}
            </button>
          </div>
        </div>

        <div className="text-center text-gray-500 text-xs mt-4">
          Dosidicus-2 Headless Trainer Launcher
        </div>
      </div>
    </div>
  );
}
