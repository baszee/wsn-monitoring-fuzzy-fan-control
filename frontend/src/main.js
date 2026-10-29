/**
 * Entrypoint Aplikasi Frontend Dashboard WSN.
 */

// import './style.css'; // Gaya dimuat via index.html style/link tag
import { fetchLatestNodes, fetchLatestControl, fetchFuzzyDetail, triggerManualTick } from './api.js';
import { renderHeader } from './components/Header.js';
import { renderNodeCards } from './components/NodeCards.js';
import { renderFanControlPanel } from './components/FanControlPanel.js';
import { renderDecisionChain } from './components/DecisionChain.js';
import { renderSimulationPanel } from './components/SimulationPanel.js';

// Application State
const state = {
  nodes: [],
  controlData: null,
  selectedNodeId: null,
  fuzzyDetail: null,
  isOnline: true,
  lastUpdated: null,
};

async function updateData() {
  const [nodesRes, controlRes] = await Promise.all([
    fetchLatestNodes(),
    fetchLatestControl(),
  ]);

  if (!nodesRes && !controlRes) {
    state.isOnline = false;
    renderApp();
    return;
  }

  state.isOnline = true;
  state.lastUpdated = new Date();

  if (nodesRes) state.nodes = nodesRes;
  if (controlRes) state.controlData = controlRes;

  // Tentukan default selected node: utamakan node penentu i* jika belum ada pilihan manual
  const determiningNodeId = state.controlData?.determining_node_id;
  if (!state.selectedNodeId || !state.nodes.some(n => n.node_id === state.selectedNodeId)) {
    state.selectedNodeId = determiningNodeId || state.nodes[0]?.node_id || 'NODE-01';
  }

  // Ambil detail transparansi fuzzy untuk node terpilih
  if (state.selectedNodeId) {
    const detail = await fetchFuzzyDetail(state.selectedNodeId);
    if (detail) state.fuzzyDetail = detail;
  }

  renderApp();
}

function renderApp() {
  const appContainer = document.getElementById('app');
  if (!appContainer) return;

  const headerContainer = document.getElementById('header-section');
  const nodeCardsContainer = document.getElementById('nodes-section');
  const fanControlContainer = document.getElementById('fan-section');
  const decisionContainer = document.getElementById('decision-section');
  const simulationContainer = document.getElementById('simulation-section');

  // Render Header
  if (headerContainer) {
    renderHeader(headerContainer, {
      controlData: state.controlData,
      lastUpdated: state.lastUpdated,
      isOnline: state.isOnline,
      onRefresh: async () => {
        await triggerManualTick();
        await updateData();
      },
    });
  }

  // Render Node Cards
  if (nodeCardsContainer) {
    renderNodeCards(nodeCardsContainer, {
      nodes: state.nodes,
      selectedNodeId: state.selectedNodeId,
      onSelectNode: async (nodeId) => {
        state.selectedNodeId = nodeId;
        state.fuzzyDetail = await fetchFuzzyDetail(nodeId);
        renderApp();
      },
    });
  }

  // Render Fan Control Panel
  if (fanControlContainer) {
    renderFanControlPanel(fanControlContainer, {
      controlData: state.controlData,
    });
  }

  // Render Decision Chain
  if (decisionContainer) {
    const isDetermining = state.selectedNodeId === state.controlData?.determining_node_id;
    const pwmVal = state.controlData?.pwm_command_percent;
    renderDecisionChain(decisionContainer, {
      fuzzyDetail: state.fuzzyDetail,
      selectedNodeId: state.selectedNodeId,
      isDetermining,
      pwmValue: pwmVal,
    });
  }

  // Simulation Panel hanya di-render sekali pada initialization
}

// Inisialisasi awal saat DOM siap
document.addEventListener('DOMContentLoaded', () => {
  // Render simulation panel sekali di awal
  const simulationContainer = document.getElementById('simulation-section');
  if (simulationContainer) {
    renderSimulationPanel(simulationContainer);
  }

  // Polling data perdana
  updateData();

  // Polling data otomatis tiap 5 detik (sinkron dengan worker background)
  setInterval(updateData, 5000);
});
