<script>
  import { onMount, onDestroy } from 'svelte';
  import Chart from 'chart.js/auto';
  import { fade } from 'svelte/transition';

  let chartCanvas;
  let chart;
  let loading = true;
  let error = null;
  let updateInterval;

  async function fetchHourlyData() {
    try {
      const response = await fetch('/api/incidents/hourly');
      if (!response.ok) throw new Error('Failed to fetch hourly data');
      const data = await response.json();
      return data;
    } catch (err) {
      console.error('Error fetching hourly data:', err);
      error = 'Failed to load chart data';
      return null;
    }
  }

  function createChart(data) {
    if (!data || !data.labels || !data.counts || !chartCanvas) return;

    const ctx = chartCanvas.getContext('2d');
    
    // Destroy existing chart if it exists
    if (chart) {
      chart.destroy();
    }

    // Create gradient for the line
    const gradient = ctx.createLinearGradient(0, 0, 0, 100);
    gradient.addColorStop(0, 'rgba(66, 153, 225, 0.2)');
    gradient.addColorStop(1, 'rgba(66, 153, 225, 0)');

    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels.map(label => {
          const date = new Date(label);
          return date.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
          });
        }),
        datasets: [{
          label: 'Incidents',
          data: data.counts,
          borderColor: 'rgb(66, 153, 225)',
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: {
              color: 'rgba(0, 0, 0, 0.05)'
            },
            ticks: {
              stepSize: 1,
              font: {
                size: 11
              }
            }
          },
          x: {
            grid: {
              display: false
            },
            ticks: {
              font: {
                size: 11
              }
            }
          }
        },
        interaction: {
          intersect: false,
          mode: 'index'
        }
      }
    });
  }

  async function updateChart() {
    loading = true;
    error = null;
    const data = await fetchHourlyData();
    if (data) {
      // Wait for the next tick to ensure canvas is mounted
      await new Promise(resolve => setTimeout(resolve, 0));
      createChart(data);
    }
    loading = false;
  }

  onMount(() => {
    // Wait for the component to be fully mounted before initial update
    setTimeout(() => {
      updateChart();
      updateInterval = setInterval(updateChart, 60000); // Update every minute
    }, 0);
  });

  onDestroy(() => {
    if (updateInterval) {
      clearInterval(updateInterval);
    }
    if (chart) {
      chart.destroy();
    }
  });
</script>

<div class="chart-container" in:fade={{ duration: 200 }}>
  <div class="chart-header">
    <h3>Incidents in the Last Hour</h3>
    <div class="chart-legend">
      <div class="legend-item">
        <div class="legend-color"></div>
        <span>Incidents</span>
      </div>
    </div>
  </div>
  
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <span>Loading chart data...</span>
    </div>
  {:else if error}
    <div class="error">
      <span>⚠️</span>
      <span>{error}</span>
    </div>
  {:else}
    <canvas bind:this={chartCanvas}></canvas>
  {/if}
</div>

<style>
  .chart-container {
    background: var(--card-bg);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 4px 20px var(--shadow-color);
    height: 300px;
    position: relative;
  }

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .chart-header h3 {
    margin: 0;
    font-size: 1.1rem;
    color: var(--text-darker);
    font-weight: 600;
  }

  .chart-legend {
    display: flex;
    gap: 1rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .legend-color {
    width: 12px;
    height: 12px;
    background: rgb(66, 153, 225);
    border-radius: 2px;
  }

  canvas {
    width: 100% !important;
    height: calc(100% - 60px) !important;
  }

  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    gap: 1rem;
  }

  .spinner {
    width: 30px;
    height: 30px;
    border: 3px solid rgba(66, 153, 225, 0.1);
    border-radius: 50%;
    border-left-color: rgb(66, 153, 225);
    animation: spin 1s linear infinite;
  }

  .error {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    color: var(--error-color);
    height: 100%;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  @media (max-width: 768px) {
    .chart-container {
      height: 250px;
      padding: 1rem;
    }

    .chart-header {
      margin-bottom: 1rem;
    }

    .chart-header h3 {
      font-size: 1rem;
    }

    .legend-item {
      font-size: 0.8rem;
    }
  }
</style> 